import sqlite3
from typing import Optional, Tuple

class WebhookDB:
    def __init__(self, db_name: str = 'webhooks.db'):
        self.db_name = db_name
        self.conn = None
        self.cursor = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def init_db(self):
        with self:
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS webhooks
                                   (name TEXT PRIMARY KEY, webhook_id INTEGER UNIQUE, webhook_token TEXT)''')
            self.conn.commit()

    def get_webhook_info(self, name: str) -> Optional[Tuple[int, str]]:
        with self:
            self.cursor.execute("SELECT webhook_id, webhook_token FROM webhooks WHERE name = ?", (name,))
            result = self.cursor.fetchone()
        return result if result else None

    def save_webhook_info(self, name: str, webhook_id: int, webhook_token: str):
        with self:
            self.cursor.execute("INSERT OR REPLACE INTO webhooks (name, webhook_id, webhook_token) VALUES (?, ?, ?)",
                                (name, webhook_id, webhook_token))
            self.conn.commit()
