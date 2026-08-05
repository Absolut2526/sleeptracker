import certifi
import os
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

import logging
import sys
import json
import asyncio
from datetime import datetime, timedelta
from aiohttp import web  # Додано для веб-сервера Render
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)
from g4f.client import Client

ai_client = Client()

# 🔑 Токен бота від @BotFather (зчитуємо з Environment Variables для безпеки)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8769890259:AAG3E0z5291d1OGwoJVSm9xmi2j2jQY2HbI")

# Ініціалізація бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

DATA_FILE = "sleep_ai_data.json"

LANGUAGES = {
    "uk": "🇺🇦 Українська",
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский"
}

# --- БАГАТОМОВНИЙ СЛОВНИК (I18N) ---
STRINGS = {
    "uk": {
        "welcome": "👋🌙 Ласкаво просимо до **ШІ-Помічника з покращення якості сну**!\n\n📋 **Крок 1 з 6:** Оберіть зручну мову спілкування:",
        "step_age": "🔹 **Крок 2 з 6:** Оберіть вашу **вікову категорію**:",
        "step_bedtime": "🔹 **Крок 3 з 6:** О котрій годині ви **зазвичай лягаєте спати**?",
        "step_waketime": "🔹 **Крок 4 з 6:** О котрій годині ви **зазвичай прокидаєтеся**?",
        "step_goal": "🔹 **Крок 5 з 6:** Яка ваша **головна мета** покращення сну?",
        "step_disruptor": "🔹 **Крок 6 з 6:** Що найчастіше **заважає вам якісно спати**?",
        "profile_created": "🎉 **Персональний ШІ-Профіль Сну створено!**",
        "btn_sleep": "🌙 Лягаю спати",
        "btn_wake": "☀️ Я прокинувся",
        "btn_ask_ai": "🤖 Запитати ШІ-Консультанта",
        "btn_caffeine": "☕ Кофеїновий таймер",
        "btn_stats": "📊 ШІ-Статистика & Борг",
        "btn_profile": "👤 Мій Профіль & Налаштування",
        "btn_cycles": "⏱️ Калькулятор циклів",
        "btn_journal": "📜 Журнал сну",
        "btn_breath": "🧘 Вправа 4-7-8",
        "btn_tips": "💡 Поради",
        "change_lang": "🌐 Змінити мову / Change language",
        "re_onboarding": "🔄 Пройти опитування знову",
        "toggle_rem": "Нагадування про сон",
        "going_to_sleep": "🌙 Надобраніч! Таймер сну запущено о {time}.\nТисніть «☀️ Я прокинувся», коли прокинетеся.",
        "already_sleeping": "🌙 Ви вже спите! Коли прокинетеся, натисніть «☀️ Я прокинувся».",
        "not_sleeping": "☀️ Ви ще не вмикали таймер сну. Натисніть «🌙 Лягаю спати».",
        "woke_up_ask_quality": "☀️ Доброго дня / ранку!\n⏱️ Ви проспали **{h} год {m} хв** ({hrs} год).\n\nЯк ви почуваєтеся? Оцініть якість сну:",
        "log_saved": "✅ **Запис сну збережено!**\n📅 Дата: {date}\n⏱️ Тривалість: **{duration} год** ({bedtime} - {waketime})\n✨ Оцінка: {quality}",
        "caff_title": "☕ **Кофеїновий калькулятор сну**\n\nО котрій годині ви випили останню порцію кави/енергетика?",
        "caff_result": "☕ **Аналіз виведення кофеїну:**\n\n⏰ Час вживання: **{time}**\n📉 50% кофеїну в крові до: **{half_life}**\n🟢 Безпечне очищення: о **{clear}**\n\n💡 **Порада ШІ:** Стежте, щоб 6-годинний період напіввиведення кофеїну закінчувався до вашого часу засинання!"
    },
    "en": {
        "welcome": "👋🌙 Welcome to the **AI Sleep Improvement Assistant**!\n\n📋 **Step 1 of 6:** Choose your preferred language:",
        "step_age": "🔹 **Step 2 of 6:** Choose your **age category**:",
        "step_bedtime": "🔹 **Step 3 of 6:** What time do you **usually go to bed**?",
        "step_waketime": "🔹 **Step 4 of 6:** What time do you **usually wake up**?",
        "step_goal": "🔹 **Step 5 of 6:** What is your **main sleep goal**?",
        "step_disruptor": "🔹 **Step 6 of 6:** What most often **disrupts your sleep**?",
        "profile_created": "🎉 **Personal AI Sleep Profile Created!**",
        "btn_sleep": "🌙 Going to sleep",
        "btn_wake": "☀️ I woke up",
        "btn_ask_ai": "🤖 Ask AI Advisor",
        "btn_caffeine": "☕ Caffeine Timer",
        "btn_stats": "📊 AI Stats & Debt",
        "btn_profile": "👤 Profile & Settings",
        "btn_cycles": "⏱️ Cycle Calculator",
        "btn_journal": "📜 Sleep Journal",
        "btn_breath": "🧘 4-7-8 Breathing",
        "btn_tips": "💡 Tips",
        "change_lang": "🌐 Change language",
        "re_onboarding": "🔄 Retake survey",
        "toggle_rem": "Sleep reminder",
        "going_to_sleep": "🌙 Good night! Sleep timer started at {time}.\nPress '☀️ I woke up' when you wake up.",
        "already_sleeping": "🌙 You are already sleeping! Press '☀️ I woke up' when you wake up.",
        "not_sleeping": "☀️ You haven't started the timer yet. Press '🌙 Going to sleep'.",
        "woke_up_ask_quality": "☀️ Good day / Morning!\n⏱️ You slept **{h} h {m} m** ({hrs} h).\n\nHow do you feel? Rate your sleep quality:",
        "log_saved": "✅ **Sleep Log Saved!**\n📅 Date: {date}\n⏱️ Duration: **{duration} h** ({bedtime} - {waketime})\n✨ Rating: {quality}",
        "caff_title": "☕ **Caffeine Sleep Calculator**\n\nWhat time did you have your last coffee/energy drink?",
        "caff_result": "☕ **Caffeine Elimination Analysis:**\n\n⏰ Intaken at: **{time}**\n📉 50% caffeine in blood until: **{half_life}**\n🟢 Safe elimination: at **{clear}**\n\n💡 **AI Tip:** Ensure the 6-hour half-life period finishes before your bedtime!"
    },
    "ru": {
        "welcome": "👋🌙 Добро пожаловать в **ИИ-Помощник по улучшению качества сна**!\n\n📋 **Шаг 1 из 6:** Выберите удобный язык общения:",
        "step_age": "🔹 **Шаг 2 из 6:** Выберите вашу **возрастную категорию**:",
        "step_bedtime": "🔹 **Шаг 3 из 6:** Во сколько вы **обычно ложитесь спать**?",
        "step_waketime": "🔹 **Шаг 4 из 6:** Во сколько вы **обычно просыпаетесь**?",
        "step_goal": "🔹 **Шаг 5 из 6:** Какова ваша **главная цель** улучшения сна?",
        "step_disruptor": "🔹 **Шаг 6 из 6:** Что чаще всего **мешает вам спать**?",
        "profile_created": "🎉 **Персональный ИИ-Профиль Сна создан!**",
        "btn_sleep": "🌙 Ложусь спать",
        "btn_wake": "☀️ Я проснулся",
        "btn_ask_ai": "🤖 Спросить ИИ-Консультанта",
        "btn_caffeine": "☕ Кофеиновый таймер",
        "btn_stats": "📊 ИИ-Статистика и Долг",
        "btn_profile": "👤 Мой Профиль и Настройки",
        "btn_cycles": "⏱️ Калькулятор циклов",
        "btn_journal": "📜 Журнал сна",
        "btn_breath": "🧘 Упражнение 4-7-8",
        "btn_tips": "💡 Советы",
        "change_lang": "🌐 Изменить язык / Change language",
        "re_onboarding": "🔄 Пройти опрос заново",
        "toggle_rem": "Напоминание о сне",
        "going_to_sleep": "🌙 Спокойной ночи! Таймер сна запущен в {time}.\nНажмите «☀️ Я проснулся», когда проснетесь.",
        "already_sleeping": "🌙 Вы уже спите! Когда проснетесь, нажмите «☀️ Я проснулся».",
        "not_sleeping": "☀️ Вы еще не включали таймер сна. Нажмите «🌙 Ложусь спать».",
        "woke_up_ask_quality": "☀️ Доброго дня / утра!\n⏱️ Вы проспали **{h} ч {m} мин** ({hrs} ч).\n\nКак вы себя чувствуете? Оцените качество сна:",
        "log_saved": "✅ **Запись сна сохранена!**\n📅 Дата: {date}\n⏱️ Длительность: **{duration} ч** ({bedtime} - {waketime})\n✨ Оценка: {quality}",
        "caff_title": "☕ **Кофеиновый калькулятор сна**\n\nВо сколько вы выпили последнюю порцию кофе/энергетика?",
        "caff_result": "☕ **Анализ выведения кофеина:**\n\n⏰ Время приема: **{time}**\n📉 50% кофеина в крови до: **{half_life}**\n🟢 Безопасная очистка: в **{clear}**\n\n💡 **Совет ИИ:** Следите, чтобы 6-часовой период полувыведения кофеина заканчивался до вашего времени засыпания!"
    }
}

AGE_GROUPS = {
    "uk": {
        "age_teen": {"title": "🧒 Підліток (13-17 років)", "target_hours": 9.0},
        "age_young": {"title": "🧑 Молодь / Дорослі (18-35 років)", "target_hours": 8.0},
        "age_adult": {"title": "🧔 Зрілий вік (36-60 років)", "target_hours": 7.5},
        "age_senior": {"title": "👵 Поважний вік (60+ років)", "target_hours": 7.0}
    },
    "en": {
        "age_teen": {"title": "🧒 Teen (13-17 yrs)", "target_hours": 9.0},
        "age_young": {"title": "🧑 Young Adult (18-35 yrs)", "target_hours": 8.0},
        "age_adult": {"title": "🧔 Adult (36-60 yrs)", "target_hours": 7.5},
        "age_senior": {"title": "👵 Senior (60+ yrs)", "target_hours": 7.0}
    },
    "ru": {
        "age_teen": {"title": "🧒 Подросток (13-17 лет)", "target_hours": 9.0},
        "age_young": {"title": "🧑 Молодежь / Взрослые (18-35 лет)", "target_hours": 8.0},
        "age_adult": {"title": "🧔 Зрелый возраст (36-60 лет)", "target_hours": 7.5},
        "age_senior": {"title": "👵 Пожилой возраст (60+ лет)", "target_hours": 7.0}
    }
}

BEDTIME_OPTIONS = {
    "uk": {
        "bt_early": "🌅 21:00 - 22:00 (Ранній)",
        "bt_normal": "🌙 22:00 - 23:00 (Оптимальний)",
        "bt_late": "🌌 23:00 - 01:00 (Нічна сова)",
        "bt_night": "🦉 01:00 - 03:00 (Глибока ніч)",
        "bt_deep_night": "⚡ 03:00 - 05:00 (Перед світанком)",
        "bt_morning_owl": "🌇 05:00 - 07:00+ (Після 5 ранку / Зміна)"
    },
    "en": {
        "bt_early": "🌅 21:00 - 22:00 (Early)",
        "bt_normal": "🌙 22:00 - 23:00 (Optimal)",
        "bt_late": "🌌 23:00 - 01:00 (Night Owl)",
        "bt_night": "🦉 01:00 - 03:00 (Deep Night)",
        "bt_deep_night": "⚡ 03:00 - 05:00 (Before Dawn)",
        "bt_morning_owl": "🌇 05:00 - 07:00+ (After 5 AM / Shift)"
    },
    "ru": {
        "bt_early": "🌅 21:00 - 22:00 (Ранний)",
        "bt_normal": "🌙 22:00 - 23:00 (Оптимальный)",
        "bt_late": "🌌 23:00 - 01:00 (Ночная сова)",
        "bt_night": "🦉 01:00 - 03:00 (Глубокая ночь)",
        "bt_deep_night": "⚡ 03:00 - 05:00 (Перед рассветом)",
        "bt_morning_owl": "🌇 05:00 - 07:00+ (После 5 утра / Смена)"
    }
}

WAKETIME_OPTIONS = {
    "uk": {
        "wt_early": "🌅 05:00 - 07:00 (Рання пташка)",
        "wt_normal": "☀️ 07:00 - 09:00 (Стандарт)",
        "wt_comfort": "🌤️ 09:00 - 11:00 (Комфортний ранок)",
        "wt_noon": "🕛 11:00 - 13:00 (Південь)",
        "wt_afternoon": "🌇 13:00 - 15:00 (Обідній підйом)",
        "wt_late_day": "😴 Після 15:00 (Пізній день)"
    },
    "en": {
        "wt_early": "🌅 05:00 - 07:00 (Early Bird)",
        "wt_normal": "☀️ 07:00 - 09:00 (Standard)",
        "wt_comfort": "🌤️ 09:00 - 11:00 (Comfort Morning)",
        "wt_noon": "🕛 11:00 - 13:00 (Noon)",
        "wt_afternoon": "🌇 13:00 - 15:00 (Afternoon)",
        "wt_late_day": "😴 After 15:00 (Late Day)"
    },
    "ru": {
        "wt_early": "🌅 05:00 - 07:00 (Ранняя пташка)",
        "wt_normal": "☀️ 07:00 - 09:00 (Стандарт)",
        "wt_comfort": "🌤️ 09:00 - 11:00 (Комфортное утро)",
        "wt_noon": "🕛 11:00 - 13:00 (Полдень)",
        "wt_afternoon": "🌇 13:00 - 15:00 (Обеденный подъем)",
        "wt_late_day": "😴 После 15:00 (Поздний день)"
    }
}

GOALS = {
    "uk": {
        "goal_wake": "🚀 Легше прокидатися у свій час",
        "goal_fall": "💤 Швидше засинати",
        "goal_quality": "📊 Покращити якість сну",
        "goal_schedule": "⏱️ Вирівняти режим сну"
    },
    "en": {
        "goal_wake": "🚀 Wake up easier",
        "goal_fall": "💤 Fall asleep faster",
        "goal_quality": "📊 Improve sleep quality",
        "goal_schedule": "⏱️ Align sleep schedule"
    },
    "ru": {
        "goal_wake": "🚀 Легче просыпаться",
        "goal_fall": "💤 Быстрее засыпать",
        "goal_quality": "📊 Улучшить качество сна",
        "goal_schedule": "⏱️ Выровнять режим сна"
    }
}

DISRUPTORS = {
    "uk": {
        "dis_phone": "📱 Смартфон / Соцмережі перед сном",
        "dis_coffee": "☕ Кава / Чай пізно увечері",
        "dis_stress": "💼 Робочий стрес та тривожність",
        "dis_food": "🍕 Важка їжа пізно ввечері",
        "dis_noise": "🔊 Шум або незручна подушка/ліжко",
        "dis_none": "✅ Жодних особливих перешкод"
    },
    "en": {
        "dis_phone": "📱 Smartphone / Social media before bed",
        "dis_coffee": "☕ Coffee / Tea late in the evening",
        "dis_stress": "💼 Work stress & anxiety",
        "dis_food": "🍕 Heavy food late at night",
        "dis_noise": "🔊 Noise or uncomfortable bed",
        "dis_none": "✅ No major disruptors"
    },
    "ru": {
        "dis_phone": "📱 Смартфон / Соцсети перед сном",
        "dis_coffee": "☕ Кофе / Чай поздно вечером",
        "dis_stress": "💼 Рабочий стресс и тревожность",
        "dis_food": "🍕 Тяжелая еда поздно вечером",
        "dis_noise": "🔊 Шум или неудобная подушка/кровать",
        "dis_none": "✅ Никаких особых помех"
    }
}

QUALITY_MAP = {
    "q_excellent": "🚀 Відмінно / Excellent / Отлично",
    "q_good": "😊 Добре / Good / Хорошо",
    "q_normal": "😐 Нормально / Normal / Нормально",
    "q_poor": "🥱 Погано / Poor / Плохо"
}

# FSM Стани
class OnboardingState(StatesGroup):
    waiting_for_lang = State()
    waiting_for_age = State()
    waiting_for_bedtime = State()
    waiting_for_waketime = State()
    waiting_for_goal = State()
    waiting_for_disruptor = State()

class SleepForm(StatesGroup):
    waiting_for_ai_question = State()

# --- Збереження та завантаження JSON ---
def load_user_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_user_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_profile(user_id):
    data = load_user_data()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "lang": "uk",
            "is_configured": False,
            "age_group": "age_young",
            "usual_bedtime": "bt_normal",
            "usual_waketime": "wt_normal",
            "goal": "goal_quality",
            "disruptor": "dis_phone",
            "reminders_enabled": True,
            "active_sleep_start": None,
            "logs": []
        }
        save_user_data(data)
    return data[uid]

def update_user_profile(user_id, user_dict):
    data = load_user_data()
    data[str(user_id)] = user_dict
    save_user_data(data)

def get_text(profile, key, **kwargs):
    lang = profile.get("lang", "uk")
    template = STRINGS.get(lang, STRINGS["uk"]).get(key, STRINGS["uk"].get(key, ""))
    return template.format(**kwargs)

# --- СПРАВЖНІЙ ШІ-ДВИГУН ГЕНЕРАЦІЇ АНАЛІЗУ СНУ (LIVE LLM) ---
def generate_real_ai_analysis(profile, duration, quality, bedtime_str, waketime_str):
    lang = profile.get("lang", "uk")
    age_key = profile.get("age_group", "age_young")
    age_info = AGE_GROUPS.get(lang, AGE_GROUPS["uk"]).get(age_key, AGE_GROUPS["uk"]["age_young"])
    target = age_info["target_hours"]
    diff = round(duration - target, 1)
    diff_str = f"+{diff}" if diff > 0 else f"{diff}"
    cycles = round(duration / 1.5, 1)

    disruptor_title = DISRUPTORS.get(lang, DISRUPTORS["uk"]).get(profile.get("disruptor", "dis_phone"), "N/A")
    goal_title = GOALS.get(lang, GOALS["uk"]).get(profile.get("goal", "goal_quality"), "N/A")

    lang_names = {"uk": "Ukrainian (українська)", "en": "English", "ru": "Russian (русский)"}
    selected_lang = lang_names.get(lang, "Ukrainian")

    prompt = (
        f"Ти — ШІ-аналітик сну. Твоє єдине завдання — надати СТИСЛИЙ ВИСНОВОК СНУ (sleep verdict) за цю ніч. НЕ ДАВАЙ ЖОДНИХ ПОРАД! Тільки підсумок та оцінка стану.\n\n"
        f"Дані користувача:\n"
        f"- Сон: {duration} год (норма для його віку: {target} год, різниця: {diff_str} год, ~{cycles} фаз).\n"
        f"- Розклад: {bedtime_str} - {waketime_str}.\n"
        f"- Перешкода: {disruptor_title}.\n\n"
        f"Формат (до 40-50 слів!):\n"
        f"📊 **Оцінка відновлення:** [наприклад: 85/100 🟢 Добре / 70/100 🟡 Посередньо]\n"
        f"🧠 **Висновок сну:** (2 короткі речення про пройдені фази, дефіцит/профіцит та біоритми)\n"
        f"⚡ **Стан ЦНС та Енергії:** (1 коротке речення про готовність нервової системи та рівень втоми)\n\n"
        f"Мова: {selected_lang}. Без порад, без привітань!"
    )

    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content
        if content and len(content.strip()) > 20:
            return content.strip()
    except Exception as e:
        logging.error(f"Live AI Error: {e}")

    return generate_ai_deep_analysis_fallback(profile, duration, quality, bedtime_str, waketime_str)

def generate_real_ai_answer(profile, question):
    lang = profile.get("lang", "uk")
    age_key = profile.get("age_group", "age_young")
    age_info = AGE_GROUPS.get(lang, AGE_GROUPS["uk"]).get(age_key, AGE_GROUPS["uk"]["age_young"])
    
    lang_names = {"uk": "Ukrainian (українська)", "en": "English", "ru": "Russian (русский)"}
    selected_lang = lang_names.get(lang, "Ukrainian")

    prompt = (
        f"Ти — досвідчений ШІ-консультант із сну та відновлення організму.\n"
        f"Профіль користувача: вікова категорія '{age_info['title']}', мета '{profile.get('goal', 'N/A')}', перешкода '{profile.get('disruptor', 'N/A')}'.\n"
        f"Користувач запитує: \"{question}\"\n\n"
        f"Дай вичерпну, корисну, науково обґрунтовану та зрозумілу відповідь у форматуванні Markdown.\n"
        f"Мова відповіді обов'язково: {selected_lang}."
    )

    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content
        if content and len(content.strip()) > 20:
            return content.strip()
    except Exception as e:
        logging.error(f"Live AI Question Error: {e}")

    return "🤖 **AI Sleep Advisor:** Для покращення якості сну дотримуйтесь регулярного режиму, провітрюйте кімнату перед сном та вимикайте екрани за годину до відпочинку!"

def generate_ai_deep_analysis_fallback(profile, duration, quality, bedtime_str, waketime_str):
    lang = profile.get("lang", "uk")
    age_key = profile.get("age_group", "age_young")
    age_info = AGE_GROUPS.get(lang, AGE_GROUPS["uk"]).get(age_key, AGE_GROUPS["uk"]["age_young"])
    target = age_info["target_hours"]
    diff = round(duration - target, 1)
    cycles = round(duration / 1.5, 1)

    if diff >= 0:
        score = "90/100 🟢 Відмінно"
        status_text = f"Норму сну ({target} год) перевиконано. Пройдено ~{cycles} фаз."
        cns_text = "Нервова система полностью восстановлена."
    else:
        score = "72/100 🟡 Посередньо"
        status_text = f"Виявлено дефіцит у {abs(diff)} год. Пройдено ~{cycles} фаз."
        cns_text = "Присутня залишкова втома через недосип."

    if lang == "uk":
        return (
            f"📊 **Оцінка відновлення:** {score}\n\n"
            f"🧠 **Висновок сну:** {status_text} Графік {bedtime_str} - {waketime_str}.\n"
            f"⚡ **Стан ЦНС та Енергії:** {cns_text}"
        )
    elif lang == "en":
        return (
            f"📊 **Recovery Score:** {score}\n\n"
            f"🧠 **Sleep Verdict:** {status_text} Schedule: {bedtime_str} - {waketime_str}.\n"
            f"⚡ **CNS & Energy State:** {cns_text}"
        )
    else:
        return (
            f"📊 **Оценка восстановления:** {score}\n\n"
            f"🧠 **Вывод по сну:** {status_text} Расписание: {bedtime_str} - {waketime_str}.\n"
            f"⚡ **Состояние ЦНС и Энергии:** {cns_text}"
        )

# --- ГОЛОВНЕ МЕНЮ МОВ —--
def get_main_keyboard(profile, is_sleeping=False):
    lang = profile.get("lang", "uk")
    s = STRINGS.get(lang, STRINGS["uk"])

    sleep_btn = KeyboardButton(text=s["btn_wake"]) if is_sleeping else KeyboardButton(text=s["btn_sleep"])
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [sleep_btn],
            [KeyboardButton(text=s["btn_ask_ai"]), KeyboardButton(text=s["btn_stats"])],
            [KeyboardButton(text=s["btn_caffeine"]), KeyboardButton(text=s["btn_profile"])]
        ],
        resize_keyboard=True
    )
    return kb

# --- ONBOARDING: КРОК 1 (ВИБІР МОВИ) ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    buttons = [
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="ob_lang_uk")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="ob_lang_en")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="ob_lang_ru")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    welcome_text = (
        f"Hi, {message.from_user.first_name}! 👋🌙\n\n"
        f"Welcome to **AI Sleep Assistant**!\n\n"
        f"🔹 **Step 1 of 6 / Крок 1 з 6:** Please select your preferred language / Оберіть мову:"
    )
    await message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(OnboardingState.waiting_for_lang)

@dp.callback_query(F.data.startswith("ob_lang_"))
async def process_onboarding_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.replace("ob_lang_", "")
    if lang in LANGUAGES:
        await state.update_data(lang=lang)

        profile = get_user_profile(callback.from_user.id)
        profile["lang"] = lang
        update_user_profile(callback.from_user.id, profile)

        ages = AGE_GROUPS.get(lang, AGE_GROUPS["uk"])
        buttons = []
        for a_key, a_info in ages.items():
            buttons.append([InlineKeyboardButton(text=a_info['title'], callback_data=f"ob_age_{a_key}")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        s = STRINGS.get(lang, STRINGS["uk"])

        await callback.message.edit_text(
            f"🌐 Language: **{LANGUAGES[lang]}**\n\n"
            f"{s['step_age']}",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        await state.set_state(OnboardingState.waiting_for_age)
    await callback.answer()

@dp.callback_query(F.data.startswith("ob_age_"))
async def process_onboarding_age(callback: CallbackQuery, state: FSMContext):
    age_key = callback.data.replace("ob_age_", "")
    data = await state.get_data()
    lang = data.get("lang", "uk")

    ages = AGE_GROUPS.get(lang, AGE_GROUPS["uk"])
    if age_key in ages:
        await state.update_data(age_group=age_key)
        
        bedtimes = BEDTIME_OPTIONS.get(lang, BEDTIME_OPTIONS["uk"])
        buttons = []
        for bt_key, bt_title in bedtimes.items():
            buttons.append([InlineKeyboardButton(text=bt_title, callback_data=f"ob_bt_{bt_key}")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        s = STRINGS.get(lang, STRINGS["uk"])
        age_title = ages[age_key]["title"]

        await callback.message.edit_text(
            f"✅ {age_title}\n\n"
            f"{s['step_bedtime']}",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        await state.set_state(OnboardingState.waiting_for_bedtime)
    await callback.answer()

@dp.callback_query(F.data.startswith("ob_bt_"))
async def process_onboarding_bedtime(callback: CallbackQuery, state: FSMContext):
    bt_key = callback.data.replace("ob_bt_", "")
    data = await state.get_data()
    lang = data.get("lang", "uk")

    bedtimes = BEDTIME_OPTIONS.get(lang, BEDTIME_OPTIONS["uk"])
    if bt_key in bedtimes:
        await state.update_data(usual_bedtime=bt_key)

        waketimes = WAKETIME_OPTIONS.get(lang, WAKETIME_OPTIONS["uk"])
        buttons = []
        for wt_key, wt_title in waketimes.items():
            buttons.append([InlineKeyboardButton(text=wt_title, callback_data=f"ob_wt_{wt_key}")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        s = STRINGS.get(lang, STRINGS["uk"])

        await callback.message.edit_text(
            f"✅ {bedtimes[bt_key]}\n\n"
            f"{s['step_waketime']}",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        await state.set_state(OnboardingState.waiting_for_waketime)
    await callback.answer()

@dp.callback_query(F.data.startswith("ob_wt_"))
async def process_onboarding_waketime(callback: CallbackQuery, state: FSMContext):
    wt_key = callback.data.replace("ob_wt_", "")
    data = await state.get_data()
    lang = data.get("lang", "uk")

    waketimes = WAKETIME_OPTIONS.get(lang, WAKETIME_OPTIONS["uk"])
    if wt_key in waketimes:
        await state.update_data(usual_waketime=wt_key)

        goals = GOALS.get(lang, GOALS["uk"])
        buttons = []
        for g_key, g_title in goals.items():
            buttons.append([InlineKeyboardButton(text=g_title, callback_data=f"ob_goal_{g_key}")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        s = STRINGS.get(lang, STRINGS["uk"])

        await callback.message.edit_text(
            f"✅ {waketimes[wt_key]}\n\n"
            f"{s['step_goal']}",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        await state.set_state(OnboardingState.waiting_for_goal)
    await callback.answer()

@dp.callback_query(F.data.startswith("ob_goal_"))
async def process_onboarding_goal(callback: CallbackQuery, state: FSMContext):
    goal_key = callback.data.replace("ob_goal_", "")
    data = await state.get_data()
    lang = data.get("lang", "uk")

    goals = GOALS.get(lang, GOALS["uk"])
    if goal_key in goals:
        await state.update_data(goal=goal_key)

        disruptors = DISRUPTORS.get(lang, DISRUPTORS["uk"])
        buttons = []
        for dis_key, dis_title in disruptors.items():
            buttons.append([InlineKeyboardButton(text=dis_title, callback_data=f"ob_dis_{dis_key}")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        s = STRINGS.get(lang, STRINGS["uk"])

        await callback.message.edit_text(
            f"✅ {goals[goal_key]}\n\n"
            f"{s['step_disruptor']}",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        await state.set_state(OnboardingState.waiting_for_disruptor)
    await callback.answer()

@dp.callback_query(F.data.startswith("ob_dis_"))
async def process_onboarding_disruptor(callback: CallbackQuery, state: FSMContext):
    dis_key = callback.data.replace("ob_dis_", "")
    data = await state.get_data()

    lang = data.get("lang", "uk")
    age_key = data.get("age_group", "age_young")
    bt_key = data.get("usual_bedtime", "bt_normal")
    wt_key = data.get("usual_waketime", "wt_normal")
    goal_key = data.get("goal", "goal_quality")

    profile = get_user_profile(callback.from_user.id)
    profile["lang"] = lang
    profile["age_group"] = age_key
    profile["usual_bedtime"] = bt_key
    profile["usual_waketime"] = wt_key
    profile["goal"] = goal_key
    profile["disruptor"] = dis_key
    profile["is_configured"] = True
    update_user_profile(callback.from_user.id, profile)

    await state.clear()

    age_info = AGE_GROUPS.get(lang, AGE_GROUPS["uk"]).get(age_key, AGE_GROUPS["uk"]["age_young"])
    bt_title = BEDTIME_OPTIONS.get(lang, BEDTIME_OPTIONS["uk"]).get(bt_key, "N/A")
    wt_title = WAKETIME_OPTIONS.get(lang, WAKETIME_OPTIONS["uk"]).get(wt_key, "N/A")
    goal_title = GOALS.get(lang, GOALS["uk"]).get(goal_key, "N/A")
    dis_title = DISRUPTORS.get(lang, DISRUPTORS["uk"]).get(dis_key, "N/A")

    s = STRINGS.get(lang, STRINGS["uk"])

    await callback.message.delete()
    await callback.message.answer(
        f"{s['profile_created']}\n\n"
        f"🌐 Language / Мова: **{LANGUAGES.get(lang, 'Українська')}**\n"
        f"👤 Category: **{age_info['title']}**\n"
        f"💤 Target sleep: **{age_info['target_hours']} h / ніч / hrs**\n"
        f"🌙 Bedtime: **{bt_title}**\n"
        f"☀️ Waketime: **{wt_title}**\n"
        f"🎯 Goal: **{goal_title}**\n"
        f"⚠️ Disruptor: **{dis_title}**\n\n"
        f"🤖 AI Sleep Assistant ready!",
        reply_markup=get_main_keyboard(profile, is_sleeping=False),
        parse_mode="Markdown"
    )
    await callback.answer()

async def safe_edit_message(msg: types.Message, text: str, parse_mode: str = "Markdown"):
    try:
        await msg.edit_text(text, parse_mode=parse_mode)
    except Exception as e1:
        logging.warning(f"Edit with parse_mode {parse_mode} failed: {e1}")
        try:
            await msg.edit_text(text)
        except Exception as e2:
            logging.error(f"Edit plain text failed: {e2}")
            try:
                await msg.answer(text, parse_mode="Markdown")
            except Exception:
                await msg.answer(text)

# --- 🌙 ЛЯГАЮ СПАТИ / ☀️ Я ПРОКИНУВСЯ ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_sleep"], STRINGS["en"]["btn_sleep"], STRINGS["ru"]["btn_sleep"]]))
async def process_bedtime(message: types.Message):
    profile = get_user_profile(message.from_user.id)
    if profile.get("active_sleep_start"):
        await message.answer(get_text(profile, "already_sleeping"), parse_mode="Markdown")
        return

    now_iso = datetime.now().isoformat()
    profile["active_sleep_start"] = now_iso
    update_user_profile(message.from_user.id, profile)

    now_str = datetime.now().strftime("%H:%M")
    await message.answer(
        get_text(profile, "going_to_sleep", time=now_str),
        reply_markup=get_main_keyboard(profile, is_sleeping=True),
        parse_mode="Markdown"
    )

@dp.message(F.text.in_([STRINGS["uk"]["btn_wake"], STRINGS["en"]["btn_wake"], STRINGS["ru"]["btn_wake"]]))
async def process_waketime(message: types.Message, state: FSMContext):
    profile = get_user_profile(message.from_user.id)
    start_iso = profile.get("active_sleep_start")

    if not start_iso:
        await message.answer(
            get_text(profile, "not_sleeping"),
            reply_markup=get_main_keyboard(profile, is_sleeping=False),
            parse_mode="Markdown"
        )
        return

    start_time = datetime.fromisoformat(start_iso)
    end_time = datetime.now()

    diff_seconds = max(60, (end_time - start_time).total_seconds())
    hours = diff_seconds / 3600.0
    duration_rounded = round(hours, 1)

    bedtime_str = start_time.strftime("%H:%M")
    waketime_str = end_time.strftime("%H:%M")
    date_str = end_time.strftime("%d.%m.%Y")
    quality = "😊 Automatic"

    new_log = {
        "date": date_str,
        "bedtime": bedtime_str,
        "waketime": waketime_str,
        "duration": duration_rounded,
        "quality": quality
    }

    profile["active_sleep_start"] = None
    profile["logs"].insert(0, new_log)
    update_user_profile(message.from_user.id, profile)
    await state.clear()

    lang = profile.get("lang", "uk")
    saved_msg = get_text(profile, "log_saved", date=date_str, duration=duration_rounded, bedtime=bedtime_str, waketime=waketime_str, quality=quality)

    thinking_txt = {
        "uk": "🤖 **ШІ генерує персональний аналіз ночі... ⏳**",
        "en": "🤖 **AI is generating your personal sleep analysis... ⏳**",
        "ru": "🤖 **ИИ генерирует персональный анализ ночи... ⏳**"
    }
    status_str = thinking_txt.get(lang, thinking_txt["uk"])

    msg = await message.answer(
        f"{saved_msg}\n\n{status_str}",
        reply_markup=get_main_keyboard(profile, is_sleeping=False),
        parse_mode="Markdown"
    )

    ai_deep_report = await asyncio.to_thread(generate_real_ai_analysis, profile, duration_rounded, quality, bedtime_str, waketime_str)

    final_content = f"{saved_msg}\n\n{ai_deep_report}"
    await safe_edit_message(msg, final_content, parse_mode="Markdown")

# --- ☕ КОФЕЇНОВИЙ ТАЙМЕР ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_caffeine"], STRINGS["en"]["btn_caffeine"], STRINGS["ru"]["btn_caffeine"]]))
async def process_caffeine_menu(message: types.Message):
    profile = get_user_profile(message.from_user.id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="14:00", callback_data="caf_14:00"),
                InlineKeyboardButton(text="18:00", callback_data="caf_18:00"),
                InlineKeyboardButton(text="22:00", callback_data="caf_22:00")
            ],
            [
                InlineKeyboardButton(text="00:00", callback_data="caf_00:00"),
                InlineKeyboardButton(text="02:00", callback_data="caf_02:00")
            ]
        ]
    )
    await message.answer(get_text(profile, "caff_title"), reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("caf_"))
async def process_caffeine_choice(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    time_str = callback.data.replace("caf_", "")
    h, m = map(int, time_str.split(":"))

    now = datetime.now()
    caff_time = datetime(now.year, now.month, now.day, h, m)

    half_life_time = caff_time + timedelta(hours=6)
    clear_time = caff_time + timedelta(hours=10)

    res_text = get_text(
        profile, "caff_result",
        time=time_str,
        half_life=half_life_time.strftime('%H:%M'),
        clear=clear_time.strftime('%H:%M')
    )

    await callback.message.edit_text(res_text, parse_mode="Markdown")
    await callback.answer()

# --- 👤 ПРОФІЛЬ & НАЛАШТУВАННЯ ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_profile"], STRINGS["en"]["btn_profile"], STRINGS["ru"]["btn_profile"]]))
async def show_profile(message: types.Message, state: FSMContext):
    profile = get_user_profile(message.from_user.id)
    if not profile.get("is_configured"):
        await cmd_start(message, state)
        return

    lang = profile.get("lang", "uk")
    s = STRINGS.get(lang, STRINGS["uk"])

    age_info = AGE_GROUPS.get(lang, AGE_GROUPS["uk"]).get(profile.get("age_group", "age_young"), {"title": "N/A", "target_hours": 8.0})
    bt_title = BEDTIME_OPTIONS.get(lang, BEDTIME_OPTIONS["uk"]).get(profile.get("usual_bedtime", "bt_normal"), "N/A")
    wt_title = WAKETIME_OPTIONS.get(lang, WAKETIME_OPTIONS["uk"]).get(profile.get("usual_waketime", "wt_normal"), "N/A")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=s["change_lang"], callback_data="re_onboarding")],
            [InlineKeyboardButton(text=s["re_onboarding"], callback_data="re_onboarding")]
        ]
    )

    await message.answer(
        f"👤 **Profile / Профіль:**\n\n"
        f"• Language / Мова: **{LANGUAGES.get(lang, 'Українська')}**\n"
        f"• Age / Вік: **{age_info['title']}**\n"
        f"• Target sleep: **{age_info['target_hours']} h**\n"
        f"• Bedtime: **{bt_title}**\n"
        f"• Waketime: **{wt_title}**",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "re_onboarding")
async def re_onboarding(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await cmd_start(callback.message, state)

# --- 📊 СТАТИСТИКА & БОРГ ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_stats"], STRINGS["en"]["btn_stats"], STRINGS["ru"]["btn_stats"]]))
async def process_stats(message: types.Message):
    profile = get_user_profile(message.from_user.id)
    lang = profile.get("lang", "uk")
    logs = profile.get("logs", [])
    age_info = AGE_GROUPS.get(lang, AGE_GROUPS["uk"]).get(profile.get("age_group", "age_young"), {"title": "N/A", "target_hours": 8.0})
    target_hrs = age_info["target_hours"]

    if not logs:
        await message.answer(f"📊 Profile Target: **{target_hrs} h / night**. Log your first sleep using the menu!", parse_mode="Markdown")
        return

    last_log = logs[0]
    recent_7 = logs[:7]
    avg_7 = round(sum(l["duration"] for l in recent_7) / len(recent_7), 1)

    text = (
        f"📊 **AI Sleep Report / Звіт**\n\n"
        f"👤 Category: **{age_info['title']}**\n"
        f"🎯 Target: **{target_hrs} h / night**\n"
        f"🛌 Last Sleep: **{last_log['duration']} h** ({last_log['quality']})\n"
        f"📈 7-day average: **{avg_7} h / night**\n"
    )

    await message.answer(text, parse_mode="Markdown")

# --- ⏱️ КАЛЬКУЛЯТОР ЦИКЛІВ ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_cycles"], STRINGS["en"]["btn_cycles"], STRINGS["ru"]["btn_cycles"]]))
async def process_cycles(message: types.Message):
    now = datetime.now()
    text = f"⏱️ **Sleep Cycle Calculator (90 min)**\n\nIf you fall asleep at **{now.strftime('%H:%M')}**, best wake up times:\n\n"
    cycles = [(3, 4.5), (4, 6.0), (5, 7.5), (6, 9.0)]
    for c, hrs in cycles:
        wake_time = now + timedelta(minutes=int(c * 90 + 15))
        text += f"• **{wake_time.strftime('%H:%M')}** ({hrs} h)\n"
    await message.answer(text, parse_mode="Markdown")

# --- 📜 ЖУРНАЛ СНУ ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_journal"], STRINGS["en"]["btn_journal"], STRINGS["ru"]["btn_journal"]]))
async def process_journal(message: types.Message):
    profile = get_user_profile(message.from_user.id)
    logs = profile.get("logs", [])
    if not logs:
        await message.answer("📜 Sleep journal is empty / порожній.", parse_mode="Markdown")
        return

    text = "📜 **Sleep Journal:**\n\n"
    for log in logs[:5]:
        text += f"🗓 **{log['date']}** ({log['bedtime']} - {log['waketime']})\n   • {log['duration']} h | {log['quality']}\n\n"

    await message.answer(text, parse_mode="Markdown")

# --- 🧘 ВПРАВА 4-7-8 ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_breath"], STRINGS["en"]["btn_breath"], STRINGS["ru"]["btn_breath"]]))
async def process_breathing(message: types.Message):
    text = (
        "🧘 **4-7-8 Breathing Technique / Техніка 4-7-8:**\n\n"
        "1️⃣ **Inhale** / Вдих (4 sec)\n"
        "2️⃣ **Hold** / Затримайте (7 sec)\n"
        "3️⃣ **Exhale** / Видих (8 sec)\n\n"
        "Repeat 4 times to calm your nervous system!"
    )
    await message.answer(text, parse_mode="Markdown")

# --- 💡 ПОРАДИ ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_tips"], STRINGS["en"]["btn_tips"], STRINGS["ru"]["btn_tips"]]))
async def process_tips(message: types.Message):
    text = (
        "💡 **Sleep Hygiene Tips / Поради:**\n\n"
        "📱 **Screens:** Turn off devices 30-45 mins before sleep.\n"
        "☕ **Caffeine:** Avoid coffee 7 hours prior to bedtime.\n"
        "🌡️ **Room:** Keep temperature cool (18-20°C / 65-68°F).\n"
        "🕶️ **Night owls:** Use Blackout curtains if sleeping past dawn!"
    )
    await message.answer(text, parse_mode="Markdown")

# --- 🤖 ЗАПИТАТИ ШІ-КОНСУЛЬТАНТА ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_ask_ai"], STRINGS["en"]["btn_ask_ai"], STRINGS["ru"]["btn_ask_ai"]]))
async def ask_ai_start(message: types.Message, state: FSMContext):
    profile = get_user_profile(message.from_user.id)
    lang = profile.get("lang", "uk")
    prompt_txt = {
        "uk": "🤖 **ШІ-Консультант зі сну:**\n\nНапишіть будь-яке запитання про сон, біоритми чи відновлення (наприклад: *Як швидко заснути після стресу?*):",
        "en": "🤖 **AI Sleep Advisor:**\n\nAsk any question about sleep, circadian rhythms, or recovery:",
        "ru": "🤖 **ИИ-Консультант по сну:**\n\nНапишите любой вопрос о сне, биоритмах или восстановлении:"
    }
    await message.answer(prompt_txt.get(lang, prompt_txt["uk"]), parse_mode="Markdown")
    await state.set_state(SleepForm.waiting_for_ai_question)

@dp.message(SleepForm.waiting_for_ai_question)
async def process_ai_question(message: types.Message, state: FSMContext):
    profile = get_user_profile(message.from_user.id)
    user_q = message.text
    await state.clear()
    
    thinking_msg = await message.answer("🤖 **ШІ обдумає ваше запитання... ⏳**", parse_mode="Markdown")
    
    ai_answer = await asyncio.to_thread(generate_real_ai_answer, profile, user_q)
    
    try:
        await thinking_msg.edit_text(f"🤖 **ШІ-Консультант:**\n\n{ai_answer}", parse_mode="Markdown")
    except Exception:
        await message.answer(f"🤖 **ШІ-Консультант:**\n\n{ai_answer}", parse_mode="Markdown")

# --- ВЕБ-СЕРВЕР ДЛЯ СУМІСНОСТІ З RENDER WEB SERVICE ---
async def handle_ping(request):
    return web.Response(text="Bot is live and listening!")

async def main():
    logging.basicConfig(level=logging.INFO)
    print("🤖 Multilingual bot with Deep AI Sleep Engine launched!")

    # Запускаємо фоновий веб-сервер для перевірки портів Render
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Web server bound to port {port}")

    # Запускаємо polling бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот зупинений.")