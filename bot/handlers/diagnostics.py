import logging
import os

from telebot import types

import database
from bot.keyboards.payments import diagnostics_menu_kb, diagnostics_what_kb
from bot.messages import texts
from utils.helpers import safe_call

logger = logging.getLogger("nasiba_bot")

# Фото с описанием диагностики лежат в корне проекта.
_DIAGNOSTICS_PHOTOS = ["1.png", "2.png"]


def register(bot):

    def _get_diagnostics_media():
        """Отдаёт фото по кэшированному file_id, если он уже есть, иначе
        загружает файл с диска (и после первой отправки кэширует file_id,
        чтобы больше не перезаливать тяжёлые PNG на каждый клик)."""
        media = []
        open_files = []
        for i, path in enumerate(_DIAGNOSTICS_PHOTOS):
            setting_key = f"diagnostics_photo_file_id_{i}"
            cached_file_id = database.get_setting(setting_key)
            caption = texts.DIAGNOSTICS_MAIN if i == 0 else None
            if cached_file_id:
                media.append(types.InputMediaPhoto(cached_file_id, caption=caption))
            elif os.path.exists(path):
                f = open(path, "rb")
                open_files.append(f)
                media.append(types.InputMediaPhoto(f, caption=caption))
        return media, open_files

    def _cache_uploaded_file_ids(messages):
        for i, msg in enumerate(messages):
            if msg.photo:
                database.set_setting(f"diagnostics_photo_file_id_{i}", msg.photo[-1].file_id)

    @bot.callback_query_handler(func=lambda c: c.data == "menu_diagnostics")
    def handle_menu_diagnostics(call):
        try:
            safe_call(bot.answer_callback_query, call.id)
            user = database.get_or_create_user(call.from_user)
            database.log_event(user["id"], "diagnostics_opened")

            media, open_files = _get_diagnostics_media()
            if media:
                try:
                    sent_messages = bot.send_media_group(call.message.chat.id, media)
                    _cache_uploaded_file_ids(sent_messages)
                finally:
                    for f in open_files:
                        f.close()
                bot.send_message(
                    call.message.chat.id,
                    texts.DIAGNOSTICS_CHOOSE_ACTION,
                    reply_markup=diagnostics_menu_kb(),
                )
            else:
                bot.send_message(
                    call.message.chat.id,
                    texts.DIAGNOSTICS_MAIN,
                    reply_markup=diagnostics_menu_kb(),
                )
        except Exception:
            logger.exception("Ошибка при показе меню диагностики")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data == "diag_what")
    def handle_diag_what(call):
        try:
            safe_call(bot.answer_callback_query, call.id)
            bot.send_message(
                call.message.chat.id,
                texts.DIAGNOSTICS_WHAT_YOU_GET,
                reply_markup=diagnostics_what_kb(),
            )
        except Exception:
            logger.exception("Ошибка в разделе «Что я получу»")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)
