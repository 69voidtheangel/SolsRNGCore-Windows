from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import os
from typing import Any


if os.name == "nt":
    _windows_config_root = Path(
        os.environ.get(
            "LOCALAPPDATA",
            Path.home() / "AppData" / "Local",
        )
    )
    CONFIG_DIR = _windows_config_root / "SolsRNGCore"
else:
    CONFIG_DIR = (
        Path(
            os.environ.get(
                "XDG_CONFIG_HOME",
                Path.home() / ".config",
            )
        )
        / "solsrng"
    )

CONFIG_PATH = CONFIG_DIR / "core.json"


NORMAL_BIOMES = [
    "NORMAL",
    "WINDY",
    "SNOWY",
    "RAINY",
    "SANDSTORM",
    "HELL",
    "STARFALL",
    "HEAVEN",
    "CORRUPTION",
    "NULL",
]

EVENT_BIOMES = [
    "PUMPKIN MOON",
    "GRAVEYARD",
    "BLAZING SUN",
    "BLOOD RAIN",
    "AURORA",
    "EGGLAND",
]

RARE_LIST = [
    "GLITCHED",
    "DREAMSPACE",
    "CYBERSPACE",
    "SINGULARITY",
]

RARE_BIOMES = set(RARE_LIST)

BIOMES = (
    NORMAL_BIOMES
    + EVENT_BIOMES
    + RARE_LIST
)


@dataclass
class WebhookProfile:
    name: str = "Main Server"

    enabled: bool = False

    url: str = ""

    # Which biomes this Discord profile receives.
    notify_biomes: list[str] = field(
        default_factory=lambda: list(BIOMES)
    )

    # One Discord role ID per biome.
    # Empty string = no role ping.
    biome_roles: dict[str, str] = field(
        default_factory=lambda: {
            biome: ""
            for biome in BIOMES
        }
    )

    # For rare biomes:
    # role ID first;
    # if no role ID exists and this is enabled,
    # use @everyone instead.
    rare_everyone_fallback: bool = False

    roblox_private_server_url: str = ""

    biome_image_dir: str = "library/biomes"


@dataclass
class AntiAFKConfig:
    enabled: bool = False

    interval_seconds: float = 120.0

    # space / alt_tab
    method: str = "space"

    # auto / ydotool / xdotool
    backend: str = "auto"


@dataclass
class AppConfig:
    profiles: list[WebhookProfile] = field(
        default_factory=lambda: [
            WebhookProfile()
        ]
    )

    active_profile: int = 0

    anti_afk: AntiAFKConfig = field(
        default_factory=AntiAFKConfig
    )

    theme: str = "midnight"


def _coerce_roles(raw: Any) -> dict[str, str]:
    roles = {
        biome: ""
        for biome in BIOMES
    }

    if isinstance(raw, dict):
        for biome in BIOMES:
            value = raw.get(
                biome,
                "",
            )

            roles[biome] = (
                str(value).strip()
                if value is not None
                else ""
            )

    return roles


def _profile_from_dict(
    data: dict[str, Any],
) -> WebhookProfile:
    # Migrate old rare-role configurations.
    old_rare = data.get(
        "rare",
        {},
    )

    if not isinstance(
        old_rare,
        dict,
    ):
        old_rare = {}

    old_roles = [
        str(value).strip()
        for value in old_rare.get(
            "role_ids",
            [],
        )
        if str(value).strip()
    ]

    roles = _coerce_roles(
        data.get(
            "biome_roles",
            {},
        )
    )

    for rare, role in zip(
        RARE_LIST,
        old_roles,
    ):
        if not roles.get(rare):
            roles[rare] = role

    raw_notify = data.get(
        "notify_biomes",
        BIOMES,
    )

    if not isinstance(
        raw_notify,
        list,
    ):
        raw_notify = list(BIOMES)

    notify = [
        str(value)
        .strip()
        .upper()
        for value in raw_notify
        if str(value)
        .strip()
        .upper()
        in BIOMES
    ]

    if not notify:
        notify = list(BIOMES)

    return WebhookProfile(
        name=str(
            data.get(
                "name",
                "Main Server",
            )
        ),

        enabled=bool(
            data.get(
                "enabled",
                True,
            )
        ),

        url=str(
            data.get(
                "url",
                "",
            )
        ),

        notify_biomes=notify,

        biome_roles=roles,

        rare_everyone_fallback=bool(
            data.get(
                "rare_everyone_fallback",
                False,
            )
        ),

        roblox_private_server_url=str(
            data.get(
                "roblox_private_server_url",
                "",
            )
        ),

        biome_image_dir=str(
            data.get(
                "biome_image_dir",
                "library/biomes",
            )
        ),
    )


def _from_dict(
    data: dict[str, Any],
) -> AppConfig:

    if "profiles" in data:
        raw_profiles = data.get(
            "profiles",
            [],
        )

        if not isinstance(
            raw_profiles,
            list,
        ):
            raw_profiles = []

        profiles = [
            _profile_from_dict(profile)
            for profile in raw_profiles
            if isinstance(
                profile,
                dict,
            )
        ]

        if not profiles:
            profiles = [
                WebhookProfile()
            ]

    elif "webhook" in data:
        old = data.get(
            "webhook",
            {},
        )

        if not isinstance(
            old,
            dict,
        ):
            old = {}

        profiles = [
            _profile_from_dict(
                {
                    "name": "Main Server",
                    **old,
                }
            )
        ]

    else:
        profiles = [
            WebhookProfile()
        ]

    anti_afk = data.get(
        "anti_afk",
        {},
    )

    if not isinstance(
        anti_afk,
        dict,
    ):
        anti_afk = {}

    try:
        active_profile = int(
            data.get(
                "active_profile",
                0,
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        active_profile = 0

    active_profile = max(
        0,
        min(
            active_profile,
            len(profiles) - 1,
        ),
    )

    try:
        interval_seconds = float(
            anti_afk.get(
                "interval_seconds",
                120,
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        interval_seconds = 120.0

    method = str(
        anti_afk.get(
            "method",
            "space",
        )
    ).strip().lower()

    if method not in {
        "space",
        "alt_tab",
    }:
        method = "space"

    backend = str(
        anti_afk.get(
            "backend",
            "auto",
        )
    ).strip().lower()

    if backend not in {
        "auto",
        "windows",
    }:
        backend = "auto"

    return AppConfig(
        profiles=profiles,

        active_profile=active_profile,

        anti_afk=AntiAFKConfig(
            enabled=bool(
                anti_afk.get(
                    "enabled",
                    False,
                )
            ),

            interval_seconds=interval_seconds,

            method=method,

            backend=backend,
        ),

        theme=str(
            data.get(
                "theme",
                "midnight",
            )
        ),
    )


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        return AppConfig()

    try:
        raw = json.loads(
            CONFIG_PATH.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            raw,
            dict,
        ):
            return AppConfig()

        return _from_dict(raw)

    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
    ):
        return AppConfig()


def save_config(
    config: AppConfig,
) -> None:
    CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = CONFIG_PATH.with_suffix(
        ".json.tmp"
    )

    temporary.write_text(
        json.dumps(
            asdict(config),
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary.replace(
        CONFIG_PATH
    )
