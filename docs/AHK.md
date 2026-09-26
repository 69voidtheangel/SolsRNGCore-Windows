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
