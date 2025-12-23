"""Интеграция Кондиционер GoldStar GSAC/GSACI через MQTT."""
from __future__ import annotations

import logging
import re
from typing import Dict, Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.components import mqtt

from .const import DOMAIN, CONF_DEVICE_ID, MQTT_TOPICS, CONNECTED_ONLINE, CONNECTED_OFFLINE

_LOGGER = logging.getLogger(__name__)

# Список всех платформ интеграции
PLATFORMS = ["climate", "select", "sensor", "number", "switch"]

# Регулярное выражение для валидации device_id при загрузке
DEVICE_ID_PATTERN = re.compile(r'^[a-fA-F0-9]{12}$')


class DeviceAvailabilityManager:
    """Менеджер для отслеживания доступности устройства."""
    
    def __init__(self, hass: HomeAssistant, device_id: str, entry_id: str):
        """Инициализация менеджера доступности."""
        self.hass = hass
        self.device_id = device_id
        self.entry_id = entry_id
        self._available = False
        self._entities = []
        self._availability_topic = MQTT_TOPICS["connected_out"].format(device_id=device_id)
        
    def add_entity(self, entity):
        """Добавление сущности для управления доступностью."""
        self._entities.append(entity)
        # Обновляем состояние доступности новой сущности
        entity._available = self._available
        
    def remove_entity(self, entity):
        """Удаление сущности."""
        if entity in self._entities:
            self._entities.remove(entity)
    
    async def setup(self):
        """Настройка подписки на топик доступности."""
        @callback
        def availability_received(message):
            """Обработка сообщений о доступности."""
            payload = message.payload
            
            _LOGGER.debug(
                "Устройство %s: получен статус доступности: %s",
                self.device_id, payload
            )
            
            new_available = payload == CONNECTED_ONLINE
            
            if new_available != self._available:
                self._available = new_available
                status_text = "онлайн" if new_available else "офлайн"
                _LOGGER.info(
                    "Устройство %s перешло в статус: %s",
                    self.device_id, status_text
                )
                
                # Асинхронно уведомляем все сущности об изменении доступности
                for entity in self._entities:
                    self.hass.async_create_task(
                        entity.on_availability_changed(new_available)
                    )
        
        # Подписка на топик доступности
        await mqtt.async_subscribe(
            self.hass,
            self._availability_topic,
            availability_received,
            qos=1
        )
        
        # Устанавливаем начальный статус как недоступный
        self._available = False
    
    @property
    def available(self) -> bool:
        """Текущий статус доступности устройства."""
        return self._available


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка интеграции из конфигурационной записи."""
    
    device_id = entry.data.get(CONF_DEVICE_ID, "").strip()
    
    if not device_id:
        _LOGGER.error("Отсутствует Device ID в конфигурации")
        raise ConfigEntryNotReady("Отсутствует Device ID")
    
    if len(device_id) != 12:
        _LOGGER.error("Некорректная длина Device ID: %s (ожидается 12 символов)", len(device_id))
        raise ConfigEntryNotReady("Некорректная длина Device ID")
    
    if not DEVICE_ID_PATTERN.match(device_id):
        _LOGGER.error("Некорректный формат Device ID: %s", device_id)
        raise ConfigEntryNotReady("Некорректный формат Device ID")
    
    # Инициализируем менеджер доступности
    availability_manager = DeviceAvailabilityManager(hass, device_id, entry.entry_id)
    
    # Инициализируем хранилище данных для этой интеграции
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "device_id": device_id,
        "availability_manager": availability_manager,
        "entities": {}
    }
    
    # Загружаем все платформы (сущности)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Настраиваем менеджер доступности
    await availability_manager.setup()
    
    _LOGGER.info(
        "Интеграция '%s' успешно загружена для устройства %s",
        entry.title,
        device_id
    )
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка конфигурационной записи."""
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    
    _LOGGER.info(
        "Интеграция '%s' выгружена. Статус: %s",
        entry.title,
        "успешно" if unload_ok else "с ошибками"
    )
    
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Миграция устаревших конфигураций."""
    _LOGGER.debug("Миграция конфигурации с версии %s", config_entry.version)
    
    if config_entry.version == 1:
        device_id = config_entry.data.get(CONF_DEVICE_ID, "")
        
        if device_id and (len(device_id) != 12 or not DEVICE_ID_PATTERN.match(device_id)):
            _LOGGER.warning(
                "Обнаружен некорректный Device ID в старой конфигурации: %s", 
                device_id
            )
        
        new_data = {**config_entry.data}
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            version=2
        )
        _LOGGER.info("Конфигурация мигрирована на версию 2")
        return True
    
    return True