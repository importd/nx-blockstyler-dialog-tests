@echo off
setlocal
cd /d E:\Code\auto-dialog

set "NX=C:\Users\feather\nx10"
set "UGII_BASE_DIR=%NX%"
set "UGII_USERFCN=%NX%\UGOPEN"
set "UGII_ROOT_DIR=%NX%\UGII"
set "PATH=%NX%\UGII;%NX%\UGOPEN;%PATH%"

call "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1

if not exist application mkdir application
copy /y baseDialog.dlx application\baseDialog.dlx >nul

set "NODEBUG=1"

cl -nologo -c -EHsc -DCRTAPI1=_cdecl -DCRTAPI2=_cdecl -GS ^
   -D_AMD64_=1 -DWIN64 -D_WIN64 -DWIN32 -D_WIN32 -W4 ^
   -D_WIN32_IE=0x0500 -DWINVER=0x0500 -Ox -DNDEBUG ^
   -D_MT -D_DLL -MD -I. -I"%UGII_USERFCN%" baseDialog.cpp
if errorlevel 1 exit /b 1

call "%UGII_USERFCN%\uflink.bat" UFDLL baseDialog.dll
if errorlevel 1 exit /b 1

echo built baseDialog.dll
