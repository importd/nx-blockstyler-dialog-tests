# -*- coding: utf-8 -*-
"""NX 10 Python 3.3 orchestrator: run cases through <Dialog>_test.dll.

Run inside a GUI NX session (MCP nx_run_python, Tools -> Journal -> Play, or
File -> Execute -> NX Open). The DLL hook reads AUTODLG_CASE/AUTODLG_OUT,
which must have been set before NX started; this script only rewrites the
file contents per case.

Python 3.3 compatible: no f-strings, no subprocess.run.
"""

import ctypes
import json
import os
import shutil
import sys
import time

HERE = os.environ.get("AUTODLG_HOME")
if not HERE:
    if "__file__" in globals():
        HERE = os.path.dirname(os.path.abspath(__file__))
    else:
        HERE = os.getcwd()
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import harness_core as H  # noqa: E402

DEFAULT_DLL = "baseDialog_test.dll"
DEFAULT_CASES = os.path.join(HERE, "cases.json")
FIXED_CASE = os.path.join(HERE, "tmp", "cases", "current.ini")
FIXED_OUT = os.path.join(HERE, "tmp", "results", "current.ini")
DEFAULT_SAMPLE_PART = (r"D:\Program Files\Siemens\NX 10.0\UGII"
                       r"\drafting_welcome\sample_parts\flange.prt")

_DLL_LIB = None


def _tmp(tmp_dir):
    return tmp_dir or os.path.join(HERE, "tmp")


def _abs(path):
    if path is None:
        return None
    return path if os.path.isabs(path) else os.path.join(HERE, path)


def ensure_part(session, NXOpen, cfg):
    part = session.Parts.Work
    if part is not None and list(part.Bodies):
        return part

    wanted = _abs(cfg.get("part"))
    if not wanted:
        wanted = os.environ.get("AUTODLG_SAMPLE_PART") or DEFAULT_SAMPLE_PART
    if wanted and os.path.isfile(wanted):
        # NX 10's OpenBaseDisplay returns a tuple and raises if already open;
        # ignore both and re-check Work.
        try:
            session.Parts.OpenBaseDisplay(wanted)
        except Exception:
            pass
    part = session.Parts.Work
    if part is not None and list(part.Bodies):
        return part
    raise RuntimeError(
        "no work part with a body; open a part before running, or set "
        "cases.json 'part' / AUTODLG_SAMPLE_PART")


def _load_ufusr(dll_path):
    global _DLL_LIB
    if not os.path.isfile(dll_path):
        raise RuntimeError("test DLL not found: %s" % dll_path)
    _DLL_LIB = ctypes.CDLL(dll_path)
    try:
        fn = _DLL_LIB.ufusr
    except AttributeError:
        raise RuntimeError(
            "%s does not export ufusr. Define USER_EXIT_OR_MENU, rebuild, and "
            "check with: dumpbin /exports %s" % (dll_path,
                                                 os.path.basename(dll_path)))
    fn.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int), ctypes.c_int]
    fn.restype = None
    return fn


def _paths(fixed_case, fixed_out, case_dir, result_dir, name):
    if fixed_case and fixed_out:
        return fixed_case, fixed_out, True
    return (os.path.join(case_dir, name + ".ini"),
            os.path.join(result_dir, name + ".ini"), False)


def _write_running(path, case, out_file, case_file):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"id": case.get("id"), "name": case.get("name"),
                   "title": case.get("title"), "file": case.get("file"),
                   "case_file": case_file, "out_file": out_file}, f,
                  ensure_ascii=False, indent=2)


def _copy_result(src, dst):
    if not os.path.isfile(src):
        return False
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        shutil.copyfile(src, dst)
        return True
    except Exception:
        return False


def main(cases_path=None, dry_run=False, tmp_dir=None, dll=None, part=None,
         fixed_case=None, fixed_out=None):
    cases_path = _abs(cases_path) or DEFAULT_CASES
    tmp_dir = _tmp(tmp_dir)
    cfg = H.load_cases(cases_path)
    cases = H.prepare_manifest(cfg)

    case_dir = os.path.join(tmp_dir, "cases")
    result_dir = os.path.join(tmp_dir, "results")
    os.makedirs(case_dir, exist_ok=True)
    os.makedirs(result_dir, exist_ok=True)

    manifest_path = os.path.join(tmp_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"time": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "dll": dll or cfg.get("dll") or DEFAULT_DLL,
                   "part": part or cfg.get("part"),
                   "timeout_ms": cfg.get("timeout_ms", 8000),
                   "cases": cases}, f, ensure_ascii=False, indent=2)

    # Write all per-case files even on dry-run: this is the cheap review step.
    for case in cases:
        H.write_case_file(case, os.path.join(case_dir, case["file"]),
                          case["id"])

    if dry_run:
        return {"dry_run": True, "cases": len(cases),
                "manifest": manifest_path}

    # Fixed paths are only reliable if the DLL saw them at NX startup.
    if fixed_case is None:
        fixed_case = os.environ.get("AUTODLG_CASE")
    if fixed_out is None:
        fixed_out = os.environ.get("AUTODLG_OUT")
    if not (fixed_case and fixed_out):
        # The hook will not see os.environ changes made here. Fail loudly
        # instead of producing five identical "missing result" failures.
        raise RuntimeError(
            "AUTODLG_CASE/AUTODLG_OUT were not visible when NX started. "
            "Launch NX via launch.bat (or set them in the same cmd), then run "
            "this script again. Editing os.environ from NX Python is not "
            "reliably visible to the DLL's getenv.")

    dll_path = _abs(dll or cfg.get("dll") or DEFAULT_DLL)
    import NXOpen
    session = NXOpen.Session.GetSession()
    ensure_part(session, NXOpen, dict(cfg, part=part or cfg.get("part")))
    ufusr = _load_ufusr(dll_path)

    rows = []
    running_path = os.path.join(tmp_dir, "running.json")
    timeout_ms = cfg.get("timeout_ms", 8000)
    for case in cases:
        case_file, out_file, is_fixed = _paths(
            fixed_case, fixed_out, case_dir, result_dir, case["id"])
        H.write_case_file(case, case_file, case["id"])
        if os.path.exists(out_file):
            os.remove(out_file)
        stale = os.path.join(result_dir, case["file"])
        if os.path.exists(stale):
            os.remove(stale)
        _write_running(running_path, case, out_file, case_file)

        returned = 1
        error = ""
        ret = ctypes.c_int(0)
        try:
            ufusr(None, ctypes.byref(ret), 0)
        except Exception as exc:
            returned = 0
            error = str(exc)

        result = H.parse_result(out_file)
        if is_fixed and os.path.isfile(out_file):
            _copy_result(out_file, stale)
        try:
            os.remove(running_path)
        except OSError:
            pass
        result["returned"] = returned
        if error:
            result["error"] = error
        checks = H.compare(case, result)
        rows.append({"name": case.get("name"), "id": case.get("id"),
                     "file": case.get("file"), "title": case.get("title"),
                     "pass": all(c["pass"] for c in checks),
                     "checks": checks, "result": result})

    return H.write_outputs(
        rows, os.path.join(tmp_dir, "results.json"),
        os.path.join(tmp_dir, "summary.txt"),
        title=cfg.get("title", "NX dialog harness"))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=DEFAULT_CASES)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tmp-dir", default=None)
    parser.add_argument("--dll", default=None)
    parser.add_argument("--part", default=None)
    args = parser.parse_args()
    result = main(args.cases, args.dry_run, args.tmp_dir, args.dll, args.part)
    print(json.dumps(result, ensure_ascii=False, indent=2))
