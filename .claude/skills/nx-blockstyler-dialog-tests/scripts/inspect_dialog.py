#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""List Block Styler block IDs and validate a cases.json against a .dlx.

This is an authoring/preflight tool. It does not start NX and does not load the
plugin DLL. It parses the generated .dlx (and optionally .hpp / patched .cpp)
so you can avoid guessing block IDs or discovering typos only inside NX.

Examples
--------
    python inspect_dialog.py --dlx baseDialog.dlx --hpp baseDialog.hpp
    python inspect_dialog.py --dlx baseDialog.dlx --cases cases.json
    python inspect_dialog.py --dlx baseDialog.dlx --cpp baseDialog.cpp \
        --cases cases.json --emit-cases cases.skeleton.json

Exit code is 0 when there are no errors (warnings are allowed), 1 otherwise.
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

TOP_LEVEL_EXPECT_KEYS = {
    "shown", "hook_ran", "close_attempted", "apply_rc", "returned",
    "error", "error_contains", "recovered_from",
}

# Block presentation -> (hook support, property key, value kind)
# "yes" means the shipped autodlg_test.h can inject/read it.
KINDS = {
    "Select Object": ("yes", "SelectedObjects", "selection"),
    "Selection": ("yes", "SelectedObjects", "selection"),
    "Enumeration": ("yes", "Value", "enum"),
    "Linear Dimension": ("yes", "Value", "double"),
    "Angle Dimension": ("yes", "Value", "double"),
    "Double": ("yes", "Value", "double"),
    "Integer": ("yes", "Value", "integer"),
    "Color": ("yes", "Value", "integer"),
    "Toggle": ("yes", "Value", "logical"),
    "Check": ("yes", "Value", "logical"),
    "String": ("yes", "Value", "string"),
    "Group": ("no", "-", "container"),
    "Label": ("no", "-", "label"),
    "Separator": ("no", "-", "container"),
    "Button": ("no", "-", "button"),
    "Tab": ("no", "-", "container"),
    "Section": ("no", "-", "container"),
    "User Defined UI Block": ("no", "-", "unknown"),
}


def _read_text(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def _class_kind(class_name):
    name = (class_name or "").lower()
    if "selection" in name:
        return "Select Object"
    if "enum" in name:
        return "Enumeration"
    if "linear_dim" in name or "dim" in name:
        return "Linear Dimension"
    if "toggle" in name or "check" in name:
        return "Toggle"
    if "integer" in name or "int" in name:
        return "Integer"
    if "string" in name:
        return "String"
    if "double" in name or "expression" in name:
        return "Double"
    if "group" in name:
        return "Group"
    if "label" in name:
        return "Label"
    return ""


def _walk_with_parents(root):
    stack = [(root, None)]
    while stack:
        node, parent = stack.pop()
        yield node, parent
        for child in list(node):
            stack.append((child, node))


def _ancestor_item(node, parent_map):
    cur = node
    while cur is not None:
        if cur.tag == "item" and cur.get("presentation"):
            return cur
        cur = parent_map.get(cur)
    return None


def _find_props(item, sname=None, prop_id=None, direct_only=False):
    """Find Property nodes. direct_only avoids leaking into child block items
    (a Group's subtree contains the whole dialog)."""
    out = []
    nodes = list(item) if direct_only else [n for n, _ in _walk_with_parents(item)]
    for node in nodes:
        if node.tag != "Property":
            continue
        if sname is not None and node.get("sname") != sname:
            continue
        if prop_id is not None and node.get("id") != prop_id:
            continue
        out.append(node)
    return out


def parse_dlx(path):
    text = _read_text(path)
    root = ET.fromstring(text)
    parent_map = {}
    for node, parent in _walk_with_parents(root):
        parent_map[node] = parent

    blocks = []
    seen = set()
    for node, _ in _walk_with_parents(root):
        if node.tag != "Property" or node.get("sname") != "BlockID":
            continue
        block_id = (node.get("value") or "").strip()
        if not block_id or block_id in seen:
            continue
        seen.add(block_id)
        item = _ancestor_item(node, parent_map)
        if item is None:
            blocks.append({"id": block_id, "presentation": "?", "class": "",
                           "key": "-", "kind": "unknown", "support": "?",
                           "options": [], "default": None, "notes": []})
            continue

        presentation = item.get("presentation") or ""
        class_name = item.get("class") or ""
        if not presentation:
            presentation = _class_kind(class_name)
        support, key, kind = KINDS.get(
            presentation, ("no", "-", _class_kind(class_name) or "unknown"))

        # The BlockID Property's parent PropertyList holds this block's own
        # properties. Searching the whole subtree would pick up a Group's
        # children (and their enum Titles).
        block_plist = parent_map.get(node)
        own_props = []
        if block_plist is not None and block_plist.tag == "PropertyList":
            own_props = [c for c in list(block_plist) if c.tag == "Property"]

        def own(sname=None, prop_id=None):
            out = []
            for p in own_props:
                if sname is not None and p.get("sname") != sname:
                    continue
                if prop_id is not None and p.get("id") != prop_id:
                    continue
                out.append(p)
            return out

        options = []
        # Block options: Titles (display) and Titles_1 (runtime enum).
        for p in own(sname="Items", prop_id="Titles"):
            for s in p.findall("Strings"):
                v = s.get("value")
                if v is not None:
                    options.append(v)
        if not options:
            for p in own(sname="Value", prop_id="Titles_1"):
                for o in p.findall("Option"):
                    options.append(o.get("name") or o.get("value") or "?")

        default = None
        for p in own(sname="Value"):
            if p.get("type") in ("double", "integer", "logical", "string"):
                default = p.get("value")
                break
        if default is None and kind == "enum":
            for p in own(prop_id="Titles_1"):
                default = p.get("selected")
                break

        notes = []
        if kind == "selection":
            notes.append("read back is object count; key may also be Value")
        if kind == "enum":
            if not options:
                notes.append("NO OPTIONS: run autodlg_patch.py --dlx "
                             "or define Titles + Titles_1 in Block Styler")
            else:
                notes.append("%d option(s): %s" % (len(options),
                                                   ", ".join(options[:8])))
        if kind in ("container", "label", "button"):
            notes.append("not injectable; keep out of AUTODLG_HOOK")

        blocks.append({
            "id": block_id,
            "presentation": presentation or "?",
            "class": class_name,
            "key": key,
            "kind": kind,
            "support": support,
            "options": options,
            "default": default,
            "notes": notes,
        })
    return blocks


def parse_hpp_members(path):
    """Map block member names to their // Block type: ... comment, best effort."""
    out = {}
    text = _read_text(path)
    for line in text.splitlines():
        m = re.search(r"\*\s*(\w+)\s*;\s*//\s*Block type:\s*(.+?)\s*$", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def parse_hook_ids(path):
    text = _read_text(path)
    m = re.search(r"AUTODLG_HOOK\s*\(\s*theDialog\s*,\s*([^)]*)\)", text)
    if not m:
        return None
    return re.findall(r'"([^"]+)"', m.group(1))


def print_table(blocks, members, hook_ids=None):
    print("%-22s %-19s %-10s %-11s %-6s %s" %
          ("ID", "Presentation", "Injectable", "Key", "Kind", "Notes"))
    print("-" * 100)
    for b in blocks:
        member = " [member]" if b["id"] in members else ""
        print("%-22s %-19s %-10s %-11s %-6s %s%s" %
              (b["id"], b["presentation"], b["support"], b["key"],
               b["kind"], "; ".join(b["notes"]), member))

    injectable = [b["id"] for b in blocks if b["support"] == "yes"]
    shown_ids = hook_ids if hook_ids is not None else injectable
    print("")
    print("Suggested hook%s:" % (" (parsed from --cpp)" if hook_ids else ""))
    print('  AUTODLG_HOOK(theDialog, %s);' %
          ", ".join('"%s"' % i for i in shown_ids))
    print("")
    print("Inject with:")
    by_id = {b["id"]: b for b in blocks}
    for block_id in shown_ids:
        b = by_id.get(block_id)
        if b is None or b["support"] != "yes":
            continue
        if b["kind"] == "selection":
            example = "first_body"
        elif b["kind"] == "enum":
            example = "0"
        elif b["kind"] in ("double",):
            example = "1.0"
        elif b["kind"] in ("integer",):
            example = "1"
        elif b["kind"] == "logical":
            example = "true"
        else:
            example = '"text"'
        print('  set.%-18s = %s' % (b["id"], example))


def validate(dlx_path, blocks, cases_path, hook_ids):
    with open(cases_path, "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    by_id = {b["id"]: b for b in blocks}
    errors = []
    warnings = []

    if not isinstance(cfg.get("cases"), list):
        errors.append("cases.json: top-level 'cases' must be a list")
        return errors, warnings

    for idx, case in enumerate(cfg["cases"]):
        where = "case[%d] %r" % (idx, case.get("name", "?"))
        if "name" not in case:
            errors.append("%s: missing 'name'" % where)
            continue
        sets = case.get("set", {})
        if not isinstance(sets, dict):
            errors.append("%s: 'set' must be an object" % where)
            sets = {}
        # A negative test intentionally feeds a bad value; still validate the
        # block ID and hook membership, but skip type/range checks.
        permissive = bool(case.get("allow_invalid") or case.get("negative"))
        for key, value in sets.items():
            b = by_id.get(key)
            if b is None:
                errors.append("%s: set.%s is not a block ID in the dlx"
                              % (where, key))
                continue
            if b["support"] != "yes":
                errors.append("%s: set.%s is a %s block; not injectable"
                              % (where, key, b["presentation"]))
            if hook_ids is not None and key not in hook_ids:
                errors.append("%s: set.%s is not in AUTODLG_HOOK(%s); "
                              "the hook will never read it"
                              % (where, key, ", ".join(hook_ids)))
            kind = b["kind"]
            if permissive:
                continue
            if kind == "enum":
                if not isinstance(value, int) or isinstance(value, bool):
                    errors.append("%s: set.%s must be an enum index (int), "
                                  "got %r" % (where, key, value))
                elif b["options"] and not (0 <= value < len(b["options"])):
                    errors.append("%s: set.%s index %d out of range 0..%d"
                                  % (where, key, value, len(b["options"]) - 1))
                elif not b["options"]:
                    errors.append("%s: set.%s enum has no options; run "
                                  "autodlg_patch.py --dlx" % (where, key))
            elif kind == "double":
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    errors.append("%s: set.%s must be a number" % (where, key))
            elif kind == "integer":
                if not isinstance(value, int) or isinstance(value, bool):
                    errors.append("%s: set.%s must be an int" % (where, key))
            elif kind == "logical":
                if not isinstance(value, bool) and value not in (0, 1):
                    errors.append("%s: set.%s must be true/false" % (where, key))
            elif kind == "selection":
                if value != "first_body":
                    warnings.append("%s: set.%s=%r; the shipped hook only "
                                    "supports 'first_body'" % (where, key, value))
            elif kind == "string":
                if not isinstance(value, str):
                    errors.append("%s: set.%s must be a string" % (where, key))

        expect = case.get("expect", {})
        if not isinstance(expect, dict):
            errors.append("%s: 'expect' must be an object" % where)
            continue
        for key in expect:
            if key in TOP_LEVEL_EXPECT_KEYS:
                continue
            b = by_id.get(key)
            if b is None:
                errors.append("%s: expect.%s is not a block ID in the dlx"
                              % (where, key))
                continue
            if b["support"] != "yes":
                warnings.append("%s: expect.%s is a %s block; it will not "
                                "have a got.* value"
                                % (where, key, b["presentation"]))
        if case.get("error_contains") and not expect.get("error_contains"):
            warnings.append("%s: 'error_contains' belongs under 'expect'" % where)

    return errors, warnings


def emit_cases(path, blocks, dll_name):
    cases = [{"name": "smoke_defaults",
              "expect": {"shown": 1, "hook_ran": 1}}]
    sets, expects = {}, {}
    for b in blocks:
        if b["support"] != "yes":
            continue
        kind = b["kind"]
        if kind == "selection":
            sets[b["id"]] = "first_body"
            expects[b["id"]] = 1
        elif kind == "enum":
            if b["options"]:
                sets[b["id"]] = 0
                expects[b["id"]] = 0
        elif kind == "double":
            sets[b["id"]] = 1.0
            expects[b["id"]] = 1.0
        elif kind == "integer":
            sets[b["id"]] = 1
            expects[b["id"]] = 1
        elif kind == "logical":
            sets[b["id"]] = True
            expects[b["id"]] = True
    if sets:
        cases.append({"name": "smoke_set", "set": sets, "expect": expects})
    cfg = {"title": "generated skeleton", "dll": dll_name,
           "part": None, "timeout_ms": 8000, "cases": cases}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cases


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dlx", required=True, help="generated .dlx")
    ap.add_argument("--hpp", help="generated .hpp (member names)")
    ap.add_argument("--cpp", help="patched .cpp (read AUTODLG_HOOK IDs)")
    ap.add_argument("--ids", help="comma-separated hook IDs instead of --cpp")
    ap.add_argument("--cases", help="cases.json to validate")
    ap.add_argument("--emit-cases", help="write a starter cases JSON here")
    ap.add_argument("--json", action="store_true", help="print JSON summary")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.dlx):
        print("error: dlx not found: %s" % args.dlx, file=sys.stderr)
        return 1
    try:
        blocks = parse_dlx(args.dlx)
    except Exception as exc:
        print("error: cannot parse %s as XML: %s" % (args.dlx, exc),
              file=sys.stderr)
        return 1
    members = parse_hpp_members(args.hpp) if args.hpp else {}
    hook_ids = None
    if args.cpp:
        hook_ids = parse_hook_ids(args.cpp)
        if hook_ids is None:
            print("warning: no AUTODLG_HOOK(...) found in %s" % args.cpp,
                  file=sys.stderr)
    if args.ids:
        hook_ids = [x.strip() for x in args.ids.split(",") if x.strip()]

    if not args.json:
        print_table(blocks, members, hook_ids)

    summary = {"dlx": os.path.abspath(args.dlx), "blocks": blocks,
               "hook_ids": hook_ids}
    errors, warnings = [], []
    if args.cases:
        errors, warnings = validate(args.dlx, blocks, args.cases, hook_ids)
        summary["errors"] = errors
        summary["warnings"] = warnings
        if not args.json:
            print("")
            print("validate %s: %d error(s), %d warning(s)" %
                  (args.cases, len(errors), len(warnings)))
            for e in errors:
                print("  ERROR   " + e)
            for w in warnings:
                print("  WARN    " + w)

    if args.emit_cases:
        base = os.path.splitext(os.path.basename(args.dlx))[0]
        dll = base + "_test.dll"
        cases = emit_cases(args.emit_cases, blocks, dll)
        summary["emitted"] = {"path": os.path.abspath(args.emit_cases),
                              "cases": len(cases)}
        if not args.json:
            print("")
            print("wrote %s (%d cases)" % (args.emit_cases, len(cases)))

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
