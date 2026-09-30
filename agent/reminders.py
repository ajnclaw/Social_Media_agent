# reminders.py
#
# Reminders live in a small SQLite database (agent/../reminders.db), not a
# flat JSON file like memory.py -- they need real queries ("what's still
# pending", "mark these delivered") rather than just key/value lookup.

import sqlite3
import uuid
from datetime import datetime, timedelta

from .config import REMINDERS_DB


class InvalidReminderTime(ValueError):
    pass


def _connect():
    conn = sqlite3.connect(REMINDERS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id TEXT PRIMARY KEY,
            message TEXT NOT NULL,
            when_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            delivered INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    return conn


def _row_to_dict(row):
    return {
        "id": row["id"],
        "message": row["message"],
        "when": row["when_at"],
        "created_at": row["created_at"],
        "delivered": bool(row["delivered"]),
    }


def _ensure_offset(when):
    """
    The model is given the *server's* current time, complete with its
    UTC offset, and asked to compute an absolute datetime from it -- but
    nothing stops it from dropping the offset in its actual answer. A
    naive datetime (no offset) would then get parsed as local time by
    whatever reads it next -- which is the phone, in a different
    timezone than the server that did the computing. Silently attaching
    the server's own current offset when one is missing removes that
    failure mode: it's the same reference frame the model reasoned in,
    so the absolute instant it meant is preserved either way.
    """
    try:
        parsed = datetime.fromisoformat(when)
    except ValueError:
        return when  # not parseable here; stored as-is, phone-side parse will fail loudly instead of silently

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)

    return parsed.isoformat()


def _validate_when(when, now):
    """
    The model occasionally hallucinates a wildly wrong absolute datetime
    (observed live: asked for "in 3 minutes", got back a date from 2023)
    instead of actually computing from the current time it was given.
    Silently accepting that means a reminder that can never fire -- the
    phone correctly refuses to schedule anything already in the past, so
    it just vanishes with no one the wiser. Raising here instead turns
    that into a tool error the model sees and can recompute from, rather
    than a silent no-op.
    """
    try:
        parsed = datetime.fromisoformat(when)
    except ValueError as exc:
        raise InvalidReminderTime(
            f"'{when}' is not a valid ISO 8601 datetime: {exc}. "
            f"The current time is {now.isoformat()} -- compute an "
            f"absolute datetime after that from the user's request."
        ) from exc

    if parsed < now - timedelta(minutes=1):
        raise InvalidReminderTime(
            f"Computed reminder time {when} is in the past. The actual "
            f"current time is {now.isoformat()} -- recompute 'when' as "
            f"an absolute datetime after that, using the user's "
            f"requested delay or time."
        )

    if parsed > now + timedelta(days=365):
        raise InvalidReminderTime(
            f"Computed reminder time {when} is more than a year out, "
            f"which almost certainly isn't what the user meant. The "
            f"current time is {now.isoformat()} -- double check the "
            f"date and recompute."
        )


def add_reminder(message, when):
    """
    `when` must be an absolute ISO 8601 datetime string -- resolving
    relative language ("in 10 minutes", "tomorrow at 9am") against the
    current time given in the model's prompt happens before this is
    called, not here. See _ensure_offset() for why a missing offset
    gets filled in rather than trusted as-is, and _validate_when() for
    why an implausible result is rejected rather than stored.
    """
    now = datetime.now().astimezone()
    reminder_id = uuid.uuid4().hex[:8]
    created_at = now.isoformat()
    when = _ensure_offset(when)

    _validate_when(when, now)

    with _connect() as conn:
        conn.execute(
            "INSERT INTO reminders (id, message, when_at, created_at, delivered) "
            "VALUES (?, ?, ?, ?, 0)",
            (reminder_id, message, when, created_at),
        )

    return {
        "id": reminder_id,
        "message": message,
        "when": when,
        "created_at": created_at,
        "delivered": False,
    }


def list_reminders(include_delivered=False):
    with _connect() as conn:
        if include_delivered:
            rows = conn.execute("SELECT * FROM reminders ORDER BY when_at").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE delivered = 0 ORDER BY when_at"
            ).fetchall()

    return [_row_to_dict(row) for row in rows]


def mark_delivered(reminder_ids):
    if not reminder_ids:
        return

    with _connect() as conn:
        conn.executemany(
            "UPDATE reminders SET delivered = 1 WHERE id = ?",
            [(reminder_id,) for reminder_id in reminder_ids],
        )
