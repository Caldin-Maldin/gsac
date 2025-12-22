"""Константы для интеграции Вольдемаров кондиционер."""

# Идентификатор домена (обязательно должен совпадать с именем папки)
DOMAIN = "gsac"

# Название интеграции для UI
DEFAULT_NAME = "Вольдемаров кондиционер"

# Стандартный device_id (12 hex-символов)
DEFAULT_DEVICE_ID = "1cdbd4cbcc74"
DEFAULT_IP_ADDRESS = "192.168.1.34"

# Конфигурационные ключи
CONF_DEVICE_ID = "device_id"
CONF_IP_ADDRESS = "ip_address"

# ============ СООБЩЕНИЯ ОБ ОШИБКАХ ============
ERROR_MESSAGES = {
    "device_id_required": "Введите Device ID",
    "device_id_length": "Device ID должен состоять из 12 символов",
    "device_id_format": "Используйте только буквы a-f и цифры 0-9",
    "device_id_already_configured": "Этот Device ID уже настроен",
    "device_id_already_used": "Этот Device ID уже используется в другой конфигурации",
    "ip_address_required": "Введите IP-адрес кондиционера",
    "ip_address_invalid": "Неверный формат IP-адреса",
    "device_unavailable": "Устройство недоступно по указанному IP-адресу",
}

# ============ ПАРАМЕТРЫ ПРОВЕРКИ ДОСТУПНОСТИ ============
PING_TIMEOUT = 2  # Таймаут ping в секундах
PING_COUNT = 2    # Количество попыток ping
CHECK_AVAILABILITY = True  # Включить проверку доступности


# ============ ПАРАМЕТРЫ ТЕМПЕРАТУРЫ ============
TEMP_MIN = 16     # Минимальная температура (°C)
TEMP_MAX = 30     # Максимальная температура (°C)
TEMP_STEP = 1     # Шаг изменения температуры
TEMP_DEFAULT = 22 # Температура по умолчанию

# ============ MQTT ТОПИКИ (шаблоны) ============
# Формат: {device_id} будет заменен на реальный ID устройства
MQTT_TOPICS = {
    "mode_in": "{device_id}/mode/in",             # Установка режима (в)
    "mode_out": "{device_id}/mode/out",           # Чтение режима (из)
    "temp_out": "{device_id}/sensor/temperature/out",      # Температура комнаты
    "temp_comfort_out": "{device_id}/temperature_comfort/out",  # Целевая температура
    "temp_comfort_in": "{device_id}/temperature_comfort/in",    # Установка целевой температуры
    "fan_speed_out": "{device_id}/power/out",     # Скорость вентилятора
    "fan_speed_in": "{device_id}/power/in",       # Установка скорости
    "backlight_out": "{device_id}/backlight_auto/out",    # Статус жалюзи
    "backlight_in": "{device_id}/backlight_auto/in",      # Управление жалюзи
    "connected_out": "{device_id}/connected/out", # Статус подключения устройства
}

# ============ КОНСТАНТЫ ДОСТУПНОСТИ ============
CONNECTED_ONLINE = "1"
CONNECTED_OFFLINE = "0"

# ============ МАППИНГИ РЕЖИМОВ ============

# Режимы работы кондиционера (MQTT → Человекочитаемые)
MODE_MAPPING = {
    # MQTT: [HA режим, Человеческое название, Иконка]
    "0": ["off", "Выключено", "mdi:power-off"],
    "1": ["auto", "Авто", "mdi:auto-mode"],
    "2": ["cool", "Холод", "mdi:snowflake"],
    "3": ["dry", "Осушение", "mdi:water"],
    "4": ["heat", "Тепло", "mdi:fire"],
    "5": ["fan_only", "Вентиляция", "mdi:fan"],
}

# Для select сущностей (выпадающий список)
MODE_SELECT_OPTIONS = {
    mqtt_val: human_name 
    for mqtt_val, (_, human_name, _) in MODE_MAPPING.items()
}

MODE_SELECT_ICONS = {
    mqtt_val: icon 
    for mqtt_val, (_, _, icon) in MODE_MAPPING.items()
}

# Преобразование HA режимов → MQTT значения
HA_TO_MQTT_MODES = {
    ha_mode: mqtt_val 
    for mqtt_val, (ha_mode, _, _) in MODE_MAPPING.items()
}

# Преобразование MQTT → HA режимы (для climate сущности)
MQTT_TO_HA_MODES = {
    mqtt_val: ha_mode 
    for mqtt_val, (ha_mode, _, _) in MODE_MAPPING.items()
}

# ============ СКОРОСТИ ВЕНТИЛЯТОРА ============

FAN_SPEEDS = {
    # MQTT: [HA значение, Человеческое название, Иконка]
    "0": ["auto", "Авто", "mdi:fan-auto"],
    "1": ["low", "Низкая", "mdi:fan-speed-1"],
    "2": ["medium", "Средняя", "mdi:fan-speed-2"],
    "3": ["high", "Высокая", "mdi:fan-speed-3"],
}

# Для select сущности
FAN_SELECT_OPTIONS = {
    mqtt_val: human_name 
    for mqtt_val, (_, human_name, _) in FAN_SPEEDS.items()
}

FAN_SELECT_ICONS = {
    mqtt_val: icon 
    for mqtt_val, (_, _, icon) in FAN_SPEEDS.items()
}

# Преобразования
HA_TO_MQTT_FAN = {
    ha_mode: mqtt_val 
    for mqtt_val, (ha_mode, _, _) in FAN_SPEEDS.items()
}

MQTT_TO_HA_FAN = {
    mqtt_val: ha_mode 
    for mqtt_val, (ha_mode, _, _) in FAN_SPEEDS.items()
}

# Константы для удобства использования в коде
FAN_AUTO = "auto"
FAN_LOW = "low"
FAN_MEDIUM = "medium"
FAN_HIGH = "high"

# ============ РЕЖИМЫ ЖАЛЮЗИ ============

SWING_MODES = {
    "1": ["on", "Включены", "mdi:blinds-horizontal"],
    "0": ["off", "Выключены", "mdi:blinds-horizontal-closed"],
}

HA_TO_MQTT_SWING = {
    ha_mode: mqtt_val 
    for mqtt_val, (ha_mode, _, _) in SWING_MODES.items()
}

MQTT_TO_HA_SWING = {
    mqtt_val: ha_mode 
    for mqtt_val, (ha_mode, _, _) in SWING_MODES.items()
}

# Константы
SWING_ON = "on"
SWING_OFF = "off"
BLINDS_ON = "1"
BLINDS_OFF = "0"