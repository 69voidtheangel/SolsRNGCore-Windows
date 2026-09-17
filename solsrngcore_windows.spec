from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
ASSETS = ROOT / "assets"
LIBRARY = ROOT / "library"

hiddenimports = collect_submodules("solsrng_core")

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
    excludes=[
        "solsrng_core.platform.linux",
        "solsrng_core.antiafk.backends.xdotool",
        "solsrng_core.antiafk.backends.ydotool",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SolsRNGCore-Windows",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
