"""Чиста логіка аналізу сну: Sleep Score, тенденції, рекомендації, гейміфікація.

Модуль не знає про Telegram — лише обчислення. Локалізація виконується в bot.py.
"""
import math
from datetime import datetime, timedelta

MAX_SCORE = 100

# --- Допоміжні функції часу ---

def parse_hhmm(value):
    if not value:
        return None
    try:
        h, m = str(value).split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def minutes_to_hhmm(total_min):
    total_min = int(total_min) % (24 * 60)
    return f"{total_min // 60:02d}:{total_min % 60:02d}"


def evening_minutes(total_min):
    """Час засинання подаємо як хвилини після 18:00, щоб 23:30 і 01:30 були поряд."""
    if total_min is None:
        return None
    return (total_min - 18 * 60) % (24 * 60)


def circular_distance_min(a, b):
    """Мінімальна відстань між двома моментами доби (хвилини)."""
    d = abs(a - b) % (24 * 60)
    return min(d, 24 * 60 - d)


def parse_log_date(date_str):
    try:
        return datetime.strptime(str(date_str), "%d.%m.%Y")
    except (ValueError, TypeError):
        return None


def duration_to_text(duration_hours):
    """7.7 год -> '7 год 42 хв'."""
    if duration_hours is None:
        return None
    total_min = int(round(duration_hours * 60))
    h, m = divmod(total_min, 60)
    return f"{h} год {m} хв" if h else f"{m} хв"


# --- Sleep Score ---

def _duration_points(duration, target):
    if duration is None:
        return 12, "missing"
    if duration >= target:
        return 30, "ok"
    loss = int((target - duration) / 0.5) * 5
    return max(5, 30 - loss), "low"


def _quality_points(log):
    q = log.get("quality_num")
    if q is None:
        return 12, "missing"
    return max(0, min(20, int(round(q)) * 2)), "ok"


def _wakeups_points(log):
    w = log.get("wakeups")
    if w is None:
        return 6, "missing"
    try:
        w = int(w)
    except (ValueError, TypeError):
        return 6, "missing"
    if w <= 0:
        return 10, "ok"
    if w == 1:
        return 7, "some"
    if w == 2:
        return 4, "many"
    return 1, "many"


def _goal_deviation_points(actual_min, goal_min, max_points):
    if actual_min is None or goal_min is None:
        return max_points // 2, "missing"
    dev = circular_distance_min(evening_minutes(actual_min), evening_minutes(goal_min))
    if dev <= 30:
        return max_points, "ok"
    if dev <= 60:
        return int(max_points * 0.75), "some"
    if dev <= 90:
        return int(max_points * 0.5), "big"
    return int(max_points * 0.25), "big"


def _yes_no_points(value, max_points):
    if value is None:
        return max_points // 2, "missing"
    return (max_points, "ok") if not value else (1, "bad")


def compute_sleep_score(profile, log):
    """Повертає (score, components), де components — dict з деталями для пояснення."""
    if not isinstance(log, dict):
        return 0, {}

    target = profile.get("_target_hours", 8.0)
    goal_bedtime = profile.get("_goal_bedtime")
    goal_waketime = profile.get("_goal_waketime")

    duration = log.get("duration")
    d_points, d_status = _duration_points(duration, target)
    q_points, q_status = _quality_points(log)
    w_points, w_status = _wakeups_points(log)
    b_points, b_status = _goal_deviation_points(
        parse_hhmm(log.get("bedtime")), parse_hhmm(goal_bedtime), 15)
    k_points, k_status = _goal_deviation_points(
        parse_hhmm(log.get("waketime")), parse_hhmm(goal_waketime), 15)
    c_points, c_status = _yes_no_points(log.get("caffeine"), 5)
    s_points, s_status = _yes_no_points(log.get("screens"), 5)

    score = d_points + q_points + w_points + b_points + k_points + c_points + s_points

    components = {
        "score": score,
        "duration": {"points": d_points, "status": d_status},
        "quality": {"points": q_points, "status": q_status},
        "wakeups": {"points": w_points, "status": w_status},
        "bedtime": {"points": b_points, "status": b_status},
        "waketime": {"points": k_points, "status": k_status},
        "caffeine": {"points": c_points, "status": c_status},
        "screens": {"points": s_points, "status": s_status},
    }
    return score, components


def explain_score(components):
    """Повертає (good_keys, bad_keys, tip_keys) — ключі для локалізації."""
    good = []
    bad = []
    tips = []

    if components.get("duration", {}).get("status") == "ok":
        good.append("duration_ok")
    elif components.get("duration", {}).get("status") == "low":
        bad.append("duration_low")
        tips.append("tip_duration")

    if components.get("quality", {}).get("status") == "ok":
        good.append("quality_ok")
    elif components.get("quality", {}).get("points", 0) < 12:
        bad.append("quality_low")

    if components.get("wakeups", {}).get("status") == "ok":
        good.append("wakeups_ok")
    elif components.get("wakeups", {}).get("status") == "many":
        bad.append("wakeups_many")
        tips.append("tip_wakeups")

    if components.get("bedtime", {}).get("status") == "ok":
        good.append("bedtime_ok")
    elif components.get("bedtime", {}).get("status") == "big":
        bad.append("bedtime_late")
        tips.append("tip_bedtime")

    if components.get("waketime", {}).get("status") == "ok":
        good.append("waketime_ok")
    elif components.get("waketime", {}).get("status") == "big":
        bad.append("waketime_late")

    if components.get("caffeine", {}).get("status") == "bad":
        bad.append("caffeine_bad")
        tips.append("tip_caffeine")
    if components.get("screens", {}).get("status") == "bad":
        bad.append("screens_bad")
        tips.append("tip_screens")

    return good, bad, tips[:3]


# --- Тенденції ---

def _avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _stddev(values):
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def analyze_trends(profile, logs, days):
    """Аналіз останніх N днів: середні, найкращий/найгірший день, стабільність."""
    recent = list(logs[:days]) if isinstance(logs, list) else []
    result = {
        "days": days,
        "count": len(recent),
        "avg_duration": _avg([l.get("duration") for l in recent]),
        "avg_score": _avg([l.get("score") for l in recent if l.get("score") is not None]),
        "avg_bedtime": None,
        "avg_waketime": None,
        "bedtime_stddev_min": None,
        "waketime_stddev_min": None,
        "stability": None,
        "best": None,
        "worst": None,
    }
    if not recent:
        return result

    bedtimes = [parse_hhmm(l.get("bedtime")) for l in recent]
    waketimes = [parse_hhmm(l.get("waketime")) for l in recent]
    bed_evening = [evening_minutes(b) for b in bedtimes if b is not None]
    wake_plain = [w for w in waketimes if w is not None]

    if bed_evening:
        result["avg_bedtime"] = minutes_to_hhmm((18 * 60 + _avg(bed_evening)) % (24 * 60))
        result["bedtime_stddev_min"] = round(_stddev(bed_evening))
    if wake_plain:
        result["avg_waketime"] = minutes_to_hhmm(_avg(wake_plain))
        result["waketime_stddev_min"] = round(_stddev(wake_plain))

    if result["bedtime_stddev_min"] is not None and result["waketime_stddev_min"] is not None:
        worst_std = max(result["bedtime_stddev_min"], result["waketime_stddev_min"])
        result["stability"] = "high" if worst_std < 45 else ("medium" if worst_std < 90 else "low")

    scored = [(l, l.get("score")) for l in recent if l.get("score") is not None]
    if scored:
        best = max(scored, key=lambda x: x[1])
        worst = min(scored, key=lambda x: x[1])
        result["best"] = {"date": best[0].get("date"), "score": best[1]}
        result["worst"] = {"date": worst[0].get("date"), "score": worst[1]}

    return result


def find_patterns(profile, logs, days=14):
    """Прості закономірності: пізнє засинання/кофеїн/екрани → нижчий Score."""
    recent = list(logs[:days]) if isinstance(logs, list) else []
    scored = [l for l in recent if l.get("score") is not None]
    if len(scored) < 3:
        return []

    goal_bedtime = profile.get("_goal_bedtime")
    goal_min = parse_hhmm(goal_bedtime) if goal_bedtime else None
    patterns = []

    def group_diff(predicate, label):
        good_grp = [l.get("score") for l in scored if not predicate(l)]
        bad_grp = [l.get("score") for l in scored if predicate(l)]
        if len(good_grp) >= 2 and len(bad_grp) >= 2:
            diff = round(_avg(bad_grp) - _avg(good_grp))
            if abs(diff) >= 5:
                patterns.append({
                    "label": label,
                    "score_diff": diff,
                    "good_count": len(good_grp),
                    "bad_count": len(bad_grp),
                })

    if goal_min:
        group_diff(
            lambda l: parse_hhmm(l.get("bedtime")) is not None
            and circular_distance_min(
                evening_minutes(parse_hhmm(l.get("bedtime"))), evening_minutes(goal_min)) > 60,
            "late_bedtime")

    group_diff(lambda l: bool(l.get("caffeine")), "caffeine")
    group_diff(lambda l: bool(l.get("screens")), "screens")
    group_diff(lambda l: int(l.get("wakeups") or 0) >= 2, "wakeups")

    return patterns


def build_recommendations(profile, logs):
    """Рекомендації на основі даних користувача (максимум 4, короткі)."""
    trends7 = analyze_trends(profile, logs, 7)
    recs = []

    target = profile.get("_target_hours", 8.0)
    goal_bedtime = profile.get("_goal_bedtime")

    if trends7["count"] >= 2:
        avg_dur = trends7["avg_duration"]
        if avg_dur is not None and avg_dur < target - 0.5:
            recs.append("rec_duration")

        if trends7["avg_bedtime"] and goal_bedtime:
            goal_min = parse_hhmm(goal_bedtime)
            avg_bed = parse_hhmm(trends7["avg_bedtime"])
            if goal_min is not None and avg_bed is not None and \
                    circular_distance_min(evening_minutes(avg_bed), evening_minutes(goal_min)) > 60:
                recs.append("rec_bedtime")

        if trends7["waketime_stddev_min"] is not None and trends7["waketime_stddev_min"] > 60:
            recs.append("rec_waketime")

        recent = list(logs[:7]) if isinstance(logs, list) else []
        if recent:
            screens_rate = _avg([1 if l.get("screens") else 0 for l in recent if l.get("screens") is not None])
            caffeine_rate = _avg([1 if l.get("caffeine") else 0 for l in recent if l.get("caffeine") is not None])
            wakeups_avg = _avg([l.get("wakeups") for l in recent if l.get("wakeups") is not None])
            if screens_rate is not None and screens_rate >= 0.5:
                recs.append("rec_screens")
            if caffeine_rate is not None and caffeine_rate >= 0.4:
                recs.append("rec_caffeine")
            if wakeups_avg is not None and wakeups_avg >= 2:
                recs.append("rec_wakeups")

    if not recs:
        recs.append("rec_keep")

    return recs[:4]


# --- Гейміфікація ---

def compute_streak(logs, today=None):
    """Кількість днів поспіль із записами (починаючи з останнього запису).

    `today` — дата (date) у локальній зоні користувача; якщо не передана,
    береться поточна дата UTC сервера (для сумісності з легасі-викликами).
    """
    if not isinstance(logs, list) or not logs:
        return 0
    dates = []
    for l in logs:
        d = parse_log_date(l.get("date"))
        if d:
            dates.append(d.date())
    dates = sorted(set(dates))
    if not dates:
        return 0

    last = dates[-1]
    if today is None:
        today = datetime.now().date()
    if (today - last).days > 1:
        return 0

    streak = 0
    cur = last
    while cur in dates:
        streak += 1
        cur = cur - timedelta(days=1)
    return streak


def compute_xp(logs):
    if not isinstance(logs, list):
        return 0
    xp = len(logs) * 10
    for l in logs:
        if int(l.get("quality_num") or 0) >= 8:
            xp += 5
        if l.get("score") is not None and l["score"] >= 80:
            xp += 5
    return xp


def level_from_xp(xp):
    return 1 + xp // 150


def level_progress(xp):
    """Частка прогресу до наступного рівня (0.0-1.0)."""
    return (xp % 150) / 150


ACHIEVEMENTS = [
    {"id": "first_log", "icon": "🏆", "xp": 20},
    {"id": "streak_3", "icon": "🔥", "xp": 30},
    {"id": "streak_7", "icon": "🔥", "xp": 70},
    {"id": "nights_8h_5", "icon": "🌙", "xp": 50},
    {"id": "score_90", "icon": "⭐", "xp": 40},
    {"id": "score_80_3", "icon": "💎", "xp": 45},
    {"id": "early_5", "icon": "🌅", "xp": 35},
    {"id": "no_phone_3", "icon": "📵", "xp": 30},
]


def check_achievements(logs, today=None):
    """Повертає dict {achievement_id: achieved_bool} для всіх досягнень.

    `today` — дата в локальній зоні користувача (для streak-досягнень).
    """
    if not isinstance(logs, list):
        logs = []
    has_quality = [l for l in logs if l.get("quality_num") is not None]
    has_score = [l for l in logs if l.get("score") is not None]
    return {
        "first_log": len(logs) >= 1,
        "streak_3": compute_streak(logs, today=today) >= 3,
        "streak_7": compute_streak(logs, today=today) >= 7,
        "nights_8h_5": len([l for l in logs if (l.get("duration") or 0) >= 8]) >= 5,
        "score_90": any(l.get("score") is not None and l["score"] >= 90 for l in has_score),
        "score_80_3": len([l for l in has_score if l["score"] >= 80]) >= 3,
        "early_5": len([l for l in logs if parse_hhmm(l.get("waketime")) is not None and parse_hhmm(l.get("waketime")) < 7 * 60]) >= 5,
        "no_phone_3": len([l for l in logs if l.get("screens") is False]) >= 3,
    }


def get_achievement(aid):
    for a in ACHIEVEMENTS:
        if a["id"] == aid:
            return a
    return None