# SolsRNGCore-Windows

Windows-native SolsRNGCore packaged as a single executable plus an optional installer.

## Output

- `dist\SolsRNGCore-Windows.exe` — the main **single-file EXE**. Python, PySide6, requests, application code, assets, and the bundled biome library are packaged into it.
- `installer\output\SolsRNGCore-Windows-Setup.exe` — a normal Windows installer that installs that EXE, creates Start Menu/uninstall entries, and can optionally create a desktop shortcut.

## Dependencies

The end-user does **not** need Python, pip, PySide6, requests, or the source tree. Those runtime dependencies are bundled into the main EXE by PyInstaller.

The Windows build machine needs:

- Python 3.10+
- PyInstaller 6.x
- Inno Setup 6 (only for building the installer)

Run `build_windows.bat` on Windows. It installs the Python build dependencies, builds the one-file EXE, then builds the installer.
