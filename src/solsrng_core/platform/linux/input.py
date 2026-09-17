from __future__ import annotations

from solsrng_core.antiafk.backends import (
    InputBackend,
    InputBackendError,
    XdotoolBackend,
    YdotoolBackend,
)
from solsrng_core.platform.linux.environment import (
    detect_environment,
)


def create_input_backend() -> InputBackend:
    environment = detect_environment()

    # ydotool is preferred everywhere because it works through Linux
    # input/uinput and does not depend on an X11 window.
    if environment.commands.get("ydotool", False):
        try:
            return YdotoolBackend()
        except InputBackendError:
            pass

    # xdotool is a fallback for X11/XWayland environments.
    if (
        environment.session.x11_available
        or environment.session.xwayland_available
    ):
        if environment.commands.get("xdotool", False):
            return XdotoolBackend()

    display = environment.session.display_server

    raise InputBackendError(
        "No supported Linux input backend is available. "
        f"Detected display server: {display}. "
        "Install ydotool for Wayland/native input, or "
        "xdotool for X11/XWayland fallback."
    )
