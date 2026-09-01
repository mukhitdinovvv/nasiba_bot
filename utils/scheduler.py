"""
Планировщик напоминаний о записи (за 24 часа и за 1 час).
Используется APScheduler с планировщиком в памяти процесса.
При перезапуске бота напоминания для будущих записей пересоздаются
из базы данных — см. reschedule_all_future_reminders().
"""
import datetime as dt
import logging

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from telebot import types

import config
import database
from bot.messages import texts
from bot.keyboards.materials import after_material_kb
from utils.helpers import format_date_human, format_time_human, safe_call, user_display_name

logger = logging.getLogger("nasiba_bot")

scheduler = BackgroundScheduler(timezone=pytz.timezone(config.TIMEZONE))


def start():
    if not scheduler.running:
        scheduler.start()
        logger.info("Планировщик напоминаний запущен")


def _send_reminder(bot, appointment_id: int, kind: str):
    try:
        appointment = database.get_appointment_by_id(appointment_id)
        if not appointment or appointment["status"] != "confirmed":
            return
        user = database.get_user_by_id(appointment["user_id"])
        if not user:
            return
        start = dt.datetime.fromisoformat(appointment["start_time"])
        if kind == "admin_2h":
            if not config.ADMIN_TELEGRAM_ID:
                return
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                types.InlineKeyboardButton("✅ Диагностика завершена", callback_data=f"admin_appt_complete:{appointment_id}"),
                types.InlineKeyboardButton("🔄 Перенести диагностику", callback_data=f"admin_appt_reschedule:{appointment_id}"),
            )
            safe_call(
                bot.send_message,
                config.ADMIN_TELEGRAM_ID,
                texts.ADMIN_REMINDER_2H.format(
                    name=user_display_name(user),
                    date=format_date_human(start),
                    time=format_time_human(start),
                ),
                reply_markup=keyboard,
            )
            return
        if kind == "24h":
            text = texts.REMINDER_24H.format(
                date=format_date_human(start), time=format_time_human(start)
            )
        else:
            text = texts.REMINDER_1H.format(time=format_time_human(start))
        safe_call(bot.send_message, user["telegram_id"], text)
    except Exception:
        logger.exception("Ошибка при отправке напоминания для записи %s", appointment_id)


def _send_material_follow_up(bot, telegram_id: int):
    safe_call(bot.send_message, telegram_id, texts.AFTER_MATERIAL, reply_markup=after_material_kb())


def schedule_material_follow_up(bot, telegram_id: int):
    scheduler.add_job(
        _send_material_follow_up,
        "date",
        run_date=dt.datetime.now(pytz.timezone(config.TIMEZONE)) + dt.timedelta(minutes=30),
        args=[bot, telegram_id],
    )


def schedule_reminders(bot, appointment_id: int, start_time: dt.datetime):
    tz = pytz.timezone(config.TIMEZONE)
    now = dt.datetime.now(tz)

    reminder_24h_at = start_time - dt.timedelta(hours=24)
    reminder_admin_2h_at = start_time - dt.timedelta(hours=2)
    reminder_1h_at = start_time - dt.timedelta(hours=1)

    if reminder_24h_at > now:
        scheduler.add_job(
            _send_reminder,
            "date",
            run_date=reminder_24h_at,
            args=[bot, appointment_id, "24h"],
            id=f"reminder_24h_{appointment_id}",
            replace_existing=True,
        )
    if reminder_admin_2h_at > now and config.ADMIN_TELEGRAM_ID:
        scheduler.add_job(
            _send_reminder,
            "date",
            run_date=reminder_admin_2h_at,
            args=[bot, appointment_id, "admin_2h"],
            id=f"reminder_admin_2h_{appointment_id}",
            replace_existing=True,
        )
    if reminder_1h_at > now:
        scheduler.add_job(
            _send_reminder,
            "date",
            run_date=reminder_1h_at,
            args=[bot, appointment_id, "1h"],
            id=f"reminder_1h_{appointment_id}",
            replace_existing=True,
        )


def cancel_reminders(appointment_id: int):
    for kind in ("24h", "admin_2h", "1h"):
        job_id = f"reminder_{kind}_{appointment_id}"
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass  # задачи могло не быть — это нормально


def reschedule_all_future_reminders(bot):
    """Вызывается один раз при старте бота, чтобы восстановить напоминания
    для уже существующих будущих записей после перезапуска процесса."""
    try:
        for appt in database.list_upcoming_appointments(limit=200):
            start = dt.datetime.fromisoformat(appt["start_time"])
            schedule_reminders(bot, appt["id"], start)
    except Exception:
        logger.exception("Не удалось восстановить напоминания после перезапуска")
