"""Селекторы для интеграции Вольдемаров кондиционер."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import GSACBaseEntity
from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    MQTT_TOPICS,
    MODE_SELECT_OPTIONS,
    MODE_SELECT_ICONS,
    FAN_SELECT_OPTIONS,
    FAN_SELECT_ICONS,
    HA_TO_MQTT_MODES,
    HA_TO_MQTT_FAN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Настройка селекторов из конфигурационной записи."""
    
    device_id = config_entry.data.get(CONF_DEVICE_ID)
    
    topics = {}
    for key, template in MQTT_TOPICS.items():
        topics[key] = template.format(device_id=device_id)
    
    _LOGGER.info(
        "Настраиваем селекторы для устройства: %s",
        device_id
    )
    
    entities = [
        ModeSelect(
            hass=hass,
            device_id=device_id,
            topic_read=topics["mode_out"],
            topic_write=topics["mode_in"],
            entry_id=config_entry.entry_id
        ),
        FanSpeedSelect(
            hass=hass,
            device_id=device_id,
            topic_read=topics["fan_speed_out"],
            topic_write=topics["fan_speed_in"],
            entry_id=config_entry.entry_id
        )
    ]
    
    async_add_entities(entities)


class ModeSelect(GSACBaseEntity, SelectEntity):
    """Селектор для выбора режима работы кондиционера."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        topic_read: str,
        topic_write: str,
        entry_id: str
    ) -> None:
        """Инициализация селектора режима."""
        super().__init__(hass, device_id, entry_id)
        
        self._topic_read = topic_read
        self._topic_write = topic_write
        
        self._attr_name = "Режим работы"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_mode_select"
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:air-conditioner"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Вольдемаров кондиционер ({device_id})",
            "manufacturer": "Voldemar",
            "model": "Local MQTT",
        }
        
        self._attr_options = list(MODE_SELECT_OPTIONS.values())
        self._attr_current_option = MODE_SELECT_OPTIONS.get("0", "Выключено")
        
        self._current_mode_mqtt = "0"
        self._message_callback = None

    async def _setup_mqtt_subscriptions(self):
        """Настройка подписок на MQTT топики."""
        _LOGGER.debug("Настраиваем MQTT подписки для селектора режима")
        
        @callback
        def message_received(message):
            """Обработка новых сообщений MQTT."""
            if not self._available:
                return
                
            payload = message.payload
            
            _LOGGER.debug(
                "Селектор режима получил сообщение: %s", 
                payload
            )
            
            if payload in MODE_SELECT_OPTIONS:
                self._current_mode_mqtt = payload
                self._attr_current_option = MODE_SELECT_OPTIONS[payload]
                self._attr_icon = MODE_SELECT_ICONS.get(payload, "mdi:air-conditioner")
                self.safe_async_write_ha_state()
            else:
                _LOGGER.warning(
                    "Получено неизвестное значение режима: %s", 
                    payload
                )
        
        self._message_callback = message_received
        
        unsubscribe = await mqtt.async_subscribe(
            self.hass,
            self._topic_read,
            message_received,
            qos=1
        )
        self._add_mqtt_subscription(unsubscribe)

    async def _reset_state(self):
        """Сброс состояния при потере доступности."""
        _LOGGER.debug("Сбрасываем состояние селектора режима")
        self._current_mode_mqtt = "0"
        self._attr_current_option = MODE_SELECT_OPTIONS.get("0", "Выключено")

    async def async_select_option(self, option: str) -> None:
        """Изменение выбранного режима."""
        if not self._available:
            _LOGGER.warning("Устройство недоступно, невозможно изменить режим")
            return
        
        mqtt_value = None
        for value, name in MODE_SELECT_OPTIONS.items():
            if name == option:
                mqtt_value = value
                break
        
        if mqtt_value is None:
            _LOGGER.error("Некорректный режим: %s", option)
            return
        
        await mqtt.async_publish(
            self.hass,
            self._topic_write,
            mqtt_value,
            qos=1,
            retain=False
        )
        
        self._current_mode_mqtt = mqtt_value
        self._attr_current_option = option
        self._attr_icon = MODE_SELECT_ICONS.get(mqtt_value, "mdi:air-conditioner")
        self.safe_async_write_ha_state()
        
        _LOGGER.info("Установлен режим: %s (MQTT: %s)", option, mqtt_value)

    @property
    def extra_state_attributes(self):
        """Дополнительные атрибуты состояния."""
        return {
            "device_id": self._device_id,
            "read_topic": self._topic_read,
            "write_topic": self._topic_write,
            "current_mode_mqtt": self._current_mode_mqtt,
            "options_mapping": MODE_SELECT_OPTIONS,
            "device_available": self._available,
        }


class FanSpeedSelect(GSACBaseEntity, SelectEntity):
    """Селектор для выбора скорости вентилятора."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        topic_read: str,
        topic_write: str,
        entry_id: str
    ) -> None:
        """Инициализация селектора скорости."""
        super().__init__(hass, device_id, entry_id)
        
        self._topic_read = topic_read
        self._topic_write = topic_write
        
        self._attr_name = "Скорость вентилятора"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_fan_speed_select"
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:fan"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Вольдемаров кондиционер ({device_id})",
            "manufacturer": "Voldemar",
            "model": "Local MQTT",
        }
        
        self._attr_options = list(FAN_SELECT_OPTIONS.values())
        self._attr_current_option = FAN_SELECT_OPTIONS.get("0", "Авто")
        
        self._current_fan_speed_mqtt = "0"
        self._message_callback = None

    async def _setup_mqtt_subscriptions(self):
        """Настройка подписок на MQTT топики."""
        _LOGGER.debug("Настраиваем MQTT подписки для селектора скорости")
        
        @callback
        def message_received(message):
            """Обработка новых сообщений MQTT."""
            if not self._available:
                return
                
            payload = message.payload
            
            _LOGGER.debug(
                "Селектор скорости получил сообщение: %s", 
                payload
            )
            
            if payload in FAN_SELECT_OPTIONS:
                self._current_fan_speed_mqtt = payload
                self._attr_current_option = FAN_SELECT_OPTIONS[payload]
                self._attr_icon = FAN_SELECT_ICONS.get(payload, "mdi:fan")
                self.safe_async_write_ha_state()
            else:
                _LOGGER.warning(
                    "Получено неизвестное значение скорости: %s", 
                    payload
                )
        
        self._message_callback = message_received
        
        unsubscribe = await mqtt.async_subscribe(
            self.hass,
            self._topic_read,
            message_received,
            qos=1
        )
        self._add_mqtt_subscription(unsubscribe)

    async def _reset_state(self):
        """Сброс состояния при потере доступности."""
        _LOGGER.debug("Сбрасываем состояние селектора скорости")
        self._current_fan_speed_mqtt = "0"
        self._attr_current_option = FAN_SELECT_OPTIONS.get("0", "Авто")

    async def async_select_option(self, option: str) -> None:
        """Изменение выбранной скорости вентилятора."""
        if not self._available:
            _LOGGER.warning("Устройство недоступно, невозможно изменить скорость")
            return
        
        mqtt_value = None
        for value, name in FAN_SELECT_OPTIONS.items():
            if name == option:
                mqtt_value = value
                break
        
        if mqtt_value is None:
            _LOGGER.error("Некорректная скорость: %s", option)
            return
        
        await mqtt.async_publish(
            self.hass,
            self._topic_write,
            mqtt_value,
            qos=1,
            retain=False
        )
        
        self._current_fan_speed_mqtt = mqtt_value
        self._attr_current_option = option
        self._attr_icon = FAN_SELECT_ICONS.get(mqtt_value, "mdi:fan")
        self.safe_async_write_ha_state()
        
        _LOGGER.info("Установлена скорость: %s (MQTT: %s)", option, mqtt_value)

    @property
    def extra_state_attributes(self):
        """Дополнительные атрибуты состояния."""
        return {
            "device_id": self._device_id,
            "read_topic": self._topic_read,
            "write_topic": self._topic_write,
            "current_fan_speed_mqtt": self._current_fan_speed_mqtt,
            "options_mapping": FAN_SELECT_OPTIONS,
            "device_available": self._available,
        }