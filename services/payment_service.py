"""
Небольшой сервис для работы с оплатой диагностики.
Проверка оплаты — полностью ручная, автоматической проверки Kaspi нет.
"""
import database
import config


def start_payment(user_row, source: str):
    """Создаёт новую запись об оплате в статусе pending."""
    return database.create_payment(user_row["id"], config.DIAGNOSTICS_PRICE, source)


def attach_receipt_and_get_payment(user_row, file_id: str, file_type: str):
    payment = database.get_pending_payment_for_user(user_row["id"])
    if not payment:
        payment = database.create_payment(user_row["id"], config.DIAGNOSTICS_PRICE, user_row["source"])
    database.attach_receipt(payment["id"], file_id, file_type)
    return database.get_payment(payment["id"])
