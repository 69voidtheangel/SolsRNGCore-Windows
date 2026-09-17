@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "dist" mkdir "dist"
if not exist "installer\output" mkdir "installer\output"

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher ^(py^) was not found.
    echo Install Python 3.11+ for Windows and try again.
    exit /b 1
)

echo [1/4] Installing/updating build dependencies...
py -m pip install --upgrade pip
if errorlevel 1 exit /b %errorlevel%
py -m pip install -r requirements.txt "PyInstaller>=6,<7"
if errorlevel 1 exit /b %errorlevel%

echo [2/4] Building single-file executable...
py -m PyInstaller --clean --noconfirm solsrngcore_windows.spec
if errorlevel 1 exit /b %errorlevel%

where ISCC.exe >nul 2>nul
if errorlevel 1 (
    echo.
    echo Inno Setup compiler ISCC.exe was not found.
    echo The main EXE was built successfully:
    echo   dist\SolsRNGCore-Windows.exe
    echo Install Inno Setup, then run this script again to create the installer.
    exit /b 2
)

echo [3/4] Building installer...
ISCC.exe installer.iss
if errorlevel 1 exit /b %errorlevel%

echo [4/4] Done.
echo Main EXE:   dist\SolsRNGCore-Windows.exe
echo Installer:  installer\output\SolsRNGCore-Windows-Setup.exe
endlocal
