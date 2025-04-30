import feedparser
import asyncio
import numpy as np
import re
import logging
import datetime
import httpx

from datetime import datetime, timezone, timedelta

from httpx import AsyncClient, Timeout
from parse import (
    parselink,
    parseFoto,
    parseMainText,
    parselink_sb,
    parseFoto_sb,
    parseMainText_sb,
    parse_summary_sb
)
from sql import create_table, save_to_db, select_for_db, create_table_words, get_recent_news_texts
from variables import BOT_TOKEN, CHAT_ID, EDITOR_CHAT_ID
from gptai import check_news_relevance, check_news_uniqueness
from keyboard import news_actions
from aiogram import Router, Bot, Dispatcher, types, F
from handlers import router as handlers_router
from handlers import dp
from urllib.parse import urlparse, urljoin

INTERVAL_MINUTES = 10   # Интервал между проверками новостей в МИНУТАХ

# Настройка таймаутов
HTTPX_TIMEOUT = Timeout(30.0, connect=60.0)
BOT_TIMEOUT = 35

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)

RSS_FEEDS = [
    {
        'url': 'https://belta.by/rss/',
        'source': 'BELTA.BY',
        'parse_id': parselink,
        'parse_photo': parseFoto,
        'parse_text': parseMainText,
        'parse_summary': lambda entry: entry.get('summary', '')
    },
    {
        'url': 'https://www.sb.by/articles/rss/',
        'source': 'SB.BY',
        'parse_id': parselink_sb,
        'parse_photo': parseFoto_sb,
        'parse_text': parseMainText_sb,
        'parse_summary': lambda entry: parse_summary_sb(entry.link)
    },
]

# Вспомогательные функции
def is_valid_url(url: str) -> bool:
    """Проверяет валидность URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

async def send_news_item(bot: Bot, news: dict):
    """Универсальная отправка новости с обработкой изображений"""
    try:
        title = re.sub(r'[\r\n\t\s]+', ' ', news['title'])
        summary = re.sub(r'[\r\n\t\s]+', ' ', news["summary"])
        
        message_text = (
            f"<b>{title}</b>\n\n{summary}\n"
            f'🔗 Источник: <a href="{news["link"]}">{news.get("source", "")}</a>'
        )

        photo_url = news.get('photo_url')
        
        # Проверка валидности URL фото
        if photo_url and is_valid_url(photo_url):
            await bot.send_photo(
                chat_id=EDITOR_CHAT_ID,
                photo=photo_url,
                caption=message_text,
                parse_mode="HTML",
                reply_markup=news_actions(),
                show_caption_above_media=True
            )
        else:
            await bot.send_message(
                chat_id=EDITOR_CHAT_ID,
                text=message_text,
                parse_mode="HTML",
                reply_markup=news_actions(),
                disable_web_page_preview=True
            )

    except Exception as e:
        logger.error(f"Ошибка отправки: {str(e)}")
        # Фолбэк без фото
        await bot.send_message(
            chat_id=EDITOR_CHAT_ID,
            text=message_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )


async def process_rss_feed(bot: Bot, feed_config: dict):
    """Обрабатывает RSS-ленту на основе конфигурации"""
    async with AsyncClient(timeout=HTTPX_TIMEOUT, headers={'User-Agent': 'Mozilla/5.0 (compatible; RSS-Reader/1.0)'}) as client:
        try:
            try:
                response = await client.get(feed_config['url'])
            
            except httpx.ConnectError as e:
                logger.error(f"Ошибка подключения к {feed_config['url']}: {str(e)}")
                return
            except Exception as e:
                logger.exception(f"Неизвестная ошибка: {e}")
                return
            
            if response.status_code != 200:
                logger.error(f"Ошибка доступа к {feed_config['url']}")
                return

            feed = feedparser.parse(response.text)
            for entry in feed.entries[::-1]:  # Обработка с конца
                # Проверка времени публикации
                pub_time = entry.get('published_parsed')
                if not pub_time:
                    logger.warning(f"Пропуск записи без времени: {entry.link}")
                    continue

                try:
                    # Создание aware datetime объекта
                    pub_datetime = datetime(*pub_time[:6], tzinfo=timezone.utc)
                    current_time = datetime.now(timezone.utc)
                    logger.debug(f"Время публикации: {pub_datetime}, текущее время: {current_time}")

                    if (current_time - pub_datetime) < timedelta(minutes=30):
                        logger.info(f"Пропуск свежей новости: {entry.link}")
                        continue

                except Exception as e:
                    logger.error(f"Ошибка обработки времени: {e}")
                    continue

                # Извлечение данных
                news_id = feed_config['parse_id'](entry.link)
                if not news_id:
                    continue

                # Проверка наличия в БД
                if await select_for_db(news_id, feed_config['source']):
                    continue

                try:
                    photo_url = feed_config['parse_photo'](entry.link)
                except Exception as e:
                    logger.error(f"Ошибка парсинга фото: {e}")
                    photo_url = None
                
                try:
                    summary = feed_config['parse_summary'](entry)
                except Exception as e:
                    logger.error(f"Ошибка получения summary: {e}")
                    summary = ""


                full_text = f"{entry.title} {summary}"

                try:
                    # Проверяем через GPT
                    relevance = await check_news_relevance(full_text)
                    if relevance not in ['y', 'n']:
                        logger.warning(f"Некорректный ответ GPT: {relevance}")
                        relevance = 'n'
                        await save_to_db(news_id, entry.title, entry.link, feed_config['source'], status='rejected')
                        continue

                    if relevance != 'y':
                        logger.info(f"Новость не соответствует тематике: {entry.link}")
                        await save_to_db(news_id, entry.title, entry.link, feed_config['source'], status='rejected')
                        continue
                except Exception as e:
                    logger.error(f"Ошибка проверки GPT: {e}")
                    continue

                try:
                    # Проверка уникальности
                    content = f"{entry.title}"

                    previous_news = await get_recent_news_texts(6)
                    is_unique = await check_news_uniqueness(content, previous_news)

                    if is_unique != 'y':
                        logger.info(f"Дубликат новости: {entry.link}")
                        await save_to_db(news_id, entry.title, entry.link, feed_config['source'], status='duplicate')
                        continue
                except Exception as e:
                    logger.error(f"Ошибка проверки GPT на уникальность: {e}")
                    continue


                logger.error(f"Новость СООТВЕТСТВУЕТ тематике: {entry.link}")    
                # Сохранение и отправка
                await save_to_db(news_id, entry.title, entry.link, feed_config['source'], status='approved')
                await send_news_item(bot, {
                    'title': entry.title,
                    'summary': summary,
                    'link': entry.link,
                    'source': feed_config['source'],
                    'photo_url': photo_url
                })
                await asyncio.sleep(7)

        except Exception as e:
            logger.exception(f"Ошибка в {feed_config['url']}: {e}")

async def scheduler():
    """Запуск обработки всех RSS-лент"""
    while True:
        try:
            tasks = [process_rss_feed(bot, feed) for feed in RSS_FEEDS]
            await asyncio.gather(*tasks)
            await asyncio.sleep(INTERVAL_MINUTES * 60)
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            await asyncio.sleep(60)  # Задержка при ошибках

async def main():
    dp.include_router(handlers_router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await create_table()
        await create_table_words()

        # Запускаем планировщик в текущем цикле событий
        scheduler_task = asyncio.create_task(scheduler())
        
        # Запускаем обработчик сообщений
        await dp.start_polling(bot)

    except Exception as e:
        logger.exception(f"Main error: {e}")
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())