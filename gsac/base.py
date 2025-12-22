"""Базовый класс для всех сущностей интеграции."""
from __future__ import annotations

import logging
from typing import Callable, List, Tuple, Any
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GSACBaseEntity(Entity):
    """Базовый класс для всех сущностей Вольдемаров кондиционера."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        entry_id: str
    ) -> None:
        """Инициализация базовой сущности."""
        self.hass = hass
        self._device_id = device_id
        self._entry_id = entry_id
        
        # Флаг доступности
        self._available = False
        # Флаг готовности сущности (entity_id назначен)
        self._entity_ready = False
        # Список подписок на MQTT
        self._mqtt_subscriptions = []
        
        # Регистрация в менеджере доступности
        self._register_with_availability_manager()
    
    def _register_with_availability_manager(self):
        """Регистрация в менеджере доступности."""
        if DOMAIN in self.hass.data and self._entry_id in self.hass.data[DOMAIN]:
            data = self.hass.data[DOMAIN][self._entry_id]
            if "availability_manager" in data:
                availability_manager = data["availability_manager"]
                availability_manager.add_entity(self)
                # Устанавливаем начальное состояние доступности
                self._available = availability_manager.available
                _LOGGER.debug(
                    "Сущность зарегистрирована в менеджере доступности. Начальный статус: %s",
                    "доступна" if self._available else "недоступна"
                )
    
    async def async_added_to_hass(self) -> None:
        """Вызывается при добавлении сущности в Home Assistant."""
        # Теперь сущность готова к обновлению состояния
        self._entity_ready = True
        _LOGGER.debug("Сущность %s готова к работе", self.entity_id)
        
        # Подписываемся на MQTT топики, если устройство доступно
        if self._available:
            await self._setup_mqtt_subscriptions()
    
    async def async_will_remove_from_hass(self) -> None:
        """Очистка при удалении сущности."""
        self._entity_ready = False
        await self._unsubscribe_mqtt()
        
        if DOMAIN in self.hass.data and self._entry_id in self.hass.data[DOMAIN]:
            data = self.hass.data[DOMAIN][self._entry_id]
            if "availability_manager" in data:
                availability_manager = data["availability_manager"]
                availability_manager.remove_entity(self)
                _LOGGER.debug(
                    "Сущность %s удалена из менеджера доступности",
                    self.entity_id
                )
        await super().async_will_remove_from_hass()
    
    def safe_async_write_ha_state(self):
        """Безопасное обновление состояния сущности."""
        if self._entity_ready and self.entity_id is not None:
            self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "Попытка обновить состояние сущности, которая еще не готова: %s",
                self.name
            )
    
    async def on_availability_changed(self, available: bool):
        """Вызывается при изменении доступности устройства."""
        if self._available == available:
            return
            
        self._available = available
        _LOGGER.debug(
            "Сущность %s: доступность изменена на %s",
            self.entity_id, "доступна" if available else "недоступна"
        )
        
        if available:
            # Устройство стало доступным - подписываемся на топики
            await self._setup_mqtt_subscriptions()
        else:
            # Устройство стало недоступным - отписываемся от топиков
            await self._unsubscribe_mqtt()
            # Сбрасываем состояние
            await self._reset_state()
        
        # Обновляем состояние в HA
        self.safe_async_write_ha_state()
    
    async def _setup_mqtt_subscriptions(self):
        """Настройка подписок на MQTT топики.
        Должен быть переопределен в дочерних классах."""
        pass
    
    async def _unsubscribe_mqtt(self):
        """Отписка от всех MQTT топиков."""
        for unsubscribe in self._mqtt_subscriptions:
            unsubscribe()
        self._mqtt_subscriptions.clear()
    
    async def _reset_state(self):
        """Сброс состояния сущности при потере доступности.
        Должен быть переопределен в дочерних классах."""
        pass
    
    def _add_mqtt_subscription(self, unsubscribe_callback):
        """Добавление подписки MQTT в список для последующей отписки."""
        self._mqtt_subscriptions.append(unsubscribe_callback)
    
    @property
    def available(self) -> bool:
        """Доступность сущности."""
        return self._available
    
    @property
    def device_id(self) -> str:
        """ID устройства."""
        return self._device_id