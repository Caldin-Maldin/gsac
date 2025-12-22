"""Переключатель жалюзи для интеграции Вольдемаров кондиционер."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import GSACBaseEntity
from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    MQTT_TOPICS,
    SWING_MODES,
    HA_TO_MQTT_SWING,
    MQTT_TO_HA_SWING,
    SWING_ON,
    SWING_OFF,
    BLINDS_ON,
    BLINDS_OFF,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Настройка переключателя жалюзи из конфигурационной записи."""
    
    device_id = config_entry.data.get(CONF_DEVICE_ID)
    
    topics = {}
    for key, template in MQTT_TOPICS.items():
        topics[key] = template.format(device_id=device_id)
    
    _LOGGER.info(
        "Настраиваем переключатель жалюзи для устройства: %s",
        device_id
    )
    
    entity = BlindsSwitch(
        hass=hass,
        device_id=device_id,
        topic_in=topics["backlight_in"],
        topic_out=topics["backlight_out"],
        name="Горизонтальные жалюзи",
        switch_type="horizontal_blinds",
        icon="mdi:blinds-horizontal",
        entry_id=config_entry.entry_id
    )
    
    async_add_entities([entity])


class BlindsSwitch(GSACBaseEntity, SwitchEntity):
    """Переключатель горизонтальных жалюзи."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        topic_in: str,
        topic_out: str,
        name: str,
        switch_type: str,
        icon: str,
        entry_id: str
    ) -> None:
        """Инициализация переключателя."""
        super().__init__(hass, device_id, entry_id)
        
        self._topic_in = topic_in
        self._topic_out = topic_out
        self._switch_type = switch_type
        
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{switch_type}"
        self._attr_has_entity_name = True
        self._attr_icon = icon
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Вольдемаров кондиционер ({device_id})",
            "manufacturer": "Voldemar",
            "model": "Local MQTT",
        }
        
        self._state = False
        self._message_callback = None

    async def _setup_mqtt_subscriptions(self):
        """Настройка подписок на MQTT топики."""
        _LOGGER.debug("Настраиваем MQTT подписки для переключателя жалюзи")
        
        @callback
        def message_received(message):
            """Обработка новых сообщений MQTT."""
            if not self._available:
                return
                
            payload = message.payload
            
            _LOGGER.debug(
                "Переключатель '%s' получил сообщение: %s", 
                self._attr_name, payload
            )
            
            if payload == BLINDS_ON:
                self._state = True
                _LOGGER.debug("Жалюзи включены")
            elif payload == BLINDS_OFF:
                self._state = False
                _LOGGER.debug("Жалюзи выключены")
            else:
                _LOGGER.warning(
                    "Неизвестное состояние жалюзи: %s", 
                    payload
                )
            
            self.safe_async_write_ha_state()
        
        self._message_callback = message_received
        
        unsubscribe = await mqtt.async_subscribe(
            self.hass,
            self._topic_out,
            message_received,
            qos=0
        )
        self._add_mqtt_subscription(unsubscribe)

    async def _reset_state(self):
        """Сброс состояния при потере доступности."""
        _LOGGER.debug("Сбрасываем состояние переключателя жалюзи")
        self._state = False

    @property
    def is_on(self) -> bool | None:
        """Состояние переключателя (включен/выключен)."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Включение жалюзи."""
        if not self._available:
            _LOGGER.warning("Устройство недоступно, невозможно включить жалюзи")
            return
            
        await self._publish_state(BLINDS_ON)
        self._state = True
        self.safe_async_write_ha_state()
        _LOGGER.info("Жалюзи включены")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Выключение жалюзи."""
        if not self._available:
            _LOGGER.warning("Устройство недоступно, невозможно выключить жалюзи")
            return
            
        await self._publish_state(BLINDS_OFF)
        self._state = False
        self.safe_async_write_ha_state()
        _LOGGER.info("Жалюзи выключены")

    async def _publish_state(self, payload: str) -> None:
        """Публикация состояния в MQTT."""
        try:
            await mqtt.async_publish(
                self.hass,
                self._topic_in,
                payload,
                qos=0,
                retain=False
            )
            _LOGGER.debug("Отправлено в MQTT: %s -> %s", self._topic_in, payload)
        except Exception as e:
            _LOGGER.error("Ошибка отправки в MQTT: %s", e)
            raise

    @property
    def extra_state_attributes(self):
        """Дополнительные атрибуты состояния."""
        return {
            "device_id": self._device_id,
            "switch_type": self._switch_type,
            "topic_in": self._topic_in,
            "topic_out": self._topic_out,
            "blinds_on_value": BLINDS_ON,
            "blinds_off_value": BLINDS_OFF,
            "device_available": self._available,
        }