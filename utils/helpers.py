import logging
import re
from datetime import datetime

import config

logger = logging.getLogger("nasiba_bot")

SLUG_RE = re.compile(r"^[a-zA-Z0-9_]+$")


def is_admin(telegram_id: int) -> bool:
    return bool(config.ADMIN_TELEGRAM_ID) and telegram_id == config.ADMIN_TELEGRAM_ID


def is_valid_slug(slug: str) -> bool:
    return bool(slug) and bool(SLUG_RE.match(slug))


def deep_link(slug: str) -> str:
    username = config.BOT_USERNAME or "your_bot"
    return f"https://t.me/{username}?start={slug}"


def safe_call(func, *args, **kwargs):
    """Оборачивает вызов и логирует ошибку вместо падения бота."""
    try:
        return func(*args, **kwargs)
    except Exception:
        logger.exception("Ошибка при выполнении %s", getattr(func, "__name__", func))
        return None


def format_date_human(dt: datetime) -> str:
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
    return f"{dt.day} {months[dt.month - 1]}"


def format_time_human(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def user_display_name(user_row) -> str:
    if user_row is None:
        return "—"
    parts = [user_row["first_name"] or "", user_row["last_name"] or ""]
    name = " ".join(p for p in parts if p).strip()
    return name or (user_row["username"] or str(user_row["telegram_id"]))
