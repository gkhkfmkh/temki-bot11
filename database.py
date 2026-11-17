from pathlib import Path
import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS products(
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, category TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '', price REAL NOT NULL DEFAULT 0,
 cost REAL NOT NULL DEFAULT 0, stock INTEGER NOT NULL DEFAULT 0,
 photo_path TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS deals(
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, category TEXT NOT NULL,
 buy_price REAL NOT NULL, sell_price REAL NOT NULL, fee REAL NOT NULL DEFAULT 0,
 source TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 decided_at TEXT
);
CREATE TABLE IF NOT EXISTS drafts(
 id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL,
 title TEXT NOT NULL, description TEXT NOT NULL, price REAL NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 decided_at TEXT, FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS orders(
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT NOT NULL DEFAULT '',
 buyer TEXT NOT NULL DEFAULT 'Покупатель', product_id INTEGER,
 product_title TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0,
 cost REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'new',
 delivery_text TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS market_rows(
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, category TEXT NOT NULL,
 price REAL NOT NULL, url TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',
 notes TEXT NOT NULL DEFAULT '', imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit(
 id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, entity TEXT NOT NULL,
 entity_id INTEGER, details TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

class Database:
    def __init__(self, path):
        self.path = path

    async def connect(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(self.path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys=ON")
        return conn

    async def initialize(self):
        async with await self.connect() as conn:
            await conn.executescript(SCHEMA)
            await conn.commit()

    async def execute(self, sql, params=()):
        async with await self.connect() as conn:
            cur = await conn.execute(sql, params)
            await conn.commit()
            return cur.lastrowid

    async def one(self, sql, params=()):
        async with await self.connect() as conn:
            cur = await conn.execute(sql, params)
            return await cur.fetchone()

    async def all(self, sql, params=()):
        async with await self.connect() as conn:
            cur = await conn.execute(sql, params)
            return await cur.fetchall()

    async def log(self, action, entity, entity_id=None, details=""):
        await self.execute("INSERT INTO audit(action,entity,entity_id,details) VALUES(?,?,?,?)",
                           (action, entity, entity_id, details[:1500]))
