"""Планувальник Telegram-нагадувань.

Нагадування зберігаються у профілі користувача:
    reminders = {
        "timezone_offset": 0,        # години відносно UTC
        "wind_down": {"enabled": True, "time": "22:30"},   # підготовка до сну
        "log":       {"enabled": True, "time": "08:00"},   # записати сон
        "morning":   {"enabled": False, "time": "07:30"},  # ранкове
        "goal":      {"enabled": False, "time": "23:00"},  # цільовий час сну
    }
    reminders_last_sent = {"wind_down": "2026-08-14", ...}
"""
import asyncio
import logging

import timeutil

REMINDER_TYPES = ("wind_down", "log", "morning", "goal")

DEFAULT_REMINDERS = {
    "timezone_offset": 0,
    "wind_down": {"enabled": True, "time": "22:30"},
    "log": {"enabled": True, "time": "08:00"},
    "morning": {"enabled": False, "time": "07:30"},
    "goal": {"enabled": False, "time": "23:00"},
}


def get_reminders(profile):
    rem = profile.get("reminders") or {}
    merged = {k: dict(v) for k, v in DEFAULT_REMINDERS.items() if isinstance(v, dict)}
    for k, v in rem.items():
        if isinstance(v, dict):
            merged[k] = {**merged.get(k, {}), **v}
        else:
            merged[k] = v
    return merged


def parse_rem_time(value):
    try:
        h, m = str(value).split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


class ReminderScheduler:
    def __init__(self, bot, load_profile_fn, save_profile_fn):
        self.bot = bot
        self.load_profile = load_profile_fn
        self.save_profile = save_profile_fn
        self._task = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self):
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logging.error(f"ReminderScheduler error: {e}")
            await asyncio.sleep(30)

    def _local_now(self, profile):
        """Поточний час у timezone користувача (IANA, profile["timezone"])."""
        return timeutil.utc_now().astimezone(timeutil.get_user_timezone(profile))

    async def _tick(self):
        from bot import load_user_data, save_user_data  # локальний імпорт, щоб уникнути циклів
        data = load_user_data()

        for uid, profile in data.items():
            if not profile.get("is_configured"):
                continue
            rem = get_reminders(profile)
            local = self._local_now(profile)
            current_min = local.hour * 60 + local.minute
            local_date = local.date().isoformat()

            for rtype in REMINDER_TYPES:
                cfg = rem.get(rtype) or {}
                if not cfg.get("enabled"):
                    continue
                rtime = parse_rem_time(cfg.get("time"))
                if rtime is None:
                    continue
                if current_min == rtime:
                    last = (profile.get("reminders_last_sent") or {}).get(rtype)
                    if last == local_date:
                        continue
                    await self._send(uid, rtype, local_date)

    async def _send(self, uid, rtype, local_date):
        try:
            from bot import get_text  # локальний імпорт
            profile = self.load_profile(uid)
            text = get_text(profile, f"rem_{rtype}")
            await self.bot.send_message(chat_id=int(uid), text=text, parse_mode="Markdown")
            profile.setdefault("reminders_last_sent", {})[rtype] = local_date
            self.save_profile(uid, profile)
        except Exception as e:
            logging.warning(f"Reminder send failed for {uid} ({rtype}): {e}")