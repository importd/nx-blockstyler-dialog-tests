@echo off
setlocal
set "PROJECT=%~dp0"
if "%PROJECT:~-1%"=="\" set "PROJECT=%PROJECT:~0,-1%"
cd /d "%PROJECT%"

rem ---------------------------------------------------------------------------
rem Configure these three lines. They can also be set in the environment before
rem calling this script.
rem ---------------------------------------------------------------------------
if "%DIALOG%"=="" set "DIALOG=baseDialog"
if "%NX%"=="" set "NX=C:\Users\feather\nx10"
if "%VCVARS%"=="" set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"

set "UGII_BASE_DIR=%NX%"
set "UGII_USERFCN=%NX%\UGOPEN"
set "UGII_ROOT_DIR=%NX%\UGII"
set "PATH=%NX%\UGII;%NX%\UGOPEN;%PATH%"

if not exist "%DIALOG%.dlx" goto :no_dlx
if not exist "%DIALOG%.cpp" goto :no_cpp
if not exist "%DIALOG%_test.cpp" goto :no_test
if not exist "%UGII_USERFCN%\uflink.bat" goto :no_uflink
if not exist "%VCVARS%" goto :no_vcvars

call "%VCVARS%" >nul
if errorlevel 1 exit /b 1

if not exist application mkdir application
copy /y "%DIALOG%.dlx" "application\%DIALOG%.dlx" >nul
if errorlevel 1 exit /b 1

set "NODEBUG=1"
set "CLFLAGS=-nologo -c -EHsc -DCRTAPI1=_cdecl -DCRTAPI2=_cdecl -GS -D_AMD64_=1 -DWIN64 -D_WIN64 -DWIN32 -D_WIN32 -W4 -D_WIN32_IE=0x0500 -DWINVER=0x0500 -Ox -DNDEBUG -D_MT -D_DLL -MD -I. -I%UGII_USERFCN%"

if "%~1"=="prod" goto prod

cl %CLFLAGS% "%DIALOG%_test.cpp"
if errorlevel 1 exit /b 1
call "%UGII_USERFCN%\uflink.bat" UFDLL "%DIALOG%_test.dll"
if errorlevel 1 exit /b 1
echo built %DIALOG%_test.dll
exit /b 0

:prod
cl %CLFLAGS% "%DIALOG%.cpp"
if errorlevel 1 exit /b 1
call "%UGII_USERFCN%\uflink.bat" UFDLL "%DIALOG%.dll"
if errorlevel 1 exit /b 1
echo built %DIALOG%.dll
exit /b 0

:no_dlx
echo missing %DIALOG%.dlx
exit /b 1
:no_cpp
echo missing %DIALOG%.cpp
exit /b 1
:no_test
echo missing %DIALOG%_test.cpp
exit /b 1
:no_uflink
echo missing uflink.bat under %UGII_USERFCN%
exit /b 1
:no_vcvars
echo missing vcvars64.bat: %VCVARS%
exit /b 1
