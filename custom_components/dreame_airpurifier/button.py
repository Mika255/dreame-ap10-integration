"""Button platform for Dreame Air Purifier."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .api import DreameAirPurifier
from .const import DOMAIN
from .entity import DreameEntity

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DreameFilterResetButton(data["coordinator"], p) for p in data["purifiers"]])

class DreameFilterResetButton(DreameEntity, ButtonEntity):
    _attr_icon = "mdi:filter-sync"
    _attr_name = "Filter Reset"
    def __init__(self, coordinator, purifier: DreameAirPurifier):
        super().__init__(coordinator, purifier, "filter_reset", "Filter Reset")
    async def async_press(self) -> None:
        await self.hass.async_add_executor_job(self._purifier.reset_filter)
        await self.coordinator.async_request_refresh()
