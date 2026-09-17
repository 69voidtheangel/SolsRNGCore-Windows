from __future__ import annotations

import sys
from pathlib import Path

def main() -> int:
    if sys.platform != "win32":
        print("SolsRNGCore-Windows must be run on Windows.", file=sys.stderr)
        return 2

    from solsrng_core.gui.app import run
    return int(run())

if __name__ == "__main__":
    raise SystemExit(main())
