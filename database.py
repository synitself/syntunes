import sqlite3
import json
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Any, Optional


class Database:
    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS users
                           (
                               user_id
                               INTEGER
                               PRIMARY
                               KEY,
                               username
                               TEXT,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP
                           )
                           ''')

            # Добавляем колонку scheduled_publish_time, если её нет
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN scheduled_publish_time TEXT DEFAULT '20:00'")
            except sqlite3.OperationalError:
                # Колонка уже существует
                pass

            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS user_beatmakers
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               user_id
                               INTEGER,
                               beatmaker_name
                               TEXT,
                               beatmaker_tag
                               TEXT,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               FOREIGN
                               KEY
                           (
                               user_id
                           ) REFERENCES users
                           (
                               user_id
                           ),
                               UNIQUE
                           (
                               user_id,
                               beatmaker_name
                           )
                               )
                           ''')

            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS user_types
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               user_id
                               INTEGER,
                               type_name
                               TEXT,
                               type_tags
                               TEXT,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               FOREIGN
                               KEY
                           (
                               user_id
                           ) REFERENCES users
                           (
                               user_id
                           ),
                               UNIQUE
                           (
                               user_id,
                               type_name
                           )
                               )
                           ''')

            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS scheduled_uploads
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               user_id
                               INTEGER,
                               video_title
                               TEXT,
                               scheduled_date
                               TEXT,
                               scheduled_time
                               TEXT,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               FOREIGN
                               KEY
                           (
                               user_id
                           ) REFERENCES users
                           (
                               user_id
                           )
                               )
                           ''')

            conn.commit()

    def add_user(self, user_id: int, username: str = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           INSERT
                           OR IGNORE INTO users (user_id, username)
                VALUES (?, ?)
                           ''', (user_id, username))
            conn.commit()

    def set_scheduled_publish_time(self, user_id: int, time_str: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           INSERT INTO users (user_id, scheduled_publish_time)
                           VALUES (?, ?) ON CONFLICT(user_id) DO
                           UPDATE SET scheduled_publish_time=excluded.scheduled_publish_time
                           ''', (user_id, time_str))
            conn.commit()

    def get_scheduled_publish_time(self, user_id: int) -> str:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT scheduled_publish_time FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    return row[0]
            except sqlite3.OperationalError:
                # Колонка не существует, возвращаем значение по умолчанию
                pass
            return '20:00'

    def get_next_available_date(self, user_id: int, time_str: str) -> str:
        """Возвращает следующую доступную дату для публикации"""
        msk_tz = pytz.timezone('Europe/Moscow')
        current_date = datetime.now(msk_tz).date()

        # Начинаем с завтрашнего дня
        check_date = current_date + timedelta(days=1)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Ищем первую свободную дату
            for _ in range(365):  # Проверяем год вперед
                date_str = check_date.strftime('%Y-%m-%d')

                cursor.execute('''
                               SELECT COUNT(*)FROM scheduled_uploads 
                    WHERE user_id = ? AND scheduled_date = ? AND scheduled_time = ?
                ''', (user_id, date_str, time_str))

                count = cursor.fetchone()[0]

                if count == 0:
                    return date_str

                check_date += timedelta(days=1)

        # Если не нашли свободную дату (маловероятно), возвращаем завтрашний день
        return (current_date + timedelta(days=1)).strftime('%Y-%m-%d')

    def add_scheduled_upload(self, user_id: int, video_title: str, scheduled_date: str, scheduled_time: str):
        """Добавляет запись о запланированной публикации"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           INSERT INTO scheduled_uploads (user_id, video_title, scheduled_date, scheduled_time)
                           VALUES (?, ?, ?, ?)
                           ''', (user_id, video_title, scheduled_date, scheduled_time))
            conn.commit()

    def get_user_scheduled_uploads(self, user_id: int) -> List[Dict[str, str]]:
        """Возвращает список запланированных публикаций пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT video_title, scheduled_date, scheduled_time
                           FROM scheduled_uploads
                           WHERE user_id = ?
                           ORDER BY scheduled_date, scheduled_time
                           ''', (user_id,))

            return [{'title': row[0], 'date': row[1], 'time': row[2]} for row in cursor.fetchall()]

    def add_user_beatmaker(self, user_id: int, beatmaker_name: str, beatmaker_tag: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_beatmakers (user_id, beatmaker_name, beatmaker_tag)
                VALUES (?, ?, ?)
            ''', (user_id, beatmaker_name, beatmaker_tag))
            conn.commit()

    def get_user_beatmakers(self, user_id: int) -> List[Dict[str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT beatmaker_name, beatmaker_tag
                           FROM user_beatmakers
                           WHERE user_id = ?
                           ORDER BY created_at DESC
                           ''', (user_id,))

            return [{'name': row[0], 'tag': row[1]} for row in cursor.fetchall()]

    def remove_user_beatmaker(self, user_id: int, beatmaker_name: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           DELETE
                           FROM user_beatmakers
                           WHERE user_id = ?
                             AND beatmaker_name = ?
                           ''', (user_id, beatmaker_name))
            conn.commit()

    def add_user_type(self, user_id: int, type_name: str, type_tags: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_types (user_id, type_name, type_tags)
                VALUES (?, ?, ?)
            ''', (user_id, type_name, type_tags))
            conn.commit()

    def get_user_types(self, user_id: int) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT type_name
                           FROM user_types
                           WHERE user_id = ?
                           ORDER BY created_at DESC
                           ''', (user_id,))
            return [row[0] for row in cursor.fetchall()]

    def get_user_type_data(self, user_id: int, type_name: str) -> Optional[Dict[str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT type_name, type_tags
                           FROM user_types
                           WHERE user_id = ?
                             AND type_name = ?
                           ''', (user_id, type_name))

            row = cursor.fetchone()
            if row:
                return {'name': row[0], 'tags': row[1]}
            return None

    def remove_user_type(self, user_id: int, type_name: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           DELETE
                           FROM user_types
                           WHERE user_id = ?
                             AND type_name = ?
                           ''', (user_id, type_name))
            conn.commit()
