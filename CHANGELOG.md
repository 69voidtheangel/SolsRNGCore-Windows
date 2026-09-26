# Changelog

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
