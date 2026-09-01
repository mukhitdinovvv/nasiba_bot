"""
Точка входа Telegram-бота для Насибы.

Запуск:
    python main.py

Бот собирается из независимых модулей-хендлеров (bot/handlers/*),
каждый из которых регистрирует свои команды и callback'и на общем
объекте bot. Общая логика — простая и линейная, без сложных фреймворков.
"""
import logging

import telebot

import config
import database
from utils import scheduler as reminder_scheduler

# Увеличенные таймауты нужны для загрузки крупных локальных фото
# (например, в диагностике) — дефолтных 15/30 сек не всегда хватает.
telebot.apihelper.CONNECT_TIMEOUT = 30
telebot.apihelper.READ_TIMEOUT = 90

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("nasiba_bot")


def create_bot() -> telebot.TeleBot:
    if not config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в .env")

    bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode=None)

    # Если username бота не прописан вручную в .env — получаем его сам.
    if not config.BOT_USERNAME:
        try:
            me = bot.get_me()
            config.BOT_USERNAME = me.username
            logger.info("Определён username бота: @%s", config.BOT_USERNAME)
        except Exception:
            logger.exception("Не удалось получить username бота через get_me()")

    return bot


def register_handlers(bot: telebot.TeleBot):
    from bot.handlers import start, materials, diagnostics, payment, brief, calendar, products, admin

    # Порядок регистрации важен только для читаемости — все callback_data
    # и content_type-фильтры уникальны между модулями, поэтому конфликтов нет.
    start.register(bot)
    materials.register(bot)
    diagnostics.register(bot)
    payment.register(bot)
    brief.register(bot)
    calendar.register(bot)
    calendar.register_admin_reschedule_handlers(bot)
    products.register(bot)
    admin.register(bot)


def main():
    logger.info("Запуск бота...")
    database.init_db()

    bot = create_bot()
    register_handlers(bot)

    reminder_scheduler.start()
    reminder_scheduler.reschedule_all_future_reminders(bot)

    logger.info("Бот запущен и готов принимать сообщения.")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)


if __name__ == "__main__":
    main()
