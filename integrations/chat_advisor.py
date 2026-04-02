"""
Chat Advisor — Conversational interface for Mode 2 (Income Goal Planning)

Collects retirement planning fields via a multi-turn conversation using
OpenAI GPT-4.1-mini, then returns structured field data so fin_advisor.py
can calculate the required portfolio without any form entry.
"""

from __future__ import annotations
import os
import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Country-specific defaults
_DEFAULTS = {
    "US": {
        "retirement_age": 65,
        "life_expectancy": 90,
        "tax_rate": 22,
        "growth_rate": 4.0,
        "inflation_rate": 3.0,
    },
    "India": {
        "retirement_age": 60,
        "life_expectancy": 85,
        "tax_rate": 10,
        "growth_rate": 10.0,
        "inflation_rate": 7.0,
    },
}

_REQUIRED_FIELDS = {"country", "birth_year", "retirement_age", "life_expectancy", "target_income"}

SYSTEM_PROMPT_TEMPLATE = """You are a friendly retirement planning assistant for Smart Retire AI.
Your job is to collect a few pieces of information from the user so we can calculate the retirement
portfolio/corpus they need to meet their income goal. Keep the conversation SHORT — aim for 2–3 exchanges total.

Country context: {country}
Currency: {currency}
Portfolio terminology: {corpus_label}

Fields you need:
- country (already {country} — update only if user says otherwise)
- birth_year (personal, must ask)
- target_income — desired after-tax annual income in retirement in {currency} (personal, must ask)
- retirement_age (default {retirement_age})
- life_expectancy (default {life_expectancy})
- tax_rate (default {tax_rate}%)
- growth_rate (default {growth_rate}%)
- inflation_rate (default {inflation_rate}%)
- legacy_goal (default 0)
- life_expenses (default 0)

## Conversation flow — follow this exactly:

TURN 1 (your opening): Ask for country, birth_year, and target_income together in one message.
  The hardcoded opening already does this — if the user's first message answers all three, move to Turn 2.

TURN 2 (after user replies with country + birth_year + target_income): Confirm ALL defaults in one block
  and ask the user to confirm or change any. Format like:
  "Got it! I'll use these defaults for {country} — let me know if you'd like to change anything:
  - Retire at: **{retirement_age}**
  - Plan to age: **{life_expectancy}**
  - Tax rate: **{tax_rate}%**
  - {corpus_label} growth: **{growth_rate}%**
  - Inflation: **{inflation_rate}%**
  - Legacy goal / one-time expenses: **none**

  (blank line — then on its own paragraph:) All good, or anything to adjust?"

  IMPORTANT: If the user said India, use India defaults (retire 60, plan to 85, 10% tax, 10% growth, 7% inflation).
  If the user said US, use US defaults (retire 65, plan to 90, 22% tax, 4% growth, 3% inflation).

TURN 3+: If user says "looks good" or similar → set done=true. If user changes a value, update
  it and confirm the change, then set done=true on that same response.

## Rules:
- NEVER ask for fields one at a time after the opening — present all defaults in Turn 2.
- Support what-if questions at any point. If user says "what if I retire at 60?", update
  retirement_age to 60 and reflect it in the __data__ block immediately.
- Be concise and warm. Skip filler phrases.
- target_income is ANNUAL. ONLY ask "Just to confirm — is that monthly or annual?" if the
  number is clearly too small to be a full-year income: below {currency}20,000 for US, or below
  {currency}1,50,000 for India. If the number is at or above that threshold, treat it as annual
  WITHOUT asking — never flag large numbers like $100,000 or ₹10,00,000.
- Never re-ask for fields the user has already provided (e.g. birth_year). If the user changes
  country mid-conversation, keep all confirmed fields and only update the country-specific defaults
  (retirement_age, life_expectancy, tax_rate, growth_rate, inflation_rate).
- Always end every message with a JSON block on its own line (no markdown fences):
  __data__: {{"country": "US", "birth_year": 1980, "retirement_age": 65, "life_expectancy": 90, "target_income": 80000, "tax_rate": 22, "growth_rate": 4.0, "inflation_rate": 3.0, "legacy_goal": 0, "life_expenses": 0, "done": false}}
  Use null for fields not yet known. Set "done": true only when all required fields are confirmed.

Required fields (must not be null before done=true): birth_year, target_income, retirement_age, life_expectancy.

## Explaining calculations:
A [CALCULATION CONTEXT] block may appear as a system message containing the actual computed
numbers and formula breakdown. If the user asks how the corpus/portfolio number was calculated
(e.g. "how did you come up with that?", "explain the calculation", "walk me through the math"),
use those numbers to explain step by step:
  1. Gross income needed before tax — target income ÷ (1 − tax_rate)
  2. Annuity present-value (PV) factor — derived from growth rate, inflation rate, and years in retirement;
     gives intuition for how many years of gross withdrawal the corpus must cover in today's money
  3. How the corpus was found: a year-by-year simulation found the minimum starting balance such that
     withdrawals (growing with inflation) last the full retirement period at the given growth rate
  4. Use the exact corpus figure from the context — the PV factor is for intuition only
Be friendly and educational. Use the exact numbers from the context — never invent values.
Never use backtick or code formatting for numbers or currency values — write them as plain text.
After giving the explanation, still append the __data__ block with the last known field values and done=true."""


def build_system_prompt(country: str = "US") -> str:
    d = _DEFAULTS.get(country, _DEFAULTS["US"])
    currency = "₹" if country == "India" else "$"
    corpus_label = "Corpus" if country == "India" else "Portfolio"
    return SYSTEM_PROMPT_TEMPLATE.format(
        country=country,
        currency=currency,
        corpus_label=corpus_label,
        retirement_age=d["retirement_age"],
        life_expectancy=d["life_expectancy"],
        tax_rate=d["tax_rate"],
        growth_rate=d["growth_rate"],
        inflation_rate=d["inflation_rate"],
    )


def _parse_data_block(text: str) -> tuple[str, dict]:
    """Extract and remove the __data__ JSON block from the assistant message.

    Returns (clean_message, fields_dict). fields_dict is empty if not found.
    """
    pattern = r"__data__:\s*(\{.*\})\s*$"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        return text.strip(), {}

    clean = text[: match.start()].strip()
    try:
        fields = json.loads(match.group(1))
    except json.JSONDecodeError:
        logger.warning("Failed to parse __data__ block: %s", match.group(1))
        fields = {}

    return clean, fields


def chat_with_advisor(
    messages: list[dict],
    country: str = "US",
    openai_api_key: Optional[str] = None,
    calc_context: Optional[str] = None,
) -> tuple[str, dict]:
    """Send conversation history to GPT-4.1-mini and return (display_message, extracted_fields).

    messages: list of {"role": "user"/"assistant", "content": "..."}
    Returns:
        display_message: assistant text with __data__ block stripped
        extracted_fields: dict of field values (nulls filtered out), plus "done" bool
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package is required. Run: pip install openai>=1.0.0")

    api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not set. Add it to your .env file or Streamlit secrets."
        )

    client = OpenAI(api_key=api_key)

    system_prompt = build_system_prompt(country)
    full_messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if calc_context:
        full_messages.append({"role": "system", "content": calc_context})
    full_messages += messages

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=full_messages,
        temperature=0.4,
        max_tokens=900,
    )

    raw = response.choices[0].message.content or ""
    display_message, fields = _parse_data_block(raw)

    # Strip null values so callers only see confirmed fields
    confirmed = {k: v for k, v in fields.items() if v is not None and k != "done"}
    confirmed["done"] = bool(fields.get("done", False))

    return display_message, confirmed


def fields_are_complete(fields: dict) -> bool:
    """True when all required fields have non-null confirmed values."""
    return all(fields.get(f) is not None for f in _REQUIRED_FIELDS)
