import logging

import config
import database
from bot.keyboards.payments import payment_link_kb, admin_payment_kb, start_brief_kb
from bot.messages import texts
from services import payment_service
from utils.helpers import safe_call, user_display_name

logger = logging.getLogger("nasiba_bot")


def _notify_admin_about_payment(bot, user_row, payment_row):
    if not config.ADMIN_TELEGRAM_ID:
        logger.warning("ADMIN_TELEGRAM_ID не задан — некому отправить чек.")
        return
    text = (
        "🔔 Новая оплата\n\n"
        f"Клиент:\nИмя: {user_display_name(user_row)}\n"
        f"Username: @{user_row['username'] or '—'}\n"
        f"Telegram ID: {user_row['telegram_id']}\n\n"
        f"Источник: {user_row['source'] or '—'}\n\n"
        f"Сумма: {payment_row['amount']} ₸\n\n"
        "Статус: ожидает проверки."
    )
    kb = admin_payment_kb(payment_row["id"])
    try:
        if payment_row["receipt_file_type"] == "photo":
            bot.send_photo(config.ADMIN_TELEGRAM_ID, payment_row["receipt_file_id"], caption=text, reply_markup=kb)
        else:
            bot.send_document(config.ADMIN_TELEGRAM_ID, payment_row["receipt_file_id"], caption=text, reply_markup=kb)
    except Exception:
        logger.exception("Не удалось отправить чек администратору")


def register(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "diag_pay")
    def handle_diag_pay(call):
        try:
            bot.answer_callback_query(call.id)
            user = database.get_or_create_user(call.from_user)
            database.log_event(user["id"], "diagnostics_pay_clicked")

            existing_confirmed = database.get_confirmed_payment_for_user(user["id"])
            if existing_confirmed:
                bot.send_message(
                    call.message.chat.id,
                    texts.RECEIPT_ALREADY_CONFIRMED,
                    reply_markup=start_brief_kb(),
                )
                return

            payment_service.start_payment(user, user["source"])
            bot.send_message(
                call.message.chat.id,
                texts.PAYMENT_INSTRUCTIONS,
                reply_markup=payment_link_kb(),
            )
        except Exception:
            logger.exception("Ошибка при старте оплаты")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)

    @bot.message_handler(content_types=["photo", "document"])
    def handle_possible_receipt(message):
        try:
            user = database.get_or_create_user(message.from_user)

            existing_confirmed = database.get_confirmed_payment_for_user(user["id"])
            if existing_confirmed:
                bot.send_message(message.chat.id, texts.RECEIPT_ALREADY_CONFIRMED, reply_markup=start_brief_kb())
                return

            pending = database.get_pending_payment_for_user(user["id"])
            if not pending:
                # Нет активного заказа диагностики — не считаем файл чеком.
                return

            if message.content_type == "photo":
                file_id = message.photo[-1].file_id
                file_type = "photo"
            else:
                file_id = message.document.file_id
                file_type = "document"

            payment = payment_service.attach_receipt_and_get_payment(user, file_id, file_type)
            database.log_event(user["id"], "receipt_sent")

            bot.send_message(message.chat.id, texts.RECEIPT_RECEIVED)
            _notify_admin_about_payment(bot, user, payment)
        except Exception:
            logger.exception("Ошибка при обработке чека")
            safe_call(bot.send_message, message.chat.id, texts.GENERIC_ERROR)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay_confirm:"))
    def handle_pay_confirm(call):
        try:
            if call.from_user.id != config.ADMIN_TELEGRAM_ID:
                bot.answer_callback_query(call.id, texts.ADMIN_ONLY, show_alert=True)
                return
            payment_id = int(call.data.split(":", 1)[1])
            payment = database.get_payment(payment_id)
            if not payment:
                bot.answer_callback_query(call.id, "Платёж не найден.", show_alert=True)
                return
            database.update_payment_status(payment_id, "confirmed", admin_id=call.from_user.id)
            user = database.get_user_by_id(payment["user_id"])

            bot.answer_callback_query(call.id, texts.PAYMENT_CONFIRMED_ADMIN)
            safe_call(bot.send_message, call.message.chat.id, texts.PAYMENT_CONFIRMED_ADMIN)
            safe_call(
                bot.send_message,
                user["telegram_id"],
                texts.PAYMENT_CONFIRMED_CLIENT,
                reply_markup=start_brief_kb(),
            )
        except Exception:
            logger.exception("Ошибка при подтверждении оплаты")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay_reject:"))
    def handle_pay_reject(call):
        try:
            if call.from_user.id != config.ADMIN_TELEGRAM_ID:
                bot.answer_callback_query(call.id, texts.ADMIN_ONLY, show_alert=True)
                return
            payment_id = int(call.data.split(":", 1)[1])
            payment = database.get_payment(payment_id)
            if not payment:
                bot.answer_callback_query(call.id, "Платёж не найден.", show_alert=True)
                return
            database.update_payment_status(payment_id, "rejected")
            user = database.get_user_by_id(payment["user_id"])

            bot.answer_callback_query(call.id, texts.PAYMENT_REJECTED_ADMIN)
            safe_call(bot.send_message, call.message.chat.id, texts.PAYMENT_REJECTED_ADMIN)
            safe_call(bot.send_message, user["telegram_id"], texts.PAYMENT_REJECTED_CLIENT)
        except Exception:
            logger.exception("Ошибка при отклонении оплаты")
            safe_call(bot.answer_callback_query, call.id, texts.GENERIC_ERROR, show_alert=True)
