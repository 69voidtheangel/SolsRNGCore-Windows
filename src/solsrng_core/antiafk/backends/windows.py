from __future__ import annotations

import ctypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from ctypes import wintypes

from .base import InputBackend, InputBackendError

user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_PATH = 260

ULONG_PTR = wintypes.WPARAM


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


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


@dataclass(frozen=True)
class WindowInfo:
    window_id: int
    title: str
    process_id: int = 0
    process_name: str = ""


VK = {
    "tab": 0x09,
    "space": 0x20,
    "alt": 0x12,
    "ctrl": 0x11,
    "a": 0x41,
}


class WindowsWindowBackend:
    """Native Win32 window discovery plus background message injection.

    Background input uses PostMessage/WindowFromPoint first, so the caller does
    not need to foreground the game window for ordinary Win32 message targets.
    Game engines may ignore those messages; callers should use a controlled
    SendInput fallback when the target does not accept background messages.
    """

    @staticmethod
    def _window_title(hwnd: int) -> str:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()

    @staticmethod
    def _process_info(hwnd: int) -> tuple[int, str]:
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        pid = int(process_id.value)
        if not pid:
            return 0, ""

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            pid,
        )
        if not handle:
            return pid, ""

        try:
            size = wintypes.DWORD(MAX_PATH)
            buffer = ctypes.create_unicode_buffer(MAX_PATH)
            if kernel32.QueryFullProcessImageNameW(
                handle,
                0,
                buffer,
                ctypes.byref(size),
            ):
                return pid, Path(buffer.value).name
        finally:
            kernel32.CloseHandle(handle)

        return pid, ""

    @classmethod
    def enumerate_windows(cls) -> list[WindowInfo]:
        windows: list[WindowInfo] = []
        enum_proc_type = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            wintypes.HWND,
            wintypes.LPARAM,
        )

        def callback(hwnd, _lparam):
            hwnd_int = int(hwnd)
            if not user32.IsWindowVisible(hwnd_int):
                return True
            title = cls._window_title(hwnd_int)
            if not title:
                return True
            pid, process_name = cls._process_info(hwnd_int)
            windows.append(
                WindowInfo(
                    window_id=hwnd_int,
                    title=title,
                    process_id=pid,
                    process_name=process_name,
                )
            )
            return True

        callback_ref = enum_proc_type(callback)
        if not user32.EnumWindows(callback_ref, 0):
            raise InputBackendError(
                f"EnumWindows failed with Win32 error {ctypes.get_last_error()}."
            )
        return windows

    @classmethod
    def find_window(
        cls,
        pattern: str,
        *,
        process_name: str | None = None,
    ) -> WindowInfo:
        wanted = str(pattern).strip().lower()
        if not wanted:
            raise InputBackendError("Window search text cannot be empty.")

        process_wanted = (
            str(process_name).strip().lower()
            if process_name
            else ""
        )

        exact: list[WindowInfo] = []
        partial: list[WindowInfo] = []

        for window in cls.enumerate_windows():
            title = window.title.lower()
            process = window.process_name.lower()
            if process_wanted and process != process_wanted:
                continue
            if title == wanted:
                exact.append(window)
            elif wanted in title:
                partial.append(window)
            elif process_wanted and process_wanted in process:
                partial.append(window)

        if exact:
            return exact[0]
        if partial:
            return partial[0]

        extra = (
            f" (process={process_name})"
            if process_name
            else ""
        )
        raise InputBackendError(
            f'Could not find a visible Windows window matching "{pattern}"{extra}.'
        )

    @staticmethod
    def _client_point(hwnd: int, screen_x: int, screen_y: int) -> POINT:
        point = POINT(int(screen_x), int(screen_y))
        if not user32.ScreenToClient(hwnd, ctypes.byref(point)):
            raise InputBackendError(
                f"ScreenToClient failed with Win32 error {ctypes.get_last_error()}."
            )
        return point

    @staticmethod
    def _mouse_lparam(point: POINT) -> int:
        x = int(point.x) & 0xFFFF
        y = int(point.y) & 0xFFFF
        return x | (y << 16)

    @classmethod
    def _best_mouse_target(cls, hwnd: int, screen_x: int, screen_y: int) -> int:
        cursor = POINT(int(screen_x), int(screen_y))
        child = int(user32.WindowFromPoint(cursor))
        if child:
            pid, _ = cls._process_info(child)
            target_pid, _ = cls._process_info(hwnd)
            if pid and target_pid and pid == target_pid:
                return child
        return int(hwnd)

    @classmethod
    def click_background(
        cls,
        hwnd: int,
        screen_x: int,
        screen_y: int,
    ) -> bool:
        target = cls._best_mouse_target(hwnd, screen_x, screen_y)
        point = cls._client_point(target, screen_x, screen_y)
        lparam = cls._mouse_lparam(point)

        posted = bool(
            user32.PostMessageW(
                target,
                WM_MOUSEMOVE,
                0,
                lparam,
            )
        )
        posted = bool(
            user32.PostMessageW(
                target,
                WM_LBUTTONDOWN,
                MK_LBUTTON,
                lparam,
            )
        ) and posted
        posted = bool(
            user32.PostMessageW(
                target,
                WM_LBUTTONUP,
                0,
                lparam,
            )
        ) and posted
        return posted

    @classmethod
    def _keyboard_target(cls, hwnd: int) -> int:
        thread_id = int(user32.GetWindowThreadProcessId(hwnd, None))
        if not thread_id:
            return int(hwnd)

        # Prefer the thread's current focus window when available.
        try:
            class GUITHREADINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("flags", wintypes.DWORD),
                    ("hwndActive", wintypes.HWND),
                    ("hwndFocus", wintypes.HWND),
                    ("hwndCapture", wintypes.HWND),
                    ("hwndMenuOwner", wintypes.HWND),
                    ("hwndMoveSize", wintypes.HWND),
                    ("hwndCaret", wintypes.HWND),
                    ("rcCaret", wintypes.RECT),
                ]

            info = GUITHREADINFO()
            info.cbSize = ctypes.sizeof(GUITHREADINFO)
            if user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
                if info.hwndFocus:
                    return int(info.hwndFocus)
                if info.hwndActive:
                    return int(info.hwndActive)
        except Exception:
            pass

        return int(hwnd)

    @classmethod
    def post_key(
        cls,
        hwnd: int,
        key: str,
    ) -> bool:
        normalized = str(key).strip().lower()
        if normalized not in VK:
            raise InputBackendError(
                f"Unsupported background Windows key: {key}"
            )
        target = cls._keyboard_target(hwnd)
        vk = VK[normalized]
        down = bool(
            user32.PostMessageW(
                target,
                WM_KEYDOWN,
                vk,
                0x00000001,
            )
        )
        time.sleep(0.015)
        up = bool(
            user32.PostMessageW(
                target,
                WM_KEYUP,
                vk,
                0xC0000001,
            )
        )
        return down and up

    @classmethod
    def post_hotkey(
        cls,
        hwnd: int,
        *keys: str,
    ) -> bool:
        if not keys:
            raise InputBackendError("Background hotkey requires at least one key.")

        target = cls._keyboard_target(hwnd)
        vks = []
        for key in keys:
            normalized = str(key).strip().lower()
            if normalized not in VK:
                raise InputBackendError(
                    f"Unsupported background Windows key: {key}"
                )
            vks.append(VK[normalized])

        ok = True
        for vk in vks:
            ok = bool(
                user32.PostMessageW(
                    target,
                    WM_KEYDOWN,
                    vk,
                    0x00000001,
                )
            ) and ok
        for vk in reversed(vks):
            ok = bool(
                user32.PostMessageW(
                    target,
                    WM_KEYUP,
                    vk,
                    0xC0000001,
                )
            ) and ok
        return ok

    @classmethod
    def post_text(
        cls,
        hwnd: int,
        text: str,
    ) -> bool:
        target = cls._keyboard_target(hwnd)
        ok = True
        for character in str(text):
            if ord(character) > 0xFFFF:
                return False
            ok = bool(
                user32.PostMessageW(
                    target,
                    WM_CHAR,
                    ord(character),
                    0x00000001,
                )
            ) and ok
        return ok


class WindowsInputBackend(InputBackend):
    """Native Windows keyboard injection through user32.SendInput."""

    name = "windows"

    def __init__(self) -> None:
        if not hasattr(user32, "SendInput"):
            raise InputBackendError("Windows SendInput is unavailable.")
        self.window = WindowsWindowBackend()

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

    def background_key(self, hwnd: int, key: str) -> bool:
        return self.window.post_key(hwnd, key)

    def background_hotkey(self, hwnd: int, *keys: str) -> bool:
        return self.window.post_hotkey(hwnd, *keys)

    def background_click(
        self,
        hwnd: int,
        screen_x: int,
        screen_y: int,
    ) -> bool:
        return self.window.click_background(
            hwnd,
            screen_x,
            screen_y,
        )

    def background_text(self, hwnd: int, text: str) -> bool:
        return self.window.post_text(hwnd, text)
