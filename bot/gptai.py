import re
import asyncio

from openai import OpenAI
from sql import get_all_words, get_recent_news_texts
from variables import API_KEY

client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

async def clean_text(text: str) -> str:
    # Удаляем все не-буквы и не-цифры, оставляем пробелы
    cleaned = re.sub(r'[^a-zA-Zа-яА-Я0-9\s]', ' ', text)
    # Заменяем множественные пробелы на один
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # Приводим к нижнему регистру
    return cleaned.strip().lower()

async def check_news_relevance(news_text: str) -> str:
    
    list_from_sql = await get_all_words()

    final_list = "\n".join([f"{word}" for word in list_from_sql])

    news = await clean_text(news_text)

    truncated_text = (news_text[:997] + '..') if len(news_text) > 1000 else news_text

    system_prompt = f"""Определи, соответствует ли новость тематике на основе списка ключевых слов.
1. Проверь упоминание слов из списка в тексте
2. Оцени контекст использования ключевых слов
3. Учти тематические связи между словами
Ответь ТОЛЬКО одной буквой:
   y - если соответствует
   n - если НЕ соответствует

Список ключевых слов: {final_list}
Новость: {truncated_text}"""
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "user", "content": system_prompt},
        ],
        temperature=0,
        max_tokens=1,
        stream=False
    )
    
    return response.choices[0].message.content.strip().lower()


async def check_news_uniqueness(news_text: str, previous_news: list) -> str:
    if not previous_news:
        return 'y'
    
    truncated_current = (news_text[:997] + '..') if len(news_text) > 1000 else news_text
    truncated_previous = [(text[:497] + '..') if len(text) > 500 else text for text in previous_news][-10:]
    previous_list = "\n\n".join([f"Новость {i+1}:\n{text}" for i, text in enumerate(truncated_previous)])
    system_prompt = f"""Проверь, является ли новая новость дубликатом хотя бы одной новости из списка последних новостей. Возможно переформулирование нескольких слов.
Ответь ТОЛЬКО одной буквой "y" или "n":
y - если новость не дубликат
n - если новость дубликат

Новая новость:
{truncated_current}

Последние новости:
{previous_list}"""
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": system_prompt}],
        temperature=0,
        max_tokens=1
    )
    
    return response.choices[0].message.content.strip().lower()


async def main():
    test_text = """В Молодечненском районе за пятилетку в планах реализовать 3 фермы по выращиванию КРС
"""
    previous_news = await get_recent_news_texts(6)
    print(previous_news)
    print(await check_news_uniqueness(test_text, previous_news))

if __name__ == '__main__':
    asyncio.run(main())