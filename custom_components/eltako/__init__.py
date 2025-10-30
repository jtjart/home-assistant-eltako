"""The Eltako integration."""

import logging

from eltakobus.util import AddressExpression

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import config_helpers
from .const import (
    BAUD_RATE_DEVICE_TYPE_MAPPING,
    CONF_BASE_ID,
    CONF_DEVICE_TYPE,
    CONF_ENABLE_TEACH_IN_BUTTONS,
    CONF_GATEWAY_ADDRESS,
    CONF_GATEWAY_AUTO_RECONNECT,
    CONF_GATEWAY_DESCRIPTION,
    CONF_GATEWAY_MESSAGE_DELAY,
    CONF_GATEWAY_PORT,
    CONF_SERIAL_PATH,
    DATA_ELTAKO,
    DATA_ENTITIES,
    DOMAIN,
    ELTAKO_CONFIG,
    PLATFORMS,
    GatewayDeviceType,
)
from .gateway import EnOceanGateway
from .schema import CONFIG_SCHEMA

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Eltako component."""
    return True


def get_gateway_from_hass(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> EnOceanGateway:
    """Retrieve the EnOcean gateway instance from Home Assistant data."""
    return hass.data[DATA_ELTAKO][config_entry.data[CONF_GATEWAY_DESCRIPTION]]


def _set_gateway_to_hass(hass: HomeAssistant, gateway_entity: EnOceanGateway) -> None:
    hass.data[DATA_ELTAKO][gateway_entity.dev_name] = gateway_entity


def get_device_config_for_gateway(
    hass: HomeAssistant, gateway: EnOceanGateway
) -> ConfigType:
    """Retrieve the device configuration for a specific EnOcean gateway."""
    return config_helpers.get_device_config(
        hass.data[DATA_ELTAKO][ELTAKO_CONFIG], gateway.dev_id
    )


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up an Eltako gateway for the given entry."""
    _LOGGER.info("Start gateway setup")

    # Check domain
    if config_entry.domain != DOMAIN:
        _LOGGER.warning(
            "Ooops, received configuration entry of wrong domain '%s' (expected: '%s')",
            config_entry.domain,
            DOMAIN,
        )
        return

    # Read the config
    config = await config_helpers.async_get_home_assistant_config(hass, CONFIG_SCHEMA)

    # Check if gateway ids are unique
    if not config_helpers.config_check_gateway(config):
        raise Exception("Gateway Ids are not unique.")

    # set config for global access
    eltako_data = hass.data.setdefault(DATA_ELTAKO, {})
    eltako_data[ELTAKO_CONFIG] = config
    # print whole eltako configuration
    _LOGGER.debug("config: %s", config)

    general_settings = config_helpers.get_general_settings_from_configuration(hass)
    # Initialise the gateway
    # get base_id from user input
    if CONF_GATEWAY_DESCRIPTION not in config_entry.data.keys():
        _LOGGER.warning(
            "Ooops, device information for gateway is not available. Try to delete and recreate the gateway"
        )
        return
    gateway_description = config_entry.data[CONF_GATEWAY_DESCRIPTION]  # from user input
    if not ("(" in gateway_description and ")" in gateway_description):
        _LOGGER.warning(
            "Ooops, no base id of gateway available. Try to delete and recreate the gateway"
        )
        return
    gateway_id = config_helpers.get_id_from_name(gateway_description)

    # get home assistant configuration section matching base_id
    gateway_config = await config_helpers.async_find_gateway_config_by_id(
        gateway_id, hass, CONFIG_SCHEMA
    )
    if not gateway_config:
        _LOGGER.warning(
            "Ooops, no gateway configuration found in '/homeassistant/configuration.yaml'"
        )
        return

    # get serial path info
    if CONF_SERIAL_PATH not in config_entry.data.keys():
        _LOGGER.warning("Ooops, no information about serial path available for gateway")
        return
    gateway_serial_path = config_entry.data[CONF_SERIAL_PATH]

    # only transceiver can send teach-in telegrams
    gateway_device_type = GatewayDeviceType.find(
        gateway_config[CONF_DEVICE_TYPE]
    )  # from configuration
    if gateway_device_type is None:
        _LOGGER.error(
            "USB device %s is not supported", gateway_config[CONF_DEVICE_TYPE]
        )
        return False
    if gateway_device_type == GatewayDeviceType.LAN:
        if gateway_config.get(CONF_GATEWAY_ADDRESS, None) is None:
            raise Exception(
                f"Missing field '{CONF_GATEWAY_ADDRESS}' for LAN Gateway (id: {gateway_id})"
            )

    general_settings[CONF_ENABLE_TEACH_IN_BUTTONS] = (
        True  # GatewayDeviceType.is_transceiver(gateway_device_type) # should only be disabled for decentral gateways
    )

    _LOGGER.info("Initializes Gateway Device '%s'", gateway_description)
    gateway_name = gateway_config.get(CONF_NAME, None)  # from configuration
    baud_rate = BAUD_RATE_DEVICE_TYPE_MAPPING[gateway_device_type]
    port = gateway_config.get(CONF_GATEWAY_PORT, 5100)
    auto_reconnect = gateway_config.get(CONF_GATEWAY_AUTO_RECONNECT, True)
    gateway_base_id = AddressExpression.parse(gateway_config[CONF_BASE_ID])
    message_delay = gateway_config.get(CONF_GATEWAY_MESSAGE_DELAY, None)
    _LOGGER.debug(
        "id: %s, device type: %s, serial path: %s, baud rate: %s, base id: %s",
        gateway_id,
        gateway_device_type,
        gateway_serial_path,
        baud_rate,
        gateway_base_id,
    )
    usb_gateway = EnOceanGateway(
        general_settings,
        hass,
        gateway_id,
        gateway_device_type,
        gateway_serial_path,
        baud_rate,
        port,
        gateway_base_id,
        gateway_name,
        auto_reconnect,
        message_delay,
        config_entry,
    )

    await usb_gateway.async_setup()
    _set_gateway_to_hass(hass, usb_gateway)

    hass.data[DATA_ELTAKO][DATA_ENTITIES] = {}
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Eltako config entry."""

    gateway = get_gateway_from_hass(hass, config_entry)

    _LOGGER.info("Unload %s and all its supported devices!", gateway.dev_name)
    gateway.unload()
    del hass.data[DATA_ELTAKO][gateway.dev_name]

    return True
