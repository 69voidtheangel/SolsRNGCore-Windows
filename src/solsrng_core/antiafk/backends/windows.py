from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from .base import InputBackend, InputBackendError

user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001

ULONG_PTR = wintypes.WPARAM

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    ]

VK = {
    "tab": 0x09,
    "space": 0x20,
    "alt": 0x12,
    "ctrl": 0x11,
    "a": 0x41,
}

class WindowsInputBackend(InputBackend):
    """Native Windows keyboard injection through user32.SendInput."""

    name = "windows"

    def __init__(self) -> None:
        if not hasattr(user32, "SendInput"):
            raise InputBackendError("Windows SendInput is unavailable.")

    @classmethod
    def _vk(cls, key: str) -> int:
        normalized = str(key).strip().lower()
        try:
            return VK[normalized]
        except KeyError as exc:
            raise InputBackendError(
                f"Unsupported Windows key: {key}"
            ) from exc

    @classmethod
    def _send_key(cls, vk: int, down: bool) -> None:
        flags = 0 if down else KEYEVENTF_KEYUP
        event = INPUT(
            type=INPUT_KEYBOARD,
            ki=KEYBDINPUT(
                wVk=vk,
                wScan=0,
                dwFlags=flags,
                time=0,
                dwExtraInfo=0,
            ),
        )

        sent = user32.SendInput(
            1,
            ctypes.byref(event),
            ctypes.sizeof(INPUT),
        )

        if sent != 1:
            error = ctypes.get_last_error()
            raise InputBackendError(
                f"SendInput failed with Win32 error {error}."
            )

    def press_key(self, key: str) -> None:
        vk = self._vk(key)
        self._send_key(vk, True)
        time.sleep(0.01)
        self._send_key(vk, False)

    def hotkey(self, *keys: str) -> None:
        if not keys:
            raise InputBackendError("hotkey() requires at least one key.")

        vks = [self._vk(key) for key in keys]
        for vk in vks:
            self._send_key(vk, True)
        for vk in reversed(vks):
            self._send_key(vk, False)
