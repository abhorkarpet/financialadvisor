"""
Unit tests for integrations/statement_processor.py — all pure/deterministic methods.

No OpenAI API calls are made: the StatementProcessor is constructed with a fake key
(the openai client is initialised but never called by these tests).
"""

import unittest
import io
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch openai.OpenAI at import time so constructing StatementProcessor doesn't
# require a real key to be validated by the SDK.
_mock_openai = patch("openai.OpenAI", MagicMock())
_mock_openai.start()

from integrations.statement_processor import (
    StatementProcessor,
    StatementProcessorError,
    _normalize_institution,
)

_mock_openai.stop()


def _make_sp() -> StatementProcessor:
    """Return a StatementProcessor backed by a mock OpenAI client."""
    with patch("openai.OpenAI", MagicMock()):
        return StatementProcessor(openai_api_key="sk-fake-test-key")


class TestNormalizeInstitution(unittest.TestCase):

    def test_simple_name(self):
        self.assertEqual(_normalize_institution("Fidelity"), "fidelity")

    def test_drops_generic_suffixes(self):
        self.assertEqual(_normalize_institution("Fidelity Brokerage Services LLC"), "fidelity")

    def test_multi_word_institution(self):
        # "Morgan Stanley" — first non-drop word
        self.assertEqual(_normalize_institution("Morgan Stanley"), "morgan")

    def test_vanguard_financial(self):
        self.assertEqual(_normalize_institution("Vanguard Financial"), "vanguard")

    def test_empty_string(self):
        # Falls through to "unknown"
        result = _normalize_institution("")
        self.assertIsInstance(result, str)

    def test_all_drop_words(self):
        # All words are generic suffixes — returns first word after stripping punctuation
        result = _normalize_institution("Financial Brokerage Services")
        self.assertIsInstance(result, str)


class TestRepairJson(unittest.TestCase):

    def setUp(self):
        self.sp = _make_sp()

    def test_valid_json_with_accounts(self):
        raw = '{"document_metadata": {}, "accounts": [{"account_id": "1"}], "warnings": []}'
        result = self.sp._repair_json(raw)
        self.assertIsNotNone(result)
        self.assertIn("accounts", result)
        self.assertEqual(len(result["accounts"]), 1)

    def test_strips_markdown_fences(self):
        raw = '```json\n{"document_metadata": {}, "accounts": [], "warnings": []}\n```'
        result = self.sp._repair_json(raw)
        self.assertIsNotNone(result)
        self.assertIn("accounts", result)

    def test_valid_json_without_accounts_key(self):
        raw = '{"document_metadata": {}, "warnings": []}'
        result = self.sp._repair_json(raw)
        # Should return minimal structure, not None
        self.assertIsNotNone(result)
        self.assertEqual(result.get("accounts"), [])

    def test_embedded_json_regex_fallback(self):
        raw = 'Some preamble {"document_metadata": {}, "accounts": [], "warnings": []} trailing text'
        result = self.sp._repair_json(raw)
        self.assertIsNotNone(result)

    def test_completely_invalid_returns_none(self):
        result = self.sp._repair_json("this is not json at all %%% {{{}}")
        self.assertIsNone(result)

    def test_empty_string_returns_none(self):
        result = self.sp._repair_json("")
        self.assertIsNone(result)


class TestClassify(unittest.TestCase):

    def setUp(self):
        self.sp = _make_sp()

    def _classify(self, account_type, account_name=""):
        acc = {"account_type": account_type, "account_name": account_name}
        return self.sp._classify(acc)

    def test_401k(self):
        result = self._classify("401k")
        self.assertEqual(result["tax_treatment"], "tax_deferred")
        self.assertEqual(result["purpose"], "income")
        self.assertEqual(result["income_eligibility"], "eligible")
        self.assertEqual(result["classification_confidence"], 0.95)

    def test_roth_ira(self):
        result = self._classify("roth_ira")
        self.assertEqual(result["tax_treatment"], "tax_free")

    def test_hsa(self):
        result = self._classify("hsa")
        self.assertEqual(result["tax_treatment"], "tax_free")
        self.assertEqual(result["purpose"], "healthcare_only")
        self.assertEqual(result["income_eligibility"], "conditionally_eligible")
        self.assertEqual(result["classification_confidence"], 0.90)

    def test_brokerage(self):
        result = self._classify("brokerage")
        self.assertEqual(result["tax_treatment"], "post_tax")
        self.assertEqual(result["purpose"], "general_income")

    def test_unknown_type_fallback(self):
        result = self._classify("mystery_account")
        self.assertEqual(result["tax_treatment"], "unknown")
        self.assertEqual(result["purpose"], "restricted_other")
        self.assertEqual(result["classification_confidence"], 0.60)

    def test_529_by_name_overrides_type(self):
        result = self._classify("checking", account_name="529 College Savings")
        self.assertEqual(result["tax_treatment"], "tax_free")
        self.assertEqual(result["purpose"], "education_only")
        self.assertEqual(result["income_eligibility"], "not_eligible")
        self.assertEqual(result["classification_confidence"], 0.90)

    def test_ira(self):
        result = self._classify("ira")
        self.assertEqual(result["tax_treatment"], "tax_deferred")

    def test_roth_401k(self):
        result = self._classify("roth_401k")
        self.assertEqual(result["tax_treatment"], "tax_free")

    def test_stock_plan(self):
        result = self._classify("stock_plan")
        self.assertEqual(result["tax_treatment"], "post_tax")
        self.assertEqual(result["purpose"], "employment_compensation")


class TestMarkForPruning(unittest.TestCase):

    def setUp(self):
        self.sp = _make_sp()

    def _mark(self, account):
        return self.sp._mark_for_pruning(account)

    def test_cash_account_flagged(self):
        acc = {"account_name": "Cash & Money Market", "account_type": "brokerage", "ending_balance": 5000}
        result = self._mark(acc)
        self.assertTrue(result.get("_prune"))

    def test_mmf_account_flagged(self):
        acc = {"account_name": "Fidelity MMF", "account_type": "brokerage", "ending_balance": 1000}
        result = self._mark(acc)
        self.assertTrue(result.get("_prune"))

    def test_stock_plan_no_balance_flagged(self):
        acc = {"account_name": "RSU Plan", "account_type": "stock_plan", "ending_balance": None}
        result = self._mark(acc)
        self.assertTrue(result.get("_prune"))

    def test_embedded_stock_plan_no_last4_flagged(self):
        acc = {
            "account_name": "Stock Plan",
            "account_type": "stock_plan",
            "ending_balance": 50000,
            "account_number_last4": None,
        }
        result = self._mark(acc)
        self.assertTrue(result.get("_prune"))

    def test_normal_401k_not_flagged(self):
        acc = {"account_name": "My 401(k)", "account_type": "401k", "ending_balance": 100000}
        result = self._mark(acc)
        self.assertFalse(result.get("_prune", False))

    def test_stock_plan_with_last4_not_flagged(self):
        acc = {
            "account_name": "ESPP",
            "account_type": "stock_plan",
            "ending_balance": 25000,
            "account_number_last4": "7890",
        }
        result = self._mark(acc)
        self.assertFalse(result.get("_prune", False))


class TestPruneFlagged(unittest.TestCase):

    def setUp(self):
        self.sp = _make_sp()

    def test_stock_plan_null_balance_excluded(self):
        accounts = [
            {"account_name": "RSU", "account_type": "stock_plan", "ending_balance": None,
             "institution": "Fidelity", "_prune": True},
        ]
        kept, warnings = self.sp._prune_flagged(accounts)
        self.assertEqual(len(kept), 0)
        self.assertTrue(any("Stock Plan" in w for w in warnings))

    def test_embedded_stock_plan_with_brokerage_sibling_excluded(self):
        accounts = [
            {
                "account_name": "Stock Plan Summary", "account_type": "stock_plan",
                "ending_balance": 40000, "account_number_last4": None,
                "institution": "Fidelity", "_prune": True,
            },
            {
                "account_name": "Brokerage", "account_type": "brokerage",
                "ending_balance": 80000, "account_number_last4": "1234",
                "institution": "Fidelity", "_prune": False,
            },
        ]
        kept, warnings = self.sp._prune_flagged(accounts)
        names = [a["account_name"] for a in kept]
        self.assertIn("Brokerage", names)
        self.assertNotIn("Stock Plan Summary", names)

    def test_embedded_stock_plan_without_brokerage_sibling_kept(self):
        accounts = [
            {
                "account_name": "Stock Plan Summary", "account_type": "stock_plan",
                "ending_balance": 40000, "account_number_last4": None,
                "institution": "Schwab", "_prune": True,
            },
        ]
        kept, warnings = self.sp._prune_flagged(accounts)
        self.assertEqual(len(kept), 1)
        self.assertTrue(any("no account number" in w for w in warnings))

    def test_cash_with_parent_brokerage_excluded(self):
        accounts = [
            {
                "account_name": "Cash Balance", "account_type": "savings",
                "ending_balance": 2000, "institution": "Fidelity", "_prune": True,
            },
            {
                "account_name": "Brokerage", "account_type": "brokerage",
                "ending_balance": 50000, "institution": "Fidelity", "_prune": False,
            },
        ]
        kept, warnings = self.sp._prune_flagged(accounts)
        names = [a["account_name"] for a in kept]
        self.assertNotIn("Cash Balance", names)

    def test_cash_without_parent_brokerage_kept(self):
        accounts = [
            {
                "account_name": "Cash Balance", "account_type": "savings",
                "ending_balance": 2000, "institution": "Vanguard", "_prune": True,
            },
        ]
        kept, _ = self.sp._prune_flagged(accounts)
        self.assertEqual(len(kept), 1)
        self.assertNotIn("_prune", kept[0])

    def test_prune_flag_stripped_from_kept_accounts(self):
        accounts = [
            {"account_name": "IRA", "account_type": "ira", "ending_balance": 10000,
             "institution": "Vanguard"},
        ]
        kept, _ = self.sp._prune_flagged(accounts)
        self.assertNotIn("_prune", kept[0])


class TestDecomposeBuckets(unittest.TestCase):

    def setUp(self):
        self.sp = _make_sp()

    def test_non_retirement_unchanged(self):
        acc = {"account_type": "roth_ira", "_raw_tax_sources": [{"label": "Roth", "balance": 5000}]}
        result = self.sp._decompose_buckets(acc)
        self.assertNotIn("tax_buckets", result)

    def test_no_raw_sources_unchanged(self):
        acc = {"account_type": "401k"}
        result = self.sp._decompose_buckets(acc)
        self.assertNotIn("tax_buckets", result)

    def test_employee_deferral_maps_to_traditional(self):
        acc = {
            "account_type": "401k",
            "ending_balance": 10000,
            "_raw_tax_sources": [{"label": "Employee Deferral", "balance": 10000}],
        }
        result = self.sp._decompose_buckets(acc)
        self.assertIn("tax_buckets", result)
        bucket = result["tax_buckets"][0]
        self.assertEqual(bucket["bucket_type"], "traditional_401k")
        self.assertEqual(bucket["tax_treatment"], "tax_deferred")

    def test_roth_in_plan_maps_correctly(self):
        acc = {
            "account_type": "401k",
            "ending_balance": 5000,
            "_raw_tax_sources": [{"label": "Roth In-Plan Conversion", "balance": 5000}],
        }
        result = self.sp._decompose_buckets(acc)
        bucket = result["tax_buckets"][0]
        self.assertEqual(bucket["bucket_type"], "roth_in_plan_conversion")
        self.assertEqual(bucket["tax_treatment"], "tax_free")

    def test_after_tax_maps_correctly(self):
        acc = {
            "account_type": "401k",
            "ending_balance": 3000,
            "_raw_tax_sources": [{"label": "After-Tax Contributions", "balance": 3000}],
        }
        result = self.sp._decompose_buckets(acc)
        bucket = result["tax_buckets"][0]
        self.assertEqual(bucket["bucket_type"], "after_tax_401k")
        self.assertEqual(bucket["tax_treatment"], "post_tax")

    def test_unmatched_label_with_balance_creates_unknown_bucket(self):
        acc = {
            "account_type": "401k",
            "ending_balance": 2000,
            "_raw_tax_sources": [{"label": "Mystery Source", "balance": 2000}],
        }
        result = self.sp._decompose_buckets(acc)
        bucket = result["tax_buckets"][0]
        self.assertEqual(bucket["bucket_type"], "unknown")

    def test_unmatched_label_with_zero_balance_not_added(self):
        acc = {
            "account_type": "401k",
            "ending_balance": 0,
            "_raw_tax_sources": [{"label": "Zero Balance Source", "balance": 0}],
        }
        result = self.sp._decompose_buckets(acc)
        self.assertNotIn("tax_buckets", result)

    def test_multiple_buckets(self):
        acc = {
            "account_type": "401k",
            "ending_balance": 15000,
            "_raw_tax_sources": [
                {"label": "Employee Deferral", "balance": 10000},
                {"label": "Roth In-Plan Conversion", "balance": 5000},
            ],
        }
        result = self.sp._decompose_buckets(acc)
        self.assertEqual(len(result["tax_buckets"]), 2)


class TestFingerprint(unittest.TestCase):

    def test_with_last4_uses_institution_last4_type(self):
        acc = {
            "institution": "Fidelity",
            "account_number_last4": "1234",
            "account_type": "401k",
            "account_name": "My 401k",
        }
        fp = StatementProcessor._fingerprint(acc)
        self.assertEqual(fp, "fidelity|1234|401k")

    def test_without_last4_uses_institution_name_type_currency(self):
        acc = {
            "institution": "Vanguard",
            "account_number_last4": None,
            "account_type": "ira",
            "account_name": "Traditional IRA",
            "currency": "USD",
        }
        fp = StatementProcessor._fingerprint(acc)
        self.assertEqual(fp, "vanguard|traditional ira|ira|usd")

    def test_institution_normalised_in_fingerprint(self):
        acc1 = {"institution": "Fidelity", "account_number_last4": "1111", "account_type": "401k"}
        acc2 = {"institution": "Fidelity Brokerage Services LLC", "account_number_last4": "1111", "account_type": "401k"}
        self.assertEqual(
            StatementProcessor._fingerprint(acc1),
            StatementProcessor._fingerprint(acc2),
        )


class TestCompletenessScore(unittest.TestCase):

    def test_empty_account_scores_zero(self):
        self.assertEqual(StatementProcessor._completeness_score({}), 0)

    def test_balance_only_scores_two(self):
        self.assertEqual(StatementProcessor._completeness_score({"ending_balance": 1000}), 2)

    def test_balance_and_date_scores_three(self):
        acc = {"ending_balance": 1000, "balance_as_of_date": "2024-12-31"}
        self.assertEqual(StatementProcessor._completeness_score(acc), 3)

    def test_balance_and_buckets_scores_four(self):
        acc = {"ending_balance": 1000, "tax_buckets": [{"bucket_type": "traditional_401k"}]}
        self.assertEqual(StatementProcessor._completeness_score(acc), 4)

    def test_all_fields_scores_five(self):
        acc = {
            "ending_balance": 1000,
            "tax_buckets": [{}],
            "balance_as_of_date": "2024-12-31",
        }
        self.assertEqual(StatementProcessor._completeness_score(acc), 5)


class TestChooseWinner(unittest.TestCase):

    def setUp(self):
        self.sp = _make_sp()

    def test_newer_date_wins(self):
        a = {"balance_as_of_date": "2024-12-31", "ending_balance": 1000}
        b = {"balance_as_of_date": "2024-06-30", "ending_balance": 1000}
        self.assertIs(self.sp._choose_winner(a, b), a)

    def test_older_date_loses(self):
        a = {"balance_as_of_date": "2023-12-31", "ending_balance": 1000}
        b = {"balance_as_of_date": "2024-12-31", "ending_balance": 1000}
        self.assertIs(self.sp._choose_winner(a, b), b)

    def test_higher_completeness_wins_when_no_date(self):
        a = {"ending_balance": 1000, "tax_buckets": [{}]}   # score 4
        b = {"ending_balance": 2000}                         # score 2
        self.assertIs(self.sp._choose_winner(a, b), a)

    def test_equal_completeness_returns_first(self):
        a = {"ending_balance": 1000}
        b = {"ending_balance": 2000}
        self.assertIs(self.sp._choose_winner(a, b), a)

    def test_one_date_one_no_date_falls_back_to_score(self):
        a = {"balance_as_of_date": "", "ending_balance": 1000}
        b = {"ending_balance": 2000, "tax_buckets": [{}]}    # score 4 vs 2
        self.assertIs(self.sp._choose_winner(a, b), b)


class TestDedupAccounts(unittest.TestCase):

    def setUp(self):
        self.sp = _make_sp()

    def _make_account(self, institution, last4, acct_type, name="IRA", balance=10000, date="2024-12-31"):
        return {
            "institution": institution,
            "account_number_last4": last4,
            "account_type": acct_type,
            "account_name": name,
            "ending_balance": balance,
            "balance_as_of_date": date,
            "currency": "USD",
        }

    def test_unique_accounts_all_kept(self):
        accounts = [
            self._make_account("Fidelity", "1234", "401k"),
            self._make_account("Vanguard", "5678", "ira"),
        ]
        deduped, warnings = self.sp._dedup_accounts(accounts)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(warnings, [])

    def test_duplicate_fingerprint_one_kept(self):
        a = self._make_account("Fidelity", "1234", "401k", balance=10000, date="2024-06-30")
        b = self._make_account("Fidelity", "1234", "401k", balance=11000, date="2024-12-31")
        deduped, warnings = self.sp._dedup_accounts([a, b])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(len(warnings), 1)
        self.assertIn("Duplicate", warnings[0])

    def test_newer_statement_wins_dedup(self):
        a = self._make_account("Fidelity", "1234", "401k", balance=10000, date="2024-06-30")
        b = self._make_account("Fidelity", "1234", "401k", balance=11000, date="2024-12-31")
        deduped, _ = self.sp._dedup_accounts([a, b])
        self.assertEqual(deduped[0]["ending_balance"], 11000)


class TestChunkText(unittest.TestCase):

    def setUp(self):
        self.sp = _make_sp()

    def test_short_text_single_chunk(self):
        text = "This is a short document."
        chunks = self.sp._chunk_text(text, "test.pdf")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0][0], text)
        self.assertEqual(chunks[0][1], "test.pdf")

    def test_long_text_splits_into_multiple_chunks(self):
        text = "A" * 300_000  # 2× the 150k threshold
        chunks = self.sp._chunk_text(text, "large.pdf")
        self.assertEqual(len(chunks), 2)
        self.assertIn("part 1", chunks[0][1])
        self.assertIn("part 2", chunks[1][1])

    def test_chunk_labels_include_filename(self):
        text = "B" * 300_000
        chunks = self.sp._chunk_text(text, "report.pdf")
        for _, label in chunks:
            self.assertIn("report.pdf", label)


class TestNormalizeFiles(unittest.TestCase):

    def test_tuple_input(self):
        result = StatementProcessor._normalize_files([("file.pdf", b"pdfbytes")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "file.pdf")
        self.assertEqual(result[0][1], b"pdfbytes")

    def test_bytes_input_auto_named(self):
        result = StatementProcessor._normalize_files([b"rawbytes"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "document_1.pdf")
        self.assertEqual(result[0][1], b"rawbytes")

    def test_file_like_object(self):
        f = io.BytesIO(b"filebytes")
        f.name = "upload.pdf"
        result = StatementProcessor._normalize_files([f])
        self.assertEqual(result[0][0], "upload.pdf")
        self.assertEqual(result[0][1], b"filebytes")

    def test_file_like_without_name_attribute(self):
        f = io.BytesIO(b"anon")
        # BytesIO has no .name attribute by default
        if hasattr(f, "name"):
            del f.name
        result = StatementProcessor._normalize_files([f])
        self.assertTrue(result[0][0].endswith(".pdf"))

    def test_tuple_with_file_like_value(self):
        f = io.BytesIO(b"inner")
        result = StatementProcessor._normalize_files([("custom.pdf", f)])
        self.assertEqual(result[0][0], "custom.pdf")
        self.assertEqual(result[0][1], b"inner")

    def test_unsupported_type_raises(self):
        with self.assertRaises(StatementProcessorError):
            StatementProcessor._normalize_files([12345])

    def test_multiple_files(self):
        result = StatementProcessor._normalize_files([
            ("a.pdf", b"bytes_a"),
            ("b.pdf", b"bytes_b"),
        ])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], "a.pdf")
        self.assertEqual(result[1][0], "b.pdf")


if __name__ == "__main__":
    unittest.main()
