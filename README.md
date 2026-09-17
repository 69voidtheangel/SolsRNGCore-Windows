# SolsRNGCore Windows

Windows-native port of **SolsRNGCore**.

This repository keeps the shared Sol's RNG core, Discord notification system, profile persistence, GUI, automation model, and diagnostics, while replacing the Linux-specific input/window layer with native Windows APIs.

## Windows-specific changes

- Native `user32.SendInput` keyboard input
- Native Win32 window discovery/focus via `EnumWindows`, `GetWindowTextW`, and `SetForegroundWindow`
- Native cursor/click injection via `SetCursorPos` + mouse events
- No `ydotool`, `xdotool`, `wdotool`, or Linux session dependencies
- `%LOCALAPPDATA%\SolsRNGCore\core.json` configuration
- Roblox log discovery under `%LOCALAPPDATA%\Roblox\logs` / `%APPDATA%\Roblox\logs`
- `SOLSRNG_ROBLOX_LOG_DIR` can override log discovery

## Important

The Windows port is designed as a platform port, not a claim that every Roblox log source is identical to Sober. The log watcher preserves the existing RPC parser and makes the log directory configurable so the correct Windows log source can be tested without hard-coding an unsupported path.

## Run

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

## Build an executable

PyInstaller is intentionally optional:

```powershell
python -m pip install pyinstaller
pyinstaller --noconfirm --windowed --name SolsRNGCore main.py
```

## Notes

- Roblox window automation uses absolute screen coordinates, matching the existing SolsRNGCore automation design.
- Run display scaling at a predictable value when recording coordinates.
- The first Windows implementation should be validated against the exact Roblox/Bloxstrap log format on the target machine.
