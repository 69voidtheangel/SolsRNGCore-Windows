from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class WindowsInfo:
    name: str = "Windows"
    version: str = ""
    build: str = ""
    architecture: str = ""

@dataclass(frozen=True)
class WindowsSession:
    desktop: str
    display_server: str
    session_type: str
    wayland_available: bool = False
    x11_available: bool = False
    xwayland_available: bool = False

@dataclass(frozen=True)
class WindowsEnvironment:
    distribution: WindowsInfo
    session: WindowsSession
    commands: dict[str, str | None]

def detect_environment() -> WindowsEnvironment:
    version = platform.version()
    release = platform.release()
    build = platform.win32_ver()[1] or ""
    architecture = platform.machine()

    return WindowsEnvironment(
        distribution=WindowsInfo(
            version=version,
            build=build,
            architecture=architecture,
        ),
        session=WindowsSession(
            desktop="Windows",
            display_server="Desktop Window Manager (DWM)",
            session_type="Windows",
        ),
        commands={
            "python": shutil.which("python"),
            "powershell": shutil.which("powershell"),
            "pwsh": shutil.which("pwsh"),
        },
    )

def default_log_directories() -> list[Path]:
    candidates: list[Path] = []

    local = os.environ.get("LOCALAPPDATA")
    appdata = os.environ.get("APPDATA")

    if local:
        candidates.append(Path(local) / "Roblox" / "logs")

    if appdata:
        candidates.append(Path(appdata) / "Roblox" / "logs")

    # User can always override discovery with SOLSRNG_ROBLOX_LOG_DIR.
    override = os.environ.get("SOLSRNG_ROBLOX_LOG_DIR", "").strip()
    if override:
        candidates.insert(0, Path(override).expanduser())

    result: list[Path] = []
    seen: set[str] = set()

    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            resolved = candidate.expanduser()

        key = str(resolved).lower()
        if key not in seen:
            seen.add(key)
            result.append(resolved)

    return result
