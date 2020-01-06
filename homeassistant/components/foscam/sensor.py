"""Support for Buienradar.nl weather service."""
from datetime import timedelta
import logging

from libpyfoscam import FoscamCamera
from libpyfoscam.foscam import (
    FOSCAM_SUCCESS as FOSCAM_SUCCESS,
    ERROR_FOSCAM_FORMAT as FOSCAM_ERROR_FORMAT,
    ERROR_FOSCAM_AUTH as FOSCAM_ERROR_AUTH,
    ERROR_FOSCAM_CMD as FOSCAM_ERROR_CMD,
    ERROR_FOSCAM_EXE as FOSCAM_ERROR_EXE,
    ERROR_FOSCAM_TIMEOUT as FOSCAM_ERROR_TIMEOUT,
    ERROR_FOSCAM_UNAVAILABLE as FOSCAM_ERROR_UNAVAILABLE
)
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import (
    DATA as FOSCAM_DATA,
    DOMAIN as FOSCAM_DOMAIN,
    ENTITIES as FOSCAM_ENTITIES,
    CONF_IP,
    DEFAULT_NAME,
    DEFAULT_PORT
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

FOSCAM_ALARM_MAPPING = {
    '0': 'Disabled',
    '1': 'No alarm',
    '2': 'Detect alarm'
}

FOSCAM_RECORD_MAPPING = {
    '0': 'Not in recording',
    '1': 'Recording'
}

FOSCAM_SDCARD_MAPPING = {
    '0': 'No SD card',
    '1': 'SD card ok',
    '2': 'SD card read only'
}

FOSCAM_WIFI_MAPPING = {
    '0': 'No wifi connected',
    '1': 'Connected',
}

FOSCAM_INFRALED_MAPPING = {
    '0': 'OFF',
    '1': 'ON',
}

# Supported sensor types:
# Key: ['label', unit, icon]
SENSOR_TYPES = {
    "motionDetectAlarm": ["Motion detect alarm", FOSCAM_ALARM_MAPPING, 'mdi:walk'],
    "soundAlarm": ["Sound alarm", FOSCAM_ALARM_MAPPING, 'mdi-speaker'],
    "record": ["Record", FOSCAM_RECORD_MAPPING, 'mdi:record-rec'],
    "sdState": ["SD card state", FOSCAM_SDCARD_MAPPING, None],
    "sdFreeSpace": ["SD free space", None, None],
    "sdTotalSpace": ["SD total space", None, None],
    "isWifiConnected": ["Wifi connected", FOSCAM_WIFI_MAPPING, 'mdi:access-point'],
    "wifiConnectedAP": ["Wifi accesspoint", None, 'mdi:access-point'],
    "infraLedState": ["Infraled", FOSCAM_INFRALED_MAPPING, 'mdi:led-outline']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a Foscam IP Camera."""

    camera = FoscamCamera(
        config[CONF_IP],
        config[CONF_PORT],
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        verbose=True,
    )

    dev = []
    foscam_data = HassFoscamData(hass, camera)
    for sensor_type in SENSOR_TYPES:
        dev.append(
            HassFoscamSensor(
                foscam_data,
                sensor_type,
                config[CONF_NAME],
            )
        )
        _LOGGER.debug("Added sensor %s", sensor_type)

    async_add_entities(dev, True)

class HassFoscamSensor(Entity):
    """An implementation of a Foscam IP sensor."""

    def __init__(self, foscam_data, sensor_type, name):
        """Initialize a Foscam camera."""
        super().__init__()

        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._foscam_data = foscam_data
        self._name = f"{name} {SENSOR_TYPES[sensor_type][0]}"
        self._data = {}
        self.type = sensor_type        

    async def async_update(self):
        """Load the sensor with relevant data."""
        await self._foscam_data.async_update()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return SENSOR_TYPES[self.type][2]

    @property
    def state(self):
        """Return the state of the device."""
        try:
            data = self._foscam_data.data[self.type]
            if isinstance(self._unit_of_measurement, dict):
                data = self._unit_of_measurement[data]
        except (KeyError, TypeError):
            data = None
        return data

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        if isinstance(self._unit_of_measurement, dict):
            return None
        return self._unit_of_measurement

class HassFoscamData(Entity):
    """Get data from Foscam IP camera."""

    def __init__(self, hass, camera):
        """Initialize the data object."""
        super().__init__()

        self._camera = camera
        self.hass = hass
        self.data = {}

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        """Get the data from Foscam IP API."""
        ret, response = await self.hass.async_add_executor_job(self._camera.get_dev_state)

        _LOGGER.debug("Get dev state from Foscam IP camera. Ret: %s, Response: %s", ret, response)

        if ret == FOSCAM_SUCCESS:
            self.data = response
            return True

        reason = 'Unknown'
        if ret == FOSCAM_ERROR_AUTH:
            reason = 'Failed authentication'
        elif ret == FOSCAM_ERROR_CMD:
            reason = 'Access deny. May the cmd is not supported.'
        elif ret == FOSCAM_ERROR_EXE:
            reason = 'CGI execute fail'
        elif ret == FOSCAM_ERROR_FORMAT:
            reason = 'Invalid format'
        elif ret == FOSCAM_ERROR_TIMEOUT:
            reason = 'Timeout'
        elif ret == FOSCAM_ERROR_UNAVAILABLE:
            reason = 'Camera not available'
        _LOGGER.error('Error while get dev_state from Foscam IP camera. Reason: %s, Response: %s', reason, response)
        return False
