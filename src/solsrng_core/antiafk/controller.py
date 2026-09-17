from __future__ import annotations

import ctypes
import threading
import time
from typing import Callable

from .backends.windows import (
    WindowsInputBackend,
    WindowsWindowBackend,
    WindowInfo,
)
from .backends.base import InputBackendError

user32 = ctypes.WinDLL("user32", use_last_error=True)


class WindowError(RuntimeError):
    """Raised when Windows Anti-AFK cannot perform an input action."""


class AntiAFKController:
    """Native Windows Anti-AFK controller.

    The worker runs in a daemon thread. Space mode targets the detected Roblox
    window with background Win32 messages first. If the game rejects those
    messages, the controller briefly uses native SendInput and restores the
    previous window immediately.
    """

    SPACE_MODE = "space"
    ALT_TAB_MODE = "alt_tab"

    def __init__(
        self,
        interval_seconds: float = 120.0,
        method: str = SPACE_MODE,
        backend_preference: str = "auto",
        log: Callable[[str], None] | None = None,
        priority_gate=None,
        game_window_pattern: str = "Roblox",
    ):
        del backend_preference
        self.interval_seconds = max(1.0, float(interval_seconds))
        self.method = self._normalize_method(method)
        self.log = log or (lambda _: None)
        self.priority_gate = priority_gate
        self.game_window_pattern = (
            game_window_pattern or "Roblox"
        ).strip()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._backend = WindowsInputBackend()
        self._windows = WindowsWindowBackend()

    @classmethod
    def _normalize_method(cls, method: str) -> str:
        value = str(method).strip().lower()
        aliases = {
            "space": cls.SPACE_MODE,
            "space mode": cls.SPACE_MODE,
            "alt+tab": cls.ALT_TAB_MODE,
            "alt-tab": cls.ALT_TAB_MODE,
            "alt tab": cls.ALT_TAB_MODE,
            "alt_tab": cls.ALT_TAB_MODE,
        }
        if value not in aliases:
            raise WindowError(f"Unsupported Anti-AFK method: {method}")
        return aliases[value]

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @staticmethod
    def _foreground_window() -> WindowInfo:
        hwnd = int(user32.GetForegroundWindow())
        if not hwnd:
            raise WindowError("Could not determine the active window.")
        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
        return WindowInfo(hwnd, title)

    @staticmethod
    def _set_foreground(window: WindowInfo) -> None:
        if not window.window_id or not user32.IsWindow(window.window_id):
            raise WindowError("Previous window is no longer available.")
        if user32.IsIconic(window.window_id):
            user32.ShowWindow(window.window_id, 9)  # SW_RESTORE
        if not user32.SetForegroundWindow(window.window_id):
            error = ctypes.get_last_error()
            raise WindowError(
                f"SetForegroundWindow failed: {error}"
            )
        time.sleep(0.20)

    def _find_game(self) -> WindowInfo:
        for process_name in (
            "RobloxPlayerBeta.exe",
            "Sober.exe",
        ):
            try:
                return self._windows.find_window(
                    self.game_window_pattern,
                    process_name=process_name,
                )
            except Exception:
                pass
        try:
            return self._windows.find_window(
                self.game_window_pattern
            )
        except Exception as exc:
            raise WindowError(str(exc)) from exc

    def _press_space(self, game: WindowInfo) -> bool:
        try:
            if self._backend.background_key(
                game.window_id,
                "space",
            ):
                self.log(
                    f"Anti-AFK: background Space → {game.title}"
                )
                return True
        except InputBackendError:
            pass
        return False

    def _foreground_space_fallback(self, previous: WindowInfo):
        self._backend.press_key("space")
        self.log("Anti-AFK: native SendInput Space fallback")
        try:
            self._set_foreground(previous)
        except WindowError as exc:
            self.log(
                f"Anti-AFK: previous window restore failed: {exc}"
            )

    def _alt_tab_once(self) -> None:
        try:
            self._backend.hotkey("alt", "tab")
        except InputBackendError as exc:
            raise WindowError(str(exc)) from exc

    def _tick(self) -> None:
        previous = self._foreground_window()

        if self.method == self.SPACE_MODE:
            game = self._find_game()
            if self._press_space(game):
                return

            # Some game engines ignore background WM_KEY* messages. Fall back
            # to the proven SendInput path, then immediately restore focus.
            self.log(
                f"Anti-AFK: {game.title} rejected background input; "
                "using focus fallback"
            )
            if game.window_id != previous.window_id:
                self._set_foreground(game)
            self._foreground_space_fallback(previous)
            return

        # Alt+Tab is inherently a foreground-window operation.
        self._alt_tab_once()
        time.sleep(0.20)
        try:
            self._backend.press_key("space")
            self.log("Anti-AFK: Alt+Tab → Space")
        finally:
            time.sleep(0.20)
            try:
                self._set_foreground(previous)
                self.log("Anti-AFK: previous window restored")
            except WindowError as exc:
                self.log(
                    f"Anti-AFK restore failed: {exc}"
                )
                raise

    def start(self) -> None:
        if self.running:
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="SolsRNG-Windows-AntiAFK",
            daemon=True,
        )
        self._thread.start()
        self.log(
            "Anti-AFK started "
            f"(method={self.method}, backend=windows-native-background-first, "
            f"window={self.game_window_pattern})"
        )

    def stop(self, restore: bool = True) -> None:
        del restore
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        self._thread = None
        self.log("Anti-AFK stopped")

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self.priority_gate is not None:
                    self.priority_gate.enter_afk()
                try:
                    self._tick()
                finally:
                    if self.priority_gate is not None:
                        self.priority_gate.leave()
            except Exception as exc:
                self.log(f"Anti-AFK error: {exc}")
            if self._stop.wait(self.interval_seconds):
                break

    def swap_to_game(self) -> None:
        self.log(
            "Anti-AFK: game window is detected automatically; "
            "background input is attempted first."
        )

    def restore_previous_window(self) -> None:
        self.log(
            "Anti-AFK: previous-window restore is automatic after "
            "the native focus fallback."
        )
