"""Сенсоры температуры для интеграции Кондиционер GoldStar GSAC/GSACI."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import GSACBaseEntity
from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    MQTT_TOPICS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Настройка сенсоров температуры из конфигурационной записи."""
    
    device_id = config_entry.data.get(CONF_DEVICE_ID)
    
    topics = {}
    for key, template in MQTT_TOPICS.items():
        topics[key] = template.format(device_id=device_id)
    
    _LOGGER.info(
        "Настраиваем сенсоры температуры для устройства: %s",
        device_id
    )
    
    sensors = [
        TemperatureSensor(
            hass=hass,
            device_id=device_id,
            topic=topics["temp_out"],
            name="Текущая температура в комнате",
            sensor_type="current_temperature",
            icon="mdi:thermometer",
            entry_id=config_entry.entry_id,
            is_target_temp=False
        ),
        TemperatureSensor(
            hass=hass,
            device_id=device_id,
            topic=topics["temp_comfort_out"],
            name="Целевая температура кондиционера",
            sensor_type="target_temperature",
            icon="mdi:thermometer-check",
            entry_id=config_entry.entry_id,
            is_target_temp=True
        )
    ]
    
    async_add_entities(sensors)


class TemperatureSensor(GSACBaseEntity, SensorEntity):

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        topic: str,
        name: str,
        sensor_type: str,
        icon: str,
        entry_id: str,
        is_target_temp: bool = False
    ) -> None:
        super().__init__(hass, device_id, entry_id)
        
        self._topic = topic
        self._sensor_type = sensor_type
        self._is_target_temp = is_target_temp
        
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{sensor_type}"
        self._attr_has_entity_name = True
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = "°C"
        self._attr_device_class = "temperature"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Кондиционер GoldStar GSAC/GSACI ({device_id})",
            "manufacturer": "Voldemar",
            "model": "GoldStar GSAC/GSACI",
        }
        
        self._attr_native_value = None
        self._message_callback = None

    async def _setup_mqtt_subscriptions(self):
        """Настройка подписок на MQTT топики."""
        _LOGGER.debug("Настраиваем MQTT подписки для сенсора %s", self._attr_name)
        
        @callback
        def message_received(message):
            if not self._available:
                return
                
            payload = message.payload
            
            _LOGGER.debug(
                "Сенсор '%s' получил сообщение: %s", 
                self._attr_name, payload
            )
            
            try:
                temperature = float(payload)
                
                if self._is_target_temp:
                    temperature = int(round(temperature))
                
                self._attr_native_value = temperature
                self.safe_async_write_ha_state()
                
            except (ValueError, TypeError) as e:
                _LOGGER.warning(
                    "Некорректное значение температуры для '%s': %s. Ошибка: %s", 
                    self._attr_name, payload, e
                )
                self._attr_native_value = None
                self.safe_async_write_ha_state()
        
        self._message_callback = message_received
        
        unsubscribe = await mqtt.async_subscribe(
            self.hass,
            self._topic,
            message_received,
            qos=1
        )
        self._add_mqtt_subscription(unsubscribe)

    async def _reset_state(self):
        """Сброс состояния при потере доступности."""
        _LOGGER.debug("Сбрасываем состояние сенсора %s", self._attr_name)
        self._attr_native_value = None

    @property
    def extra_state_attributes(self):
        return {
            "device_id": self._device_id,
            "topic": self._topic,
            "sensor_type": self._sensor_type,
            "is_target_temperature": self._is_target_temp,
            "unit_of_measurement": "°C",
            "device_available": self._available,
        }