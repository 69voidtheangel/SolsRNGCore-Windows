from __future__ import annotations

import ctypes
import threading
import time
from typing import Callable

from .backends.windows import WindowsInputBackend
from .backends.base import InputBackendError

class WindowError(RuntimeError):
    """Raised when Windows Anti-AFK cannot perform an input action."""

user32 = ctypes.WinDLL("user32", use_last_error=True)

class AntiAFKController:
    """
    Native Windows Anti-AFK controller.

    Methods:
        space   - press Space at the configured interval.
        alt_tab - switch to the next window, press Space, then switch back.

    This implementation intentionally avoids external automation tools.
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
    ):
        self.interval_seconds = max(1.0, float(interval_seconds))
        self.method = self._normalize_method(method)
        self.backend_preference = self._normalize_backend(backend_preference)
        self.log = log or (lambda _: None)
        self.priority_gate = priority_gate
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._backend = WindowsInputBackend()

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

    @staticmethod
    def _normalize_backend(backend: str) -> str:
        value = str(backend).strip().lower()
        if value not in {"auto", "windows"}:
            raise WindowError(f"Unsupported Windows input backend: {backend}")
        return "windows"

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @staticmethod
    def _foreground_window() -> int:
        return int(user32.GetForegroundWindow())

    @staticmethod
    def _set_foreground(hwnd: int) -> None:
        if not hwnd or not user32.IsWindow(hwnd):
            raise WindowError("Previous window is no longer available.")
        if not user32.SetForegroundWindow(hwnd):
            error = ctypes.get_last_error()
            raise WindowError(f"SetForegroundWindow failed: {error}")

    def _press_space(self) -> None:
        try:
            self._backend.press_key("space")
        except InputBackendError as exc:
            raise WindowError(str(exc)) from exc

    def _alt_tab_once(self) -> None:
        try:
            self._backend.hotkey("alt", "tab")
        except InputBackendError as exc:
            raise WindowError(str(exc)) from exc

    def _tick(self) -> None:
        if self.method == self.SPACE_MODE:
            self._press_space()
            self.log("Anti-AFK: Space pressed")
            return

        previous = self._foreground_window()
        self._alt_tab_once()
        time.sleep(0.20)
        try:
            self._press_space()
            self.log("Anti-AFK: Alt+Tab → Space")
        finally:
            time.sleep(0.20)
            try:
                self._set_foreground(previous)
                self.log("Anti-AFK: previous window restored")
            except WindowError as exc:
                self.log(f"Anti-AFK restore failed: {exc}")
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
            f"Anti-AFK started (method={self.method}, backend=windows)"
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
        self.log("Anti-AFK: focus switching is handled automatically.")

    def restore_previous_window(self) -> None:
        self.log("Anti-AFK: previous-window restore is handled automatically.")
