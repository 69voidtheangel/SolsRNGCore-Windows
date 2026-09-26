# Built-in pixel simulator

solsrng_windows.simulator.SolsRNGFishingSimulator is a deterministic synthetic fishing UI used to validate the pixel engine without requiring Roblox to be running.

It covers the same calibrated states consumed by the engine:

- idle
- catch-ready pixel
- moving reel marker with shaded target
- completed state

Automated coverage runs at 1280x720, 1280x800, 1920x1080, 2560x1440, and 3840x2160. The Fishing tab also exposes Run Built-in Simulator Test for the current display.

The public Sol's RNG Rolling Simulator is a separate roll/simulation website; it is not an authoritative reproduction of the Roblox fishing UI. The built-in harness therefore tests the pixel-engine contract directly instead of claiming website compatibility.