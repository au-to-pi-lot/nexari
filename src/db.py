import sqlite3
from typing import Optional, Tuple

def init_db():
    conn = sqlite3.connect('webhooks.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS webhooks
                 (name TEXT PRIMARY KEY, webhook_id INTEGER UNIQUE, webhook_token TEXT)''')
    conn.commit()
    conn.close()

def get_webhook_info(name: str) -> Optional[Tuple[int, str]]:
    conn = sqlite3.connect('webhooks.db')
    c = conn.cursor()
    c.execute("SELECT webhook_id, webhook_token FROM webhooks WHERE name = ?", (name,))
    result = c.fetchone()
    conn.close()
    return result if result else None

def save_webhook_info(name: str, webhook_id: int, webhook_token: str):
    conn = sqlite3.connect('webhooks.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO webhooks (name, webhook_id, webhook_token) VALUES (?, ?, ?)",
              (name, webhook_id, webhook_token))
    conn.commit()
    conn.close()
