import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

import openai
from PyPDF2 import PdfReader
from docx import Document
import pandas as pd
from io import BytesIO

# Загрузка переменных окружения
load_dotenv()

# Настройка логгирования
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранение данных пользователя (в памяти)
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Загрузите файлы (PDF, Word, Excel), а затем задайте вопросы по ним."
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    file = await update.message.document.get_file()
    
    # Скачивание файла
    file_bytes = await file.download_as_bytearray()
    
    # Определение типа файла и обработка
    file_name = update.message.document.file_name.lower()
    text = ""
    
    try:
        if file_name.endswith(".pdf"):
            reader = PdfReader(BytesIO(file_bytes))
            for page in reader.pages:
                text += page.extract_text() + "\n"
        
        elif file_name.endswith(".docx"):
            doc = Document(BytesIO(file_bytes))
            for para in doc.paragraphs:
                text += para.text + "\n"
        
        elif file_name.endswith(".xlsx"):
            df = pd.read_excel(BytesIO(file_bytes), sheet_name=None)
            for sheet_name, sheet in df.items():
                text += f"Лист: {sheet_name}\n"
                text += sheet.to_string() + "\n\n"
        
        else:
            await update.message.reply_text("Формат файла не поддерживается.")
            return
        
        # Сохранение текста
        if user_id not in user_data:
            user_data[user_id] = ""
        user_data[user_id] += text + "\n\n"
        await update.message.reply_text("Файл успешно обработан! Теперь задайте вопрос.")
    
    except Exception as e:
        await update.message.reply_text(f"Ошибка обработки файла: {str(e)}")

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    question = update.message.text
    
    if user_id not in user_data or not user_data[user_id]:
        await update.message.reply_text("Сначала загрузите файлы!")
        return
    
    try:
        # Формирование промпта для GPT
        prompt = f"Документ:\n{user_data[user_id]}\n\nВопрос: {question}\nОтвет:"
        
        # Запрос к OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ты помогаешь анализировать документы. Отвечай точно и кратко."},
                {"role": "user", "content": prompt}
            ]
        )
        
        answer = response.choices[0].message['content']
        await update.message.reply_text(answer)
    
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")

def main():
    # Инициализация OpenAI
    openai.api_key = os.getenv("OPENAI_API_KEY")
    
    # Создание бота
    app = ApplicationBuilder().token("7656880971:AAGJoYRxFIwyY8SygB6I0K9EWSTU1PXgjvc").build()
    
    # Обработчики
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))
    app.add_handler(MessageHandler(filters.COMMAND, start))
    
    # Запуск бота
    app.run_polling()

if __name__ == "__main__":
    main()