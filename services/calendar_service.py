"""
Работа с Google Calendar.

Логика максимально простая:
- один календарь (GOOGLE_CALENDAR_ID);
- рабочие часы и длительность встречи берутся из .env;
- свободные слоты вычисляются как рабочие часы минус занятые интервалы.

Авторизация выполняется один раз через google_auth.py (см. README),
токен сохраняется в google/token.json и переиспользуется/обновляется.
"""
import datetime as dt
import logging
import os

import pytz
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config
import database

logger = logging.getLogger("nasiba_bot")

SCOPES = ["https://www.googleapis.com/auth/calendar"]

_service = None


class CalendarUnavailable(Exception):
    """Календарь недоступен (нет токена / ошибка сети / ошибка API)."""


def _load_credentials():
    if not os.path.exists(config.GOOGLE_TOKEN_PATH):
        raise CalendarUnavailable(
            "Google Calendar не авторизован. Запусти google_auth.py один раз, "
            "как описано в README."
        )
    creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_PATH, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(config.GOOGLE_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds


def get_service():
    global _service
    if _service is not None:
        return _service
    try:
        creds = _load_credentials()
        _service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return _service
    except Exception as e:
        logger.error("Google Calendar недоступен: %s", e)
        raise CalendarUnavailable(str(e))


def _tz():
    return pytz.timezone(config.TIMEZONE)


def _work_hours_for_date(date: dt.date):
    tz = _tz()
    start_h, start_m = map(int, config.WORK_START.split(":"))
    end_h, end_m = map(int, config.WORK_END.split(":"))
    start = tz.localize(dt.datetime.combine(date, dt.time(start_h, start_m)))
    end = tz.localize(dt.datetime.combine(date, dt.time(end_h, end_m)))
    return start, end


def get_busy_intervals(date: dt.date):
    """Возвращает список (start, end) занятых интервалов в этот день (timezone-aware)."""
    service = get_service()
    day_start, day_end = _work_hours_for_date(date)
    try:
        events_result = service.events().list(
            calendarId=config.GOOGLE_CALENDAR_ID,
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except HttpError as e:
        logger.error("Ошибка Google Calendar API: %s", e)
        raise CalendarUnavailable(str(e))

    busy = []
    for event in events_result.get("items", []):
        start = event["start"].get("dateTime")
        end = event["end"].get("dateTime")
        if not start or not end:
            continue  # события на весь день пропускаем
        busy.append((
            dt.datetime.fromisoformat(start),
            dt.datetime.fromisoformat(end),
        ))
    return busy


def get_free_slots(date: dt.date):
    """Список datetime (timezone-aware) свободных слотов начала встречи."""
    tz = _tz()
    now = dt.datetime.now(tz)
    day_start, day_end = _work_hours_for_date(date)
    duration = dt.timedelta(minutes=config.APPOINTMENT_DURATION)

    busy = get_busy_intervals(date)
    blocked = [
        (dt.datetime.fromisoformat(row["start_time"]), dt.datetime.fromisoformat(row["end_time"]))
        for row in database.list_schedule_blocks_for_date(date.isoformat())
    ]

    slots = []
    cursor = day_start
    step = dt.timedelta(minutes=30)
    while cursor + duration <= day_end:
        slot_end = cursor + duration
        if cursor > now:  # не предлагаем прошедшее время
            intervals = busy + blocked
            overlaps = any(cursor < b_end and slot_end > b_start for b_start, b_end in intervals)
            if not overlaps:
                slots.append(cursor)
        cursor += step
    return slots


def create_event(summary: str, description: str, start: dt.datetime, end: dt.datetime) -> str:
    service = get_service()
    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": config.TIMEZONE},
        "end": {"dateTime": end.isoformat(), "timeZone": config.TIMEZONE},
    }
    try:
        created = service.events().insert(
            calendarId=config.GOOGLE_CALENDAR_ID, body=event
        ).execute()
        return created.get("id")
    except HttpError as e:
        logger.error("Не удалось создать событие в Google Calendar: %s", e)
        raise CalendarUnavailable(str(e))


def delete_event(event_id: str):
    if not event_id:
        return
    service = get_service()
    try:
        service.events().delete(calendarId=config.GOOGLE_CALENDAR_ID, eventId=event_id).execute()
    except HttpError as e:
        logger.warning("Не удалось удалить событие %s: %s", event_id, e)
