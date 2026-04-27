"""
Pure Python Financial Statement Processor

Drop-in replacement for the n8n workflow. Accepts the same file inputs as N8NClient
and returns the same response dict structure — no n8n subscription required.

Env vars:
    OPENAI_API_KEY   — required
    OPENAI_MODEL     — override model (default: gpt-4.1-mini)
"""

import os
import io
import re
import json
import time
import logging
from typing import Callable, List, Dict, Optional, Tuple, Union, BinaryIO

from pypdf import PdfReader
import openai

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — verbatim copy from the n8n "AI Agent" node systemMessage
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """You are a financial document extraction engine.

Your task is to read financial documents (PDF text already extracted upstream)
and return a single structured JSON object containing ONLY explicitly stated
financial facts, with ALL personally identifiable information (PII) removed.

You MUST NOT interpret tax rules, retirement rules, income eligibility,
usage restrictions, or future implications.
You MUST NOT classify accounts beyond basic account type identification.

====================================================================
GLOBAL PRECEDENCE RULES (HIGHEST PRIORITY)
====================================================================
1. Extract ONLY what is explicitly stated in the document.
2. NEVER infer, calculate, estimate, net, or impute values.
3. NEVER discard explicit balances or summaries due to perceived redundancy.
4. NEVER override an explicit rule with a later instruction.
5. When rules conflict, follow this precedence order:
   (1) GLOBAL PRECEDENCE RULES
   (2) PII REMOVAL RULES
   (3) BALANCE EXTRACTION RULES
   (4) ACCOUNT-TYPE-SPECIFIC ALLOWED EXTRACTIONS
   (5) RAW FACT EXTENSIONS (Tax Sources, Contributions, Basis)
   (6) WARNINGS

====================================================================
CORE OBJECTIVE
====================================================================
Extract explicit final balances for each account found in the document.

Accepted balance labels include:
- "Ending Balance"
- "Ending Account Value"
- "Total Ending Value"
- "Vested Balance" (ONLY for stock plan accounts)

====================================================================
STRICT BALANCE EXTRACTION RULES
====================================================================
1. Output VALID JSON ONLY. No markdown, no commentary.
2. Extract balances ONLY if explicitly stated.
3. Prefer ENDING balances over beginning, average, or projected values.
4. For stock plans:
   - Extract VESTED balance only
   - Ignore unvested, potential, estimated, or hypothetical values
5. If multiple balances exist for the same account:
   - Prefer Ending Balance
   - Else Ending Account Value
   - Else Total Ending Value
   - Else Vested Balance (stock plans only)
6. Deduplicate repeated balances across pages.
7. Currency must be numeric (no symbols, no commas).
8. Dates must be ISO-8601 (YYYY-MM-DD) when available.
9. If unclear, set value to null and add a warning.

====================================================================
PII REMOVAL RULES (ABSOLUTE)
====================================================================
DO NOT output:
- names (full or partial)
- addresses
- phone numbers
- email addresses
- SSNs / tax IDs
- full account numbers
- employee IDs
- grant IDs
- reference numbers

ALLOWED:
- institution name (e.g., Fidelity, Morgan Stanley)
- generic account labels (e.g., "Savings Account", "401k", "HSA")
- last 4 digits of account number ONLY if explicitly labeled as such

Never mask or partially redact PII — exclude it entirely.

====================================================================
OUTPUT STRUCTURE
====================================================================
{
  "document_metadata": {},
  "accounts": [],
  "warnings": []
}

====================================================================
DOCUMENT METADATA (NO PII)
====================================================================
document_metadata = {
  "source_institution": string | null,
  "document_type": one of [
    "bank_statement",
    "brokerage_statement",
    "retirement_statement",
    "stock_plan_statement",
    "unknown"
  ],
  "statement_start_date": YYYY-MM-DD | null,
  "statement_end_date": YYYY-MM-DD | null
}

====================================================================
ACCOUNT OBJECT (NO INTERPRETATION)
====================================================================
accounts[] = {
  "account_id": string,                 // synthetic, generated ID
  "institution": string | null,
  "account_name": string | null,        // generic label only
  "account_number_last4": string | null,
  "account_type": one of [
    "checking",
    "savings",
    "brokerage",
    "401k",
    "roth_401k",
    "ira",
    "roth_ira",
    "hsa",
    "stock_plan",
    "unknown"
  ],
  "ending_balance": number | null,
  "balance_as_of_date": YYYY-MM-DD | null,
  "currency": "USD"
}

====================================================================
ACCOUNT-TYPE-SPECIFIC ALLOWED EXTRACTIONS
====================================================================
These rules DEFINE what may be extracted.
They do NOT override balance extraction rules.

- Retirement accounts (401k / 403b / 457):
  - ending_balance (required)
  - raw_tax_sources (optional, explicit only)
  - raw_contributions (optional, explicit only)

- Brokerage accounts:
  - ending_balance (required)
  - raw_basis (optional, explicit only)

- Bank accounts (checking / savings):
  - ending_balance only

- HSA:
  - ending_balance
  - raw_contributions (optional)

- Stock plans:
  - vested ending_balance only

====================================================================
SPECIAL HANDLING
====================================================================
- If a document contains multiple accounts, extract EACH separately.
- Ignore household or portfolio totals if individual account balances exist.
- Ignore transactions, holdings, income, gains/losses, projections, charts.
- Ignore any data tied to an identifiable person.

====================================================================
RAW TAX SOURCE EXTRACTION (NO INTERPRETATION)
====================================================================
If a retirement statement explicitly lists BALANCES by contribution or source
type (e.g., "Employee Deferral", "Roth In-Plan Conversion", "After-Tax"):

- Extract those balances verbatim
- Do NOT infer tax treatment
- Do NOT classify or label behavior
- Do NOT create new accounts

Output as:

"raw_tax_sources": [
  {
    "label": string,
    "balance": number
  }
]

IMPORTANT CLARIFICATION:
Tables labeled "Contribution Summary", "Source Summary", or similar,
that list BALANCES by contribution type (not transaction activity),
are authoritative balance ledgers and MUST be extracted here
when balances are explicitly stated.

Only include this field if balances are explicitly stated and vested.

====================================================================
WARNINGS
====================================================================
Add a short, non-PII warning if:
- multiple conflicting ending balances exist
- account type cannot be determined
- statement period is missing

====================================================================
FINAL OUTPUT
====================================================================
Return ONE JSON object containing all extracted balances and raw facts.
"""

# ---------------------------------------------------------------------------
# Classification map — port of n8n "Classify Account" JS node
# (tax_treatment, purpose, income_eligibility, classification_confidence)
# ---------------------------------------------------------------------------
_CLASSIFY_MAP: Dict[str, Tuple[str, str, str, float]] = {
    "checking":   ("post_tax",    "general_income",          "eligible",               0.95),
    "savings":    ("post_tax",    "general_income",          "eligible",               0.95),
    "brokerage":  ("post_tax",    "general_income",          "eligible",               0.95),
    "401k":       ("tax_deferred","income",                  "eligible",               0.95),
    "403b":       ("tax_deferred","income",                  "eligible",               0.95),
    "457":        ("tax_deferred","income",                  "eligible",               0.95),
    "ira":        ("tax_deferred","income",                  "eligible",               0.95),
    "roth_401k":  ("tax_free",    "income",                  "eligible",               0.95),
    "roth_ira":   ("tax_free",    "income",                  "eligible",               0.95),
    "hsa":        ("tax_free",    "healthcare_only",         "conditionally_eligible", 0.90),
    "stock_plan": ("post_tax",    "employment_compensation", "eligible",               0.85),
}

# Tax bucket label matching — port of n8n "Tax Bucket Decomposition" JS node
# Each entry: (substrings_to_match, bucket_type, tax_treatment)
_BUCKET_LABEL_MAP: List[Tuple[List[str], str, str]] = [
    (["employee deferral", "traditional"], "traditional_401k",        "tax_deferred"),
    (["roth in-plan", "roth in plan", "roth conversion", "roth contribution", "roth"],
                                          "roth_in_plan_conversion",  "tax_free"),
    (["after-tax", "after tax"],           "after_tax_401k",           "post_tax"),
]

_RETIREMENT_TYPES = {"401k", "403b", "457"}

# Chunk threshold: join all pages unless text exceeds this (falls back to 5-page chunks)
_MAX_CHUNK_CHARS = 150_000

# Institution name normalisation — strips generic suffixes so "Fidelity" and
# "Fidelity Brokerage Services LLC" both key to "fidelity".
_INSTITUTION_DROP_WORDS = {
    "brokerage", "services", "service", "financial", "bank", "investments",
    "investment", "securities", "advisors", "advisory", "group", "trust",
    "wealth", "management", "asset", "assets", "fund", "funds", "capital",
}


def _normalize_institution(inst: str) -> str:
    words = inst.lower().strip().split()
    for word in words:
        clean = re.sub(r"[^a-z0-9]", "", word)
        if clean and clean not in _INSTITUTION_DROP_WORDS:
            return clean
    return words[0] if words else "unknown"


class StatementProcessorError(Exception):
    """Base exception for StatementProcessor errors."""


class StatementProcessor:
    """
    Pure Python replacement for the n8n financial statement processing workflow.

    Interface is identical to N8NClient so it can be swapped in without changing
    any calling code.
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        timeout: int = 120,
        max_retries: int = 2,
    ) -> None:
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise StatementProcessorError(
                "OPENAI_API_KEY not set. Provide it via environment variable or openai_api_key parameter."
            )
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout)
        self._model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self._temperature = temperature
        self._max_retries = max_retries
        self._token_usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        logger.info("StatementProcessor initialised (model=%s)", self._model)

    # ------------------------------------------------------------------
    # Public interface — identical to N8NClient.upload_statements()
    # ------------------------------------------------------------------

    def upload_statements(
        self,
        files: Union[List[BinaryIO], List[bytes], List[tuple]],
        progress_callback: Optional[Callable[[str, int, int, str, int, int], None]] = None,
    ) -> Dict:
        """Process uploaded statement files.

        progress_callback(stage, file_index, total_files, filename, chunk_index, total_chunks)
        Stages: "text_extract", "ai_call", "file_done"
        """
        start = time.time()
        self._token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        try:
            normalised = self._normalize_files(files)
        except Exception as exc:
            return {"success": False, "error": str(exc), "execution_time": time.time() - start}

        all_accounts: List[Dict] = []
        all_warnings: List[str] = []
        total_files = len(normalised)

        for file_index, (filename, file_bytes) in enumerate(normalised):
            try:
                accounts, warnings = self._process_file(
                    filename, file_bytes,
                    file_index=file_index,
                    total_files=total_files,
                    progress_callback=progress_callback,
                )
                all_accounts.extend(accounts)
                all_warnings.extend(warnings)
                if progress_callback:
                    progress_callback("file_done", file_index, total_files, filename, 0, 1)
            except Exception as exc:
                all_warnings.append(f"Error processing {filename}: {exc}")
                logger.exception("Error processing %s", filename)

        # Cross-file deduplication
        all_accounts, dedup_warnings = self._dedup_accounts(all_accounts)
        all_warnings.extend(dedup_warnings)

        # Cross-file duplicate account warning — verbatim logic from n8n_client.py lines 390–409
        seen_account_ids: Dict[str, str] = {}
        for account in all_accounts:
            acct_id = account.get("account_id") or account.get("account_name")
            last4 = str(account.get("account_number_last4", "")).strip()
            dedup_key = last4 if last4 and last4 not in ("", "nan", "None") else acct_id
            if not dedup_key:
                continue
            source_file = account.get("_document_metadata", {}).get("source_file", "unknown file")
            if dedup_key in seen_account_ids:
                prev_file = seen_account_ids[dedup_key]
                if prev_file != source_file:
                    label = f"…{last4}" if last4 and last4 not in ("", "nan", "None") else acct_id
                    all_warnings.append(
                        f"Duplicate account detected ({label}) appears in both "
                        f"'{prev_file}' and '{source_file}' — review to avoid double-counting assets"
                    )
            else:
                seen_account_ids[dedup_key] = source_file

        if not all_accounts:
            return {
                "success": False,
                "error": "No accounts found in any uploaded document",
                "execution_time": time.time() - start,
                "token_usage": dict(self._token_usage),
            }

        return {
            "success": True,
            "data": all_accounts,
            "format": "json",
            "rows_extracted": len(all_accounts),
            "has_data": True,
            "warnings": all_warnings,
            "execution_time": time.time() - start,
            "token_usage": dict(self._token_usage),
        }

    # ------------------------------------------------------------------
    # File-level processing
    # ------------------------------------------------------------------

    def _process_file(
        self,
        filename: str,
        file_bytes: bytes,
        file_index: int = 0,
        total_files: int = 1,
        progress_callback: Optional[Callable[[str, int, int, str, int, int], None]] = None,
    ) -> Tuple[List[Dict], List[str]]:
        warnings: List[str] = []

        if progress_callback:
            progress_callback("text_extract", file_index, total_files, filename, 0, 1)

        text, extract_warnings = self._extract_text(file_bytes, filename)
        warnings.extend(extract_warnings)

        if not text.strip():
            warnings.append(f"{filename}: no extractable text found — may be a scanned-only PDF.")
            return [], warnings

        chunks = self._chunk_text(text, filename)
        total_chunks = len(chunks)
        all_accounts: List[Dict] = []

        for chunk_idx, (chunk_text, chunk_label) in enumerate(chunks):
            if progress_callback:
                progress_callback("ai_call", file_index, total_files, filename, chunk_idx, total_chunks)
            raw, ai_warnings = self._call_ai(chunk_text, chunk_label)
            warnings.extend(ai_warnings)
            if raw is None:
                continue

            doc_meta = raw.get("document_metadata", {})
            doc_meta["source_file"] = filename

            for account in raw.get("accounts", []):
                # Match n8n_client.py line 349: attach _document_metadata
                account["_document_metadata"] = doc_meta

                # Match n8n_client.py lines 354–358: rename raw_tax_sources → _raw_tax_sources
                if "raw_tax_sources" in account:
                    account["_raw_tax_sources"] = account.pop("raw_tax_sources")

                # Match n8n_client.py lines 364–366: rename raw_contributions → _raw_contributions
                if "raw_contributions" in account:
                    account["_raw_contributions"] = account.pop("raw_contributions")

                # Match n8n_client.py lines 370–378: skip accounts with no ending_balance
                ending_balance = account.get("ending_balance")
                if ending_balance is None or ending_balance == "":
                    name = account.get("account_name", "Unknown account")
                    warnings.append(
                        f"Excluded {name}: no vested balance available (typically unvested stocks)"
                    )
                    continue

                # Single-pass post-processing (classify + prune-flag + tax buckets)
                account = self._process_account(account)
                all_accounts.append(account)

            warnings.extend(raw.get("warnings", []))

        # Pruning pass (needs the full file account list for cross-account brokerage check)
        all_accounts, prune_warnings = self._prune_flagged(all_accounts)
        warnings.extend(prune_warnings)

        # Within-file deduplication
        all_accounts, dedup_warnings = self._dedup_accounts(all_accounts)
        warnings.extend(dedup_warnings)

        return all_accounts, warnings

    # ------------------------------------------------------------------
    # PDF extraction
    # ------------------------------------------------------------------

    def _extract_text(self, file_bytes: bytes, filename: str) -> Tuple[str, List[str]]:
        warnings: List[str] = []
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
        except Exception as exc:
            return "", [f"{filename}: could not open PDF — {exc}"]

        # Silence pypdf._cmap encoding noise — these warnings ("illegal character",
        # "could not find 'cmap'", etc.) are internal PDF renderer issues that the
        # user cannot act on.  Route them to debug-level logging only.
        cmap_logger = logging.getLogger("pypdf._cmap")
        cmap_logger.setLevel(logging.ERROR)

        page_texts: List[str] = []
        for i, page in enumerate(reader.pages, start=1):
            logger.debug("pypdf extracting: %s — page %d/%d", filename, i, len(reader.pages))
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text.replace(" ", "").replace("\n", ""):
                page_texts.append(text)

        return "\n".join(page_texts), warnings

    def _chunk_text(self, text: str, filename: str) -> List[Tuple[str, str]]:
        """Return [(chunk_text, label)] — usually one item (the whole doc)."""
        if len(text) <= _MAX_CHUNK_CHARS:
            return [(text, filename)]

        # Split into 5-page-equivalent chunks by character count
        chunk_size = _MAX_CHUNK_CHARS
        chunks = []
        i = 0
        part = 1
        while i < len(text):
            chunk = text[i : i + chunk_size]
            chunks.append((chunk, f"{filename} (part {part})"))
            i += chunk_size
            part += 1
        logger.info("%s is large (%d chars), split into %d chunks", filename, len(text), len(chunks))
        return chunks

    # ------------------------------------------------------------------
    # AI call
    # ------------------------------------------------------------------

    def _call_ai(self, text: str, label: str) -> Tuple[Optional[Dict], List[str]]:
        """Call the OpenAI API with the exact prompt from the n8n workflow."""
        warnings: List[str] = []
        user_message = f"Extract structured CSV from the following OCR text: {text}"

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    temperature=self._temperature,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                )
                raw_content = response.choices[0].message.content or ""
                if response.usage:
                    self._token_usage["prompt_tokens"] += response.usage.prompt_tokens
                    self._token_usage["completion_tokens"] += response.usage.completion_tokens
                    self._token_usage["total_tokens"] += response.usage.total_tokens
                parsed = self._repair_json(raw_content)
                if parsed is None:
                    warnings.append(f"{label}: AI returned malformed JSON — skipped.")
                return parsed, warnings
            except openai.RateLimitError:
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)
                else:
                    warnings.append(f"{label}: OpenAI rate limit exceeded after {self._max_retries} retries.")
                    return None, warnings
            except openai.APIError as exc:
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)
                else:
                    warnings.append(f"{label}: OpenAI API error — {exc}")
                    return None, warnings

        return None, warnings

    def _repair_json(self, raw: str) -> Optional[Dict]:
        """Strip markdown fences and parse JSON; regex fallback for embedded objects."""
        # Strip ```json ... ``` or ``` ... ```
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "accounts" in parsed:
                return parsed
            # Minimal valid structure if 'accounts' missing
            return {"document_metadata": {}, "accounts": [], "warnings": []}
        except json.JSONDecodeError:
            pass

        # Regex fallback: find first {...} block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        return None

    # ------------------------------------------------------------------
    # Single-pass account processing
    # ------------------------------------------------------------------

    def _process_account(self, account: Dict) -> Dict:
        """classify + mark for pruning + decompose tax buckets — one loop."""
        account = self._classify(account)
        account = self._mark_for_pruning(account)
        account = self._decompose_buckets(account)
        return account

    def _classify(self, account: Dict) -> Dict:
        """Port of n8n 'Classify Account' JS node."""
        acct_type = (account.get("account_type") or "").lower().strip()
        name = (account.get("account_name") or "").lower()

        # 529 check by name
        if "529" in name:
            account["tax_treatment"] = "tax_free"
            account["purpose"] = "education_only"
            account["income_eligibility"] = "not_eligible"
            account["classification_confidence"] = 0.90
            return account

        if acct_type in _CLASSIFY_MAP:
            tx, purpose, eligibility, conf = _CLASSIFY_MAP[acct_type]
        else:
            tx, purpose, eligibility, conf = "unknown", "restricted_other", "conditionally_eligible", 0.60

        account["tax_treatment"] = account.get("tax_treatment") or tx
        account["purpose"] = purpose
        account["income_eligibility"] = eligibility
        account["classification_confidence"] = conf
        return account

    def _mark_for_pruning(self, account: Dict) -> Dict:
        """Mark accounts that may be pruned; final decision made in _prune_flagged."""
        name = (account.get("account_name") or "").lower()
        acct_type = (account.get("account_type") or "").lower()

        is_cash_like = any(kw in name for kw in ("cash", "money market", "mmf", "bank deposit"))
        is_unvested_stock = acct_type == "stock_plan" and account.get("ending_balance") is None

        # Stock plan summary rows embedded in brokerage statements show "Potential Value"
        # (all unvested RSUs). They have no account number and no exercisable balance.
        # The system prompt says to ignore these, but full-document AI sometimes picks them up.
        bal = account.get("ending_balance")
        is_embedded_stock_summary = (
            acct_type == "stock_plan"
            and bal is not None
            and bal > 0
            and not account.get("account_number_last4")
        )

        if is_cash_like or is_unvested_stock or is_embedded_stock_summary:
            account["_prune"] = True
        return account

    def _prune_flagged(self, accounts: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """Port of n8n 'Account Pruning & De-duplication' JS node pruning logic."""
        warnings: List[str] = []
        kept: List[Dict] = []

        brokerage_accounts = [
            a for a in accounts
            if (a.get("account_type") or "").lower() == "brokerage"
            and a.get("ending_balance") is not None
        ]

        for account in accounts:
            if not account.get("_prune"):
                kept.append(account)
                continue

            name = (account.get("account_name") or "").lower()
            acct_type = (account.get("account_type") or "").lower()

            # Unvested stock (null balance): always remove
            if acct_type == "stock_plan" and account.get("ending_balance") is None:
                warnings.append("Stock Plan account found without explicit vested balance; excluded.")
                continue

            # Embedded stock plan summary (non-null balance, no account number): remove if a
            # brokerage at the same institution exists — this is an unvested "Potential Value"
            # row from a stock plan summary page inside a brokerage statement.
            if acct_type == "stock_plan" and not account.get("account_number_last4"):
                institution = account.get("institution")
                norm_inst = _normalize_institution(institution or "")
                has_sibling_brokerage = any(
                    _normalize_institution(b.get("institution") or "") == norm_inst
                    for b in brokerage_accounts
                )
                if has_sibling_brokerage:
                    warnings.append(
                        f"Stock Plan summary row at {institution!r} excluded — "
                        "balance likely reflects unvested/potential value, not exercisable shares."
                    )
                    continue
                else:
                    # No brokerage sibling — keep with a warning
                    warnings.append(
                        f"Stock Plan account at {institution!r} has no account number; "
                        "verify this reflects a vested/exercisable balance."
                    )
                    account.pop("_prune", None)
                    kept.append(account)
                    continue

            # Cash/MMF: only remove if a parent brokerage at same institution exists with larger balance
            institution = account.get("institution")
            norm_inst = _normalize_institution(institution or "")
            balance = account.get("ending_balance") or 0
            has_parent_brokerage = any(
                _normalize_institution(b.get("institution") or "") == norm_inst
                and (b.get("ending_balance") or 0) > balance
                for b in brokerage_accounts
            )
            if has_parent_brokerage:
                warnings.append(
                    f"Cash/MMF line item \"{account.get('account_name')}\" collapsed into brokerage account."
                )
            else:
                # No parent brokerage — keep it
                account.pop("_prune", None)
                kept.append(account)
                continue

        # Strip internal flag from kept accounts
        for a in kept:
            a.pop("_prune", None)

        return kept, warnings

    def _decompose_buckets(self, account: Dict) -> Dict:
        """Port of n8n 'Tax Bucket Decomposition' JS node."""
        acct_type = (account.get("account_type") or "").lower()
        if acct_type not in _RETIREMENT_TYPES:
            return account

        raw_sources = account.get("_raw_tax_sources", [])
        if not raw_sources:
            return account

        buckets = []
        for source in raw_sources:
            label = (source.get("label") or "").lower()
            balance = source.get("balance", 0)
            matched = False
            for patterns, bucket_type, bucket_tax in _BUCKET_LABEL_MAP:
                if any(p in label for p in patterns):
                    buckets.append({
                        "bucket_type": bucket_type,
                        "tax_treatment": bucket_tax,
                        "balance": balance,
                    })
                    matched = True
                    break
            if not matched and balance:
                buckets.append({
                    "bucket_type": "unknown",
                    "tax_treatment": "unknown",
                    "balance": balance,
                })

        if not buckets:
            return account

        ending = account.get("ending_balance") or 0
        bucket_sum = sum(b["balance"] for b in buckets)
        if abs(bucket_sum - ending) > 0.01:
            account.setdefault("_document_metadata", {})
            acct_id = account.get("account_id", "unknown")
            # Still attach — matches n8n JS behaviour (warning only, not discarded)
            logger.warning(
                "Tax bucket balances do not reconcile for account %s (sum=%.2f vs balance=%.2f)",
                acct_id, bucket_sum, ending,
            )

        account["tax_buckets"] = buckets
        return account

    # ------------------------------------------------------------------
    # Deduplication — port of n8n "Account Identity & Deduplication" JS node
    # ------------------------------------------------------------------

    def _dedup_accounts(self, accounts: List[Dict]) -> Tuple[List[Dict], List[str]]:
        warnings: List[str] = []
        grouped: Dict[str, List[Dict]] = {}

        for acc in accounts:
            fp = self._fingerprint(acc)
            grouped.setdefault(fp, []).append(acc)

        deduped: List[Dict] = []
        for group in grouped.values():
            if len(group) == 1:
                deduped.append(group[0])
                continue
            winner = group[0]
            for challenger in group[1:]:
                chosen = self._choose_winner(winner, challenger)
                loser = challenger if chosen is winner else winner
                warnings.append(
                    f"Duplicate or overlapping statement detected for account "
                    f"\"{loser.get('account_name')}\". Older or less complete entry removed."
                )
                winner = chosen
            deduped.append(winner)

        return deduped, warnings

    @staticmethod
    def _fingerprint(account: Dict) -> str:
        institution = _normalize_institution(account.get("institution") or "unknown")
        last4 = (account.get("account_number_last4") or "").strip()
        account_type = (account.get("account_type") or "").lower().strip()
        if last4:
            # Account number is a stable unique identifier — immune to AI name variation
            parts = [institution, last4, account_type]
        else:
            parts = [
                institution,
                (account.get("account_name") or "").lower().strip(),
                account_type,
                (account.get("currency") or "USD").lower().strip(),
            ]
        return "|".join(parts)

    @staticmethod
    def _completeness_score(account: Dict) -> int:
        score = 0
        if account.get("ending_balance") is not None:
            score += 2
        if account.get("tax_buckets"):
            score += 2
        if account.get("balance_as_of_date"):
            score += 1
        return score

    def _choose_winner(self, a: Dict, b: Dict) -> Dict:
        date_a = a.get("balance_as_of_date") or ""
        date_b = b.get("balance_as_of_date") or ""
        if date_a and date_b:
            if date_a > date_b:
                return a
            if date_b > date_a:
                return b
        score_a = self._completeness_score(a)
        score_b = self._completeness_score(b)
        return a if score_a >= score_b else b

    # ------------------------------------------------------------------
    # File normalisation — same contract as N8NClient._prepare_files()
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_files(
        files: Union[List[BinaryIO], List[bytes], List[tuple]],
    ) -> List[Tuple[str, bytes]]:
        result: List[Tuple[str, bytes]] = []
        for i, f in enumerate(files):
            if isinstance(f, tuple):
                name, data = f[0], f[1]
                if hasattr(data, "read"):
                    data = data.read()
                result.append((str(name), bytes(data)))
            elif isinstance(f, (bytes, bytearray)):
                result.append((f"document_{i + 1}.pdf", bytes(f)))
            elif hasattr(f, "read"):
                name = getattr(f, "name", f"document_{i + 1}.pdf")
                result.append((str(name), f.read()))
            else:
                raise StatementProcessorError(f"Unsupported file type at index {i}: {type(f)}")
        return result
