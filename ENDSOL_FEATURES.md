# EndSol feature coverage

This project implements the major publicly documented EndSol Macro feature areas with an independent codebase. Public feature descriptions are used as a compatibility checklist; EndSol's source code is not copied here.

| Feature area | SolsRNGCore-Windows | Notes |
|---|---|---|
| Biome detection / alerts | Implemented | Pixel-first detection + Discord notifications. |
| Aura alerts | Implemented | Windows OCR fallback + screenshots. |
| Fishing | Implemented | Pixel-only minigame; resolution-aware calibration; auto-sell/failsafes. |
| Memory Match | Implemented | Pixel-signature 5x4 pair matching; calibration required. |
| Quest Board | Implemented | OCR classification + calibrated accept/dismiss action. |
| Merchant automation | Implemented | OCR-assisted scan + configured item click anchors. |
| Custom paths / recorder | Implemented | Stored in AppData; replay uses the AHK 1.1 bridge. |
| Egg collection routes | Implemented | Route runner is custom-path based. |
| Potion crafting / item actions | Implemented | Existing item automation plus generic action hooks. |
| Auto-pop buffs | Implemented | Uses configured timed item actions. |
| Multi-instance | Implemented | Roblox top-level window enumeration/focus. |
| Sol's Book | Implemented | Cached MediaWiki search for the Sol's RNG wiki. |
| Remote control | Implemented | Authenticated loopback HTTP; optional Discord.py control is available in the feature module. |
| Screenshot events | Implemented | Biomes, aura, merchant, fishing, rejoin, manual/periodic. |
| Live diagnostics | Implemented | Persistent logs and session reporting. |

Feature-specific Roblox UI actions remain disabled until the required calibration exists. This is deliberate: the macro does not invent coordinates for an unverified resolution or UI state.

## AHK

The Windows bridge targets AutoHotkey 1.1. It contains no AutoHotkey v2-only directives or function-call command syntax.
