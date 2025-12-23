"""Климат-платформа для интеграции Кондиционер GoldStar GSAC/GSACI."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import GSACBaseEntity
from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    MQTT_TOPICS,
    MODE_MAPPING,
    FAN_SPEEDS,
    SWING_MODES,
    HA_TO_MQTT_MODES,
    HA_TO_MQTT_FAN,
    HA_TO_MQTT_SWING,
    MQTT_TO_HA_MODES,
    MQTT_TO_HA_FAN,
    MQTT_TO_HA_SWING,
    TEMP_MIN,
    TEMP_MAX,
    TEMP_STEP,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    SWING_ON,
    SWING_OFF,
)

_LOGGER = logging.getLogger(__name__)

MQTT_TO_HVAC_MODE = {
    "0": HVACMode.OFF,
    "1": HVACMode.AUTO,
    "2": HVACMode.COOL,
    "3": HVACMode.DRY,
    "4": HVACMode.HEAT,
    "5": HVACMode.FAN_ONLY,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Настройка климат-сущности из конфигурационной записи."""
    
    device_id = config_entry.data.get(CONF_DEVICE_ID)
    
    topics = {}
    for key, template in MQTT_TOPICS.items():
        topics[key] = template.format(device_id=device_id)
    
    _LOGGER.info(
        "Настраиваем климат-сущность для устройства: %s",
        device_id
    )
    
    entity = PolarisClimateEntity(
        hass=hass,
        device_id=device_id,
        topics=topics,
        entry_id=config_entry.entry_id
    )
    
    async_add_entities([entity])


class PolarisClimateEntity(GSACBaseEntity, ClimateEntity):

    _attr_has_entity_name = True
    _attr_name = "Кондиционер"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = TEMP_STEP
    _attr_min_temp = TEMP_MIN
    _attr_max_temp = TEMP_MAX
    
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.FAN_MODE |
        ClimateEntityFeature.TURN_OFF |
        ClimateEntityFeature.TURN_ON |
        ClimateEntityFeature.SWING_MODE
    )
    
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.HEAT,
        HVACMode.FAN_ONLY,
    ]
    
    _attr_swing_modes = [SWING_ON, SWING_OFF]
    
    _attr_hvac_mode = HVACMode.OFF
    _attr_fan_mode = FAN_AUTO
    _attr_swing_mode = SWING_OFF
    _attr_current_temperature = None
    _attr_target_temperature = TEMP_MIN

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        topics: dict[str, str],
        entry_id: str
    ) -> None:
        """Инициализация климат-сущности."""
        super().__init__(hass, device_id, entry_id)
        
        self._topics = topics
        
        self._attr_unique_id = f"{DOMAIN}_{device_id}_climate"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Кондиционер GoldStar GSAC/GSACI ({device_id})",
            "manufacturer": "Voldemar",
            "model": "GoldStar GSAC/GSACI",
            "via_device": (DOMAIN, device_id),
        }
        
        self._current_hvac_action = HVACAction.OFF
        self._previous_fan_mode = FAN_AUTO
        self._need_fan_auto_correction = False
        
        # Коллбэки для подписок
        self._mode_callback = None
        self._temp_callback = None
        self._target_temp_callback = None
        self._fan_callback = None
        self._swing_callback = None

    async def _setup_mqtt_subscriptions(self):
        """Настройка подписок на MQTT топики."""
        _LOGGER.debug("Настраиваем MQTT подписки для климат-сущности")
        
        @callback
        def mode_received(msg):
            """Обработка сообщений о режиме работы."""
            if not self._available:
                return
                
            payload = msg.payload
            
            if payload in MQTT_TO_HVAC_MODE:
                new_hvac_mode = MQTT_TO_HVAC_MODE[payload]
                old_hvac_mode = self._attr_hvac_mode
                
                self._attr_hvac_mode = new_hvac_mode
                
                if new_hvac_mode == HVACMode.FAN_ONLY and old_hvac_mode != HVACMode.FAN_ONLY:
                    if self._attr_fan_mode == FAN_AUTO:
                        self._need_fan_auto_correction = True
                
                if payload == "0":
                    self._current_hvac_action = HVACAction.OFF
                elif payload == "2":
                    self._current_hvac_action = HVACAction.COOLING
                elif payload == "4":
                    self._current_hvac_action = HVACAction.HEATING
                elif payload == "5":
                    self._current_hvac_action = HVACAction.FAN
                else:
                    self._current_hvac_action = HVACAction.IDLE
                
                self.safe_async_write_ha_state()
                
                if self._need_fan_auto_correction:
                    self.hass.async_create_task(self._correct_fan_speed_for_mode())
        
        @callback
        def temperature_received(msg):
            """Обработка текущей температуры."""
            if not self._available:
                return
                
            try:
                temp = float(msg.payload)
                self._attr_current_temperature = temp
                self.safe_async_write_ha_state()
            except ValueError:
                _LOGGER.warning("Некорректное значение температуры: %s", msg.payload)
        
        @callback
        def target_temperature_received(msg):
            """Обработка целевой температуры."""
            if not self._available:
                return
                
            try:
                temp = float(msg.payload)
                self._attr_target_temperature = temp
                self.safe_async_write_ha_state()
            except ValueError:
                _LOGGER.warning("Некорректное значение целевой температуры: %s", msg.payload)
        
        @callback
        def fan_speed_received(msg):
            """Обработка скорости вентилятора."""
            if not self._available:
                return
                
            payload = msg.payload
            
            if payload in MQTT_TO_HA_FAN:
                new_fan_mode = MQTT_TO_HA_FAN[payload]
                
                if self._attr_fan_mode != FAN_AUTO:
                    self._previous_fan_mode = self._attr_fan_mode
                
                if self._need_fan_auto_correction and new_fan_mode != FAN_AUTO:
                    self._need_fan_auto_correction = False
                
                self._attr_fan_mode = new_fan_mode
                self.safe_async_write_ha_state()
        
        @callback
        def swing_received(msg):
            """Обработка состояния жалюзи."""
            if not self._available:
                return
                
            payload = msg.payload
            
            if payload in MQTT_TO_HA_SWING:
                self._attr_swing_mode = MQTT_TO_HA_SWING[payload]
                self.safe_async_write_ha_state()
        
        # Сохраняем коллбэки
        self._mode_callback = mode_received
        self._temp_callback = temperature_received
        self._target_temp_callback = target_temperature_received
        self._fan_callback = fan_speed_received
        self._swing_callback = swing_received
        
        # Подписываемся на топики
        subscriptions = [
            (self._topics["mode_out"], mode_received),
            (self._topics["temp_out"], temperature_received),
            (self._topics["temp_comfort_out"], target_temperature_received),
            (self._topics["fan_speed_out"], fan_speed_received),
            (self._topics["backlight_out"], swing_received),
        ]
        
        for topic, callback_func in subscriptions:
            unsubscribe = await mqtt.async_subscribe(
                self.hass,
                topic,
                callback_func,
                0,
            )
            self._add_mqtt_subscription(unsubscribe)

    async def _reset_state(self):
        """Сброс состояния при потере доступности."""
        _LOGGER.debug("Сбрасываем состояние климат-сущности")
        self._attr_current_temperature = None
        self._current_hvac_action = HVACAction.OFF
        self._need_fan_auto_correction = False

    async def _correct_fan_speed_for_mode(self) -> None:
        """Автоматическая корректировка скорости вентилятора для режима."""
        if not self._need_fan_auto_correction or not self._available:
            return
        
        if self._attr_hvac_mode == HVACMode.FAN_ONLY and self._attr_fan_mode == FAN_AUTO:
            await self.async_set_fan_mode(FAN_LOW)
        
        self._need_fan_auto_correction = False

    @property
    def hvac_action(self) -> HVACAction | None:
        """Текущее действие кондиционера."""
        return self._current_hvac_action
    
    @property
    def fan_modes(self) -> list[str] | None:
        """Доступные скорости вентилятора в зависимости от режима."""
        if not self._available:
            return []
            
        if self.hvac_mode == HVACMode.FAN_ONLY:
            return [FAN_LOW, FAN_MEDIUM, FAN_HIGH]
        else:
            return [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Установка нового режима работы."""
        if not self._available:
            _LOGGER.warning("Устройство недоступно, невозможно изменить режим")
            return
            
        if hvac_mode not in self.hvac_modes:
            _LOGGER.error("Неподдерживаемый режим: %s", hvac_mode)
            return
        
        old_hvac_mode = self._attr_hvac_mode
        mqtt_value = HA_TO_MQTT_MODES.get(hvac_mode.value)
        
        if mqtt_value is None:
            _LOGGER.error("Не найден MQTT код для режима: %s", hvac_mode)
            return
        
        if hvac_mode == HVACMode.FAN_ONLY and old_hvac_mode != HVACMode.FAN_ONLY:
            if self._attr_fan_mode == FAN_AUTO:
                if old_hvac_mode != HVACMode.FAN_ONLY and self._attr_fan_mode != FAN_AUTO:
                    self._previous_fan_mode = self._attr_fan_mode
                await self.async_set_fan_mode(FAN_LOW)
        
        await mqtt.async_publish(
            self.hass,
            self._topics["mode_in"],
            mqtt_value,
            0,
            False
        )
        
        self._attr_hvac_mode = hvac_mode
        self.safe_async_write_ha_state()
        
        _LOGGER.info("Установлен режим: %s (MQTT: %s)", hvac_mode, mqtt_value)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Установка целевой температуры."""
        if not self._available:
            _LOGGER.warning("Устройство недоступно, невозможно изменить температуру")
            return
            
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        temperature = max(self.min_temp, min(self.max_temp, temperature))
        temperature_int = int(round(temperature))
        
        await mqtt.async_publish(
            self.hass,
            self._topics["temp_comfort_in"],
            str(temperature_int),
            0,
            False
        )
        
        self._attr_target_temperature = temperature_int
        self.safe_async_write_ha_state()
        
        _LOGGER.info("Установлена целевая температура: %s°C", temperature_int)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Установка скорости вентилятора."""
        if not self._available:
            _LOGGER.warning("Устройство недоступно, невозможно изменить скорость вентилятора")
            return
            
        if fan_mode not in self.fan_modes:
            _LOGGER.error("Неподдерживаемая скорость: %s", fan_mode)
            return
        
        if self._attr_hvac_mode == HVACMode.FAN_ONLY and fan_mode == FAN_AUTO:
            _LOGGER.warning("Скорость 'Авто' недоступна в режиме вентиляции")
            return
        
        mqtt_value = HA_TO_MQTT_FAN.get(fan_mode)
        if mqtt_value is None:
            _LOGGER.error("Не найден MQTT код для скорости: %s", fan_mode)
            return
        
        await mqtt.async_publish(
            self.hass,
            self._topics["fan_speed_in"],
            mqtt_value,
            0,
            False
        )
        
        if fan_mode != FAN_AUTO:
            self._previous_fan_mode = fan_mode
        
        self._attr_fan_mode = fan_mode
        self.safe_async_write_ha_state()
        
        _LOGGER.info("Установлена скорость вентилятора: %s (MQTT: %s)", fan_mode, mqtt_value)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Управление горизонтальными жалюзи."""
        if not self._available:
            _LOGGER.warning("Устройство недоступно, невозможно изменить положение жалюзи")
            return
            
        if swing_mode not in self.swing_modes:
            _LOGGER.error("Неподдерживаемый режим жалюзи: %s", swing_mode)
            return
        
        mqtt_value = HA_TO_MQTT_SWING.get(swing_mode)
        if mqtt_value is None:
            _LOGGER.error("Не найден MQTT код для жалюзи: %s", swing_mode)
            return
        
        await mqtt.async_publish(
            self.hass,
            self._topics["backlight_in"],
            mqtt_value,
            0,
            False
        )
        
        self._attr_swing_mode = swing_mode
        self.safe_async_write_ha_state()
        
        _LOGGER.info("Жалюзи установлены в режим: %s (MQTT: %s)", swing_mode, mqtt_value)

    @property
    def extra_state_attributes(self):
        """Дополнительные атрибуты состояния."""
        return {
            "device_id": self._device_id,
            "previous_fan_mode": self._previous_fan_mode,
            "is_fan_only_mode": self.hvac_mode == HVACMode.FAN_ONLY,
            "device_available": self._available,
        }