@echo off
setlocal EnableExtensions
cd /d "%~dp0"

py -m pip install --upgrade pip
if errorlevel 1 exit /b %errorlevel%
py -m pip install -r requirements.txt "PyInstaller>=6,<7"
if errorlevel 1 exit /b %errorlevel%

py -m PyInstaller --clean --noconfirm solsrngcore_windows.spec
if errorlevel 1 exit /b %errorlevel%

echo Main EXE: dist\SolsRNGCore.exe
