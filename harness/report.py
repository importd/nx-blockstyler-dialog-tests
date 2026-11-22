# -*- coding: utf-8 -*-
"""Offline report: aggregate per-case results even if NX was killed."""

import argparse
import json
import os

import harness_core as H


def collect(manifest_path, results_dir):
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    rows = []
    for case in manifest.get("cases", []):
        name = case.get("name", "?")
        path = os.path.join(results_dir, name + ".ini")
        if not os.path.isfile(path):
            result = {"shown": 0, "hook_ran": 0, "apply_rc": None,
                      "close_attempted": 0, "error": "timeout", "got": {}}
        else:
            result = H.parse_result(path)
            if not result.get("shown"):
                result["error"] = result.get("error") or "not shown"
        checks = H.compare(case, result)
        rows.append({"name": name,
                     "pass": all(c["pass"] for c in checks),
                     "checks": checks, "result": result,
                     "error": result.get("error", "")})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-txt", required=True)
    args = parser.parse_args(argv)
    rows = collect(args.manifest, args.results)
    return H.write_outputs(rows, args.out_json, args.out_txt)


if __name__ == "__main__":
    main()
