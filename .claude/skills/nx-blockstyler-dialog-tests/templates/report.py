# -*- coding: utf-8 -*-
"""Offline report: aggregate per-case results even if NX was killed.

The orchestrator normally copies tmp/results/current.ini to <file>.ini after
ufusr returns. If NX is force-killed first, that copy never happens; this
script recovers the in-flight case from current.ini using running.json.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import harness_core as H  # noqa: E402


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def _load_running(path, manifest_mtime):
    if not os.path.isfile(path):
        return None
    if _mtime(path) < manifest_mtime - 1:
        return None  # stale marker from a previous run
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _case_file(case, idx):
    if case.get("file"):
        return case["file"]
    if case.get("name"):
        return case["name"] + ".ini"
    return "%03d.ini" % idx


def _matches_running(case, running):
    if not running:
        return False
    if running.get("file") and case.get("file"):
        return running["file"] == case["file"]
    if running.get("id") and case.get("id"):
        return str(running["id"]) == str(case["id"])
    return running.get("name") == case.get("name")


def collect(manifest_path, results_dir, recover=True):
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    manifest_mtime = _mtime(manifest_path)
    tmp_dir = os.path.dirname(os.path.abspath(manifest_path))
    running = _load_running(os.path.join(tmp_dir, "running.json"),
                            manifest_mtime)
    current = os.path.join(results_dir, "current.ini")
    rows = []
    for idx, case in enumerate(manifest.get("cases", [])):
        name = case.get("name", "?")
        filename = _case_file(case, idx)
        path = os.path.join(results_dir, filename)
        recovered_from = None
        if os.path.isfile(path):
            result = H.parse_result(path)
        elif (recover and _matches_running(case, running)
              and os.path.isfile(current)
              and _mtime(current) >= manifest_mtime - 1):
            result = H.parse_result(current)
            recovered_from = "current.ini"
        else:
            result = {"shown": 0, "hook_ran": 0, "apply_rc": None,
                      "close_attempted": 0, "error": "timeout", "got": {}}
        if not result.get("shown"):
            result["error"] = result.get("error") or "not shown"
        checks = H.compare(case, result)
        row = {"name": name, "id": case.get("id"), "file": filename,
               "title": case.get("title", name),
               "pass": all(c["pass"] for c in checks),
               "checks": checks, "result": result,
               "error": result.get("error", "")}
        if recovered_from:
            row["recovered_from"] = recovered_from
        rows.append(row)
    return rows, manifest


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-txt", required=True)
    parser.add_argument("--no-recover", action="store_true",
                        help="do not recover the in-flight case from current.ini")
    args = parser.parse_args(argv)
    rows, manifest = collect(args.manifest, args.results,
                             recover=not args.no_recover)
    return H.write_outputs(rows, args.out_json, args.out_txt,
                           title=manifest.get("title", "NX dialog harness"))


if __name__ == "__main__":
    main()
