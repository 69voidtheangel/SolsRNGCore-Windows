# AutoHotkey 1.1 bridge

Required version: AutoHotkey 1.1. The bridge uses v1.1 command syntax and does not depend on v2.

## GUI settings

The AHK 1.1 tab controls:

- Enable / auto-start
- Roblox foreground guard
- Queue poll interval
- SendMode: Input / Event / Play
- Key delay and press duration
- Mouse delay and default mouse speed
- Roblox window title
- Toggle / stop / emergency hotkeys
- Queue clearing on emergency stop

The GUI writes %LOCALAPPDATA%\SolsRNGCore-Windows\ahk_settings.ini. Apply / Reload AHK Settings queues RELOAD_SETTINGS; the running bridge re-reads the INI and rebinds the hotkeys.

## Queue

%LOCALAPPDATA%\SolsRNGCore-Windows\ahk_queue\ contains one command per file.

Supported commands: PRESS, KEYDOWN, KEYUP, CLICK, MOVE, TYPE, SLEEP, RUN, PING, RELOAD_SETTINGS, and EMERGENCY_STOP.

## Safety behavior

With foreground protection enabled, the bridge sends game input only while a matching Roblox window is active. The emergency hotkey can stop the bridge and clear pending queue files.

## Native AHK control panel
The `ahk/SolsRNGCore-Windows.ahk` file now includes its own AutoHotkey 1.1 GUI. It can be run directly from AutoHotkey and provides runtime controls, hotkey configuration, input timing settings, start/stop/emergency actions, and a bridge test. The GUI and Python application use the same `%LOCALAPPDATA%\\SolsRNGCore-Windows\\ahk_settings.ini` and `ahk_queue` directory.

## v0.6.2 fix
The native GUI control variables are explicitly global for AutoHotkey 1.1 function scope, preventing the startup error `A control's variable must be global or static`.

## v0.6.4 styling
The native AHK 1.1 panel now uses SolsRNGCore branding: dark purple window colors, magenta accenting, a branded header, dark input surfaces, and accented runtime telemetry. The underlying controls and Python action queue remain unchanged.
