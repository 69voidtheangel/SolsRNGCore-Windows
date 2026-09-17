from __future__ import annotations

from abc import ABC, abstractmethod


class InputBackendError(RuntimeError):
    """Raised when an input backend cannot perform an action."""


class InputBackend(ABC):
    """Common interface for Linux input injection backends."""

    name: str = "unknown"

    @abstractmethod
    def press_key(self, key: str) -> None:
        """Press and release a key."""

    @abstractmethod
    def hotkey(self, *keys: str) -> None:
        """Press a key combination."""

    def close(self) -> None:
        """Release backend resources."""
