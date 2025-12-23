"""Числовая сущность для установки температуры в интеграции Кондиционер GoldStar GSAC/GSACI."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import GSACBaseEntity
from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    MQTT_TOPICS,
    TEMP_MIN,
    TEMP_MAX,
    TEMP_STEP,
    TEMP_DEFAULT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Настройка числовой сущности для температуры из конфигурационной записи."""
    
    device_id = config_entry.data.get(CONF_DEVICE_ID)
    
    topics = {}
    for key, template in MQTT_TOPICS.items():
        topics[key] = template.format(device_id=device_id)
    
    _LOGGER.info(
        "Настраиваем числовую сущность для устройства: %s",
        device_id
    )
    
    entity = TargetTemperatureNumber(
        hass=hass,
        device_id=device_id,
        topic_read=topics["temp_comfort_out"],
        topic_write=topics["temp_comfort_in"],
        entry_id=config_entry.entry_id
    )
    
    async_add_entities([entity])


class TargetTemperatureNumber(GSACBaseEntity, NumberEntity):
    """Числовая сущность для установки целевой температуры."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        topic_read: str,
        topic_write: str,
        entry_id: str
    ) -> None:
        """Инициализация числовой сущности."""
        super().__init__(hass, device_id, entry_id)
        
        self._topic_read = topic_read
        self._topic_write = topic_write
        
        self._attr_name = "Установить температуру"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_target_temperature"
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:thermometer-plus"
        self._attr_native_unit_of_measurement = "°C"
        self._attr_device_class = "temperature"
        self._attr_mode = NumberMode.BOX
        
        self._attr_native_min_value = TEMP_MIN
        self._attr_native_max_value = TEMP_MAX
        self._attr_native_step = TEMP_STEP
        self._attr_native_value = TEMP_DEFAULT
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Кондиционер GoldStar GSAC/GSACI ({device_id})",
            "manufacturer": "Voldemar",
            "model": "GoldStar GSAC/GSACI",
        }
        
        self._message_callback = None

    async def _setup_mqtt_subscriptions(self):
        """Настройка подписок на MQTT топики."""
        _LOGGER.debug("Настраиваем MQTT подписки для числовой сущности")
        
        @callback
        def message_received(message):
            """Обработка новых сообщений MQTT."""
            if not self._available:
                return
                
            payload = message.payload
            
            _LOGGER.debug(
                "Числовая сущность получила сообщение: %s", 
                payload
            )
            
            try:
                temperature = float(payload)
                temperature_int = int(round(temperature))
                
                if TEMP_MIN <= temperature_int <= TEMP_MAX:
                    self._attr_native_value = temperature_int
                    self.safe_async_write_ha_state()
                else:
                    _LOGGER.warning(
                        "Температура вне допустимого диапазона: %s", 
                        temperature_int
                    )
                    
            except (ValueError, TypeError) as e:
                _LOGGER.warning(
                    "Некорректное значение температуры: %s. Ошибка: %s", 
                    payload, e
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
        _LOGGER.debug("Сбрасываем состояние числовой сущности")
        self._attr_native_value = TEMP_DEFAULT

    async def async_set_native_value(self, value: float) -> None:
        """Установка нового значения температуры."""
        if not self._available:
            _LOGGER.warning("Устройство недоступно, невозможно установить температуру")
            return
            
        try:
            temp_int = int(round(value))
            
            if temp_int < TEMP_MIN or temp_int > TEMP_MAX:
                _LOGGER.error(
                    "Температура %s вне допустимого диапазона [%s, %s]",
                    temp_int, TEMP_MIN, TEMP_MAX
                )
                return
            
            await mqtt.async_publish(
                self.hass,
                self._topic_write,
                str(temp_int),
                qos=1,
                retain=False
            )
            
            _LOGGER.info("Установлена целевая температура: %s°C", temp_int)
            
            self._attr_native_value = temp_int
            self.safe_async_write_ha_state()
            
        except Exception as e:
            _LOGGER.error("Ошибка при установке температуры: %s", e)
            raise

    @property
    def extra_state_attributes(self):
        """Дополнительные атрибуты состояния."""
        return {
            "device_id": self._device_id,
            "read_topic": self._topic_read,
            "write_topic": self._topic_write,
            "min_temperature": TEMP_MIN,
            "max_temperature": TEMP_MAX,
            "step": TEMP_STEP,
            "default_temperature": TEMP_DEFAULT,
            "device_available": self._available,
        }