"""Dreame Air Purifier Cloud API Client."""
import hashlib
import json
import logging
import requests
import time

_LOGGER = logging.getLogger(__name__)

DREAME_SALT = "RAylYC%fmSKp7%Tq"
DREAME_USER_AGENT = "Dreame_Smarthome/2.1.9 (iPhone; iOS 18.4.1; Scale/3.00)"
DREAME_AUTH_BASIC = "Basic ZHJlYW1lX2FwcHYxOkFQXmR2QHpAU1FZVnhOODg="
DREAME_TENANT_ID = "000000"
DREAME_RLC = "1c80b3787b2266776bcdc481f37d8fa42ba10a30af81a6df-1"
FIRMWARE_VERSION_KEYS = (
    "firmwareVersion",
    "firmware_version",
    "fwVersion",
    "fw_version",
)

# === MiOT Property Map for dreame.airp.u2507 (Dreame AP10) ===
# Verified by live testing and Dreame-AP10-API-Analysis.md.

# siid 2: Air Purifier Control
PROP_POWER = {"siid": 2, "piid": 1}  # int: 1=on, 2=standby/off
PROP_MODE = {"siid": 2, "piid": 3}  # int: 0=AI, 1=Strong, 2=Sleep, 3=Custom, 4=Pet
PROP_FAN_SPEED = {"siid": 2, "piid": 4}  # int: 1-5 fan speed level
PROP_VOICE_INTERACTION_VOLUME = {"siid": 2, "piid": 5}  # int: 80/90/100
PROP_LIGHT_CONTROL = {"siid": 2, "piid": 6}  # int: -1=off, 0=blue, 1=orange, 2=green
PROP_KEYPRESS_TONE = {"siid": 2, "piid": 7}  # int: 0=off, 1=on

# siid 3: Environment Sensors
PROP_AQ_LEVEL = {"siid": 3, "piid": 4}
PROP_PM25 = {"siid": 3, "piid": 5}

# siid 4: Filter
PROP_FILTER_LIFE = {"siid": 4, "piid": 1}
PROP_FILTER_DAYS_LEFT = {"siid": 4, "piid": 2}
PROP_FILTER_USED = {"siid": 4, "piid": 3}

# siid 6: Device Settings
PROP_DEVICE_LOCATION = {"siid": 6, "piid": 3}
PROP_CHILD_LOCK = {"siid": 6, "piid": 5}
PROP_PLAY_MODE = {"siid": 6, "piid": 6}
PROP_VOICE_INTERACTION = {"siid": 6, "piid": 7}
PROP_TIMER = {"siid": 6, "piid": 8}

# Poll batches (small to avoid timeout)
POLL_BATCHES = [
    [
        PROP_POWER,
        PROP_MODE,
        PROP_FAN_SPEED,
        PROP_VOICE_INTERACTION_VOLUME,
        PROP_LIGHT_CONTROL,
        PROP_KEYPRESS_TONE,
    ],
    [PROP_AQ_LEVEL, PROP_PM25],
    [PROP_FILTER_LIFE, PROP_FILTER_DAYS_LEFT, PROP_FILTER_USED],
    [PROP_DEVICE_LOCATION, PROP_CHILD_LOCK, PROP_PLAY_MODE, PROP_VOICE_INTERACTION, PROP_TIMER],
]

# Mode mapping (verified)
MODE_AI_PURIFY = 0
MODE_STRONG_PURIFICATION = 1
MODE_SLEEP_PURIFICATION = 2
MODE_CUSTOM = 3
MODE_PET_PURIFY = 4

MODE_NAMES = {
    MODE_AI_PURIFY: "AI Purify",
    MODE_STRONG_PURIFICATION: "Strong Purification",
    MODE_SLEEP_PURIFICATION: "Sleep Purification",
    MODE_CUSTOM: "Custom Mode",
    MODE_PET_PURIFY: "Pet Purify",
}
MODE_NAME_TO_VALUE = {v: k for k, v in MODE_NAMES.items()}

LIGHT_CONTROL_OPTIONS = {
    "Off": -1,
    "Blue": 0,
    "Orange": 1,
    "Green": 2,
}
LIGHT_CONTROL_VALUE_TO_OPTION = {v: k for k, v in LIGHT_CONTROL_OPTIONS.items()}

VOICE_INTERACTION_VOLUME_OPTIONS = {
    "Minimum": 80,
    "Moderate": 90,
    "High": 100,
}
VOICE_INTERACTION_VOLUME_VALUE_TO_OPTION = {
    v: k for k, v in VOICE_INTERACTION_VOLUME_OPTIONS.items()
}

TIMER_MIN_HOURS = 0
TIMER_MAX_HOURS = 12

# Power: MUST use toggle action (set_properties times out on siid 2 piid 1)
ACTION_TOGGLE_POWER = {"siid": 2, "aiid": 3}


def _as_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _as_int(value, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value, default: bool = False) -> bool:
    parsed = _as_int(value)
    if parsed is not None:
        return parsed != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "on", "yes"}:
            return True
        if lowered in {"false", "off", "no"}:
            return False
    return default


def _extract_firmware_version(device_info: dict) -> str | None:
    for source in (device_info, _as_dict(device_info.get("deviceInfo"))):
        for key in FIRMWARE_VERSION_KEYS:
            version = source.get(key)
            if version not in (None, ""):
                return str(version)
    return None


class DreameCloudAPI:
    """Client for the Dreame Cloud API."""

    def __init__(self, username: str, password: str, country: str = "us"):
        self._username = username
        self._password = password
        self._country = country
        self._session = requests.Session()
        self._access_token = None
        self._refresh_token = None
        self._uid = None
        self._tenant_id = DREAME_TENANT_ID
        self._token_expire = None

    @property
    def api_url(self) -> str:
        return f"https://{self._country}.iot.dreame.tech:13267"

    @property
    def logged_in(self) -> bool:
        return self._access_token is not None

    def login(self) -> bool:
        url = f"{self.api_url}/dreame-auth/oauth/token"
        pw_hash = hashlib.md5((self._password + DREAME_SALT).encode("utf-8")).hexdigest()
        data = f"platform=IOS&scope=all&grant_type=password&username={self._username}&password={pw_hash}&type=account"
        headers = {
            "User-Agent": DREAME_USER_AGENT,
            "Authorization": DREAME_AUTH_BASIC,
            "Tenant-Id": DREAME_TENANT_ID,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
        }
        if self._country == "cn":
            headers["Dreame-Rlc"] = DREAME_RLC
        try:
            response = self._session.post(url, headers=headers, data=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if "access_token" in result:
                    self._access_token = result["access_token"]
                    self._refresh_token = result.get("refresh_token")
                    self._uid = result.get("uid")
                    self._tenant_id = result.get("tenant_id", DREAME_TENANT_ID)
                    self._token_expire = time.time() + result.get("expires_in", 3600) - 120
                    return True
                _LOGGER.error("Login failed: %s", result)
            else:
                _LOGGER.error("Login failed (HTTP %s): %s", response.status_code, response.text)
        except Exception as ex:
            _LOGGER.error("Login error: %s", ex)
        return False

    def _refresh_login(self) -> bool:
        if self._refresh_token and self._token_expire and time.time() > self._token_expire:
            url = f"{self.api_url}/dreame-auth/oauth/token"
            data = f"platform=IOS&scope=all&grant_type=refresh_token&refresh_token={self._refresh_token}"
            headers = {
                "User-Agent": DREAME_USER_AGENT,
                "Authorization": DREAME_AUTH_BASIC,
                "Tenant-Id": self._tenant_id,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            try:
                r = self._session.post(url, headers=headers, data=data, timeout=10)
                if r.status_code == 200:
                    result = r.json()
                    if "access_token" in result:
                        self._access_token = result["access_token"]
                        self._refresh_token = result.get("refresh_token", self._refresh_token)
                        self._token_expire = time.time() + result.get("expires_in", 3600) - 120
                        return True
            except Exception as ex:
                _LOGGER.warning("Token refresh failed: %s", ex)
            return self.login()
        return True

    def _auth_headers(self) -> dict:
        return {
            "User-Agent": DREAME_USER_AGENT,
            "Authorization": DREAME_AUTH_BASIC,
            "Tenant-Id": self._tenant_id,
            "Dreame-Auth": self._access_token,
            "Content-Type": "application/json",
            "Accept": "*/*",
        }

    def get_devices(self) -> list | None:
        if not self._refresh_login():
            return None
        url = f"{self.api_url}/dreame-user-iot/iotuserbind/device/listV2"
        try:
            r = self._session.post(url, headers=self._auth_headers(), json={}, timeout=10)
            if r.status_code == 200:
                result = r.json()
                if result.get("code") == 0 and "data" in result:
                    data = result.get("data") or {}
                    page = data.get("page") or {}
                    records = page.get("records")
                    if isinstance(records, list):
                        return records
                    _LOGGER.error("Unexpected device list response: %s", result)
        except Exception as ex:
            _LOGGER.error("Failed to get devices: %s", ex)
        return None

    def get_purifiers(self) -> list:
        devices = self.get_devices()
        if not devices:
            return []
        return [d for d in devices if ".airp." in str(d.get("model") or "")]

    def send_command(self, did: str, method: str, params, host: str = None, retry: bool = True):
        if not self._refresh_login():
            return None
        host_prefix = f"-{host.split('.')[0]}" if host else ""
        url = f"{self.api_url}/dreame-iot-com{host_prefix}/device/sendCommand"
        payload = {
            "did": str(did),
            "id": 1,
            "data": {"did": str(did), "id": 1, "method": method, "params": params},
        }
        try:
            r = self._session.post(url, headers=self._auth_headers(), json=payload, timeout=10)
            if r.status_code == 200:
                result = r.json()
                if result.get("code") == 0:
                    if result.get("data") and "result" in result["data"]:
                        return result["data"]["result"]
                    if result.get("success"):
                        return {"code": 0}
            elif r.status_code == 401:
                if retry and self.login():
                    return self.send_command(did, method, params, host, retry=False)
        except Exception as ex:
            _LOGGER.error("Command failed: %s", ex)
        return None

    def get_properties(self, did: str, properties: list, host: str = None) -> dict:
        params = [{"did": str(did), "siid": p["siid"], "piid": p["piid"]} for p in properties]
        result = self.send_command(did, "get_properties", params, host)
        values = {}
        if result and isinstance(result, list):
            for prop in result:
                if prop.get("code", -1) == 0:
                    values[(prop["siid"], prop["piid"])] = prop.get("value")
        return values

    def set_property(self, did: str, siid: int, piid: int, value, host: str = None) -> bool:
        result = self.send_command(
            did,
            "set_properties",
            [{"did": str(did), "siid": siid, "piid": piid, "value": value}],
            host,
        )
        if result and isinstance(result, list) and len(result) > 0:
            return result[0].get("code", -1) == 0
        if result and isinstance(result, dict):
            return result.get("code", -1) == 0
        return False

    def call_action(self, did: str, siid: int, aiid: int, params: list = None, host: str = None) -> bool:
        result = self.send_command(
            did,
            "action",
            {"did": str(did), "siid": siid, "aiid": aiid, "in": params or []},
            host,
        )
        if result:
            return result.get("code", -1) == 0 if isinstance(result, dict) else True
        return False


class DreameAirPurifier:
    """Represents a single Dreame Air Purifier device."""

    def __init__(self, api: DreameCloudAPI, device_info: dict):
        self._api = api
        device_details = _as_dict(device_info.get("deviceInfo"))
        self._did = str(device_info["did"])
        self._host = device_info.get("bindDomain")
        self._model = device_info.get("model", "unknown")
        self._mac = device_info.get("mac", "")
        self._name = device_info.get("customName") or device_details.get("displayName", "Dreame Air Purifier")
        self._firmware_version = _extract_firmware_version(device_info)
        self._power = False
        self._mode = MODE_AI_PURIFY
        self._fan_speed = 0
        self._voice_interaction_volume = 80
        self._light_control = -1
        self._keypress_tone = False
        self._pm25 = 0
        self._aq_level = 0
        self._filter_life = 100
        self._filter_days_left = 365
        self._filter_used = 0
        self._device_location = None
        self._child_lock = False
        self._play_mode = False
        self._voice_interaction = False
        self._timer_hours = 0
        self._available = True

    @property
    def unique_id(self): return self._mac.replace(":", "").lower() or self._did
    @property
    def name(self): return self._name
    @property
    def model(self): return self._model
    @property
    def device_id(self): return self._did
    @property
    def mac(self): return self._mac
    @property
    def firmware_version(self): return self._firmware_version
    @property
    def available(self): return self._available
    @property
    def is_on(self):
        """Device is 'on' unless in sleep purification at speed 1."""
        if not self._power:
            return False
        if self._mode == MODE_SLEEP_PURIFICATION and self._fan_speed <= 1:
            return False
        return True
    @property
    def mode(self): return MODE_NAMES.get(self._mode, f"Unknown ({self._mode})")
    @property
    def mode_value(self): return self._mode
    @property
    def fan_speed(self): return self._fan_speed
    @property
    def fan_speed_percent(self): return max(0, self._fan_speed * 20) if self._fan_speed > 0 else 0
    @property
    def light_control(self): return self._light_control
    @property
    def light_control_option(self): return LIGHT_CONTROL_VALUE_TO_OPTION.get(self._light_control)
    @property
    def voice_interaction_volume(self): return self._voice_interaction_volume
    @property
    def voice_interaction_volume_option(self): return VOICE_INTERACTION_VOLUME_VALUE_TO_OPTION.get(self._voice_interaction_volume)
    @property
    def keypress_tone(self): return self._keypress_tone
    @property
    def pm25(self): return self._pm25
    @property
    def air_quality_level(self): return self._aq_level
    @property
    def filter_life(self): return self._filter_life
    @property
    def filter_days_left(self): return self._filter_days_left
    @property
    def filter_hours_used(self): return self._filter_used
    @property
    def device_location(self): return self._device_location
    @property
    def child_lock(self): return self._child_lock
    @property
    def play_mode(self): return self._play_mode
    @property
    def voice_interaction(self): return self._voice_interaction
    @property
    def timer_hours(self): return self._timer_hours

    def update(self) -> bool:
        all_values = {}
        for batch in POLL_BATCHES:
            values = self._api.get_properties(self._did, batch, self._host)
            if values:
                all_values.update(values)
        if not all_values:
            self._available = False
            return False
        self._available = True
        power = _as_int(all_values.get((2, 1)))
        if power is not None:
            self._power = power == 1
        self._mode = _as_int(all_values.get((2, 3)), self._mode)
        self._fan_speed = _as_int(all_values.get((2, 4)), self._fan_speed)
        self._voice_interaction_volume = _as_int(all_values.get((2, 5)), self._voice_interaction_volume)
        self._light_control = _as_int(all_values.get((2, 6)), self._light_control)
        self._keypress_tone = _as_bool(all_values.get((2, 7)), self._keypress_tone)
        self._aq_level = _as_int(all_values.get((3, 4)), self._aq_level)
        self._pm25 = _as_int(all_values.get((3, 5)), self._pm25)
        self._filter_life = _as_int(all_values.get((4, 1)), self._filter_life)
        self._filter_days_left = _as_int(all_values.get((4, 2)), self._filter_days_left)
        self._filter_used = _as_int(all_values.get((4, 3)), self._filter_used)
        self._device_location = all_values.get((6, 3), self._device_location)
        self._child_lock = _as_bool(all_values.get((6, 5)), self._child_lock)
        self._play_mode = _as_bool(all_values.get((6, 6)), self._play_mode)
        self._voice_interaction = _as_bool(all_values.get((6, 7)), self._voice_interaction)
        self._timer_hours = _as_int(all_values.get((6, 8)), self._timer_hours)
        return True

    def toggle_power(self) -> bool:
        return self._api.call_action(self._did, ACTION_TOGGLE_POWER["siid"], ACTION_TOGGLE_POWER["aiid"], host=self._host)

    def turn_on(self) -> bool:
        """Turn on by restoring AI Purify mode."""
        if self._power:
            return self.set_mode(MODE_AI_PURIFY)
        self.toggle_power()
        return self.set_mode(MODE_AI_PURIFY)

    def turn_off(self) -> bool:
        """Turn off by switching to Sleep Purification at minimum speed."""
        self.set_mode(MODE_SLEEP_PURIFICATION)
        return self.set_fan_speed(1)

    def set_mode(self, mode: int) -> bool:
        return self._api.set_property(self._did, 2, 3, mode, self._host)

    def set_fan_speed(self, speed: int) -> bool:
        speed = _as_int(speed, self._fan_speed or 1)
        return self._api.set_property(self._did, 2, 4, max(1, min(5, speed)), self._host)

    def set_fan_speed_percent(self, percent: int) -> bool:
        if percent <= 0:
            return self.turn_off()
        if self._mode != MODE_CUSTOM and not self.set_mode(MODE_CUSTOM):
            return False
        return self.set_fan_speed(max(1, min(5, round(percent / 20))))

    def set_light_control(self, value: int) -> bool:
        if value not in LIGHT_CONTROL_VALUE_TO_OPTION:
            return False
        return self._api.set_property(self._did, 2, 6, value, self._host)

    def set_voice_interaction_volume(self, value: int) -> bool:
        if value not in VOICE_INTERACTION_VOLUME_VALUE_TO_OPTION:
            return False
        return self._api.set_property(self._did, 2, 5, value, self._host)

    def set_keypress_tone(self, enabled: bool) -> bool:
        return self._api.set_property(self._did, 2, 7, 1 if enabled else 0, self._host)

    def set_child_lock(self, enabled: bool) -> bool:
        return self._api.set_property(self._did, 6, 5, 1 if enabled else 0, self._host)

    def set_play_mode(self, enabled: bool) -> bool:
        return self._api.set_property(self._did, 6, 6, 1 if enabled else 0, self._host)

    def set_voice_interaction(self, enabled: bool) -> bool:
        return self._api.set_property(self._did, 6, 7, 1 if enabled else 0, self._host)

    def set_timer(self, hours: int) -> bool:
        try:
            hours = int(hours)
        except (TypeError, ValueError):
            return False
        hours = max(TIMER_MIN_HOURS, min(TIMER_MAX_HOURS, hours))
        return self._api.set_property(self._did, 6, 8, hours, self._host)

    def reset_filter(self) -> bool:
        return self._api.call_action(self._did, 4, 1, host=self._host)
