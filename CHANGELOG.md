# Changelog

## 0.6.4
- Restyled the native AutoHotkey 1.1 control panel to match the SolsRNGCore dark-purple / magenta visual language.
- Added branded header, accent line, dark input surfaces, telemetry accent text, and a Windows dark-title-bar hint where supported.
- Kept the full v0.6.3 feature/control surface intact.


## 0.6.2
- Fixed the native AHK 1.1 GUI startup error caused by GUI control variables being local inside a function.
- Declared all GUI control variables global so the `.ahk` script opens normally in AutoHotkey 1.1.
- Re-ran the Python test suite: 21 passed.


## 0.6.1
- Added a native AutoHotkey 1.1 control panel to the `.ahk` script.
- The AHK script can now be launched directly in AutoHotkey without relying on the Python GUI.
- AHK GUI, tray menu, hotkeys, settings INI, command queue, and Python bridge share the same state.


## 0.6.0

- Added an AHK 1.1 settings panel and persisted INI configuration for the bridge.
- Added configurable SendMode, key delay, press duration, mouse delay, mouse speed, queue polling, Roblox foreground guard, hotkeys, and emergency queue policy.
- Added PING, RELOAD_SETTINGS, and EMERGENCY_STOP queue commands.
- Added a deterministic Sol's RNG-style fishing UI simulator and a GUI button for the current resolution.
- Added multi-resolution simulator coverage for 1280x720, 1280x800, 1920x1080, 2560x1440, and 3840x2160.
- Local validation: 21 tests passed and Python compilation passed.
