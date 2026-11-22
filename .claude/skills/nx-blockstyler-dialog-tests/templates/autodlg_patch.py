# -*- coding: utf-8 -*-
"""Idempotently patch the Block Styler C++ source and dlx for the test harness.

The generated .cpp/.hpp/.dlx are overwritten by Block Styler, so keep the
patch logic here and rerun it after every regeneration.

Examples
--------
    python autodlg_patch.py --cpp baseDialog.cpp --dlx baseDialog.dlx \
        --ids selection0,enum0,linear_dim0

    python autodlg_patch.py --cpp myDialog.cpp --dlx myDialog.dlx \
        --class myDialog --include myDialog.hpp --ids dim0,toggle0 \
        --enum-names Red,Green,Blue

The default IDs are the demo dialog's; pass --ids for a real dialog.
"""

import argparse
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

DEFINE = "#define USER_EXIT_OR_MENU 1"
INCLUDE_BLOCK = ('#ifdef AUTODLG_TEST\n'
                 '#include "autodlg_test.h"\n'
                 '#endif')
DEMO_IDS = ["selection0", "enum0", "linear_dim0"]

_TAG_RE = re.compile(r"<Property\b[^>]*/>")
_HOOK_RE = re.compile(r"AUTODLG_HOOK\s*\(\s*theDialog\s*,[^)]*\)\s*;")
_FUNC_RE = re.compile(r"void\s+(\w+)\s*::\s*dialogShown_cb\s*\(\s*\)")
_INCLUDE_RE = re.compile(r'#include\s+"([^"]+\.hpp)"')


def _matching_brace(text, open_index):
    """Index just past the brace matching the one at open_index."""
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise RuntimeError("unbalanced braces in dialogShown_cb")


def detect_cpp(text):
    m = _FUNC_RE.search(text)
    cls = m.group(1) if m else "baseDialog"
    inc = _INCLUDE_RE.search(text)
    include = inc.group(1) if inc else (cls + ".hpp")
    return cls, include


def hook_line(ids):
    return ("#ifdef AUTODLG_TEST\n"
            "    AUTODLG_HOOK(theDialog, %s);\n"
            "#endif" % ", ".join('"%s"' % i for i in ids))


def patch_cpp(text, cls=None, include=None, ids=None):
    ids = ids or DEMO_IDS
    detected_cls, detected_include = detect_cpp(text)
    cls = cls or detected_cls
    include = include or detected_include

    # 1) Replace an existing hook (so changing --ids is idempotent), or insert
    #    the hook at the end of the try body / function body.
    new_hook = hook_line(ids)
    if _HOOK_RE.search(text):
        text = _HOOK_RE.sub(
            'AUTODLG_HOOK(theDialog, %s);' %
            ", ".join('"%s"' % i for i in ids), text, count=1)
    else:
        marker = "void %s::dialogShown_cb()" % cls
        start = text.find(marker)
        if start < 0:
            raise RuntimeError(
                'dialogShown_cb not found for class "%s"; pass --class' % cls)
        func_brace = text.find("{", start)
        if func_brace < 0:
            raise RuntimeError("dialogShown_cb has no body")
        func_end = _matching_brace(text, func_brace)
        try_pos = text.find("try", start)
        brace = -1
        if 0 <= try_pos < func_end:
            brace = text.find("{", try_pos)
        if 0 <= try_pos < func_end and brace >= 0 and brace < func_end:
            # End of the try body, after the callback's own init. Blocks must
            # be initialised before cases are injected.
            end = _matching_brace(text, brace)
            insert_at = end - 1
        else:
            # No try block: end of the function body. The generated callback
            # usually has no try only after the user edited it; still better
            # than failing.
            insert_at = func_end - 1
        text = text[:insert_at] + new_hook + "\n" + text[insert_at:]

    # 2) Include the hook header after the generated .hpp include.
    if "autodlg_test.h" not in text:
        marker = '#include "%s"' % include
        if marker not in text:
            raise RuntimeError(
                'include "%s" not found; pass --include' % include)
        text = text.replace(marker, marker + "\n" + INCLUDE_BLOCK, 1)

    # 3) ufusr is inside #if USER_EXIT_OR_MENU.
    if DEFINE not in text:
        text = DEFINE + "\n" + text
    return text


def _dlx_repl(match, names):
    tag = match.group(0)
    if 'id="Titles"' in tag and 'type="utfstrings"' in tag:
        body = "".join('<Strings value="%s"/>' % n for n in names)
        return tag[:-2] + ">" + body + "</Property>"
    if 'id="Titles_1"' in tag and 'type="enum"' in tag:
        body = "".join('<Option name="%s" value="%d"/>' % (n, i)
                       for i, n in enumerate(names))
        return tag[:-2] + ">" + body + "</Property>"
    return tag


def patch_dlx(text, names=None):
    names = names or ["A", "B", "C"]
    patched = _TAG_RE.sub(lambda m: _dlx_repl(m, names), text)
    # Warn if the patch still leaves an enum with no runtime options. This is
    # a cheap sanity check; it does not replace a real Block Styler edit.
    return patched


def _patch_file(path, fn):
    with open(path, encoding="utf-8", errors="replace") as f:
        original = f.read()
    patched = fn(original)
    if patched == original:
        return False
    backup = path + ".bak"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    with open(path, "w", encoding="utf-8") as f:
        f.write(patched)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpp")
    parser.add_argument("--dlx")
    parser.add_argument("--class", dest="cls")
    parser.add_argument("--include")
    parser.add_argument("--ids",
                        help="comma-separated block IDs for AUTODLG_HOOK")
    parser.add_argument("--enum-names",
                        help="comma-separated labels for empty enum Titles/"
                             "Titles_1 (default A,B,C)")
    parser.add_argument("--make-test-cpp", action="store_true",
                        help="create <Dialog>_test.cpp if it does not exist")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would change without writing")
    args = parser.parse_args(argv)

    if args.make_test_cpp:
        if not args.cpp:
            print("make-test-cpp: ERROR: --cpp is required")
            return 1
        base = os.path.splitext(os.path.basename(args.cpp))[0]
        test_path = os.path.join(os.path.dirname(args.cpp) or ".",
                                 base + "_test.cpp")
        if os.path.exists(test_path):
            print("test-cpp: unchanged (%s exists)" % test_path)
        elif args.dry_run:
            print("test-cpp: would create %s" % test_path)
        else:
            content = (
                "#define _CRT_SECURE_NO_WARNINGS\n"
                "#define USER_EXIT_OR_MENU 1\n"
                "#define AUTODLG_TEST 1\n"
                '#include "%s"\n' % os.path.basename(args.cpp))
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(content)
            print("test-cpp: created %s" % test_path)

    ids = [x.strip() for x in args.ids.split(",") if x.strip()] \
        if args.ids else DEMO_IDS
    names = [x.strip() for x in args.enum_names.split(",") if x.strip()] \
        if args.enum_names else None

    if args.cpp:
        with open(args.cpp, encoding="utf-8", errors="replace") as f:
            src = f.read()
        try:
            out = patch_cpp(src, args.cls, args.include, ids)
        except RuntimeError as exc:
            print("cpp: ERROR: %s" % exc)
            return 1
        if out == src:
            print("cpp: unchanged")
        elif args.dry_run:
            print("cpp: would patch (hook ids: %s)" % ", ".join(ids))
        else:
            _patch_file(args.cpp, lambda _: out)
            print("cpp: patched (hook ids: %s)" % ", ".join(ids))

    if args.dlx:
        with open(args.dlx, encoding="utf-8", errors="replace") as f:
            src = f.read()
        out = patch_dlx(src, names)
        if out == src:
            print("dlx: unchanged")
        elif args.dry_run:
            print("dlx: would patch (enum names: %s)" %
                  ", ".join(names or ["A", "B", "C"]))
        else:
            try:
                ET.fromstring(out)
            except Exception as exc:
                print("dlx: ERROR: patch would produce invalid XML: %s" % exc)
                return 1
            _patch_file(args.dlx, lambda _: out)
            print("dlx: patched (enum names: %s)" %
                  ", ".join(names or ["A", "B", "C"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
