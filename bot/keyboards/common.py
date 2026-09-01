from telebot import types


def back_to_menu_button() -> types.InlineKeyboardButton:
    return types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu_home")
