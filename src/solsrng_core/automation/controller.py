from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from .models import AutomationCoordinates, AutomationItem
from .windows_background import (
    WindowsBackgroundInput,
    WindowsTargetWindow,
)


class AutomationError(RuntimeError):
    pass


WindowInfo = WindowsTargetWindow


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
    input_mode: str = "BACKGROUND"


class AutomationController:
    """Windows automation controller using window-directed background input."""

    RETRIES = 3
    CLICK_SETTLE = 0.12
    TYPE_SETTLE = 0.20

    def __init__(
        self,
        *,
        backend: str = "auto",
        game_window_pattern: str = "Roblox",
        on_status: Callable[[AutomationStatus], None] | None = None,
        priority_gate=None,
    ):
        self.backend = "windows_background"
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
        self._input = WindowsBackgroundInput(self.game_window_pattern)

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

    def _sync_target_pattern(self):
        self._input.window_pattern = (
            self.game_window_pattern.strip() or "Roblox"
        )

    def authenticate_async(self):
        if self.status.authenticated or self.status.authenticating:
            return
        self.status.authenticating = True
        self._emit_status()
        self._auth_thread = threading.Thread(
            target=self.authenticate,
            name="solsrng-windows-target-detect",
            daemon=True,
        )
        self._auth_thread.start()

    def authenticate(self) -> bool:
        try:
            self._sync_target_pattern()
            target = self._input.find_window()
            self.status.authenticated = True
            self.status.auth_error = ""
            self.status.game_window = target.display_name
            self.status.message = "TARGET DETECTED • BACKGROUND READY"
            self.log_status(target)
            return True
        except Exception as exc:
            self.status.authenticated = False
            self.status.auth_error = str(exc)
            self.status.game_window = ""
            return False
        finally:
            self.status.authenticating = False
            self._emit_status()

    def retry_authentication(self):
        self.status.authenticated = False
        self.status.auth_error = ""
        self.status.game_window = ""
        self.authenticate_async()

    def log_status(self, window: WindowsTargetWindow):
        self._set_message(
            f"TARGET READY • {window.title} • {window.executable}",
        )

    def find_game_window(self) -> WindowInfo:
        self._sync_target_pattern()
        return self._input.find_window()

    def start(self):
        if self.status.running:
            return
        if not self.status.authenticated:
            raise AutomationError("Detect the Roblox target window first.")
        self._validate_items()
        self._stop_event.clear()
        self.status.running = True
        self.status.testing = False
        self.status.message = "RUNNING • BACKGROUND"
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
            raise AutomationError("Detect the Roblox target window first.")
        self._validate_item(item)
        if not self._run_lock.acquire(blocking=False):
            raise AutomationError("Automation is already busy.")
        self.status.testing = True
        self.status.message = f"TESTING • BACKGROUND • {item.name}"
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

    def _validate_item(self, item: AutomationItem):
        if not item.search_text.strip():
            raise AutomationError(f"{item.name}: search text is empty.")
        missing = self.coordinates.missing()
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

    def _target_or_refresh(self, current: WindowInfo | None = None) -> WindowInfo:
        if current is not None and self._input.is_alive(current):
            return current
        return self.find_game_window()

    def _run_item(self, item: AutomationItem):
        game = self.find_game_window()
        self.status.game_window = game.display_name
        self.status.previous_window = ""
        self._emit_status()

        coords = self.coordinates
        if coords.missing():
            raise AutomationError(
                "Shared automation coordinates are incomplete: "
                + ", ".join(coords.missing())
            )

        self._set_message(
            f"BACKGROUND RUN • {game.display_name}",
            current_item=item.name,
        )

        try:
            game = self._target_or_refresh(game)
            self._click(game, coords.inventory, "Inventory", item)
            time.sleep(item.click_delay_seconds)

            game = self._target_or_refresh(game)
            self._click(game, coords.items, "Items", item)
            time.sleep(item.click_delay_seconds)

            game = self._target_or_refresh(game)
            self._click(game, coords.search_bar, "Search Bar", item)
            time.sleep(item.click_delay_seconds)

            self._ctrl_a(game)
            time.sleep(0.05)
            self._type_text(game, item.search_text)
            time.sleep(max(item.click_delay_seconds, self.TYPE_SETTLE))

            game = self._target_or_refresh(game)
            self._click(game, coords.first_slot, "First Slot", item)
            time.sleep(item.click_delay_seconds)

            game = self._target_or_refresh(game)
            self._click(game, coords.quantity, "Quantity", item)
            time.sleep(0.10)
            self._ctrl_a(game)
            time.sleep(0.05)
            self._type_text(game, "1")
            time.sleep(max(item.click_delay_seconds, self.TYPE_SETTLE))

            game = self._target_or_refresh(game)
            self._click(game, coords.use_button, "Use Button", item)
            time.sleep(item.post_use_delay_seconds)

            game = self._target_or_refresh(game)
            self._click(game, coords.close_inventory, "Close Inventory", item)

            self._set_message(
                f"COMPLETE • BACKGROUND • {item.name}",
                current_item=item.name,
            )
        finally:
            self.status.game_window = ""
            self.status.previous_window = ""
            self._emit_status()

    def _click(
        self,
        game: WindowInfo,
        coordinate,
        label: str,
        item: AutomationItem,
    ):
        if coordinate is None:
            raise AutomationError(
                f"{item.name}: {label} coordinate is missing."
            )
        x, y = int(coordinate[0]), int(coordinate[1])
        game = self._target_or_refresh(game)
        try:
            self._input.click_screen(game, x, y)
        except Exception as exc:
            raise AutomationError(
                f"{item.name}: background click failed at {label}: {exc}"
            ) from exc
        self._set_message(
            f"BACKGROUND CLICK • {label} • {item.name}",
            current_item=item.name,
        )
        time.sleep(self.CLICK_SETTLE)

    def _type_text(self, game: WindowInfo, text: str):
        game = self._target_or_refresh(game)
        try:
            self._input.type_text(game, text)
        except Exception as exc:
            raise AutomationError(
                f"Background text input failed: {exc}"
            ) from exc

    def _ctrl_a(self, game: WindowInfo):
        game = self._target_or_refresh(game)
        try:
            self._input.hotkey(game, "ctrl", "a")
        except Exception as exc:
            raise AutomationError(
                f"Background Ctrl+A failed: {exc}"
            ) from exc
