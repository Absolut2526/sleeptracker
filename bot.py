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
import hashlib
import hmac

# Ensure the project root is in sys.path so that submodules (sleep_logic, reminders) are findable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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

import sleep_logic
import timeutil
from reminders import ReminderScheduler, get_reminders, DEFAULT_REMINDERS

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

DATA_FILE = os.getenv("DATA_FILE", "sleep_ai_data.json")

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

# Trial configuration
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "1"))

# Support tickets file
TICKETS_FILE = os.getenv("TICKETS_FILE", "support_tickets.json")

class PaymentReceiptState(StatesGroup):
    waiting_for_receipt = State()

class SupportState(StatesGroup):
    waiting_for_message = State()

class AdminSupportState(StatesGroup):
    waiting_for_reply = State()

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
        "locked_menu_hint": "🔒 Меню нижче доступне до оплати:",
        # === TRIAL ===
        "trial_offer_title": "✨ **Try Premium for free!**",
        "trial_offer_what": "На {days} день ви отримаєте:\n• AI Sleep Coach\n• День 1 персонального курсу\n• Цілі та нагадування\n• Розширена статистика",
        "trial_offer_note": "Ваші дані та прогрес зберігаються.",
        "trial_offer_no_auto": "Після завершення Trial Premium не продовжується автоматично — немає автосписання.",
        "cta_try": "✨ Try Premium",
        "trial_activated": "🎉 **Premium Trial activated!**",
        "trial_now_title": "Ось що тепер доступно:",
        "trial_ends_on": "⏳ Trial закінчиться: **{date}**",
        "trial_ended": "⏳ **Ваш Premium Trial завершено.**\n\nВаші дані та прогрес збережені. Нічого не втрачено.",
        "trial_already_used": "⚠️ Ви вже використали безкоштовний Trial.",
        "trial_back_hint": "🔙 Повернутися до вибору",
        "trial_keyboard_hint": "✅ Оновлено! Оберіть розділ меню:",
        # === AI COACH ===
        "ai_coach_welcome": "🧠 **AI Sleep Coach**\n\nЗапитайте мене про свій сон. Натисніть пропозицію нижче або напишіть власну:",
        "ai_q_score": "Чому мій Score низький?",
        "ai_q_tonight": "Як покращити сон цієї ночі?",
        "ai_q_7days": "Проаналізуй мої останні 7 днів",
        "ai_q_first": "Що змінити першим?",
        # === SUPPORT ===
        "btn_support": "💬 Support",
        "support_title": "💬 **Support**\n\nЯк ми можемо допомогти?",
        "support_cat_bug": "🐛 Report a problem",
        "support_cat_payment": "💳 Payment problem",
        "support_cat_question": "❓ Ask a question",
        "support_ask_message": "✍️ **{category}**\n\nОпишіть вашу проблему. Зазвичай відповідаємо протягом декількох годин:",
        "support_received": "✅ **Ваше повідомлення надіслано в підтримку.**",
        "support_back_hint": "✅ Готово! Оберіть розділ меню:",
        "welcome_back": "👋 Вітаємо знову! Ваш профіль уже налаштовано. Оберіть дію:",
        "btn_stats": "📊 Статистика",
        "btn_goals": "🎯 Цілі",
        "btn_reminders": "⏰ Нагадування",
        "btn_achievements": "🏆 Досягнення",
        "ask_quality": "😴 Як ви оціните **якість сну** від 1 до 10?\n*(1 — жахливо, 10 — ідеально)*",
        "ask_wakeups": "🌙 Скільки разів ви **прокидалися вночі**?",
        "ask_factors": "📋 Що було **перед сном**? Натискайте кнопки, щоб позначити:\n\n☕ **Кофеїн** — кава/чай/енергетик після 18:00\n📱 **Телефон** — екрани в ліжку перед сном\n😴 **Денний сон** — спали вдень",
        "factors_done": "✅ Готово",
        "skip_btn": "⏭ Пропустити",
        "score_title": "🌙 **Sleep Score:** **{score}/100**",
        "score_good": "✅ **Що добре:**\n{items}",
        "score_bad": "⚠️ **Що погіршило результат:**\n{items}",
        "score_tips": "💡 **Що можна покращити сьогодні:**\n{items}",
        "duration_ok": "тривалість у нормі",
        "duration_low": "сон коротший за норму",
        "tip_duration": "лягти на 30 хв раніше, щоб збільшити сон",
        "quality_ok": "висока якість сну",
        "quality_low": "низька якість сну",
        "wakeups_ok": "сон без пробуджень",
        "wakeups_many": "часті пробудження",
        "tip_wakeups": "спробувати дихальну практику 4-7-8 перед сном",
        "bedtime_ok": "час засинання близький до цілі",
        "bedtime_late": "пізнє засинання",
        "tip_bedtime": "поступово зсувати засинання на 15 хв раніше щовечора",
        "waketime_ok": "час підйому близький до цілі",
        "waketime_late": "пізній підйом",
        "caffeine_bad": "кофеїн увечері",
        "tip_caffeine": "без кофеїну за 6-8 годин до сну",
        "screens_bad": "телефон перед сном",
        "tip_screens": "прибрати екрани за 45 хв до сну",
        "stats_title": "📊 **Статистика сну — останні {days} днів**",
        "stats_count": "📝 Записів: **{count}**",
        "avg_duration": "⏱ Середня тривалість: **{value}**",
        "avg_score": "🌙 Середній Sleep Score: **{value}/100**",
        "avg_bedtime": "🌅 Середній час засинання: **{value}**",
        "avg_waketime": "☀️ Середній час підйому: **{value}**",
        "best_day": "🏅 Найкращий день: **{date}** ({score}/100)",
        "worst_day": "🧱 Найгірший день: **{date}** ({score}/100)",
        "stability": "📈 Стабільність режиму: **{value}**",
        "stability_high": "висока 🟢",
        "stability_medium": "середня 🟡",
        "stability_low": "низька 🔴",
        "no_data": "😴 Ще недостатньо записів для аналізу. Записуйте сон щодня — і статистика з'явиться!",
        "patterns_title": "🔍 **Закономірності:**",
        "pattern_late_bedtime": "У дні, коли ви лягаєте пізніше за ціль, Sleep Score у середньому на {diff} балів нижчий",
        "pattern_caffeine": "У дні з кофеїном увечері Score у середньому на {diff} балів нижчий",
        "pattern_screens": "У дні з телефоном перед сном Score у середньому на {diff} балів нижчий",
        "pattern_wakeups": "У ночі з пробудженнями (2+) Score у середньому на {diff} балів нижчий",
        "rec_title": "💡 **Персональні рекомендації:**",
        "rec_duration": "💤 Сон у середньому коротший за норму. Додайте 30-60 хв до часу сну щовечора",
        "rec_bedtime": "🌙 Ви лягаєте пізніше за ціль. Зсувайте засинання на 15 хв раніше кожні 2 дні",
        "rec_waketime": "☀️ Час підйому нестабільний. Вставайте в один і той самий час навіть у вихідні",
        "rec_screens": "📱 Часто телефон перед сном. Вимкніть екрани за 45 хв до сну — це підніме Score",
        "rec_caffeine": "☕ Часто кофеїн увечері. Остання кава — за 6-8 годин до сну",
        "rec_wakeups": "🌙 Часті пробудження вночі. Спробуйте вечірній ритуал: 4-7-8 дихання та прохолодна спальня",
        "rec_keep": "👏 Ви тримаєте режим! Продовжуйте та намагайтеся лягати в один і той самий час",
        "goals_title": "🎯 **Ваші цілі сну:**",
        "goals_body": "🌅 Лягати: **{bedtime}**\n☀️ Вставати: **{waketime}**\n⏱ Сон: **{duration} год**\n\n📊 **Прогрес за 7 днів:**\n• Середній час засинання: **{avg_bedtime}**\n• Середній час підйому: **{avg_waketime}**\n• Середня тривалість: **{avg_duration}**",
        "goal_set_bedtime": "🌅 **Цільовий час засинання.** Виберіть час:",
        "goal_set_waketime": "☀️ **Цільовий час підйому.** Виберіть час:",
        "goal_set_duration": "⏱ **Бажана тривалість сну.** Виберіть:",
        "goal_saved": "✅ Ціль збережено!",
        "goal_btn_bedtime": "Час сну",
        "goal_btn_waketime": "Підйом",
        "goal_btn_duration": "Тривалість",
        "rem_tz_btn": "Часовий пояс",
        "rem_title": "⏰ **Нагадування**\n\nОберіть нагадування для налаштування. Для вимкнення — вимкніть перемикач.",
        "rem_type_wind_down": "🌙 Підготовка до сну",
        "rem_type_log": "📝 Записати сон",
        "rem_type_morning": "☀️ Ранкове",
        "rem_type_goal": "🎯 Цільовий час сну",
        "rem_on": "🟢 Увімкнено",
        "rem_off": "⚪ Вимкнено",
        "rem_enabled": "✅ Увімкнено",
        "rem_disabled": "❌ Вимкнено",
        "rem_tz_title": "🌍 **Часовий пояс.** Оберіть зміщення відносно UTC:",
        "rem_tz_saved": "✅ Часовий пояс збережено: UTC{offset}",
        "rem_time_title": "⏰ Виберіть час нагадування:",
        "rem_time_saved": "✅ Час нагадування: **{time}**",
        "rem_wind_down": "🌙 **Час готуватися до сну!**\n\nЗа годину до сну:\n1️⃣ Приглушіть світло, приберіть екрани\n2️⃣ Провітріть спальню\n3️⃣ Зробіть дихальну практику 4-7-8",
        "rem_log": "📝 **Як минула ніч?**\nЯкщо ви ще не записали сон — натисніть «☀️ Я прокинувся» в меню. 🌙",
        "rem_morning": "☀️ **Доброго ранку!**\nПроведіть 10 хвилин на світлі — це запускає біоритми. І не забудьте записати свій сон!",
        "rem_goal": "🎯 **Час лягати спати відповідно до вашої цілі!**\nНадобраніч, спокійного сну! 🌙",
        "ach_title": "🏆 **Досягнення**\n\n⭐ Рівень: **{level}** | XP: **{xp}**\n📈 Прогрес до рівня {next}: **{progress}%**\n🔥 Серія днів: **{streak}**\n\nДосягнення:",
        "ach_first_log": "🏆 Перший запис сну",
        "ach_streak_3": "🔥 3 дні поспіль",
        "ach_streak_7": "🔥 7 днів поспіль",
        "ach_nights_8h_5": "🌙 5 ночей з 8+ годинами",
        "ach_score_90": "⭐ Sleep Score 90+",
        "ach_score_80_3": "💎 3 дні зі Score 80+",
        "ach_early_5": "🌅 5 ранніх підйомів",
        "ach_no_phone_3": "📵 3 ночі без телефону",
        "ach_new": "🎉 **Нове досягнення:** {achievement}!",
        "level_up": "⬆️ **Новий рівень {level}!** Продовжуйте в тому ж дусі!",
        "unknown_msg": "🤔 Я не розумію це повідомлення. Скористайтеся кнопками меню нижче:",
        "step_duration": "🔹 **Скільки годин ви зазвичай спите?**",
        "step_problem": "🔹 **Що найчастіше заважає вам якісно спати?**",
        "onboarding_done": "🎉 **Твій персональний план готовий!**\n\n⏱ Цільовий сон: **{duration} год**\n🌅 Бажаний час сну: **{bedtime}**\n☀️ Бажаний підйом: **{waketime}**\n\nДалі ШІ складе для вас персональний 7-денний курс покращення сну. 🧠",
        "score_badge_high": "🟢 Чудовий результат!",
        "score_badge_mid": "🟡 Непогано, є куди рости",
        "score_badge_low": "🔴 Варто звернути увагу на режим",
        "onboarding_welcome": "Привіт, {name}! 👋🌙\n\nЛаскаво просимо до **AI Sleep Assistant**!\n\n🔹 **Крок 1 з 5:** Оберіть зручну мову спілкування:",
        "onboarding_course_ready": "✨ **ШІ сформував ваш Персональний 7-Денний Курс Сну!**",
        "onboarding_profile_analysis": "📊 **Аналіз вашого профілю:**",
        "onboarding_cat": "• Категорія: **{age}**",
        "onboarding_goal": "• Мета: **{goal}**",
        "onboarding_dis": "• Головна перешкода: **{dis}**",
        "onboarding_program": "🎯 **Згенерована персоналізована програма:**",
        "onboarding_locked": "🔒 **Доступ закритий.** Без оплати пройти ваш персональний курс неможливо.\nЩоб відкрити всі 7 днів уроків, трекер сну, ШІ-консультанта та чек-лист, придбайте доступ.",
        "onboarding_price": "🏷️ **Вартість курсу:** **99 грн** *(одноразовий платіж • доступ назавжди)*",
        "all_locked": "🔒 **Усі функції заблоковано до оплати.** Скористайтеся меню нижче:",
        "result_title": "🧠 **Ваш профіль сну**",
        "result_score_note": "_Оцінка сформована з ваших відповідей. Вона оновлюватиметься після кожної записаної ночі._",
        "result_main_problem": "🔴 **Головна проблема:**\n",
        "result_second_problem": "🟡 **Друга проблема:**\n",
        "result_good_title": "🟢 **Що вже добре:**\n",
        "result_means_title": "**Що це означає**",
        "result_means_low": "У вашому сні є кілька зон, які можна покращити. Більшість проблем сну вирішується зміною звичок — саме на цьому зосереджений ваш план.",
        "result_means_mid": "Ваш сон непоганий, але є куди рости. Невеликі корективи режиму можуть помітно покращити самопочуття.",
        "result_means_high": "Ваш сон уже сильний. Далі — закріпити результат і зробити його стабільним.",
        "result_plan": "🎯 **Ваш план:** спати **{duration} год**, лягати о **{bedtime}**, вставати о **{waketime}**",
        "result_advice_title": "💡 **Базова рекомендація:**\n",
        "prob_duration": "Недостатня тривалість сну",
        "prob_bedtime": "Пізній час засинання",
        "prob_waketime": "Пізній / нерегулярний час підйому",
        "prob_dis_phone": "Телефон або екрани перед сном",
        "prob_dis_coffee": "Кофеїн у другій половині дня",
        "prob_dis_stress": "Стрес і тривожність перед сном",
        "prob_dis_food": "Пізня важка їжа",
        "prob_dis_noise": "Шум або незручні умови для сну",
        "prob_default": "стабільність режиму",
        "good_duration": "Тривалість сну близька до норми",
        "good_bedtime": "Час засинання близький до оптимального",
        "good_waketime": "Ранній і регулярний підйом",
        "good_no_disruptor": "Немає явних перешкод для сну",
        "advice_duration": "Спробуйте додати 30–60 хв сну: лягайте на 15 хв раніше щодня цього тижня.",
        "advice_bedtime": "Зсувайте час засинання на 15 хв раніше кожні 2–3 дні.",
        "advice_waketime": "Вставайте в один і той самий час, навіть у вихідні — це стабілізує біоритм.",
        "advice_dis_phone": "Приберіть екрани за 45–60 хв до сну — це швидко покращує засинання.",
        "advice_dis_coffee": "Спробуйте останню каву за 6–8 годин до сну.",
        "advice_dis_stress": "Спробуйте «хвилину тиші»: виписуйте думки в нотатки за 30 хв до сну.",
        "advice_dis_food": "Вечеряйте за 2,5–3 години до сну, без важкої їжі.",
        "advice_dis_noise": "Зробіть спальню темною, тихою та прохолодною (18–20 °C).",
        "cta_see_plan": "✨ Побачити мій персональний план",
        "preview_title": "🔒 **Ваш персональний 7-денний план**",
        "preview_day_locked": "🔒 {title}",
        "preview_unlock_hint": "Це лише перший день. Повний план — із практичними вправами на кожен день — відкривається в Premium.",
        "cta_unlock": "🔓 Розблокувати повний план",
        "paywall_headline_low": "Ваш сон можна покращити.",
        "paywall_headline_mid": "Ваш сон непоганий — але може бути кращим.",
        "paywall_headline_high": "Ваш сон уже міцний — зробимо його ще кращим.",
        "paywall_score": "Ваш Score: **{score}/100**",
        "paywall_opportunity": "Найбільша можливість: **{problem}**",
        "paywall_solution": "Premium дає вам персональний 7-денний план, щоб працювати саме над цим.",
        "paywall_benefits_title": "**Що ви отримаєте:**",
        "benefit_analysis": "🔬 **Повний аналіз сну** — детальний розбір кожної ночі саме для вас",
        "benefit_coach": "🤖 **AI Sleep Coach** — персональні поради на основі ваших записів сну",
        "benefit_course": "📅 **7-денний план** — покрокова програма під вашу головну проблему",
        "benefit_habits": "⏰ **Цілі та нагадування** — формуйте здорову звичку без зусиль",
        "benefit_stats": "📊 **Статистика, тренди та досягнення** — бачте прогрес тиждень за тижнем",
        "paywall_trust": "Побудовано навколо ваших даних сну • Персоналізовано під ваш режим",
        "cta_start": "🚀 Почати покращувати мій сон",
        "prem_unlocked": "🎉 **Premium активовано!**",
        "prem_now_title": "Ось що вам тепер доступно:",
        "prem_item_analysis": "1️⃣ **Персональний аналіз** — розуміння ваших ночей",
        "prem_item_coach": "2️⃣ **AI Sleep Coach** — консультації у будь-який момент",
        "prem_item_course": "3️⃣ **7-денний курс** — ваш персональний план",
        "prem_item_goals": "4️⃣ **Цілі та нагадування** — звичка, яка тримається",
        "prem_item_stats": "5️⃣ **Повна статистика** — тренди, досягнення, серії",
        "cta_day1": "🚀 Розпочати День 1",
        "prem_menu_hint": "✅ Готово! Оберіть розділ меню:",
        "slept_duration": "⏱️ Ви проспали **{duration}** ({bedtime} - {waketime})\n\n",
        "sleep_quality_label": "😴 Якість: **{quality}**",
        "sleep_wakeups_label": "🌙 Пробуджень: **{wakeups}**",
        "factor_caffeine": "☕ Кофеїн",
        "factor_caffeine_on": "✅ ☕ Кофеїн",
        "factor_screens": "📱 Телефон",
        "factor_screens_on": "✅ 📱 Телефон",
        "factor_nap": "😴 Денний сон",
        "factor_nap_on": "✅ 😴 Денний сон",
        "wakeups_0": "0 разів",
        "wakeups_1": "1 раз",
        "wakeups_2": "2 рази",
        "wakeups_3": "3+ рази",
        "log_not_found": "Запис не знайдено. Почніть новий запис.",
        "invalid_value": "⚠️ Некоректне значення",
        "score_line": "🌙 **Sleep Score: {score}/100**",
        "profile_level_line": "🏆 Рівень: **{level}** | XP: **{xp}** | 🔥 Серія: **{streak}** дн.",
        "back": "🔙 Назад",
        "rem_tz_line": "🌍 Часовий пояс: **{zone}**",
        "invalid_type": "⚠️ Некоректний тип",
        "invalid_data": "⚠️ Некоректні дані",
        "invalid_time": "⚠️ Некоректний час",
        "course_title_premium": "👑 **Ваш Персональний 7-Денний Курс Сну**",
        "course_progress": "📊 Ваш прогрес: **{count}/7 днів** ({percent}%)",
        "course_unlocked": "🔓 Відкрито днів: **{count}/7**",
        "course_intro": "Курс відкривається поступово — наступний день стає доступним після завершення попереднього. Оберіть доступний день:",
        "course_locked_wait": "🔒 День {day} (через {wait} дн.)",
        "course_locked_prev": "🔒 День {day} (завершіть День {prev})",
        "course_mark_done": "✅ Позначити день пройденим",
        "course_mark_undo": "🎉 Урок пройдено! (Скасувати)",
        "course_back_list": "🔙 До списку уроків",
        "course_day_undone": "↩️ Позначку Дня {day} скасовано.",
        "course_day_done": "🎉 Вітаємо! День {day} успішно пройдено!",
        "course_locked_msg": "🔒 Цей день ще закритий. Нові дні відкриваються після завершення попереднього дня курсу.",
        "course_stale_btn": "⚠️ Застаріла кнопка. Відкрийте курс заново.",
        "course_not_open": "🔒 Цей день ще не відкрито. Завершіть попередній день курсу.",
        "goal_hours": "{value} год",
        "ai_thinking_q": "🤖 **ШІ обдумає ваше запитання... ⏳**",
        "ai_advisor_prefix": "🤖 **ШІ-Консультант:**\n\n",
        "course_fb_1": "☀️ День 1: Світловий біохакінг & нейтралізація «{dis}»",
        "course_fb_2": "🧘 День 2: Техніка US Navy (засинання за 120 секунд)",
        "course_fb_3": "🫁 День 3: Дихальна формула 4-7-8 проти кортизолу",
        "course_fb_4": "☕ День 4: Кофеїнове вікно & вечірні перекуси",
        "course_fb_5": "📝 День 5: «Коробка тривог» та правило 20 хвилин",
        "course_fb_6": "❄️ День 6: Мікроклімат спальні під мету «{goal}»",
        "course_fb_7": "📜 День 7: Ваш персональний вечірній ритуал",
        "onboarding_ai_loading": "🧠 **ШІ аналізує ваші відповіді...**\n<i>Складаємо для вас Персональний 7-Денний Курс Сну під категорію «{age}» та перешкоду «{dis}»...</i>",
        "rem_open_time": "⏰ Час: **{time}**\n\nОберіть дію:"
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
        "locked_menu_hint": "🔒 The menu below is available before payment:",
        # === TRIAL ===
        "trial_offer_title": "✨ **Try Premium for free!**",
        "trial_offer_what": "For {days} day you get:\n• AI Sleep Coach\n• Day 1 of your personal course\n• Goals & reminders\n• Full statistics",
        "trial_offer_note": "Your data and progress are saved.",
        "trial_offer_no_auto": "After the trial ends, Premium won't renew automatically — no auto-charges.",
        "cta_try": "✨ Try Premium",
        "trial_activated": "🎉 **Premium Trial activated!**",
        "trial_now_title": "Here's what you can do now:",
        "trial_ends_on": "⏳ Trial ends: **{date}**",
        "trial_ended": "⏳ **Your Premium trial has ended.**\n\nYour data and progress are saved. Nothing is lost.",
        "trial_already_used": "⚠️ You've already used your free trial.",
        "trial_back_hint": "🔙 Back to options",
        "trial_keyboard_hint": "✅ Updated! Choose a menu section:",
        # === AI COACH ===
        "ai_coach_welcome": "🧠 **AI Sleep Coach**\n\nAsk me about your sleep — tap a suggestion or type your own question:",
        "ai_q_score": "Why is my Score low?",
        "ai_q_tonight": "How can I improve my sleep tonight?",
        "ai_q_7days": "Analyze my last 7 days",
        "ai_q_first": "What should I change first?",
        # === SUPPORT ===
        "btn_support": "💬 Support",
        "support_title": "💬 **Support**\n\nHow can we help?",
        "support_cat_bug": "🐛 Report a problem",
        "support_cat_payment": "💳 Payment problem",
        "support_cat_question": "❓ Ask a question",
        "support_ask_message": "✍️ **{category}**\n\nDescribe your issue. We usually reply within a few hours:",
        "support_received": "✅ **Your message has been sent to support.**",
        "support_back_hint": "✅ Done! Choose a menu section:",
        "welcome_back": "👋 Welcome back! Your profile is already set up. Choose an action:",
        "btn_stats": "📊 Statistics",
        "btn_goals": "🎯 Goals",
        "btn_reminders": "⏰ Reminders",
        "btn_achievements": "🏆 Achievements",
        "ask_quality": "😴 How would you rate your **sleep quality** from 1 to 10?\n*(1 — terrible, 10 — perfect)*",
        "ask_wakeups": "🌙 How many times did you **wake up at night**?",
        "ask_factors": "📋 What happened **before sleep**? Tap the buttons to mark:\n\n☕ **Caffeine** — coffee/tea/energy drink after 6 PM\n📱 **Phone** — screens in bed before sleep\n😴 **Daytime nap** — slept during the day",
        "factors_done": "✅ Done",
        "skip_btn": "⏭ Skip",
        "score_title": "🌙 **Sleep Score:** **{score}/100**",
        "score_good": "✅ **What went well:**\n{items}",
        "score_bad": "⚠️ **What hurt the result:**\n{items}",
        "score_tips": "💡 **What you can improve today:**\n{items}",
        "duration_ok": "duration is within the norm",
        "duration_low": "sleep shorter than the norm",
        "tip_duration": "go to bed 30 min earlier to get more sleep",
        "quality_ok": "high sleep quality",
        "quality_low": "low sleep quality",
        "wakeups_ok": "slept without wake-ups",
        "wakeups_many": "frequent wake-ups",
        "tip_wakeups": "try the 4-7-8 breathing technique before bed",
        "bedtime_ok": "bedtime close to the goal",
        "bedtime_late": "late bedtime",
        "tip_bedtime": "gradually shift bedtime 15 min earlier each night",
        "waketime_ok": "wake time close to the goal",
        "waketime_late": "late wake-up",
        "caffeine_bad": "evening caffeine",
        "tip_caffeine": "no caffeine 6-8 hours before bed",
        "screens_bad": "phone before bed",
        "tip_screens": "put away screens 45 min before bed",
        "stats_title": "📊 **Sleep statistics — last {days} days**",
        "stats_count": "📝 Entries: **{count}**",
        "avg_duration": "⏱ Average duration: **{value}**",
        "avg_score": "🌙 Average Sleep Score: **{value}/100**",
        "avg_bedtime": "🌅 Average bedtime: **{value}**",
        "avg_waketime": "☀️ Average wake time: **{value}**",
        "best_day": "🏅 Best day: **{date}** ({score}/100)",
        "worst_day": "🧱 Worst day: **{date}** ({score}/100)",
        "stability": "📈 Schedule stability: **{value}**",
        "stability_high": "high 🟢",
        "stability_medium": "medium 🟡",
        "stability_low": "low 🔴",
        "no_data": "😴 Not enough entries for analysis yet. Log your sleep daily and stats will appear!",
        "patterns_title": "🔍 **Patterns found:**",
        "pattern_late_bedtime": "On days you go to bed later than the goal, Sleep Score is on average {diff} points lower",
        "pattern_caffeine": "On days with evening caffeine, Score is on average {diff} points lower",
        "pattern_screens": "On days with phone before bed, Score is on average {diff} points lower",
        "pattern_wakeups": "On nights with wake-ups (2+), Score is on average {diff} points lower",
        "rec_title": "💡 **Personal recommendations:**",
        "rec_duration": "💤 Sleep is shorter than the norm on average. Add 30-60 min to your sleep time each evening",
        "rec_bedtime": "🌙 You go to bed later than the goal. Shift bedtime 15 min earlier every 2 days",
        "rec_waketime": "☀️ Wake time is unstable. Wake up at the same time even on weekends",
        "rec_screens": "📱 Phone before bed too often. Turn off screens 45 min before bed — it will raise your Score",
        "rec_caffeine": "☕ Evening caffeine too often. Last coffee 6-8 hours before bed",
        "rec_wakeups": "🌙 Frequent night wake-ups. Try an evening routine: 4-7-8 breathing and a cool bedroom",
        "rec_keep": "👏 You keep the routine! Continue and try to go to bed at the same time",
        "goals_title": "🎯 **Your sleep goals:**",
        "goals_body": "🌅 Bedtime: **{bedtime}**\n☀️ Wake time: **{waketime}**\n⏱ Sleep: **{duration} h**\n\n📊 **Progress over 7 days:**\n• Average bedtime: **{avg_bedtime}**\n• Average wake time: **{avg_waketime}**\n• Average duration: **{avg_duration}**",
        "goal_set_bedtime": "🌅 **Target bedtime.** Choose a time:",
        "goal_set_waketime": "☀️ **Target wake time.** Choose a time:",
        "goal_set_duration": "⏱ **Desired sleep duration.** Choose:",
        "goal_saved": "✅ Goal saved!",
        "goal_btn_bedtime": "Bedtime",
        "goal_btn_waketime": "Wake time",
        "goal_btn_duration": "Duration",
        "rem_tz_btn": "Time zone",
        "rem_title": "⏰ **Reminders**\n\nChoose a reminder to configure. Turn off the switch to disable it.",
        "rem_type_wind_down": "🌙 Wind-down",
        "rem_type_log": "📝 Log sleep",
        "rem_type_morning": "☀️ Morning",
        "rem_type_goal": "🎯 Target bedtime",
        "rem_on": "🟢 On",
        "rem_off": "⚪ Off",
        "rem_enabled": "✅ Enabled",
        "rem_disabled": "❌ Disabled",
        "rem_tz_title": "🌍 **Time zone.** Choose the offset from UTC:",
        "rem_tz_saved": "✅ Time zone saved: UTC{offset}",
        "rem_time_title": "⏰ Choose the reminder time:",
        "rem_time_saved": "✅ Reminder time: **{time}**",
        "rem_wind_down": "🌙 **Time to wind down!**\n\nOne hour before bed:\n1️⃣ Dim the lights, put away screens\n2️⃣ Air out the bedroom\n3️⃣ Do the 4-7-8 breathing practice",
        "rem_log": "📝 **How was your night?**\nIf you haven't logged your sleep yet — press '☀️ I woke up' in the menu. 🌙",
        "rem_morning": "☀️ **Good morning!**\nSpend 10 minutes in daylight — it resets your circadian rhythm. And don't forget to log your sleep!",
        "rem_goal": "🎯 **Time to go to bed according to your goal!**\nGood night, sleep well! 🌙",
        "ach_title": "🏆 **Achievements**\n\n⭐ Level: **{level}** | XP: **{xp}**\n📈 Progress to level {next}: **{progress}%**\n🔥 Streak: **{streak}** days\n\nAchievements:",
        "ach_first_log": "🏆 First sleep log",
        "ach_streak_3": "🔥 3 days in a row",
        "ach_streak_7": "🔥 7 days in a row",
        "ach_nights_8h_5": "🌙 5 nights with 8+ hours",
        "ach_score_90": "⭐ Sleep Score 90+",
        "ach_score_80_3": "💎 3 days with Score 80+",
        "ach_early_5": "🌅 5 early wake-ups",
        "ach_no_phone_3": "📵 3 nights without phone",
        "ach_new": "🎉 **New achievement:** {achievement}!",
        "level_up": "⬆️ **New level {level}!** Keep it up!",
        "unknown_msg": "🤔 I don't understand this message. Use the menu buttons below:",
        "step_duration": "🔹 **How many hours do you usually sleep?**",
        "step_problem": "🔹 **What most often disrupts your sleep?**",
        "onboarding_done": "🎉 **Your personal plan is ready!**\n\n⏱ Target sleep: **{duration} h**\n🌅 Desired bedtime: **{bedtime}**\n☀️ Desired wake time: **{waketime}**\n\nNext, AI will build your personal 7-day sleep improvement course. 🧠",
        "score_badge_high": "🟢 Great result!",
        "score_badge_mid": "🟡 Not bad, room to grow",
        "score_badge_low": "🔴 Worth paying attention to your routine",
        "onboarding_welcome": "Hi, {name}! 👋🌙\n\nWelcome to **AI Sleep Assistant**!\n\n🔹 **Step 1 of 5:** Please select your preferred language:",
        "onboarding_course_ready": "✨ **AI has created your Personal 7-Day Sleep Course!**",
        "onboarding_profile_analysis": "📊 **Your profile analysis:**",
        "onboarding_cat": "• Category: **{age}**",
        "onboarding_goal": "• Goal: **{goal}**",
        "onboarding_dis": "• Main disruptor: **{dis}**",
        "onboarding_program": "🎯 **Your generated personalized program:**",
        "onboarding_locked": "🔒 **Access is locked.** Without payment, you cannot take your personal course.\nTo unlock all 7 days of lessons, the sleep tracker, the AI advisor and the checklist, buy access.",
        "onboarding_price": "🏷️ **Course price:** **99 UAH** *(one-time payment • lifetime access)*",
        "all_locked": "🔒 **All features are locked until payment.** Use the menu below:",
        "result_title": "🧠 **Your sleep profile**",
        "result_score_note": "_Score is based on your answers. It will update with every logged night._",
        "result_main_problem": "🔴 **Main problem:**\n",
        "result_second_problem": "🟡 **Second problem:**\n",
        "result_good_title": "🟢 **What's already going well:**\n",
        "result_means_title": "**What this means**",
        "result_means_low": "Your sleep has several areas that can be improved. Most sleep issues are solved by changing habits — and that's exactly what your plan focuses on.",
        "result_means_mid": "Your sleep is okay, but there is room for improvement. Small schedule tweaks can noticeably improve how you feel.",
        "result_means_high": "Your sleep is already strong. Next step: keep the result and make it consistent.",
        "result_plan": "🎯 **Your plan:** sleep **{duration} h**, go to bed at **{bedtime}**, wake up at **{waketime}**",
        "result_advice_title": "💡 **Basic recommendation:**\n",
        "prob_duration": "Not enough sleep duration",
        "prob_bedtime": "Late bedtime",
        "prob_waketime": "Late / irregular wake-up time",
        "prob_dis_phone": "Phone or screens before bed",
        "prob_dis_coffee": "Caffeine in the afternoon",
        "prob_dis_stress": "Stress and anxiety before bed",
        "prob_dis_food": "Late heavy meals",
        "prob_dis_noise": "Noise or uncomfortable sleep conditions",
        "prob_default": "sleep consistency",
        "good_duration": "Sleep duration is close to the norm",
        "good_bedtime": "Bedtime is close to optimal",
        "good_waketime": "Early and regular wake-up",
        "good_no_disruptor": "No major sleep disruptors",
        "advice_duration": "Try adding 30–60 min of sleep: go to bed 15 min earlier each day this week.",
        "advice_bedtime": "Shift your bedtime 15 min earlier every 2–3 days.",
        "advice_waketime": "Wake up at the same time, even on weekends — it stabilizes your rhythm.",
        "advice_dis_phone": "Put screens away 45–60 min before bed — it improves falling asleep quickly.",
        "advice_dis_coffee": "Try your last coffee 6–8 hours before bed.",
        "advice_dis_stress": "Try a \"quiet minute\": write your thoughts in notes 30 min before bed.",
        "advice_dis_food": "Have dinner 2.5–3 hours before bed, avoid heavy meals.",
        "advice_dis_noise": "Make your bedroom dark, quiet and cool (18–20 °C).",
        "cta_see_plan": "✨ See my personalized plan",
        "preview_title": "🔒 **Your personalized 7-day plan**",
        "preview_day_locked": "🔒 {title}",
        "preview_unlock_hint": "That's just day one. The full plan — with practical exercises for each day — unlocks with Premium.",
        "cta_unlock": "🔓 Unlock my full plan",
        "paywall_headline_low": "Your sleep can improve.",
        "paywall_headline_mid": "Your sleep is okay — but it can be better.",
        "paywall_headline_high": "Your sleep is already strong — let's make it even better.",
        "paywall_score": "Your score: **{score}/100**",
        "paywall_opportunity": "Your biggest opportunity: **{problem}**",
        "paywall_solution": "Premium gives you a personalized 7-day plan to work on it.",
        "paywall_benefits_title": "**What you get:**",
        "benefit_analysis": "🔬 **Full sleep analysis** — a detailed breakdown of each night, just for you",
        "benefit_coach": "🤖 **AI Sleep Coach** — personal advice based on your sleep logs",
        "benefit_course": "📅 **7-day plan** — a step-by-step program for your main problem",
        "benefit_habits": "⏰ **Goals & reminders** — build a healthy habit without effort",
        "benefit_stats": "📊 **Statistics, trends & achievements** — see progress week by week",
        "paywall_trust": "Built around your sleep data • Personalized to your schedule",
        "cta_start": "🚀 Start improving my sleep",
        "prem_unlocked": "🎉 **Premium unlocked!**",
        "prem_now_title": "Here's what you can do now:",
        "prem_item_analysis": "1️⃣ **Personal analysis** — understand your nights",
        "prem_item_coach": "2️⃣ **AI Sleep Coach** — advice any time you need it",
        "prem_item_course": "3️⃣ **7-day course** — your personal plan",
        "prem_item_goals": "4️⃣ **Goals & reminders** — a habit that sticks",
        "prem_item_stats": "5️⃣ **Full statistics** — trends, achievements, streaks",
        "cta_day1": "🚀 Start Day 1",
        "prem_menu_hint": "✅ Done! Choose a menu section:",
        "slept_duration": "⏱️ You slept **{duration}** ({bedtime} - {waketime})\n\n",
        "sleep_quality_label": "😴 Quality: **{quality}**",
        "sleep_wakeups_label": "🌙 Wake-ups: **{wakeups}**",
        "factor_caffeine": "☕ Caffeine",
        "factor_caffeine_on": "✅ ☕ Caffeine",
        "factor_screens": "📱 Phone",
        "factor_screens_on": "✅ 📱 Phone",
        "factor_nap": "😴 Daytime nap",
        "factor_nap_on": "✅ 😴 Daytime nap",
        "wakeups_0": "0 times",
        "wakeups_1": "1 time",
        "wakeups_2": "2 times",
        "wakeups_3": "3+ times",
        "log_not_found": "Log not found. Start a new log.",
        "invalid_value": "⚠️ Invalid value",
        "score_line": "🌙 **Sleep Score: {score}/100**",
        "profile_level_line": "🏆 Level: **{level}** | XP: **{xp}** | 🔥 Streak: **{streak}** days",
        "back": "🔙 Back",
        "rem_tz_line": "🌍 Time zone: **{zone}**",
        "invalid_type": "⚠️ Invalid type",
        "invalid_data": "⚠️ Invalid data",
        "invalid_time": "⚠️ Invalid time",
        "course_title_premium": "👑 **Your Personal 7-Day Sleep Course**",
        "course_progress": "📊 Your progress: **{count}/7 days** ({percent}%)",
        "course_unlocked": "🔓 Unlocked days: **{count}/7**",
        "course_intro": "The course unlocks gradually — the next day becomes available after you complete the previous one. Choose an available day:",
        "course_locked_wait": "🔒 Day {day} (in {wait} days)",
        "course_locked_prev": "🔒 Day {day} (complete Day {prev})",
        "course_mark_done": "✅ Mark the day as completed",
        "course_mark_undo": "🎉 Lesson completed! (Undo)",
        "course_back_list": "🔙 Back to lessons",
        "course_day_undone": "↩️ Day {day} completion undone.",
        "course_day_done": "🎉 Congratulations! Day {day} completed successfully!",
        "course_locked_msg": "🔒 This day is still locked. New days unlock after you complete the previous day of the course.",
        "course_stale_btn": "⚠️ Stale button. Open the course again.",
        "course_not_open": "🔒 This day is not unlocked yet. Complete the previous day of the course.",
        "goal_hours": "{value} h",
        "ai_thinking_q": "🤖 **AI is thinking about your question... ⏳**",
        "ai_advisor_prefix": "🤖 **AI Advisor:**\n\n",
        "course_fb_1": "☀️ Day 1: Light Biohacking & neutralizing «{dis}»",
        "course_fb_2": "🧘 Day 2: US Navy Technique (sleep in 120 seconds)",
        "course_fb_3": "🫁 Day 3: 4-7-8 Breathing Formula against cortisol",
        "course_fb_4": "☕ Day 4: Caffeine Window & evening snacks",
        "course_fb_5": "📝 Day 5: 'Worry Box' & the 20-minute rule",
        "course_fb_6": "❄️ Day 6: Bedroom microclimate for the goal «{goal}»",
        "course_fb_7": "📜 Day 7: Your personal evening ritual",
        "onboarding_ai_loading": "🧠 **AI is analyzing your answers...**\n<i>Building your Personal 7-Day Sleep Course for the category «{age}» and disruptor «{dis}»...</i>",
        "rem_open_time": "⏰ Time: **{time}**\n\nChoose an action:"
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
        "locked_menu_hint": "🔒 Меню ниже доступно до оплаты:",
        "welcome_back": "👋 С возвращением! Ваш профиль уже настроен. Выберите действие:",
        "btn_stats": "📊 Статистика",
        "btn_goals": "🎯 Цели",
        "btn_reminders": "⏰ Напоминания",
        "btn_achievements": "🏆 Достижения",
        "ask_quality": "😴 Как вы оцените **качество сна** от 1 до 10?\n*(1 — ужасно, 10 — идеально)*",
        "ask_wakeups": "🌙 Сколько раз вы **просыпались ночью**?",
        "ask_factors": "📋 Что было **перед сном**? Нажимайте кнопки, чтобы отметить:\n\n☕ **Кофеин** — кофе/чай/энергетик после 18:00\n📱 **Телефон** — экраны в кровати перед сном\n😴 **Дневной сон** — спали днём",
        "factors_done": "✅ Готово",
        "skip_btn": "⏭ Пропустить",
        "score_title": "🌙 **Sleep Score:** **{score}/100**",
        "score_good": "✅ **Что хорошо:**\n{items}",
        "score_bad": "⚠️ **Что ухудшило результат:**\n{items}",
        "score_tips": "💡 **Что можно улучшить сегодня:**\n{items}",
        "duration_ok": "длительность в норме",
        "duration_low": "сон короче нормы",
        "tip_duration": "лечь на 30 мин раньше, чтобы увеличить сон",
        "quality_ok": "высокое качество сна",
        "quality_low": "низкое качество сна",
        "wakeups_ok": "сон без пробуждений",
        "wakeups_many": "частые пробуждения",
        "tip_wakeups": "попробовать дыхательную практику 4-7-8 перед сном",
        "bedtime_ok": "время засыпания близко к цели",
        "bedtime_late": "позднее засыпание",
        "tip_bedtime": "постепенно сдвигать засыпание на 15 мин раньше каждый вечер",
        "waketime_ok": "время подъёма близко к цели",
        "waketime_late": "поздний подъём",
        "caffeine_bad": "кофеин вечером",
        "tip_caffeine": "без кофеина за 6-8 часов до сна",
        "screens_bad": "телефон перед сном",
        "tip_screens": "убрать экраны за 45 мин до сна",
        "stats_title": "📊 **Статистика сна — последние {days} дней**",
        "stats_count": "📝 Записей: **{count}**",
        "avg_duration": "⏱ Средняя длительность: **{value}**",
        "avg_score": "🌙 Средний Sleep Score: **{value}/100**",
        "avg_bedtime": "🌅 Среднее время засыпания: **{value}**",
        "avg_waketime": "☀️ Среднее время подъёма: **{value}**",
        "best_day": "🏅 Лучший день: **{date}** ({score}/100)",
        "worst_day": "🧱 Худший день: **{date}** ({score}/100)",
        "stability": "📈 Стабильность режима: **{value}**",
        "stability_high": "высокая 🟢",
        "stability_medium": "средняя 🟡",
        "stability_low": "низкая 🔴",
        "no_data": "😴 Пока недостаточно записей для анализа. Записывайте сон каждый день — и статистика появится!",
        "patterns_title": "🔍 **Закономерности:**",
        "pattern_late_bedtime": "В дни, когда вы ложитесь позже цели, Sleep Score в среднем на {diff} баллов ниже",
        "pattern_caffeine": "В дни с кофеином вечером Score в среднем на {diff} баллов ниже",
        "pattern_screens": "В дни с телефоном перед сном Score в среднем на {diff} баллов ниже",
        "pattern_wakeups": "В ночи с пробуждениями (2+) Score в среднем на {diff} баллов ниже",
        "rec_title": "💡 **Персональные рекомендации:**",
        "rec_duration": "💤 Сон в среднем короче нормы. Добавьте 30-60 минут ко времени сна каждый вечер",
        "rec_bedtime": "🌙 Вы ложитесь позже цели. Сдвигайте засыпание на 15 мин раньше каждые 2 дня",
        "rec_waketime": "☀️ Время подъёма нестабильно. Вставайте в одно и то же время даже в выходные",
        "rec_screens": "📱 Часто телефон перед сном. Выключите экраны за 45 мин до сна — это поднимет Score",
        "rec_caffeine": "☕ Часто кофеин вечером. Последний кофе — за 6-8 часов до сна",
        "rec_wakeups": "🌙 Частые пробуждения ночью. Попробуйте вечерний ритуал: дыхание 4-7-8 и прохладная спальня",
        "rec_keep": "👏 Вы держите режим! Продолжайте и старайтесь ложиться в одно и то же время",
        "goals_title": "🎯 **Ваши цели сна:**",
        "goals_body": "🌅 Ложиться: **{bedtime}**\n☀️ Вставать: **{waketime}**\n⏱ Сон: **{duration} ч**\n\n📊 **Прогресс за 7 дней:**\n• Среднее время засыпания: **{avg_bedtime}**\n• Среднее время подъёма: **{avg_waketime}**\n• Средняя длительность: **{avg_duration}**",
        "goal_set_bedtime": "🌅 **Целевое время засыпания.** Выберите время:",
        "goal_set_waketime": "☀️ **Целевое время подъёма.** Выберите время:",
        "goal_set_duration": "⏱ **Желаемая длительность сна.** Выберите:",
        "goal_saved": "✅ Цель сохранена!",
        "goal_btn_bedtime": "Время сна",
        "goal_btn_waketime": "Подъём",
        "goal_btn_duration": "Длительность",
        "rem_tz_btn": "Часовой пояс",
        "rem_title": "⏰ **Напоминания**\n\nВыберите напоминание для настройки. Чтобы отключить — выключите переключатель.",
        "rem_type_wind_down": "🌙 Подготовка ко сну",
        "rem_type_log": "📝 Записать сон",
        "rem_type_morning": "☀️ Утреннее",
        "rem_type_goal": "🎯 Целевое время сна",
        "rem_on": "🟢 Вкл",
        "rem_off": "⚪ Выкл",
        "rem_enabled": "✅ Включено",
        "rem_disabled": "❌ Выключено",
        "rem_tz_title": "🌍 **Часовой пояс.** Выберите смещение относительно UTC:",
        "rem_tz_saved": "✅ Часовой пояс сохранён: UTC{offset}",
        "rem_time_title": "⏰ Выберите время напоминания:",
        "rem_time_saved": "✅ Время напоминания: **{time}**",
        "rem_wind_down": "🌙 **Время готовиться ко сну!**\n\nЗа час до сна:\n1️⃣ Приглушите свет, уберите экраны\n2️⃣ Проветрите спальню\n3️⃣ Сделайте дыхательную практику 4-7-8",
        "rem_log": "📝 **Как прошла ночь?**\nЕсли вы ещё не записали сон — нажмите «☀️ Я проснулся» в меню. 🌙",
        "rem_morning": "☀️ **Доброе утро!**\nПроведите 10 минут на свету — это запускает биоритмы. И не забудьте записать свой сон!",
        "rem_goal": "🎯 **Время ложиться спать согласно вашей цели!**\nСпокойной ночи! 🌙",
        "ach_title": "🏆 **Достижения**\n\n⭐ Уровень: **{level}** | XP: **{xp}**\n📈 Прогресс до уровня {next}: **{progress}%**\n🔥 Серия дней: **{streak}**\n\nДостижения:",
        "ach_first_log": "🏆 Первая запись сна",
        "ach_streak_3": "🔥 3 дня подряд",
        "ach_streak_7": "🔥 7 дней подряд",
        "ach_nights_8h_5": "🌙 5 ночей с 8+ часами",
        "ach_score_90": "⭐ Sleep Score 90+",
        "ach_score_80_3": "💎 3 дня со Score 80+",
        "ach_early_5": "🌅 5 ранних подъёмов",
        "ach_no_phone_3": "📵 3 ночи без телефона",
        "ach_new": "🎉 **Новое достижение:** {achievement}!",
        "level_up": "⬆️ **Новый уровень {level}!** Продолжайте в том же духе!",
        "unknown_msg": "🤔 Я не понимаю это сообщение. Воспользуйтесь кнопками меню ниже:",
        "step_duration": "🔹 **Сколько часов вы обычно спите?**",
        "step_problem": "🔹 **Что чаще всего мешает вам спать?**",
        "onboarding_done": "🎉 **Ваш персональный план готов!**\n\n⏱ Целевой сон: **{duration} ч**\n🌅 Желаемое время сна: **{bedtime}**\n☀️ Желаемый подъём: **{waketime}**\n\nДалее ИИ составит для вас персональный 7-дневный курс улучшения сна. 🧠",
        "score_badge_high": "🟢 Отличный результат!",
        "score_badge_mid": "🟡 Неплохо, есть куда расти",
        "score_badge_low": "🔴 Стоит обратить внимание на режим",
        "onboarding_welcome": "Привет, {name}! 👋🌙\n\nДобро пожаловать в **AI Sleep Assistant**!\n\n🔹 **Шаг 1 из 5:** Выберите удобный язык общения:",
        "onboarding_course_ready": "✨ **ИИ сформировал ваш Персональный 7-Дневный Курс Сна!**",
        "onboarding_profile_analysis": "📊 **Анализ вашего профиля:**",
        "onboarding_cat": "• Категория: **{age}**",
        "onboarding_goal": "• Цель: **{goal}**",
        "onboarding_dis": "• Главная помеха: **{dis}**",
        "onboarding_program": "🎯 **Сгенерированная персонализированная программа:**",
        "onboarding_locked": "🔒 **Доступ закрыт.** Без оплаты пройти ваш персональный курс невозможно.\nЧтобы открыть все 7 дней уроков, трекер сна, ИИ-консультанта и чек-лист, приобретите доступ.",
        "onboarding_price": "🏷️ **Стоимость курса:** **99 грн** *(разовый платёж • доступ навсегда)*",
        "all_locked": "🔒 **Все функции заблокированы до оплаты.** Воспользуйтесь меню ниже:",
        "result_title": "🧠 **Ваш профиль сна**",
        "result_score_note": "_Оценка сформирована из ваших ответов. Она будет обновляться после каждой записанной ночи._",
        "result_main_problem": "🔴 **Главная проблема:**\n",
        "result_second_problem": "🟡 **Вторая проблема:**\n",
        "result_good_title": "🟢 **Что уже хорошо:**\n",
        "result_means_title": "**Что это значит**",
        "result_means_low": "В вашем сне есть несколько зон, которые можно улучшить. Большинство проблем со сном решается изменением привычек — именно на этом сосредоточен ваш план.",
        "result_means_mid": "Ваш сон неплохой, но есть куда расти. Небольшие корректировки режима могут заметно улучшить самочувствие.",
        "result_means_high": "Ваш сон уже крепкий. Дальше — закрепить результат и сделать его стабильным.",
        "result_plan": "🎯 **Ваш план:** спать **{duration} ч**, ложиться в **{bedtime}**, вставать в **{waketime}**",
        "result_advice_title": "💡 **Базовая рекомендация:**\n",
        "prob_duration": "Недостаточная длительность сна",
        "prob_bedtime": "Позднее засыпание",
        "prob_waketime": "Поздний / нерегулярный подъём",
        "prob_dis_phone": "Телефон или экраны перед сном",
        "prob_dis_coffee": "Кофеин во второй половине дня",
        "prob_dis_stress": "Стресс и тревожность перед сном",
        "prob_dis_food": "Поздняя тяжёлая еда",
        "prob_dis_noise": "Шум или неудобные условия для сна",
        "prob_default": "стабильность режима",
        "good_duration": "Длительность сна близка к норме",
        "good_bedtime": "Время засыпания близко к оптимальному",
        "good_waketime": "Ранний и регулярный подъём",
        "good_no_disruptor": "Нет явных помех для сна",
        "advice_duration": "Попробуйте добавить 30–60 минут сна: ложитесь на 15 минут раньше каждый день на этой неделе.",
        "advice_bedtime": "Сдвигайте время засыпания на 15 минут раньше каждые 2–3 дня.",
        "advice_waketime": "Вставайте в одно и то же время, даже в выходные — это стабилизирует биоритм.",
        "advice_dis_phone": "Уберите экраны за 45–60 минут до сна — это быстро улучшает засыпание.",
        "advice_dis_coffee": "Попробуйте последний кофе за 6–8 часов до сна.",
        "advice_dis_stress": "Попробуйте «минуту тишины»: записывайте мысли в заметки за 30 минут до сна.",
        "advice_dis_food": "Ужинайте за 2,5–3 часа до сна, без тяжёлой еды.",
        "advice_dis_noise": "Сделайте спальню тёмной, тихой и прохладной (18–20 °C).",
        "cta_see_plan": "✨ Посмотреть мой персональный план",
        "preview_title": "🔒 **Ваш персональный 7-дневный план**",
        "preview_day_locked": "🔒 {title}",
        "preview_unlock_hint": "Это лишь первый день. Полный план — с практическими упражнениями на каждый день — открывается в Premium.",
        "cta_unlock": "🔓 Разблокировать полный план",
        "paywall_headline_low": "Ваш сон можно улучшить.",
        "paywall_headline_mid": "Ваш сон неплохой — но может быть лучше.",
        "paywall_headline_high": "Ваш сон уже крепкий — сделаем его ещё лучше.",
        "paywall_score": "Ваш Score: **{score}/100**",
        "paywall_opportunity": "Ваша главная возможность: **{problem}**",
        "paywall_solution": "Premium даёт вам персональный 7-дневный план, чтобы работать именно над этим.",
        "paywall_benefits_title": "**Что вы получите:**",
        "benefit_analysis": "🔬 **Полный анализ сна** — детальный разбор каждой ночи именно для вас",
        "benefit_coach": "🤖 **AI Sleep Coach** — персональные советы на основе ваших записей сна",
        "benefit_course": "📅 **7-дневный план** — пошаговая программа под вашу главную проблему",
        "benefit_habits": "⏰ **Цели и напоминания** — формируйте здоровую привычку без усилий",
        "benefit_stats": "📊 **Статистика, тренды и достижения** — видите прогресс неделя за неделей",
        "paywall_trust": "Построено вокруг ваших данных сна • Персонализировано под ваш режим",
        "cta_start": "🚀 Начать улучшать мой сон",
        "prem_unlocked": "🎉 **Premium активирован!**",
        "prem_now_title": "Вот что вам теперь доступно:",
        "prem_item_analysis": "1️⃣ **Персональный анализ** — понимание ваших ночей",
        "prem_item_coach": "2️⃣ **AI Sleep Coach** — консультации в любой момент",
        "prem_item_course": "3️⃣ **7-дневный курс** — ваш персональный план",
        "prem_item_goals": "4️⃣ **Цели и напоминания** — привычка, которая держится",
        "prem_item_stats": "5️⃣ **Полная статистика** — тренды, достижения, серии",
        "cta_day1": "🚀 Начать День 1",
        "prem_menu_hint": "✅ Готово! Выберите раздел меню:",
        "slept_duration": "⏱️ Вы проспали **{duration}** ({bedtime} - {waketime})\n\n",
        "sleep_quality_label": "😴 Качество: **{quality}**",
        "sleep_wakeups_label": "🌙 Пробуждений: **{wakeups}**",
        "factor_caffeine": "☕ Кофеин",
        "factor_caffeine_on": "✅ ☕ Кофеин",
        "factor_screens": "📱 Телефон",
        "factor_screens_on": "✅ 📱 Телефон",
        "factor_nap": "😴 Дневной сон",
        "factor_nap_on": "✅ 😴 Дневной сон",
        "wakeups_0": "0 раз",
        "wakeups_1": "1 раз",
        "wakeups_2": "2 раза",
        "wakeups_3": "3+ раза",
        "log_not_found": "Запись не найдена. Начните новую запись.",
        "invalid_value": "⚠️ Некорректное значение",
        "score_line": "🌙 **Sleep Score: {score}/100**",
        "profile_level_line": "🏆 Уровень: **{level}** | XP: **{xp}** | 🔥 Серия: **{streak}** дн.",
        "back": "🔙 Назад",
        "rem_tz_line": "🌍 Часовой пояс: **{zone}**",
        "invalid_type": "⚠️ Некорректный тип",
        "invalid_data": "⚠️ Некорректные данные",
        "invalid_time": "⚠️ Некорректное время",
        "course_title_premium": "👑 **Ваш Персональный 7-Дневный Курс Сна**",
        "course_progress": "📊 Ваш прогресс: **{count}/7 дней** ({percent}%)",
        "course_unlocked": "🔓 Открыто дней: **{count}/7**",
        "course_intro": "Курс открывается постепенно — следующий день становится доступным после завершения предыдущего. Выберите доступный день:",
        "course_locked_wait": "🔒 День {day} (через {wait} дн.)",
        "course_locked_prev": "🔒 День {day} (завершите День {prev})",
        "course_mark_done": "✅ Отметить день пройденным",
        "course_mark_undo": "🎉 Урок пройден! (Отменить)",
        "course_back_list": "🔙 К списку уроков",
        "course_day_undone": "↩️ Отметку Дня {day} отменено.",
        "course_day_done": "🎉 Поздравляем! День {day} успешно пройден!",
        "course_locked_msg": "🔒 Этот день ещё закрыт. Новые дни открываются после завершения предыдущего дня курса.",
        "course_stale_btn": "⚠️ Устаревшая кнопка. Откройте курс заново.",
        "course_not_open": "🔒 Этот день ещё не открыт. Завершите предыдущий день курса.",
        "goal_hours": "{value} ч",
        "ai_thinking_q": "🤖 **ИИ обдумает ваш вопрос... ⏳**",
        "ai_advisor_prefix": "🤖 **ИИ-Консультант:**\n\n",
        "course_fb_1": "☀️ День 1: Световой биохакинг & нейтрализация «{dis}»",
        "course_fb_2": "🧘 День 2: Техника US Navy (засыпание за 120 секунд)",
        "course_fb_3": "🫁 День 3: Дыхательная формула 4-7-8 против кортизола",
        "course_fb_4": "☕ День 4: Кофеиновое окно & вечерние перекусы",
        "course_fb_5": "📝 День 5: «Коробка тревог» и правило 20 минут",
        "course_fb_6": "❄️ День 6: Микроклимат спальни под цель «{goal}»",
        "course_fb_7": "📜 День 7: Ваш персональный вечерний ритуал",
        "onboarding_ai_loading": "🧠 **ИИ анализирует ваши ответы...**\n<i>Составляем для вас Персональный 7-Дневный Курс Сна под категорию «{age}» и помеху «{dis}»...</i>",
        "rem_open_time": "⏰ Время: **{time}**\n\nВыберите действие:"
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

# Розширений трекер: після пробудження користувач відповідає на кілька швидких питань
class SleepLogForm(StatesGroup):
    waiting_for_quality = State()
    waiting_for_wakeups = State()
    waiting_for_factors = State()

# Налаштування цілей / нагадувань через діалог
class SettingsForm(StatesGroup):
    waiting_for_bedtime = State()
    waiting_for_waketime = State()
    waiting_for_duration = State()
    waiting_for_rem_time = State()
    waiting_for_tz = State()

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
            # Резервна копія після кожного успішного запису (захист від пошкодження файлу)
            try:
                backup_path = DATA_FILE + ".bak"
                fd2, tmp2 = tempfile.mkstemp(prefix=".sleep_ai_bak_", suffix=".tmp", dir=dir_name)
                with os.fdopen(fd2, "w", encoding="utf-8") as f2:
                    json.dump(data, f2, ensure_ascii=False, indent=2)
                    f2.flush()
                    os.fsync(f2.fileno())
                os.replace(tmp2, backup_path)
            except Exception:
                pass
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
            "timezone": timeutil.DEFAULT_TIMEZONE,
            "age_group": "age_young",
            "usual_bedtime": "bt_normal",
            "usual_waketime": "wt_normal",
            "goal": "goal_quality",
            "disruptor": "dis_phone",
            "reminders_enabled": True,
            "reminders": {k: dict(v) for k, v in DEFAULT_REMINDERS.items() if isinstance(v, dict)},
            "active_sleep_start": None,
            "logs": [],
            "funnel": {},
            "achievements": [],
            "xp": 0,
            "trial_used": False,
            "trial_started_at": None,
            "trial_expires_at": None,
        }
        save_user_data(data)
    return data[uid]

def get_target_hours(profile):
    lang = profile.get("lang", "uk")
    age_key = profile.get("age_group", "age_young")
    age_info = AGE_GROUPS.get(lang, AGE_GROUPS["uk"]).get(age_key, AGE_GROUPS["uk"]["age_young"])
    return age_info.get("target_hours", 8.0)

def get_goal_bedtime(profile):
    return profile.get("goal_bedtime") or "23:30"

def get_goal_waketime(profile):
    return profile.get("goal_waketime") or "07:30"

def is_trial_active(profile):
    """Перевіряє, чи активний безкоштовний Trial для користувача."""
    if not profile.get("trial_used"):
        return False
    exp = profile.get("trial_expires_at")
    if not exp:
        return False
    try:
        exp_dt = datetime.fromisoformat(exp)
    except (ValueError, TypeError):
        return False
    return timeutil.utc_now() < exp_dt

def has_premium_access(profile):
    """Перевіряє доступ до Premium (сплачений або активний Trial)."""
    return profile.get("is_premium", False) or is_trial_active(profile)

def start_trial(profile):
    """Активує Trial для користувача (один раз). Повертає (success, expires_at)."""
    if profile.get("trial_used"):
        return False, None
    now = timeutil.utc_now()
    expires = now + timedelta(days=TRIAL_DAYS)
    profile["trial_used"] = True
    profile["trial_started_at"] = now.isoformat(timespec="minutes")
    profile["trial_expires_at"] = expires.isoformat(timespec="minutes")
    return True, expires.isoformat(timespec="minutes")

def trial_status_text(profile):
    """Текст статусу Trial для повідомлень (локалізація через STRINGS)."""
    if not profile.get("trial_used"):
        return "available"
    if is_trial_active(profile):
        return "active"
    return "expired"

# --- SUPPORT TICKETS ---
_tickets_lock = threading.RLock()

def load_tickets():
    with _tickets_lock:
        try:
            with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

def save_tickets(data):
    with _tickets_lock:
        dir_name = os.path.dirname(os.path.abspath(TICKETS_FILE))
        fd, tmp_path = tempfile.mkstemp(prefix=".support_", suffix=".tmp", dir=dir_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, TICKETS_FILE)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

def create_ticket(user_id, category, message):
    """Створює нове звернення в підтримку. Повертає ticket_id."""
    tickets = load_tickets()
    tid = max([int(k) for k in tickets.keys()] + [1000]) + 1
    now = timeutil.utc_now().isoformat(timespec="minutes")
    ticket = {
        "id": tid,
        "user_id": str(user_id),
        "category": category,
        "message": message,
        "status": "open",
        "admin_reply": None,
        "created_at": now,
        "updated_at": now,
    }
    tickets[str(tid)] = ticket
    save_tickets(tickets)
    return tid

def get_ticket(tid):
    tickets = load_tickets()
    return tickets.get(str(tid))

def update_ticket(tid, **fields):
    tickets = load_tickets()
    if str(tid) in tickets:
        tickets[str(tid)].update(fields)
        tickets[str(tid)]["updated_at"] = timeutil.utc_now().isoformat(timespec="minutes")
        save_tickets(tickets)
        return True
    return False

def get_open_tickets():
    tickets = load_tickets()
    return [t for t in tickets.values() if t["status"] in ("open", "in_progress")]

def get_all_tickets():
    tickets = load_tickets()
    # Сортування: open -> in_progress -> resolved, потім за датою
    status_order = {"open": 0, "in_progress": 1, "resolved": 2}
    return sorted(tickets.values(), key=lambda t: (status_order.get(t["status"], 9), t["created_at"]))

DUR_HOURS = {"dur_6": 6.0, "dur_6_7": 6.7, "dur_7_8": 7.5, "dur_8_9": 8.5, "dur_9": 9.0}

def compute_initial_score(profile):
    """Попередній Sleep Score (0-100) на основі відповідей онбордингу.

    Детермінований, без медичних тверджень. Повертає:
    (score, main_issue, second_issue, goods)
    де issue = (problem_key, penalty, advice_key) або None.
    """
    dur_hours = DUR_HOURS.get(profile.get("usual_duration", "dur_7_8"), 7.5)
    bt = profile.get("usual_bedtime", "bt_normal")
    wt = profile.get("usual_waketime", "wt_normal")
    dis = profile.get("disruptor", "dis_none")

    issues = []
    if dur_hours < 7.0:
        issues.append(("prob_duration", 25 if dur_hours < 6.5 else 15, "advice_duration"))
    if bt in ("bt_night", "bt_deep_night", "bt_morning_owl"):
        issues.append(("prob_bedtime", 20 if bt != "bt_night" else 15, "advice_bedtime"))
    elif bt == "bt_late":
        issues.append(("prob_bedtime", 8, "advice_bedtime"))
    if wt in ("wt_noon", "wt_afternoon", "wt_late_day"):
        issues.append(("prob_waketime", 16 if wt in ("wt_afternoon", "wt_late_day") else 12, "advice_waketime"))
    elif wt == "wt_comfort":
        issues.append(("prob_waketime", 6, "advice_waketime"))
    dis_penalty = {"dis_phone": 14, "dis_coffee": 10, "dis_stress": 12, "dis_food": 7, "dis_noise": 7, "dis_none": 0}
    if dis_penalty.get(dis, 0):
        dis_short = dis.replace("dis_", "")
        issues.append((f"prob_dis_{dis_short}", dis_penalty[dis], f"advice_dis_{dis_short}"))

    score = max(30, min(98, 100 - sum(p for _, p, _ in issues)))
    issues.sort(key=lambda x: -x[1])
    main_issue = issues[0] if issues else None
    second_issue = issues[1] if len(issues) > 1 else None
    goods = []
    if dur_hours >= 7.0:
        goods.append("good_duration")
    if bt in ("bt_early", "bt_normal"):
        goods.append("good_bedtime")
    if wt in ("wt_early", "wt_normal"):
        goods.append("good_waketime")
    if dis == "dis_none":
        goods.append("good_no_disruptor")
    return score, main_issue, second_issue, goods

def _fmt_duration_hours(value):
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value)

def get_goal_waketime(profile):
    return profile.get("goal_waketime") or "07:30"

def build_sleep_context(profile):
    """Контекст для sleep_logic: цільові значення з профілю."""
    return {
        "_target_hours": get_target_hours(profile),
        "_goal_bedtime": get_goal_bedtime(profile),
        "_goal_waketime": get_goal_waketime(profile),
    }

def parse_hhmm_int(value):
    """Парсить час HH:MM у хвилини від початку доби.

    Приймає лише валідний формат HH:MM (години 0–23, хвилини 0–59).
    Повертає None для будь-якого некоректного значення: 25:99, 99:99, абв тощо.
    """
    try:
        hh_str, mm_str = str(value).strip().split(":")
        hh, mm = int(hh_str), int(mm_str)
    except (ValueError, AttributeError):
        return None
    if not (0 <= hh <= 23) or not (0 <= mm <= 59):
        return None
    return hh * 60 + mm

def track_event(profile, event: str):
    """Фіксує подію для аналітики воронки продажів і активності."""
    now = timeutil.utc_now()
    profile.setdefault("funnel", {})
    profile["funnel"][event] = profile["funnel"].get(event, 0) + 1
    profile["last_active"] = now.isoformat(timespec="minutes")
    if not profile.get("registered_at"):
        profile["registered_at"] = now.isoformat(timespec="minutes")

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

def build_ai_user_context(profile):
    """Структурований контекст користувача для AI Sleep Coach (без зайвих персональних даних)."""
    lang = profile.get("lang", "uk")
    logs = profile.get("logs", [])[:14]
    
    # Основні дані
    age_key = profile.get("age_group", "age_young")
    age_info = AGE_GROUPS.get(lang, AGE_GROUPS["uk"]).get(age_key, AGE_GROUPS["uk"]["age_young"])
    goal = profile.get("goal", "goal_quality")
    disruptor = profile.get("disruptor", "dis_phone")
    target_hours = get_target_hours(profile)
    
    # Останній Score
    last_score = None
    if logs and logs[0].get("score") is not None:
        last_score = logs[0]["score"]
    
    # Статистика по логам
    avg_duration = None
    avg_bedtime_min = None
    avg_waketime_min = None
    if logs:
        durations = [l.get("duration", 0) for l in logs if l.get("duration")]
        if durations:
            avg_duration = round(sum(durations) / len(durations), 1)
        
        bedtime_mins = []
        waketime_mins = []
        for l in logs:
            bt = l.get("bedtime")
            wt = l.get("waketime")
            if bt and ":" in bt:
                try:
                    h, m = map(int, bt.split(":"))
                    bedtime_mins.append(h * 60 + m)
                except: pass
            if wt and ":" in wt:
                try:
                    h, m = map(int, wt.split(":"))
                    waketime_mins.append(h * 60 + m)
                except: pass
        if bedtime_mins:
            avg_bedtime_min = round(sum(bedtime_mins) / len(bedtime_mins))
        if waketime_mins:
            avg_waketime_min = round(sum(waketime_mins) / len(waketime_mins))
    
    def fmt_hm(minutes):
        if minutes is None:
            return "—"
        h = minutes // 60
        m = minutes % 60
        return f"{h:02d}:{m:02d}"
    
    # Регулярність (streak + кількість записів за тиждень)
    streak = sleep_logic.current_streak(logs) if hasattr(sleep_logic, 'current_streak') else 0
    week_logs = logs[:7] if len(logs) >= 7 else logs
    week_count = len(week_logs)
    
    # Фактори
    caffeine_count = sum(1 for l in logs if l.get("caffeine"))
    screens_count = sum(1 for l in logs if l.get("screens"))
    nap_count = sum(1 for l in logs if l.get("nap"))
    
    # Нагадування
    reminders = profile.get("reminders", {})
    enabled_reminders = [k for k, v in reminders.items() if isinstance(v, dict) and v.get("enabled")]
    
    # Прогрес курсу
    course_completed = len(profile.get("course_completed", []))
    
    # Initial Score
    initial_score, _, _, _ = compute_initial_score(profile)
    
    # Тренд останніх 7 днів (середня тривалість останні 3 vs попередні 4)
    trend = "stable"
    if len(logs) >= 7:
        recent_3 = sum(l.get("duration", 0) for l in logs[:3]) / 3
        prev_4 = sum(l.get("duration", 0) for l in logs[3:7]) / 4
        if recent_3 > prev_4 + 0.3:
            trend = "improving"
        elif recent_3 < prev_4 - 0.3:
            trend = "declining"
    
    # Language for response
    lang_names = {"uk": "Ukrainian (українська)", "en": "English", "ru": "Russian (русский)"}
    selected_lang = lang_names.get(lang, "Ukrainian")
    
    context_lines = [
        f"Мова відповіді: {selected_lang}",
        f"Вікова категорія: {age_info['title']} (норма сну {age_info['target_hours']} год)",
        f"Мета: {GOALS.get(lang, GOALS['uk']).get(goal, goal)}",
        f"Головна перешкода: {DISRUPTORS.get(lang, DISRUPTORS['uk']).get(disruptor, disruptor)}",
    ]
    
    if last_score is not None:
        context_lines.append(f"Останній Sleep Score: {last_score}/100")
    context_lines.append(f"Початковий Score (з онбордингу): {initial_score}/100")
    
    if avg_duration is not None:
        context_lines.append(f"Середня тривалість сну ({len(logs)} записів): {avg_duration} год")
    if avg_bedtime_min is not None:
        context_lines.append(f"Середній час засинання: {fmt_hm(avg_bedtime_min)}")
    if avg_waketime_min is not None:
        context_lines.append(f"Середній час пробудження: {fmt_hm(avg_waketime_min)}")
    
    if streak:
        context_lines.append(f"Поточна серія: {streak} днів")
    context_lines.append(f"Записів за останні 7 днів: {week_count}")
    
    if caffeine_count or screens_count or nap_count:
        context_lines.append(f"Фактори (за {len(logs)} ночей): кофеїн — {caffeine_count}, екрани — {screens_count}, денний сон — {nap_count}")
    
    if enabled_reminders:
        context_lines.append(f"Активні нагадування: {', '.join(enabled_reminders)}")
    
    if course_completed:
        context_lines.append(f"Пройдено уроків курсу: {course_completed}/7")
    
    if trend != "stable":
        context_lines.append(f"Тренд тривалості (останні 3 vs попередні 4 ночі): {trend}")
    
    # Цільові значення
    goal_bt = profile.get("goal_bedtime", "22:30")
    goal_wt = profile.get("goal_waketime", "07:30")
    context_lines.append(f"Цільове засинання: {goal_bt}, цільовий підйом: {goal_wt}, цільова тривалість: {target_hours} год")
    
    return "\n".join(context_lines)

def generate_real_ai_answer(profile, question):
    """Генерує персоналізовану відповідь AI Sleep Coach на основі контексту користувача."""
    lang = profile.get("lang", "uk")
    lang_names = {"uk": "Ukrainian (українська)", "en": "English", "ru": "Russian (русский)"}
    selected_lang = lang_names.get(lang, "Ukrainian")
    
    user_context = build_ai_user_context(profile)
    
    prompt = (
        f"Ти — персональний AI Sleep Coach. Відповідаєш на основі реальних даних користувача.\n\n"
        f"КОНТЕКСТ КОРИСТУВАЧА (лише фактичні дані):\n{user_context}\n\n"
        f"ПИТАННЯ КОРИСТУВАЧА: \"{question}\"\n\n"
        f"ПРАВИЛА:\n"
        f"1. Відповідай мовою: {selected_lang}.\n"
        f"2. Використовуй ТІЛЬКИ дані з контексту. Якщо даних немає — чесно скажи, що інформації недостатньо, і запропонуй записати ще кілька ночей.\n"
        f"3. Не став медичні діагнози, не роби категоричних медичних висновків, не лякай користувача.\n"
        f"4. Якщо користувач описує серйозну проблему зі здоров'ям — обережно порадь звернутися до лікаря/сомнолога.\n"
        f"5. Якщо питання «чому Score низький» — поясни на основі його Score та факторів з контексту.\n"
        f"6. Якщо «проаналізуй останні 7 днів» — використовуй саме останні записи з контексту.\n"
        f"7. Відповідь 60-150 слів, Markdown, конкретні поради, без води.\n"
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
    
    fallback = {
        "uk": "🤖 **AI Sleep Coach:** Для покращення якості сну дотримуйтесь регулярного режиму, провітрюйте кімнату перед сном та вимикайте екрани за годину до відпочинку! Якщо бажаєте персональних порад — запишіть кілька ночей сну.",
        "en": "🤖 **AI Sleep Coach:** To improve sleep quality, keep a regular schedule, air out the room before bed, and turn off screens an hour before rest! For personalized advice, log a few nights of sleep.",
        "ru": "🤖 **ИИ-Сонный тренер:** Для улучшения качества сна соблюдайте регулярный режим, проветривайте комнату перед сном и выключайте экраны за час до отдыха! Для персональных советов запишите несколько ночей сна."
    }
    return fallback.get(lang, fallback["uk"])

def build_personal_course_fallback(profile):
    """Персоналізований курс без ШІ (якщо провайдер g4f недоступний)."""
    lang = profile.get("lang", "uk")
    dis_title = DISRUPTORS.get(lang, DISRUPTORS["uk"]).get(profile.get("disruptor", "dis_phone"), "Телефон / Гаджети")
    goal_title = GOALS.get(lang, GOALS["uk"]).get(profile.get("goal", "goal_quality"), "Покращити якість сну")

    titles = {
        1: get_text(profile, "course_fb_1", dis=dis_title),
        2: get_text(profile, "course_fb_2"),
        3: get_text(profile, "course_fb_3"),
        4: get_text(profile, "course_fb_4"),
        5: get_text(profile, "course_fb_5"),
        6: get_text(profile, "course_fb_6", goal=goal_title),
        7: get_text(profile, "course_fb_7")
    }
    base = get_course_days(profile)
    return {d: {"title": titles[d], "text": base[d]["text"]} for d in range(1, 8)}

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
    has_access = has_premium_access(profile)

    # Якщо немає доступу до Premium — показуємо кнопку купівлі, профіль та підтримку
    if not has_access:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=s.get("btn_buy", "💳 Придбати курс (99 грн)"))],
                [KeyboardButton(text=s.get("btn_profile", "👤 Профіль")), KeyboardButton(text=s.get("btn_support", "💬 Support"))]
            ],
            resize_keyboard=True
        )

    sleep_btn = KeyboardButton(text=s["btn_wake"]) if is_sleeping else KeyboardButton(text=s["btn_sleep"])
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [sleep_btn],
            [KeyboardButton(text=s["btn_course"]), KeyboardButton(text=s["btn_ask_ai"])],
            [KeyboardButton(text=s["btn_journal"]), KeyboardButton(text=s["btn_stats"])],
            [KeyboardButton(text=s["btn_goals"]), KeyboardButton(text=s["btn_reminders"])],
            [KeyboardButton(text=s["btn_profile"]), KeyboardButton(text=s["btn_support"])]
        ],
        resize_keyboard=True
    )
    return kb

# --- ПЕЙВОЛ: 99 грн за 7-денний курс ---
def get_course_days(profile):
    """Персональний курс від ШІ, якщо він є; інакше — базова програма (мовою користувача)."""
    personal = profile.get("personal_course")
    if isinstance(personal, dict) and len(personal) >= 7:
        try:
            course = {int(k): v for k, v in personal.items()}
            if all(d in course and course[d].get("title") and course[d].get("text") for d in range(1, 8)):
                return course
        except (ValueError, TypeError, AttributeError):
            pass
    lang = profile.get("lang", "uk") or "uk"
    base = {"uk": BOT_COURSE_DAYS, "en": BOT_COURSE_DAYS_EN, "ru": BOT_COURSE_DAYS_RU}
    return base.get(lang, BOT_COURSE_DAYS)

def build_paywall(profile, locked_feature=False):
    """Єдиний екран оплати: персональний заголовок за Score, проблема, вигоди, CTA + Trial кнопка."""
    score, main_issue, _, _ = compute_initial_score(profile)
    band = "low" if score < 60 else ("mid" if score < 80 else "high")
    problem = get_text(profile, main_issue[0]) if main_issue else get_text(profile, "prob_default")
    header = get_text(profile, "paywall_locked_header") if locked_feature else ""

    # Trial status note
    trial_note = ""
    if profile.get("trial_used") and not is_trial_active(profile):
        trial_note = f"\n{get_text(profile, 'trial_ended')}\n"

    text = (
        f"{header}"
        f"**{get_text(profile, 'paywall_headline_' + band)}**\n\n"
        f"{get_text(profile, 'paywall_score', score=score)}\n\n"
        f"{get_text(profile, 'paywall_opportunity', problem=problem)}\n\n"
        f"{get_text(profile, 'paywall_solution')}\n\n"
        f"{get_text(profile, 'paywall_benefits_title')}\n"
        f"{get_text(profile, 'benefit_analysis')}\n"
        f"{get_text(profile, 'benefit_coach')}\n"
        f"{get_text(profile, 'benefit_course')}\n"
        f"{get_text(profile, 'benefit_habits')}\n"
        f"{get_text(profile, 'benefit_stats')}"
        f"{trial_note}\n\n"
        f"{get_text(profile, 'paywall_price')}\n"
        f"_{get_text(profile, 'paywall_trust')}_"
    )

    buttons = [
        [InlineKeyboardButton(text=get_text(profile, "cta_start"), callback_data="pay_mono_link")]
    ]
    # Додаємо кнопку Trial, якщо користувач ще не використовував його
    if not profile.get("trial_used") and not profile.get("is_premium", False):
        buttons.append([InlineKeyboardButton(text=get_text(profile, "cta_try"), callback_data="trial_offer")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    return text, kb

def build_result_screen(profile):
    """Персональний результат тесту: Score, проблеми, що це означає, базова рекомендація."""
    score, main_issue, second_issue, goods = compute_initial_score(profile)
    band = "low" if score < 60 else ("mid" if score < 80 else "high")
    lines = [
        get_text(profile, "result_title"),
        get_text(profile, "score_line", score=score),
        get_text(profile, "result_score_note"),
    ]
    if main_issue:
        lines.append(get_text(profile, "result_main_problem") + get_text(profile, main_issue[0]))
    if second_issue:
        lines.append(get_text(profile, "result_second_problem") + get_text(profile, second_issue[0]))
    if goods:
        lines.append(get_text(profile, "result_good_title") + "\n".join("• " + get_text(profile, g) for g in goods))
    lines.append(get_text(profile, "result_means_title"))
    lines.append(get_text(profile, f"result_means_{band}"))
    lines.append(get_text(profile, "result_plan",
                          duration=_fmt_duration_hours(profile.get("goal_duration", 8)),
                          bedtime=profile.get("goal_bedtime", "23:30"),
                          waketime=profile.get("goal_waketime", "07:30")))
    if main_issue:
        lines.append(get_text(profile, "result_advice_title") + get_text(profile, main_issue[2]))
    text = "\n\n".join(lines)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(profile, "cta_see_plan"), callback_data="result_see_plan")]
    ])
    return text, kb

def build_preview_screen(profile):
    """Preview заблокованого плану: День 1 відкрито, дні 2-7 під замком."""
    course = get_course_days(profile)
    day1 = course[1]
    title1 = day1["title"]
    text1 = day1["text"]
    preview = text1[:220] + ("…" if len(text1) > 220 else "")
    locked_lines = "\n".join(
        get_text(profile, "preview_day_locked", title=course[d]["title"]) for d in range(2, 8)
    )
    text = (
        f"{get_text(profile, 'preview_title')}\n\n"
        f"✅ **{title1}**\n{preview}\n\n"
        f"{locked_lines}\n\n"
        f"{get_text(profile, 'preview_unlock_hint')}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(profile, "cta_unlock"), callback_data="preview_unlock")]
    ])
    return text, kb

async def require_premium(message: types.Message):
    """True — доступ є. False — показано пейвол, хендлер має вийти."""
    profile = get_user_profile(message.from_user.id)
    if has_premium_access(profile):
        return True

    track_event(profile, "paywall_view")
    save_user_profile(message.from_user.id, profile)

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
    profile = get_user_profile(message.from_user.id)
    # Користувач уже пройшов онбординг — не запускаємо його заново.
    if profile.get("is_configured", False):
        await message.answer(
            get_text(profile, "welcome_back"),
            reply_markup=get_main_keyboard(profile),
        )
        return
    buttons = [
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="ob_lang_uk")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="ob_lang_en")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="ob_lang_ru")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    # Мова — завжди з профілю (єдине джерело правди). Для нових користувачів — дефолт.
    lang = profile.get("lang", "uk") or "uk"
    welcome_text = get_text(profile, "onboarding_welcome", name=message.from_user.first_name)
    await message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(OnboardingState.waiting_for_lang)

@dp.callback_query(F.data.startswith("ob_lang_"))
async def process_onboarding_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.replace("ob_lang_", "")
    if lang in LANGUAGES:
        await state.update_data(lang=lang)

        profile = get_user_profile(callback.from_user.id)
        # Мова зберігається в профілі — єдине джерело правди на весь flow.
        profile["lang"] = lang
        update_user_profile(callback.from_user.id, profile)

        waketimes = WAKETIME_OPTIONS.get(lang, WAKETIME_OPTIONS["uk"])
        buttons = []
        for wt_key, wt_title in waketimes.items():
            buttons.append([InlineKeyboardButton(text=wt_title, callback_data=f"ob_wt_{wt_key}")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        s = STRINGS.get(lang, STRINGS["uk"])

        await callback.message.edit_text(
            f"🌐 Language: **{LANGUAGES[lang]}**\n\n"
            f"{s['step_waketime']}",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        await state.set_state(OnboardingState.waiting_for_waketime)
    await callback.answer()

@dp.callback_query(F.data.startswith("ob_age_"))
async def process_onboarding_age(callback: CallbackQuery, state: FSMContext):
    age_key = callback.data.replace("ob_age_", "")
    data = await state.get_data()
    # Мова — з профілю (збережена на кроці 1), FSM — лише резерв.
    lang = get_user_profile(callback.from_user.id).get("lang") or data.get("lang", "uk")

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

@dp.callback_query(F.data.startswith("ob_wt_"))
async def process_onboarding_waketime(callback: CallbackQuery, state: FSMContext):
    wt_key = callback.data.replace("ob_wt_", "")
    data = await state.get_data()
    # Мова — з профілю (збережена на кроці 1), FSM — лише резерв.
    lang = get_user_profile(callback.from_user.id).get("lang") or data.get("lang", "uk")

    waketimes = WAKETIME_OPTIONS.get(lang, WAKETIME_OPTIONS["uk"])
    if wt_key in waketimes:
        await state.update_data(usual_waketime=wt_key)

        bedtimes = BEDTIME_OPTIONS.get(lang, BEDTIME_OPTIONS["uk"])
        buttons = []
        for bt_key, bt_title in bedtimes.items():
            buttons.append([InlineKeyboardButton(text=bt_title, callback_data=f"ob_bt_{bt_key}")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        s = STRINGS.get(lang, STRINGS["uk"])

        await callback.message.edit_text(
            f"✅ {waketimes[wt_key]}\n\n"
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
    # Мова — з профілю (збережена на кроці 1), FSM — лише резерв.
    lang = get_user_profile(callback.from_user.id).get("lang") or data.get("lang", "uk")

    bedtimes = BEDTIME_OPTIONS.get(lang, BEDTIME_OPTIONS["uk"])
    if bt_key in bedtimes:
        await state.update_data(usual_bedtime=bt_key)

        s = STRINGS.get(lang, STRINGS["uk"])
        duration_options = [
            ("dur_6", "😴 Менше 6 годин"),
            ("dur_6_7", "😴 6-7 годин"),
            ("dur_7_8", "😴 7-8 годин"),
            ("dur_8_9", "😊 8-9 годин"),
            ("dur_9", "💪 Понад 9 годин")
        ]
        buttons = [[InlineKeyboardButton(text=t, callback_data=f"ob_dur_{key}")] for key, t in duration_options]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            f"✅ {bedtimes[bt_key]}\n\n"
            f"{s['step_duration']}",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        await state.set_state(OnboardingState.waiting_for_goal)
    await callback.answer()

@dp.callback_query(F.data.startswith("ob_dur_"))
async def process_onboarding_duration(callback: CallbackQuery, state: FSMContext):
    dur_key = callback.data.replace("ob_dur_", "")
    data = await state.get_data()
    # Мова — з профілю (збережена на кроці 1), FSM — лише резерв.
    lang = get_user_profile(callback.from_user.id).get("lang") or data.get("lang", "uk")

    duration_options = {
        "dur_6": 6.0,
        "dur_6_7": 7.0,
        "dur_7_8": 8.0,
        "dur_8_9": 9.0,
        "dur_9": 10.0
    }
    if dur_key in duration_options:
        await state.update_data(usual_duration=dur_key)

        s = STRINGS.get(lang, STRINGS["uk"])
        disruptors = DISRUPTORS.get(lang, DISRUPTORS["uk"])
        buttons = []
        for dis_key, dis_title in disruptors.items():
            buttons.append([InlineKeyboardButton(text=dis_title, callback_data=f"ob_dis_{dis_key}")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            f"✅ {s['step_duration']}\n\n"
            f"{s['step_problem']}",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        await state.set_state(OnboardingState.waiting_for_disruptor)
    await callback.answer()

@dp.callback_query(F.data.startswith("ob_dis_"))
async def process_onboarding_disruptor(callback: CallbackQuery, state: FSMContext):
    dis_key = callback.data.replace("ob_dis_", "")
    data = await state.get_data()

    # Мова — з профілю (збережена на кроці 1), FSM — лише резерв.
    lang = get_user_profile(callback.from_user.id).get("lang") or data.get("lang", "uk")
    age_key = data.get("age_group", "age_young")
    bt_key = data.get("usual_bedtime", "bt_normal")
    wt_key = data.get("usual_waketime", "wt_normal")
    goal_key = data.get("goal")
    dur_key = data.get("usual_duration", "dur_7_8")

    # Мета виводиться зі звичної тривалості сну (без зайвого питання)
    DUR_GOALS = {
        "dur_6": "goal_fall",
        "dur_6_7": "goal_quality",
        "dur_7_8": "goal_quality",
        "dur_8_9": "goal_schedule",
        "dur_9": "goal_schedule",
    }
    if goal_key not in GOALS.get(lang, GOALS["uk"]):
        goal_key = DUR_GOALS.get(dur_key, "goal_quality")
    target_hours = DUR_HOURS.get(dur_key, 8.0)

    profile = get_user_profile(callback.from_user.id)
    profile["lang"] = lang
    profile["age_group"] = age_key
    profile["usual_bedtime"] = bt_key
    profile["usual_waketime"] = wt_key
    profile["usual_duration"] = dur_key
    profile["goal"] = goal_key
    profile["disruptor"] = dis_key
    profile["is_configured"] = True
    # IANA-timezone за замовчуванням (Europe/Kyiv), якщо користувач не обрав.
    profile["timezone"] = profile.get("timezone") or timeutil.DEFAULT_TIMEZONE
    # Цілі за замовчуванням із відповідей онбордингу
    if not profile.get("goal_bedtime"):
        bt_title = BEDTIME_OPTIONS.get(lang, BEDTIME_OPTIONS["uk"]).get(bt_key, "bt_normal")
        profile["goal_bedtime"] = {"bt_early": "21:30", "bt_normal": "22:30", "bt_late": "23:30", "bt_night": "00:30", "bt_deep_night": "01:30", "bt_morning_owl": "02:30"}.get(bt_key, "23:30")
    if not profile.get("goal_waketime"):
        profile["goal_waketime"] = {"wt_early": "06:00", "wt_normal": "07:30", "wt_comfort": "09:00", "wt_noon": "10:30", "wt_afternoon": "12:00", "wt_late_day": "14:00"}.get(wt_key, "07:30")
    if not profile.get("goal_duration"):
        profile["goal_duration"] = target_hours
    profile["registered_at"] = profile.get("registered_at") or timeutil.utc_now().isoformat(timespec="minutes")
    profile["last_active"] = timeutil.utc_now().isoformat(timespec="minutes")
    update_user_profile(callback.from_user.id, profile)

    await state.clear()

    age_info = AGE_GROUPS.get(lang, AGE_GROUPS["uk"]).get(age_key, AGE_GROUPS["uk"]["age_young"])
    dis_title = DISRUPTORS.get(lang, DISRUPTORS["uk"]).get(dis_key, "Телефон / Гаджети")

    # Первинне сповіщення про роботу ШІ
    await callback.message.delete()
    loading_msg = await callback.message.answer(
        get_text(profile, "onboarding_ai_loading", age=age_info['title'], dis=dis_title),
        parse_mode="HTML"
    )

    # ШІ складає персональний курс саме під відповіді цього користувача
    course = await asyncio.to_thread(generate_personal_course, profile)
    profile["personal_course"] = {str(day): lesson for day, lesson in course.items()}
    profile["course_generated_at"] = timeutil.utc_now().strftime("%Y-%m-%d %H:%M")
    update_user_profile(callback.from_user.id, profile)

    try:
        await loading_msg.delete()
    except Exception:
        pass

    # Персональний результат тесту + CTA до попереднього перегляду плану
    result_text, result_kb = build_result_screen(profile)
    await callback.message.answer(result_text, reply_markup=result_kb, parse_mode="Markdown")
    # Обмежена клавіатура до оплати
    await callback.message.answer(
        get_text(profile, "all_locked"),
        reply_markup=get_main_keyboard(profile, is_sleeping=False),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "result_see_plan")
async def process_result_see_plan(callback: CallbackQuery):
    """З результату тесту — попередній перегляд плану (День 1 + закриті дні)."""
    profile = get_user_profile(callback.from_user.id)
    if profile.get("is_premium", False):
        text, kb = render_course_list(profile)
    else:
        text, kb = build_preview_screen(profile)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "preview_unlock")
async def process_preview_unlock(callback: CallbackQuery):
    """З попереднього перегляду — персоналізований пейвол."""
    profile = get_user_profile(callback.from_user.id)
    if profile.get("is_premium", False):
        text, kb = render_course_list(profile)
    else:
        track_event(profile, "paywall_view")
        save_user_profile(callback.from_user.id, profile)
        text, kb = build_paywall(profile)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
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

    # Зберігаємо момент засинання в UTC (aware) — єдині годинники проєкту.
    profile["active_sleep_start"] = timeutil.utc_now().isoformat()
    update_user_profile(message.from_user.id, profile)

    # Відображаємо локальний час у timezone користувача (Europe/Kyiv тощо).
    now_str = timeutil.local_time_str(timeutil.utc_now(), timeutil.get_user_timezone(profile))
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

    # Обидва моменти — UTC-aware: різниця коректна для будь-якого timezone,
    # переходу через опівніч та сну довше доби.
    start_dt = timeutil.parse_stored_dt(start_iso)
    if start_dt is None:
        profile["active_sleep_start"] = None
        update_user_profile(message.from_user.id, profile)
        await message.answer(
            get_text(profile, "not_sleeping"),
            reply_markup=get_main_keyboard(profile, is_sleeping=False),
            parse_mode="Markdown"
        )
        return
    zone = timeutil.get_user_timezone(profile)
    end_dt = timeutil.utc_now()

    diff_seconds = max(60, (end_dt - start_dt).total_seconds())
    hours = diff_seconds / 3600.0
    duration_rounded = round(hours, 1)

    # Відображення — у локальному часі користувача (не UTC сервера!).
    bedtime_str = timeutil.local_time_str(start_dt, zone)
    waketime_str = timeutil.local_time_str(end_dt, zone)
    date_str = timeutil.local_date_dmy(end_dt, zone)

    pending = {
        "date": date_str,
        "bedtime": bedtime_str,
        "waketime": waketime_str,
        "duration": duration_rounded,
        "quality_num": None,
        "wakeups": 0,
        "caffeine": None,
        "screens": None,
        "nap": None,
    }
    await state.set_state(SleepLogForm.waiting_for_quality)
    await state.update_data(pending=pending)

    profile["active_sleep_start"] = None
    update_user_profile(message.from_user.id, profile)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{n} 😴", callback_data=f"sl_q_{n}") for n in range(1, 6)],
        [InlineKeyboardButton(text=f"{n} 😊", callback_data=f"sl_q_{n}") for n in range(6, 11)],
        [InlineKeyboardButton(text=get_text(profile, "skip_btn"), callback_data="sl_skip")]
    ])
    await message.answer(
        get_text(profile, "slept_duration",
                 duration=sleep_logic.duration_to_text(duration_rounded),
                 bedtime=bedtime_str, waketime=waketime_str)
        + get_text(profile, 'ask_quality'),
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "sl_skip")
async def process_sleep_skip(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    pending = data.get("pending")
    if not pending:
        profile = get_user_profile(callback.from_user.id)
        await callback.answer(get_text(profile, "log_not_found"), show_alert=True)
        return
    await _finalize_sleep_log(callback.message, state, pending)
    await callback.answer()

def _sleep_factors_kb(profile, data):
    caffeine = data.get("caffeine")
    screens = data.get("screens")
    nap = data.get("nap")
    s = STRINGS.get(profile.get("lang", "uk"), STRINGS["uk"])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=(s.get("factor_caffeine_on") if caffeine else s.get("factor_caffeine")),
            callback_data="sl_f_toggle_caffeine")],
        [InlineKeyboardButton(
            text=(s.get("factor_screens_on") if screens else s.get("factor_screens")),
            callback_data="sl_f_toggle_screens")],
        [InlineKeyboardButton(
            text=(s.get("factor_nap_on") if nap else s.get("factor_nap")),
            callback_data="sl_f_toggle_nap")],
        [InlineKeyboardButton(text=get_text(profile, "factors_done"), callback_data="sl_f_done"),
         InlineKeyboardButton(text=get_text(profile, "skip_btn"), callback_data="sl_skip")]
    ])

def _sleep_wakeups_kb(profile):
    s = STRINGS.get(profile.get("lang", "uk"), STRINGS["uk"])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=s.get("wakeups_0"), callback_data="sl_w_0"),
         InlineKeyboardButton(text=s.get("wakeups_1"), callback_data="sl_w_1")],
        [InlineKeyboardButton(text=s.get("wakeups_2"), callback_data="sl_w_2"),
         InlineKeyboardButton(text=s.get("wakeups_3"), callback_data="sl_w_3")],
        [InlineKeyboardButton(text=get_text(profile, "skip_btn"), callback_data="sl_skip")]
    ])

@dp.callback_query(F.data.startswith("sl_q_"))
async def process_sleep_quality(callback: CallbackQuery, state: FSMContext):
    if callback.data == "sl_q_":
        await callback.answer()
        return
    try:
        quality_num = int(callback.data.replace("sl_q_", ""))
    except ValueError:
        profile = get_user_profile(callback.from_user.id)
        await callback.answer(get_text(profile, "invalid_value"), show_alert=True)
        return
    if not 1 <= quality_num <= 10:
        profile = get_user_profile(callback.from_user.id)
        await callback.answer(get_text(profile, "invalid_value"), show_alert=True)
        return

    data = await state.get_data()
    if not data.get("pending"):
        profile = get_user_profile(callback.from_user.id)
        await callback.answer(get_text(profile, "log_not_found"), show_alert=True)
        return
    data["pending"]["quality_num"] = quality_num
    await state.update_data(pending=data["pending"])
    await state.set_state(SleepLogForm.waiting_for_wakeups)

    profile = get_user_profile(callback.from_user.id)
    await callback.message.edit_text(
        get_text(profile, "sleep_quality_label", quality=f"{quality_num}/10")
        + f"\n\n{get_text(profile, 'ask_wakeups')}",
        reply_markup=_sleep_wakeups_kb(profile),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("sl_w_"))
async def process_sleep_wakeups(callback: CallbackQuery, state: FSMContext):
    if callback.data == "sl_w_":
        await callback.answer()
        return
    try:
        wakeups = int(callback.data.replace("sl_w_", ""))
    except ValueError:
        profile = get_user_profile(callback.from_user.id)
        await callback.answer(get_text(profile, "invalid_value"), show_alert=True)
        return

    data = await state.get_data()
    if not data.get("pending"):
        profile = get_user_profile(callback.from_user.id)
        await callback.answer(get_text(profile, "log_not_found"), show_alert=True)
        return
    data["pending"]["wakeups"] = wakeups
    await state.update_data(pending=data["pending"])
    await state.set_state(SleepLogForm.waiting_for_factors)

    profile = get_user_profile(callback.from_user.id)
    await callback.message.edit_text(
        get_text(profile, "sleep_wakeups_label", wakeups=wakeups)
        + f"\n\n{get_text(profile, 'ask_factors')}",
        reply_markup=_sleep_factors_kb(profile, data["pending"]),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("sl_f_toggle_"))
async def process_sleep_factor_toggle(callback: CallbackQuery, state: FSMContext):
    key = callback.data.replace("sl_f_toggle_", "")
    if key not in ("caffeine", "screens", "nap"):
        await callback.answer()
        return
    data = await state.get_data()
    if not data.get("pending"):
        profile = get_user_profile(callback.from_user.id)
        await callback.answer(get_text(profile, "log_not_found"), show_alert=True)
        return
    data["pending"][key] = not bool(data["pending"].get(key))
    await state.update_data(pending=data["pending"])

    profile = get_user_profile(callback.from_user.id)
    try:
        await callback.message.edit_text(
            get_text(profile, "ask_factors"),
            reply_markup=_sleep_factors_kb(profile, data["pending"]),
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data == "sl_f_done")
async def process_sleep_factors_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    pending = data.get("pending")
    if not pending:
        profile = get_user_profile(callback.from_user.id)
        await callback.answer(get_text(profile, "log_not_found"), show_alert=True)
        return
    await _finalize_sleep_log(callback.message, state, pending)
    await callback.answer()

async def _finalize_sleep_log(message: types.Message, state: FSMContext, pending: dict):
    user_id = message.from_user.id
    profile = get_user_profile(user_id)

    pending["caffeine"] = bool(pending.get("caffeine"))
    pending["screens"] = bool(pending.get("screens"))
    pending["nap"] = bool(pending.get("nap"))
    q = pending.get("quality_num")

    score, components = sleep_logic.compute_sleep_score(build_sleep_context(profile), pending)
    pending["score"] = score
    if q is not None:
        pending["quality"] = f"{q}/10"
    else:
        pending["quality"] = get_text(profile, "quality_auto")

    profile["logs"].insert(0, pending)
    track_event(profile, "log_saved")

    # Гейміфікація
    old_level = sleep_logic.level_from_xp(profile.get("xp", 0))
    profile["xp"] = sleep_logic.compute_xp(profile["logs"])
    new_level = sleep_logic.level_from_xp(profile["xp"])
    # Дати записів — локальні для користувача; streak рахуємо відносно них.
    log_date = sleep_logic.parse_log_date(pending.get("date"))
    achievements = sleep_logic.check_achievements(
        profile["logs"], today=log_date.date() if log_date else None)
    new_achievements = []
    for aid, achieved in achievements.items():
        if achieved and aid not in profile.get("achievements", []):
            profile["achievements"].append(aid)
            new_achievements.append(aid)
    save_user_profile(user_id, profile)

    await state.clear()

    lines = [
        get_text(profile, "log_saved",
                 date=pending["date"],
                 duration=sleep_logic.duration_to_text(pending["duration"]),
                 bedtime=pending["bedtime"],
                 waketime=pending["waketime"],
                 quality=pending["quality"]),
        f"\n{get_text(profile, 'score_line', score=score)}",
    ]
    if score >= 80:
        lines.append(f"*{get_text(profile, 'score_badge_high')}*")
    elif score >= 60:
        lines.append(f"*{get_text(profile, 'score_badge_mid')}*")
    else:
        lines.append(f"*{get_text(profile, 'score_badge_low')}*")

    good, bad, tips = sleep_logic.explain_score(components)
    if good:
        good_lines = "\n".join(f"• {get_text(profile, k)}" for k in good)
        lines.append(f"\n{get_text(profile, 'score_good', items=good_lines)}")
    if bad:
        bad_lines = "\n".join(f"• {get_text(profile, k)}" for k in bad)
        lines.append(f"\n{get_text(profile, 'score_bad', items=bad_lines)}")
    if tips:
        tip_lines = "\n".join(f"• {get_text(profile, k)}" for k in tips)
        lines.append(f"\n{get_text(profile, 'score_tips', items=tip_lines)}")

    if new_achievements:
        for aid in new_achievements:
            ach = sleep_logic.get_achievement(aid)
            if ach:
                lines.append(f"\n{get_text(profile, 'ach_new', achievement=ach['icon'] + ' ' + get_text(profile, 'ach_' + aid))}")
    if new_level > old_level:
        lines.append(f"\n{get_text(profile, 'level_up', level=new_level)}")

    status_str = get_text(profile, "ai_thinking")
    msg = await message.answer(
        "\n".join(lines) + f"\n\n{status_str}",
        reply_markup=get_main_keyboard(profile, is_sleeping=False),
        parse_mode="Markdown"
    )

    # ШІ-аналіз ночі (фоном, у фоновому потоці)
    ai_deep_report = await asyncio.to_thread(
        generate_real_ai_analysis, profile, pending["duration"], pending["quality"],
        pending["bedtime"], pending["waketime"])
    final_content = "\n".join(lines) + f"\n\n{ai_deep_report}"
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

    logs = profile.get("logs", [])
    xp = profile.get("xp", 0) or sleep_logic.compute_xp(logs)
    level = sleep_logic.level_from_xp(xp)
    streak = sleep_logic.compute_streak(logs)
    profile_text += (
        f"\n{get_text(profile, 'profile_level_line', level=level, xp=xp, streak=streak)}"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏆 " + s["btn_achievements"], callback_data="prof_achievements")],
            [InlineKeyboardButton(text=s["change_lang"], callback_data="re_onboarding")],
            [InlineKeyboardButton(text=s["re_onboarding"], callback_data="re_onboarding")]
        ]
    )
    await message.answer(
        profile_text,
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "prof_achievements")
async def process_profile_achievements(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    s = STRINGS.get(profile.get("lang", "uk"), STRINGS["uk"])
    logs = profile.get("logs", [])
    xp = profile.get("xp", 0) or sleep_logic.compute_xp(logs)
    level = sleep_logic.level_from_xp(xp)
    progress = int(sleep_logic.level_progress(xp) * 100)
    streak = sleep_logic.compute_streak(logs)
    achieved = set(profile.get("achievements", []))

    lines = [get_text(profile, "ach_title",
                      level=level, xp=xp, next=level + 1, progress=progress, streak=streak)]
    for a in sleep_logic.ACHIEVEMENTS:
        done = a["id"] in achieved
        mark = "✅" if done else "🔒"
        lines.append(f"{mark} {get_text(profile, 'ach_' + a['id'])}")

    buttons = [[InlineKeyboardButton(text=get_text(profile, "back") + " " + s["btn_profile"], callback_data="prof_back")]]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data == "prof_back")
async def process_profile_back(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    lang = profile.get("lang", "uk")
    s = STRINGS.get(lang, STRINGS["uk"])
    age_info = AGE_GROUPS.get(lang, AGE_GROUPS["uk"]).get(profile.get("age_group", "age_young"), {"title": "N/A", "target_hours": 8.0})
    bt_title = BEDTIME_OPTIONS.get(lang, BEDTIME_OPTIONS["uk"]).get(profile.get("usual_bedtime", "bt_normal"), "N/A")
    wt_title = WAKETIME_OPTIONS.get(lang, WAKETIME_OPTIONS["uk"]).get(profile.get("usual_waketime", "wt_normal"), "N/A")
    logs = profile.get("logs", [])
    xp = profile.get("xp", 0) or sleep_logic.compute_xp(logs)
    level = sleep_logic.level_from_xp(xp)
    streak = sleep_logic.compute_streak(logs)

    profile_text = (
        f"{get_text(profile, 'profile_title')}\n\n"
        + get_text(profile, "profile_body",
                   lang=LANGUAGES.get(lang, "Українська"),
                   age=age_info["title"], target=age_info["target_hours"],
                   bedtime=bt_title, waketime=wt_title)
        + f"\n{get_text(profile, 'profile_level_line', level=level, xp=xp, streak=streak)}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 " + s["btn_achievements"], callback_data="prof_achievements")],
        [InlineKeyboardButton(text=s["change_lang"], callback_data="re_onboarding")],
        [InlineKeyboardButton(text=s["re_onboarding"], callback_data="re_onboarding")]
    ])
    try:
        await callback.message.edit_text(profile_text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()

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

# --- 📊 СТАТИСТИКА: ТЕНДЕНЦІЇ, ЗАКОНОМІРНОСТІ, РЕКОМЕНДАЦІЇ ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_stats"], STRINGS["en"]["btn_stats"], STRINGS["ru"]["btn_stats"]]))
async def process_stats(message: types.Message):
    if not await require_premium(message):
        return

    profile = get_user_profile(message.from_user.id)
    logs = profile.get("logs", [])
    if not logs:
        await message.answer(get_text(profile, "no_data"), parse_mode="Markdown")
        return

    s = STRINGS.get(profile.get("lang", "uk"), STRINGS["uk"])
    ctx = build_sleep_context(profile)

    buttons = [
        [InlineKeyboardButton(text="7 днів", callback_data="stats_days_7"),
         InlineKeyboardButton(text="14 днів", callback_data="stats_days_14"),
         InlineKeyboardButton(text="30 днів", callback_data="stats_days_30")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        get_text(profile, "stats_title", days=7),
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("stats_days_"))
async def process_stats_days(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    try:
        days = int(callback.data.replace("stats_days_", ""))
    except ValueError:
        days = 7
    if days not in (7, 14, 30):
        days = 7
    await callback.message.edit_text(
        await _render_stats(profile, days),
        parse_mode="Markdown"
    )
    await callback.answer()

async def _render_stats(profile, days):
    logs = profile.get("logs", [])
    ctx = build_sleep_context(profile)
    t = sleep_logic.analyze_trends(ctx, logs, days)

    if t["count"] == 0:
        return get_text(profile, "stats_title", days=days) + "\n\n" + get_text(profile, "no_data")

    lines = [get_text(profile, "stats_title", days=days)]
    lines.append(get_text(profile, "stats_count", count=t["count"]))
    if t["avg_duration"] is not None:
        lines.append(get_text(profile, "avg_duration", value=sleep_logic.duration_to_text(t["avg_duration"])))
    if t["avg_score"] is not None:
        lines.append(get_text(profile, "avg_score", value=t["avg_score"]))
    if t["avg_bedtime"]:
        lines.append(get_text(profile, "avg_bedtime", value=t["avg_bedtime"]))
    if t["avg_waketime"]:
        lines.append(get_text(profile, "avg_waketime", value=t["avg_waketime"]))
    if t["best"]:
        lines.append(get_text(profile, "best_day", date=t["best"]["date"], score=t["best"]["score"]))
    if t["worst"]:
        lines.append(get_text(profile, "worst_day", date=t["worst"]["date"], score=t["worst"]["score"]))
    if t["stability"]:
        stability_key = {"high": "stability_high", "medium": "stability_medium", "low": "stability_low"}[t["stability"]]
        lines.append(get_text(profile, "stability", value=get_text(profile, stability_key)))

    patterns = sleep_logic.find_patterns(ctx, logs, min(days, 14))
    if patterns:
        lines.append(f"\n{get_text(profile, 'patterns_title')}")
        for p in patterns:
            diff = abs(p["score_diff"])
            lines.append(f"• {get_text(profile, 'pattern_' + p['label'], diff=diff)}")

    recs = sleep_logic.build_recommendations(ctx, logs)
    if recs:
        lines.append(f"\n{get_text(profile, 'rec_title')}")
        for r in recs:
            lines.append(f"• {get_text(profile, r)}")

    return "\n".join(lines)

# --- 💬 SUPPORT ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_support"], STRINGS["en"]["btn_support"], STRINGS["ru"]["btn_support"]]))
async def process_support(message: types.Message, state: FSMContext):
    """Головне меню підтримки."""
    profile = get_user_profile(message.from_user.id)
    text = get_text(profile, "support_title")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(profile, "support_cat_bug"), callback_data="support_cat_bug")],
        [InlineKeyboardButton(text=get_text(profile, "support_cat_payment"), callback_data="support_cat_payment")],
        [InlineKeyboardButton(text=get_text(profile, "support_cat_question"), callback_data="support_cat_question")],
        [InlineKeyboardButton(text=get_text(profile, "back"), callback_data="support_back")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("support_cat_"))
async def process_support_category(callback: CallbackQuery, state: FSMContext):
    """Обрано категорію звернення."""
    profile = get_user_profile(callback.from_user.id)
    cat = callback.data.replace("support_cat_", "")
    cat_title = get_text(profile, f"support_cat_{cat}")
    await state.update_data(support_category=cat)
    text = get_text(profile, "support_ask_message", category=cat_title)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(profile, "back"), callback_data="support_back_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(SupportState.waiting_for_message)
    await callback.answer()

@dp.callback_query(F.data == "support_back_main")
async def process_support_back_main(callback: CallbackQuery, state: FSMContext):
    """Повернення до головного меню підтримки з вводу повідомлення."""
    await state.clear()
    profile = get_user_profile(callback.from_user.id)
    text = get_text(profile, "support_title")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(profile, "support_cat_bug"), callback_data="support_cat_bug")],
        [InlineKeyboardButton(text=get_text(profile, "support_cat_payment"), callback_data="support_cat_payment")],
        [InlineKeyboardButton(text=get_text(profile, "support_cat_question"), callback_data="support_cat_question")],
        [InlineKeyboardButton(text=get_text(profile, "back"), callback_data="support_back")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "support_back")
async def process_support_back(callback: CallbackQuery):
    """Повернення до головного меню з підтримки."""
    profile = get_user_profile(callback.from_user.id)
    await callback.message.delete()
    await callback.message.answer(
        get_text(profile, "support_back_hint"),
        reply_markup=get_main_keyboard(profile, is_sleeping=bool(profile.get("active_sleep_start"))),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(SupportState.waiting_for_message)
async def process_support_message(message: types.Message, state: FSMContext):
    """Отримання повідомлення користувача для підтримки."""
    profile = get_user_profile(message.from_user.id)
    data = await state.get_data()
    category = data.get("support_category", "question")
    await state.clear()

    tid = create_ticket(message.from_user.id, category, message.text)
    track_event(profile, "support_ticket_created")
    save_user_profile(message.from_user.id, profile)

    # Повідомлення адмінам
    ticket = get_ticket(tid)
    cat_title = get_text(profile, f"support_cat_{category}")
    username = profile.get("username") or message.from_user.username or f"User_{message.from_user.id}"
    admin_text = (
        f"🎫 <b>Нове звернення #{tid}</b>\n\n"
        f"👤 <b>Користувач:</b> @{html.escape(username)} (ID: <code>{message.from_user.id}</code>)\n"
        f"🏷 <b>Категорія:</b> {html.escape(cat_title)}\n"
        f"📅 <b>Час:</b> <i>{ticket['created_at']}</i>\n\n"
        f"📝 <b>Повідомлення:</b>\n{html.escape(message.text)}"
    )
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Відповісти в адмінці", callback_data=f"admin_support_view_{tid}")]
    ])

    # Надсилаємо в адмін-групу та адмінам
    sent = False
    if ADMIN_GROUP_ID:
        try:
            await bot.send_message(chat_id=ADMIN_GROUP_ID, text=admin_text, reply_markup=admin_kb, parse_mode="HTML")
            sent = True
        except Exception:
            pass
    if not sent:
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=admin_kb, parse_mode="HTML")
            except Exception:
                pass

    # Підтвердження користувачу
    await message.answer(
        f"{get_text(profile, 'support_received')}\n\n📨 <b>Ticket:</b> <code>#{tid}</code>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(profile, is_sleeping=bool(profile.get("active_sleep_start")))
    )

# --- 🎯 ЦІЛІ ---
GOAL_BEDTIME_PRESETS = ["21:30", "22:00", "22:30", "23:00", "23:30", "00:00", "00:30", "01:00"]
GOAL_WAKETIME_PRESETS = ["05:30", "06:00", "06:30", "07:00", "07:30", "08:00", "08:30", "09:00", "10:00"]
GOAL_DURATION_PRESETS = [6.5, 7.0, 7.5, 8.0, 8.5, 9.0]

@dp.message(F.text.in_([STRINGS["uk"]["btn_goals"], STRINGS["en"]["btn_goals"], STRINGS["ru"]["btn_goals"]]))
async def process_goals(message: types.Message):
    if not await require_premium(message):
        return
    profile = get_user_profile(message.from_user.id)
    s = STRINGS.get(profile.get("lang", "uk"), STRINGS["uk"])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌅 " + s.get("goal_btn_bedtime", ""), callback_data="goal_set_bedtime"),
         InlineKeyboardButton(text="☀️ " + s.get("goal_btn_waketime", ""), callback_data="goal_set_waketime")],
        [InlineKeyboardButton(text="⏱ " + s.get("goal_btn_duration", ""), callback_data="goal_set_duration")],
    ])
    await message.answer(await _render_goals(profile), reply_markup=kb, parse_mode="Markdown")

async def _render_goals(profile):
    ctx = build_sleep_context(profile)
    t = sleep_logic.analyze_trends(ctx, profile.get("logs", []), 7)
    avg_bedtime = t["avg_bedtime"] or "—"
    avg_waketime = t["avg_waketime"] or "—"
    avg_duration = sleep_logic.duration_to_text(t["avg_duration"]) if t["avg_duration"] is not None else "—"
    body = get_text(profile, "goals_body",
                    bedtime=profile.get("goal_bedtime", "23:30"),
                    waketime=profile.get("goal_waketime", "07:30"),
                    duration=profile.get("goal_duration", 8),
                    avg_bedtime=avg_bedtime,
                    avg_waketime=avg_waketime,
                    avg_duration=avg_duration)
    return get_text(profile, "goals_title") + "\n\n" + body

@dp.callback_query(F.data == "goal_set_bedtime")
async def process_goal_set_bedtime(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    buttons = [[InlineKeyboardButton(text=t, callback_data=f"goal_bedtime_{t.replace(':', '_')}")] for t in GOAL_BEDTIME_PRESETS]
    buttons.append([InlineKeyboardButton(text=get_text(profile, "back"), callback_data="goal_back")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback.message.edit_text(get_text(profile, "goal_set_bedtime"), reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data == "goal_set_waketime")
async def process_goal_set_waketime(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    buttons = [[InlineKeyboardButton(text=t, callback_data=f"goal_waketime_{t.replace(':', '_')}")] for t in GOAL_WAKETIME_PRESETS]
    buttons.append([InlineKeyboardButton(text=get_text(profile, "back"), callback_data="goal_back")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback.message.edit_text(get_text(profile, "goal_set_waketime"), reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data == "goal_set_duration")
async def process_goal_set_duration(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    buttons = [[InlineKeyboardButton(text=get_text(profile, "goal_hours", value=d), callback_data=f"goal_duration_{d}")] for d in GOAL_DURATION_PRESETS]
    buttons.append([InlineKeyboardButton(text=get_text(profile, "back"), callback_data="goal_back")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback.message.edit_text(get_text(profile, "goal_set_duration"), reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data.startswith("goal_bedtime_"))
async def process_goal_save_bedtime(callback: CallbackQuery):
    time_str = callback.data.replace("goal_bedtime_", "").replace("_", ":")
    profile = get_user_profile(callback.from_user.id)
    profile["goal_bedtime"] = time_str
    save_user_profile(callback.from_user.id, profile)
    await callback.answer(get_text(profile, "goal_saved"))
    await _goals_render_after_edit(callback, profile)

@dp.callback_query(F.data.startswith("goal_waketime_"))
async def process_goal_save_waketime(callback: CallbackQuery):
    time_str = callback.data.replace("goal_waketime_", "").replace("_", ":")
    profile = get_user_profile(callback.from_user.id)
    profile["goal_waketime"] = time_str
    save_user_profile(callback.from_user.id, profile)
    await callback.answer(get_text(profile, "goal_saved"))
    await _goals_render_after_edit(callback, profile)

@dp.callback_query(F.data.startswith("goal_duration_"))
async def process_goal_save_duration(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    try:
        duration = float(callback.data.replace("goal_duration_", ""))
    except ValueError:
        await callback.answer(get_text(profile, "invalid_value"), show_alert=True)
        return
    if duration not in GOAL_DURATION_PRESETS:
        await callback.answer(get_text(profile, "invalid_value"), show_alert=True)
        return
    profile["goal_duration"] = duration
    save_user_profile(callback.from_user.id, profile)
    await callback.answer(get_text(profile, "goal_saved"))
    await _goals_render_after_edit(callback, profile)

@dp.callback_query(F.data == "goal_back")
async def process_goal_back(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    await _goals_render_after_edit(callback, profile)

async def _goals_render_after_edit(callback: CallbackQuery, profile=None):
    profile = profile or get_user_profile(callback.from_user.id)
    s = STRINGS.get(profile.get("lang", "uk"), STRINGS["uk"])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌅 " + s.get("goal_btn_bedtime", ""), callback_data="goal_set_bedtime"),
         InlineKeyboardButton(text="☀️ " + s.get("goal_btn_waketime", ""), callback_data="goal_set_waketime")],
        [InlineKeyboardButton(text="⏱ " + s.get("goal_btn_duration", ""), callback_data="goal_set_duration")],
    ])
    try:
        await callback.message.edit_text(await _render_goals(profile), reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()

@dp.message(F.text.in_([STRINGS["uk"]["btn_reminders"], STRINGS["en"]["btn_reminders"], STRINGS["ru"]["btn_reminders"]]))
async def process_reminders(message: types.Message):
    if not await require_premium(message):
        return
    profile = get_user_profile(message.from_user.id)
    await message.answer(await _render_reminders_menu(profile), reply_markup=_reminders_menu_kb(profile), parse_mode="Markdown")

def _reminders_menu_kb(profile):
    rem = get_reminders(profile)
    s = STRINGS.get(profile.get("lang", "uk"), STRINGS["uk"])
    buttons = []
    for rtype in ("wind_down", "log", "morning", "goal"):
        cfg = rem.get(rtype) or {}
        state_str = s.get("rem_on") if cfg.get("enabled") else s.get("rem_off")
        buttons.append([InlineKeyboardButton(
            text=f"{s.get('rem_type_' + rtype)} — {state_str}",
            callback_data=f"rem_open_{rtype}")])
    buttons.append([InlineKeyboardButton(text="🌍 " + s.get("rem_type_tz", "Часовий пояс"), callback_data="rem_tz")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def _render_reminders_menu(profile):
    rem = get_reminders(profile)
    s = STRINGS.get(profile.get("lang", "uk"), STRINGS["uk"])
    lines = [s.get("rem_title")]
    zone = timeutil.get_user_timezone(profile)
    lines.append(get_text(profile, "rem_tz_line", zone=zone.key))
    return "\n\n".join(lines)

@dp.callback_query(F.data.startswith("rem_open_"))
async def process_reminder_open(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    rtype = callback.data.replace("rem_open_", "")
    rem = get_reminders(profile)
    cfg = rem.get(rtype) or {}
    s = STRINGS.get(profile.get("lang", "uk"), STRINGS["uk"])
    status = s.get("rem_enabled") if cfg.get("enabled") else s.get("rem_disabled")
    text = (
        f"{s.get('rem_type_' + rtype)} — {status}\n"
        f"{get_text(profile, 'rem_open_time', time=cfg.get('time', '—'))}"
    )
    buttons = [
        [InlineKeyboardButton(
            text=(s.get("rem_disabled") if cfg.get("enabled") else s.get("rem_enabled")),
            callback_data=f"rem_toggle_{rtype}")],
        [InlineKeyboardButton(text="⏰ " + s.get("rem_time_title", "Змінити час"), callback_data=f"rem_time_{rtype}")],
        [InlineKeyboardButton(text=get_text(profile, "back"), callback_data="rem_back")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data == "rem_back")
async def process_reminder_back(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    try:
        await callback.message.edit_text(
            await _render_reminders_menu(profile),
            reply_markup=_reminders_menu_kb(profile),
            parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data.startswith("rem_toggle_"))
async def process_reminder_toggle(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    rtype = callback.data.replace("rem_toggle_", "")
    rem = get_reminders(profile)
    if rtype not in rem or not isinstance(rem[rtype], dict):
        await callback.answer(get_text(profile, "invalid_type"), show_alert=True)
        return
    rem[rtype]["enabled"] = not rem[rtype].get("enabled", False)
    profile["reminders"] = rem
    save_user_profile(callback.from_user.id, profile)

    s = STRINGS.get(profile.get("lang", "uk"), STRINGS["uk"])
    status = s.get("rem_enabled") if rem[rtype]["enabled"] else s.get("rem_disabled")
    await callback.answer(status)
    try:
        await callback.message.edit_text(
            await _render_reminders_menu(profile),
            reply_markup=_reminders_menu_kb(profile),
            parse_mode="Markdown")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("rem_time_"))
async def process_reminder_time(callback: CallbackQuery, state: FSMContext):
    profile = get_user_profile(callback.from_user.id)
    rtype = callback.data.replace("rem_time_", "")
    s = STRINGS.get(profile.get("lang", "uk"), STRINGS["uk"])
    times = ["21:00", "21:30", "22:00", "22:30", "23:00", "23:30"] if rtype == "wind_down" else (
        ["23:00", "23:30", "00:00", "00:30", "01:00"] if rtype == "goal" else
        ["06:30", "07:00", "07:30", "08:00", "08:30", "09:00", "10:00"])
    buttons = [[InlineKeyboardButton(text=t, callback_data=f"rem_settime_{rtype}_{t}")] for t in times]
    buttons.append([InlineKeyboardButton(text=get_text(profile, "back"), callback_data="rem_back")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback.message.edit_text(s.get("rem_time_title"), reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data.startswith("rem_settime_"))
async def process_reminder_settime(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    data_part = callback.data[len("rem_settime_"):]
    if "_" not in data_part:
        await callback.answer(get_text(profile, "invalid_data"), show_alert=True)
        return
    rtype, time_raw = data_part.rsplit("_", 1)
    time_str = time_raw.replace("_", ":")
    if ":" not in time_str:
        await callback.answer(get_text(profile, "invalid_time"), show_alert=True)
        return
    profile = get_user_profile(callback.from_user.id)
    rem = get_reminders(profile)
    if rtype not in rem or not isinstance(rem[rtype], dict):
        await callback.answer(get_text(profile, "invalid_type"), show_alert=True)
        return
    rem[rtype]["time"] = time_str
    rem[rtype]["enabled"] = True
    profile["reminders"] = rem
    save_user_profile(callback.from_user.id, profile)

    s = STRINGS.get(profile.get("lang", "uk"), STRINGS["uk"])
    await callback.answer(get_text(profile, "rem_time_saved", time=time_str))
    try:
        await callback.message.edit_text(
            await _render_reminders_menu(profile),
            reply_markup=_reminders_menu_kb(profile),
            parse_mode="Markdown")
    except Exception:
        pass

@dp.callback_query(F.data == "rem_tz")
async def process_reminder_tz(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    s = STRINGS.get(profile.get("lang", "uk"), STRINGS["uk"])
    offsets = [-12, -11, -10, -9, -8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    buttons = [[InlineKeyboardButton(text=f"UTC{off:+d}", callback_data=f"rem_settz_{off}")] for off in offsets]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback.message.edit_text(s.get("rem_tz_title"), reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data.startswith("rem_settz_"))
async def process_reminder_settz(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    try:
        offset = int(callback.data.replace("rem_settz_", ""))
    except ValueError:
        await callback.answer(get_text(profile, "invalid_value"), show_alert=True)
        return
    if not -12 <= offset <= 12:
        await callback.answer(get_text(profile, "invalid_value"), show_alert=True)
        return
    profile = get_user_profile(callback.from_user.id)
    rem = get_reminders(profile)
    rem["timezone_offset"] = offset
    profile["reminders"] = rem
    # Синхронізуємо IANA-timezone профілю з обраним зміщенням
    # (для України +3 → Europe/Kyiv; інакше — best-effort зона зі зміщенням).
    profile["timezone"] = timeutil.OFFSET_TO_ZONE.get(offset, timeutil.DEFAULT_TIMEZONE)
    save_user_profile(callback.from_user.id, profile)

    await callback.answer(get_text(profile, "rem_tz_saved", offset=offset))
    try:
        await callback.message.edit_text(
            await _render_reminders_menu(profile),
            reply_markup=_reminders_menu_kb(profile),
            parse_mode="Markdown")
    except Exception:
        pass

# --- 🏆 ДОСЯГНЕННЯ ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_achievements"], STRINGS["en"]["btn_achievements"], STRINGS["ru"]["btn_achievements"]]))
async def process_achievements(message: types.Message):
    if not await require_premium(message):
        return
    profile = get_user_profile(message.from_user.id)
    logs = profile.get("logs", [])
    xp = profile.get("xp", 0) or sleep_logic.compute_xp(logs)
    level = sleep_logic.level_from_xp(xp)
    progress = int(sleep_logic.level_progress(xp) * 100)
    streak = sleep_logic.compute_streak(logs)
    achieved = set(profile.get("achievements", []))

    lines = [get_text(profile, "ach_title",
                      level=level, xp=xp, next=level + 1, progress=progress, streak=streak)]
    for a in sleep_logic.ACHIEVEMENTS:
        done = a["id"] in achieved
        mark = "✅" if done else "🔒"
        lines.append(f"{mark} {get_text(profile, 'ach_' + a['id'])}")

    await message.answer("\n".join(lines), parse_mode="Markdown")
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

BOT_COURSE_DAYS_EN = {
    1: {
        "title": "☀️ Day 1: Light Biohacking & Melatonin",
        "text": (
            "🎓 **Lesson 1: Light Biohacking & Melatonin**\n\n"
            "🧠 **Why do we struggle to fall asleep?**\n"
            "The sleep hormone *melatonin* is produced by the pineal gland only in darkness. Bright blue light from phone screens and bulbs blocks melatonin production by almost 80%!\n\n"
            "⚡ **Today's practical task:**\n"
            "1️⃣ **In the morning:** Get 10-15 minutes of sunlight right after waking up (resets your biological clock).\n"
            "2️⃣ **In the evening:** 45 minutes before bed, dim the bright lights, turn on 'Night Shift' on your phone and put the screens away."
        )
    },
    2: {
        "title": "🧘 Day 2: US Navy 2-Min Technique",
        "text": (
            "🎓 **Lesson 2: Military sleep technique (US Navy)**\n\n"
            "🧘 **Fall asleep in 120 seconds in any conditions:**\n"
            "1️⃣ **Relax your face:** Close your eyes, relax your forehead, jaw and tongue.\n"
            "2️⃣ **Drop your shoulders:** Let your shoulders sink fully into the mattress.\n"
            "3️⃣ **Exhale:** Fully relax your chest and legs from hips to feet.\n"
            "4️⃣ **Clear your mind:** Imagine yourself in a boat on a calm lake under the stars. Repeat: *'Don't think, don't think, don't think'* (10 sec)."
        )
    },
    3: {
        "title": "🫁 Day 3: 4-7-8 Technique & Calm",
        "text": (
            "🎓 **Lesson 3: Slowing the heart rate (4-7-8)**\n\n"
            "🫁 **The secret of activating the vagus nerve:**\n"
            "1️⃣ Inhale through the nose — **4 seconds**\n"
            "2️⃣ Hold your breath — **7 seconds**\n"
            "3️⃣ Slow exhale through the mouth — **8 seconds**\n\n"
            "✨ Repeat 4 cycles. This lowers your pulse and cortisol level in 2 minutes!"
        )
    },
    4: {
        "title": "☕ Day 4: Caffeine Window & Dinner",
        "text": (
            "🎓 **Lesson 4: Caffeine timeout & Dinner**\n\n"
            "☕ **Caffeine half-life = 6 hours!**\n"
            "• Last cup of coffee — no later than 7-8 hours before sleep.\n"
            "• Dinner 2.5-3 hours before bed (avoid heavy fatty meat).\n"
            "• Snack: chamomile tea, a handful of almonds or a banana."
        )
    },
    5: {
        "title": "📝 Day 5: 20-Min Rule & 'Worry Box'",
        "text": (
            "🎓 **Lesson 5: The 20-minute rule & 'Worry Box'**\n\n"
            "💡 **If you can't fall asleep after 20 minutes:**\n"
            "Get out of bed, sit in a chair with dim light and read a book. Return to bed only when you feel sleepy!\n\n"
            "📝 **'Worry Box' (Brain Dump):**\n"
            "Write down all anxious thoughts and tomorrow's tasks in a notebook one hour before bed."
        )
    },
    6: {
        "title": "❄️ Day 6: Bedroom Microclimate (18-20°C)",
        "text": (
            "🎓 **Lesson 6: Bedroom microclimate & Deep sleep**\n\n"
            "🌡️ **Temperature 18-20°C:** To fall asleep, your body temperature must drop by 1°C.\n"
            "💨 **Ventilation:** 10 minutes before bed.\n"
            "🕶️ **Complete darkness:** Sleep mask or blackout curtains.\n"
            "🛁 **Warm shower 1 hour before bed:** Speeds up body cooling after leaving the bath."
        )
    },
    7: {
        "title": "📜 Day 7: Personal Sleep Ritual",
        "text": (
            "🎓 **Lesson 7: Personal evening ritual & Finale**\n\n"
            "🎉 **Congratulations! You have completed the 7-day sleep intensive!**\n\n"
            "✨ **Your evening wind-down checklist:**\n"
            "✅ Ventilated the bedroom (18-20°C)\n"
            "✅ Turned off screens 45 min before bed\n"
            "✅ Wrote down anxious thoughts in a notebook\n"
            "✅ Did the 4-7-8 breathing and US Navy relaxation"
        )
    }
}

BOT_COURSE_DAYS_RU = {
    1: {
        "title": "☀️ День 1: Световой биохакинг & Мелатонин",
        "text": (
            "🎓 **Урок 1: Световой биохакинг & Мелатонин**\n\n"
            "🧠 **Почему мы тяжело засыпаем?**\n"
            "Гормон сна *мелатонин* выделяется эпифизом только в темноте. Яркий синий свет экранов смартфонов и лампочек блокирует выделение мелатонина почти на 80%!\n\n"
            "⚡ **Практическое задание на сегодня:**\n"
            "1️⃣ **Утром:** Получите 10-15 мин солнечного света сразу после подъёма (перезапуск биологических часов).\n"
            "2️⃣ **Вечером:** За 45 мин до сна выключите яркое освещение, включите 'Night Shift' на телефоне и отложите экраны."
        )
    },
    2: {
        "title": "🧘 День 2: US Navy 2-Min Technique",
        "text": (
            "🎓 **Урок 2: Военная техника засыпания (US Navy)**\n\n"
            "🧘 **Засыпай за 120 секунд в любых условиях:**\n"
            "1️⃣ **Расслабление лица:** Закройте глаза, расслабьте лоб, челюсть и язык.\n"
            "2️⃣ **Опустите плечи:** Позвольте плечам полностью провалиться в матрас.\n"
            "3️⃣ **Выдохните:** Полностью расслабьте грудь и ноги от бёдер до ступней.\n"
            "4️⃣ **Очистите разум:** Представьте себя в лодке на тихом озере под звёздами. Повторяйте: *'Не думай, не думай, не думай'* (10 сек)."
        )
    },
    3: {
        "title": "🫁 День 3: Техника 4-7-8 & Спокойствие",
        "text": (
            "🎓 **Урок 3: Замедление сердечного ритма (4-7-8)**\n\n"
            "🫁 **Секрет активации блуждающего нерва:**\n"
            "1️⃣ Вдох носом — **4 секунды**\n"
            "2️⃣ Задержите дыхание — **7 секунд**\n"
            "3️⃣ Медленный выдох ртом — **8 секунд**\n\n"
            "✨ Повторите 4 цикла. Это снижает пульс и уровень кортизола за 2 минуты!"
        )
    },
    4: {
        "title": "☕ День 4: Кофеиновое окно & Ужин",
        "text": (
            "🎓 **Урок 4: Кофеиновый тайм-аут & Ужин**\n\n"
            "☕ **Период полувыведения кофеина = 6 часов!**\n"
            "• Последняя чашка кофе — не позже чем за 7-8 часов до сна.\n"
            "• Ужин за 2.5-3 часа до сна (избегайте тяжёлого жирного мяса).\n"
            "• Перекус: ромашковый чай, горсть миндаля или банан."
        )
    },
    5: {
        "title": "📝 День 5: Правило 20 мин & 'Коробка тревог'",
        "text": (
            "🎓 **Урок 5: Правило 20 минут & 'Коробка тревог'**\n\n"
            "💡 **Если не засыпается больше 20 минут:**\n"
            "Встаньте с кровати, сядьте в кресло при приглушённом свете и почитайте книгу. Возвращайтесь в кровать только при появлении сонливости!\n\n"
            "📝 **'Коробка тревог' (Brain Dump):**\n"
            "Выпишите все тревожные мысли и дела на завтра в блокнот за 1 час до сна."
        )
    },
    6: {
        "title": "❄️ День 6: Микроклимат спальни (18-20°C)",
        "text": (
            "🎓 **Урок 6: Микроклимат спальни & Глубокий сон**\n\n"
            "🌡️ **Температура 18-20°C:** Для засыпания температура тела должна упасть на 1°C.\n"
            "💨 **Проветривание:** 10 минут перед сном.\n"
            "🕶️ **Полная темнота:** Маска для сна или шторы Blackout.\n"
            "🛁 **Тёплый душ за 1 час до сна:** Ускоряет охлаждение тела после выхода из ванной."
        )
    },
    7: {
        "title": "📜 День 7: Персональный ритуал сна",
        "text": (
            "🎓 **Урок 7: Персональный вечерний ритуал & Финал**\n\n"
            "🎉 **Поздравляем! Вы завершили 7-дневный интенсив сна!**\n\n"
            "✨ **Ваш вечерний чек-лист перед сном:**\n"
            "✅ Проветрил спальню (18-20°C)\n"
            "✅ Выключил экраны за 45 мин\n"
            "✅ Выписал тревожные мысли в блокнот\n"
            "✅ Выполнил дыхание 4-7-8 и US Navy релаксацию"
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
    text, kb = render_course_list(profile)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "pay_mono_link")
async def process_pay_mono_link(callback: CallbackQuery, state: FSMContext):
    profile = get_user_profile(callback.from_user.id)
    track_event(profile, "buy_click")
    save_user_profile(callback.from_user.id, profile)
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
    # Час у локальній зоні користувача, який надіслав квитанцію.
    sender_profile = get_user_profile(user_id)
    now_str = timeutil.local_datetime_str(timeutil.utc_now(), timeutil.get_user_timezone(sender_profile))

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
    track_event(user_profile, "receipt_submitted")
    save_user_profile(user_id, user_profile)
    await message.answer(
        get_text(user_profile, "receipt_received"),
        parse_mode="Markdown"
    )

@dp.message(PaymentReceiptState.waiting_for_receipt)
async def process_receipt_not_photo(message: types.Message):
    profile = get_user_profile(message.from_user.id)
    await message.answer(get_text(profile, "receipt_not_photo"), parse_mode="Markdown")

# --- ОБРОБНИКИ КНОПОК ПРИЙНЯТИ / ВІДХИЛИТИ В АДМІН-ГРУПІ ---
def _is_admin(user_id) -> bool:
    return user_id in ADMIN_IDS

@dp.callback_query(F.data.startswith("adm_approve_"))
async def process_admin_approve_payment(callback: CallbackQuery):
    # БЕЗПЕКА: лише адміністратор може підтверджувати оплату.
    # Раніше цю кнопку міг "натиснути" будь-хто, сформувавши callback_data вручну.
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ заборонено", show_alert=True)
        return
    try:
        target_user_id = int(callback.data.replace("adm_approve_", "").strip())
    except (ValueError, TypeError):
        await callback.answer("⚠️ Некоректні дані", show_alert=True)
        return
    admin_name = callback.from_user.username or callback.from_user.first_name
    now_str = timeutil.utc_now().strftime("%Y-%m-%d %H:%M")

    # Активація доступу
    profile = get_user_profile(target_user_id)
    track_event(profile, "payment_approved")
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

    # Premium onboarding: що тепер доступно + CTA «Розпочати День 1»
    try:
        premium_text = (
            f"{get_text(profile, 'prem_unlocked')}\n\n"
            f"{get_text(profile, 'prem_now_title')}\n"
            f"{get_text(profile, 'prem_item_analysis')}\n"
            f"{get_text(profile, 'prem_item_coach')}\n"
            f"{get_text(profile, 'prem_item_course')}\n"
            f"{get_text(profile, 'prem_item_goals')}\n"
            f"{get_text(profile, 'prem_item_stats')}"
        )
        prem_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text(profile, "cta_day1"), callback_data="prem_start_day1")]
        ])
        await bot.send_message(
            chat_id=target_user_id,
            text=premium_text,
            reply_markup=prem_kb,
            parse_mode="Markdown"
        )
        await bot.send_message(
            chat_id=target_user_id,
            text=get_text(profile, "prem_menu_hint"),
            reply_markup=get_main_keyboard(profile, is_sleeping=False),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Failed to notify user {target_user_id}: {e}")

    await callback.answer("✅ Оплату підтверджено та доступ активовано!", show_alert=True)

@dp.callback_query(F.data.startswith("adm_reject_"))
async def process_admin_reject_payment(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ заборонено", show_alert=True)
        return
    try:
        target_user_id = int(callback.data.replace("adm_reject_", "").strip())
    except (ValueError, TypeError):
        await callback.answer("⚠️ Некоректні дані", show_alert=True)
        return
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
    track_event(profile, "payment_rejected")
    save_user_profile(target_user_id, profile)
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

    text, kb = build_paywall(profile)
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
    avg_activity = round(total_logs / total_users, 1) if total_users > 0 else 0

    now = timeutil.utc_now()
    today_str = now.strftime("%Y-%m-%d")
    week_ago = (now - timedelta(days=7)).isoformat(timespec="minutes")

    def _registered(p):
        r = p.get("registered_at", "")
        return r[:10] == today_str

    def _registered_week(p):
        r = p.get("registered_at", "")
        return r and r >= week_ago[:16]

    def _active(p):
        a = p.get("last_active", "")
        return bool(a) and a >= week_ago[:16]

    new_today = sum(1 for p in all_data.values() if _registered(p))
    new_week = sum(1 for p in all_data.values() if _registered_week(p))
    active = sum(1 for p in all_data.values() if _active(p))

    # Воронка продажів
    def _funnel_sum(event):
        return sum(p.get("funnel", {}).get(event, 0) for p in all_data.values())

    paywall_views = _funnel_sum("paywall_view")
    buy_clicks = _funnel_sum("buy_click")
    receipts = _funnel_sum("receipt_submitted")
    approved = _funnel_sum("payment_approved")
    rejected = _funnel_sum("payment_rejected")

    # Підтримка
    open_tickets = len(get_open_tickets())
    all_tickets = len(load_tickets())

    text = (
        f"👑 <b>Панель Управління Адміністратора</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Аналітика Проєкту:</b>\n"
        f"• 👥 Всього користувачів: <b>{total_users}</b>\n"
        f"• 🆕 Нові за сьогодні: <b>{new_today}</b>\n"
        f"• 🆕 Нові за тиждень: <b>{new_week}</b>\n"
        f"• ✅ Активні за тиждень: <b>{active}</b>\n"
        f"• 💳 Premium-користувачі: <b>{total_buyers}</b>\n"
        f"• 💰 Дохід: <b>{revenue} грн</b>\n"
        f"• 📈 Конверсія в покупку: <b>{conversion}%</b>\n"
        f"• 📝 Записів сну: <b>{total_logs}</b> (середня активність: <b>{avg_activity}</b>)\n\n"
        f"🛒 <b>Воронка продажів:</b>\n"
        f"• 👁 Переглядів пейволу: <b>{paywall_views}</b>\n"
        f"• 💳 Кліків «Купити»: <b>{buy_clicks}</b>\n"
        f"• 📸 Надіслано квитанцій: <b>{receipts}</b>\n"
        f"• ✅ Підтверджено: <b>{approved}</b>\n"
        f"• ❌ Відхилено: <b>{rejected}</b>\n\n"
        f"🎫 <b>Підтримка:</b>\n"
        f"• 📬 Відкритих звернень: <b>{open_tickets}</b>\n"
        f"• 📦 Всього звернень: <b>{all_tickets}</b>\n\n"
        f"Оберіть потрібний розділ меню нижче:"
    )

    buttons = [
        [InlineKeyboardButton(text="👥 Список покупців", callback_data="admin_buyers")],
        [InlineKeyboardButton(text="🔍 Пошук користувача", callback_data="admin_search_info"),
         InlineKeyboardButton(text="⚡ Видати доступ", callback_data="admin_grant_info")],
        [InlineKeyboardButton(text="🎫 Підтримка", callback_data="admin_support"),
         InlineKeyboardButton(text="📢 Масова розсилка", callback_data="admin_broadcast_info")],
        [InlineKeyboardButton(text="🔄 Оновити дані", callback_data="admin_refresh")]
    ]
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ <b>Доступ заборонено.</b> Команда доступна лише власникові бота.", parse_mode="HTML")
        return
    text, kb = build_admin_dashboard()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_search_info")
async def process_admin_search_info(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return
    text = (
        "🔍 <b>Пошук користувача</b>\n\n"
        "Введіть команду:\n"
        "<code>/user TELEGRAM_USER_ID</code>\n"
        "<i>(наприклад: /user 1373248099)</i>\n\n"
        "Доступна інформація: ID, username, дата реєстрації, Premium-статус, "
        "остання активність, кількість записів сну, воронка оплат."
    )
    buttons = [[InlineKeyboardButton(text="🔙 Назад в Адмінку", callback_data="admin_refresh")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()

@dp.message(F.text.startswith("/user"))
async def cmd_user_info(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("⚠️ Вкажіть Telegram ID, наприклад:\n`/user 123456789`", parse_mode="Markdown")
        return

    uid = parts[1].strip()
    all_data = load_user_data()
    if uid not in all_data:
        await message.answer(f"❌ Користувач з ID `{uid}` не знайдений у базі.", parse_mode="Markdown")
        return

    p = all_data[uid]
    funnel = p.get("funnel", {})
    username = html.escape(str(p.get("username", f"User_{uid}")))
    text = (
        f"👤 <b>Інформація про користувача:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• 🆔 ID: <code>{uid}</code>\n"
        f"• 🧑 Username: @{username}\n"
        f"• 🌐 Мова: <b>{p.get('lang', 'uk')}</b>\n"
        f"• 📅 Реєстрація: <i>{html.escape(str(p.get('registered_at', 'Невідомо')))}</i>\n"
        f"• ⏱ Остання активність: <i>{html.escape(str(p.get('last_active', 'Невідомо')))}</i>\n"
        f"• 💳 Premium: <b>{'✅ Так' if p.get('is_premium') else '❌ Ні'}</b>\n"
        f"• 📝 Записів сну: <b>{len(p.get('logs', []))}</b>\n"
        f"• 🏆 Прогрес курсу: <b>{len(p.get('course_completed', []))}/7</b>\n"
        f"• 📈 XP: <b>{p.get('xp', 0)}</b>\n\n"
        f"🛒 <b>Воронка:</b>\n"
        f"👁 {funnel.get('paywall_view', 0)} | 💳 {funnel.get('buy_click', 0)} | "
        f"📸 {funnel.get('receipt_submitted', 0)} | ✅ {funnel.get('payment_approved', 0)} | "
        f"❌ {funnel.get('payment_rejected', 0)}"
    )
    await message.answer(text, parse_mode="HTML")

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

# --- АДМІН-ПАНЕЛЬ: ПІДТРИМКА ---
@dp.callback_query(F.data == "admin_support")
async def process_admin_support(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return

    tickets = get_all_tickets()
    if not tickets:
        text = "🎫 <b>Підтримка</b>\n\nЗвернень поки немає."
    else:
        lines = ["🎫 <b>Підтримка</b>\n"]
        status_emoji = {"open": "🟢", "in_progress": "🟡", "resolved": "✅"}
        for t in tickets[:15]:
            emoji = status_emoji.get(t["status"], "⚪")
            username = t.get("username") or f"User_{t['user_id']}"
            cat_name = {"bug": "🐛", "payment": "💳", "question": "❓"}.get(t["category"], t["category"])
            lines.append(f"{emoji} <b>#{t['id']}</b> | {cat_name} | @{html.escape(username)} | <i>{t['created_at']}</i>")
        text = "\n".join(lines)

    buttons = []
    for t in tickets[:15]:
        buttons.append([InlineKeyboardButton(text=f"#{t['id']} | {t['user_id']} | {t['category']}", callback_data=f"admin_support_view_{t['id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад в Адмінку", callback_data="admin_refresh")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_support_view_"))
async def process_admin_support_view(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return
    try:
        tid = int(callback.data.replace("admin_support_view_", ""))
    except ValueError:
        await callback.answer("⚠️ Некоректний ID", show_alert=True)
        return

    ticket = get_ticket(tid)
    if not ticket:
        await callback.answer("❌ Звернення не знайдено", show_alert=True)
        return

    username = ticket.get("username") or f"User_{ticket['user_id']}"
    cat_name = {"bug": "🐛 Report a problem", "payment": "💳 Payment problem", "question": "❓ Ask a question"}.get(ticket["category"], ticket["category"])
    status_name = {"open": "🟢 Відкрите", "in_progress": "🟡 У роботі", "resolved": "✅ Вирішене"}.get(ticket["status"], ticket["status"])

    text = (
        f"🎫 <b>Звернення #{tid}</b>\n\n"
        f"👤 <b>Користувач:</b> @{html.escape(username)} (ID: <code>{ticket['user_id']}</code>)\n"
        f"🏷 <b>Категорія:</b> {cat_name}\n"
        f"📊 <b>Статус:</b> {status_name}\n"
        f"📅 <b>Створено:</b> <i>{ticket['created_at']}</i>\n"
        f"🔄 <b>Оновлено:</b> <i>{ticket['updated_at']}</i>\n\n"
        f"📝 <b>Повідомлення:</b>\n{html.escape(ticket['message'])}"
    )
    if ticket.get("admin_reply"):
        text += f"\n\n💬 <b>Відповідь адміна:</b>\n{html.escape(ticket['admin_reply'])}"

    buttons = [
        [InlineKeyboardButton(text="💬 Відповісти", callback_data=f"admin_support_reply_{tid}")],
        [InlineKeyboardButton(text="✅ Вирішено", callback_data=f"admin_support_resolve_{tid}")],
        [InlineKeyboardButton(text="🔙 Назад до списку", callback_data="admin_support")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_support_reply_"))
async def process_admin_support_reply(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return
    try:
        tid = int(callback.data.replace("admin_support_reply_", ""))
    except ValueError:
        await callback.answer("⚠️ Некоректний ID", show_alert=True)
        return

    await state.update_data(admin_reply_tid=tid)
    await state.set_state(AdminSupportState.waiting_for_reply)
    await callback.message.edit_text(f"💬 <b>Відповідь до звернення #{tid}</b>\n\nНапишіть повідомлення для користувача:", parse_mode="HTML")
    await callback.answer()

@dp.message(AdminSupportState.waiting_for_reply)
async def process_admin_support_reply_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    tid = data.get("admin_reply_tid")
    await state.clear()

    ticket = get_ticket(tid)
    if not ticket:
        await message.answer("❌ Звернення не знайдено.")
        return

    update_ticket(tid, status="in_progress", admin_reply=message.text)

    # Надсилаємо відповідь користувачу
    try:
        user_profile = get_user_profile(int(ticket["user_id"]))
        user_text = (
            f"💬 <b>Відповідь підтримки до вашого звернення #{tid}</b>\n\n"
            f"{html.escape(message.text)}"
        )
        await bot.send_message(chat_id=int(ticket["user_id"]), text=user_text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to send admin reply to user {ticket['user_id']}: {e}")

    await message.answer(f"✅ Відповідь надіслано користувачу (Ticket #{tid}). Статус оновлено на «У роботі».")

@dp.callback_query(F.data.startswith("admin_support_resolve_"))
async def process_admin_support_resolve(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return
    try:
        tid = int(callback.data.replace("admin_support_resolve_", ""))
    except ValueError:
        await callback.answer("⚠️ Некоректний ID", show_alert=True)
        return

    update_ticket(tid, status="resolved")
    await callback.answer("✅ Звернення позначено як вирішене", show_alert=True)
    # Оновлюємо перегляд
    await process_admin_support_view(callback)

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
    profile["purchased_at"] = timeutil.utc_now().strftime("%Y-%m-%d %H:%M") + " (Admin Grant)"
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
            # Без parse_mode: спеціальні символи Markdown (_ * [ ] тощо) у тексті
            # не ламають доставку, а помилка одного користувача не зупиняє розсилку.
            await bot.send_message(chat_id=int(uid), text=broadcast_text)
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
    # Беремо перші 16 символів = "%Y-%m-%d %H:%M" (UTC-наївний формат).
    try:
        purchased_dt = datetime.strptime(purchased_raw[:16], "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return 1

    days_passed = (timeutil.utc_now() - timeutil.to_utc(purchased_dt)).days
    unlocked = 1 + max(days_passed, 0)
    return min(unlocked, 7)

def get_available_days(profile):
    """Дні, контент яких реально відкрито користувачу.

    День 1 доступний одразу після оплати/активації Trial. Кожен наступний день відкривається
    лише тоді, коли завершено попередній день І минула необхідна кількість діб
    з моменту оплати/активації (по одному дню щодоби).
    """
    if not has_premium_access(profile):
        return set()
    time_cap = get_unlocked_days(profile)
    completed = set(profile.get("course_completed", []))
    available = set()
    for day in range(1, time_cap + 1):
        if day == 1 or (day - 1) in completed:
            available.add(day)
    return available

def render_course_list(profile):
    """Список днів персонального курсу з прогресом та поступовим розблокуванням."""
    completed = profile.get("course_completed", [])
    count = len(completed)
    percent = int((count / 7) * 100)
    course = get_course_days(profile)
    available = get_available_days(profile)
    time_cap = get_unlocked_days(profile)

    text = (
        f"{get_text(profile, 'course_title_premium')}\n\n"
        f"{get_text(profile, 'course_progress', count=count, percent=percent)}\n"
        f"{get_text(profile, 'course_unlocked', count=len(available))}\n\n"
        f"{get_text(profile, 'course_intro')}"
    )
    buttons = []
    for day in range(1, 8):
        if day in available:
            icon = "✅" if day in completed else "📘"
            buttons.append([InlineKeyboardButton(text=f"{icon} {course[day]['title']}", callback_data=f"crs_day_{day}")])
        elif day > time_cap:
            # Ще не настав час (по одному дню щодоби) — показуємо замок і скільки чекати.
            wait = day - time_cap
            lock_label = get_text(profile, "course_locked_wait", day=day, wait=wait)
            buttons.append([InlineKeyboardButton(text=lock_label, callback_data="crs_locked")])
        else:
            # Час настав, але попередній день не завершено.
            lock_label = get_text(profile, "course_locked_prev", day=day, prev=day - 1)
            buttons.append([InlineKeyboardButton(text=lock_label, callback_data="crs_locked")])

    return text, InlineKeyboardMarkup(inline_keyboard=buttons)

async def deny_if_not_premium(callback: CallbackQuery, profile):
    """Блокує доступ до уроків, якщо оплату не підтверджено (або її відкликано)."""
    if has_premium_access(profile):
        return False
    await callback.answer(
        "🔒 " + get_text(profile, "paywall_locked_header").strip(),
        show_alert=True)
    text, kb = build_paywall(profile)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    return True

@dp.callback_query(F.data == "crs_locked")
async def process_course_locked(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    await callback.answer(
        get_text(profile, "course_locked_msg"),
        show_alert=True,
    )

@dp.callback_query(F.data.startswith("crs_day_"))
async def process_course_day_view(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    try:
        day_num = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer(get_text(profile, "course_stale_btn"), show_alert=True)
        return
    if day_num < 1 or day_num > 7:
        await callback.answer(get_text(profile, "course_stale_btn"), show_alert=True)
        return
    if await deny_if_not_premium(callback, profile):
        return

    # Захист від відкриття ще заблокованого дня (наприклад, через застарілу кнопку).
    if day_num not in get_available_days(profile):
        await callback.answer(
            get_text(profile, "course_not_open"),
            show_alert=True,
        )
        return

    completed = profile.get("course_completed", [])
    is_done = day_num in completed

    course = get_course_days(profile)
    text = course.get(day_num, course[1])["text"]

    btn_done_text = get_text(profile, "course_mark_done") if not is_done else get_text(profile, "course_mark_undo")
    buttons = [
        [InlineKeyboardButton(text=btn_done_text, callback_data=f"crs_toggle_{day_num}")],
        [InlineKeyboardButton(text=get_text(profile, "course_back_list"), callback_data="crs_back_list")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("crs_toggle_"))
async def process_course_day_toggle(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    try:
        day_num = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer(get_text(profile, "course_stale_btn"), show_alert=True)
        return
    if day_num < 1 or day_num > 7:
        await callback.answer(get_text(profile, "course_stale_btn"), show_alert=True)
        return
    if await deny_if_not_premium(callback, profile):
        return

    if "course_completed" not in profile:
        profile["course_completed"] = []

    # Захист від ручного/застарілого callback'а на заблокований день.
    if day_num not in get_available_days(profile):
        await callback.answer(
            get_text(profile, "course_not_open"),
            show_alert=True,
        )
        return

    if day_num in profile["course_completed"]:
        profile["course_completed"].remove(day_num)
        msg = get_text(profile, "course_day_undone", day=day_num)
    else:
        profile["course_completed"].append(day_num)
        msg = get_text(profile, "course_day_done", day=day_num)

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

@dp.callback_query(F.data == "prem_start_day1")
async def process_prem_start_day1(callback: CallbackQuery):
    """CTA після покупки: одразу відкриває День 1 курсу."""
    profile = get_user_profile(callback.from_user.id)
    if await deny_if_not_premium(callback, profile):
        return

    course = get_course_days(profile)
    text = course[1]["text"]
    buttons = [
        [InlineKeyboardButton(text=get_text(profile, "course_mark_done"), callback_data="crs_toggle_1")],
        [InlineKeyboardButton(text=get_text(profile, "course_back_list"), callback_data="crs_back_list")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

# --- 🎁 PREMIUM TRIAL ---
@dp.callback_query(F.data == "trial_offer")
async def process_trial_offer(callback: CallbackQuery):
    """Показує екран пропозиції Trial перед активацією."""
    profile = get_user_profile(callback.from_user.id)
    if profile.get("is_premium", False):
        await callback.answer(get_text(profile, "already_premium"), show_alert=True)
        return
    if profile.get("trial_used"):
        await callback.answer(get_text(profile, "trial_already_used"), show_alert=True)
        return

    text = (
        f"{get_text(profile, 'trial_offer_title')}\n\n"
        f"{get_text(profile, 'trial_offer_what', days=TRIAL_DAYS)}\n\n"
        f"{get_text(profile, 'trial_offer_note')}\n\n"
        f"{get_text(profile, 'trial_offer_no_auto')}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(profile, "cta_try"), callback_data="trial_activate")],
        [InlineKeyboardButton(text=get_text(profile, "back"), callback_data="trial_back")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "trial_activate")
async def process_trial_activate(callback: CallbackQuery):
    """Активує Trial для користувача."""
    profile = get_user_profile(callback.from_user.id)
    if profile.get("is_premium", False):
        await callback.answer(get_text(profile, "already_premium"), show_alert=True)
        return
    if profile.get("trial_used"):
        await callback.answer(get_text(profile, "trial_already_used"), show_alert=True)
        return

    success, expires_at = start_trial(profile)
    if not success:
        await callback.answer(get_text(profile, "trial_already_used"), show_alert=True)
        return

    save_user_profile(callback.from_user.id, profile)
    track_event(profile, "trial_activated")
    save_user_profile(callback.from_user.id, profile)

    # Форматуємо дату закінчення Trial у локальний час користувача
    zone = timeutil.get_user_timezone(profile)
    try:
        expires_dt = datetime.fromisoformat(expires_at)
        expires_local = timeutil.local_datetime_str(expires_dt, zone)
    except Exception:
        expires_local = expires_at

    text = (
        f"{get_text(profile, 'trial_activated')}\n\n"
        f"{get_text(profile, 'trial_now_title')}\n"
        f"{get_text(profile, 'prem_item_analysis')}\n"
        f"{get_text(profile, 'prem_item_coach')}\n"
        f"{get_text(profile, 'prem_item_course')}\n"
        f"{get_text(profile, 'prem_item_goals')}\n"
        f"{get_text(profile, 'prem_item_stats')}\n\n"
        f"{get_text(profile, 'trial_ends_on', date=expires_local)}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(profile, "cta_day1"), callback_data="prem_start_day1")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # Надсилаємо оновлену клавіатуру
    await callback.message.answer(
        get_text(profile, "trial_keyboard_hint"),
        reply_markup=get_main_keyboard(profile, is_sleeping=False),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "trial_back")
async def process_trial_back(callback: CallbackQuery):
    """Повертається до пейволу з кнопки Trial."""
    profile = get_user_profile(callback.from_user.id)
    text, kb = build_paywall(profile)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

# --- 🤖 AI SLEEP COACH ---
@dp.message(F.text.in_([STRINGS["uk"]["btn_ask_ai"], STRINGS["en"]["btn_ask_ai"], STRINGS["ru"]["btn_ask_ai"]]))
async def ask_ai_start(message: types.Message, state: FSMContext):
    if not await require_premium(message):
        return

    profile = get_user_profile(message.from_user.id)
    text = get_text(profile, "ai_coach_welcome")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(profile, "ai_q_score"), callback_data="ai_q_score")],
        [InlineKeyboardButton(text=get_text(profile, "ai_q_tonight"), callback_data="ai_q_tonight")],
        [InlineKeyboardButton(text=get_text(profile, "ai_q_7days"), callback_data="ai_q_7days")],
        [InlineKeyboardButton(text=get_text(profile, "ai_q_first"), callback_data="ai_q_first")],
        [InlineKeyboardButton(text=get_text(profile, "back"), callback_data="ai_coach_back")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(SleepForm.waiting_for_ai_question)

@dp.callback_query(F.data.startswith("ai_q_"))
async def process_ai_quick_question(callback: CallbackQuery, state: FSMContext):
    """Обробка швидких запитань до AI Coach."""
    profile = get_user_profile(callback.from_user.id)
    if not has_premium_access(profile):
        await callback.answer(get_text(profile, "paywall_locked_header"), show_alert=True)
        return

    q_map = {
        "ai_q_score": get_text(profile, "ai_q_score"),
        "ai_q_tonight": get_text(profile, "ai_q_tonight"),
        "ai_q_7days": get_text(profile, "ai_q_7days"),
        "ai_q_first": get_text(profile, "ai_q_first"),
    }
    user_q = q_map.get(callback.data, "")
    if not user_q:
        await callback.answer("⚠️ Невідоме запитання", show_alert=True)
        return

    await state.clear()
    thinking_msg = await callback.message.edit_text(get_text(profile, "ai_thinking_q"), parse_mode="Markdown")
    
    ai_answer = await asyncio.to_thread(generate_real_ai_answer, profile, user_q)
    
    try:
        await thinking_msg.edit_text(get_text(profile, "ai_advisor_prefix") + ai_answer, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(get_text(profile, "ai_advisor_prefix") + ai_answer, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "ai_coach_back")
async def process_ai_coach_back(callback: CallbackQuery, state: FSMContext):
    """Повернення до головного меню з AI Coach."""
    await state.clear()
    profile = get_user_profile(callback.from_user.id)
    await callback.message.delete()
    await callback.message.answer(
        get_text(profile, "support_back_hint"),
        reply_markup=get_main_keyboard(profile, is_sleeping=bool(profile.get("active_sleep_start"))),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(SleepForm.waiting_for_ai_question)
async def process_ai_question(message: types.Message, state: FSMContext):
    profile = get_user_profile(message.from_user.id)
    user_q = message.text
    await state.clear()
    
    thinking_msg = await message.answer(get_text(profile, "ai_thinking_q"), parse_mode="Markdown")
    
    ai_answer = await asyncio.to_thread(generate_real_ai_answer, profile, user_q)
    
    try:
        await thinking_msg.edit_text(get_text(profile, "ai_advisor_prefix") + ai_answer, parse_mode="Markdown")
    except Exception:
        await message.answer(get_text(profile, "ai_advisor_prefix") + ai_answer, parse_mode="Markdown")

# --- ОБРОБНИКИ НЕВІДОМИХ ПОВІДОМЛЕНЬ ТА ПОМИЛОК ---
@dp.message(F.text)
async def handle_unknown_text(message: types.Message):
    profile = get_user_profile(message.from_user.id)
    await message.answer(
        get_text(profile, "unknown_msg"),
        reply_markup=get_main_keyboard(profile, is_sleeping=bool(profile.get("active_sleep_start"))),
        parse_mode="Markdown"
    )

@dp.errors()
async def global_error_handler(event: types.ErrorEvent):
    """Один користувач не може впустити весь бот: логуємо та продовжуємо."""
    logging.error(f"Handler error: {type(event.exception).__name__}: {event.exception}")

# --- ВЕБ-СЕРВЕР ДЛЯ СУМІСНОСТІ З RENDER WEB SERVICE ---
async def handle_ping(request):
    return web.Response(text="Bot is live and listening!")

# --- API ДЛЯ MINI APP (з валідацією Telegram WebApp initData) ---
def validate_init_data(init_data: str):
    """Перевіряє підпис Telegram WebApp initData (HMAC-SHA256)."""
    if not init_data:
        return None
    try:
        parsed = dict(item.split("=", 1) for item in init_data.split("&"))
        if "hash" not in parsed:
            return None
        received_hash = parsed["hash"]
        data_check = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items()) if k != "hash")
        secret_key = hmac.new(
            b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
        computed_hash = hmac.new(
            secret_key, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed_hash, received_hash):
            return None
        import urllib.parse
        user_json = urllib.parse.unquote(parsed.get("user", ""))
        user = json.loads(user_json) if user_json else {}
        return user.get("id")
    except Exception as e:
        logging.warning(f"initData validation failed: {e}")
        return None

def profile_to_api(uid):
    data = load_user_data()
    p = data.get(str(uid))
    if not p:
        return None
    logs = p.get("logs", [])[:30]
    ctx = build_sleep_context(p)
    for log in logs:
        if log.get("score") is None:
            score, _ = sleep_logic.compute_sleep_score(ctx, log)
            log["score"] = score
    trends = sleep_logic.analyze_trends(ctx, logs, 7)
    zone = timeutil.get_user_timezone(p)
    return {
        "id": str(uid),
        "lang": p.get("lang", "uk"),
        "timezone": p.get("timezone") or timeutil.DEFAULT_TIMEZONE,
        "is_premium": bool(p.get("is_premium", False)),
        "is_configured": bool(p.get("is_configured", False)),
        "username": p.get("username"),
        "goal_bedtime": get_goal_bedtime(p),
        "goal_waketime": get_goal_waketime(p),
        "goal_duration": p.get("goal_duration", get_target_hours(p)),
        "active_sleep_start": p.get("active_sleep_start"),
        "logs": logs,
        "streak": sleep_logic.compute_streak(logs, today=timeutil.local_today(zone)),
        "level": sleep_logic.level_from_xp(p.get("xp", 0) or sleep_logic.compute_xp(logs)),
        "xp": p.get("xp", 0) or sleep_logic.compute_xp(logs),
        "achievements": p.get("achievements", []),
        "trends": {
            "avg_duration": trends.get("avg_duration"),
            "avg_score": trends.get("avg_score"),
            "avg_bedtime": trends.get("avg_bedtime"),
            "avg_waketime": trends.get("avg_waketime"),
        },
        "course_completed": p.get("course_completed", []),
        "registered_at": p.get("registered_at"),
    }

async def api_me(request):
    user_id = validate_init_data(request.query.get("initData", ""))
    if not user_id:
        return web.json_response({"error": "unauthorized"}, status=401)
    data = profile_to_api(user_id)
    if not data:
        # Новий користувач без профілю (ще не натискав /start) — коректна
        # відповідь замість 404: Mini App отримує дефолтний стан.
        data = {
            "id": str(user_id),
            "lang": "uk",
            "timezone": timeutil.DEFAULT_TIMEZONE,
            "is_premium": False,
            "is_configured": False,
            "username": None,
            "goal_bedtime": "23:30",
            "goal_waketime": "07:30",
            "goal_duration": 8.0,
            "active_sleep_start": None,
            "logs": [],
            "streak": 0,
            "level": 1,
            "xp": 0,
            "achievements": [],
            "trends": {
                "avg_duration": None,
                "avg_score": None,
                "avg_bedtime": None,
                "avg_waketime": None,
            },
            "course_completed": [],
            "registered_at": None,
        }
    return web.json_response(data)

async def api_log(request):
    user_id = validate_init_data(request.query.get("initData", ""))
    if not user_id:
        return web.json_response({"error": "unauthorized"}, status=401)
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)
    if not isinstance(payload, dict):
        return web.json_response({"error": "bad_request"}, status=400)

    profile = get_user_profile(user_id)
    # Дата запису — у локальному часі користувача (не UTC сервера).
    local_date = timeutil.local_date_dmy(timeutil.utc_now(), timeutil.get_user_timezone(profile))

    def _safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    bedtime = str(payload.get("bedtime", "")).strip()
    waketime = str(payload.get("waketime", "")).strip()
    if parse_hhmm_int(bedtime) is None or parse_hhmm_int(waketime) is None:
        return web.json_response({"error": "bad_time"}, status=400)

    bed_min = parse_hhmm_int(bedtime)
    wake_min = parse_hhmm_int(waketime)
    if wake_min <= bed_min:
        wake_min += 24 * 60
    duration = round((wake_min - bed_min) / 60, 1)

    quality_raw = _safe_int(payload.get("quality"), 0)
    wakeups_raw = _safe_int(payload.get("wakeups"), 0)
    log = {
        "date": local_date,
        "bedtime": bedtime,
        "waketime": waketime,
        "duration": duration,
        "quality_num": quality_raw if 1 <= quality_raw <= 10 else None,
        "wakeups": min(9, max(0, wakeups_raw)),
        "caffeine": bool(payload.get("caffeine")),
        "screens": bool(payload.get("screens")),
        "nap": bool(payload.get("nap")),
        "note": str(payload.get("note", ""))[:200],
    }
    if log["quality_num"] is not None:
        log["quality"] = f"{log['quality_num']}/10"
    else:
        log["quality"] = get_text(profile, "quality_auto")

    score, components = sleep_logic.compute_sleep_score(build_sleep_context(profile), log)
    log["score"] = score
    profile["logs"].insert(0, log)
    track_event(profile, "log_saved")
    profile["xp"] = sleep_logic.compute_xp(profile["logs"])
    achievements = sleep_logic.check_achievements(profile["logs"])
    new_ach = []
    for aid, achieved in achievements.items():
        if achieved and aid not in profile.get("achievements", []):
            profile["achievements"].append(aid)
            new_ach.append(aid)
    save_user_profile(user_id, profile)

    return web.json_response({"ok": True, "score": score, "new_achievements": new_ach})

async def api_goals(request):
    user_id = validate_init_data(request.query.get("initData", ""))
    if not user_id:
        return web.json_response({"error": "unauthorized"}, status=401)
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)

    profile = get_user_profile(user_id)
    updated = {}

    bt = str(payload.get("goal_bedtime", "")).strip()
    if bt and parse_hhmm_int(bt) is not None:
        profile["goal_bedtime"] = bt
        updated["goal_bedtime"] = bt

    wt = str(payload.get("goal_waketime", "")).strip()
    if wt and parse_hhmm_int(wt) is not None:
        profile["goal_waketime"] = wt
        updated["goal_waketime"] = wt

    try:
        dur = float(payload.get("goal_duration", 0) or 0)
        if 4 <= dur <= 12:
            profile["goal_duration"] = round(dur, 1)
            updated["goal_duration"] = profile["goal_duration"]
    except (TypeError, ValueError):
        pass

    if updated:
        save_user_profile(user_id, profile)
    return web.json_response({"ok": True, "updated": updated})

async def main():
    logging.basicConfig(level=logging.INFO)
    print("🤖 Multilingual bot with Deep AI Sleep Engine launched!")

    # Запускаємо фоновий веб-сервер для перевірки портів Render + API Mini App
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/api/me", api_me)
    app.router.add_post("/api/log", api_log)
    app.router.add_post("/api/goals", api_goals)
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

    # Планувальник нагадувань
    scheduler = ReminderScheduler(bot, get_user_profile, update_user_profile)
    scheduler.start()

    # Запускаємо polling бота
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот зупинений.")