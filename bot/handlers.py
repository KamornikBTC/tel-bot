import datetime
import asyncio
import logging

from variables import CHANNEL_ID, CHAT_ID
from sql import update_db
from parse import parselink

from aiogram import Router, F, Dispatcher, Bot, types
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sql import create_table, save_to_db, select_for_db, create_table_words, save_word, delete_word, get_all_words

router = Router()
dp = Dispatcher()

class Form(StatesGroup):
    add_word = State()
    delete_word = State()

# Добавить функцию создания клавиатуры
def get_main_keyboard():
    kb = [
        [
            types.KeyboardButton(text="Список слов"),
            types.KeyboardButton(text="Добавить слово"),
            types.KeyboardButton(text="Удалить слово")
        ],
    ]
    return types.ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="Выберите команду"
    )


@router.callback_query(F.data == 'delete_news')
async def delete_news_handler(callback: CallbackQuery):
    try:
        # Удаляем сообщение
        await callback.message.delete()
        
        # Обновляем статус в БД
        if callback.message.entities:
            for entity in callback.message.entities:
                if entity.type == 'text_link':
                    news_id = parselink(entity.url)
                    if news_id:
                        await update_db(news_id, 'Deleted', datetime.datetime.now())
        
        await callback.answer("Новость удалена!")
    except Exception as e:
        print(f"Ошибка при удалении: {e}")
        await callback.answer("Не удалось удалить новость", show_alert=True)

@router.callback_query(F.data == 'send_to_channel')
async def send_to_channel_handler(callback: CallbackQuery):
    try:
        # Копируем сообщение в канал
        await callback.bot.copy_message(
            chat_id=CHANNEL_ID,
            from_chat_id=callback.message.chat.id,
            message_id=callback.message.message_id
        )
        
        # Удаляем оригинальное сообщение
        await callback.message.delete()
        
        # Обновляем статус в БД
        if callback.message.entities:
            for entity in callback.message.entities:
                if entity.type == 'text_link':
                    news_id = parselink(entity.url)
                    if news_id:
                        await update_db(news_id, 'Published', datetime.datetime.now())
        
        await callback.answer("Новость опубликована!")
    except Exception as e:
        print(f"Ошибка при отправке: {e}")
        await callback.answer("Не удалось отправить новость", show_alert=True)



# Обработчик кнопки "Добавить слово"
@dp.message(F.text.lower() == "добавить слово")
async def add_word_command(message: Message, state: FSMContext):
    await message.answer(
        "Введите слово для добавления:",
        reply_markup=ReplyKeyboardRemove()  # Скрываем клавиатуру
    )
    await state.set_state(Form.add_word)
    try:
        await message.delete()
    except Exception as e:
        logging.error(f"Ошибка удаления сообщения: {e}")

# Обработчик ввода слова для добавления
@dp.message(Form.add_word)
async def process_add_word(message: Message, state: FSMContext):
    word = message.text.strip().lower()
    if await save_word(word):
        await message.answer(
            f"✅ Слово '{word}' успешно добавлено!",
            reply_markup=get_main_keyboard()  # Восстанавливаем клавиатуру
        )
    else:
        await message.answer(
            f"⚠️ Слово '{word}' уже существует в списке",
            reply_markup=get_main_keyboard()
        )
    await state.clear()


# Обработчик кнопки "Удалить слово"
@dp.message(F.text.lower() == "удалить слово")
async def delete_word_command(message: Message, state: FSMContext):
    await message.answer(
        "Введите слово для удаления:",
        reply_markup=ReplyKeyboardRemove()  # Скрываем клавиатуру
    )
    await state.set_state(Form.delete_word)
    try:
        await message.delete()
    except Exception as e:
        logging.error(f"Ошибка удаления сообщения: {e}")

@dp.message(Form.delete_word)
async def process_delete_word(message: Message, state: FSMContext):
    word = message.text.strip().lower()
    if await delete_word(word):
        await message.answer(
            f"✅ Слово '{word}' успешно удалено!",
            reply_markup=get_main_keyboard()  # Восстанавливаем клавиатуру
        )
    else:
        await message.answer(
            f"⚠️ Слова '{word}' нет в списке",
            reply_markup=get_main_keyboard()
        )
    await state.clear()

# Остальные обработчики остаются без изменений
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Бот работает!",
        reply_markup=get_main_keyboard()  # Отправляем клавиатуру при старте
    )

@dp.message(F.text.lower() == "список слов")
async def word_list(message: types.Message):
    words = await get_all_words()
    
    if not words:
        await message.answer("📭 Список ключевых слов пуст")
        return
    
    await message.answer(
        f"📚 Список ключевых слов:\n" + "\n".join([f"• {word}" for word in words]),
        parse_mode="Markdown",
    )

    try:
        # Удаляем сообщение с текстом кнопки
        await message.delete()
    except Exception as e:
        logging.error(f"Ошибка удаления сообщения: {e}")
