@echo off
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"

set "NX=C:\Users\feather\nx10"
set "UGII_BASE_DIR=%NX%"
set "UGII_USERFCN=%NX%\UGOPEN"
set "UGII_ROOT_DIR=%NX%\UGII"
set "PATH=%NX%\UGII;%NX%\UGOPEN;%PATH%"

call "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1

cd /d "%ROOT%"
if not exist build mkdir build
if not exist application mkdir application
copy /y src\baseDialog.dlx application\baseDialog.dlx >nul
if errorlevel 1 exit /b 1

set "NODEBUG=1"

if "%~1"=="prod" goto prod

cl -nologo -c -EHsc -DCRTAPI1=_cdecl -DCRTAPI2=_cdecl -GS ^
   -D_AMD64_=1 -DWIN64 -D_WIN64 -DWIN32 -D_WIN32 -W4 ^
   -D_WIN32_IE=0x0500 -DWINVER=0x0500 -Ox -DNDEBUG ^
   -D_MT -D_DLL -MD -Isrc -I"%UGII_USERFCN%" -Fobuild\ src\baseDialog_test.cpp
if errorlevel 1 exit /b 1

pushd build
call "%UGII_USERFCN%\uflink.bat" UFDLL baseDialog_test.dll
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" exit /b 1
echo built build\baseDialog_test.dll
exit /b 0

:prod
cl -nologo -c -EHsc -DCRTAPI1=_cdecl -DCRTAPI2=_cdecl -GS ^
   -D_AMD64_=1 -DWIN64 -D_WIN64 -DWIN32 -D_WIN32 -W4 ^
   -D_WIN32_IE=0x0500 -DWINVER=0x0500 -Ox -DNDEBUG ^
   -D_MT -D_DLL -MD -Isrc -I"%UGII_USERFCN%" -Fobuild\ src\baseDialog.cpp
if errorlevel 1 exit /b 1

pushd build
call "%UGII_USERFCN%\uflink.bat" UFDLL baseDialog.dll
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" exit /b 1
echo built build\baseDialog.dll
exit /b 0
