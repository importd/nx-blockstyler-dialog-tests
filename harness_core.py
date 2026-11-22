# -*- coding: utf-8 -*-
"""Pure logic for the NX dialog harness: cases, results, comparisons, summary."""

import json
import os
import time


def load_cases(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cases = cfg.get("cases")
    if not isinstance(cases, list):
        raise ValueError("cases must be a list")
    for case in cases:
        if "name" not in case:
            raise ValueError("case missing name")
    return cfg


def write_case_file(case, path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    lines = []
    if case.get("apply"):
        lines.append("apply=1")
    for key in sorted(case.get("set", {})):
        value = case["set"][key]
        if isinstance(value, bool):
            value = 1 if value else 0
        lines.append("set.%s=%s" % (key, value))
    with open(path, "w", encoding="utf-8") as f:
        if lines:
            f.write("\n".join(lines) + "\n")


def parse_result(path):
    out = {"shown": 0, "hook_ran": 0, "apply_rc": None,
           "close_attempted": 0, "error": "", "got": {}}
    if not os.path.isfile(path):
        out["error"] = "result file missing"
        return out
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key.startswith("got."):
                out["got"][key[4:]] = value
            elif key in ("shown", "hook_ran", "close_attempted"):
                try:
                    out[key] = int(value)
                except ValueError:
                    pass
            elif key == "apply_rc":
                try:
                    out[key] = int(value) if value != "" else None
                except ValueError:
                    out[key] = None
            elif key == "error":
                out[key] = value
    return out


def _same(got, expect):
    if isinstance(expect, bool):
        return bool(got) == expect
    if isinstance(expect, (int, float)):
        try:
            return abs(float(got) - float(expect)) < 1e-6
        except (TypeError, ValueError):
            return False
    return str(got) == str(expect)


def compare(case, result):
    expect = case.get("expect", {})
    checks = [{"name": "shown",
               "pass": result.get("shown") == expect.get("shown", 1),
               "got": result.get("shown"),
               "expect": expect.get("shown", 1)}]
    got_map = result.get("got", {})
    for key in expect:
        if key == "shown":
            continue
        got = got_map[key] if key in got_map else result.get(key)
        checks.append({"name": key, "pass": _same(got, expect[key]),
                       "got": got, "expect": expect[key]})
    return checks


def summarize(rows):
    total = len(rows)
    passed = sum(1 for row in rows if row.get("pass"))
    return {"total": total, "passed": passed, "failed": total - passed}


def write_outputs(rows, out_json, out_txt):
    summary = summarize(rows)
    data = {"time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "cases": rows, "summary": summary}
    parent = os.path.dirname(out_json)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if out_txt:
        lines = ["nx-shear-angle dialog harness",
                 "time: %s" % data["time"],
                 "cases: %d  passed: %d  failed: %d" %
                 (summary["total"], summary["passed"], summary["failed"]),
                 ""]
        for row in rows:
            lines.append("%s %s" % ("PASS" if row.get("pass") else "FAIL",
                                    row.get("name")))
            for check in row.get("checks", []):
                if not check.get("pass"):
                    lines.append("  - %s: got=%r expect=%r" %
                                 (check["name"], check.get("got"),
                                  check.get("expect")))
            if row.get("error"):
                lines.append("  - error: " + str(row["error"]))
        text = "\n".join(lines) + "\n"
        parent = os.path.dirname(out_txt)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_txt, "w", encoding="utf-8") as f:
            f.write(text)
    return data
