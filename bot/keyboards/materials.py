from telebot import types

import config
from bot.keyboards.common import back_to_menu_button


def materials_list_kb(materials) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for m in materials:
        kb.add(types.InlineKeyboardButton(m["title"], callback_data=f"material_get:{m['slug']}"))
    kb.add(back_to_menu_button())
    return kb


def after_material_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔎 Диагностика", callback_data="menu_diagnostics"),
        types.InlineKeyboardButton("🎁 Другие материалы", callback_data="menu_materials"),
        back_to_menu_button(),
    )
    return kb


def channel_subscription_kb(slug: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    if config.TELEGRAM_CHANNEL_URL:
        kb.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=config.TELEGRAM_CHANNEL_URL))
    kb.add(types.InlineKeyboardButton("✅ Проверить подписку", callback_data=f"channel_check:{slug}"))
    return kb


def channel_subscription_start_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    if config.TELEGRAM_CHANNEL_URL:
        kb.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=config.TELEGRAM_CHANNEL_URL))
    kb.add(types.InlineKeyboardButton("✅ Проверить подписку", callback_data="channel_check_start"))
    return kb


def diagnostics_teaser_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔎 Пройти диагностику", callback_data="menu_diagnostics"))
    return kb
