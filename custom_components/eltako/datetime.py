"""Support for Eltako datetime entities."""

from datetime import datetime
import logging

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import get_gateway_from_hass
from .const import DOMAIN, MANUFACTURER
from .device import (
    EltakoEntity,
    log_entities_to_be_added,
    validate_actuators_dev_and_sender_id,
)
from .gateway import EnOceanGateway

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an Eltako buttons."""
    gateway: EnOceanGateway = get_gateway_from_hass(hass, config_entry)

    entities: list[EltakoEntity] = []

    platform = Platform.DATE

    # last received message timestamp
    entities.append(GatewayLastReceivedMessage(platform, gateway))

    validate_actuators_dev_and_sender_id(entities)
    log_entities_to_be_added(entities, platform)
    async_add_entities(entities)


class GatewayLastReceivedMessage(EltakoEntity, DateTimeEntity):
    """Protocols last time when message received."""

    def __init__(self, platform: str, gateway: EnOceanGateway) -> None:
        """Initialize the datetime entity for storing the last time a gateway message was received."""
        self.entity_description = EntityDescription(
            key="Last Message Received",
            name="Last Message Received",
            icon="mdi:button-cursor",
            device_class=SensorDeviceClass.DATE,
        )
        self.gateway.set_last_message_received_handler(self.set_value)

        super().__init__(platform, gateway, gateway.base_id, gateway.dev_name, None)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.gateway.serial_path)},
            name=self.gateway.dev_name,
            manufacturer=MANUFACTURER,
            model=self.gateway.model,
            via_device=(DOMAIN, self.gateway.serial_path),
        )

    def set_value(self, value: datetime) -> None:
        """Update the current value."""

        self.native_value = value
        self.schedule_update_ha_state()
