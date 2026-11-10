import json
import sqlite3
from pathlib import Path
from datetime import datetime

class Database:
    def __init__(self, path):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        with self.conn:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS products(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game TEXT NOT NULL, category TEXT NOT NULL, name TEXT NOT NULL,
                price REAL NOT NULL, facts TEXT NOT NULL, listing TEXT NOT NULL,
                photos TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS replies(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger TEXT NOT NULL, answer TEXT NOT NULL, enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                details TEXT NOT NULL, user_id INTEGER, created_at TEXT NOT NULL
            );
            """)
            self.conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('reply_mode','mixed')")

    def add_product(self, game, category, name, price, facts, listing, photos, status):
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO products(game,category,name,price,facts,listing,photos,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (game, category, name, price, facts, json.dumps(listing, ensure_ascii=False),
                 json.dumps(photos, ensure_ascii=False), status, datetime.now().isoformat(timespec="seconds"))
            )
            return cur.lastrowid

    def get_product(self, pid):
        row = self.conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if not row: return None
        d = dict(row)
        d["listing"] = json.loads(d["listing"])
        d["photos"] = json.loads(d["photos"])
        return d

    def list_products(self, limit=20):
        rows = self.conn.execute("SELECT * FROM products ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["listing"] = json.loads(d["listing"])
            d["photos"] = json.loads(d["photos"])
            result.append(d)
        return result

    def update_listing(self, pid, listing):
        with self.conn:
            self.conn.execute("UPDATE products SET listing=? WHERE id=?", (json.dumps(listing, ensure_ascii=False), pid))

    def delete_product(self, pid):
        with self.conn:
            self.conn.execute("DELETE FROM products WHERE id=?", (pid,))

    def add_reply(self, trigger, answer):
        with self.conn:
            self.conn.execute("INSERT INTO replies(trigger,answer,created_at) VALUES(?,?,?)",
                              (trigger, answer, datetime.now().isoformat(timespec="seconds")))

    def list_replies(self):
        return [dict(x) for x in self.conn.execute("SELECT * FROM replies WHERE enabled=1 ORDER BY id DESC").fetchall()]

    def match_reply(self, text):
        text = text.lower()
        rows = self.list_replies()
        matches = [r for r in rows if r["trigger"].lower() in text]
        return max(matches, key=lambda r: len(r["trigger"])) if matches else None

    def get_settings(self):
        return {r["key"]: r["value"] for r in self.conn.execute("SELECT * FROM settings").fetchall()}

    def set_setting(self, key, value):
        with self.conn:
            self.conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def add_event(self, kind, details, user_id=None):
        with self.conn:
            self.conn.execute("INSERT INTO events(kind,details,user_id,created_at) VALUES(?,?,?,?)",
                              (kind, details, user_id, datetime.now().isoformat(timespec="seconds")))

    def stats(self):
        products = self.conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        replies = self.conn.execute("SELECT COUNT(*) FROM replies WHERE enabled=1").fetchone()[0]
        events = self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        value = self.conn.execute("SELECT COALESCE(SUM(price),0) FROM products").fetchone()[0]
        return {"products": products, "replies": replies, "events": events, "draft_value": value}
