import aiosqlite

# –––––––––––––––––––– БД НОВОСТЕЙ –––––––––––––––––––––––––––––––––

#Создаем БД, если ее нет в каталоге
async def create_table():
    async with aiosqlite.connect('storage.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS motor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                news_id TEXT,
                title TEXT,
                link TEXT,
                status TEXT,
                source TEXT,
                date DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(news_id, source)
            )
        ''')
        await db.commit()

async def save_to_db(news_id: str, title: str, link: str, source: str, status: str = 'pending'):
    async with aiosqlite.connect('storage.db') as db:
        await db.execute(
            '''INSERT INTO motor
            (news_id, title, link, source, status) 
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(news_id, source) DO UPDATE SET
            status = excluded.status''',
            (news_id, title, link, source, status)
        )
        await db.commit()

async def select_for_db(news_id: str, source: str) -> bool:
    """Проверяет существование новости по ID и источнику"""
    async with aiosqlite.connect('storage.db') as db:
        cursor = await db.execute(
            'SELECT 1 FROM motor WHERE news_id = ? AND source = ?',
            (news_id, source)
        )
        return await cursor.fetchone() is not None

#Обновляем запись в БД по ИД
async def update_db(news_id, status, date):
    async with aiosqlite.connect('storage.db') as db:
        await db.execute('UPDATE motor SET status = ?, date = ? WHERE news_id = ?',
                         (status, date, news_id))
        await db.commit()

async def get_recent_news_texts(hours):
    async with aiosqlite.connect('storage.db') as db:
        cursor = await db.execute(
            '''SELECT title FROM motor 
            WHERE datetime(date) >= datetime("now", ?) 
            AND status != 'rejected' 
            ORDER BY date DESC
            LIMIT 10''',
            (f"-{hours} hours",)
        )
        result = await cursor.fetchall()
        return [row[0] for row in result if row[0]]

# –––––––––––––––––––– БД ключевых слов –––––––––––––––––––––––––––––––––

# Создание таблицы
async def create_table_words():
    async with aiosqlite.connect('keywords.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS tabl 
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         word TEXT UNIQUE)''')
        await db.commit()

# Добавление слова
async def save_word(word: str):
    async with aiosqlite.connect('keywords.db') as db:
        try:
            await db.execute('INSERT INTO tabl (word) VALUES (?)', (word.lower(),))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False  # Если слово уже существует

# Удаление слова
async def delete_word(word: str):
    async with aiosqlite.connect('keywords.db') as db:
        cursor = await db.execute('DELETE FROM tabl WHERE word = ?', (word.lower(),))
        await db.commit()
        return cursor.rowcount > 0

# Получение всех слов
async def get_all_words():
    async with aiosqlite.connect('keywords.db') as db:
        cursor = await db.execute('SELECT word FROM tabl ORDER BY word')
        result = await cursor.fetchall()
        return [row[0] for row in result]
