@echo off
setlocal
cd /d E:\Code\auto-dialog

set "UGII_USER_DIR=E:\Code\auto-dialog"
set "AUTODLG_CASE=E:\Code\auto-dialog\tmp\cases\current.ini"
set "AUTODLG_OUT=E:\Code\auto-dialog\tmp\results\current.ini"
set "AUTODLG_TIMEOUT_MS=8000"

if not exist application mkdir application
copy /y baseDialog.dlx application\baseDialog.dlx >nul
if not exist tmp\cases mkdir tmp\cases
if not exist tmp\results mkdir tmp\results

echo Environment ready for NX 10.
echo Start NX 10, open a part with a body, then run the harness:
echo   1) MCP: nx_run_python -^> run_cases.main(cases_path=r"E:\Code\auto-dialog\cases.json", dry_run=False)
echo   2) or NX menu: Tools -^> Journal -^> Play... and select E:\Code\auto-dialog\run_cases.py
echo.
echo Close NX when done; this script then writes tmp\summary.txt.
echo.

"D:\Program Files\Siemens\NX 10.0\UGII\ugraf.exe"

echo.
if exist tmp\manifest.json (
  python report.py --manifest tmp\manifest.json --results tmp\results ^
    --out-json tmp\results.json --out-txt tmp\summary.txt
  if exist tmp\summary.txt type tmp\summary.txt
) else (
  echo No tmp\manifest.json - run_cases.py was not run.
)
