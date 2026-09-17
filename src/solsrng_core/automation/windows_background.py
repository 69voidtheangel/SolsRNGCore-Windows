from __future__ import annotations

import ctypes
import time
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from typing import Iterator

from solsrng_core.antiafk.backends.windows import WindowsInputBackend

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetFocus.argtypes = [wintypes.HWND]
user32.SetFocus.restype = wintypes.HWND
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL

kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_RESTORE = 9
VK = {"tab": 0x09, "space": 0x20, "alt": 0x12, "ctrl": 0x11, "a": 0x41, "v": 0x56}

@dataclass(frozen=True)
class WindowsTargetWindow:
    hwnd: int
    title: str
    process_id: int
    executable: str

    @property
    def display_name(self) -> str:
        return f"{self.title} ({self.executable or 'unknown process'}, PID {self.process_id})"

class WindowsBackgroundInput:
    """Reliable Windows input for Roblox/game windows.

    Roblox does not reliably consume queued WM_KEYDOWN/WM_LBUTTON messages.
    We therefore use a short foreground transaction for native SendInput, then
    immediately restore the user's previous foreground window and mouse cursor.
    The automation remains fully asynchronous and never leaves Roblox focused.
    """

    DEFAULT_PROCESS_NAMES = ("RobloxPlayerBeta.exe", "RobloxPlayer.exe")

    def __init__(self, window_pattern: str = "Roblox", process_names: tuple[str, ...] | None = None) -> None:
        self.window_pattern = (window_pattern or "Roblox").strip()
        self.process_names = tuple(name.lower() for name in (process_names or self.DEFAULT_PROCESS_NAMES))
        self._native = WindowsInputBackend()
        import threading
        self._transaction_lock = threading.RLock()

    @staticmethod
    def _title(hwnd: int) -> str:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()

    @staticmethod
    def _process_name(hwnd: int) -> tuple[int, str]:
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_id = int(pid.value)
        if not process_id:
            return 0, ""
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
        if not handle:
            return process_id, ""
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return process_id, ""
            return process_id, buffer.value.rsplit("\\", 1)[-1]
        finally:
            kernel32.CloseHandle(handle)

    def _candidate(self, hwnd: int) -> WindowsTargetWindow:
        pid, executable = self._process_name(hwnd)
        return WindowsTargetWindow(hwnd, self._title(hwnd), pid, executable)

    def list_windows(self) -> list[WindowsTargetWindow]:
        windows: list[WindowsTargetWindow] = []
        def callback(hwnd, _lparam):
            hwnd_value = int(hwnd)
            if not user32.IsWindowVisible(hwnd_value):
                return True
            title = self._title(hwnd_value)
            if title:
                windows.append(self._candidate(hwnd_value))
            return True
        callback_ref = EnumWindowsProc(callback)
        if not user32.EnumWindows(callback_ref, 0):
            raise RuntimeError(f"EnumWindows failed with Win32 error {ctypes.get_last_error()}.")
        return windows

    def find_window(self) -> WindowsTargetWindow:
        pattern = (self.window_pattern or "Roblox").strip().lower()
        candidates = self.list_windows()
        process = [w for w in candidates if w.executable.lower() in self.process_names]
        process_exact = [w for w in process if w.title.lower() == pattern]
        process_partial = [w for w in process if pattern in w.title.lower()]
        exact = [w for w in candidates if w.title.lower() == pattern]
        partial = [w for w in candidates if pattern in w.title.lower()]
        if process_exact:
            return process_exact[0]
        if process_partial:
            return process_partial[0]
        if process:
            return process[0]
        if exact:
            return exact[0]
        if partial:
            return partial[0]
        raise RuntimeError(f'Could not find a visible Windows window matching "{self.window_pattern}".')

    @staticmethod
    def is_alive(window: WindowsTargetWindow) -> bool:
        return bool(user32.IsWindow(window.hwnd) and user32.IsWindowVisible(window.hwnd))

    @staticmethod
    def _attach_for_activation(target: int) -> tuple[int, int] | None:
        current = int(user32.GetForegroundWindow() or 0)
        current_thread = int(user32.GetWindowThreadProcessId(current, None)) if current else 0
        target_thread = int(user32.GetWindowThreadProcessId(target, None))
        own_thread = int(kernel32.GetCurrentThreadId())
        attached_target = False
        if target_thread and target_thread != own_thread:
            if not user32.AttachThreadInput(own_thread, target_thread, True):
                raise RuntimeError(f"AttachThreadInput failed with Win32 error {ctypes.get_last_error()}.")
            attached_target = True
        return (own_thread, target_thread) if attached_target else None

    @staticmethod
    def _detach_after_activation(state: tuple[int, int] | None) -> None:
        if state is None:
            return
        own_thread, target_thread = state
        if target_thread and target_thread != own_thread:
            user32.AttachThreadInput(own_thread, target_thread, False)

    @contextmanager
    def _focused_transaction(self, window: WindowsTargetWindow) -> Iterator[None]:
        with self._transaction_lock:
            if not self.is_alive(window):
                raise RuntimeError("Target window is no longer available.")
            previous = int(user32.GetForegroundWindow() or 0)
            state = None
            try:
                state = self._attach_for_activation(window.hwnd)
                user32.ShowWindow(window.hwnd, SW_RESTORE)
                user32.BringWindowToTop(window.hwnd)
                if not user32.SetForegroundWindow(window.hwnd):
                    raise RuntimeError(f"SetForegroundWindow failed with Win32 error {ctypes.get_last_error()}.")
                user32.SetFocus(window.hwnd)
                time.sleep(0.08)
                if int(user32.GetForegroundWindow() or 0) != window.hwnd:
                    raise RuntimeError("Windows did not activate the Roblox target window.")
                yield
            finally:
                self._detach_after_activation(state)
                if previous and user32.IsWindow(previous):
                    restore_state = None
                    try:
                        restore_state = self._attach_for_activation(previous)
                        user32.ShowWindow(previous, SW_RESTORE)
                        user32.BringWindowToTop(previous)
                        user32.SetForegroundWindow(previous)
                    finally:
                        self._detach_after_activation(restore_state)

    def press_key(self, window: WindowsTargetWindow, key: str) -> None:
        normalized = str(key).strip().lower()
        if normalized not in VK:
            raise RuntimeError(f"Unsupported Windows key: {key}")
        with self._focused_transaction(window):
            self._native.press_key(normalized)

    def hotkey(self, window: WindowsTargetWindow, *keys: str) -> None:
        with self._focused_transaction(window):
            self._native.hotkey(*keys)

    def type_text(self, window: WindowsTargetWindow, text: str) -> None:
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", wintypes.WPARAM)]
        class INPUT_UNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]
        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]
        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002
        user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        user32.SendInput.restype = wintypes.UINT
        with self._focused_transaction(window):
            for char in str(text):
                code = ord(char)
                down = INPUT(type=1, ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, 0))
                up = INPUT(type=1, ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0))
                if user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT)) != 1:
                    raise RuntimeError(f"Unicode key injection failed with Win32 error {ctypes.get_last_error()}.")
                if user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT)) != 1:
                    raise RuntimeError(f"Unicode key release failed with Win32 error {ctypes.get_last_error()}.")
                time.sleep(0.008)

    def click_screen(self, window: WindowsTargetWindow, x: int, y: int) -> None:
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", wintypes.WPARAM)]
        class INPUT_UNION(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]
        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]
        MOUSEEVENTF_MOVE = 0x0001
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004
        user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        user32.SendInput.restype = wintypes.UINT
        with self._focused_transaction(window):
            old = wintypes.POINT()
            if not user32.GetCursorPos(ctypes.byref(old)):
                raise RuntimeError(f"GetCursorPos failed with Win32 error {ctypes.get_last_error()}.")
            try:
                if not user32.SetCursorPos(int(x), int(y)):
                    raise RuntimeError(f"SetCursorPos failed with Win32 error {ctypes.get_last_error()}.")
                move = INPUT(type=0, mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_MOVE, 0, 0))
                down = INPUT(type=0, mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, 0))
                up = INPUT(type=0, mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, 0))
                for event, label in ((move, "move"), (down, "click-down"), (up, "click-up")):
                    if user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
                        raise RuntimeError(f"Mouse {label} injection failed with Win32 error {ctypes.get_last_error()}.")
                time.sleep(0.03)
            finally:
                user32.SetCursorPos(int(old.x), int(old.y))

    def background_space(self, window: WindowsTargetWindow) -> None:
        self.press_key(window, "space")
