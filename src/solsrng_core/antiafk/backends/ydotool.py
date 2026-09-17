from __future__ import annotations

import os
import shutil
import subprocess
import time

from .base import InputBackend, InputBackendError


class YdotoolBackend(InputBackend):
    """Linux input backend using ydotool."""

    name = "ydotool"

    KEYCODES = {
        "tab": 15,
        "space": 57,
        "alt": 56,
    }

    def __init__(self) -> None:
        if shutil.which("ydotool") is None:
            raise InputBackendError(
                "ydotool is not installed or not available in PATH."
            )

        self.socket_path = os.environ.get(
            "YDOTOOL_SOCKET",
            f"/run/user/{os.getuid()}/ydotool_socket",
        )

        self._ensure_daemon()

    def _ensure_daemon(self) -> None:
        socket = self.socket_path

        if os.path.exists(socket):
            return

        daemon = shutil.which("ydotoold")

        if daemon is None:
            raise InputBackendError(
                "ydotool is installed, but ydotoold is not available."
            )

        try:
            subprocess.Popen(
                [
                    daemon,
                    "--socket-path",
                    socket,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise InputBackendError(
                f"Unable to start ydotoold: {exc}"
            ) from exc

        for _ in range(20):
            if os.path.exists(socket):
                return

            time.sleep(0.05)

        raise InputBackendError(
            f"ydotoold did not create its socket: {socket}"
        )

    def _code(self, key: str) -> int:
        normalized = key.strip().lower()

        try:
            return self.KEYCODES[normalized]
        except KeyError as exc:
            raise InputBackendError(
                f"Unsupported ydotool key: {key}"
            ) from exc

    def _run(self, events: list[str]) -> None:
        command = [
            "ydotool",
            "key",
            "--socket-path",
            self.socket_path,
            *events,
        ]

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
        except subprocess.TimeoutExpired as exc:
            raise InputBackendError(
                "ydotool timed out."
            ) from exc
        except OSError as exc:
            raise InputBackendError(
                f"Unable to execute ydotool: {exc}"
            ) from exc

        if result.returncode != 0:
            message = (
                result.stderr.strip()
                or result.stdout.strip()
                or f"exit code {result.returncode}"
            )

            raise InputBackendError(
                f"ydotool failed: {message}"
            )

    def press_key(self, key: str) -> None:
        code = self._code(key)

        self._run(
            [
                f"{code}:1",
                f"{code}:0",
            ]
        )

    def hotkey(self, *keys: str) -> None:
        if not keys:
            raise InputBackendError(
                "hotkey() requires at least one key."
            )

        codes = [self._code(key) for key in keys]

        events = [
            f"{code}:1"
            for code in codes
        ]

        events.extend(
            f"{code}:0"
            for code in reversed(codes)
        )

        self._run(events)
