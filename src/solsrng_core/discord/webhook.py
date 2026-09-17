from __future__ import annotations

import json
import mimetypes
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from solsrng_core.config import (
    BIOMES,
    RARE_BIOMES,
    WebhookProfile,
)


BIOME_STYLES: dict[str, dict[str, object]] = {
    "NORMAL": {"emoji": "🌎", "color": 0x5865F2},
    "WINDY": {"emoji": "🌪", "color": 0x95A5A6},
    "SNOWY": {"emoji": "❄", "color": 0xB9F2FF},
    "RAINY": {"emoji": "🌧", "color": 0x3498DB},
    "SANDSTORM": {"emoji": "🏜", "color": 0xC2B280},
    "HELL": {"emoji": "🔥", "color": 0xFF0000},
    "STARFALL": {"emoji": "⭐", "color": 0xFFD700},
    "HEAVEN": {"emoji": "✨", "color": 0xFFFFFF},
    "CORRUPTION": {"emoji": "☠", "color": 0x8B0000},
    "NULL": {"emoji": "⬛", "color": 0x000000},

    "PUMPKIN MOON": {"emoji": "🎃", "color": 0xFF7518},
    "GRAVEYARD": {"emoji": "🪦", "color": 0x555555},
    "BLAZING SUN": {"emoji": "☀", "color": 0xFF8C00},
    "BLOOD RAIN": {"emoji": "🩸", "color": 0x990000},
    "AURORA": {"emoji": "🌌", "color": 0x00FFFF},
    "EGGLAND": {"emoji": "🥚", "color": 0xFFFF99},

    "GLITCHED": {"emoji": "⚡", "color": 0xFF00FF},
    "DREAMSPACE": {"emoji": "💤", "color": 0x9B59B6},
    "CYBERSPACE": {"emoji": "💻", "color": 0x00FF00},
    "SINGULARITY": {"emoji": "🌌", "color": 0x111111},
}


EVENT_STYLES: dict[str, dict[str, object]] = {
    "STARTED": {"emoji": "▶", "color": 0x57F287},
    "STOPPED": {"emoji": "⏹", "color": 0xED4245},
}


DEFAULT_STYLE = {
    "emoji": "🌎",
    "color": 0x5865F2,
}


@dataclass
class WebhookResult:
    ok: bool
    status: int | None = None
    error: str | None = None


def _norm(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        re.sub(
            r"\.(png|jpe?g|webp|gif)$",
            "",
            value.strip().lower(),
        ),
    )


class DiscordWebhook:
    """Discord webhook sender for Sol's RNG Core notifications."""

    def __init__(self, profile: WebhookProfile):
        self.profile = profile

    def _urls(self) -> list[str]:
        return list(
            dict.fromkeys(
                part.strip()
                for part in re.split(
                    r"[,;\n\s]+",
                    self.profile.url or "",
                )
                if part.strip()
            )
        )

    def _role_mention(
        self,
        biome: str,
        *,
        allow_everyone: bool = True,
    ) -> tuple[str, list[str]]:
        role_id = self.profile.biome_roles.get(
            biome,
            "",
        ).strip()

        if role_id.isdigit():
            return (
                f"<@&{role_id}>",
                [role_id],
            )

        if (
            allow_everyone
            and biome in RARE_BIOMES
            and self.profile.rare_everyone_fallback
        ):
            return "@everyone", []

        return "", []

    def _image(self, biome: str) -> Path | None:
        base = Path(
            self.profile.biome_image_dir
        ).expanduser()

        if base.is_absolute():
            roots = [base]
        else:
            project_root = (
                Path(__file__)
                .resolve()
                .parents[3]
            )

            roots = [
                Path.cwd() / base,
                project_root / base,
            ]

        extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
        }

        target = _norm(biome)

        for root in roots:
            if not root.is_dir():
                continue

            try:
                entries = root.iterdir()
            except OSError:
                continue

            for path in entries:
                try:
                    if (
                        path.is_file()
                        and path.suffix.lower()
                        in extensions
                        and _norm(path.name)
                        == target
                    ):
                        return path
                except OSError:
                    continue

        return None

    def _build_embed(
        self,
        *,
        title: str,
        description: str,
        color: int,
        thumbnail: str | None = None,
    ) -> dict:
        embed: dict = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "footer": {
                "text": (
                    f"Sol's RNG Core • "
                    f"{self.profile.name} • "
                    "github.com/69voidtheangel/"
                    "SolsRNGCore"
                ),
                "icon_url": (
                    "https://raw.githubusercontent.com/"
                    "69voidtheangel/SolsRNGCore/main/"
                    "assets/solsrng_core_logo.svg"
                ),
            },
        }

        if thumbnail:
            embed["thumbnail"] = {
                "url": thumbnail
            }

        return embed

    def _build_backup_embed(
        self,
        *,
        biome: str,
        details: str | None = None,
        title_suffix: str = "notification",
    ) -> dict:
        """
        Minimal fallback embed.

        No biome image, attachment, custom thumbnail, or other
        optional asset is required. This exists so a notification
        can still be delivered when the normal biome presentation
        cannot be used.
        """
        biome = str(biome).strip().upper()

        description = (
            f"Sol's RNG **{biome}** "
            f"{title_suffix}."
        )

        if details:
            description += f"\n{details}"

        if self.profile.roblox_private_server_url:
            description += (
                "\n\n[Join Roblox Private Server]"
                f"({self.profile.roblox_private_server_url})"
            )

        return self._build_embed(
            title=f"⚠️ {biome}",
            description=description,
            color=0x5865F2,
        )

    def _send_payload(
        self,
        payload: dict,
        *,
        image: Path | None = None,
        require_enabled: bool = True,
    ) -> WebhookResult:
        urls = self._urls()

        if not urls:
            return WebhookResult(
                False,
                error="No webhook URL configured",
            )

        if (
            require_enabled
            and not self.profile.enabled
        ):
            return WebhookResult(
                False,
                error="Profile disabled",
            )

        successes = 0
        errors: list[str] = []
        last_status: int | None = None

        for url in urls:
            opened = None

            try:
                if image is not None:
                    payload_for_request = (
                        json.loads(
                            json.dumps(payload)
                        )
                    )

                    payload_for_request[
                        "embeds"
                    ][0]["thumbnail"] = {
                        "url": (
                            f"attachment://"
                            f"{image.name}"
                        )
                    }

                    opened = image.open("rb")

                    response = requests.post(
                        url,
                        data={
                            "payload_json": json.dumps(
                                payload_for_request
                            )
                        },
                        files={
                            "file": (
                                image.name,
                                opened,
                                (
                                    mimetypes.guess_type(
                                        image.name
                                    )[0]
                                    or "application/"
                                    "octet-stream"
                                ),
                            )
                        },
                        timeout=(5, 15),
                    )

                else:
                    response = requests.post(
                        url,
                        json=payload,
                        timeout=(5, 15),
                    )

                last_status = response.status_code

                if (
                    200
                    <= response.status_code
                    < 300
                ):
                    successes += 1
                else:
                    errors.append(
                        f"{response.status_code}: "
                        f"{response.text[:200]}"
                    )

            except (
                requests.RequestException,
                OSError,
            ) as exc:
                errors.append(str(exc))

            finally:
                if opened is not None:
                    try:
                        opened.close()
                    except OSError:
                        pass

        if successes == len(urls):
            return WebhookResult(
                True,
                status=last_status,
            )

        if successes:
            return WebhookResult(
                True,
                status=last_status,
                error=(
                    f"Sent to {successes}/"
                    f"{len(urls)} webhooks: "
                    + " | ".join(errors)
                ),
            )

        return WebhookResult(
            False,
            status=last_status,
            error=(
                " | ".join(errors)
                or "Unknown webhook error"
            ),
        )

    def send_biome_appeared(
        self,
        biome: str,
        *,
        details: str | None = None,
    ) -> WebhookResult:
        biome = biome.strip().upper()

        if biome not in BIOMES:
            return WebhookResult(
                False,
                error=f"Unknown biome {biome!r}",
            )

        if biome not in self.profile.notify_biomes:
            return WebhookResult(
                False,
                error=f"Biome {biome!r} disabled",
            )

        style = BIOME_STYLES.get(
            biome,
            DEFAULT_STYLE,
        )

        emoji = str(style["emoji"])
        color = int(style["color"])

        description = (
            f"Sol's RNG **{biome}** "
            "has appeared."
        )

        if details:
            description += f"\n{details}"

        if self.profile.roblox_private_server_url:
            description += (
                "\n\n[Join Roblox Private Server]"
                f"({self.profile.roblox_private_server_url})"
            )

        mention, role_ids = self._role_mention(
            biome
        )

        payload = {
            "content": mention,
            "allowed_mentions": {
                "parse": (
                    ["everyone"]
                    if mention == "@everyone"
                    else []
                ),
                "roles": role_ids,
            },
            "embeds": [
                self._build_embed(
                    title=(
                        f"{emoji} "
                        f"{biome} has appeared"
                    ),
                    description=description,
                    color=color,
                )
            ],
        }

        return self._send_payload(
            payload,
            image=self._image(biome),
        )

    def send_unknown_biome(
        self,
        biome: str,
    ) -> WebhookResult:
        """
        Backup notification for a biome that is not registered
        in the application's BIOMES table.

        This intentionally does NOT use:
          - biome role mappings
          - @everyone
          - custom biome images
          - registered biome styling
          - profile notify_biomes filtering

        It reports the detected biome name and includes the
        configured Roblox private server link when available.
        """
        biome = str(biome).strip().upper()

        if not biome:
            return WebhookResult(
                False,
                error="Unknown biome name is empty",
            )

        description = (
            "Sober reported a biome that is not "
            "currently registered in Sol's RNG Core.\n\n"
            f"**Biome:** `{biome}`"
        )

        private_server_url = str(
            getattr(self.profile, "roblox_private_server_url", "") or ""
        ).strip()

        if private_server_url:
            description += (
                f"\n\n[🔗 **Join Server**]({private_server_url})"
            )

        payload = {
            "content": "",
            "allowed_mentions": {
                "parse": [],
                "roles": [],
                "users": [],
            },
            "embeds": [
                self._build_embed(
                    title="⚠ Unknown Biome Detected",
                    description=description,
                    color=0x5865F2,
                )
            ],
        }

        return self._send_payload(
            payload,
            image=None,
        )

    def send_biome_ended(
        self,
        biome: str,
        *,
        duration: str | None = None,
        details: str | None = None,
    ) -> WebhookResult:
        biome = biome.strip().upper()

        if biome not in BIOMES:
            return WebhookResult(
                False,
                error=f"Unknown biome {biome!r}",
            )

        if biome not in self.profile.notify_biomes:
            return WebhookResult(
                False,
                error=f"Biome {biome!r} disabled",
            )

        style = BIOME_STYLES.get(
            biome,
            DEFAULT_STYLE,
        )

        emoji = str(style["emoji"])
        color = int(style["color"])

        description = (
            f"Sol's RNG **{biome}** "
            "has ended."
        )

        if duration:
            description += (
                f"\nDuration: **{duration}**"
            )

        if details:
            description += f"\n{details}"

        mention, role_ids = self._role_mention(
            biome
        )

        payload = {
            "content": mention,
            "allowed_mentions": {
                "parse": (
                    ["everyone"]
                    if mention == "@everyone"
                    else []
                ),
                "roles": role_ids,
            },
            "embeds": [
                self._build_embed(
                    title=(
                        f"{emoji} "
                        f"{biome} has ended"
                    ),
                    description=description,
                    color=color,
                )
            ],
        }

        return self._send_payload(
            payload,
            image=None,
        )

    def send_started(self) -> WebhookResult:
        style = EVENT_STYLES["STARTED"]

        payload = {
            "content": "",
            "allowed_mentions": {
                "parse": [],
                "roles": [],
            },
            "embeds": [
                self._build_embed(
                    title=(
                        "▶ Sol's RNG Core "
                        "has started"
                    ),
                    description=(
                        "Sol's RNG Core is now "
                        "running and monitoring "
                        "the Sober log."
                    ),
                    color=int(style["color"]),
                )
            ],
        }

        return self._send_payload(payload)

    def send_stopped(self) -> WebhookResult:
        style = EVENT_STYLES["STOPPED"]

        payload = {
            "content": "",
            "allowed_mentions": {
                "parse": [],
                "roles": [],
            },
            "embeds": [
                self._build_embed(
                    title=(
                        "⏹ Sol's RNG Core "
                        "has stopped"
                    ),
                    description=(
                        "Sol's RNG Core has "
                        "stopped monitoring "
                        "the Sober log."
                    ),
                    color=int(style["color"]),
                )
            ],
        }

        return self._send_payload(payload)

    def test(self) -> WebhookResult:
        """Send a test notification only to this profile."""

        mention = ""

        # Test notifications never accidentally ping everyone.
        payload = {
            "content": mention,
            "allowed_mentions": {
                "parse": [],
                "roles": [],
            },
            "embeds": [
                self._build_embed(
                    title="🧪 Sol's RNG Core test",
                    description=(
                        "This is a test notification "
                        f"for webhook profile "
                        f"**{self.profile.name}**.\n\n"
                        "The selected webhook is "
                        "working correctly."
                    ),
                    color=0x5865F2,
                )
            ],
        }

        return self._send_payload(
            payload,
            require_enabled=False,
        )

    def send_biome(
        self,
        biome: str,
        *,
        duration: str | None = None,
        details: str | None = None,
    ) -> WebhookResult:
        if duration is not None:
            return self.send_biome_ended(
                biome,
                duration=duration,
                details=details,
            )

        return self.send_biome_appeared(
            biome,
            details=details,
        )
