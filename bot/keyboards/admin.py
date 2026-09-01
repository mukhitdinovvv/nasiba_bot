from telebot import types


def admin_main_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📚 Материалы", callback_data="admin_materials"),
        types.InlineKeyboardButton("💳 Оплаты", callback_data="admin_payments"),
        types.InlineKeyboardButton("📅 Записи", callback_data="admin_appointments"),
        types.InlineKeyboardButton("🗓 Расписание", callback_data="admin_schedule"),
        types.InlineKeyboardButton("📄 Шаблон брифа", callback_data="admin_brief_template"),
        types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
    )
    return kb


def admin_materials_menu_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("➕ Добавить материал", callback_data="admin_material_add"),
        types.InlineKeyboardButton("📚 Список материалов", callback_data="admin_material_list"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_home"),
    )
    return kb


def admin_materials_list_kb(materials) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for m in materials:
        mark = "✅" if m["is_active"] else "🚫"
        kb.add(types.InlineKeyboardButton(
            f"{mark} {m['title']} ({m['slug']})", callback_data=f"admin_material_open:{m['id']}"
        ))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_materials"))
    return kb


def admin_material_detail_kb(material_id: int, is_active: bool) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("➕ Добавить файл", callback_data=f"admin_material_add_file:{material_id}"),
        types.InlineKeyboardButton("✏️ Редактировать название", callback_data=f"admin_material_edit_title:{material_id}"),
        types.InlineKeyboardButton("✏️ Редактировать описание", callback_data=f"admin_material_edit_desc:{material_id}"),
    )
    if is_active:
        kb.add(types.InlineKeyboardButton("🗑 Удалить (скрыть)", callback_data=f"admin_material_delete:{material_id}"))
    else:
        kb.add(types.InlineKeyboardButton("♻️ Восстановить", callback_data=f"admin_material_restore:{material_id}"))
    kb.add(types.InlineKeyboardButton("⬅️ К списку", callback_data="admin_material_list"))
    return kb


def admin_payments_menu_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("⏳ Ожидают проверки", callback_data="admin_payments_pending"),
        types.InlineKeyboardButton("✅ Подтверждённые", callback_data="admin_payments_confirmed"),
        types.InlineKeyboardButton("❌ Отклонённые", callback_data="admin_payments_rejected"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_home"),
    )
    return kb


def admin_appointments_menu_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📅 Ближайшие записи", callback_data="admin_appointments_upcoming"),
        types.InlineKeyboardButton("✅ Завершённые диагностики", callback_data="admin_appointments_completed"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_home"),
    )
    return kb


def admin_schedule_kb(dates) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    for date, label in dates:
        kb.add(types.InlineKeyboardButton(label, callback_data=f"admin_schedule_date:{date}"))
    kb.add(types.InlineKeyboardButton("🔒 Закрыть период", callback_data="admin_schedule_close_period"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_home"))
    return kb


def admin_schedule_day_kb(date: str, is_closed: bool) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    if is_closed:
        kb.add(types.InlineKeyboardButton("🔓 Открыть день", callback_data=f"admin_schedule_open:{date}"))
    else:
        kb.add(
            types.InlineKeyboardButton("🔒 Закрыть весь день", callback_data=f"admin_schedule_close_day:{date}"),
            types.InlineKeyboardButton("🔒 Закрыть время", callback_data=f"admin_schedule_close_time:{date}"),
        )
    kb.add(types.InlineKeyboardButton("⬅️ К датам", callback_data="admin_schedule"))
    return kb


def admin_back_kb(callback_data: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=callback_data))
    return kb
