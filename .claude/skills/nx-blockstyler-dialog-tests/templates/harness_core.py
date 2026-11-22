# -*- coding: utf-8 -*-
"""Pure logic for the NX dialog harness: cases, results, comparisons, summary.

NX 10's embedded Python is 3.3, so this module must stay 3.3-compatible:
no f-strings, no subprocess.run, no typing syntax.
"""

import json
import os
import re
import time


TOP_LEVEL_KEYS = ("shown", "hook_ran", "close_attempted", "apply_rc",
                  "returned", "recovered_from")


def load_cases(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cases = cfg.get("cases")
    if not isinstance(cases, list):
        raise ValueError("cases must be a list")
    for case in cases:
        if not isinstance(case, dict) or "name" not in case:
            raise ValueError("every case needs a name")
    return cfg


def one_line(text):
    return str(text).replace("\r", " ").replace("\n", " ")


def safe_name(name):
    """Filesystem-safe slug; kept for old manifests and for human inspection."""
    slug = re.sub(r"[^0-9A-Za-z_.-]+", "_", one_line(name or "case")).strip("._")
    return slug or "case"


def prepare_manifest(cfg):
    """Assign stable id/file names. Display names never become file names."""
    rows = []
    for idx, case in enumerate(cfg.get("cases", [])):
        item = dict(case)
        item["id"] = "%03d" % idx
        item["file"] = item["id"] + ".ini"
        item.setdefault("title", case.get("name", ""))
        if cfg.get("timeout_ms") is not None and "timeout_ms" not in item:
            item["timeout_ms"] = cfg["timeout_ms"]
        rows.append(item)
    return rows


def write_case_file(case, path, case_id=None):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    lines = []
    if case_id is not None:
        lines.append("id=%s" % case_id)
    if case.get("name") is not None:
        # The C++ hook ignores unknown keys; this is for humans debugging .ini.
        lines.append("name=%s" % one_line(case["name"]))
    if case.get("timeout_ms") is not None:
        lines.append("timeout_ms=%s" % int(case["timeout_ms"]))
    if case.get("apply"):
        lines.append("apply=1")
    for key in sorted(case.get("set", {})):
        value = case["set"][key]
        if isinstance(value, bool):
            value = 1 if value else 0
        lines.append("set.%s=%s" % (key, one_line(value)))
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


def _check(name, got, expect):
    return {"name": name, "pass": _same(got, expect),
            "got": got, "expect": expect}


def compare(case, result):
    """Compare one result against a case.

    Defaults make silent passes hard:
      shown=1, hook_ran=1, close_attempted=1, error empty.
    A failure-path case opts out with allow_error or expect.error_contains.
    A no-close meta-test opts in with expect.close_attempted = 0.
    """
    expect = dict(case.get("expect", {}))
    checks = []

    checks.append(_check("shown", result.get("shown", 0),
                         expect.pop("shown", 1)))
    checks.append(_check("hook_ran", result.get("hook_ran", 0),
                         expect.pop("hook_ran", 1)))
    checks.append(_check("close_attempted", result.get("close_attempted", 0),
                         expect.pop("close_attempted", 1)))

    if "error" in expect:
        checks.append(_check("error", result.get("error", ""),
                             expect.pop("error")))
        expect.pop("error_contains", None)
    elif "error_contains" in expect:
        needle = expect.pop("error_contains")
        got = result.get("error", "")
        checks.append({"name": "error_contains", "pass": needle in got,
                       "got": got, "expect": needle})
    elif not case.get("allow_error"):
        checks.append(_check("error_empty", result.get("error", ""), ""))

    got_map = result.get("got", {})
    for key in expect:
        got = got_map[key] if key in got_map else result.get(key)
        checks.append(_check(key, got, expect[key]))
    return checks


def summarize(rows):
    total = len(rows)
    passed = sum(1 for row in rows if row.get("pass"))
    return {"total": total, "passed": passed, "failed": total - passed}


def write_outputs(rows, out_json, out_txt, title="NX dialog harness"):
    summary = summarize(rows)
    data = {"time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "cases": rows, "summary": summary}
    parent = os.path.dirname(out_json)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if out_txt:
        lines = [title,
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
            if row.get("recovered_from"):
                lines.append("  - recovered from: " + row["recovered_from"])
        text = "\n".join(lines) + "\n"
        parent = os.path.dirname(out_txt)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_txt, "w", encoding="utf-8") as f:
            f.write(text)
    return data
