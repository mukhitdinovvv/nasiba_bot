import logging

import database
from bot.messages import texts
from services import calendar_service
from utils.helpers import safe_call

logger = logging.getLogger("nasiba_bot")


def register(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "brief_start")
    def handle_brief_start(call):
        try:
            bot.answer_callback_query(call.id)
            user = database.get_or_create_user(call.from_user)

            confirmed = database.get_confirmed_payment_for_user(user["id"])
            if not confirmed:
                bot.send_message(
                    call.message.chat.id,
                    "Сначала нужно оплатить диагностику — нажми «🔎 Диагностика» в главном меню.",
                )
                return

            existing_brief = database.get_uploaded_brief_for_user(user["id"])
            if existing_brief:
                from bot.handlers.calendar import send_date_choice
                bot.send_message(call.message.chat.id, texts.BRIEF_ALREADY_RECEIVED)
                send_date_choice(bot, call.message.chat.id)
                return

            template_file_id = database.get_setting("brief_template_file_id")
            template_file_name = database.get_setting("brief_template_file_name") or "Бриф.xlsx"
            if not template_file_id:
                bot.send_message(call.message.chat.id, texts.BRIEF_TEMPLATE_UNAVAILABLE)
                return

            bot.send_document(call.message.chat.id, template_file_id, caption=texts.BRIEF_INTRO)
            msg = bot.send_message(call.message.chat.id, texts.BRIEF_UPLOAD_PROMPT)
            bot.register_next_step_handler(msg, _receive_brief_file, bot)
        except Exception:
            logger.exception("Ошибка при старте брифа")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)

    def _receive_brief_file(message, bot):
        try:
            if message.content_type != "document":
                msg = bot.send_message(message.chat.id, texts.BRIEF_FILE_REQUIRED)
                bot.register_next_step_handler(msg, _receive_brief_file, bot)
                return
            user = database.get_or_create_user(message.from_user)
            document = message.document
            if not document.file_name.lower().endswith(".xlsx"):
                msg = bot.send_message(message.chat.id, texts.BRIEF_FILE_REQUIRED)
                bot.register_next_step_handler(msg, _receive_brief_file, bot)
                return
            database.create_file_brief(
                user["id"], document.file_id, "document", document.file_name, None
            )
            database.log_event(user["id"], "brief_completed")

            from bot.handlers.calendar import send_date_choice
            bot.send_message(message.chat.id, texts.BRIEF_DONE)
            send_date_choice(bot, message.chat.id)
        except Exception:
            logger.exception("Ошибка при сохранении брифа")
            safe_call(bot.send_message, message.chat.id, texts.GENERIC_ERROR)
