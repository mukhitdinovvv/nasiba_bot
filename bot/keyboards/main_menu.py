from telebot import types


def main_menu_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🎁 Бесплатные материалы", callback_data="menu_materials"),
        types.InlineKeyboardButton("🔎 Диагностика — 3 000 ₸", callback_data="menu_diagnostics"),
        types.InlineKeyboardButton("💼 Мои продукты", callback_data="menu_products"),
        types.InlineKeyboardButton("💬 Задать вопрос", callback_data="menu_ask"),
    )
    return kb


def consent_data_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Согласна", callback_data="consent_data_ok"))
    return kb


def consent_marketing_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Разрешаю", callback_data="consent_marketing_ok"))
    return kb
