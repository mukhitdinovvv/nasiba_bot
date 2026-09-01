import datetime as dt
import logging

from telebot import types

import config
import database
from bot.keyboards.admin import (
    admin_main_kb,
    admin_materials_menu_kb,
    admin_materials_list_kb,
    admin_material_detail_kb,
    admin_payments_menu_kb,
    admin_appointments_menu_kb,
    admin_back_kb,
    admin_schedule_day_kb,
    admin_schedule_kb,
)
from bot.keyboards.payments import admin_payment_kb
from bot.messages import texts
from utils.helpers import is_admin, is_valid_slug, deep_link, safe_call, user_display_name

logger = logging.getLogger("nasiba_bot")


def _guard(bot, call_or_message) -> bool:
    """Возвращает True, если пользователь — администратор."""
    from_user = getattr(call_or_message, "from_user", None)
    if not from_user or not is_admin(from_user.id):
        if hasattr(call_or_message, "id"):  # это callback_query
            safe_call(bot.answer_callback_query, call_or_message.id, texts.ADMIN_ONLY, show_alert=True)
        else:
            safe_call(bot.send_message, call_or_message.chat.id, texts.ADMIN_ONLY)
        return False
    return True


def register(bot):

    def _day_bounds(date: dt.date):
        start_hour, start_minute = map(int, config.WORK_START.split(":"))
        end_hour, end_minute = map(int, config.WORK_END.split(":"))
        tz = __import__("pytz").timezone(config.TIMEZONE)
        start = tz.localize(dt.datetime.combine(date, dt.time(start_hour, start_minute)))
        end = tz.localize(dt.datetime.combine(date, dt.time(end_hour, end_minute)))
        return start, end

    def _is_day_closed(date: dt.date) -> bool:
        start, end = _day_bounds(date)
        return any(
            block["start_time"] == start.isoformat() and block["end_time"] == end.isoformat()
            for block in database.list_schedule_blocks_for_date(date.isoformat())
        )

    def _send_schedule_day(bot, chat_id, date: dt.date):
        from services import calendar_service

        closed = _is_day_closed(date)
        appointments = database.list_confirmed_appointments_for_date(date.isoformat())
        blocks = database.list_schedule_blocks_for_date(date.isoformat())
        lines = [f"📅 {date.strftime('%d.%m.%Y')}"]
        if closed:
            lines += ["", "🔒 День закрыт"]
        else:
            slots = calendar_service.get_free_slots(date)
            lines += ["", f"🟢 Свободных слотов: {len(slots)}"]
        if appointments:
            lines += ["", "🔴 Записи:"]
            for appointment in appointments:
                user = database.get_user_by_id(appointment["user_id"])
                time = dt.datetime.fromisoformat(appointment["start_time"]).strftime("%H:%M")
                lines.append(f"{time} - {user_display_name(user)}")
        if blocks and not closed:
            lines += ["", f"🔒 Ручных блокировок: {len(blocks)}"]
        bot.send_message(
            chat_id,
            "\n".join(lines),
            reply_markup=admin_schedule_day_kb(date.isoformat(), closed),
        )

    @bot.callback_query_handler(func=lambda c: c.data == "admin_schedule")
    def handle_admin_schedule(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        dates = []
        for offset in range(config.DAYS_AHEAD_FOR_BOOKING):
            date = dt.date.today() + dt.timedelta(days=offset)
            dates.append((date.isoformat(), date.strftime("%d.%m (%a)")))
        bot.send_message(call.message.chat.id, "🗓 Выбери дату для управления расписанием:", reply_markup=admin_schedule_kb(dates))

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_schedule_date:"))
    def handle_admin_schedule_date(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        _send_schedule_day(bot, call.message.chat.id, dt.date.fromisoformat(call.data.split(":", 1)[1]))

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_schedule_close_day:"))
    def handle_admin_schedule_close_day(call):
        if not _guard(bot, call):
            return
        date = dt.date.fromisoformat(call.data.split(":", 1)[1])
        start, end = _day_bounds(date)
        database.add_schedule_block(start.isoformat(), end.isoformat(), "День закрыт администратором")
        bot.answer_callback_query(call.id, "День закрыт.")
        _send_schedule_day(bot, call.message.chat.id, date)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_schedule_open:"))
    def handle_admin_schedule_open(call):
        if not _guard(bot, call):
            return
        date = dt.date.fromisoformat(call.data.split(":", 1)[1])
        database.remove_schedule_blocks_for_date(date.isoformat())
        bot.answer_callback_query(call.id, "День открыт.")
        _send_schedule_day(bot, call.message.chat.id, date)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_schedule_close_time:"))
    def handle_admin_schedule_close_time(call):
        if not _guard(bot, call):
            return
        from services import calendar_service

        date = dt.date.fromisoformat(call.data.split(":", 1)[1])
        slots = calendar_service.get_free_slots(date)
        if not slots:
            bot.answer_callback_query(call.id, "Нет свободных слотов для закрытия.", show_alert=True)
            return
        keyboard = types.InlineKeyboardMarkup(row_width=3)
        keyboard.add(*[
            types.InlineKeyboardButton(slot.strftime("%H:%M"), callback_data=f"admin_schedule_close_slot:{date.isoformat()}:{slot.strftime('%H:%M')}")
            for slot in slots
        ])
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "Выбери время, которое нужно закрыть:", reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_schedule_close_slot:"))
    def handle_admin_schedule_close_slot(call):
        if not _guard(bot, call):
            return
        _, date_str, time_str = call.data.split(":", 2)
        date = dt.date.fromisoformat(date_str)
        hour, minute = map(int, time_str.split(":"))
        tz = __import__("pytz").timezone(config.TIMEZONE)
        start = tz.localize(dt.datetime.combine(date, dt.time(hour, minute)))
        end = start + dt.timedelta(minutes=config.APPOINTMENT_DURATION)
        database.add_schedule_block(start.isoformat(), end.isoformat(), "Слот закрыт администратором")
        bot.answer_callback_query(call.id, "Слот закрыт.")
        _send_schedule_day(bot, call.message.chat.id, date)

    @bot.callback_query_handler(func=lambda c: c.data == "admin_schedule_close_period")
    def handle_admin_schedule_close_period(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id,
            "Отправь период в формате: ДД.ММ.ГГГГ ДД.ММ.ГГГГ\nНапример: 05.09.2026 07.09.2026",
        )
        bot.register_next_step_handler(msg, _close_schedule_period, bot)

    def _close_schedule_period(message, bot):
        if not is_admin(message.from_user.id):
            return
        try:
            start_text, end_text = message.text.split()
            start_date = dt.datetime.strptime(start_text, "%d.%m.%Y").date()
            end_date = dt.datetime.strptime(end_text, "%d.%m.%Y").date()
            if end_date < start_date:
                raise ValueError
        except (AttributeError, ValueError):
            msg = bot.send_message(message.chat.id, "Неверный формат. Пример: 05.09.2026 07.09.2026")
            bot.register_next_step_handler(msg, _close_schedule_period, bot)
            return

        date = start_date
        while date <= end_date:
            day_start, day_end = _day_bounds(date)
            database.add_schedule_block(day_start.isoformat(), day_end.isoformat(), "Период закрыт администратором")
            date += dt.timedelta(days=1)
        bot.send_message(message.chat.id, f"Период {start_text} - {end_text} закрыт ✅")

    @bot.message_handler(commands=["admin"])
    def handle_admin_command(message):
        if not _guard(bot, message):
            return
        bot.send_message(message.chat.id, texts.ADMIN_MENU_TITLE, reply_markup=admin_main_kb())

    @bot.callback_query_handler(func=lambda c: c.data == "admin_home")
    def handle_admin_home(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, texts.ADMIN_MENU_TITLE, reply_markup=admin_main_kb())

    # ------------------------------------------------------------------
    # МАТЕРИАЛЫ
    # ------------------------------------------------------------------

    @bot.callback_query_handler(func=lambda c: c.data == "admin_materials")
    def handle_admin_materials(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📚 Материалы", reply_markup=admin_materials_menu_kb())

    @bot.callback_query_handler(func=lambda c: c.data == "admin_material_add")
    def handle_admin_material_add(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, texts.ADMIN_MATERIAL_ADD_TITLE)
        bot.register_next_step_handler(msg, _collect_title, bot, {})

    def _collect_title(message, bot, data):
        if not is_admin(message.from_user.id):
            return
        data["title"] = message.text
        msg = bot.send_message(
            message.chat.id,
            texts.ADMIN_MATERIAL_ADD_SLUG.format(bot_username=config.BOT_USERNAME or "your_bot"),
        )
        bot.register_next_step_handler(msg, _collect_slug, bot, data)

    def _collect_slug(message, bot, data):
        if not is_admin(message.from_user.id):
            return
        slug = message.text.strip()
        if not is_valid_slug(slug):
            msg = bot.send_message(message.chat.id, texts.ADMIN_MATERIAL_ADD_SLUG_INVALID)
            bot.register_next_step_handler(msg, _collect_slug, bot, data)
            return
        if database.slug_exists(slug):
            msg = bot.send_message(message.chat.id, texts.ADMIN_MATERIAL_ADD_SLUG_TAKEN)
            bot.register_next_step_handler(msg, _collect_slug, bot, data)
            return
        data["slug"] = slug
        msg = bot.send_message(message.chat.id, texts.ADMIN_MATERIAL_ADD_DESC)
        bot.register_next_step_handler(msg, _collect_description, bot, data)

    def _collect_description(message, bot, data):
        if not is_admin(message.from_user.id):
            return
        data["description"] = message.text
        msg = bot.send_message(message.chat.id, texts.ADMIN_MATERIAL_ADD_FILE)
        bot.register_next_step_handler(msg, _collect_file, bot, data)

    def _collect_file(message, bot, data):
        if not is_admin(message.from_user.id):
            return
        try:
            if message.content_type == "document":
                file_id = message.document.file_id
                file_type = "document"
            elif message.content_type == "photo":
                file_id = message.photo[-1].file_id
                file_type = "photo"
            else:
                msg = bot.send_message(
                    message.chat.id,
                    "Нужен файл (документ, PDF или фото). Отправь файл ещё раз:",
                )
                bot.register_next_step_handler(msg, _collect_file, bot, data)
                return

            database.add_material(data["slug"], data["title"], data["description"], file_id, file_type)
            link = deep_link(data["slug"])
            bot.send_message(message.chat.id, texts.ADMIN_MATERIAL_ADDED.format(link=link))
        except Exception:
            logger.exception("Ошибка при добавлении материала")
            safe_call(bot.send_message, message.chat.id, texts.GENERIC_ERROR)

    @bot.callback_query_handler(func=lambda c: c.data == "admin_material_list")
    def handle_admin_material_list(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        materials = database.list_all_materials()
        if not materials:
            bot.send_message(call.message.chat.id, texts.ADMIN_NO_MATERIALS)
            return
        bot.send_message(call.message.chat.id, "Список материалов:", reply_markup=admin_materials_list_kb(materials))

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_material_open:"))
    def handle_admin_material_open(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        material_id = int(call.data.split(":", 1)[1])
        material = database.get_material_by_id(material_id)
        if not material:
            bot.send_message(call.message.chat.id, "Материал не найден.")
            return
        link = deep_link(material["slug"])
        status = "активен ✅" if material["is_active"] else "скрыт 🚫"
        text = (
            f"{material['title']}\n\n"
            f"Slug: {material['slug']}\n"
            f"Статус: {status}\n"
            f"Описание: {material['description'] or '—'}\n\n"
            f"Deep-link:\n{link}"
        )
        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=admin_material_detail_kb(material_id, bool(material["is_active"])),
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_material_add_file:"))
    def handle_admin_material_add_file(call):
        if not _guard(bot, call):
            return
        material_id = int(call.data.split(":", 1)[1])
        if not database.get_material_by_id(material_id):
            bot.answer_callback_query(call.id, "Материал не найден.", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Отправь второй файл для этого материала.")
        bot.register_next_step_handler(msg, _save_additional_material_file, bot, material_id)

    def _save_additional_material_file(message, bot, material_id):
        if not is_admin(message.from_user.id):
            return
        if message.content_type == "document":
            file_id = message.document.file_id
            file_type = "document"
            file_name = message.document.file_name
        elif message.content_type == "photo":
            file_id = message.photo[-1].file_id
            file_type = "photo"
            file_name = None
        else:
            msg = bot.send_message(message.chat.id, "Нужен документ или фото. Отправь файл ещё раз.")
            bot.register_next_step_handler(msg, _save_additional_material_file, bot, material_id)
            return
        database.add_material_file(material_id, file_id, file_type, file_name)
        bot.send_message(message.chat.id, "Второй файл добавлен ✅")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_material_edit_title:"))
    def handle_admin_material_edit_title(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        material_id = int(call.data.split(":", 1)[1])
        msg = bot.send_message(call.message.chat.id, texts.ADMIN_EDIT_TITLE_PROMPT)
        bot.register_next_step_handler(msg, _apply_title_edit, bot, material_id)

    def _apply_title_edit(message, bot, material_id):
        if not is_admin(message.from_user.id):
            return
        if message.text and message.text.strip() == "/skip":
            bot.send_message(message.chat.id, texts.ADMIN_MATERIAL_UPDATED)
            return
        database.update_material(material_id, title=message.text)
        bot.send_message(message.chat.id, texts.ADMIN_MATERIAL_UPDATED)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_material_edit_desc:"))
    def handle_admin_material_edit_desc(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        material_id = int(call.data.split(":", 1)[1])
        msg = bot.send_message(call.message.chat.id, texts.ADMIN_EDIT_DESC_PROMPT)
        bot.register_next_step_handler(msg, _apply_desc_edit, bot, material_id)

    def _apply_desc_edit(message, bot, material_id):
        if not is_admin(message.from_user.id):
            return
        if message.text and message.text.strip() == "/skip":
            bot.send_message(message.chat.id, texts.ADMIN_MATERIAL_UPDATED)
            return
        database.update_material(material_id, description=message.text)
        bot.send_message(message.chat.id, texts.ADMIN_MATERIAL_UPDATED)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_material_delete:"))
    def handle_admin_material_delete(call):
        if not _guard(bot, call):
            return
        material_id = int(call.data.split(":", 1)[1])
        database.deactivate_material(material_id)
        bot.answer_callback_query(call.id, texts.ADMIN_MATERIAL_DELETED)
        safe_call(bot.send_message, call.message.chat.id, texts.ADMIN_MATERIAL_DELETED)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_material_restore:"))
    def handle_admin_material_restore(call):
        if not _guard(bot, call):
            return
        material_id = int(call.data.split(":", 1)[1])
        database.activate_material(material_id)
        bot.answer_callback_query(call.id, "Материал восстановлен ✅")
        safe_call(bot.send_message, call.message.chat.id, "Материал восстановлен ✅")

    # ------------------------------------------------------------------
    # ОПЛАТЫ
    # ------------------------------------------------------------------

    @bot.callback_query_handler(func=lambda c: c.data == "admin_payments")
    def handle_admin_payments(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "💳 Оплаты", reply_markup=admin_payments_menu_kb())

    def _payment_summary_text(payment, user):
        return (
            f"Имя: {user_display_name(user)}\n"
            f"Username: @{user['username'] or '—'}\n"
            f"Telegram ID: {user['telegram_id']}\n"
            f"Сумма: {payment['amount']} ₸\n"
            f"Источник: {user['source'] or '—'}\n"
            f"Дата: {payment['created_at']}"
        )

    @bot.callback_query_handler(func=lambda c: c.data in (
        "admin_payments_pending", "admin_payments_confirmed", "admin_payments_rejected"
    ))
    def handle_admin_payments_list(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        status = call.data.split("_")[-1]
        payments = database.list_payments_by_status(status)
        if not payments:
            bot.send_message(call.message.chat.id, texts.ADMIN_NO_PAYMENTS)
            return
        for payment in payments:
            user = database.get_user_by_id(payment["user_id"])
            if not user:
                continue
            text = _payment_summary_text(payment, user)
            kb = admin_payment_kb(payment["id"]) if status == "pending" else None
            try:
                if payment["receipt_file_id"]:
                    if payment["receipt_file_type"] == "photo":
                        bot.send_photo(call.message.chat.id, payment["receipt_file_id"], caption=text, reply_markup=kb)
                    else:
                        bot.send_document(call.message.chat.id, payment["receipt_file_id"], caption=text, reply_markup=kb)
                else:
                    bot.send_message(call.message.chat.id, text, reply_markup=kb)
            except Exception:
                logger.exception("Ошибка при показе платежа администратору")

    # ------------------------------------------------------------------
    # ЗАПИСИ
    # ------------------------------------------------------------------

    @bot.callback_query_handler(func=lambda c: c.data == "admin_appointments")
    def handle_admin_appointments(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📅 Записи и анкеты", reply_markup=admin_appointments_menu_kb())

    @bot.callback_query_handler(func=lambda c: c.data in ("admin_appointments_upcoming", "admin_appointments_completed"))
    def handle_admin_appointments_list(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        if call.data == "admin_appointments_upcoming":
            appointments = database.list_upcoming_appointments(limit=50)
            empty_text = texts.ADMIN_NO_APPOINTMENTS
        else:
            appointments = database.list_appointments_by_status("completed", limit=50)
            empty_text = "Завершённых диагностик пока нет."
        if not appointments:
            bot.send_message(call.message.chat.id, empty_text, reply_markup=admin_back_kb("admin_appointments"))
            return
        for appt in appointments:
            user = database.get_user_by_id(appt["user_id"])
            brief = database.get_uploaded_brief_for_user(appt["user_id"]) if user else None
            text = (
                f"Имя: {user_display_name(user) if user else '—'}\n"
                f"Username: @{user['username'] or '—' if user else '—'}\n"
                f"Начало: {appt['start_time']}\n"
                f"Окончание: {appt['end_time']}\n"
            )
            if brief:
                text += f"\nБриф: {brief['file_name']}"
            bot.send_message(call.message.chat.id, text)
            if brief:
                safe_call(bot.send_document, call.message.chat.id, brief["file_id"], caption=brief["file_name"])
        bot.send_message(call.message.chat.id, "Это все записи в списке.", reply_markup=admin_back_kb("admin_appointments"))

    @bot.callback_query_handler(func=lambda c: c.data == "admin_brief_template")
    def handle_admin_brief_template(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Отправь шаблон брифа в формате .xlsx.")
        bot.register_next_step_handler(msg, _save_brief_template, bot)

    def _save_brief_template(message, bot):
        if not is_admin(message.from_user.id):
            return
        if message.content_type != "document" or not message.document.file_name.lower().endswith(".xlsx"):
            msg = bot.send_message(message.chat.id, "Нужен файл Excel в формате .xlsx. Отправь шаблон ещё раз.")
            bot.register_next_step_handler(msg, _save_brief_template, bot)
            return
        database.set_setting("brief_template_file_id", message.document.file_id)
        database.set_setting("brief_template_file_name", message.document.file_name)
        bot.send_message(message.chat.id, "Шаблон брифа сохранён ✅")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_appt_complete:"))
    def handle_admin_appt_complete(call):
        if not _guard(bot, call):
            return
        appointment_id = int(call.data.split(":", 1)[1])
        appointment = database.get_appointment_by_id(appointment_id)
        if not appointment or appointment["status"] != "confirmed":
            bot.answer_callback_query(call.id, "Эта запись уже не активна.", show_alert=True)
            return
        database.complete_appointment(appointment_id)
        database.set_client_status(appointment["user_id"], "diagnostics_completed")
        from utils.scheduler import cancel_reminders
        cancel_reminders(appointment_id)
        user = database.get_user_by_id(appointment["user_id"])
        bot.answer_callback_query(call.id, "Диагностика отмечена как завершённая.")
        bot.send_message(call.message.chat.id, "Статус клиента изменён на diagnostics_completed.")
        safe_call(bot.send_message, user["telegram_id"], texts.APPOINTMENT_COMPLETED_CLIENT)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_appt_reschedule:"))
    def handle_admin_appt_reschedule(call):
        if not _guard(bot, call):
            return
        appointment_id = int(call.data.split(":", 1)[1])
        appointment = database.get_appointment_by_id(appointment_id)
        if not appointment or appointment["status"] != "confirmed":
            bot.answer_callback_query(call.id, "Эта запись уже не активна.", show_alert=True)
            return
        from bot.handlers.calendar import send_admin_reschedule_date_choice
        bot.answer_callback_query(call.id)
        send_admin_reschedule_date_choice(bot, call.message.chat.id, appointment_id)

    # ------------------------------------------------------------------
    # ПОЛЬЗОВАТЕЛИ
    # ------------------------------------------------------------------

    @bot.callback_query_handler(func=lambda c: c.data == "admin_users")
    def handle_admin_users(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        users = database.list_users(limit=20)
        if not users:
            bot.send_message(call.message.chat.id, texts.ADMIN_NO_USERS, reply_markup=admin_back_kb("admin_home"))
            return
        lines = ["👥 Последние пользователи:\n"]
        for u in users:
            payment = database.get_confirmed_payment_for_user(u["id"])
            appointment = database.get_active_appointment_for_user(u["id"])
            lines.append(
                f"— {user_display_name(u)} (@{u['username'] or '—'})\n"
                f"  Источник: {u['source'] or '—'} | Первый материал: {u['first_material'] or '—'}\n"
                f"  Оплата: {'подтверждена ✅' if payment else 'нет'} | "
                f"Запись: {appointment['start_time'] if appointment else 'нет'}"
            )
        bot.send_message(call.message.chat.id, "\n\n".join(lines), reply_markup=admin_back_kb("admin_home"))

    # ------------------------------------------------------------------
    # СТАТИСТИКА
    # ------------------------------------------------------------------

    @bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
    def handle_admin_stats(call):
        if not _guard(bot, call):
            return
        bot.answer_callback_query(call.id)
        total_users = database.count_users()
        sources = database.list_distinct_sources()
        source_lines = "\n".join(
            f"{s} — {database.count_users_by_source(s)}" for s in sources
        ) or "—"
        materials_given = database.count_event("material_received")
        diag_clicks = database.count_event("diagnostics_opened")
        receipts_sent = database.count_payments_with_receipt()
        confirmed = database.count_payments_by_status("confirmed")
        appointments = database.count_appointments()

        text = (
            "📊 Статистика\n\n"
            f"Пользователей: {total_users}\n\n"
            f"Материалы:\n{source_lines}\n\n"
            f"Всего материалов выдано: {materials_given}\n\n"
            f"Диагностика:\nнажали — {diag_clicks}\n\n"
            f"Чеки:\nотправлено — {receipts_sent}\nподтверждено — {confirmed}\n\n"
            f"Записей: {appointments}"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=admin_back_kb("admin_home"))
