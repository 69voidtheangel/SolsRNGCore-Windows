from __future__ import annotations

import ctypes
from ctypes import wintypes
import threading
import time
from dataclasses import dataclass
from typing import Callable

from .models import AutomationCoordinates, AutomationItem
from solsrng_core.antiafk.backends.windows import WindowsInputBackend
from solsrng_core.antiafk.backends.base import InputBackendError

user32 = ctypes.WinDLL("user32", use_last_error=True)

class AutomationError(RuntimeError):
    pass

@dataclass
class WindowInfo:
    window_id: int
    title: str

@dataclass
class AutomationStatus:
    running: bool = False
    testing: bool = False
    message: str = "STOPPED"
    current_item: str = ""
    next_run_timestamp: float | None = None
    authenticated: bool = False
    authenticating: bool = False
    auth_error: str = ""
    game_window: str = ""
    previous_window: str = ""

class AutomationController:
    """Windows implementation of the existing SolsRNGCore automation interface."""

    RETRIES = 3
    FOCUS_DELAY = 0.35
    POST_FOCUS_DELAY = 0.50
    RESTORE_DELAY = 0.20
    CLICK_SETTLE = 0.15
    TYPE_SETTLE = 0.20

    def __init__(
        self,
        *,
        backend: str = "auto",
        game_window_pattern: str = "Roblox",
        on_status: Callable[[AutomationStatus], None] | None = None,
        priority_gate=None,
    ):
        self.backend = "windows"
        self.game_window_pattern = (game_window_pattern or "Roblox").strip()
        self.on_status = on_status
        self.priority_gate = priority_gate
        self.items: list[AutomationItem] = []
        self.coordinates = AutomationCoordinates()
        self.status = AutomationStatus()
        self._thread: threading.Thread | None = None
        self._auth_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._run_lock = threading.Lock()
        self._input = WindowsInputBackend()

    def _emit_status(self):
        if self.on_status:
            try:
                self.on_status(self.status)
            except Exception:
                pass

    def _set_message(self, message: str, *, current_item: str | None = None):
        self.status.message = message
        if current_item is not None:
            self.status.current_item = current_item
        self._emit_status()

    def authenticate_async(self):
        if self.status.authenticated or self.status.authenticating:
            return
        self.status.authenticating = True
        self._emit_status()
        self._auth_thread = threading.Thread(
            target=self.authenticate,
            name="solsrng-windows-auth",
            daemon=True,
        )
        self._auth_thread.start()

    def authenticate(self) -> bool:
        try:
            self._input.press_key("space")
            self.status.authenticated = True
            self.status.auth_error = ""
            return True
        except Exception as exc:
            self.status.authenticated = False
            self.status.auth_error = str(exc)
            return False
        finally:
            self.status.authenticating = False
            self._emit_status()

    def retry_authentication(self):
        self.status.authenticated = False
        self.status.auth_error = ""
        self.authenticate_async()

    @staticmethod
    def _window_title(hwnd: int) -> str:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value.strip()

    def _list_windows(self) -> list[WindowInfo]:
        windows: list[WindowInfo] = []
        enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)  # type: ignore[name-defined]

        def callback(hwnd, _lparam):
            if user32.IsWindowVisible(hwnd):
                title = self._window_title(int(hwnd))
                if title:
                    windows.append(WindowInfo(int(hwnd), title))
            return True

        callback_ref = enum_proc_type(callback)
        user32.EnumWindows(callback_ref, 0)
        return windows

    def find_game_window(self) -> WindowInfo:
        pattern = self.game_window_pattern.lower()
        exact = []
        partial = []
        for window in self._list_windows():
            title = window.title.lower()
            if title == pattern:
                exact.append(window)
            elif pattern in title:
                partial.append(window)
        if exact:
            return exact[0]
        if partial:
            return partial[0]
        raise AutomationError(
            f'Could not find a Windows window matching "{self.game_window_pattern}".'
        )

    @staticmethod
    def _activate_window(window: WindowInfo):
        if not user32.SetForegroundWindow(window.window_id):
            raise AutomationError(
                f'Could not focus "{window.title}" (Win32 error {ctypes.get_last_error()}).'
            )
        time.sleep(0.35)

    def _get_active_window(self) -> WindowInfo:
        hwnd = int(user32.GetForegroundWindow())
        if not hwnd:
            raise AutomationError("Could not determine the active window.")
        return WindowInfo(hwnd, self._window_title(hwnd))

    def _restore_window(self, window: WindowInfo):
        self._activate_window(window)

    def _validate_item(self, item: AutomationItem):
        if not item.search_text.strip():
            raise AutomationError(f"{item.name}: search text is empty.")
        missing = item.coordinates.missing()
        if missing:
            raise AutomationError(
                f"{item.name}: missing coordinates: {', '.join(missing)}"
            )
        if item.cooldown_seconds < 0:
            raise AutomationError(f"{item.name}: cooldown cannot be negative.")

    def _validate_items(self):
        enabled = [i for i in self.items if i.enabled]
        if not enabled:
            raise AutomationError("No enabled automation items.")
        for item in enabled:
            self._validate_item(item)

    def start(self):
        if self.status.running:
            return
        if not self.status.authenticated:
            raise AutomationError("Input Access is not authenticated.")
        self._validate_items()
        self._stop_event.clear()
        self.status.running = True
        self.status.testing = False
        self.status.message = "RUNNING"
        self.status.current_item = ""
        self.status.next_run_timestamp = None
        self._emit_status()
        self._thread = threading.Thread(
            target=self._worker,
            name="solsrng-windows-automation",
            daemon=True,
        )
        self._thread.start()

    def test_item(self, item: AutomationItem):
        if self.status.testing:
            return
        if self.status.running:
            raise AutomationError("Stop Automation before running a test.")
        if not self.status.authenticated:
            raise AutomationError("Input Access is not authenticated.")
        self._validate_item(item)
        if not self._run_lock.acquire(blocking=False):
            raise AutomationError("Automation is already busy.")
        self.status.testing = True
        self.status.message = f"TESTING • {item.name}"
        self.status.current_item = item.name
        self._emit_status()
        try:
            self._run_item(item)
            self.status.message = f"TEST COMPLETE • {item.name}"
        finally:
            self.status.testing = False
            self.status.current_item = ""
            self._emit_status()
            self._run_lock.release()

    def stop(self):
        self._stop_event.set()
        self.status.running = False
        self.status.testing = False
        self.status.message = "STOPPED"
        self.status.current_item = ""
        self.status.next_run_timestamp = None
        self._emit_status()

    def shutdown(self):
        self.stop()

    def _worker(self):
        while not self._stop_event.is_set():
            try:
                if self.priority_gate is not None:
                    self.priority_gate.enter_automation()
                try:
                    for item in [i for i in self.items if i.enabled]:
                        if self._stop_event.is_set():
                            break
                        self._run_item(item)
                        self.status.next_run_timestamp = (
                            time.time() + item.cooldown_seconds
                        )
                        self._emit_status()
                        if self._stop_event.wait(item.cooldown_seconds):
                            break
                finally:
                    if self.priority_gate is not None:
                        self.priority_gate.leave()
            except Exception as exc:
                self._set_message(f"ERROR • {exc}")
                if self._stop_event.wait(1.0):
                    break

        self.status.running = False
        self.status.next_run_timestamp = None
        self._emit_status()

    def _run_item(self, item: AutomationItem):
        previous = self._get_active_window()
        self.status.previous_window = previous.title
        self._emit_status()

        game = self.find_game_window()
        self.status.game_window = game.title
        self._emit_status()

        self._set_message(f"FOCUSING • {game.title}", current_item=item.name)
        coords = self.coordinates
        if coords.missing():
            raise AutomationError(
                "Shared automation coordinates are incomplete: "
                + ", ".join(coords.missing())
            )

        self._activate_window(game)
        time.sleep(self.POST_FOCUS_DELAY)

        try:
            sequence = [
                (coords.inventory, "Inventory"),
                (coords.items, "Items"),
                (coords.search_bar, "Search Bar"),
                (coords.first_slot, "First Slot"),
                (coords.quantity, "Quantity"),
                (coords.use_button, "Use Button"),
                (coords.close_inventory, "Close Inventory"),
            ]

            self._set_message(
                f"OPENING INVENTORY • {item.name}",
                current_item=item.name,
            )

            self._click(coords.inventory, "Inventory", item)
            time.sleep(item.click_delay_seconds)
            self._click(coords.items, "Items", item)
            time.sleep(item.click_delay_seconds)
            self._click(coords.search_bar, "Search Bar", item)
            time.sleep(item.click_delay_seconds)
            self._ctrl_a()
            time.sleep(0.05)
            self._type_text(item.search_text)
            time.sleep(max(item.click_delay_seconds, self.TYPE_SETTLE))
            self._click(coords.first_slot, "First Slot", item)
            time.sleep(item.click_delay_seconds)
            self._click(coords.quantity, "Quantity", item)
            time.sleep(0.10)
            self._ctrl_a()
            time.sleep(0.05)
            self._type_text("1")
            time.sleep(max(item.click_delay_seconds, self.TYPE_SETTLE))
            self._click(coords.use_button, "Use Button", item)
            time.sleep(item.post_use_delay_seconds)
            self._click(coords.close_inventory, "Close Inventory", item)

            self._set_message(f"COMPLETE • {item.name}", current_item=item.name)
        finally:
            self._set_message(
                f"RESTORING • {previous.title}",
                current_item=item.name,
            )
            time.sleep(self.RESTORE_DELAY)
            try:
                self._restore_window(previous)
            finally:
                self.status.game_window = ""
                self.status.previous_window = ""
                self._emit_status()

    def _click(self, coordinate, label: str, item: AutomationItem):
        if coordinate is None:
            raise AutomationError(
                f"{item.name}: {label} coordinate is missing."
            )
        x, y = int(coordinate[0]), int(coordinate[1])
        user32.SetCursorPos(x, y)
        time.sleep(self.CLICK_SETTLE)
        # mouse left button
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self._set_message(
            f"CLICK • {label} • {item.name}",
            current_item=item.name,
        )

    def _type_text(self, text: str):
        # Use clipboard paste for reliable Unicode on Windows.
        import subprocess
        encoded = str(text).replace("'", "''")
        ps = (
            "Set-Clipboard -Value "
            + "'" + encoded + "'"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise AutomationError(
                result.stderr.strip() or "Unable to write clipboard."
            )
        self._input.hotkey("ctrl", "v")

    def _ctrl_a(self):
        self._input.hotkey("ctrl", "a")
