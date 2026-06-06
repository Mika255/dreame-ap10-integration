"""Select platform for Dreame Air Purifier."""
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .api import DreameAirPurifier, LIGHT_CONTROL_OPTIONS, VOICE_INTERACTION_VOLUME_OPTIONS
from .const import DOMAIN
from .entity import DreameEntity

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for p in data["purifiers"]:
        entities.extend([DreameLightControlSelect(data["coordinator"], p), DreameVoiceInteractionVolumeSelect(data["coordinator"], p)])
    async_add_entities(entities)

class DreameBaseSelect(DreameEntity, SelectEntity):
    def __init__(self, coordinator, purifier: DreameAirPurifier, key: str, name: str):
        super().__init__(coordinator, purifier, key, name)

class DreameLightControlSelect(DreameBaseSelect):
    _attr_icon = "mdi:palette"
    _attr_options = list(LIGHT_CONTROL_OPTIONS)
    def __init__(self, c, p): super().__init__(c, p, "light_control", "Light Control")
    @property
    def current_option(self): return self._purifier.light_control_option
    async def async_select_option(self, option: str) -> None:
        await self.hass.async_add_executor_job(self._purifier.set_light_control, LIGHT_CONTROL_OPTIONS[option])
        await self.coordinator.async_request_refresh()

class DreameVoiceInteractionVolumeSelect(DreameBaseSelect):
    _attr_icon = "mdi:volume-high"
    _attr_options = list(VOICE_INTERACTION_VOLUME_OPTIONS)
    def __init__(self, c, p): super().__init__(c, p, "voice_interaction_volume", "Voice Interaction Volume")
    @property
    def current_option(self): return self._purifier.voice_interaction_volume_option
    async def async_select_option(self, option: str) -> None:
        await self.hass.async_add_executor_job(self._purifier.set_voice_interaction_volume, VOICE_INTERACTION_VOLUME_OPTIONS[option])
        await self.coordinator.async_request_refresh()
