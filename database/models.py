"""
SQL-схема базы данных.
Простые таблицы SQLite, без ORM — так проще поддерживать маленький проект.
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    source TEXT,
    first_material TEXT,
    consent_data INTEGER DEFAULT 0,
    consent_marketing INTEGER DEFAULT 0,
    client_status TEXT DEFAULT 'lead',
    created_at TEXT,
    last_activity TEXT
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    file_id TEXT,
    file_type TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS material_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    file_id TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_name TEXT,
    created_at TEXT,
    FOREIGN KEY (material_id) REFERENCES materials (id)
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount INTEGER,
    status TEXT DEFAULT 'pending',
    receipt_file_id TEXT,
    receipt_file_type TEXT,
    source TEXT,
    created_at TEXT,
    confirmed_at TEXT,
    confirmed_by INTEGER,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS briefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT,
    instagram TEXT,
    goal TEXT,
    problem TEXT,
    expectation TEXT,
    file_id TEXT,
    file_type TEXT,
    file_name TEXT,
    drive_file_url TEXT,
    created_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    google_event_id TEXT,
    start_time TEXT,
    end_time TEXT,
    status TEXT DEFAULT 'confirmed',
    created_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS schedule_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    reason TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS admin_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER,
    action TEXT,
    target TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Простой лог событий для статистики (нажатия кнопок, ключевые шаги воронки)
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    event_type TEXT,
    event_data TEXT,
    created_at TEXT
);
"""
