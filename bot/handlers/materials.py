import logging

import config
import database
from bot.keyboards.materials import (
    materials_list_kb,
    after_material_kb,
    channel_subscription_kb,
    channel_subscription_start_kb,
)
from bot.messages import texts
from utils.helpers import safe_call
from utils.scheduler import schedule_material_follow_up

logger = logging.getLogger("nasiba_bot")


def _is_channel_member(bot, telegram_id: int) -> bool:
    channel_id = config.TELEGRAM_CHANNEL_ID or database.get_setting("telegram_channel_id")
    if not channel_id:
        return False
    member = bot.get_chat_member(int(channel_id), telegram_id)
    return member.status not in ("left", "kicked")


def request_channel_subscription(bot, chat_id: int, slug: str):
    bot.send_message(
        chat_id,
        texts.CHANNEL_SUBSCRIPTION_REQUIRED,
        reply_markup=channel_subscription_kb(slug),
    )


def request_channel_subscription_start(bot, chat_id: int):
    bot.send_message(
        chat_id,
        texts.CHANNEL_SUBSCRIPTION_REQUIRED_START,
        reply_markup=channel_subscription_start_kb(),
    )


def _send_material_file(bot, chat_id, material):
    file_type = material["file_type"]
    file_id = material["file_id"]
    caption = material["title"]
    if file_type == "document":
        bot.send_document(chat_id, file_id, caption=caption)
    elif file_type == "photo":
        bot.send_photo(chat_id, file_id, caption=caption)
    else:
        bot.send_document(chat_id, file_id, caption=caption)


def _send_material_files(bot, chat_id, material):
    files = database.list_material_files(material["id"])
    if not files:
        _send_material_file(bot, chat_id, material)
        return
    for index, file_row in enumerate(files, start=1):
        caption = material["title"] if len(files) == 1 else f"{material['title']} ({index}/{len(files)})"
        if file_row["file_type"] == "photo":
            bot.send_photo(chat_id, file_row["file_id"], caption=caption)
        else:
            bot.send_document(chat_id, file_row["file_id"], caption=caption)


def deliver_material_to_user(bot, chat_id, user_row, slug: str):
    """Универсальная доставка материала по slug — работает для любого
    материала, который есть в базе, без отдельных if/else на каждый slug."""
    try:
        material = database.get_material_by_slug(slug)
        if not material:
            safe_call(bot.send_message, chat_id, texts.MATERIAL_NOT_FOUND)
            return
        if material["description"]:
            bot.send_message(chat_id, material["description"])
        _send_material_files(bot, chat_id, material)
        database.log_event(user_row["id"], "material_received", slug)
        schedule_material_follow_up(bot, user_row["telegram_id"])
    except Exception:
        logger.exception("Ошибка при отправке материала %s", slug)
        safe_call(bot.send_message, chat_id, texts.GENERIC_ERROR)


def register(bot):

    @bot.my_chat_member_handler(func=lambda update: update.chat.type == "channel")
    def handle_bot_channel_membership(update):
        try:
            status = update.new_chat_member.status
            if status not in ("administrator", "creator"):
                return
            database.set_setting("telegram_channel_id", str(update.chat.id))
            logger.info("Канал для проверки подписки сохранён: %s", update.chat.id)
        except Exception:
            logger.exception("Не удалось сохранить ID канала для проверки подписки")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("channel_check:"))
    def handle_channel_check(call):
        try:
            slug = call.data.split(":", 1)[1]
            if not _is_channel_member(bot, call.from_user.id):
                bot.answer_callback_query(call.id, texts.CHANNEL_SUBSCRIPTION_NOT_CONFIRMED, show_alert=True)
                return
            user = database.get_or_create_user(call.from_user, source=slug)
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, texts.AFTER_SUBSCRIPTION)
            deliver_material_to_user(bot, call.message.chat.id, user, slug)
        except Exception:
            logger.exception("Ошибка проверки подписки на канал")
            safe_call(bot.answer_callback_query, call.id, texts.CHANNEL_CHECK_UNAVAILABLE, show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data == "channel_check_start")
    def handle_channel_check_start(call):
        try:
            if not _is_channel_member(bot, call.from_user.id):
                bot.answer_callback_query(call.id, texts.CHANNEL_SUBSCRIPTION_NOT_CONFIRMED, show_alert=True)
                return
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, texts.AFTER_SUBSCRIPTION_START)
            from bot.handlers.start import send_main_menu
            send_main_menu(bot, call.message.chat.id)
        except Exception:
            logger.exception("Ошибка проверки подписки на канал при /start")
            safe_call(bot.answer_callback_query, call.id, texts.CHANNEL_CHECK_UNAVAILABLE, show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data == "menu_materials")
    def handle_menu_materials(call):
        try:
            bot.answer_callback_query(call.id)
            materials = database.list_active_materials()
            if not materials:
                bot.send_message(call.message.chat.id, texts.NO_MATERIALS_YET)
                return
            bot.send_message(
                call.message.chat.id,
                texts.MATERIALS_INTRO,
                reply_markup=materials_list_kb(materials),
            )
        except Exception:
            logger.exception("Ошибка при показе списка материалов")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("material_get:"))
    def handle_material_get(call):
        try:
            bot.answer_callback_query(call.id)
            slug = call.data.split(":", 1)[1]
            user = database.get_or_create_user(call.from_user, source=slug)
            database.set_user_source_and_first_material(call.from_user.id, slug)
            deliver_material_to_user(bot, call.message.chat.id, user, slug)
        except Exception:
            logger.exception("Ошибка при получении материала по кнопке")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)
