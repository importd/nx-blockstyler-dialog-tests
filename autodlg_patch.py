# -*- coding: utf-8 -*-
"""Idempotently patch the Block Styler C++ source and dlx for the test harness."""

import argparse
import os
import re
import shutil

DEFINE = "#define USER_EXIT_OR_MENU 1"
INCLUDE_BLOCK = '#ifdef AUTODLG_TEST\n#include "autodlg_test.h"\n#endif'
HOOK_BLOCK = ('#ifdef AUTODLG_TEST\n'
              '    AUTODLG_HOOK(theDialog, "selection0", "enum0", "linear_dim0");\n'
              '#endif')

_TAG_RE = re.compile(r"<Property\b[^>]*/>")


def patch_cpp(text):
    if "AUTODLG_HOOK" not in text:
        marker = "void baseDialog::dialogShown_cb()"
        start = text.find(marker)
        if start < 0:
            raise RuntimeError("dialogShown_cb not found")
        try_pos = text.find("try", start)
        brace = text.find("{", try_pos) if try_pos >= 0 else -1
        if try_pos < 0 or brace < 0:
            raise RuntimeError("try block not found in dialogShown_cb")
        text = text[:brace + 1] + "\n" + HOOK_BLOCK + "\n" + text[brace + 1:]
    if "autodlg_test.h" not in text:
        marker = '#include "baseDialog.hpp"'
        if marker not in text:
            raise RuntimeError('include "baseDialog.hpp" not found')
        text = text.replace(marker, marker + "\n" + INCLUDE_BLOCK, 1)
    if DEFINE not in text:
        text = DEFINE + "\n" + text
    return text


def _dlx_repl(match):
    tag = match.group(0)
    if 'id="Titles"' in tag and 'type="utfstrings"' in tag:
        return (tag[:-2] + '>'
                '<Strings value="A"/><Strings value="B"/><Strings value="C"/>'
                '</Property>')
    if 'id="Titles_1"' in tag and 'type="enum"' in tag:
        return (tag[:-2] + '>'
                '<Option name="A" value="0"/><Option name="B" value="1"/>'
                '<Option name="C" value="2"/></Property>')
    return tag


def patch_dlx(text):
    return _TAG_RE.sub(_dlx_repl, text)


def _patch_file(path, fn):
    with open(path, encoding="utf-8") as f:
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
    args = parser.parse_args(argv)
    if args.cpp:
        changed = _patch_file(args.cpp, patch_cpp)
        print("cpp: %s" % ("patched" if changed else "unchanged"))
    if args.dlx:
        changed = _patch_file(args.dlx, patch_dlx)
        print("dlx: %s" % ("patched" if changed else "unchanged"))


if __name__ == "__main__":
    main()
