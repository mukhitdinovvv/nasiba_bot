"""
Слой доступа к базе данных SQLite.
Никакой ORM — простые функции с обычными SQL-запросами.
Одно соединение на процесс, потокобезопасность обеспечивается
check_same_thread=False (telebot использует несколько потоков,
но нагрузка на маленький проект невелика).
"""
import sqlite3
import threading
from datetime import datetime

import config
from .models import SCHEMA

_lock = threading.Lock()
_conn = None


def get_conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(config.DATABASE_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def init_db():
    conn = get_conn()
    with _lock:
        conn.executescript(SCHEMA)
        _add_column_if_missing(conn, "users", "client_status", "TEXT DEFAULT 'lead'")
        _add_column_if_missing(conn, "briefs", "file_id", "TEXT")
        _add_column_if_missing(conn, "briefs", "file_type", "TEXT")
        _add_column_if_missing(conn, "briefs", "file_name", "TEXT")
        _add_column_if_missing(conn, "briefs", "drive_file_url", "TEXT")
        conn.execute(
            """INSERT INTO material_files (material_id, file_id, file_type, created_at)
               SELECT id, file_id, file_type, created_at FROM materials
               WHERE file_id IS NOT NULL
                 AND NOT EXISTS (
                     SELECT 1 FROM material_files WHERE material_files.material_id = materials.id
                 )"""
        )
        conn.commit()


def _add_column_if_missing(conn, table: str, column: str, definition: str):
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _execute(query: str, params: tuple = ()):
    conn = get_conn()
    with _lock:
        cur = conn.execute(query, params)
        conn.commit()
        return cur


def _fetchone(query: str, params: tuple = ()):
    conn = get_conn()
    with _lock:
        cur = conn.execute(query, params)
        return cur.fetchone()


def _fetchall(query: str, params: tuple = ()):
    conn = get_conn()
    with _lock:
        cur = conn.execute(query, params)
        return cur.fetchall()


# ---------------------------------------------------------------------------
# USERS
# ---------------------------------------------------------------------------

def get_user_by_telegram_id(telegram_id: int):
    return _fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))


def get_user_by_id(user_id: int):
    return _fetchone("SELECT * FROM users WHERE id = ?", (user_id,))


def get_or_create_user(tg_user, source: str = None) -> sqlite3.Row:
    """Находит пользователя по telegram_id либо создаёт нового.
    source указывается только при первом создании (не перезаписывается)."""
    existing = get_user_by_telegram_id(tg_user.id)
    if existing:
        _execute(
            "UPDATE users SET username=?, first_name=?, last_name=?, last_activity=? WHERE telegram_id=?",
            (tg_user.username, tg_user.first_name, tg_user.last_name, now(), tg_user.id),
        )
        return get_user_by_telegram_id(tg_user.id)

    _execute(
        """INSERT INTO users
           (telegram_id, username, first_name, last_name, source, first_material,
            consent_data, consent_marketing, created_at, last_activity)
           VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?)""",
        (
            tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name,
            source, None, now(), now(),
        ),
    )
    return get_user_by_telegram_id(tg_user.id)


def set_user_source_and_first_material(telegram_id: int, source: str):
    """Записывает источник, только если он ещё не был установлен ранее."""
    user = get_user_by_telegram_id(telegram_id)
    if user and not user["source"]:
        _execute(
            "UPDATE users SET source=?, first_material=? WHERE telegram_id=?",
            (source, source, telegram_id),
        )


def set_consent_data(telegram_id: int):
    _execute("UPDATE users SET consent_data=1 WHERE telegram_id=?", (telegram_id,))


def set_consent_marketing(telegram_id: int, value: bool):
    _execute("UPDATE users SET consent_marketing=? WHERE telegram_id=?", (1 if value else 0, telegram_id))


def touch_user(telegram_id: int):
    _execute("UPDATE users SET last_activity=? WHERE telegram_id=?", (now(), telegram_id))


def list_users(limit: int = 30, offset: int = 0):
    return _fetchall(
        "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)
    )


def count_users() -> int:
    row = _fetchone("SELECT COUNT(*) AS c FROM users")
    return row["c"] if row else 0


# ---------------------------------------------------------------------------
# MATERIALS
# ---------------------------------------------------------------------------

def get_material_by_slug(slug: str):
    return _fetchone(
        "SELECT * FROM materials WHERE slug = ? AND is_active = 1", (slug,)
    )


def get_material_by_id(material_id: int):
    return _fetchone("SELECT * FROM materials WHERE id = ?", (material_id,))


def list_active_materials():
    return _fetchall(
        "SELECT * FROM materials WHERE is_active = 1 ORDER BY created_at DESC"
    )


def list_all_materials():
    return _fetchall("SELECT * FROM materials ORDER BY created_at DESC")


def slug_exists(slug: str) -> bool:
    return _fetchone("SELECT 1 FROM materials WHERE slug = ?", (slug,)) is not None


def add_material(slug: str, title: str, description: str, file_id: str, file_type: str):
    _execute(
        """INSERT INTO materials (slug, title, description, file_id, file_type, is_active, created_at)
           VALUES (?, ?, ?, ?, ?, 1, ?)""",
        (slug, title, description, file_id, file_type, now()),
    )
    material = get_material_by_slug(slug)
    add_material_file(material["id"], file_id, file_type)
    return material


def add_material_file(material_id: int, file_id: str, file_type: str, file_name: str = None):
    _execute(
        """INSERT INTO material_files (material_id, file_id, file_type, file_name, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (material_id, file_id, file_type, file_name, now()),
    )


def list_material_files(material_id: int):
    return _fetchall(
        "SELECT * FROM material_files WHERE material_id=? ORDER BY id ASC", (material_id,)
    )


def update_material(material_id: int, title: str = None, description: str = None):
    material = get_material_by_id(material_id)
    if not material:
        return None
    new_title = title if title is not None else material["title"]
    new_desc = description if description is not None else material["description"]
    _execute(
        "UPDATE materials SET title=?, description=? WHERE id=?",
        (new_title, new_desc, material_id),
    )
    return get_material_by_id(material_id)


def deactivate_material(material_id: int):
    _execute("UPDATE materials SET is_active=0 WHERE id=?", (material_id,))


def activate_material(material_id: int):
    _execute("UPDATE materials SET is_active=1 WHERE id=?", (material_id,))


# ---------------------------------------------------------------------------
# PAYMENTS
# ---------------------------------------------------------------------------

def create_payment(user_id: int, amount: int, source: str):
    _execute(
        """INSERT INTO payments (user_id, amount, status, source, created_at)
           VALUES (?, ?, 'pending', ?, ?)""",
        (user_id, amount, source, now()),
    )
    row = _fetchone(
        "SELECT * FROM payments WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)
    )
    return row


def attach_receipt(payment_id: int, file_id: str, file_type: str):
    _execute(
        "UPDATE payments SET receipt_file_id=?, receipt_file_type=?, status='pending' WHERE id=?",
        (file_id, file_type, payment_id),
    )


def get_payment(payment_id: int):
    return _fetchone("SELECT * FROM payments WHERE id = ?", (payment_id,))


def get_pending_payment_for_user(user_id: int):
    """Последний платёж пользователя без чека или в статусе pending/rejected."""
    return _fetchone(
        """SELECT * FROM payments WHERE user_id=? AND status IN ('pending','rejected')
           ORDER BY id DESC LIMIT 1""",
        (user_id,),
    )


def get_confirmed_payment_for_user(user_id: int):
    return _fetchone(
        "SELECT * FROM payments WHERE user_id=? AND status='confirmed' ORDER BY id DESC LIMIT 1",
        (user_id,),
    )


def update_payment_status(payment_id: int, status: str, admin_id: int = None):
    if status == "confirmed":
        _execute(
            "UPDATE payments SET status=?, confirmed_at=?, confirmed_by=? WHERE id=?",
            (status, now(), admin_id, payment_id),
        )
    else:
        _execute("UPDATE payments SET status=? WHERE id=?", (status, payment_id))


def list_payments_by_status(status: str, limit: int = 20):
    return _fetchall(
        "SELECT * FROM payments WHERE status=? ORDER BY created_at DESC LIMIT ?",
        (status, limit),
    )


def count_payments_with_receipt() -> int:
    row = _fetchone("SELECT COUNT(*) AS c FROM payments WHERE receipt_file_id IS NOT NULL")
    return row["c"] if row else 0


def count_payments_by_status(status: str) -> int:
    row = _fetchone("SELECT COUNT(*) AS c FROM payments WHERE status=?", (status,))
    return row["c"] if row else 0


# ---------------------------------------------------------------------------
# BRIEFS
# ---------------------------------------------------------------------------

def create_brief(user_id: int, name, instagram, goal, problem, expectation):
    _execute(
        """INSERT INTO briefs (user_id, name, instagram, goal, problem, expectation, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, name, instagram, goal, problem, expectation, now()),
    )
    return get_brief_for_user(user_id)


def get_brief_for_user(user_id: int):
    return _fetchone(
        "SELECT * FROM briefs WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)
    )


def create_file_brief(user_id: int, file_id: str, file_type: str, file_name: str, drive_file_url: str):
    _execute(
        """INSERT INTO briefs (user_id, file_id, file_type, file_name, drive_file_url, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, file_id, file_type, file_name, drive_file_url, now()),
    )
    return get_brief_for_user(user_id)


def get_uploaded_brief_for_user(user_id: int):
    return _fetchone(
        """SELECT * FROM briefs WHERE user_id=? AND file_id IS NOT NULL
           ORDER BY id DESC LIMIT 1""",
        (user_id,),
    )


def get_setting(key: str):
    row = _fetchone("SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else None


def set_setting(key: str, value: str):
    _execute(
        """INSERT INTO settings (key, value) VALUES (?, ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
        (key, value),
    )


# ---------------------------------------------------------------------------
# APPOINTMENTS
# ---------------------------------------------------------------------------

def create_appointment(user_id: int, google_event_id: str, start_time: str, end_time: str):
    _execute(
        """INSERT INTO appointments (user_id, google_event_id, start_time, end_time, status, created_at)
           VALUES (?, ?, ?, ?, 'confirmed', ?)""",
        (user_id, google_event_id, start_time, end_time, now()),
    )
    return get_active_appointment_for_user(user_id)


def get_active_appointment_for_user(user_id: int):
    return _fetchone(
        """SELECT * FROM appointments WHERE user_id=? AND status='confirmed'
           ORDER BY start_time DESC LIMIT 1""",
        (user_id,),
    )


def get_appointment_by_id(appointment_id: int):
    return _fetchone("SELECT * FROM appointments WHERE id=?", (appointment_id,))


def cancel_appointment(appointment_id: int):
    _execute("UPDATE appointments SET status='cancelled' WHERE id=?", (appointment_id,))


def complete_appointment(appointment_id: int):
    _execute("UPDATE appointments SET status='completed' WHERE id=?", (appointment_id,))


def reschedule_appointment(appointment_id: int, google_event_id: str, start_time: str, end_time: str):
    _execute(
        """UPDATE appointments SET google_event_id=?, start_time=?, end_time=?, status='confirmed'
           WHERE id=?""",
        (google_event_id, start_time, end_time, appointment_id),
    )
    return get_appointment_by_id(appointment_id)


def list_upcoming_appointments(limit: int = 20):
    return _fetchall(
        """SELECT * FROM appointments WHERE status='confirmed' AND start_time >= ?
           ORDER BY start_time ASC LIMIT ?""",
        (now(), limit),
    )


# ---------------------------------------------------------------------------
# SCHEDULE BLOCKS
# ---------------------------------------------------------------------------

def add_schedule_block(start_time: str, end_time: str, reason: str = None):
    _execute(
        "INSERT INTO schedule_blocks (start_time, end_time, reason, created_at) VALUES (?, ?, ?, ?)",
        (start_time, end_time, reason, now()),
    )


def remove_schedule_blocks_for_date(date: str):
    _execute("DELETE FROM schedule_blocks WHERE start_time LIKE ?", (f"{date}%",))


def list_schedule_blocks_for_date(date: str):
    return _fetchall(
        "SELECT * FROM schedule_blocks WHERE start_time LIKE ? ORDER BY start_time ASC",
        (f"{date}%",),
    )


def list_confirmed_appointments_for_date(date: str):
    return _fetchall(
        """SELECT * FROM appointments WHERE status='confirmed' AND start_time LIKE ?
           ORDER BY start_time ASC""",
        (f"{date}%",),
    )


def list_appointments_by_status(status: str, limit: int = 50):
    return _fetchall(
        "SELECT * FROM appointments WHERE status=? ORDER BY start_time DESC LIMIT ?",
        (status, limit),
    )


def set_client_status(user_id: int, status: str):
    _execute("UPDATE users SET client_status=? WHERE id=?", (status, user_id))


def count_appointments() -> int:
    row = _fetchone("SELECT COUNT(*) AS c FROM appointments WHERE status='confirmed'")
    return row["c"] if row else 0


# ---------------------------------------------------------------------------
# EVENTS (для статистики)
# ---------------------------------------------------------------------------

def log_event(user_id, event_type: str, event_data: str = None):
    _execute(
        "INSERT INTO events (user_id, event_type, event_data, created_at) VALUES (?, ?, ?, ?)",
        (user_id, event_type, event_data, now()),
    )


def count_event(event_type: str) -> int:
    row = _fetchone("SELECT COUNT(*) AS c FROM events WHERE event_type=?", (event_type,))
    return row["c"] if row else 0


def count_users_by_source(source: str) -> int:
    row = _fetchone("SELECT COUNT(*) AS c FROM users WHERE source=?", (source,))
    return row["c"] if row else 0


def list_distinct_sources():
    rows = _fetchall(
        "SELECT DISTINCT source FROM users WHERE source IS NOT NULL"
    )
    return [r["source"] for r in rows]
