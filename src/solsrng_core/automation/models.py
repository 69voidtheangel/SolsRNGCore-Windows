from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AutomationCoordinates:
    inventory: tuple[int, int] | None = None
    items: tuple[int, int] | None = None
    search_bar: tuple[int, int] | None = None
    first_slot: tuple[int, int] | None = None
    quantity: tuple[int, int] | None = None
    use_button: tuple[int, int] | None = None
    close_inventory: tuple[int, int] | None = None

    def complete(self) -> bool:
        return all(
            value is not None
            for value in (
                self.inventory,
                self.items,
                self.search_bar,
                self.first_slot,
                self.quantity,
                self.use_button,
                self.close_inventory,
            )
        )

    def missing(self) -> list[str]:
        names = [
            ("inventory", "Inventory"),
            ("items", "Items"),
            ("search_bar", "Search Bar"),
            ("first_slot", "First Slot"),
            ("quantity", "Quantity / One Item"),
            ("use_button", "Use Button"),
            ("close_inventory", "Close Inventory"),
        ]

        return [
            label
            for attribute, label in names
            if getattr(self, attribute) is None
        ]

    def to_dict(self) -> dict:
        def encode(value):
            return (
                list(value)
                if value is not None
                else None
            )

        return {
            "inventory": encode(self.inventory),
            "items": encode(self.items),
            "search_bar": encode(self.search_bar),
            "first_slot": encode(self.first_slot),
            "quantity": encode(self.quantity),
            "use_button": encode(self.use_button),
            "close_inventory": encode(self.close_inventory),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
    ) -> "AutomationCoordinates":
        if not isinstance(data, dict):
            data = {}

        def parse(value):
            if not value or len(value) != 2:
                return None

            return int(value[0]), int(value[1])

        return cls(
            inventory=parse(data.get("inventory")),
            items=parse(data.get("items")),
            search_bar=parse(data.get("search_bar")),
            first_slot=parse(data.get("first_slot")),
            quantity=parse(data.get("quantity")),
            use_button=parse(data.get("use_button")),
            close_inventory=parse(data.get("close_inventory")),
        )

    def copy(self) -> "AutomationCoordinates":
        return AutomationCoordinates.from_dict(
            self.to_dict()
        )


@dataclass
class AutomationItem:
    name: str
    search_text: str
    cooldown_seconds: float

    enabled: bool = True

    # Kept for backward compatibility with old automation.json
    # files. New automation uses AutomationSettings.coordinates.
    coordinates: AutomationCoordinates = field(
        default_factory=AutomationCoordinates
    )

    click_delay_seconds: float = 0.25
    post_use_delay_seconds: float = 1.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "search_text": self.search_text,
            "cooldown_seconds": self.cooldown_seconds,
            "enabled": self.enabled,
            "coordinates": self.coordinates.to_dict(),
            "click_delay_seconds": self.click_delay_seconds,
            "post_use_delay_seconds": self.post_use_delay_seconds,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
    ) -> "AutomationItem":
        if not isinstance(data, dict):
            data = {}

        return cls(
            name=str(
                data.get(
                    "name",
                    "Unnamed Item",
                )
            ),
            search_text=str(
                data.get(
                    "search_text",
                    data.get("name", ""),
                )
            ),
            cooldown_seconds=float(
                data.get(
                    "cooldown_seconds",
                    0.0,
                )
            ),
            enabled=bool(
                data.get(
                    "enabled",
                    True,
                )
            ),
            coordinates=AutomationCoordinates.from_dict(
                data.get(
                    "coordinates",
                    {},
                )
            ),
            click_delay_seconds=float(
                data.get(
                    "click_delay_seconds",
                    0.25,
                )
            ),
            post_use_delay_seconds=float(
                data.get(
                    "post_use_delay_seconds",
                    1.0,
                )
            ),
        )
