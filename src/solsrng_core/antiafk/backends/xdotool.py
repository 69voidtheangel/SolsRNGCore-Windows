from __future__ import annotations

import shutil
import subprocess

from .base import InputBackend, InputBackendError


class XdotoolBackend(InputBackend):
    """Linux X11/XWayland input backend using xdotool."""

    name = "xdotool"

    SUPPORTED_KEYS = {
        "tab",
        "space",
        "alt",
    }

    def __init__(self) -> None:
        if shutil.which("xdotool") is None:
            raise InputBackendError(
                "xdotool is not installed or not available in PATH."
            )

    def _validate_key(self, key: str) -> str:
        normalized = key.strip().lower()

        if normalized not in self.SUPPORTED_KEYS:
            raise InputBackendError(
                f"Unsupported xdotool key: {key}"
            )

        return normalized

    def _run(self, *arguments: str) -> None:
        command = [
            "xdotool",
            *arguments,
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
                "xdotool timed out."
            ) from exc
        except OSError as exc:
            raise InputBackendError(
                f"Unable to execute xdotool: {exc}"
            ) from exc

        if result.returncode != 0:
            message = (
                result.stderr.strip()
                or result.stdout.strip()
                or f"exit code {result.returncode}"
            )

            raise InputBackendError(
                f"xdotool failed: {message}"
            )

    def press_key(self, key: str) -> None:
        key = self._validate_key(key)
        self._run("key", key)

    def hotkey(self, *keys: str) -> None:
        if not keys:
            raise InputBackendError(
                "hotkey() requires at least one key."
            )

        normalized = [
            self._validate_key(key)
            for key in keys
        ]

        self._run(
            "key",
            "+".join(normalized),
        )
