from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

# PyInstaller executes spec files without a normal __file__ global on the
# Windows runner. The workflow invokes PyInstaller from the project root.
ROOT = Path.cwd().resolve()
SRC = ROOT / "src"
ASSETS = ROOT / "assets"
LIBRARY = ROOT / "library"

hiddenimports = collect_submodules("solsrng_core")

# Windows build only: do not package Linux automation/session modules.
excludes = [
    "solsrng_core.platform.linux",
    "solsrng_core.antiafk.backends.xdotool",
    "solsrng_core.antiafk.backends.ydotool",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[
        (str(ASSETS / "solsrng_core_logo.svg"), "assets"),
        (str(LIBRARY), "library"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SolsRNGCore",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
