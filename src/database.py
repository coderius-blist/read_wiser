import aiosqlite
import json
from datetime import datetime, timedelta
from config import DATABASE_PATH, DATA_DIR


async def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                url TEXT,
                source_title TEXT,
                source_author TEXT,
                source_domain TEXT,
                tags TEXT,
                is_favorite INTEGER DEFAULT 0,
                times_shown INTEGER DEFAULT 0,
                last_shown TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

        # Migration: add new columns to existing databases
        await _migrate_db(db)


async def _migrate_db(db):
    """Add new columns if they don't exist (for existing databases)."""
    cursor = await db.execute("PRAGMA table_info(quotes)")
    columns = {row[1] for row in await cursor.fetchall()}

    migrations = [
        ("is_favorite", "INTEGER DEFAULT 0"),
        ("times_shown", "INTEGER DEFAULT 0"),
        ("last_shown", "TIMESTAMP"),
    ]

    for col_name, col_type in migrations:
        if col_name not in columns:
            await db.execute(f"ALTER TABLE quotes ADD COLUMN {col_name} {col_type}")

    await db.commit()


async def save_quote(text: str, url: str = None, title: str = None,
                     author: str = None, domain: str = None, tags: list = None) -> int:
    tags_str = ",".join(tags) if tags else None
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO quotes (text, url, source_title, source_author, source_domain, tags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (text, url, title, author, domain, tags_str)
        )
        await db.commit()
        return cursor.lastrowid


async def delete_quote(quote_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("DELETE FROM quotes WHERE id = ?", (quote_id,))
        await db.commit()
        return cursor.rowcount > 0


async def get_quote_by_id(quote_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_random_quotes(n: int = 10, use_spaced_repetition: bool = True) -> list:
    """
    Get random quotes, optionally weighted by spaced repetition.
    Quotes shown less recently and less frequently are prioritized.
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        if use_spaced_repetition:
            # Prioritize: never shown > shown long ago > shown recently
            # Also factor in times_shown (less shown = higher priority)
            cursor = await db.execute("""
                SELECT * FROM quotes
                ORDER BY
                    CASE
                        WHEN last_shown IS NULL THEN 0
                        WHEN last_shown < datetime('now', '-30 days') THEN 1
                        WHEN last_shown < datetime('now', '-7 days') THEN 2
                        ELSE 3
                    END,
                    times_shown ASC,
                    RANDOM()
                LIMIT ?
            """, (n,))
        else:
            cursor = await db.execute(
                "SELECT * FROM quotes ORDER BY RANDOM() LIMIT ?", (n,)
            )

        rows = await cursor.fetchall()
        quotes = [dict(row) for row in rows]

        # Update last_shown and times_shown for retrieved quotes
        if quotes:
            quote_ids = [q["id"] for q in quotes]
            placeholders = ",".join("?" * len(quote_ids))
            await db.execute(f"""
                UPDATE quotes
                SET last_shown = CURRENT_TIMESTAMP, times_shown = times_shown + 1
                WHERE id IN ({placeholders})
            """, quote_ids)
            await db.commit()

        return quotes


async def get_last_quotes(n: int = 5) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM quotes ORDER BY created_at DESC LIMIT ?", (n,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_quote_count() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM quotes")
        row = await cursor.fetchone()
        return row[0]


async def get_quotes_this_week() -> int:
    week_ago = datetime.now() - timedelta(days=7)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM quotes WHERE created_at >= ?",
            (week_ago.isoformat(),)
        )
        row = await cursor.fetchone()
        return row[0]


async def search_quotes(keyword: str) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM quotes WHERE text LIKE ? ORDER BY created_at DESC LIMIT 10",
            (f"%{keyword}%",)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_quotes_by_tag(tag: str) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM quotes WHERE tags LIKE ? ORDER BY created_at DESC LIMIT 10",
            (f"%{tag}%",)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_quotes_by_source(domain: str) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM quotes WHERE source_domain LIKE ? ORDER BY created_at DESC LIMIT 10",
            (f"%{domain}%",)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def toggle_favorite(quote_id: int) -> bool | None:
    """Toggle favorite status. Returns new status, or None if quote not found."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT is_favorite FROM quotes WHERE id = ?", (quote_id,))
        row = await cursor.fetchone()
        if not row:
            return None

        new_status = 0 if row[0] else 1
        await db.execute("UPDATE quotes SET is_favorite = ? WHERE id = ?", (new_status, quote_id))
        await db.commit()
        return bool(new_status)


async def get_favorite_quotes() -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM quotes WHERE is_favorite = 1 ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_top_tags(limit: int = 5) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT tags FROM quotes WHERE tags IS NOT NULL")
        rows = await cursor.fetchall()

    tag_counts = {}
    for row in rows:
        if row[0]:
            for tag in row[0].split(","):
                tag = tag.strip()
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_tags[:limit]


async def is_duplicate(text: str, minutes: int = 1) -> bool:
    cutoff = datetime.now() - timedelta(minutes=minutes)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM quotes WHERE text = ? AND created_at >= ?",
            (text, cutoff.isoformat())
        )
        row = await cursor.fetchone()
        return row[0] > 0


async def export_all_quotes() -> str:
    """Export all quotes as JSON string."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM quotes ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        quotes = [dict(row) for row in rows]

    return json.dumps(quotes, indent=2, default=str)
