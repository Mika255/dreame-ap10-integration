"""Shared entity helpers for Dreame Air Purifier."""
from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import DreameAirPurifier
from .const import DOMAIN


def dreame_device_info(purifier: DreameAirPurifier) -> dict[str, Any]:
    """Return Home Assistant device metadata for a purifier."""
    return {
        "identifiers": {(DOMAIN, purifier.unique_id)},
        "name": purifier.name,
        "manufacturer": "Dreame",
        "model": purifier.model,
        "sw_version": purifier.firmware_version,
    }


class DreameEntity(CoordinatorEntity):
    """Base entity with shared Dreame device metadata."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        purifier: DreameAirPurifier,
        key: str,
        name: str | None,
    ) -> None:
        super().__init__(coordinator)
        self._purifier = purifier
        self._attr_unique_id = f"{purifier.unique_id}_{key}"
        self._attr_name = name

    @property
    def device_info(self):
        return dreame_device_info(self._purifier)

    @property
    def available(self):
        return self._purifier.available
