# SolsRNGCore-Windows • Pixel Core v0.6.1

Windows-first Sol's RNG automation core focused on pixel detection, resolution-aware calibration, pixel-only fishing, an AutoHotkey 1.1 bridge, and an independent EndSol-style feature layer.

## v0.6.1

- AHK 1.1 Settings mirrors SendMode, key delay, press duration, mouse delay, mouse speed, queue polling, hotkeys, Roblox foreground protection, and emergency queue clearing.
- Settings are written to the local ahk_settings.ini file and reloaded without editing the script.
- A built-in Sol's RNG-style fishing simulator exercises the pixel-engine contract at the current resolution and in multi-resolution regression tests.
- Pixel-only fishing remains resolution-aware and calibration-driven.
- EndSol-style coverage includes Memory Match, Quest Board, merchant automation, custom paths, egg routes, potion/item actions, auto-pop hooks, multi-instance handling, Sol's Book caching, remote control, screenshots, and diagnostics.

UI-dependent actions require exact per-resolution calibration; the macro does not invent coordinates.

See docs/AHK.md, docs/SIMULATOR.md, and ENDSOL_FEATURES.md.
