"""Windows-only input and window backends.

Linux automation modules are intentionally not imported here. The Windows
package uses native user32 APIs for window discovery, background Win32
messages, and SendInput fallback.
"""

from .base import InputBackend, InputBackendError
from .windows import (
    WindowsInputBackend,
    WindowsWindowBackend,
    WindowInfo,
)

__all__ = [
    "InputBackend",
    "InputBackendError",
    "WindowsInputBackend",
    "WindowsWindowBackend",
    "WindowInfo",
]
