# -*- coding: utf-8 -*-
"""NX 10 Python 3.3 orchestrator: run cases through baseDialog_test.dll."""

import ctypes
import json
import os
import shutil
import sys

import harness_core as H

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DLL = os.path.join(ROOT, "build", "baseDialog_test.dll")
DEFAULT_CASES = os.path.join(HERE, "cases.json")
FIXED_CASE = os.path.join(ROOT, "tmp", "cases", "current.ini")
FIXED_OUT = os.path.join(ROOT, "tmp", "results", "current.ini")


def _tmp(tmp_dir):
    return tmp_dir or os.path.join(ROOT, "tmp")


SAMPLE_PART = (r"D:\Program Files\Siemens\NX 10.0\UGII"
               r"\drafting_welcome\sample_parts\flange.prt")


def ensure_part(session, NXOpen, tmp_dir):
    part = session.Parts.Work
    if part is not None and list(part.Bodies):
        return part
    # NX 10's Python UF wrapper has no CreateBlock1; open a shipped sample
    # part with a solid instead. OpenBaseDisplay returns a tuple and raises if
    # the part is already open, so ignore both cases and check Work again.
    try:
        session.Parts.OpenBaseDisplay(SAMPLE_PART)
    except Exception:
        pass
    part = session.Parts.Work
    if part is not None and list(part.Bodies):
        return part
    raise RuntimeError("no work part with a body; open a part before running")


def _paths(fixed_case, fixed_out, case_dir, result_dir, name):
    """If the NX process already has fixed AUTODLG_CASE/OUT paths (set before
    NX started), reuse them for every case: changing os.environ at runtime is
    not reliably visible to the DLL's CRT getenv. Otherwise use per-case paths.
    """
    if fixed_case and fixed_out:
        return fixed_case, fixed_out, True
    return (os.path.join(case_dir, name + ".ini"),
            os.path.join(result_dir, name + ".ini"), False)


def _load_ufusr():
    lib = ctypes.CDLL(DLL)
    fn = lib.ufusr
    fn.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int), ctypes.c_int]
    fn.restype = None
    return fn


def main(cases_path=None, dry_run=False, tmp_dir=None,
         fixed_case=None, fixed_out=None):
    cases_path = cases_path or DEFAULT_CASES
    tmp_dir = _tmp(tmp_dir)
    cfg = H.load_cases(cases_path)
    cases = cfg.get("cases", [])

    case_dir = os.path.join(tmp_dir, "cases")
    result_dir = os.path.join(tmp_dir, "results")
    if not os.path.isdir(case_dir):
        os.makedirs(case_dir)
    if not os.path.isdir(result_dir):
        os.makedirs(result_dir)

    with open(os.path.join(tmp_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"cases": cases}, f, ensure_ascii=False, indent=2)
    for case in cases:
        H.write_case_file(case, os.path.join(case_dir, case["name"] + ".ini"))

    if dry_run:
        return {"dry_run": True, "cases": len(cases)}

    import NXOpen
    session = NXOpen.Session.GetSession()
    ensure_part(session, NXOpen, tmp_dir)
    ufusr = _load_ufusr()

    fixed_case = fixed_case or FIXED_CASE
    fixed_out = fixed_out or FIXED_OUT
    rows = []
    timeout_ms = cfg.get("timeout_ms", 8000)
    for case in cases:
        name = case["name"]
        case_file, out_file, is_fixed = _paths(fixed_case, fixed_out,
                                               case_dir, result_dir, name)
        H.write_case_file(case, case_file)
        if os.path.exists(out_file):
            os.remove(out_file)
        if not is_fixed:
            os.environ["AUTODLG_CASE"] = case_file
            os.environ["AUTODLG_OUT"] = out_file
        os.environ["AUTODLG_TIMEOUT_MS"] = str(timeout_ms)

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
            try:
                shutil.copyfile(out_file,
                                os.path.join(result_dir, name + ".ini"))
            except Exception:
                pass
        result["returned"] = returned
        if error:
            result["error"] = error
        checks = H.compare(case, result)
        rows.append({"name": name,
                     "pass": all(c["pass"] for c in checks),
                     "checks": checks, "result": result})

    return H.write_outputs(rows, os.path.join(tmp_dir, "results.json"),
                           os.path.join(tmp_dir, "summary.txt"))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=DEFAULT_CASES)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(main(args.cases, args.dry_run), ensure_ascii=False, indent=2))
