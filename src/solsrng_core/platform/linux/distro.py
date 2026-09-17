from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LinuxDistribution:
    """Basic Linux distribution information."""

    id: str
    name: str
    version: str
    id_like: tuple[str, ...]


def detect_distribution() -> LinuxDistribution:
    """Read standard /etc/os-release information."""

    values: dict[str, str] = {}

    path = Path("/etc/os-release")

    if path.exists():
        for line in path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')

    distro_id = values.get("ID", "unknown").lower()

    id_like = tuple(
        item.lower()
        for item in values.get("ID_LIKE", "").split()
        if item
    )

    return LinuxDistribution(
        id=distro_id,
        name=values.get("NAME", distro_id),
        version=values.get("VERSION_ID", ""),
        id_like=id_like,
    )
