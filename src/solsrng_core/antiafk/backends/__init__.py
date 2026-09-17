"""Windows-only Anti-AFK input backends.

Linux backends are intentionally not imported here. Importing them from this
package caused PyInstaller/Windows startup to load xdotool/ydotool modules,
which do not belong in the Windows build.
"""

from .base import InputBackend, InputBackendError
from .windows import WindowsInputBackend

__all__ = [
    "InputBackend",
    "InputBackendError",
    "WindowsInputBackend",
]
