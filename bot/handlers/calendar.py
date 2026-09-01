import datetime as dt
import logging

from telebot import types

import config
import database
from bot.messages import texts
from services import calendar_service
from utils.helpers import format_date_human, format_time_human, is_admin, safe_call, user_display_name
from utils.scheduler import schedule_reminders, cancel_reminders

logger = logging.getLogger("nasiba_bot")


def _appt_manage_kb(appointment_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔄 Перенести", callback_data=f"appt_reschedule:{appointment_id}"),
        types.InlineKeyboardButton("❌ Отменить", callback_data=f"appt_cancel:{appointment_id}"),
    )
    return kb


def send_date_choice(bot, chat_id):
    """Показывает пользователю ближайшие даты со свободными слотами."""
    try:
        today = dt.date.today()
        kb = types.InlineKeyboardMarkup(row_width=1)
        found_any = False
        for i in range(config.DAYS_AHEAD_FOR_BOOKING):
            date = today + dt.timedelta(days=i)
            try:
                slots = calendar_service.get_free_slots(date)
            except calendar_service.CalendarUnavailable:
                bot.send_message(
                    chat_id,
                    "Не получилось подключиться к календарю. Попробуй чуть позже "
                    "или напиши мне лично 🤍",
                )
                return
            if not slots:
                continue
            found_any = True
            if i == 0:
                label = "📅 Сегодня"
            elif i == 1:
                label = "📅 Завтра"
            else:
                label = "📅 " + format_date_human(dt.datetime.combine(date, dt.time()))
            kb.add(types.InlineKeyboardButton(label, callback_data=f"cal_date:{date.isoformat()}"))
        if not found_any:
            bot.send_message(chat_id, texts.CALENDAR_NO_DATES)
            return
        bot.send_message(chat_id, texts.CALENDAR_CHOOSE_DATE, reply_markup=kb)
    except Exception:
        logger.exception("Ошибка при показе доступных дат")
        safe_call(bot.send_message, chat_id, texts.GENERIC_ERROR)


def _build_event_description(user_row, brief_row) -> str:
    return (
        f"Клиент: {user_display_name(user_row)}\n"
        f"Telegram: {user_row['telegram_id']}\n"
        f"Username: @{user_row['username'] or '—'}\n"
        "Бриф: заполненный файл доступен администратору в Telegram-боте."
    )


def register(bot):

    @bot.callback_query_handler(func=lambda c: c.data.startswith("cal_date:"))
    def handle_cal_date(call):
        try:
            bot.answer_callback_query(call.id)
            date_str = call.data.split(":", 1)[1]
            date = dt.date.fromisoformat(date_str)
            try:
                slots = calendar_service.get_free_slots(date)
            except calendar_service.CalendarUnavailable:
                bot.send_message(call.message.chat.id, "Календарь сейчас недоступен. Попробуй чуть позже 🤍")
                return
            if not slots:
                bot.send_message(call.message.chat.id, texts.CALENDAR_NO_SLOTS)
                return
            kb = types.InlineKeyboardMarkup(row_width=3)
            buttons = [
                types.InlineKeyboardButton(
                    format_time_human(slot),
                    callback_data=f"cal_time:{date.isoformat()}:{slot.strftime('%H:%M')}",
                )
                for slot in slots
            ]
            kb.add(*buttons)
            bot.send_message(
                call.message.chat.id,
                texts.CALENDAR_CHOOSE_TIME.format(date=format_date_human(dt.datetime.combine(date, dt.time()))),
                reply_markup=kb,
            )
        except Exception:
            logger.exception("Ошибка при выборе даты")
            safe_call(bot.send_message, call.message.chat.id, texts.GENERIC_ERROR)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("cal_time:"))
    def handle_cal_time(call):
        try:
            bot.answer_callback_query(call.id)
            _, date_str, time_str = call.data.split(":", 2)
            date = dt.date.fromisoformat(date_str)
            hour, minute = map(int, time_str.split(":"))

            user = database.get_or_create_user(call.from_user)
            brief = database.get_uploaded_brief_for_user(user["id"])
            if not brief:
                bot.send_message(call.message.chat.id, "Сначала нужно заполнить бриф 🤍")
                return

            tz_slots = calendar_service._tz()
            start = tz_slots.localize(dt.datetime.combine(date, dt.time(hour, minute)))
            end = start + dt.timedelta(minutes=config.APPOINTMENT_DURATION)

            # Финальная проверка — слот всё ещё свободен
            try:
                still_free = any(
                    slot.hour == hour and slot.minute == minute
                    for slot in calendar_service.get_free_slots(date)
                )
            except calendar_service.CalendarUnavailable:
                bot.send_message(call.message.chat.id, "Календарь сейчас недоступен. Попробуй чуть позже 🤍")
                return
            if not still_free:
                bot.send_message(call.message.chat.id, "Это время уже заняли. Выбери другое 🤍")
                send_date_choice(bot, call.message.chat.id)
                return

            summary = f"Диагностика блога — {user_display_name(user)}"
            description = _build_event_description(user, brief)

            try:
                event_id = calendar_service.create_event(summary, description, start, end)
            except calendar_service.CalendarUnavailable:
                bot.send_message(
                    call.message.chat.id,
                    "Не получилось создать запись в календаре. Попробуй ещё раз через "
                    "несколько секунд, либо напиши мне лично 🤍",
                )
                return

            appointment = database.create_appointment(
                user["id"], event_id, start.isoformat(), end.isoformat()
            )
            database.log_event(user["id"], "appointment_created")

            date_human = format_date_human(start)
            time_human = format_time_human(start)

            bot.send_message(
                call.message.chat.id,
                texts.APPOINTMENT_CONFIRMED_CLIENT.format(date=date_human, time=time_human),
                reply_markup=_appt_manage_kb(appointment["id"]),
            )

            if config.ADMIN_TELEGRAM_ID:
                safe_call(
                    bot.send_message,
                    config.ADMIN_TELEGRAM_ID,
                    texts.APPOINTMENT_CONFIRMED_ADMIN.format(
                        name=user_display_name(user),
                        username=user["username"] or "—",
                        instagram="файл прикреплён в Telegram",
                        date=date_human,
                        time=time_human,
                        source=user["source"] or "—",
                    ),
                )

            schedule_reminders(bot, appointment["id"], start)
        except Exception:
            logger.exception("Ошибка при создании записи")
            safe_call(bot.send_message, call.message.chat.id, texts.GENERIC_ERROR)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("appt_cancel:"))
    def handle_appt_cancel(call):
        try:
            bot.answer_callback_query(call.id)
            appointment_id = int(call.data.split(":", 1)[1])
            appointment = database.get_appointment_by_id(appointment_id)
            if not appointment or appointment["status"] != "confirmed":
                bot.send_message(call.message.chat.id, texts.APPOINTMENT_NONE)
                return
            safe_call(calendar_service.delete_event, appointment["google_event_id"])
            database.cancel_appointment(appointment_id)
            cancel_reminders(appointment_id)
            bot.send_message(call.message.chat.id, texts.APPOINTMENT_CANCELLED)
        except Exception:
            logger.exception("Ошибка при отмене записи")
            safe_call(bot.send_message, call.message.chat.id, texts.GENERIC_ERROR)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("appt_reschedule:"))
    def handle_appt_reschedule(call):
        try:
            bot.answer_callback_query(call.id)
            appointment_id = int(call.data.split(":", 1)[1])
            appointment = database.get_appointment_by_id(appointment_id)
            if not appointment or appointment["status"] != "confirmed":
                bot.send_message(call.message.chat.id, texts.APPOINTMENT_NONE)
                return
            safe_call(calendar_service.delete_event, appointment["google_event_id"])
            database.cancel_appointment(appointment_id)
            cancel_reminders(appointment_id)
            bot.send_message(call.message.chat.id, "Старая запись отменена. Выбери новое время 🤍")
            send_date_choice(bot, call.message.chat.id)
        except Exception:
            logger.exception("Ошибка при переносе записи")
            safe_call(bot.send_message, call.message.chat.id, texts.GENERIC_ERROR)


def send_admin_reschedule_date_choice(bot, chat_id, appointment_id: int):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for day_offset in range(config.DAYS_AHEAD_FOR_BOOKING):
        date = dt.date.today() + dt.timedelta(days=day_offset)
        if calendar_service.get_free_slots(date):
            keyboard.add(types.InlineKeyboardButton(
                format_date_human(dt.datetime.combine(date, dt.time())),
                callback_data=f"admin_cal_date:{appointment_id}:{date.isoformat()}",
            ))
    if not keyboard.keyboard:
        bot.send_message(chat_id, texts.CALENDAR_NO_DATES)
        return
    bot.send_message(chat_id, "Выбери новую дату диагностики:", reply_markup=keyboard)


def register_admin_reschedule_handlers(bot):
    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_cal_date:"))
    def handle_admin_cal_date(call):
        try:
            if not is_admin(call.from_user.id):
                bot.answer_callback_query(call.id, texts.ADMIN_ONLY, show_alert=True)
                return
            _, appointment_id, date_str = call.data.split(":", 2)
            date = dt.date.fromisoformat(date_str)
            slots = calendar_service.get_free_slots(date)
            keyboard = types.InlineKeyboardMarkup(row_width=3)
            keyboard.add(*[
                types.InlineKeyboardButton(
                    format_time_human(slot),
                    callback_data=f"admin_cal_time:{appointment_id}:{date.isoformat()}:{slot.strftime('%H:%M')}",
                )
                for slot in slots
            ])
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "Выбери новое время:", reply_markup=keyboard)
        except Exception:
            logger.exception("Ошибка выбора даты переноса администратором")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_cal_time:"))
    def handle_admin_cal_time(call):
        try:
            if not is_admin(call.from_user.id):
                bot.answer_callback_query(call.id, texts.ADMIN_ONLY, show_alert=True)
                return
            _, appointment_id_str, date_str, time_str = call.data.split(":", 3)
            appointment_id = int(appointment_id_str)
            appointment = database.get_appointment_by_id(appointment_id)
            if not appointment or appointment["status"] != "confirmed":
                bot.answer_callback_query(call.id, texts.APPOINTMENT_NONE, show_alert=True)
                return
            date = dt.date.fromisoformat(date_str)
            hour, minute = map(int, time_str.split(":"))
            start = calendar_service._tz().localize(dt.datetime.combine(date, dt.time(hour, minute)))
            if not any(slot.hour == hour and slot.minute == minute for slot in calendar_service.get_free_slots(date)):
                bot.answer_callback_query(call.id, "Это время уже заняли.", show_alert=True)
                return
            user = database.get_user_by_id(appointment["user_id"])
            brief = database.get_uploaded_brief_for_user(user["id"])
            new_event_id = calendar_service.create_event(
                f"Диагностика блога — {user_display_name(user)}",
                _build_event_description(user, brief),
                start,
                start + dt.timedelta(minutes=config.APPOINTMENT_DURATION),
            )
            calendar_service.delete_event(appointment["google_event_id"])
            database.reschedule_appointment(
                appointment_id, new_event_id, start.isoformat(),
                (start + dt.timedelta(minutes=config.APPOINTMENT_DURATION)).isoformat(),
            )
            cancel_reminders(appointment_id)
            schedule_reminders(bot, appointment_id, start)
            bot.answer_callback_query(call.id, "Диагностика перенесена.")
            bot.send_message(call.message.chat.id, "Диагностика перенесена в Google Calendar.")
            safe_call(bot.send_message, user["telegram_id"], texts.APPOINTMENT_RESCHEDULED_CLIENT.format(
                date=format_date_human(start), time=format_time_human(start)
            ))
        except Exception:
            logger.exception("Ошибка переноса диагностики администратором")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)
