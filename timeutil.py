"""Timezone-aware часова логіка.

Єдине правило роботи з часом:
- УСІ timestamps зберігаємо в UTC (aware).
- Для відображення користувачу конвертуємо в його timezone (IANA-ім'я).
- Timezone користувача зберігається в профілі (profile["timezone"], IANA),
  для України — Europe/Kyiv, а не ручне "+3".
- Naive timestamps із легасі-даних трактуємо як UTC (сервер завжди в UTC).

Модуль чистий (без Telegram) — легко тестувати.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Europe/Kyiv"

# Best-effort мапа зміщень старого пікера "UTC+/-N" → IANA-зона.
# Для України (UTC+3) — Europe/Kyiv.
OFFSET_TO_ZONE = {
    -12: "Etc/GMT+12", -11: "Etc/GMT+11", -10: "Etc/GMT+10", -9: "Etc/GMT+9",
    -8: "Etc/GMT+8", -7: "Etc/GMT+7", -6: "Etc/GMT+6", -5: "Etc/GMT+5",
    -4: "Etc/GMT+4", -3: "Etc/GMT+3", -2: "Etc/GMT+2", -1: "Etc/GMT+1",
    0: "Etc/UTC",
    1: "Etc/GMT-1", 2: "Etc/GMT-2", 3: "Europe/Kyiv", 4: "Etc/GMT-4",
    5: "Etc/GMT-5", 6: "Etc/GMT-6", 7: "Etc/GMT-7", 8: "Etc/GMT-8",
    9: "Etc/GMT-9", 10: "Etc/GMT-10", 11: "Etc/GMT-11", 12: "Etc/GMT-12",
}


def get_user_timezone(profile):
    """ZoneInfo із профілю користувача; дефолт — Europe/Kyiv."""
    tz_name = (profile or {}).get("timezone") or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def utc_now():
    """Поточний момент як UTC-aware datetime. Єдині годинники проєкту."""
    return datetime.now(timezone.utc)


def to_utc(dt):
    """Naive/aware → UTC-aware. Naive трактуємо як UTC (легасі-записи)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_local(dt, zone):
    """UTC(naive→UTC)-момент → aware у зоні користувача."""
    return to_utc(dt).astimezone(zone)


def parse_stored_dt(value):
    """Парсимо збережений ISO. Легасі naive → UTC."""
    if not value:
        return None
    try:
        return to_utc(datetime.fromisoformat(str(value)))
    except (ValueError, TypeError):
        return None


def utc_iso(dt):
    """ISO-рядок із зсувом, напр. 2026-08-14T19:30:00+00:00."""
    return to_utc(dt).isoformat()


def local_time_str(dt, zone):
    """'HH:MM' у локальному часі користувача."""
    return to_local(dt, zone).strftime("%H:%M")


def local_datetime_str(dt, zone):
    """'YYYY-MM-DD HH:MM' у локальному часі користувача."""
    return to_local(dt, zone).strftime("%Y-%m-%d %H:%M")


def local_date_iso(dt, zone):
    """'YYYY-MM-DD' (дата в часовому поясі користувача)."""
    return to_local(dt, zone).date().isoformat()


def local_date_dmy(dt, zone):
    """'DD.MM.YYYY' (дата в часовому поясі користувача)."""
    return to_local(dt, zone).strftime("%d.%m.%Y")


def local_today(zone):
    """Сьогоднішня дата (date) у зоні користувача."""
    return to_local(utc_now(), zone).date()