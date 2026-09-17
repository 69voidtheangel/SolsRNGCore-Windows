from __future__ import annotations

from dataclasses import dataclass

from .distro import (
    LinuxDistribution,
    detect_distribution,
)
from .session import (
    LinuxSession,
    available_commands,
    detect_session,
)


@dataclass(frozen=True)
class LinuxEnvironment:
    distribution: LinuxDistribution
    session: LinuxSession
    commands: dict[str, bool]


def detect_environment() -> LinuxEnvironment:
    return LinuxEnvironment(
        distribution=detect_distribution(),
        session=detect_session(),
        commands=available_commands(),
    )
