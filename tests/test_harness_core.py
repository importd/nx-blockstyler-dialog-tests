import os, sys, tempfile, unittest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import harness_core as H


class CaseFileTests(unittest.TestCase):
    def test_write_case_file_emits_set_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "case.ini")
            H.write_case_file({"name": "x", "apply": True,
                               "set": {"enum0": 2, "linear_dim0": 12.5,
                                       "selection0": "first_body"}}, p)
            with open(p, encoding="utf-8") as f:
                lines = f.read().splitlines()
            self.assertIn("apply=1", lines)
            self.assertIn("set.enum0=2", lines)
            self.assertIn("set.linear_dim0=12.5", lines)
            self.assertIn("set.selection0=first_body", lines)


class ResultTests(unittest.TestCase):
    def test_parse_result_flattens_got(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "r.ini")
            with open(p, "w", encoding="utf-8") as f:
                f.write("shown=1\nhook_ran=1\ngot.enum0=2\ngot.linear_dim0=12.5\n"
                        "apply_rc=0\nerror=\nclose_attempted=1\n")
            r = H.parse_result(p)
            self.assertEqual(r["shown"], 1)
            self.assertEqual(r["got"]["enum0"], "2")
            self.assertEqual(r["apply_rc"], 0)

    def test_missing_result_is_fail_shown_zero(self):
        case = {"name": "x", "expect": {"shown": 1, "enum0": 2}}
        result = H.parse_result("does-not-exist.ini")
        checks = H.compare(case, result)
        self.assertFalse(all(c["pass"] for c in checks))
        self.assertEqual(result["shown"], 0)


class CompareTests(unittest.TestCase):
    def test_compare_passes_numbers_and_strings(self):
        case = {"name": "x", "expect": {"enum0": 2, "linear_dim0": 12.5}}
        result = {"shown": 1, "hook_ran": 1, "apply_rc": None, "error": "",
                  "got": {"enum0": "2", "linear_dim0": "12.5"}}
        checks = H.compare(case, result)
        self.assertTrue(all(c["pass"] for c in checks))

    def test_compare_reports_mismatch(self):
        case = {"name": "x", "expect": {"enum0": 3}}
        result = {"shown": 1, "hook_ran": 1, "apply_rc": None, "error": "",
                  "got": {"enum0": "2"}}
        checks = H.compare(case, result)
        self.assertFalse(all(c["pass"] for c in checks))


class SummaryTests(unittest.TestCase):
    def test_summarize_counts(self):
        rows = [{"name": "a", "pass": True, "checks": []},
                {"name": "b", "pass": False, "checks": []}]
        self.assertEqual(H.summarize(rows),
                         {"total": 2, "passed": 1, "failed": 1})
