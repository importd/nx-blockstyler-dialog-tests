# -*- coding: utf-8 -*-
"""Fail if a DLL contains the test hook. The hook's Win32 user32 import is the
reliable marker (inline functions leave no readable namespace symbols)."""

import sys

MARKERS = (
    "autodlg::collect",
    "autodlg::finish",
    "autodlg::run_hook",
    "AUTODLG_HOOK",
    "user32.dll",
)


def main(path):
    with open(path, "rb") as f:
        data = f.read().lower()
    hits = [m for m in MARKERS if m.lower().encode() in data]
    if hits:
        print("test hook markers found in %s: %s" % (path, ", ".join(hits)))
        return 1
    print("prod ok: %s has no test hook markers" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
