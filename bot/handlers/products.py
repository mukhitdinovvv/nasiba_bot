import logging

from telebot import types

import config
import database
from bot.keyboards.common import back_to_menu_button
from bot.messages import texts
from utils.helpers import safe_call

logger = logging.getLogger("nasiba_bot")


def _product_kb(button_text: str, callback_data: str, with_back: bool = False) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    if with_back:
        kb.add(back_to_menu_button())
    return kb


def register(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "menu_products")
    def handle_menu_products(call):
        try:
            bot.answer_callback_query(call.id)
            user = database.get_or_create_user(call.from_user)
            database.log_event(user["id"], "products_opened")

            bot.send_message(call.message.chat.id, texts.PRODUCTS_INTRO)
            bot.send_message(
                call.message.chat.id,
                texts.PRODUCT_1,
                reply_markup=_product_kb("Записаться на консультацию", "product_request:1"),
            )
            bot.send_message(
                call.message.chat.id,
                texts.PRODUCT_2,
                reply_markup=_product_kb("Найти свой почерк", "product_request:2"),
            )
            bot.send_message(
                call.message.chat.id,
                texts.PRODUCT_3,
                reply_markup=_product_kb("Подать заявку", "product_request:3", with_back=True),
            )
        except Exception:
            logger.exception("Ошибка при показе продуктов")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("product_request:"))
    def handle_product_request(call):
        try:
            bot.answer_callback_query(call.id)
            product_num = call.data.split(":", 1)[1]
            user = database.get_or_create_user(call.from_user)
            database.log_event(user["id"], "product_request", product_num)

            bot.send_message(call.message.chat.id, texts.PRODUCT_REQUEST_SENT)
            if config.ADMIN_TELEGRAM_ID:
                names = {
                    "1": "Консультация для SMM-специалистов",
                    "2": "«Твой почерк»",
                    "3": "Индивидуальное наставничество",
                }
                text = (
                    "💼 Заявка на продукт: {product}\n\n"
                    "Имя: {name}\nUsername: @{username}\nTelegram ID: {tg_id}"
                ).format(
                    product=names.get(product_num, product_num),
                    name=call.from_user.first_name or "",
                    username=call.from_user.username or "—",
                    tg_id=call.from_user.id,
                )
                safe_call(bot.send_message, config.ADMIN_TELEGRAM_ID, text)
        except Exception:
            logger.exception("Ошибка при заявке на продукт")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)
