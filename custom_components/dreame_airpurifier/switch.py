"""Switch platform for Dreame Air Purifier."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .api import DreameAirPurifier
from .const import DOMAIN
from .entity import DreameEntity

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for p in data["purifiers"]:
        entities.extend([DreamePlayModeSwitch(data["coordinator"], p), DreameChildLockSwitch(data["coordinator"], p),
                         DreameVoiceInteractionSwitch(data["coordinator"], p), DreameKeypressToneSwitch(data["coordinator"], p)])
    async_add_entities(entities)

class DreameBaseSwitch(DreameEntity, SwitchEntity):
    def __init__(self, coordinator, purifier: DreameAirPurifier, key: str, name: str):
        super().__init__(coordinator, purifier, key, name)

class DreameChildLockSwitch(DreameBaseSwitch):
    _attr_icon = "mdi:lock"
    def __init__(self, c, p): super().__init__(c, p, "child_lock", "Child Lock")
    @property
    def is_on(self): return self._purifier.child_lock
    async def async_turn_on(self, **kwargs): await self.hass.async_add_executor_job(self._purifier.set_child_lock, True); await self.coordinator.async_request_refresh()
    async def async_turn_off(self, **kwargs): await self.hass.async_add_executor_job(self._purifier.set_child_lock, False); await self.coordinator.async_request_refresh()

class DreamePlayModeSwitch(DreameBaseSwitch):
    _attr_icon = "mdi:play-circle"
    def __init__(self, c, p): super().__init__(c, p, "play_mode", "Play Mode")
    @property
    def is_on(self): return self._purifier.play_mode
    async def async_turn_on(self, **kwargs): await self.hass.async_add_executor_job(self._purifier.set_play_mode, True); await self.coordinator.async_request_refresh()
    async def async_turn_off(self, **kwargs): await self.hass.async_add_executor_job(self._purifier.set_play_mode, False); await self.coordinator.async_request_refresh()

class DreameVoiceInteractionSwitch(DreameBaseSwitch):
    _attr_icon = "mdi:microphone"
    def __init__(self, c, p): super().__init__(c, p, "voice_interaction", "Voice Interaction")
    @property
    def is_on(self): return self._purifier.voice_interaction
    async def async_turn_on(self, **kwargs): await self.hass.async_add_executor_job(self._purifier.set_voice_interaction, True); await self.coordinator.async_request_refresh()
    async def async_turn_off(self, **kwargs): await self.hass.async_add_executor_job(self._purifier.set_voice_interaction, False); await self.coordinator.async_request_refresh()

class DreameKeypressToneSwitch(DreameBaseSwitch):
    _attr_icon = "mdi:volume-high"
    def __init__(self, c, p): super().__init__(c, p, "keypress_tone", "Keypress Tone")
    @property
    def is_on(self): return self._purifier.keypress_tone
    async def async_turn_on(self, **kwargs): await self.hass.async_add_executor_job(self._purifier.set_keypress_tone, True); await self.coordinator.async_request_refresh()
    async def async_turn_off(self, **kwargs): await self.hass.async_add_executor_job(self._purifier.set_keypress_tone, False); await self.coordinator.async_request_refresh()
