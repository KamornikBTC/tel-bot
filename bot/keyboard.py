from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def news_actions() -> InlineKeyboardMarkup:
    buttons = InlineKeyboardBuilder()
    buttons.button(text='📢 В канал', callback_data='send_to_channel')
    buttons.button(text='🗑 Удалить', callback_data='delete_news')
    buttons.adjust(2)
    return buttons.as_markup()