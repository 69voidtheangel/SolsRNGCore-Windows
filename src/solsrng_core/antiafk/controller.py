from __future__ import annotations

import threading
from typing import Callable

from solsrng_core.automation.windows_background import (
    WindowsBackgroundInput,
    WindowsTargetWindow,
)


class WindowError(RuntimeError):
    """Raised when Windows Anti-AFK cannot target the game window."""


class AntiAFKController:
    """Native Windows Anti-AFK using window-directed background input."""

    SPACE_MODE = "space"
    ALT_TAB_MODE = "alt_tab"
    BACKGROUND_MODE = "background"

    def __init__(
        self,
        interval_seconds: float = 120.0,
        method: str = SPACE_MODE,
        backend_preference: str = "auto",
        game_window_pattern: str = "Roblox",
        log: Callable[[str], None] | None = None,
        priority_gate=None,
    ):
        self.interval_seconds = max(1.0, float(interval_seconds))
        self.method = self._normalize_method(method)
        self.backend_preference = self._normalize_backend(backend_preference)
        self.game_window_pattern = (game_window_pattern or "Roblox").strip()
        self.log = log or (lambda _: None)
        self.priority_gate = priority_gate
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._backend = WindowsBackgroundInput(self.game_window_pattern)
        self._last_window: WindowsTargetWindow | None = None

    @classmethod
    def _normalize_method(cls, method: str) -> str:
        value = str(method).strip().lower()
        aliases = {
            "space": cls.SPACE_MODE,
            "space mode": cls.SPACE_MODE,
            "alt+tab": cls.BACKGROUND_MODE,
            "alt-tab": cls.BACKGROUND_MODE,
            "alt tab": cls.BACKGROUND_MODE,
            "alt_tab": cls.BACKGROUND_MODE,
            "background": cls.BACKGROUND_MODE,
        }
        if value not in aliases:
            raise WindowError(f"Unsupported Anti-AFK method: {method}")
        return aliases[value]

    @staticmethod
    def _normalize_backend(backend: str) -> str:
        del backend
        return "windows_background"

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _find_target(self) -> WindowsTargetWindow:
        self._backend.window_pattern = (
            self.game_window_pattern.strip() or "Roblox"
        )
        target = self._backend.find_window()
        self._last_window = target
        return target

    def _tick(self) -> None:
        try:
            target = self._find_target()
            self._backend.background_space(target)
            self.log(
                "Anti-AFK: background Space → "
                f"{target.title} [{target.executable}, PID {target.process_id}]"
            )
        except Exception as exc:
            raise WindowError(str(exc)) from exc

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
            "Anti-AFK started (Windows background window-directed input)"
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
                self.log(f"Anti-AFK target/input error: {exc}")
            if self._stop.wait(self.interval_seconds):
                break

    def swap_to_game(self) -> None:
        try:
            target = self._find_target()
            self.log(
                "Anti-AFK target detected without focusing it: "
                f"{target.display_name}"
            )
        except Exception as exc:
            self.log(f"Anti-AFK target detection failed: {exc}")

    def restore_previous_window(self) -> None:
        # There is deliberately nothing to restore: background input never
        # changes the user's foreground window.
        self.log("Anti-AFK: no foreground window was changed.")
