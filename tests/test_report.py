import json, os, sys, tempfile, unittest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
MODDIR = os.path.join(HERE, "harness")
if MODDIR not in sys.path:
    sys.path.insert(0, MODDIR)
import report


class ReportTests(unittest.TestCase):
    def test_missing_result_marks_timeout_and_preserves_done(self):
        with tempfile.TemporaryDirectory() as d:
            man = os.path.join(d, "manifest.json")
            res = os.path.join(d, "results")
            os.makedirs(res)
            with open(man, "w", encoding="utf-8") as f:
                json.dump({"cases": [
                    {"name": "done", "expect": {"enum0": 1}},
                    {"name": "hung", "expect": {"shown": 1}}]}, f)
            with open(os.path.join(res, "done.ini"), "w", encoding="utf-8") as f:
                f.write("shown=1\nhook_ran=1\ngot.enum0=1\nclose_attempted=1\n")
            rows = report.collect(man, res)
            by = {r["name"]: r for r in rows}
            self.assertTrue(by["done"]["pass"])
            self.assertFalse(by["hung"]["pass"])
            self.assertIn("timeout", by["hung"]["error"])

    def test_malformed_result_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            man = os.path.join(d, "manifest.json")
            res = os.path.join(d, "results")
            os.makedirs(res)
            with open(man, "w", encoding="utf-8") as f:
                json.dump({"cases": [{"name": "bad", "expect": {"shown": 1}}]}, f)
            with open(os.path.join(res, "bad.ini"), "w", encoding="utf-8") as f:
                f.write("garbage")
            rows = report.collect(man, res)
            self.assertFalse(rows[0]["pass"])
