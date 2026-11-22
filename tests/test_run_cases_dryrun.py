import json, os, subprocess, sys, tempfile, unittest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
MODDIR = os.path.join(HERE, "harness")
if MODDIR not in sys.path:
    sys.path.insert(0, MODDIR)
import run_cases


class DryRunTests(unittest.TestCase):
    def test_dry_run_writes_manifest_and_cases(self):
        with tempfile.TemporaryDirectory() as d:
            cases = os.path.join(d, "cases.json")
            out = os.path.join(d, "tmp")
            with open(cases, "w", encoding="utf-8") as f:
                json.dump({"part": None, "cases": [
                    {"name": "a", "set": {"enum0": 1}, "expect": {"enum0": 1}},
                    {"name": "b", "expect": {"shown": 1}}]}, f)
            run_cases.main(cases_path=cases, dry_run=True, tmp_dir=out)
            with open(os.path.join(out, "manifest.json"), encoding="utf-8") as f:
                manifest = json.load(f)
            self.assertEqual([c["name"] for c in manifest["cases"]], ["a", "b"])
            self.assertTrue(os.path.exists(os.path.join(out, "cases", "a.ini")))


class PathTests(unittest.TestCase):
    def test_fixed_env_paths_win(self):
        case, out, fixed = run_cases._paths(r"c:\c.ini", r"c:\o.ini",
                                            r"d:\cases", r"d:\results", "x")
        self.assertEqual((case, out, fixed), (r"c:\c.ini", r"c:\o.ini", True))

    def test_per_case_paths_without_env(self):
        case, out, fixed = run_cases._paths(None, None, r"d:\cases", r"d:\results", "x")
        self.assertFalse(fixed)
        self.assertTrue(case.endswith("x.ini"))
        self.assertTrue(out.endswith("x.ini"))


class JournalImportTests(unittest.TestCase):
    def test_imports_when_script_dir_not_on_sys_path(self):
        harness_dir = os.path.join(HERE, "harness")
        script = os.path.join(harness_dir, "run_cases.py")
        code = (
            "import os, sys, runpy\n"
            "h = os.path.abspath(%r)\n"
            "sys.path = [p for p in sys.path if os.path.abspath(p) != h]\n"
            "runpy.run_path(%r, run_name='autodlg_import_check')\n"
        ) % (harness_dir, script)
        proc = subprocess.run([sys.executable, "-c", code], cwd=HERE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0,
                         proc.stderr.decode("utf-8", "replace"))


class LayoutTests(unittest.TestCase):
    def test_paths_point_into_layout(self):
        root = HERE
        self.assertEqual(run_cases.DEFAULT_CASES,
                         os.path.join(root, "harness", "cases.json"))
        self.assertEqual(run_cases.DLL,
                         os.path.join(root, "build", "baseDialog_test.dll"))
        self.assertEqual(run_cases.FIXED_CASE,
                         os.path.join(root, "tmp", "cases", "current.ini"))
        self.assertEqual(run_cases.FIXED_OUT,
                         os.path.join(root, "tmp", "results", "current.ini"))
        self.assertEqual(run_cases._tmp(None), os.path.join(root, "tmp"))
