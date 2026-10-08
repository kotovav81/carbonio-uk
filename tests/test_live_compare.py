import unittest

from carbonio_uk.live_compare import compare_catalogs


class LiveCompareTests(unittest.TestCase):
    def test_exact_and_value_drift(self):
        self.assertEqual(compare_catalogs({"a": "x"}, {"a": "x"})["classification"], "exact")
        result = compare_catalogs({"a": "x"}, {"a": "y"})
        self.assertEqual(result["classification"], "content_drift")
        self.assertEqual(result["changed_values"], ["a"])

    def test_keyset_classifications(self):
        self.assertEqual(compare_catalogs({"a": 1, "b": 2}, {"a": 1})["classification"], "likely_live_older")
        self.assertEqual(compare_catalogs({"a": 1}, {"a": 1, "b": 2})["classification"], "likely_live_newer")
        self.assertEqual(compare_catalogs({"a": 1, "b": 2}, {"a": 1, "c": 3})["classification"], "diverged_keyset")


if __name__ == "__main__":
    unittest.main()
