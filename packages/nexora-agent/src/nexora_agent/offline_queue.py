"""SQLite-backed offline queue for telemetry and execution callbacks.

When the device loses connectivity, outbound HTTP calls are enqueued here
and replayed in order when the tunnel reconnects.

Table layout:
  queue(id INTEGER PK, kind TEXT, payload TEXT, created_at REAL, attempts INTEGER)

kind values: "telemetry" | "callback"
"""
import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from nexora_agent import config

logger = logging.getLogger("nexora-agent.queue")

_DB_INIT = """
CREATE TABLE IF NOT EXISTS queue (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT    NOT NULL,
    payload    TEXT    NOT NULL,
    created_at REAL    NOT NULL,
    attempts   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_queue_kind ON queue(kind);
"""

_MAX_ATTEMPTS = 10
_conn: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        path = config.QUEUE_DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(path), check_same_thread=False)
        _conn.executescript(_DB_INIT)
        _conn.commit()
    return _conn


def enqueue(kind: str, payload: dict) -> None:
    """Add an item to the offline queue (called from any thread)."""
    db = _db()
    db.execute(
        "INSERT INTO queue (kind, payload, created_at, attempts) VALUES (?, ?, ?, 0)",
        (kind, json.dumps(payload), time.time()),
    )
    db.commit()
    logger.debug("Queued %s item — queue size=%d", kind, depth())


def depth() -> int:
    row = _db().execute("SELECT COUNT(*) FROM queue").fetchone()
    return row[0] if row else 0


def peek(limit: int = 20) -> list[dict]:
    """Return up to `limit` oldest items without removing them."""
    rows = _db().execute(
        "SELECT id, kind, payload, attempts FROM queue ORDER BY id LIMIT ?", (limit,)
    ).fetchall()
    return [{"id": r[0], "kind": r[1], "payload": json.loads(r[2]), "attempts": r[3]} for r in rows]


def ack(item_id: int) -> None:
    """Remove a successfully delivered item."""
    _db().execute("DELETE FROM queue WHERE id = ?", (item_id,))
    _db().commit()


def nack(item_id: int) -> None:
    """Increment attempt counter; drop if over limit."""
    db = _db()
    db.execute("UPDATE queue SET attempts = attempts + 1 WHERE id = ?", (item_id,))
    db.execute("DELETE FROM queue WHERE id = ? AND attempts >= ?", (item_id, _MAX_ATTEMPTS))
    db.commit()


async def drain(
    send_telemetry_fn,
    send_callback_fn,
) -> None:
    """Drain queued items using the provided async send functions.

    send_telemetry_fn(payload: dict) -> bool   (True = success)
    send_callback_fn(payload: dict) -> bool
    """
    items = peek(limit=50)
    if not items:
        return
    logger.info("Draining offline queue — %d items pending", len(items))
    for item in items:
        try:
            if item["kind"] == "telemetry":
                ok = await send_telemetry_fn(item["payload"])
            elif item["kind"] == "callback":
                ok = await send_callback_fn(item["payload"])
            else:
                ok = True  # unknown kind — drop it

            if ok:
                ack(item["id"])
            else:
                nack(item["id"])
        except Exception as exc:
            logger.warning("Drain error item=%d: %s", item["id"], exc)
            nack(item["id"])
        await asyncio.sleep(0)  # yield between items
