"""Shared entity helpers for Dreame Air Purifier."""
from typing import Any

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
