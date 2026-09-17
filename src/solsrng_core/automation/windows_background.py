from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.EnumWindows.argtypes = [
    ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM),
    wintypes.LPARAM,
]
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
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ScreenToClient.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.ULONG_PTR]
user32.mouse_event.restype = None

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
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


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202

MK_LBUTTON = 0x0001

VK = {
    "tab": 0x09,
    "space": 0x20,
    "ctrl": 0x11,
    "a": 0x41,
}


@dataclass(frozen=True)
class WindowsTargetWindow:
    hwnd: int
    title: str
    process_id: int
    executable: str

    @property
    def display_name(self) -> str:
        return f"{self.title} ({self.executable}, PID {self.process_id})"


class WindowsBackgroundInput:
    """Window-aware Windows input that never has to steal foreground focus.

    When the target is foreground, SendInput is used for maximum compatibility.
    When the target is in the background, keyboard and mouse messages are posted
    directly to the target window so the desktop focus stays with the user.
    """

    DEFAULT_PROCESS_NAMES = (
        "RobloxPlayerBeta.exe",
        "RobloxPlayer.exe",
    )

    def __init__(
        self,
        window_pattern: str = "Roblox",
        process_names: tuple[str, ...] | None = None,
    ) -> None:
        self.window_pattern = (window_pattern or "Roblox").strip()
        self.process_names = tuple(
            name.lower()
            for name in (process_names or self.DEFAULT_PROCESS_NAMES)
        )

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

        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            process_id,
        )
        if not handle:
            return process_id, ""

        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            if not kernel32.QueryFullProcessImageNameW(
                handle,
                0,
                buffer,
                ctypes.byref(size),
            ):
                return process_id, ""
            full_path = buffer.value
            return process_id, full_path.rsplit("\\", 1)[-1]
        finally:
            kernel32.CloseHandle(handle)

    def list_windows(self) -> list[WindowsTargetWindow]:
        windows: list[WindowsTargetWindow] = []

        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            wintypes.HWND,
            wintypes.LPARAM,
        )

        def callback(hwnd, _lparam):
            hwnd_value = int(hwnd)
            if not user32.IsWindowVisible(hwnd_value):
                return True

            title = self._title(hwnd_value)
            if not title:
                return True

            process_id, executable = self._process_name(hwnd_value)
            windows.append(
                WindowsTargetWindow(
                    hwnd=hwnd_value,
                    title=title,
                    process_id=process_id,
                    executable=executable,
                )
            )
            return True

        callback_ref = callback_type(callback)
        if not user32.EnumWindows(callback_ref, 0):
            error = ctypes.get_last_error()
            raise RuntimeError(f"EnumWindows failed with Win32 error {error}.")

        return windows

    def find_window(self) -> WindowsTargetWindow:
        pattern = self.window_pattern.lower()
        candidates = self.list_windows()

        exact_process = []
        matching_process = []
        exact_title = []
        partial_title = []

        for window in candidates:
            executable = window.executable.lower()
            title = window.title.lower()
            process_match = executable in self.process_names

            if process_match and pattern in title:
                matching_process.append(window)
            if process_match:
                exact_process.append(window)
            if title == pattern:
                exact_title.append(window)
            elif pattern in title:
                partial_title.append(window)

        if matching_process:
            return matching_process[0]
        if exact_process:
            return exact_process[0]
        if exact_title:
            return exact_title[0]
        if partial_title:
            return partial_title[0]

        raise RuntimeError(
            f'Could not find a visible Windows window matching "{self.window_pattern}".'
        )

    @staticmethod
    def is_alive(window: WindowsTargetWindow) -> bool:
        return bool(
            user32.IsWindow(window.hwnd)
            and user32.IsWindowVisible(window.hwnd)
        )

    @staticmethod
    def _pack_client_point(hwnd: int, x: int, y: int) -> int:
        point = wintypes.POINT(int(x), int(y))
        if not user32.ScreenToClient(hwnd, ctypes.byref(point)):
            error = ctypes.get_last_error()
            raise RuntimeError(
                f"ScreenToClient failed with Win32 error {error}."
            )

        # Signed 16-bit x/y packed into LPARAM.
        return ((point.y & 0xFFFF) << 16) | (point.x & 0xFFFF)

    @staticmethod
    def _post(hwnd: int, message: int, wparam: int = 0, lparam: int = 0) -> None:
        if not user32.PostMessageW(hwnd, message, wparam, lparam):
            error = ctypes.get_last_error()
            raise RuntimeError(
                f"PostMessageW failed with Win32 error {error}."
            )

    @staticmethod
    def _send_input_key(vk: int, down: bool) -> None:
        # Import lazily so background operation does not depend on the old
        # Linux automation modules or on any optional package.
        from .antiafk.backends.windows import WindowsInputBackend

        backend = WindowsInputBackend()
        if down:
            backend._send_key(vk, True)
        else:
            backend._send_key(vk, False)

    def press_key(self, window: WindowsTargetWindow, key: str) -> None:
        normalized = str(key).strip().lower()
        try:
            vk = VK[normalized]
        except KeyError as exc:
            raise RuntimeError(f"Unsupported Windows key: {key}") from exc

        foreground = int(user32.GetForegroundWindow())
        if foreground == window.hwnd:
            self._send_input_key(vk, True)
            self._send_input_key(vk, False)
            return

        self._post(window.hwnd, WM_KEYDOWN, vk, 1)
        self._post(window.hwnd, WM_KEYUP, vk, 1 << 30 | 1)

    def hotkey(self, window: WindowsTargetWindow, *keys: str) -> None:
        if not keys:
            raise RuntimeError("hotkey() requires at least one key.")

        foreground = int(user32.GetForegroundWindow())
        if foreground == window.hwnd:
            from .antiafk.backends.windows import WindowsInputBackend

            backend = WindowsInputBackend()
            backend.hotkey(*keys)
            return

        vks = []
        for key in keys:
            normalized = str(key).strip().lower()
            if normalized not in VK:
                raise RuntimeError(f"Unsupported Windows key: {key}")
            vks.append(VK[normalized])

        for vk in vks:
            self._post(window.hwnd, WM_KEYDOWN, vk, 1)
        for vk in reversed(vks):
            self._post(window.hwnd, WM_KEYUP, vk, 1 << 30 | 1)

    def type_text(self, window: WindowsTargetWindow, text: str) -> None:
        foreground = int(user32.GetForegroundWindow())
        if foreground == window.hwnd:
            # Clipboard paste is more reliable for the focused case.
            import subprocess

            encoded = str(text).replace("'", "''")
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Set-Clipboard -Value '" + encoded + "'",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    result.stderr.strip() or "Unable to write clipboard."
                )
            self.hotkey(window, "ctrl", "v")
            return

        for character in str(text):
            self._post(window.hwnd, WM_CHAR, ord(character), 1)

    def click_screen(self, window: WindowsTargetWindow, x: int, y: int) -> None:
        foreground = int(user32.GetForegroundWindow())
        if foreground == window.hwnd:
            if not user32.SetCursorPos(int(x), int(y)):
                error = ctypes.get_last_error()
                raise RuntimeError(
                    f"SetCursorPos failed with Win32 error {error}."
                )
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            user32.mouse_event(0x0004, 0, 0, 0, 0)
            return

        lparam = self._pack_client_point(window.hwnd, int(x), int(y))
        self._post(window.hwnd, WM_MOUSEMOVE, 0, lparam)
        self._post(window.hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        self._post(window.hwnd, WM_LBUTTONUP, 0, lparam)

    def background_space(self, window: WindowsTargetWindow) -> None:
        # Always use window-directed messages for the background case; this
        # never changes the user's current foreground window.
        self._post(window.hwnd, WM_KEYDOWN, VK["space"], 1)
        self._post(window.hwnd, WM_KEYUP, VK["space"], 1 << 30 | 1)
