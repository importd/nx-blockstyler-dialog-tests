# -*- coding: utf-8 -*-
"""Fail if a DLL contains the test hook.

The hook's getenv() literals are the reliable marker: they are compiled only
under AUTODLG_TEST, and they survive -Ox because getenv() references them.
Exported/inline symbol names (autodlg::collect) may be absent after inlining,
and user32.dll is a legitimate import for many production plugins, so neither
is used as the sole marker.
"""

import sys

MARKERS = (
    "AUTODLG_CASE",
    "AUTODLG_OUT",
    "AUTODLG_TIMEOUT_MS",
    "AUTODLG_NO_CLOSE",
    "AUTODLG_KILL_ON_HANG",
    "AUTODLG_HOOK",
    "autodlg::collect",
    "autodlg::finish",
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
