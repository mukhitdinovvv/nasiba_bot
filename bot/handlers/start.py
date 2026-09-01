import logging

from telebot import types

import config
import database
from bot.keyboards.main_menu import main_menu_kb, consent_data_kb, consent_marketing_kb
from bot.messages import texts
from utils.helpers import safe_call, is_valid_slug

logger = logging.getLogger("nasiba_bot")

# Временное хранилище slug'а из deep-link, пока пользователь проходит согласие.
# Ключ: telegram_id. Хранится только в памяти — это нормально для такого
# небольшого шага воронки (в худшем случае пользователь просто увидит
# главное меню вместо материала, если бот перезапустится в этот момент).
_PENDING_DEEPLINK = {}


def send_main_menu(bot, chat_id, text: str = None):
    safe_call(
        bot.send_message,
        chat_id,
        text or texts.WELCOME,
        reply_markup=main_menu_kb(),
    )


def _needs_consent(user_row) -> bool:
    return not user_row["consent_data"]


def register(bot):

    @bot.message_handler(commands=["start"])
    def handle_start(message):
        try:
            tg_user = message.from_user
            payload = message.text.split(maxsplit=1)
            slug = payload[1].strip() if len(payload) > 1 else None
            if slug and not is_valid_slug(slug):
                slug = None

            user = database.get_or_create_user(tg_user, source=slug)
            if slug:
                database.set_user_source_and_first_material(tg_user.id, slug)
                database.log_event(user["id"], "deep_link_open", slug)

            if _needs_consent(user):
                if slug:
                    _PENDING_DEEPLINK[tg_user.id] = slug
                bot.send_message(
                    message.chat.id,
                    texts.CONSENT_DATA_REQUEST,
                    reply_markup=consent_data_kb(),
                )
                return

            if slug:
                from bot.handlers.materials import request_channel_subscription
                request_channel_subscription(bot, message.chat.id, slug)
            else:
                from bot.handlers.materials import _is_channel_member, request_channel_subscription_start
                if _is_channel_member(bot, tg_user.id):
                    send_main_menu(bot, message.chat.id)
                else:
                    request_channel_subscription_start(bot, message.chat.id)
        except Exception:
            logger.exception("Ошибка в /start")
            safe_call(bot.send_message, message.chat.id, texts.GENERIC_ERROR)

    @bot.callback_query_handler(func=lambda c: c.data == "consent_data_ok")
    def handle_consent_data(call):
        try:
            database.set_consent_data(call.from_user.id)
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                texts.CONSENT_MARKETING_REQUEST,
                reply_markup=consent_marketing_kb(),
            )
        except Exception:
            logger.exception("Ошибка при подтверждении согласия на данные")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data == "consent_marketing_ok")
    def handle_consent_marketing(call):
        try:
            database.set_consent_marketing(call.from_user.id, True)
            bot.answer_callback_query(call.id)
            user = database.get_user_by_telegram_id(call.from_user.id)
            slug = _PENDING_DEEPLINK.pop(call.from_user.id, None)
            bot.send_message(call.message.chat.id, texts.CONSENT_THANKS)
            if slug:
                from bot.handlers.materials import request_channel_subscription
                request_channel_subscription(bot, call.message.chat.id, slug)
            else:
                from bot.handlers.materials import _is_channel_member, request_channel_subscription_start
                if _is_channel_member(bot, call.from_user.id):
                    send_main_menu(bot, call.message.chat.id)
                else:
                    request_channel_subscription_start(bot, call.message.chat.id)
        except Exception:
            logger.exception("Ошибка при подтверждении согласия на рассылку")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data == "menu_home")
    def handle_menu_home(call):
        bot.answer_callback_query(call.id)
        send_main_menu(bot, call.message.chat.id)

    @bot.callback_query_handler(func=lambda c: c.data == "menu_ask")
    def handle_menu_ask(call):
        try:
            bot.answer_callback_query(call.id)
            msg = bot.send_message(call.message.chat.id, texts.ASK_QUESTION_PROMPT)
            bot.register_next_step_handler(msg, _forward_question, bot)
        except Exception:
            logger.exception("Ошибка в разделе «Задать вопрос»")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)

    def _forward_question(message, bot):
        try:
            user = database.get_or_create_user(message.from_user)
            database.log_event(user["id"], "question_asked", message.text)
            if config.ADMIN_TELEGRAM_ID:
                admin_text = (
                    f"💬 Новый вопрос\n\n"
                    f"От: {message.from_user.first_name or ''} (@{message.from_user.username or '—'})\n"
                    f"Telegram ID: {message.from_user.id}\n\n"
                    f"{message.text}"
                )
                safe_call(bot.send_message, config.ADMIN_TELEGRAM_ID, admin_text)
            bot.send_message(message.chat.id, texts.QUESTION_FORWARDED)
        except Exception:
            logger.exception("Ошибка при пересылке вопроса администратору")
            safe_call(bot.send_message, message.chat.id, texts.GENERIC_ERROR)
