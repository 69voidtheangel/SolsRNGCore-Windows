from __future__ import annotations

import os
import platform
import threading
import time
from collections import deque
from pathlib import Path


MAX_MEMORY_LINES = 300
MAX_LOG_BYTES = 2 * 1024 * 1024


class DiagnosticLogger:
    """
    Small bounded diagnostic logger.

    Keeps only the newest MAX_MEMORY_LINES in RAM and rotates the
    on-disk log when it grows beyond MAX_LOG_BYTES.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._memory = deque(maxlen=MAX_MEMORY_LINES)

        self.log_dir = (
            Path.home()
            / ".local"
            / "share"
            / "solsrngcore"
            / "logs"
        )

        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.log_dir / "core.log"

    def write(self, level: str, message: str) -> str:
        timestamp = time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        line = (
            f"[{timestamp}] "
            f"[{level.upper():5}] "
            f"{message}"
        )

        with self._lock:
            self._memory.append(line)

            try:
                self._rotate_if_needed()

                with self.log_file.open(
                    "a",
                    encoding="utf-8",
                ) as handle:
                    handle.write(line + "\n")

            except OSError:
                # Diagnostics must never crash the application.
                pass

        return line

    def info(self, message: str) -> str:
        return self.write("INFO", message)

    def warning(self, message: str) -> str:
        return self.write("WARN", message)

    def error(self, message: str) -> str:
        return self.write("ERROR", message)

    def fatal(self, message: str) -> str:
        return self.write("FATAL", message)

    def recent(self, count: int = 100) -> list[str]:
        with self._lock:
            if count <= 0:
                return []

            return list(self._memory)[-count:]

    def recent_text(self, count: int = 100) -> str:
        return "\n".join(self.recent(count))

    def _rotate_if_needed(self):
        try:
            if not self.log_file.exists():
                return

            if self.log_file.stat().st_size < MAX_LOG_BYTES:
                return

            old = self.log_file.with_suffix(".log.1")

            try:
                old.unlink()
            except FileNotFoundError:
                pass

            self.log_file.replace(old)

        except OSError:
            pass

    def system_info(self) -> str:
        return "\n".join(
            [
                f"OS: {platform.platform()}",
                f"Python: {platform.python_version()}",
                f"Arch: {platform.machine()}",
                f"PID: {os.getpid()}",
                f"CPU count: {os.cpu_count()}",
            ]
        )


LOGGER = DiagnosticLogger()
