"""Number platform for Dreame Air Purifier."""
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .api import DreameAirPurifier, TIMER_MAX_HOURS, TIMER_MIN_HOURS
from .const import DOMAIN
from .entity import DreameEntity

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DreameTimerNumber(data["coordinator"], p) for p in data["purifiers"]])

class DreameTimerNumber(DreameEntity, NumberEntity):
    _attr_icon = "mdi:timer-outline"
    _attr_name = "Timer"
    _attr_native_min_value = TIMER_MIN_HOURS
    _attr_native_max_value = TIMER_MAX_HOURS
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    def __init__(self, coordinator, purifier: DreameAirPurifier):
        super().__init__(coordinator, purifier, "timer", "Timer")
    @property
    def native_value(self): return self._purifier.timer_hours
    async def async_set_native_value(self, value: float) -> None:
        await self.hass.async_add_executor_job(self._purifier.set_timer, round(value))
        await self.coordinator.async_request_refresh()
