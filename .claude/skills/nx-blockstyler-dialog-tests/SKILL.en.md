---
name: nx-blockstyler-dialog-tests
description: Use when adding unattended regression tests to a C++ NX Open plugin that ships a Block UI Styler dialog (NX 10/11/12, .dlx + generated .cpp/.hpp); triggers on dialog regression, unattended tests, injecting blocks, apply_cb, Block Styler, dlx, and NX 10 tests, even when the user does not name a skill. C++ plugin dialogs only.
---

# Unattended tests for NX Block Styler dialogs (C++ plugins)

English mirror of `SKILL.md`; the Chinese file is authoritative.

**Principle: compile the hook into the real DLL, then inject → read back → assert
→ close inside `dialogShown_cb`.** A Python `CreateDialog` copy registers Python
callbacks — the plugin's `apply_cb` never runs.

One case: `ufusr` → `Show()` → `dialogShown_cb` → `AUTODLG_HOOK` → result file
→ background `WM_CLOSE`.

Path: copy templates → configure → list IDs/validate cases → patch → build →
launch NX → run `run_cases.py` → read `tmp\summary.txt`. Commands assume
Windows + NX 10 + VS2019.

## 0. Prerequisites

```bat
cmd /c mklink /J C:\Users\feather\nx10 "D:\Program Files\Siemens\NX 10.0"
dir "C:\Users\feather\nx10\UGOPEN\uflink.bat"
dir "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
```

Close NX before building (`LNK1104`). Have a part with a body
(`flange.prt` works). Keep project paths ASCII.

**Verified when:** both `dir` checks exist, NX is closed, part path known.

## 1. Copy templates and configure

```bat
xcopy /E /I /Y "<skill>\templates" "<plugin_dir>"
```

Edit `build.bat` (`DIALOG`, `NX`, `VCVARS`), `launch.bat` (`DIALOG`, `NX_EXE`,
`PART`, `TIMEOUT_MS`), and `cases.json` (`dll`, `part`, `timeout_ms`, `cases`).
`DIALOG=baseDialog` drives all four file names.

**Verified when:** all 9 template files are in the project root and point at
your dialog.

## 2. List Block IDs and validate cases

```bat
python "<skill>\scripts\inspect_dialog.py" --dlx baseDialog.dlx --hpp baseDialog.hpp
python "<skill>\scripts\inspect_dialog.py" --dlx baseDialog.dlx --cases cases.json
```

Put only injectable blocks in `AUTODLG_HOOK`: Selection, Enumeration, Double,
Integer, Logical, String — not Group/Label/Separator/Button/Tab. Keep the order
fixed. Enums need options in both `Titles` and `Titles_1` in the dlx.

**Verified when:** you have the suggested hook line and `--cases` reports zero
errors.

## 3. Patch

```bat
python autodlg_patch.py --cpp baseDialog.cpp --dlx baseDialog.dlx ^
    --ids selection0,enum0,linear_dim0 --make-test-cpp
```

It defines `USER_EXIT_OR_MENU`, includes `autodlg_test.h`, and inserts
`AUTODLG_HOOK(...)` at the **end** of `dialogShown_cb`'s `try` body (blocks only
exist after `Show()`). Rerun after every Block Styler regeneration; idempotent.

**Verified when:** `findstr /n "AUTODLG_HOOK autodlg_test.h USER_EXIT_OR_MENU"
baseDialog.cpp` shows exactly three hits.

## 4. Build and check isolation

```bat
build.bat
build.bat prod
python check_prod.py baseDialog.dll          :: prod ok
python check_prod.py baseDialog_test.dll     :: non-zero, lists markers
dumpbin /exports baseDialog_test.dll | findstr /i "ufusr"
```

Use `/MD` and a no-space junction. `build.bat` copies the dlx to `application\`;
rebuild/recopy after editing the dlx.

**Verified when:** prod passes, the test DLL fails the check, and `ufusr` is
exported.

## 5. Launch NX and run

```bat
launch.bat
```

`launch.bat` sets `UGII_USER_DIR`, `AUTODLG_CASE`, `AUTODLG_OUT`, and
`AUTODLG_TIMEOUT_MS` **before** NX starts. No `-batch`; `-journal` does not
execute on the tested machines. Keep one NX session.

```python
import sys
sys.path.insert(0, r"E:\Code\auto-dialog")
import run_cases
run_cases.main(cases_path=r"E:\Code\auto-dialog\cases.json", dry_run=False)
```

Or `Tools -> Journal -> Play...` with `run_cases.py`.

**Verified when:** `tmp\summary.txt` exists with one entry per case.

## 6. Read results (PASS criteria)

| Field | Meaning |
|---|---|
| `shown=1` | `dialogShown_cb` fired; `0` → check dlx path / `UGII_USER_DIR` / part |
| `hook_ran=1` | the hook completed |
| `close_attempted=1` | a close was attempted; `0` → `AUTODLG_NO_CLOSE=1` |
| `apply_rc=` | `apply_cb()` return; empty = not called |
| `error=` | injection/read error; must be empty on PASS |
| `got.<id>=` | read-back value |

No error is not a PASS: every PASS needs `shown=1`, `hook_ran=1`,
`close_attempted=1`, and empty `error`. Negative cases opt out with
`allow_error` or `expect.error_contains`.

Case order: defaults → set values → select body → `apply: true` (+ a concrete
business assertion) → failure path; each green before the next.

**Verified when:** every PASS `.ini` has `shown=1`, `hook_ran=1`,
`close_attempted=1`, empty `error`, and apply has a business value. Then run
twice: same results, no dialog left open.

## 7. When it breaks

Look up the symptom in `references/pitfalls.md` (`LNK1104`, `C2039`, `SetEnum`
errors, dialog not shown / won't close). Build and launch details:
`references/build-and-run.md`; block keys: `references/block-api.md`; case
fields: `references/cases-and-report.md`.

Reference implementation: `E:\Code\auto-dialog` (NX 10).
