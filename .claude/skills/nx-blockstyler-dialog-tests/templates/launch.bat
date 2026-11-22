@echo off
setlocal
set "PROJECT=%~dp0"
if "%PROJECT:~-1%"=="\" set "PROJECT=%PROJECT:~0,-1%"
cd /d "%PROJECT%"

rem ---------------------------------------------------------------------------
rem Configure these four lines (or set them in the environment before calling).
rem ---------------------------------------------------------------------------
if "%DIALOG%"=="" set "DIALOG=baseDialog"
if "%NX_EXE%"=="" set "NX_EXE=D:\Program Files\Siemens\NX 10.0\UGII\ugraf.exe"
if "%PART%"=="" set "PART=D:\Program Files\Siemens\NX 10.0\UGII\drafting_welcome\sample_parts\flange.prt"
if "%TIMEOUT_MS%"=="" set "TIMEOUT_MS=8000"

rem These MUST be set before NX starts. The DLL's getenv() cannot see changes
rem made later from NX's Python.
set "UGII_USER_DIR=%PROJECT%"
set "AUTODLG_HOME=%PROJECT%"
set "AUTODLG_CASE=%PROJECT%\tmp\cases\current.ini"
set "AUTODLG_OUT=%PROJECT%\tmp\results\current.ini"
set "AUTODLG_TIMEOUT_MS=%TIMEOUT_MS%"

if not exist application mkdir application
copy /y "%DIALOG%.dlx" "application\%DIALOG%.dlx" >nul
if errorlevel 1 exit /b 1
if not exist tmp\cases mkdir tmp\cases
if not exist tmp\results mkdir tmp\results
del /q tmp\running.json 2>nul
del /q tmp\results\current.ini 2>nul

echo Environment ready for NX.
echo   UGII_USER_DIR = %UGII_USER_DIR%
echo   AUTODLG_CASE  = %AUTODLG_CASE%
echo   AUTODLG_OUT   = %AUTODLG_OUT%
echo   timeout       = %AUTODLG_TIMEOUT_MS% ms
if defined AUTODLG_NO_CLOSE echo   NO_CLOSE      = %AUTODLG_NO_CLOSE%
echo.
echo Start NX, open a part with a body, then run the harness:
echo   1) MCP: nx_run_python -^> run_cases.main(cases_path=r"%PROJECT%\cases.json", dry_run=False)
echo   2) or NX menu: Tools -^> Journal -^> Play... and select "%PROJECT%\run_cases.py"
echo   3) or a single smoke: File -^> Execute -^> NX Open, pick "%DIALOG%_test.dll"
echo.
echo Close NX when done; this script then writes tmp\summary.txt.
echo.

"%NX_EXE%" -part "%PART%"

echo.
if exist tmp\manifest.json (
  python "%PROJECT%\report.py" --manifest "%PROJECT%\tmp\manifest.json" ^
    --results "%PROJECT%\tmp\results" ^
    --out-json "%PROJECT%\tmp\results.json" ^
    --out-txt "%PROJECT%\tmp\summary.txt"
  if exist tmp\summary.txt type tmp\summary.txt
) else (
  echo No tmp\manifest.json - run_cases.py was not run.
)
