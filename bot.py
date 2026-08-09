import certifi
import os
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Завантажуємо змінні оточення з .env (для локального запуску).
# На хостингу (Render тощо) змінні задаються через панель, і .env не потрібен.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import logging
import sys
import json
import asyncio
import html
import threading
import tempfile
import secrets
from datetime import datetime, timedelta
from aiohttp import web  # Додано для веб-сервера Render
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
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

# 🔑 Токен бота від @BotFather. ОБОВʼЯЗКОВО задається через змінну оточення BOT_TOKEN.
# Ніколи не хардкодьте токен у коді — інакше будь-хто з доступу до репозиторію захопить бота.
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задано. Додайте змінну оточення BOT_TOKEN "
        "(див. .env.example) перед запуском бота."
    )

# Ініціалізація бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

DATA_FILE = "sleep_ai_data.json"

# ID адміністраторів, які мають доступ до /admin та /buyers.
# Задаються через змінну оточення ADMIN_IDS (список через кому), напр.: ADMIN_IDS="1373248099,987654321"
ADMIN_IDS = []
env_admin = os.getenv("ADMIN_IDS")
if env_admin:
    try:
        ADMIN_IDS.extend([int(x.strip()) for x in env_admin.split(",") if x.strip()])
    except ValueError:
        logging.warning("ADMIN_IDS має некоректний формат. Очікується список чисел через кому.")

# Група для перевірки квитанцій про оплату (задається через ADMIN_GROUP_ID)
try:
    ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0"))
except ValueError:
    ADMIN_GROUP_ID = 0

class PaymentReceiptState(StatesGroup):
    waiting_for_receipt = State()

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
        "btn_course": "🎓 7-Денний Інтенсив сну",
        "btn_ask_ai": "🤖 Запитати ШІ-Консультанта",
        "btn_profile": "👤 Мій Профіль & Налаштування",
        "btn_journal": "📜 Журнал сну",
        "change_lang": "🌐 Змінити мову / Change language",
        "re_onboarding": "🔄 Пройти опитування знову",
        "toggle_rem": "Нагадування про сон",
        "going_to_sleep": "🌙 Надобраніч! Таймер сну запущено о {time}.\nТисніть «☀️ Я прокинувся», коли прокинетеся.",
        "already_sleeping": "🌙 Ви вже спите! Коли прокинетеся, натисніть «☀️ Я прокинувся».",
        "not_sleeping": "☀️ Ви ще не вмикали таймер сну. Натисніть «🌙 Лягаю спати».",
        "woke_up_ask_quality": "☀️ Доброго дня / ранку!\n⏱️ Ви проспали **{h} год {m} хв** ({hrs} год).\n\nЯк ви почуваєтеся? Оцініть якість сну:",
        "log_saved": "✅ **Запис сну збережено!**\n📅 Дата: {date}\n⏱️ Тривалість: **{duration} год** ({bedtime} - {waketime})\n✨ Оцінка: {quality}",
        "btn_buy": "💳 Придбати курс (99 грн)",
        "journal_empty": "📜 Журнал сну порожній.",
        "journal_title": "📜 Журнал сну:",
        "journal_entry": "🗓 **{date}** ({bedtime} - {waketime})\n   • {duration} год | {quality}",
        "quality_auto": "😊 Автоматично",
        "ai_thinking": "🤖 **ШІ генерує персональний аналіз ночі... ⏳**",
        "profile_title": "👤 Профіль:",
        "profile_body": "• Мова: **{lang}**\n• Вік: **{age}**\n• Цільовий сон: **{target} год**\n• Час засинання: **{bedtime}**\n• Час підйому: **{waketime}**",
        "paywall_locked_header": "🔒 **Ця функція доступна лише після оплати курсу.**\n\n",
        "paywall_title": "👑 **Ваш Персональний 7-Денний Курс Сну**",
        "paywall_program": "🎯 **Ваша програма, складена ШІ:**",
        "paywall_after": "💎 **Після оплати відкриється:**\n• Усі 7 персональних уроків із практичними вправами\n• Трекер сну, статистика та ШІ-консультант\n• Аудіо-релакс та вечірній чек-лист засинання",
        "paywall_price": "🏷️ **Вартість:** **99 грн** *(одноразовий платіж • доступ назавжди)*",
        "btn_pay_mono": "💳 Придбати доступ за 99 грн (Monobank / Card)",
        "pay_mono_title": "💳 **Оплата курсу (99 грн) через Monobank**",
        "pay_mono_steps": "1️⃣ Перейдіть за посиланням та сплатіть **99 грн** у банку Monobank.\n2️⃣ Зробіть скріншот або фото квитанції про оплату.\n3️⃣ Натисніть кнопку **«📸 Я оплатив (Надіслати квитанцію)»** та прикріпіть фото!",
        "btn_pay_link": "🔗 Банка Monobank (Сплатити 99 грн)",
        "btn_pay_sent": "📸 Я оплатив (Надіслати квитанцію)",
        "receipt_ask": "📸 **Будь ласка, надішліть фото або скріншот квитанції про оплату.**\n\nОдразу після відправки вона надійде адміністратору на перевірку ⏳",
        "receipt_received": "✅ **Квитанцію успішно отримано!**\n\nВона відправлена адміністратору на перевірку. Доступ до курсу буде активовано протягом декількох хвилин ⏳",
        "receipt_not_photo": "⚠️ **Будь ласка, прикріпіть саме фотографію або скріншот квитанції!**",
        "pay_approved_user": "🎉 **Вітаємо! Вашу оплату 99 грн підтверджено!**\n\nВам надано повний доступ до всіх функцій та 7-денного інтенсиву сну. Обирайте розділ меню нижче!",
        "pay_rejected_user": "❌ **Вашу квитанцію про оплату не підтверджено.**\n\nБудь ласка, перевірте реквізити та суму (99 грн) або зверніться до підтримки.",
        "already_premium": "🎉 **У вас вже активовано доступ до курсу!**",
        "locked_menu_hint": "🔒 Меню нижче доступне до оплати:"
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
        "btn_course": "🎓 7-Day Sleep Course",
        "btn_ask_ai": "🤖 Ask AI Advisor",
        "btn_profile": "👤 Profile & Settings",
        "btn_journal": "📜 Sleep Journal",
        "change_lang": "🌐 Change language",
        "re_onboarding": "🔄 Retake survey",
        "toggle_rem": "Sleep reminder",
        "going_to_sleep": "🌙 Good night! Sleep timer started at {time}.\nPress '☀️ I woke up' when you wake up.",
        "already_sleeping": "🌙 You are already sleeping! Press '☀️ I woke up' when you wake up.",
        "not_sleeping": "☀️ You haven't started the timer yet. Press '🌙 Going to sleep'.",
        "woke_up_ask_quality": "☀️ Good day / Morning!\n⏱️ You slept **{h} h {m} m** ({hrs} h).\n\nHow do you feel? Rate your sleep quality:",
        "log_saved": "✅ **Sleep Log Saved!**\n📅 Date: {date}\n⏱️ Duration: **{duration} h** ({bedtime} - {waketime})\n✨ Rating: {quality}",
        "btn_buy": "💳 Buy course (99 UAH)",
        "journal_empty": "📜 Your sleep journal is empty.",
        "journal_title": "📜 Sleep Journal:",
        "journal_entry": "🗓 **{date}** ({bedtime} - {waketime})\n   • {duration} h | {quality}",
        "quality_auto": "😊 Automatic",
        "ai_thinking": "🤖 **AI is generating your personal sleep analysis... ⏳**",
        "profile_title": "👤 Profile:",
        "profile_body": "• Language: **{lang}**\n• Age: **{age}**\n• Target sleep: **{target} h**\n• Bedtime: **{bedtime}**\n• Waketime: **{waketime}**",
        "paywall_locked_header": "🔒 **This feature is available only after purchasing the course.**\n\n",
        "paywall_title": "👑 **Your Personal 7-Day Sleep Course**",
        "paywall_program": "🎯 **Your AI-generated program:**",
        "paywall_after": "💎 **After payment you'll unlock:**\n• All 7 personal lessons with practical exercises\n• Sleep tracker, statistics and AI advisor\n• Audio relaxation and an evening wind-down checklist",
        "paywall_price": "🏷️ **Price:** **99 UAH** *(one-time payment • lifetime access)*",
        "btn_pay_mono": "💳 Buy access for 99 UAH (Monobank / Card)",
        "pay_mono_title": "💳 **Course payment (99 UAH) via Monobank**",
        "pay_mono_steps": "1️⃣ Follow the link and pay **99 UAH** in Monobank.\n2️⃣ Take a screenshot or photo of the payment receipt.\n3️⃣ Tap the **«📸 I've paid (Send receipt)»** button and attach the photo!",
        "btn_pay_link": "🔗 Monobank jar (Pay 99 UAH)",
        "btn_pay_sent": "📸 I've paid (Send receipt)",
        "receipt_ask": "📸 **Please send a photo or screenshot of your payment receipt.**\n\nAs soon as you send it, it will go to the administrator for review ⏳",
        "receipt_received": "✅ **Receipt received successfully!**\n\nIt has been sent to the administrator for review. Access to the course will be activated within a few minutes ⏳",
        "receipt_not_photo": "⚠️ **Please attach only a photo or a screenshot of the receipt!**",
        "pay_approved_user": "🎉 **Congratulations! Your payment of 99 UAH has been confirmed!**\n\nYou now have full access to all features and the 7-day sleep intensive. Choose a menu section below!",
        "pay_rejected_user": "❌ **Your payment receipt was not confirmed.**\n\nPlease check the details and the amount (99 UAH), or contact support.",
        "already_premium": "🎉 **You already have access to the course activated!**",
        "locked_menu_hint": "🔒 The menu below is available before payment:"
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
        "btn_course": "🎓 7-Дневный Интенсив сна",
        "btn_ask_ai": "🤖 Спросить ИИ-Консультанта",
        "btn_profile": "👤 Мой Профиль и Настройки",
        "btn_journal": "📜 Журнал сна",
        "change_lang": "🌐 Изменить язык / Change language",
        "re_onboarding": "🔄 Пройти опрос заново",
        "toggle_rem": "Напоминание о сне",
        "going_to_sleep": "🌙 Спокойной ночи! Таймер сна запущен в {time}.\nНажмите «☀️ Я проснулся», когда проснетесь.",
        "already_sleeping": "🌙 Вы уже спите! Когда проснетесь, нажмите «☀️ Я проснулся».",
        "not_sleeping": "☀️ Вы еще не включали таймер сна. Нажмите «🌙 Ложусь спать».",
        "woke_up_ask_quality": "☀️ Доброго дня / утра!\n⏱️ Вы проспали **{h} ч {m} мин** ({hrs} ч).\n\nКак вы себя чувствуете? Оцените качество сна:",
        "log_saved": "✅ **Запись сна сохранена!**\n📅 Дата: {date}\n⏱️ Длительность: **{duration} ч** ({bedtime} - {waketime})\n✨ Оценка: {quality}",
        "btn_buy": "💳 Купить курс (99 грн)",
        "journal_empty": "📜 Журнал сна пуст.",
        "journal_title": "📜 Журнал сна:",
        "journal_entry": "🗓 **{date}** ({bedtime} - {waketime})\n   • {duration} ч | {quality}",
        "quality_auto": "😊 Автоматически",
        "ai_thinking": "🤖 **ИИ генерирует персональный анализ ночи... ⏳**",
        "profile_title": "👤 Профиль:",
        "profile_body": "• Язык: **{lang}**\n• Возраст: **{age}**\n• Целевой сон: **{target} ч**\n• Время засыпания: **{bedtime}**\n• Время подъёма: **{waketime}**",
        "paywall_locked_header": "🔒 **Эта функция доступна только после оплаты курса.**\n\n",
        "paywall_title": "👑 **Ваш персональный 7-дневный курс сна**",
        "paywall_program": "🎯 **Ваша программа, составленная ИИ:**",
        "paywall_after": "💎 **После оплаты откроется:**\n• Все 7 персональных уроков с практическими упражнениями\n• Трекер сна, статистика и ИИ-консультант\n• Аудио-релакс и вечерний чек-лист засыпания",
        "paywall_price": "🏷️ **Стоимость:** **99 грн** *(разовый платёж • доступ навсегда)*",
        "btn_pay_mono": "💳 Купить доступ за 99 грн (Monobank / Card)",
        "pay_mono_title": "💳 **Оплата курса (99 грн) через Monobank**",
        "pay_mono_steps": "1️⃣ Перейдите по ссылке и оплатите **99 грн** в банке Monobank.\n2️⃣ Сделайте скриншот или фото квитанции об оплате.\n3️⃣ Нажмите кнопку **«📸 Я оплатил (Отправить квитанцию)»** и прикрепите фото!",
        "btn_pay_link": "🔗 Банка Monobank (Оплатить 99 грн)",
        "btn_pay_sent": "📸 Я оплатил (Отправить квитанцию)",
        "receipt_ask": "📸 **Пожалуйста, отправьте фото или скриншот квитанции об оплате.**\n\nСразу после отправки она поступит администратору на проверку ⏳",
        "receipt_received": "✅ **Квитанция успешно получена!**\n\nОна отправлена администратору на проверку. Доступ к курсу будет активирован в течение нескольких минут ⏳",
        "receipt_not_photo": "⚠️ **Пожалуйста, прикрепите именно фотографию или скриншот квитанции!**",
        "pay_approved_user": "🎉 **Поздравляем! Ваша оплата 99 грн подтверждена!**\n\nВам предоставлен полный доступ ко всем функциям и 7-дневному интенсиву сна. Выбирайте раздел меню ниже!",
        "pay_rejected_user": "❌ **Ваша квитанция об оплате не подтверждена.**\n\nПожалуйста, проверьте реквизиты и сумму (99 грн) или обратитесь в поддержку.",
        "already_premium": "🎉 **У вас уже активирован доступ к курсу!**",
        "locked_menu_hint": "🔒 Меню ниже доступно до оплаты:"
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

# Оцінки якості сну розкладені по мовах, щоб не змішувати три мови в одному рядку.
QUALITY_MAP = {
    "uk": {
        "q_excellent": "🚀 Відмінно",
        "q_good": "😊 Добре",
        "q_normal": "😐 Нормально",
        "q_poor": "🥱 Погано"
    },
    "en": {
        "q_excellent": "🚀 Excellent",
        "q_good": "😊 Good",
        "q_normal": "😐 Normal",
        "q_poor": "🥱 Poor"
    },
    "ru": {
        "q_excellent": "🚀 Отлично",
        "q_good": "😊 Хорошо",
        "q_normal": "😐 Нормально",
        "q_poor": "🥱 Плохо"
    }
}

def get_quality_title(profile, quality_key):
    lang = profile.get("lang", "uk")
    return QUALITY_MAP.get(lang, QUALITY_MAP["uk"]).get(
        quality_key, QUALITY_MAP["uk"].get(quality_key, quality_key)
    )

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
# Блокування захищає від race condition при одночасних користувачах,
# а атомарний запис (temp-файл + os.replace) гарантує, що збій під час
# запису не пошкодить базу всіх користувачів.
_data_lock = threading.RLock()

def load_user_data():
    with _data_lock:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

def save_user_data(data):
    with _data_lock:
        dir_name = os.path.dirname(os.path.abspath(DATA_FILE))
        # Пишемо у тимчасовий файл у тій самій директорії, потім атомарно замінюємо
        fd, tmp_path = tempfile.mkstemp(prefix=".sleep_ai_", suffix=".tmp", dir=dir_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, DATA_FILE)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

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

save_user_profile = update_user_profile

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

def build_personal_course_fallback(profile):
    """Персоналізований курс без ШІ (якщо провайдер g4f недоступний)."""
    lang = profile.get("lang", "uk")
    dis_title = DISRUPTORS.get(lang, DISRUPTORS["uk"]).get(profile.get("disruptor", "dis_phone"), "Телефон / Гаджети")
    goal_title = GOALS.get(lang, GOALS["uk"]).get(profile.get("goal", "goal_quality"), "Покращити якість сну")

    titles = {
        1: f"☀️ День 1: Світловий біохакінг & нейтралізація «{dis_title}»",
        2: "🧘 День 2: Техніка US Navy (засинання за 120 секунд)",
        3: "🫁 День 3: Дихальна формула 4-7-8 проти кортизолу",
        4: "☕ День 4: Кофеїнове вікно & вечірні перекуси",
        5: "📝 День 5: «Коробка тривог» та правило 20 хвилин",
        6: f"❄️ День 6: Мікроклімат спальні під мету «{goal_title}»",
        7: "📜 День 7: Ваш персональний вечірній ритуал"
    }
    return {d: {"title": titles[d], "text": BOT_COURSE_DAYS[d]["text"]} for d in range(1, 8)}

def generate_personal_course(profile):
    """Генерує ШІ персональний 7-денний курс під профіль користувача."""
    lang = profile.get("lang", "uk")
    age_key = profile.get("age_group", "age_young")
    age_info = AGE_GROUPS.get(lang, AGE_GROUPS["uk"]).get(age_key, AGE_GROUPS["uk"]["age_young"])
    dis_title = DISRUPTORS.get(lang, DISRUPTORS["uk"]).get(profile.get("disruptor", "dis_phone"), "N/A")
    goal_title = GOALS.get(lang, GOALS["uk"]).get(profile.get("goal", "goal_quality"), "N/A")
    bt_title = BEDTIME_OPTIONS.get(lang, BEDTIME_OPTIONS["uk"]).get(profile.get("usual_bedtime", "bt_normal"), "N/A")
    wt_title = WAKETIME_OPTIONS.get(lang, WAKETIME_OPTIONS["uk"]).get(profile.get("usual_waketime", "wt_normal"), "N/A")

    lang_names = {"uk": "Ukrainian (українська)", "en": "English", "ru": "Russian (русский)"}
    selected_lang = lang_names.get(lang, "Ukrainian")

    prompt = (
        f"Ти — сомнолог, який складає ПЕРСОНАЛЬНИЙ 7-денний курс швидкого засинання та якісного сну.\n\n"
        f"Профіль користувача:\n"
        f"- Вікова категорія: {age_info['title']} (норма сну {age_info['target_hours']} год)\n"
        f"- Звичний час засинання: {bt_title}\n"
        f"- Звичний час підйому: {wt_title}\n"
        f"- Головна мета: {goal_title}\n"
        f"- Головна перешкода сну: {dis_title}\n\n"
        f"Склади рівно 7 днів. Кожен день — окрема практична вправа з наростанням складності, "
        f"обов'язково враховуй перешкоду «{dis_title}» та мету «{goal_title}».\n\n"
        f"Поверни ВИКЛЮЧНО валідний JSON-масив з 7 об'єктів, без пояснень і без markdown-огорожі:\n"
        f'[{{"title": "☀️ День 1: коротка назва (до 55 символів, починається з емодзі)", '
        f'"text": "🎓 **Урок 1: назва**\\n\\n🧠 **Чому це працює:** 1-2 речення науки.\\n\\n'
        f'⚡ **Практичне завдання на сьогодні:**\\n1️⃣ крок\\n2️⃣ крок\\n3️⃣ крок"}}, ...]\n\n'
        f"Вимоги: поле text — 70-130 слів, Markdown (**жирний**), емодзі, тільки конкретні дії. "
        f"У title кожного дня — РІЗНЕ тематичне емодзі на початку (не повторюй одне й те саме, напр. ☀️🧘🫁☕📝❄️📜). "
        f"Мова всього тексту обов'язково: {selected_lang}. Не використовуй символ підкреслення."
    )

    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        content = (response.choices[0].message.content or "").strip()
        start, end = content.find("["), content.rfind("]")
        if start != -1 and end > start:
            days = json.loads(content[start:end + 1])
            if isinstance(days, list) and len(days) >= 7:
                course = {}
                for i, day in enumerate(days[:7], start=1):
                    title = str(day.get("title", "")).strip()
                    text = str(day.get("text", "")).strip()
                    if len(title) < 5 or len(text) < 60:
                        raise ValueError(f"День {i}: замало контенту від ШІ")
                    course[i] = {"title": title[:90], "text": text}
                logging.info(f"AI course generated for goal={goal_title}, disruptor={dis_title}")
                return course
    except Exception as e:
        logging.error(f"AI Course Generation Error: {e}")

    return build_personal_course_fallback(profile)

def generate_ai_deep_analysis_fallback(profile, duration, quality, bedtime_str, waketime_str):
    lang = profile.get("lang", "uk")
    age_key = profile.get("age_group", "age_young")
    age_info = AGE_GROUPS.get(lang, AGE_GROUPS["uk"]).get(age_key, AGE_GROUPS["uk"]["age_young"])
    target = age_info["target_hours"]
    diff = round(duration - target, 1)
    cycles = round(duration / 1.5, 1)

    is_surplus = diff >= 0

    variants = {
        "uk": {
            "score": "90/100 🟢 Відмінно" if is_surplus else "72/100 🟡 Посередньо",
            "status_text": (
                f"Норму сну ({target} год) перевиконано. Пройдено ~{cycles} фаз."
                if is_surplus else
                f"Виявлено дефіцит у {abs(diff)} год. Пройдено ~{cycles} фаз."
            ),
            "cns_text": (
                "Нервова система повністю відновлена."
                if is_surplus else
                "Присутня залишкова втома через недосип."
            ),
        },
        "en": {
            "score": "90/100 🟢 Excellent" if is_surplus else "72/100 🟡 Fair",
            "status_text": (
                f"Sleep norm ({target}h) exceeded. ~{cycles} cycles."
                if is_surplus else
                f"Detected deficit of {abs(diff)}h. ~{cycles} cycles."
            ),
            "cns_text": (
                "Nervous system fully recovered."
                if is_surplus else
                "Residual fatigue from sleep deficit."
            ),
        },
        "ru": {
            "score": "90/100 🟢 Отлично" if is_surplus else "72/100 🟡 Посредственно",
            "status_text": (
                f"Норма сна ({target}ч) перевыполнена. ~{cycles} циклов."
                if is_surplus else
                f"Обнаружен дефицит {abs(diff)}ч. ~{cycles} циклов."
            ),
            "cns_text": (
                "Нервная система полностью восстановлена."
                if is_surplus else
                "Присутствует остаточная усталость из-за недосыпа."
            ),
        },
    }

    v = variants.get(lang, variants["uk"])
    score = v["score"]
    status_text = v["status_text"]
    cns_text = v["cns_text"]

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

# --- ГОЛОВНЕ МЕНЮ БОТА ---
def get_main_keyboard(profile, is_sleeping=False):
    lang = profile.get("lang", "uk")
    s = STRINGS.get(lang, STRINGS["uk"])
    is_premium = profile.get("is_premium", False)

    # Якщо курс не оплачено — показуємо лише кнопки купівлі та профілю
    if not is_premium:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=s.get("btn_buy", "💳 Придбати курс (99 грн)"))],
                [KeyboardButton(text=s.get("btn_profile", "👤 Профіль"))]
            ],
            resize_keyboard=True
        )

    sleep_btn = KeyboardButton(text=s["btn_wake"]) if is_sleeping else KeyboardButton(text=s["btn_sleep"])
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [sleep_btn],
            [KeyboardButton(text=s["btn_course"]), KeyboardButton(text=s["btn_ask_ai"])],
            [KeyboardButton(text=s["btn_journal"])],
            [KeyboardButton(text=s["btn_profile"])]
        ],
        resize_keyboard=True
    )
    return kb

# --- ПЕЙВОЛ: 99 грн за 7-денний курс ---
def get_course_days(profile):
    """Персональний курс від ШІ, якщо він є; інакше — базова програма."""
    personal = profile.get("personal_course")
    if isinstance(personal, dict) and len(personal) >= 7:
        try:
            course = {int(k): v for k, v in personal.items()}
            if all(d in course and course[d].get("title") and course[d].get("text") for d in range(1, 8)):
                return course
        except (ValueError, TypeError, AttributeError):
            pass
    return BOT_COURSE_DAYS

def build_paywall(profile, locked_feature=False):
    """Єдиний екран оплати для бота (99 грн, одноразово)."""
    lang = profile.get("lang", "uk")
    s = STRINGS.get(lang, STRINGS["uk"])
    course = get_course_days(profile)
    days_locked_str = "\n".join([f"🔒 **{course[d]['title']}**" for d in range(1, 8)])

    header = s.get("paywall_locked_header", "") if locked_feature else ""
    text = (
        f"{header}"
        f"{s.get('paywall_title', '')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{s.get('paywall_program', '')}\n"
        f"{days_locked_str}\n\n"
        f"{s.get('paywall_after', '')}\n\n"
        f"{s.get('paywall_price', '')}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=s.get("btn_pay_mono", "💳 Придбати доступ за 99 грн (Monobank / Card)"), callback_data="pay_mono_link")]
    ])
    return text, kb

async def require_premium(message: types.Message):
    """True — доступ є. False — показано пейвол, хендлер має вийти."""
    profile = get_user_profile(message.from_user.id)
    if profile.get("is_premium", False):
        return True

    text, kb = build_paywall(profile, locked_feature=True)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await message.answer(
        get_text(profile, "locked_menu_hint"),
        reply_markup=get_main_keyboard(profile, is_sleeping=False),
        parse_mode="Markdown"
    )
    return False

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
    goal_title = GOALS.get(lang, GOALS["uk"]).get(goal_key, "Покращити якість сну")
    dis_title = DISRUPTORS.get(lang, DISRUPTORS["uk"]).get(dis_key, "Телефон / Гаджети")

    # Первинне сповіщення про роботу ШІ
    await callback.message.delete()
    loading_msg = await callback.message.answer(
        f"🧠 **ШІ аналізує ваші відповіді...**\n"
        f"<i>Складаємо для вас Персональний 7-Денний Курс Сну під категорію «{age_info['title']}» та перешкоду «{dis_title}»...</i>",
        parse_mode="HTML"
    )

    # ШІ складає персональний курс саме під відповіді цього користувача
    course = await asyncio.to_thread(generate_personal_course, profile)
    profile["personal_course"] = {str(day): lesson for day, lesson in course.items()}
    profile["course_generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    update_user_profile(callback.from_user.id, profile)

    days_locked_str = "\n".join([f"🔒 **{course[d]['title']}**" for d in range(1, 8)])

    paywall_text = (
        f"✨ **ШІ сформував ваш Персональний 7-Денний Курс Сну!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 **Аналіз вашого профілю:**\n"
        f"• Категорія: **{age_info['title']}**\n"
        f"• Мета: **{goal_title}**\n"
        f"• Головна перешкода: **{dis_title}**\n\n"
        f"🎯 **Згенерована персоналізована програма:**\n"
        f"{days_locked_str}\n\n"
        f"🔒 **Доступ закритий.** Без оплати пройти ваш персональний курс неможливо.\n"
        f"Щоб відкрити всі 7 днів уроків, трекер сну, ШІ-консультанта та чек-лист, придбайте доступ.\n\n"
        f"🏷️ **Вартість курсу:** **99 грн** *(одноразовий платіж • доступ назавжди)*"
    )

    buttons = [
        [InlineKeyboardButton(text="💳 Придбати доступ за 99 грн (Monobank / Card)", callback_data="pay_mono_link")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        await loading_msg.delete()
    except Exception:
        pass

    await callback.message.answer(paywall_text, reply_markup=kb, parse_mode="Markdown")
    # Відображення обмеженої клавіатури до оплати
    await callback.message.answer(
        "🔒 **Усі функції заблоковано до оплати.** Скористайтеся меню нижче:",
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
    if not await require_premium(message):
        return

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
    if not await require_premium(message):
        return

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
    quality = get_text(profile, "quality_auto")

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

    saved_msg = get_text(profile, "log_saved", date=date_str, duration=duration_rounded, bedtime=bedtime_str, waketime=waketime_str, quality=quality)

    status_str = get_text(profile, "ai_thinking")

    msg = await message.answer(
        f"{saved_msg}\n\n{status_str}",
        reply_markup=get_main_keyboard(profile, is_sleeping=False),
        parse_mode="Markdown"
    )

    ai_deep_report = await asyncio.to_thread(generate_real_ai_analysis, profile, duration_rounded, quality, bedtime_str, waketime_str)

    final_content = f"{saved_msg}\n\n{ai_deep_report}"
    await safe_edit_message(msg, final_content, parse_mode="Markdown")

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

    profile_text = (
        f"{get_text(profile, 'profile_title')}\n\n"
        + get_text(
            profile, "profile_body",
            lang=LANGUAGES.get(lang, "Українська"),
            age=age_info["title"],
            target=age_info["target_hours"],
            bedtime=bt_title,
            waketime=wt_title,
        )
    )
    await message.answer(
        profile_text,
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "re_onboarding")
async def re_onboarding(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await cmd_start(callback.message, state)

# --- 📜 ЖУРНАЛ СНУ ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_journal"], STRINGS["en"]["btn_journal"], STRINGS["ru"]["btn_journal"]]))
async def process_journal(message: types.Message):
    if not await require_premium(message):
        return

    profile = get_user_profile(message.from_user.id)
    logs = profile.get("logs", [])
    if not logs:
        await message.answer(get_text(profile, "journal_empty"), parse_mode="Markdown")
        return

    text = get_text(profile, "journal_title") + "\n\n"
    for log in logs[:5]:
        text += get_text(
            profile, "journal_entry",
            date=log["date"],
            bedtime=log["bedtime"],
            waketime=log["waketime"],
            duration=log["duration"],
            quality=log["quality"],
        ) + "\n\n"

    await message.answer(text, parse_mode="Markdown")

# --- 🎓 7-ДЕННИЙ ІНТЕНСИВ СНУ ТА ВЕЧІРНІЙ ЧЕК-ЛИСТ ---
BOT_COURSE_DAYS = {
    1: {
        "title": "☀️ День 1: Світловий біохакінг & Мелатонін",
        "text": (
            "🎓 **Урок 1: Світловий біохакінг & Мелатонін**\n\n"
            "🧠 **Чому ми важко засинаємо?**\n"
            "Гормон сну *мелатонін* виділяється епіфізом тільки в темряві. Яскраве синє світло екранів смартфонів та лампочок блокує виділення мелатоніну майже на 80%!\n\n"
            "⚡ **Практичне завдання на сьогодні:**\n"
            "1️⃣ **Вранці:** Отримайте 10-15 хв сонячного світла безпосередньо після підйому (перезапуск біологічного годинника).\n"
            "2️⃣ **Ввечері:** За 45 хв до сну вимкніть яскраве освітлення, увімкніть 'Night Shift' на телефоні та відкладіть екрани."
        )
    },
    2: {
        "title": "🧘 День 2: US Navy 2-Min Technique",
        "text": (
            "🎓 **Урок 2: Військова техніка засинання (US Navy)**\n\n"
            "🧘 **Засинай за 120 секунд в будь-яких умовах:**\n"
            "1️⃣ **Розслаблення обличчя:** Заплющте очі, розслабте чоло, щелепу та язик.\n"
            "2️⃣ **Опустіть плечі:** Дозвольте плечам повністю провалитися в матрац.\n"
            "3️⃣ **Видихніть:** Повністю розслабте груди та ноги від стегон до ступень.\n"
            "4️⃣ **Очистіть розум:** Уявіть себе в човні на тихому озері під зорями. Повторюйте: *'Не думай, не думай, не думай'* (10 сек)."
        )
    },
    3: {
        "title": "🫁 День 3: Техніка 4-7-8 & Спокій",
        "text": (
            "🎓 **Урок 3: Сповільнення серцевого ритму (4-7-8)**\n\n"
            "🫁 **Секрет активації вагусного нерва:**\n"
            "1️⃣ Вдих носом — **4 секунди**\n"
            "2️⃣ Затримайте дихання — **7 секунд**\n"
            "3️⃣ Повільний видих ротом — **8 секунд**\n\n"
            "✨ Повторіть 4 цикли. Це знижує пульс та рівень кортизолу за 2 хвилини!"
        )
    },
    4: {
        "title": "☕ День 4: Кофеїнове вікно & Вечеря",
        "text": (
            "🎓 **Урок 4: Кофеїновий тайм-аут & Вечеря**\n\n"
            "☕ **Період напіввиведення кофеїну = 6 годин!**\n"
            "• Остання чашка кави — не пізніше ніж за 7-8 годин до сну.\n"
            "• Вечеря за 2.5-3 години до сну (уникайте важкого жирного м'яса).\n"
            "• Перекус: ромашковий чай, жменя мигдалю або банан."
        )
    },
    5: {
        "title": "📝 День 5: Правило 20 хв & 'Коробка тривог'",
        "text": (
            "🎓 **Урок 5: Правило 20 хвилин & 'Коробка тривог'**\n\n"
            "💡 **Якщо не засинається понад 20 хв:**\n"
            "Встаньте з ліжка, сядьте в крісло при тьмяному світлі та почитайте книгу. Повертайтеся в ліжко тільки при появі сонливості!\n\n"
            "📝 **'Коробка тривог' (Brain Dump):**\n"
            "Випишіть усі тривожні думки та справи на завтра в блокнот за 1 годину до сну."
        )
    },
    6: {
        "title": "❄️ День 6: Мікроклімат спальні (18-20°C)",
        "text": (
            "🎓 **Урок 6: Мікроклімат спальні & Глибокий сон**\n\n"
            "🌡️ **Температура 18-20°C:** Для засинання температура тіла має впасти на 1°C.\n"
            "💨 **Провітрювання:** 10 хвилин перед сном.\n"
            "🕶️ **Повна темрява:** Маска для сну або штори Blackout.\n"
            "🛁 **Теплий душ за 1 год до сну:** Прискорює охолодження тіла після виходу з ванної."
        )
    },
    7: {
        "title": "📜 День 7: Персональний ритуал сну",
        "text": (
            "🎓 **Урок 7: Персональний вечірній ритуал & Фінал**\n\n"
            "🎉 **Вітаємо! Ви завершили 7-денний інтенсив сну!**\n\n"
            "✨ **Ваш вечірній чек-лист перед сном:**\n"
            "✅ Провітрив спальню (18-20°C)\n"
            "✅ Вимкнув екрани за 45 хв\n"
            "✅ Виписав тривожні думки в блокнот\n"
            "✅ Виконав 4-7-8 дихання та US Navy релаксацію"
        )
    }
}

@dp.message(F.text.in_([STRINGS["uk"]["btn_course"], STRINGS["en"]["btn_course"], STRINGS["ru"]["btn_course"]]))
async def process_course_main(message: types.Message):
    profile = get_user_profile(message.from_user.id)
    is_premium = profile.get("is_premium", False)

    if not is_premium:
        paywall_text, kb = build_paywall(profile)
        await message.answer(paywall_text, reply_markup=kb, parse_mode="Markdown")
        return

    # User IS Premium
    completed = profile.get("course_completed", [])
    count = len(completed)
    percent = int((count / 7) * 100)
    course = get_course_days(profile)

    text = (
        f"👑 **Ваш Персональний 7-Денний Курс Сну** *(доступ активний)*\n\n"
        f"📊 Ваш прогрес: **{count}/7 днів** ({percent}%)\n\n"
        f"Оберіть день курсу для проходження практичного уроку:"
    )

    buttons = []
    for day in range(1, 8):
        icon = "✅" if day in completed else "📘"
        buttons.append([InlineKeyboardButton(text=f"{icon} {course[day]['title']}", callback_data=f"crs_day_{day}")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "pay_mono_link")
async def process_pay_mono_link(callback: CallbackQuery, state: FSMContext):
    profile = get_user_profile(callback.from_user.id)
    text = (
        f"{get_text(profile, 'pay_mono_title')}\n\n"
        f"{get_text(profile, 'pay_mono_steps')}"
    )
    buttons = [
        [InlineKeyboardButton(text=get_text(profile, "btn_pay_link"), url="https://send.monobank.ua")],
        [InlineKeyboardButton(text=get_text(profile, "btn_pay_sent"), callback_data="pay_upload_receipt")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "pay_upload_receipt")
async def process_pay_upload_receipt(callback: CallbackQuery, state: FSMContext):
    profile = get_user_profile(callback.from_user.id)
    await state.set_state(PaymentReceiptState.waiting_for_receipt)
    await callback.message.answer(
        get_text(profile, "receipt_ask"),
        parse_mode="Markdown"
    )
    await callback.answer()

# --- ОБРОБНИК ФОТО КВИТАНЦІЇ ВІД КОРИСТУВАЧА ---
@dp.message(PaymentReceiptState.waiting_for_receipt, F.photo)
async def process_receipt_photo(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    raw_uname = message.from_user.username or message.from_user.first_name or f"User_{user_id}"
    safe_uname = html.escape(str(raw_uname))
    photo_file_id = message.photo[-1].file_id
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Формування повідомлення в адмін-групу
    admin_caption = (
        f"💳 <b>Нова квитанція про оплату (99 грн)!</b>\n\n"
        f"👤 <b>Користувач:</b> @{safe_uname} ({html.escape(message.from_user.first_name)})\n"
        f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
        f"📅 <b>Час надсилання:</b> <i>{now_str}</i>"
    )

    buttons = [
        [
            InlineKeyboardButton(text="✅ Прийняти (Активувати)", callback_data=f"adm_approve_{user_id}"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data=f"adm_reject_{user_id}")
        ]
    ]
    admin_kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    # Відправка фото квитанції в адмін-групу
    try:
        await bot.send_photo(chat_id=ADMIN_GROUP_ID, photo=photo_file_id, caption=admin_caption, reply_markup=admin_kb, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to send receipt to admin group: {e}")
        # Запасний варіант відправки особисто адміну
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_photo(chat_id=admin_id, photo=photo_file_id, caption=admin_caption, reply_markup=admin_kb, parse_mode="HTML")
            except Exception:
                pass

    user_profile = get_user_profile(user_id)
    await message.answer(
        get_text(user_profile, "receipt_received"),
        parse_mode="Markdown"
    )

@dp.message(PaymentReceiptState.waiting_for_receipt)
async def process_receipt_not_photo(message: types.Message):
    profile = get_user_profile(message.from_user.id)
    await message.answer(get_text(profile, "receipt_not_photo"), parse_mode="Markdown")

# --- ОБРОБНИКИ КНОПОК ПРИЙНЯТИ / ВІДХИЛИТИ В АДМІН-ГРУПІ ---
@dp.callback_query(F.data.startswith("adm_approve_"))
async def process_admin_approve_payment(callback: CallbackQuery):
    target_user_id = int(callback.data.replace("adm_approve_", "").strip())
    admin_name = callback.from_user.username or callback.from_user.first_name
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Активація доступу
    profile = get_user_profile(target_user_id)
    profile["is_premium"] = True
    profile["purchased_at"] = f"{now_str} (Receipt Approved by @{admin_name})"
    save_user_profile(target_user_id, profile)

    # Оновлення повідомлення в групі
    orig_caption = callback.message.caption or ""
    new_caption = orig_caption + f"\n\n✅ <b>ПІДТВЕРДЖЕНО АДМІНОМ</b> (@{html.escape(str(admin_name))})"
    try:
        await callback.message.edit_caption(caption=new_caption, reply_markup=None, parse_mode="HTML")
    except Exception:
        pass

    # Повідомлення користувачу в приватні повідомлення з розблокованою клавіатурою
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=get_text(profile, "pay_approved_user"),
            reply_markup=get_main_keyboard(profile, is_sleeping=False),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Failed to notify user {target_user_id}: {e}")

    await callback.answer("✅ Оплату підтверджено та доступ активовано!", show_alert=True)

@dp.callback_query(F.data.startswith("adm_reject_"))
async def process_admin_reject_payment(callback: CallbackQuery):
    target_user_id = int(callback.data.replace("adm_reject_", "").strip())
    admin_name = callback.from_user.username or callback.from_user.first_name

    # Оновлення повідомлення в групі
    orig_caption = callback.message.caption or ""
    new_caption = orig_caption + f"\n\n❌ <b>ВІДХИЛЕНО АДМІНОМ</b> (@{html.escape(str(admin_name))})"
    try:
        await callback.message.edit_caption(caption=new_caption, reply_markup=None, parse_mode="HTML")
    except Exception:
        pass

    # Повідомлення користувачу в приватні повідомлення
    profile = get_user_profile(target_user_id)
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=get_text(profile, "pay_rejected_user"),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Failed to notify user {target_user_id}: {e}")

    await callback.answer("❌ Оплату відхилено", show_alert=True)

@dp.message(F.text.in_([STRINGS["uk"]["btn_buy"], STRINGS["en"]["btn_buy"], STRINGS["ru"]["btn_buy"]]))
async def cmd_buy_course_btn(message: types.Message):
    profile = get_user_profile(message.from_user.id)
    if profile.get("is_premium", False):
        await message.answer(get_text(profile, "already_premium"), reply_markup=get_main_keyboard(profile), parse_mode="Markdown")
        return

    text = (
        f"{get_text(profile, 'pay_mono_title')}\n\n"
        f"{get_text(profile, 'pay_mono_steps')}"
    )
    buttons = [
        [InlineKeyboardButton(text=get_text(profile, "btn_pay_link"), url="https://send.monobank.ua")],
        [InlineKeyboardButton(text=get_text(profile, "btn_pay_sent"), callback_data="pay_upload_receipt")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

# --- ГОЛОВНА АДМІН-ПАНЕЛЬ (/admin) ---
def build_admin_dashboard():
    all_data = load_user_data()
    total_users = len(all_data)
    buyers = [uid for uid, p in all_data.items() if p.get("is_premium", False)]
    total_buyers = len(buyers)
    revenue = total_buyers * 99
    conversion = round((total_buyers / total_users * 100), 1) if total_users > 0 else 0
    total_logs = sum(len(p.get("logs", [])) for p in all_data.values())

    text = (
        f"👑 <b>Панель Управління Адміністратора</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Аналітика Проєкту:</b>\n"
        f"• 👥 Всього користувачів: <b>{total_users}</b>\n"
        f"• 💳 Продано курсів (99 грн): <b>{total_buyers}</b>\n"
        f"• 💰 Загальний дохід: <b>{revenue} грн</b>\n"
        f"• 📈 Конверсія в покупку: <b>{conversion}%</b>\n"
        f"• 📝 Записів сну в системі: <b>{total_logs}</b>\n\n"
        f"Оберіть потрібний розділ меню нижче:"
    )

    buttons = [
        [InlineKeyboardButton(text="👥 Список покупців", callback_data="admin_buyers")],
        [InlineKeyboardButton(text="📢 Масова розсилка", callback_data="admin_broadcast_info"), InlineKeyboardButton(text="⚡ Видати доступ", callback_data="admin_grant_info")],
        [InlineKeyboardButton(text="🔄 Оновити дані", callback_data="admin_refresh")]
    ]
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ <b>Доступ заборонено.</b> Команда доступна лише власникові бота.", parse_mode="HTML")
        return
    text, kb = build_admin_dashboard()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_refresh")
async def process_admin_refresh(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return
    text, kb = build_admin_dashboard()
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("🔄 Панель оновлено!", show_alert=False)

@dp.callback_query(F.data == "admin_buyers")
async def process_admin_buyers(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return

    all_data = load_user_data()
    buyers_list = []
    for uid, prof in all_data.items():
        if prof.get("is_premium", False):
            raw_uname = str(prof.get("username", f"User_{uid}"))
            safe_uname = html.escape(raw_uname)
            pdate = html.escape(str(prof.get("purchased_at", "Невідомо")))
            progress = len(prof.get("course_completed", []))
            buyers_list.append(f"• <b>@{safe_uname}</b> (ID: <code>{uid}</code>)\n  📅 <i>{pdate}</i> | 📊 Прогрес: <b>{progress}/7 днів</b>")

    content = "\n\n".join(buyers_list) if buyers_list else "Поки немає жодного покупця."
    text = f"📋 <b>Детальний список покупців ({len(buyers_list)}):</b>\n\n{content}"
    
    buttons = [[InlineKeyboardButton(text="🔙 Назад в Адмінку", callback_data="admin_refresh")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_grant_info")
async def process_admin_grant_info(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return

    text = (
        "⚡ <b>Управління доступом користувачів</b>\n\n"
        "🟢 <b>Видати доступ до курсу:</b>\n"
        "<code>/grant TELEGRAM_USER_ID</code>\n"
        "<i>(наприклад: /grant 1373248099)</i>\n\n"
        "🔴 <b>Забрати (анулювати) доступ:</b>\n"
        "<code>/revoke TELEGRAM_USER_ID</code>\n"
        "<i>(наприклад: /revoke 1373248099)</i>"
    )
    buttons = [[InlineKeyboardButton(text="🔙 Назад в Адмінку", callback_data="admin_refresh")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast_info")
async def process_admin_broadcast_info(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return

    text = (
        "📢 **Масова розсилка повідомлень**\n\n"
        "Ви можете відправити сповіщення усім користувачам бота за допомогою команди:\n\n"
        "`/broadcast Ваше повідомлення для розсилки`\n\n"
        "Наприклад:\n`/broadcast 🔥 Знижка на курс сну! Напишіть /course для деталей.`"
    )
    buttons = [[InlineKeyboardButton(text="🔙 Назад в Адмінку", callback_data="admin_refresh")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
    await callback.answer()

# --- КОМАНДИ ГРАНТУ ТА РОЗСИЛКИ ---
@dp.message(F.text.startswith("/grant"))
async def cmd_grant(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Вкажіть Telegram ID користувача, наприклад:\n`/grant 123456789`", parse_mode="Markdown")
        return

    target_id = parts[1].strip()
    if not target_id.isdigit():
        await message.answer(
            "❌ Некоректний Telegram ID. ID має складатися лише з цифр, наприклад:\n`/grant 123456789`",
            parse_mode="Markdown",
        )
        return

    profile = get_user_profile(target_id)
    profile["is_premium"] = True
    profile["purchased_at"] = datetime.now().strftime("%Y-%m-%d %H:%M") + " (Admin Grant)"
    save_user_profile(target_id, profile)
    
    await message.answer(f"✅ Доступ до курсу успішно надано користувачу з ID `{target_id}`!", parse_mode="Markdown")

@dp.message(F.text.startswith("/revoke"))
async def cmd_revoke(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Вкажіть Telegram ID користувача для анулювання доступу, наприклад:\n`/revoke 123456789`", parse_mode="Markdown")
        return

    target_id = parts[1].strip()
    if not target_id.isdigit():
        await message.answer(
            "❌ Некоректний Telegram ID. ID має складатися лише з цифр, наприклад:\n`/revoke 123456789`",
            parse_mode="Markdown",
        )
        return

    profile = get_user_profile(target_id)
    profile["is_premium"] = False
    save_user_profile(target_id, profile)
    
    await message.answer(f"🚫 **Доступ до курсу успішно анульовано** для користувача з ID `{target_id}`!", parse_mode="Markdown")

@dp.message(F.text.startswith("/broadcast"))
async def cmd_broadcast(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    broadcast_text = message.text.replace("/broadcast", "").strip()
    if not broadcast_text:
        await message.answer("⚠️ Введіть текст розсилки після команди, наприклад:\n`/broadcast Привіт усім!`", parse_mode="Markdown")
        return

    all_data = load_user_data()
    success_count = 0
    fail_count = 0

    status_msg = await message.answer("🚀 Розсилка розпочата...")

    for uid in all_data.keys():
        try:
            await bot.send_message(chat_id=int(uid), text=broadcast_text, parse_mode="Markdown")
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"🎉 **Масову розсилку завершено!**\n\n"
        f"✅ Доставили: **{success_count}** користувачів\n"
        f"❌ Не доставлено / заблоковано: **{fail_count}**",
        parse_mode="Markdown"
    )

def get_unlocked_days(profile):
    """Скільки днів курсу вже розблоковано.

    Логіка: День 1 відкривається одразу після оплати, а кожен наступний день —
    через добу після попереднього (День 2 наступного дня, День 3 через 2 дні тощо).
    Отже, кількість розблокованих днів = 1 + (повних діб з моменту оплати),
    але не більше 7.
    """
    purchased_raw = profile.get("purchased_at")
    if not purchased_raw:
        # Немає позначки про оплату — відкриваємо лише перший день.
        return 1

    # purchased_at може мати суфікс, напр. "2026-08-09 11:20 (Receipt Approved...)".
    # Беремо перші 16 символів = "%Y-%m-%d %H:%M".
    try:
        purchased_dt = datetime.strptime(purchased_raw[:16], "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return 1

    days_passed = (datetime.now() - purchased_dt).days
    unlocked = 1 + max(days_passed, 0)
    return min(unlocked, 7)

def render_course_list(profile):
    """Список днів персонального курсу з прогресом та поступовим розблокуванням."""
    completed = profile.get("course_completed", [])
    count = len(completed)
    percent = int((count / 7) * 100)
    course = get_course_days(profile)
    unlocked = get_unlocked_days(profile)

    text = (
        f"👑 **Ваш Персональний 7-Денний Курс Сну**\n\n"
        f"📊 Ваш прогрес: **{count}/7 днів** ({percent}%)\n"
        f"🔓 Відкрито днів: **{unlocked}/7**\n\n"
        f"Курс відкривається поступово — по одному дню щодоби. "
        f"Оберіть доступний день, щоб пройти практичний урок:"
    )
    buttons = []
    for day in range(1, 8):
        if day > unlocked:
            # Ще заблокований день — показуємо замок і скільки чекати.
            wait = day - unlocked
            lock_label = f"🔒 День {day} (через {wait} дн.)"
            buttons.append([InlineKeyboardButton(text=lock_label, callback_data="crs_locked")])
        else:
            icon = "✅" if day in completed else "📘"
            buttons.append([InlineKeyboardButton(text=f"{icon} {course[day]['title']}", callback_data=f"crs_day_{day}")])

    return text, InlineKeyboardMarkup(inline_keyboard=buttons)

async def deny_if_not_premium(callback: CallbackQuery, profile):
    """Блокує доступ до уроків, якщо оплату не підтверджено (або її відкликано)."""
    if profile.get("is_premium", False):
        return False
    await callback.answer("🔒 Доступ до курсу закрито. Придбайте курс за 99 грн.", show_alert=True)
    text, kb = build_paywall(profile)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    return True

@dp.callback_query(F.data == "crs_locked")
async def process_course_locked(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    unlocked = get_unlocked_days(profile)
    next_day = unlocked + 1
    await callback.answer(
        f"🔒 День {next_day} ще закритий. Курс відкривається по одному дню щодоби — "
        f"повертайтеся завтра!",
        show_alert=True,
    )

@dp.callback_query(F.data.startswith("crs_day_"))
async def process_course_day_view(callback: CallbackQuery):
    day_num = int(callback.data.split("_")[2])
    profile = get_user_profile(callback.from_user.id)
    if await deny_if_not_premium(callback, profile):
        return

    # Захист від відкриття ще заблокованого дня (наприклад, через застарілу кнопку).
    if day_num > get_unlocked_days(profile):
        await callback.answer(
            "🔒 Цей день ще не відкрито. Нові дні курсу з'являються по одному щодоби.",
            show_alert=True,
        )
        return

    completed = profile.get("course_completed", [])
    is_done = day_num in completed

    course = get_course_days(profile)
    text = course.get(day_num, course[1])["text"]

    btn_done_text = "✅ Позначити день пройденим" if not is_done else "🎉 Урок пройдено! (Скасувати)"
    buttons = [
        [InlineKeyboardButton(text=btn_done_text, callback_data=f"crs_toggle_{day_num}")],
        [InlineKeyboardButton(text="🔙 До списку уроків", callback_data="crs_back_list")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("crs_toggle_"))
async def process_course_day_toggle(callback: CallbackQuery):
    day_num = int(callback.data.split("_")[2])
    profile = get_user_profile(callback.from_user.id)
    if await deny_if_not_premium(callback, profile):
        return

    if "course_completed" not in profile:
        profile["course_completed"] = []

    if day_num in profile["course_completed"]:
        profile["course_completed"].remove(day_num)
        msg = f"↩️ Позначку Дня {day_num} скасовано."
    else:
        profile["course_completed"].append(day_num)
        msg = f"🎉 Вітаємо! День {day_num} успішно пройдено!"

    save_user_profile(callback.from_user.id, profile)
    await callback.answer(msg, show_alert=True)

    text, kb = render_course_list(profile)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "crs_back_list")
async def process_course_back(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    if await deny_if_not_premium(callback, profile):
        return

    text, kb = render_course_list(profile)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

# --- 🤖 ЗАПИТАТИ ШІ-КОНСУЛЬТАНТА ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_ask_ai"], STRINGS["en"]["btn_ask_ai"], STRINGS["ru"]["btn_ask_ai"]]))
async def ask_ai_start(message: types.Message, state: FSMContext):
    if not await require_premium(message):
        return

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

    # Прибираємо webhook та скидаємо чергу оновлень, щоб уникнути
    # TelegramConflictError (коли інший екземпляр опитує того самого бота)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logging.warning(f"delete_webhook failed (продовжуємо): {e}")

    # Запускаємо polling бота
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот зупинений.")