from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Callable

from solsrng_core.config import BIOMES
from solsrng_core.platform.windows.environment import default_log_directories


def _xdg_data_home() -> Path:
    value = os.environ.get("XDG_DATA_HOME", "").strip()

    if value:
        return Path(value).expanduser()

    return Path.home() / ".local" / "share"


def _sober_log_dirs() -> list[Path]:
    # Windows port: Roblox log discovery is configurable and does not assume Sober.
    if os.name == "nt":
        return default_log_directories()

    home = Path.home()
    xdg_data = _xdg_data_home()

    candidates = [
        Path(
            os.environ["SOLSRNG_SOBER_LOG_DIR"]
        ).expanduser()
        if os.environ.get("SOLSRNG_SOBER_LOG_DIR")
        else None,
        home
        / ".var"
        / "app"
        / "org.vinegarhq.Sober"
        / "data"
        / "sober"
        / "sober_logs",
        xdg_data / "sober" / "sober_logs",
        home / ".local" / "share" / "sober" / "sober_logs",
        home / ".config" / "sober" / "sober_logs",
    ]

    result: list[Path] = []
    seen: set[str] = set()

    for candidate in candidates:
        if candidate is None:
            continue

        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            resolved = candidate.expanduser()

        key = str(resolved)
        if key not in seen:
            seen.add(key)
            result.append(resolved)

    return result
def _find_existing_log_dir() -> Path | None:
    for directory in _sober_log_dirs():
        try:
            if directory.is_dir():
                return directory
        except OSError:
            continue

    return None


def _default_log_dir() -> Path:
    existing = _find_existing_log_dir()

    if existing is not None:
        return existing

    # Fall back to the standard Flatpak location when the directory
    # has not been created yet.
    return _sober_log_dirs()[0]


class SoberBiomeWatcher:
    """Monitor Roblox/Sober logs and emit only real Sol's RNG biome changes."""

    _RPC_RE = re.compile(
        r"\[BloxstrapRPC\]\s+(\{.*\})\s*$"
    )

    def __init__(
        self,
        callback: Callable[[str], None],
        log: Callable[[str], None] | None = None,
        log_path: Path | None = None,
        biome_ended_callback: Callable[[str], None] | None = None,
    ):
        self.callback = callback
        self.log = log or (lambda _: None)
        self.biome_ended_callback = biome_ended_callback

        if log_path is not None:
            supplied = log_path.expanduser()
            self.log_dir = supplied.parent
        else:
            self.log_dir = _default_log_dir()

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._current_biome: str | None = None
        self._initial_state_sent = False

    @property
    def running(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
        )

    @property
    def current_biome(self) -> str | None:
        return self._current_biome

    @property
    def log_directory(self) -> Path:
        return self.log_dir

    def start(self) -> None:
        if self.running:
            return

        self._stop.clear()

        self._thread = threading.Thread(
            target=self._run,
            name="SolsRNG-SoberLogMonitor",
            daemon=True,
        )

        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

        thread = self._thread

        if (
            thread is not None
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=0.2)

        if thread is None or not thread.is_alive():
            self._thread = None

    def _refresh_log_dir(self) -> bool:
        if self.log_dir.is_dir():
            return True

        discovered = _find_existing_log_dir()

        if discovered is None:
            return False

        if discovered != self.log_dir:
            self.log_dir = discovered

            self.log(
                f"Found Sober log directory: {discovered}"
            )

        return True

    def _find_newest_log(self) -> Path | None:
        if not self._refresh_log_dir():
            return None

        try:
            logs = [
                path
                for path in self.log_dir.glob("*.log")
                if path.is_file()
                and path.name != "latest.log"
            ]

            latest = self.log_dir / "latest.log"

            if latest.is_file():
                logs.append(latest)

            if not logs:
                return None

            return max(
                logs,
                key=lambda path: path.stat().st_mtime_ns,
            )

        except OSError:
            return None

    def _extract_biome(self, line: str) -> str | None:
        match = self._RPC_RE.search(line)

        if not match:
            return None

        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

        if payload.get("command") != "SetRichPresence":
            return None

        data = payload.get("data")

        if not isinstance(data, dict):
            return None

        large_image = data.get("largeImage")

        if not isinstance(large_image, dict):
            return None

        biome = str(
            large_image.get("hoverText", "")
        ).strip().upper()

        if not biome:
            return None

        # Sober can format biome names differently from the
        # canonical Sol's RNG Core names. Normalize whitespace
        # so names such as "SAND STORM" match "SANDSTORM".
        normalized = " ".join(biome.split())

        # Known formatting aliases.
        aliases = {
            "SAND STORM": "SANDSTORM",
        }

        return aliases.get(normalized, normalized)

    def _emit_initial_state(self, biome: str) -> None:
        self._current_biome = biome
        self._initial_state_sent = True

        self.log(
            f"Sober current biome: {biome}"
        )

        try:
            self.callback(biome)
        except Exception as exc:
            self.log(
                f"Initial biome callback error: {exc}"
            )

    def _process_biome(self, biome: str) -> None:
        # Ignore duplicate RPC updates.
        if biome == self._current_biome:
            return

        previous = self._current_biome
        self._current_biome = biome

        if previous is None:
            self._emit_initial_state(biome)
            return

        self.log(
            f"Sober biome changed: {previous} -> {biome}"
        )

        # The previous biome has ended because the authoritative
        # current biome changed.
        if self.biome_ended_callback is not None:
            try:
                self.biome_ended_callback(previous)
            except Exception as exc:
                self.log(
                    f"Biome ended callback error: {exc}"
                )

        try:
            self.callback(biome)
        except Exception as exc:
            self.log(
                f"Biome callback error: {exc}"
            )

    def _read_current_state(
        self,
        target: Path,
    ) -> int:
        """
        Read the existing log once, find the LAST valid biome,
        emit it exactly once, then return the EOF position.
        """

        last_biome: str | None = None

        try:
            with target.open(
                "r",
                encoding="utf-8",
                errors="replace",
            ) as handle:
                for line in handle:
                    biome = self._extract_biome(line)

                    if biome is not None:
                        last_biome = biome

                position = handle.tell()

        except (OSError, UnicodeError) as exc:
            self.log(
                f"Unable to read current Sober state: {exc}"
            )
            return 0

        if last_biome is not None:
            self._emit_initial_state(last_biome)

        else:
            self.log(
                "No valid Sol's RNG biome found in current Sober log"
            )

        return position

    def _run(self) -> None:
        handle = None
        current_file: Path | None = None
        position = 0

        while not self._stop.is_set():
            try:
                target = self._find_newest_log()

                if target is None:
                    self._stop.wait(0.25)
                    continue

                target = target.resolve(strict=True)

                # New Sober session / new log file.
                if handle is None or current_file != target:
                    if handle is not None:
                        try:
                            handle.close()
                        except OSError:
                            pass

                    handle = target.open(
                        "r",
                        encoding="utf-8",
                        errors="replace",
                    )

                    current_file = target
                    position = 0

                    if not self._initial_state_sent:
                        handle.close()
                        handle = None

                        position = self._read_current_state(target)

                        handle = target.open(
                            "r",
                            encoding="utf-8",
                            errors="replace",
                        )

                        handle.seek(position)

                    else:
                        # A new Sober log means a new session.
                        # Establish its current state from the file.
                        handle.close()
                        handle = None

                        self._initial_state_sent = False
                        self._current_biome = None
                        position = self._read_current_state(target)

                        handle = target.open(
                            "r",
                            encoding="utf-8",
                            errors="replace",
                        )

                        handle.seek(position)

                    self.log(
                        f"Live Sober monitoring: {target}"
                    )

                handle.seek(position)

                while not self._stop.is_set():
                    line = handle.readline()

                    if not line:
                        break

                    position = handle.tell()

                    biome = self._extract_biome(line)

                    if biome is not None:
                        self._process_biome(biome)

                newest = self._find_newest_log()

                if newest is not None:
                    try:
                        if newest.resolve() != current_file:
                            continue
                    except OSError:
                        pass

                try:
                    if (
                        current_file is not None
                        and current_file.stat().st_size < position
                    ):
                        handle.seek(0)
                        position = 0

                except OSError:
                    pass

            except (
                FileNotFoundError,
                OSError,
                UnicodeError,
            ):
                if handle is not None:
                    try:
                        handle.close()
                    except OSError:
                        pass

                handle = None
                current_file = None
                position = 0

            except Exception as exc:
                self.log(
                    f"Sober monitor error: {exc}"
                )

            self._stop.wait(0.05)

        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
