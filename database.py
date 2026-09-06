"""
Fully Async SQLite Database using aiosqlite
"""
import aiosqlite
import json
from datetime import datetime
from config import DB_PATH

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._pool = None

    async def _connect(self):
        if self._pool is None or self._pool.closed:
            self._pool = await aiosqlite.connect(self.db_path)
            self._pool.row_factory = aiosqlite.Row
        return self._pool

    async def init(self):
        conn = await self._connect()
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                username TEXT,
                status TEXT DEFAULT 'stopped',
                welcome_msg TEXT,
                buttons_json TEXT,
                bio TEXT,
                theme TEXT DEFAULT 'royal_gold',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bot_token TEXT NOT NULL,
                first_name TEXT,
                username TEXT,
                chat_id INTEGER NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, bot_token)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS blocked_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_token TEXT,
                message_preview TEXT,
                total_users INTEGER,
                sent INTEGER,
                failed INTEGER,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_stats (
                token TEXT PRIMARY KEY,
                start_count INTEGER DEFAULT 0,
                stop_count INTEGER DEFAULT 0,
                last_started TIMESTAMP,
                last_stopped TIMESTAMP,
                total_users INTEGER DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_token ON users(bot_token)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_userid ON users(user_id)
        """)
        await conn.commit()

    async def close(self):
        if self._pool and not self._pool.closed:
            await self._pool.close()
            self._pool = None

    # ─── Bot Management ───
    async def add_bot(self, token, username=None, welcome_msg=None, buttons_json=None, bio=None, theme="royal_gold"):
        conn = await self._connect()
        try:
            await conn.execute("""
                INSERT OR REPLACE INTO bots (token, username, welcome_msg, buttons_json, bio, theme, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (token, username, welcome_msg, buttons_json, bio, theme))
            await conn.execute("""
                INSERT OR IGNORE INTO bot_stats (token) VALUES (?)
            """, (token,))
            await conn.commit()
            return True
        except Exception as e:
            print(f"[DB Error] add_bot: {e}")
            return False

    async def get_bot(self, token):
        conn = await self._connect()
        async with conn.execute("SELECT * FROM bots WHERE token = ?", (token,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_all_bots(self, limit=500, offset=0):
        conn = await self._connect()
        async with conn.execute(
            "SELECT * FROM bots ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_bots_count(self):
        conn = await self._connect()
        async with conn.execute("SELECT COUNT(*) FROM bots") as cursor:
            row = await cursor.fetchone()
            return row[0]

    async def update_bot_status(self, token, status):
        conn = await self._connect()
        await conn.execute("UPDATE bots SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE token = ?", (status, token))
        await conn.commit()

    async def update_bot_welcome(self, token, welcome_msg):
        conn = await self._connect()
        await conn.execute("UPDATE bots SET welcome_msg = ?, updated_at = CURRENT_TIMESTAMP WHERE token = ?", (welcome_msg, token))
        await conn.commit()

    async def update_bot_buttons(self, token, buttons_json):
        conn = await self._connect()
        await conn.execute("UPDATE bots SET buttons_json = ?, updated_at = CURRENT_TIMESTAMP WHERE token = ?", (buttons_json, token))
        await conn.commit()

    async def update_bot_bio(self, token, bio):
        conn = await self._connect()
        await conn.execute("UPDATE bots SET bio = ?, updated_at = CURRENT_TIMESTAMP WHERE token = ?", (bio, token))
        await conn.commit()

    async def update_bot_theme(self, token, theme):
        conn = await self._connect()
        await conn.execute("UPDATE bots SET theme = ?, updated_at = CURRENT_TIMESTAMP WHERE token = ?", (theme, token))
        await conn.commit()

    async def update_bot_username(self, token, username):
        conn = await self._connect()
        await conn.execute("UPDATE bots SET username = ?, updated_at = CURRENT_TIMESTAMP WHERE token = ?", (username, token))
        await conn.commit()

    async def delete_bot(self, token):
        conn = await self._connect()
        await conn.execute("DELETE FROM bots WHERE token = ?", (token,))
        await conn.execute("DELETE FROM users WHERE bot_token = ?", (token,))
        await conn.execute("DELETE FROM bot_stats WHERE token = ?", (token,))
        await conn.commit()

    # ─── User Management ───
    async def add_user(self, user_id, bot_token, first_name, username, chat_id):
        conn = await self._connect()
        try:
            await conn.execute("""
                INSERT OR IGNORE INTO users (user_id, bot_token, first_name, username, chat_id)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, bot_token, first_name, username, chat_id))
            await conn.commit()
            return True
        except Exception as e:
            print(f"[DB Error] add_user: {e}")
            return False

    async def get_all_users(self, bot_token=None, limit=10000, offset=0):
        conn = await self._connect()
        if bot_token:
            async with conn.execute(
                "SELECT DISTINCT user_id, chat_id, bot_token FROM users WHERE bot_token = ? LIMIT ? OFFSET ?",
                (bot_token, limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with conn.execute(
                "SELECT DISTINCT user_id, chat_id, bot_token FROM users LIMIT ? OFFSET ?",
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
        return [{"user_id": r[0], "chat_id": r[1], "bot_token": r[2]} for r in rows]

    async def get_user_count(self, bot_token=None):
        conn = await self._connect()
        if bot_token:
            async with conn.execute("SELECT COUNT(DISTINCT user_id) FROM users WHERE bot_token = ?", (bot_token,)) as cursor:
                row = await cursor.fetchone()
        else:
            async with conn.execute("SELECT COUNT(DISTINCT user_id) FROM users") as cursor:
                row = await cursor.fetchone()
        return row[0]

    async def get_total_users_all_bots(self):
        conn = await self._connect()
        async with conn.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0]

    async def is_user_blocked(self, user_id):
        conn = await self._connect()
        async with conn.execute("SELECT 1 FROM blocked_users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

    async def block_user(self, user_id, reason=""):
        conn = await self._connect()
        await conn.execute("INSERT OR REPLACE INTO blocked_users (user_id, reason) VALUES (?, ?)", (user_id, reason))
        await conn.commit()

    async def unblock_user(self, user_id):
        conn = await self._connect()
        await conn.execute("DELETE FROM blocked_users WHERE user_id = ?", (user_id,))
        await conn.commit()

    # ─── Admin Management ───
    async def add_admin(self, user_id):
        conn = await self._connect()
        await conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        await conn.commit()

    async def is_admin(self, user_id):
        conn = await self._connect()
        async with conn.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

    async def get_all_admins(self):
        conn = await self._connect()
        async with conn.execute("SELECT user_id FROM admins") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

    # ─── Stats ───
    async def increment_bot_start(self, token):
        conn = await self._connect()
        await conn.execute("""
            INSERT INTO bot_stats (token, start_count, last_started)
            VALUES (?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(token) DO UPDATE SET
                start_count = start_count + 1,
                last_started = CURRENT_TIMESTAMP
        """, (token,))
        await conn.commit()

    async def increment_bot_stop(self, token):
        conn = await self._connect()
        await conn.execute("""
            INSERT INTO bot_stats (token, stop_count, last_stopped)
            VALUES (?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(token) DO UPDATE SET
                stop_count = stop_count + 1,
                last_stopped = CURRENT_TIMESTAMP
        """, (token,))
        await conn.commit()

    async def get_bot_stats(self, token):
        conn = await self._connect()
        async with conn.execute("SELECT * FROM bot_stats WHERE token = ?", (token,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_all_stats(self):
        conn = await self._connect()
        async with conn.execute("SELECT * FROM bot_stats") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ─── Broadcast Logs ───
    async def log_broadcast_start(self, bot_token, message_preview, total_users):
        conn = await self._connect()
        cursor = await conn.execute("""
            INSERT INTO broadcast_logs (bot_token, message_preview, total_users)
            VALUES (?, ?, ?)
        """, (bot_token, message_preview[:200], total_users))
        await conn.commit()
        return cursor.lastrowid

    async def log_broadcast_complete(self, log_id, sent, failed):
        conn = await self._connect()
        await conn.execute("""
            UPDATE broadcast_logs SET sent = ?, failed = ?, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (sent, failed, log_id))
        await conn.commit()

    async def get_broadcast_logs(self, limit=20):
        conn = await self._connect()
        async with conn.execute(
            "SELECT * FROM broadcast_logs ORDER BY started_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ─── Export ───
    async def export_tokens_to_file(self, filepath):
        bots = await self.get_all_bots(limit=10000)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# Telegram Bot Tokens Export\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total Bots: {len(bots)}\n\n")
            for bot in bots:
                f.write(f"{bot['token']}\n")
        return filepath

    async def backup_database(self, backup_path):
        import shutil
        shutil.copy(self.db_path, backup_path)
        return backup_path

# Global instance
db = Database()
