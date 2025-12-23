"""Конфигурационный поток для интеграции Кондиционер GoldStar GSAC/GSACI."""
from __future__ import annotations

import asyncio
import re
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    DEFAULT_DEVICE_ID,
    MQTT_TOPICS,
    ERROR_MESSAGES,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Обработка конфигурационного потока для интеграции."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH
    
    # Регулярное выражение для проверки device_id
    DEVICE_ID_PATTERN = re.compile(r'^[a-fA-F0-9]{12}$')

    async def async_step_user(self, user_input=None):
        """Первоначальный шаг конфигурации."""
        errors = {}
        
        if user_input is not None:
            # Получаем и очищаем device_id
            device_id = user_input.get(CONF_DEVICE_ID, "").strip()
            
            # Проверяем на пустое значение
            if not device_id:
                errors[CONF_DEVICE_ID] = "device_id_required"
            
            # Проверяем длину
            elif len(device_id) != 12:
                errors[CONF_DEVICE_ID] = "device_id_length"
            
            # Проверяем формат (только hex-символы)
            elif not self.DEVICE_ID_PATTERN.match(device_id):
                errors[CONF_DEVICE_ID] = "device_id_format"
            
            # Проверяем уникальность
            elif await self._is_device_id_already_configured(device_id):
                errors[CONF_DEVICE_ID] = "device_id_already_configured"
            
            # Проверяем наличие базового топика в MQTT
            else:
                mqtt_topic_exists = await self._check_mqtt_topic_exists(device_id)
                if not mqtt_topic_exists:
                    errors["base"] = "mqtt_topic_not_found"
            
            # Если все проверки пройдены
            if not errors:
                # Устанавливаем уникальный ID для этой конфигурации
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                
                # Формируем все MQTT топики
                data = {CONF_DEVICE_ID: device_id}
                
                # Добавляем все топики в конфигурацию
                for key, template in MQTT_TOPICS.items():
                    data[key] = template.format(device_id=device_id)
                
                # Создаем запись конфигурации
                return self.async_create_entry(
                    title=f"Кондиционер GoldStar GSAC/GSACI ({device_id})",
                    data=data
                )

        # Схема формы ввода с текстовым полем
        data_schema = vol.Schema({
            vol.Required(
                CONF_DEVICE_ID,
                default=DEFAULT_DEVICE_ID,
                description={
                    "suggested_value": DEFAULT_DEVICE_ID,
                    "placeholder": "Введите 12 символов (a-f, 0-9)"
                }
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                    multiline=False,
                    autocomplete="off"
                )
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "default_device_id": DEFAULT_DEVICE_ID,
                "requirements": "Должен состоять из 12 символов (буквы a-f, цифры 0-9)"
            }
        )
    
    async def _check_mqtt_topic_exists(self, device_id: str) -> bool:
        """
        Проверяет наличие топиков MQTT для указанного device_id.
        
        Важно: НЕ создает новых топиков, только проверяет существующие!
        """
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        _LOGGER.debug("Проверяем наличие MQTT топиков для device_id: %s", device_id)
        
        # 1. Проверяем, подключен ли MQTT брокер
        if not mqtt.is_connected(self.hass):
            _LOGGER.error("MQTT брокер не подключен")
            return False
        
        # 2. Подписываемся на wildcard для этого device_id
        #    MQTT брокер отправит retained сообщения, если они существуют
        topic_found = asyncio.Event()
        
        @callback
        def on_message_received(msg):
            """Обработчик полученных сообщений."""
            # Логируем только для отладки
            _LOGGER.debug("Получено MQTT сообщение: %s -> %s", msg.topic, msg.payload)
            
            # Если топик начинается с нашего device_id и это НЕ наш тестовый топик
            if msg.topic.startswith(f"{device_id}/"):
                # Игнорируем тестовые топики, которые могли быть созданы ранее
                if not msg.topic.endswith("/test_discovery") and not msg.topic.endswith("/ping"):
                    _LOGGER.info("Найден существующий топик: %s", msg.topic)
                    topic_found.set()
        
        unsubscribe = None
        try:
            # Подписываемся на все топики устройства
            wildcard_topic = f"{device_id}/#"
            _LOGGER.debug("Подписываемся на топик: %s", wildcard_topic)
            
            unsubscribe = await mqtt.async_subscribe(
                self.hass,
                wildcard_topic,
                on_message_received,
                qos=0,
                encoding="utf-8"
            )
            
            # 3. Ждем retained сообщения от MQTT брокера
            #    Брокер немедленно отправляет retained сообщения при подписке
            try:
                # Короткое ожидание для retained сообщений
                await asyncio.wait_for(topic_found.wait(), timeout=2.0)
                _LOGGER.info("Топики MQTT для device_id %s найдены", device_id)
                return True
            except asyncio.TimeoutError:
                _LOGGER.debug("Retained сообщения не найдены для device_id %s", device_id)
            
            # 4. Если retained сообщений нет, проверяем активность устройства
            #    Ждем любое сообщение от устройства в течение 3 секунд
            try:
                await asyncio.wait_for(topic_found.wait(), timeout=3.0)
                _LOGGER.info("Устройство %s активно в MQTT", device_id)
                return True
            except asyncio.TimeoutError:
                _LOGGER.debug("Устройство %s не активно в MQTT", device_id)
            
            # 5. Если до сих пор не нашли, пробуем более агрессивную проверку
            #    Но БЕЗ создания топиков!
            
            # Проверяем через LWT (Last Will and Testament) топик, если он есть
            lwt_topic = f"{device_id}/status"
            lwt_found = asyncio.Event()
            
            @callback
            def lwt_callback(msg):
                if msg.topic == lwt_topic:
                    lwt_found.set()
            
            lwt_unsubscribe = await mqtt.async_subscribe(
                self.hass,
                lwt_topic,
                lwt_callback,
                qos=0
            )
            
            try:
                await asyncio.wait_for(lwt_found.wait(), timeout=1.0)
                _LOGGER.info("Найден LWT топик: %s", lwt_topic)
                lwt_unsubscribe()
                return True
            except asyncio.TimeoutError:
                _LOGGER.debug("LWT топик не найден: %s", lwt_topic)
            finally:
                lwt_unsubscribe()
            
            # 6. Если все проверки не прошли - топиков нет
            _LOGGER.warning("Топики MQTT для device_id %s не найдены", device_id)
            return False
            
        except Exception as e:
            _LOGGER.error("Ошибка при проверке MQTT топиков: %s", str(e))
            return False
        finally:
            # Всегда отписываемся
            if unsubscribe:
                unsubscribe()
    
    async def _is_device_id_already_configured(self, device_id: str) -> bool:
        """Проверяет, настроено ли уже устройство с таким device_id."""
        # Проверяем все существующие конфигурации
        existing_entries = self._async_current_entries()
        
        for entry in existing_entries:
            if entry.data.get(CONF_DEVICE_ID) == device_id:
                return True
        
        return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Получение потока опций для этой конфигурации."""
        return OptionsFlowHandler(config_entry)