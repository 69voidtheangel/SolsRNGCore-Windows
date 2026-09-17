# SolsRNGCore Windows

This source tree is built by GitHub Actions on a real Windows runner.

The workflow produces:

- `SolsRNGCore.exe` — the PyInstaller single-file application, with Python, PySide6, requests, application code, assets, and the biome library bundled.
- `SolsRNGCore-Setup.exe` — an Inno Setup installer containing the application EXE.

The Windows build is deliberately isolated from Linux automation backends. The Windows package uses native Win32 `SendInput` and contains no runtime dependency on `xdotool`, `ydotool`, or Linux platform modules.

After a successful build, the workflow replaces the `main` branch contents with **only `SolsRNGCore-Setup.exe`**.

No local Windows installation is required to build it: push this project to GitHub and the Windows runner performs the build.
