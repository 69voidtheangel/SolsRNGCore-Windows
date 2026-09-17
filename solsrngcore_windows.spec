from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
ASSETS = ROOT / "assets"
LIBRARY = ROOT / "library"

hiddenimports = collect_submodules("solsrng_core")

# Keep this a real Windows build: Linux-only automation/session modules are excluded.
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
