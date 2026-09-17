from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .models import AutomationCoordinates, AutomationItem


CONFIG_DIR = (
    Path(
        os.environ.get(
            "XDG_CONFIG_HOME",
            Path.home() / ".config",
        )
    )
    / "solsrng"
)

CONFIG_PATH = CONFIG_DIR / "automation.json"


@dataclass
class AutomationSettings:
    enabled: bool = False
    backend: str = "auto"
    game_window_pattern: str = "Sober"

    # ONE coordinate set shared by every automation item.
    coordinates: AutomationCoordinates = field(
        default_factory=AutomationCoordinates
    )

    items: list[AutomationItem] = field(
        default_factory=list
    )

    def _sync_item_coordinates(self) -> None:
        shared = self.coordinates.copy()

        for item in self.items:
            item.coordinates = shared.copy()

    def to_dict(self) -> dict:
        self._sync_item_coordinates()

        return {
            "enabled": self.enabled,
            "backend": self.backend,
            "game_window_pattern": self.game_window_pattern,
            "coordinates": self.coordinates.to_dict(),
            "items": [
                item.to_dict()
                for item in self.items
            ],
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
    ) -> "AutomationSettings":
        if not isinstance(data, dict):
            data = {}

        raw_items = data.get(
            "items",
            [],
        )

        items: list[AutomationItem] = []

        if isinstance(raw_items, list):
            for raw in raw_items:
                if isinstance(raw, dict):
                    try:
                        items.append(
                            AutomationItem.from_dict(
                                raw
                            )
                        )
                    except Exception:
                        pass

        backend = str(
            data.get(
                "backend",
                "auto",
            )
        ).strip().lower()

        if backend not in {
            "auto",
            "ydotool",
            "xdotool",
        }:
            backend = "auto"

        pattern = str(
            data.get(
                "game_window_pattern",
                "Sober",
            )
        ).strip()

        if not pattern:
            pattern = "Sober"

        coordinates = AutomationCoordinates.from_dict(
            data.get(
                "coordinates",
                {},
            )
        )

        # Migrate old per-item coordinates.
        if not coordinates.complete():
            for item in items:
                if item.coordinates.complete():
                    coordinates = item.coordinates.copy()
                    break

        settings = cls(
            enabled=bool(
                data.get(
                    "enabled",
                    False,
                )
            ),
            backend=backend,
            game_window_pattern=pattern,
            coordinates=coordinates,
            items=items,
        )

        settings._sync_item_coordinates()

        return settings


def default_settings() -> AutomationSettings:
    return AutomationSettings(
        enabled=False,
        backend="auto",
        game_window_pattern="Sober",
        coordinates=AutomationCoordinates(),
        items=[
            AutomationItem(
                name="Strange Controller",
                search_text="Strange Controller",
                cooldown_seconds=20 * 60,
            ),
            AutomationItem(
                name="Biome Randomizer",
                search_text="Biome Randomizer",
                cooldown_seconds=35 * 60,
            ),
        ],
    )


def load_settings() -> AutomationSettings:
    if not CONFIG_PATH.is_file():
        settings = default_settings()
        save_settings(settings)
        return settings

    try:
        data = json.loads(
            CONFIG_PATH.read_text(
                encoding="utf-8"
            )
        )

    except Exception:
        settings = default_settings()
        save_settings(settings)
        return settings

    settings = AutomationSettings.from_dict(
        data
    )

    # Older automation.json files may have no items.
    # Keep existing settings, but restore the useful defaults.
    if not settings.items:
        defaults = default_settings()

        settings.items = defaults.items

        if not settings.game_window_pattern:
            settings.game_window_pattern = (
                defaults.game_window_pattern
            )

    settings._sync_item_coordinates()
    save_settings(settings)

    return settings


def save_settings(
    settings: AutomationSettings,
):
    CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = CONFIG_PATH.with_suffix(
        ".json.tmp"
    )

    temporary.write_text(
        json.dumps(
            settings.to_dict(),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary.replace(
        CONFIG_PATH
    )
