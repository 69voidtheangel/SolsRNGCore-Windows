from __future__ import annotations

import os
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class LinuxSession:
    display_server: str
    desktop: str
    session_type: str
    x11_available: bool
    wayland_available: bool
    xwayland_available: bool


def _desktop_name() -> str:
    return (
        os.environ.get(
            "XDG_CURRENT_DESKTOP",
            "",
        ).strip()
        or os.environ.get(
            "XDG_SESSION_DESKTOP",
            "",
        ).strip()
        or "unknown"
    )


def detect_session() -> LinuxSession:
    session_type = (
        os.environ.get(
            "XDG_SESSION_TYPE",
            "",
        )
        .strip()
        .lower()
    )

    wayland_available = bool(
        os.environ.get("WAYLAND_DISPLAY")
    )

    x11_available = bool(
        os.environ.get("DISPLAY")
    )

    xwayland_available = (
        wayland_available
        and x11_available
    )

    if xwayland_available:
        display_server = "xwayland"

    elif wayland_available:
        display_server = "wayland"

    elif x11_available:
        display_server = "x11"

    elif session_type:
        display_server = session_type

    else:
        display_server = "unknown"

    return LinuxSession(
        display_server=display_server,
        desktop=_desktop_name(),
        session_type=session_type or "unknown",
        x11_available=x11_available,
        wayland_available=wayland_available,
        xwayland_available=xwayland_available,
    )


def available_commands() -> dict[str, bool]:
    commands = {
        "ydotool": shutil.which("ydotool"),
        "ydotoold": shutil.which("ydotoold"),
        "xdotool": shutil.which("xdotool"),
        "wmctrl": shutil.which("wmctrl"),
        "swaymsg": shutil.which("swaymsg"),
        "hyprctl": shutil.which("hyprctl"),
        "qdbus": shutil.which("qdbus"),
        "gdbus": shutil.which("gdbus"),
    }

    return {
        name: value is not None
        for name, value in commands.items()
    }
