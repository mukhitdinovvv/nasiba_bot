from telebot import types

import config
from bot.keyboards.common import back_to_menu_button


def diagnostics_menu_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("💳 Записаться за 3 000 ₸", callback_data="diag_pay"),
        types.InlineKeyboardButton("✅ Что я получу", callback_data="diag_what"),
        types.InlineKeyboardButton("💬 Задать вопрос", callback_data="menu_ask"),
        back_to_menu_button(),
    )
    return kb


def diagnostics_what_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("💳 Записаться за 3 000 ₸", callback_data="diag_pay"))
    kb.add(back_to_menu_button())
    return kb


def payment_link_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💳 Оплатить 3 000 ₸", url=config.KASPI_PAYMENT_URL))
    return kb


def admin_payment_kb(payment_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"pay_confirm:{payment_id}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"pay_reject:{payment_id}"),
    )
    return kb


def start_brief_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📝 Заполнить бриф", callback_data="brief_start"))
    return kb
