"""
Конфигурация проекта.
Все чувствительные данные берутся из .env — не хранить секреты в коде.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _get_int(name: str, default: int = 0) -> int:
    value = os.getenv(name)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# --- Telegram ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_TELEGRAM_ID = _get_int("ADMIN_TELEGRAM_ID", 0)
TELEGRAM_CHANNEL_USERNAME = os.getenv("TELEGRAM_CHANNEL_USERNAME", "")
TELEGRAM_CHANNEL_ID = _get_int("TELEGRAM_CHANNEL_ID", 0)
TELEGRAM_CHANNEL_URL = os.getenv("TELEGRAM_CHANNEL_URL", "")

# Username бота без @. Если не задан в .env — будет получен автоматически
# через bot.get_me() при старте (см. main.py) и записан сюда.
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

# --- Оплата ---
KASPI_PAYMENT_URL = os.getenv("KASPI_PAYMENT_URL", "https://pay.kaspi.kz/pay/tiu8nyrj")
DIAGNOSTICS_PRICE = _get_int("DIAGNOSTICS_PRICE", 3000)

# --- Google Calendar ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")

GOOGLE_CREDENTIALS_PATH = os.path.join("google", "credentials.json")
GOOGLE_TOKEN_PATH = os.path.join("google", "token.json")

# --- Расписание ---
TIMEZONE = os.getenv("TIMEZONE", "Asia/Almaty")
WORK_START = os.getenv("WORK_START", "10:00")
WORK_END = os.getenv("WORK_END", "20:00")
APPOINTMENT_DURATION = _get_int("APPOINTMENT_DURATION", 40)  # минут

# --- База данных ---
DATABASE_PATH = os.getenv("DATABASE_PATH", "database.db")

# Сколько дней вперёд предлагать для записи
DAYS_AHEAD_FOR_BOOKING = 7
