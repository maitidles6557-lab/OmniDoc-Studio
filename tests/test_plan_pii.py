import unittest

from tests import conftest  # noqa: F401
from core.pii import count_pii, unique_pii
from core.plan import sanitize_actions, to_int_list


class PlanTests(unittest.TestCase):
    def test_to_int_list_handles_messy_llm_output(self):
        self.assertEqual(to_int_list([2, "3", "4-6", "x", True, None]), [2, 3, 4, 5, 6])
        self.assertEqual(to_int_list("7"), [7])
        self.assertEqual(to_int_list(None), [])

    def test_valid_plan_is_normalized(self):
        actions, warns = sanitize_actions([
            {"op": "delete_pages", "pages": ["2-4"]},
            {"op": "rotate", "angle": "90"},
            {"op": "watermark", "text": "X" * 100},
            {"op": "redact", "terms": ["Dupont", " "]},
            {"op": "redact_pii"}])
        self.assertEqual(warns, [])
        self.assertEqual(actions[0]["pages"], [2, 3, 4])
        self.assertEqual(actions[1], {"op": "rotate", "pages": [], "angle": 90})
        self.assertEqual(len(actions[2]["text"]), 40)
        self.assertEqual(actions[3]["terms"], ["Dupont"])

    def test_invalid_entries_are_dropped_with_warnings(self):
        actions, warns = sanitize_actions([
            {"op": "format_disk"}, "oops", {"op": "rotate", "angle": 45},
            {"op": "redact", "terms": ["a"]}])
        self.assertEqual(actions, [])
        self.assertEqual(len(warns), 4)

    def test_non_list_plan(self):
        self.assertEqual(sanitize_actions({"op": "redact_pii"})[0], [])


class PIITests(unittest.TestCase):
    TEXT = ("Contact : jean.dupont@example.com, tél +212 6 12 34 56 78. "
            "IBAN FR76 3000 6000 0112 3456 7890 189. CIN AB123456.")

    def test_counts(self):
        c = count_pii(self.TEXT)
        self.assertEqual(c["email"], 1)
        self.assertEqual(c["iban"], 1)
        self.assertEqual(c["CIN"], 1)
        self.assertGreaterEqual(c["téléphone"], 1)

    def test_unique_matches(self):
        found = unique_pii(self.TEXT)
        self.assertIn("jean.dupont@example.com", found)
        self.assertIn("AB123456", found)


if __name__ == "__main__":
    unittest.main()
