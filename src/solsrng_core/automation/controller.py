from __future__ import annotations

import ctypes
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable

from .models import AutomationCoordinates, AutomationItem
from solsrng_core.antiafk.backends.windows import (
    WindowsInputBackend,
    WindowsWindowBackend,
    WindowInfo,
)
from solsrng_core.antiafk.backends.base import InputBackendError

user32 = ctypes.WinDLL("user32", use_last_error=True)


class AutomationError(RuntimeError):
    pass


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
    background_mode: bool = True
    input_path: str = "background"


class AutomationController:
    """Windows-native automation controller.

    The worker is always a daemon thread. Input is attempted against the Roblox
    window without foregrounding it first. Some games (including certain Roblox
    input paths) do not consume background Win32 messages, so the controller
    transparently falls back to a brief foreground SendInput pass and restores
    the previous window immediately.
    """

    RETRIES = 3
    CLICK_SETTLE = 0.12
    TYPE_SETTLE = 0.18
    RESTORE_DELAY = 0.15

    def __init__(
        self,
        *,
        backend: str = "auto",
        game_window_pattern: str = "Roblox",
        on_status: Callable[[AutomationStatus], None] | None = None,
        priority_gate=None,
    ):
        del backend
        self.backend = "windows-native"
        self.game_window_pattern = (
            game_window_pattern or "Roblox"
        ).strip()
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
        self._windows = WindowsWindowBackend()
        self._active_game: WindowInfo | None = None
        self._foreground_fallback = False

    def _emit_status(self):
        if self.on_status:
            try:
                self.on_status(self.status)
            except Exception:
                pass

    def _set_message(
        self,
        message: str,
        *,
        current_item: str | None = None,
    ):
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
            # SendInput is used only for the one-time user authentication
            # handshake. Runtime automation uses the window-aware backend.
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

    def _list_windows(self) -> list[WindowInfo]:
        return self._windows.enumerate_windows()

    def find_game_window(self) -> WindowInfo:
        pattern = self.game_window_pattern.strip()
        process_candidates = [
            "RobloxPlayerBeta.exe",
            "Sober.exe",
        ]

        last_error: Exception | None = None
        for process_name in process_candidates:
            try:
                return self._windows.find_window(
                    pattern,
                    process_name=process_name,
                )
            except Exception as exc:
                last_error = exc

        try:
            return self._windows.find_window(pattern)
        except Exception as exc:
            if last_error is not None:
                raise AutomationError(str(exc)) from last_error
            raise AutomationError(str(exc)) from exc

    @staticmethod
    def _foreground_window() -> WindowInfo:
        hwnd = int(user32.GetForegroundWindow())
        if not hwnd:
            raise AutomationError("Could not determine the active window.")
        title_length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if title_length > 0:
            buffer = ctypes.create_unicode_buffer(title_length + 1)
            user32.GetWindowTextW(hwnd, buffer, title_length + 1)
            title = buffer.value.strip()
        return WindowInfo(hwnd, title)

    @staticmethod
    def _activate_window(window: WindowInfo):
        if not window.window_id or not user32.IsWindow(window.window_id):
            raise AutomationError("Target window is no longer available.")
        if user32.IsIconic(window.window_id):
            SW_RESTORE = 9
            user32.ShowWindow(window.window_id, SW_RESTORE)
        if not user32.SetForegroundWindow(window.window_id):
            raise AutomationError(
                f'Could not focus "{window.title}" '
                f"(Win32 error {ctypes.get_last_error()})."
            )
        time.sleep(0.30)

    def _restore_window(self, window: WindowInfo):
        if window.window_id and user32.IsWindow(window.window_id):
            try:
                self._activate_window(window)
            except AutomationError as exc:
                self._set_message(
                    f"RESTORE WARNING • {exc}",
                    current_item=self.status.current_item,
                )

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
        enabled = [item for item in self.items if item.enabled]
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
        self.status.message = "RUNNING • BACKGROUND-FIRST"
        self.status.input_path = "background"
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
                    for item in [item for item in self.items if item.enabled]:
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

    def _enable_foreground_fallback(self, game: WindowInfo):
        if self._foreground_fallback:
            return
        self._set_message(
            "BACKGROUND INPUT NOT ACCEPTED • USING NATIVE FOCUS FALLBACK",
            current_item=self.status.current_item,
        )
        self._activate_window(game)
        self._foreground_fallback = True
        self.status.input_path = "focus-fallback"
        self._emit_status()

    def _background_or_fallback(self, operation, game: WindowInfo):
        if self._foreground_fallback:
            return False
        try:
            if operation():
                return True
        except (InputBackendError, OSError):
            pass
        self._enable_foreground_fallback(game)
        return False

    def _click(
        self,
        coordinate: tuple[int, int] | None,
        label: str,
        item: AutomationItem,
        game: WindowInfo,
    ):
        if coordinate is None:
            raise AutomationError(
                f"{item.name}: {label} coordinate is missing."
            )

        x, y = int(coordinate[0]), int(coordinate[1])
        if not self._foreground_fallback:
            if self._background_or_fallback(
                lambda: self._input.background_click(
                    game.window_id,
                    x,
                    y,
                ),
                game,
            ):
                self._set_message(
                    f"BACKGROUND CLICK • {label} • {item.name}",
                    current_item=item.name,
                )
                time.sleep(self.CLICK_SETTLE)
                return

        user32.SetCursorPos(x, y)
        time.sleep(self.CLICK_SETTLE)
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self._set_message(
            f"FOCUS CLICK • {label} • {item.name}",
            current_item=item.name,
        )

    def _ctrl_a(self, game: WindowInfo):
        if not self._foreground_fallback:
            if self._background_or_fallback(
                lambda: self._input.background_hotkey(
                    game.window_id,
                    "ctrl",
                    "a",
                ),
                game,
            ):
                return
        self._input.hotkey("ctrl", "a")

    def _type_text(self, text: str, game: WindowInfo):
        if not self._foreground_fallback:
            if self._background_or_fallback(
                lambda: self._input.background_text(
                    game.window_id,
                    text,
                ),
                game,
            ):
                return

        encoded = str(text).replace("'", "''")
        ps = "Set-Clipboard -Value '" + encoded + "'"
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

    def _run_item(self, item: AutomationItem):
        previous = self._foreground_window()
        self.status.previous_window = previous.title
        self._foreground_fallback = False
        self.status.input_path = "background"
        self._emit_status()

        game = self.find_game_window()
        self._active_game = game
        self.status.game_window = game.title
        self._emit_status()

        self._set_message(
            f"FOUND • {game.title} • {game.process_name or 'unknown process'}",
            current_item=item.name,
        )

        coords = self.coordinates
        if not coords.complete():
            raise AutomationError(
                "Shared automation coordinates are incomplete: "
                + ", ".join(coords.missing())
            )

        try:
            self._set_message(
                f"BACKGROUND INPUT • {item.name}",
                current_item=item.name,
            )
            self._click(coords.inventory, "Inventory", item, game)
            time.sleep(item.click_delay_seconds)
            self._click(coords.items, "Items", item, game)
            time.sleep(item.click_delay_seconds)
            self._click(coords.search_bar, "Search Bar", item, game)
            time.sleep(item.click_delay_seconds)
            self._ctrl_a(game)
            time.sleep(0.05)
            self._type_text(item.search_text, game)
            time.sleep(max(item.click_delay_seconds, self.TYPE_SETTLE))
            self._click(coords.first_slot, "First Slot", item, game)
            time.sleep(item.click_delay_seconds)
            self._click(coords.quantity, "Quantity", item, game)
            time.sleep(0.10)
            self._ctrl_a(game)
            time.sleep(0.05)
            self._type_text("1", game)
            time.sleep(max(item.click_delay_seconds, self.TYPE_SETTLE))
            self._click(coords.use_button, "Use Button", item, game)
            time.sleep(item.post_use_delay_seconds)
            self._click(coords.close_inventory, "Close Inventory", item, game)

            self._set_message(
                f"COMPLETE • {item.name}",
                current_item=item.name,
            )
        finally:
            if self._foreground_fallback:
                self._set_message(
                    f"RESTORING • {previous.title}",
                    current_item=item.name,
                )
                time.sleep(self.RESTORE_DELAY)
                self._restore_window(previous)
            else:
                self.status.input_path = "background"
            self.status.game_window = ""
            self.status.previous_window = ""
            self._active_game = None
            self._emit_status()
