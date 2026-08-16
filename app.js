// Telegram WebApp SDK Initialization
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  tg.setHeaderColor?.('#0f1420');
  tg.setBackgroundColor?.('#0f1420');
}

/* ===================================================
   I18N (uk / en / ru)
   =================================================== */
const I18N = {
  uk: {
    loading: 'Завантаження...',
    error: 'Не вдалося завантажити дані. Перевірте з\u0027єднання.',
    retry: 'Повторити',
    navSleep: 'Сон',
    navStats: 'Статистика',
    navCourse: 'Курс',
    navJournal: 'Журнал',
    navProfile: 'Профіль',
    journalTitle: 'Журнал сну 📜',
    journalSub: 'Ваші останні записи та якість',
    journalAdd: 'Запис',
    journalEmpty: 'Немає записів сну',
    statsTitle: 'Статистика 📊',
    statsSub: 'Тенденції та закономірності сну',
    period7: '7 днів',
    period14: '14 днів',
    period30: '30 днів',
    scoreChartTitle: 'Sleep Score',
    durationChartTitle: 'Тривалість сну',
    recsTitle: 'Рекомендації',
    recsEmpty: 'Зробіть кілька записів, щоб отримати персональні рекомендації.',
    avgDuration: 'Середня тривалість',
    avgScore: 'Середній бал',
    bestScore: 'Найкращий бал',
    consistency: 'Стабільність режиму',
    lastNight: 'Остання ніч',
    targetHours: 'Ціль',
    hoursShort: 'год',
    qualityAuto: 'Автоматично',
    sleeping: '🌙 Ви зараз спите',
    sleepingSub: 'Таймер сну активний. Натисніть, коли прокинетеся.',
    wakeUp: 'Прокинутися ☀️',
    awake: '☀️ Ви прокинулися',
    awakeSub: 'Натисніть кнопку, коли лягаєте спати',
    goSleep: 'Лягати спати',
    profileTitle: 'Профіль 👤',
    profileSub: 'Цілі, досягнення та налаштування',
    streak: '🔥 серія',
    level: '⭐ рівень',
    xp: '💎 XP',
    goalsTitle: 'Цілі',
    goalBedtimeLbl: 'Цільовий час сну',
    goalWaketimeLbl: 'Цільовий час підйому',
    goalDurationLbl: 'Бажана тривалість (год)',
    goalsSave: 'Зберегти',
    goalsSaved: '✅ Цілі збережено',
    achTitle: 'Досягнення',
    ach_first_log: 'Перший запис сну',
    ach_streak_3: '3 ночі поспіль',
    ach_streak_7: 'Тиждень без перерв',
    ach_nights_8h_5: '5 ночей по 8+ годин',
    ach_score_90: 'Score 90+',
    ach_score_80_3: '3 рази Score 80+',
    ach_early_5: '5 ранніх підйомів',
    ach_no_phone_3: '3 ночі без телефону',
    sleepModalTitle: 'Записати сон 🌙',
    sleepBedtimeLbl: 'Час засинання',
    sleepWaketimeLbl: 'Час пробудження',
    sleepQualityLbl: 'Якість сну (1-10)',
    sleepWakeupsLbl: 'Пробудження вночі',
    sleepFactorsLbl: 'Фактори',
    sleepNoteLbl: 'Замітка (самопочуття)',
    sleepSave: 'Зберегти запис',
    savedOk: '✅ Запис збережено',
    saveFailed: '❌ Не вдалося зберегти. Спробуйте ще раз.',
    premiumRequired: '🔒 Для курсу потрібен Premium. Оформіть у боті.',
    day: 'День',
    done: 'Урок пройдено',
    markDone: 'Позначити урок пройденим',
    openInBot: 'Налаштування виконуються в боті',
  },
  en: {
    loading: 'Loading...',
    error: 'Failed to load data. Check your connection.',
    retry: 'Retry',
    navSleep: 'Sleep',
    navStats: 'Stats',
    navCourse: 'Course',
    navJournal: 'Journal',
    navProfile: 'Profile',
    journalTitle: 'Sleep Journal 📜',
    journalSub: 'Your latest logs & quality',
    journalAdd: 'Log',
    journalEmpty: 'No sleep logs yet',
    statsTitle: 'Statistics 📊',
    statsSub: 'Sleep trends & patterns',
    period7: '7 days',
    period14: '14 days',
    period30: '30 days',
    scoreChartTitle: 'Sleep Score',
    durationChartTitle: 'Sleep duration',
    recsTitle: 'Recommendations',
    recsEmpty: 'Log a few nights to get personalized recommendations.',
    avgDuration: 'Average duration',
    avgScore: 'Average score',
    bestScore: 'Best score',
    consistency: 'Schedule stability',
    lastNight: 'Last night',
    targetHours: 'Target',
    hoursShort: 'h',
    qualityAuto: 'Automatic',
    sleeping: '🌙 You are sleeping now',
    sleepingSub: 'Timer is active. Tap when you wake up.',
    wakeUp: 'Wake up ☀️',
    awake: '☀️ You are awake',
    awakeSub: 'Tap the button when you go to sleep',
    goSleep: 'Go to sleep',
    profileTitle: 'Profile 👤',
    profileSub: 'Goals, achievements & settings',
    streak: '🔥 streak',
    level: '⭐ level',
    xp: '💎 XP',
    goalsTitle: 'Goals',
    goalBedtimeLbl: 'Target bedtime',
    goalWaketimeLbl: 'Target wake time',
    goalDurationLbl: 'Target duration (h)',
    goalsSave: 'Save',
    goalsSaved: '✅ Goals saved',
    achTitle: 'Achievements',
    ach_first_log: 'First sleep log',
    ach_streak_3: '3 nights in a row',
    ach_streak_7: 'A week without breaks',
    ach_nights_8h_5: '5 nights of 8+ hours',
    ach_score_90: 'Score 90+',
    ach_score_80_3: '3 times Score 80+',
    ach_early_5: '5 early wake-ups',
    ach_no_phone_3: '3 nights without phone',
    sleepModalTitle: 'Log sleep 🌙',
    sleepBedtimeLbl: 'Bedtime',
    sleepWaketimeLbl: 'Wake time',
    sleepQualityLbl: 'Sleep quality (1-10)',
    sleepWakeupsLbl: 'Night wake-ups',
    sleepFactorsLbl: 'Factors',
    sleepNoteLbl: 'Note (how you feel)',
    sleepSave: 'Save log',
    savedOk: '✅ Log saved',
    saveFailed: '❌ Failed to save. Try again.',
    premiumRequired: '🔒 Premium is required for the course. Get it in the bot.',
    day: 'Day',
    done: 'Lesson completed',
    markDone: 'Mark lesson as completed',
    openInBot: 'Settings are managed in the bot',
  },
  ru: {
    loading: 'Загрузка...',
    error: 'Не удалось загрузить данные. Проверьте соединение.',
    retry: 'Повторить',
    navSleep: 'Сон',
    navStats: 'Статистика',
    navCourse: 'Курс',
    navJournal: 'Журнал',
    navProfile: 'Профиль',
    journalTitle: 'Журнал сна 📜',
    journalSub: 'Ваши последние записи и качество',
    journalAdd: 'Запись',
    journalEmpty: 'Нет записей сна',
    statsTitle: 'Статистика 📊',
    statsSub: 'Тенденции и закономерности сна',
    period7: '7 дней',
    period14: '14 дней',
    period30: '30 дней',
    scoreChartTitle: 'Sleep Score',
    durationChartTitle: 'Длительность сна',
    recsTitle: 'Рекомендации',
    recsEmpty: 'Сделайте несколько записей, чтобы получить рекомендации.',
    avgDuration: 'Средняя длительность',
    avgScore: 'Средний балл',
    bestScore: 'Лучший балл',
    consistency: 'Стабильность режима',
    lastNight: 'Прошлая ночь',
    targetHours: 'Цель',
    hoursShort: 'ч',
    qualityAuto: 'Автоматически',
    sleeping: '🌙 Вы сейчас спите',
    sleepingSub: 'Таймер активен. Нажмите, когда проснётесь.',
    wakeUp: 'Проснуться ☀️',
    awake: '☀️ Вы проснулись',
    awakeSub: 'Нажмите кнопку, когда ложитесь спать',
    goSleep: 'Ложиться спать',
    profileTitle: 'Профиль 👤',
    profileSub: 'Цели, достижения и настройки',
    streak: '🔥 серия',
    level: '⭐ уровень',
    xp: '💎 XP',
    goalsTitle: 'Цели',
    goalBedtimeLbl: 'Целевое время сна',
    goalWaketimeLbl: 'Целевое время подъёма',
    goalDurationLbl: 'Желаемая длительность (ч)',
    goalsSave: 'Сохранить',
    goalsSaved: '✅ Цели сохранены',
    achTitle: 'Достижения',
    ach_first_log: 'Первая запись сна',
    ach_streak_3: '3 ночи подряд',
    ach_streak_7: 'Неделя без перерывов',
    ach_nights_8h_5: '5 ночей по 8+ часов',
    ach_score_90: 'Score 90+',
    ach_score_80_3: '3 раза Score 80+',
    ach_early_5: '5 ранних подъёмов',
    ach_no_phone_3: '3 ночи без телефона',
    sleepModalTitle: 'Записать сон 🌙',
    sleepBedtimeLbl: 'Время засыпания',
    sleepWaketimeLbl: 'Время пробуждения',
    sleepQualityLbl: 'Качество сна (1-10)',
    sleepWakeupsLbl: 'Пробуждения ночью',
    sleepFactorsLbl: 'Факторы',
    sleepNoteLbl: 'Заметка (самочувствие)',
    sleepSave: 'Сохранить запись',
    savedOk: '✅ Запись сохранена',
    saveFailed: '❌ Не удалось сохранить. Попробуйте ещё раз.',
    premiumRequired: '🔒 Для курса нужен Premium. Оформите в боте.',
    day: 'День',
    done: 'Урок пройден',
    markDone: 'Отметить урок пройденным',
    openInBot: 'Настройки выполняются в боте',
  }
};

const ACH_ORDER = ['first_log', 'streak_3', 'streak_7', 'nights_8h_5', 'score_90', 'score_80_3', 'early_5', 'no_phone_3'];
const ACH_ICONS = {
  first_log: '🏆', streak_3: '🔥', streak_7: '🔥', nights_8h_5: '🌙',
  score_90: '⭐', score_80_3: '💎', early_5: '🌅', no_phone_3: '📵'
};

let lang = 'uk';
function t(key) { return (I18N[lang] && I18N[lang][key]) || I18N.uk[key] || key; }
function applyI18n() {
  const map = {
    loadingText: 'loading', errorText: 'error', errorRetry: 'retry',
    navSleep: 'navSleep', navStats: 'navStats', navCourse: 'navCourse',
    navJournal: 'navJournal', navProfile: 'navProfile',
    journalTitle: 'journalTitle', journalSub: 'journalSub', journalAddBtn: 'journalAdd',
    statsTitle: 'statsTitle', statsSub: 'statsSub',
    scoreChartTitle: 'scoreChartTitle', durationChartTitle: 'durationChartTitle', recsTitle: 'recsTitle',
    profileTitle: 'profileTitle', profileSub: 'profileSub',
    profileStreakLbl: 'streak', profileLevelLbl: 'level', profileXPLbl: 'xp',
    goalsTitle: 'goalsTitle', achTitle: 'achTitle',
    sleepModalTitle: 'sleepModalTitle', sleepBedtimeLbl: 'sleepBedtimeLbl',
    sleepWaketimeLbl: 'sleepWaketimeLbl', sleepQualityLbl: 'sleepQualityLbl',
    sleepWakeupsLbl: 'sleepWakeupsLbl', sleepFactorsLbl: 'sleepFactorsLbl',
    sleepNoteLbl: 'sleepNoteLbl', sleepSaveBtn: 'sleepSave',
    goalsModalTitle: 'goalsTitle', goalBedtimeLbl: 'goalBedtimeLbl',
    goalWaketimeLbl: 'goalWaketimeLbl', goalDurationLbl: 'goalDurationLbl', goalsSaveBtn: 'goalsSave'
  };
  Object.entries(map).forEach(([id, key]) => {
    const el = document.getElementById(id);
    if (el) el.textContent = t(key);
  });
  document.querySelectorAll('[data-days]').forEach(b => {
    const days = b.getAttribute('data-days');
    b.textContent = days === '7' ? t('period7') : days === '14' ? t('period14') : t('period30');
  });
}

// Екранування тексту перед вставкою в HTML (захист від XSS)
function escapeHTML(str) {
  const div = document.createElement('div');
  div.textContent = String(str == null ? '' : str);
  return div.innerHTML;
}

// App State
let state = {
  profile: null,
  isSleeping: false,
  sleepStartTime: null,
  selectedFactors: [],
  courseProgress: { completedDays: [1], checklist: { air: false, screens: false, braindump: false, caffeine: false, relax: false } }
};

let liveTimerInterval = null;
let breathingInterval = null;
let isBreathingRunning = false;
let statsPeriod = 7;

// Audio Ambient Sound Generator (Web Audio API)
let audioCtx = null;
let isAudioPlaying = false;
let currentSoundPreset = 'rain';
let activeNoiseNodes = [];
let audioTimerTimeout = null;

function saveLocal() {
  localStorage.setItem('dedicated_sleep_tracker_state', JSON.stringify({
    isSleeping: state.isSleeping,
    sleepStartTime: state.sleepStartTime,
    courseProgress: state.courseProgress
  }));
}

function loadLocal() {
  try {
    const saved = JSON.parse(localStorage.getItem('dedicated_sleep_tracker_state'));
    if (saved) {
      state.isSleeping = !!saved.isSleeping;
      state.sleepStartTime = saved.sleepStartTime || null;
      state.courseProgress = { ...state.courseProgress, ...(saved.courseProgress || {}) };
    }
  } catch (e) {
    console.error("Error loading saved state", e);
  }
}

/* ===================================================
   TELEGRAM THEME
   =================================================== */
function applyTelegramTheme() {
  if (!tg || !tg.themeParams) return;
  const p = tg.themeParams;
  const root = document.documentElement;
  const css = {
    '--bg': p.bg_color || '#0f1420',
    '--card': p.secondary_bg_color || '#1a2130',
    '--text': p.text_color || '#f4f4f5',
    '--text-secondary': p.hint_color || '#8b93a7',
    '--accent': p.button_color || '#8b5cf6',
    '--accent-text': p.button_text_color || '#ffffff'
  };
  Object.entries(css).forEach(([k, v]) => root.style.setProperty(k, v));
}

/* ===================================================
   API LAYER (vra datos z servera, ne fake)
   =================================================== */
function apiInitData() {
  return (tg && tg.initData) ? encodeURIComponent(tg.initData) : '';
}

async function apiFetch(url, options) {
  const sep = url.includes('?') ? '&' : '?';
  const res = await fetch(`${url}${sep}initData=${apiInitData()}`, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function apiMe() {
  return apiFetch('/api/me');
}

async function apiLog(payload) {
  return apiFetch('/api/log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

async function apiGoals(payload) {
  return apiFetch('/api/goals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

/* ===================================================
   INIT
   =================================================== */
function showLoading(show) {
  document.getElementById('appLoading').style.display = show ? 'flex' : 'none';
}
function showError(show, text) {
  const banner = document.getElementById('errorBanner');
  banner.style.display = show ? 'flex' : 'none';
  if (text) document.getElementById('errorText').textContent = text;
}

async function initApp() {
  showError(false);
  showLoading(true);
  try {
    const data = await apiMe();
    state.profile = data;
    if (data.lang) lang = data.lang;
    applyTelegramTheme();
    applyI18n();
    initTelegramUser();
    renderCourseTab();
    renderDashboard();
    renderJournal();
    renderStats();
    renderProfile();
    showLoading(false);
    if (state.isSleeping && state.sleepStartTime) startLiveTimer();
    updateSleepTimerUI();
  } catch (e) {
    console.error('API error', e);
    showLoading(false);
    showError(true);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadLocal();
  applyTelegramTheme();
  initApp();
  document.getElementById('themeToggle').addEventListener('click', toggleTheme);
});

// Telegram User Identification
function initTelegramUser() {
  const userNameElem = document.getElementById('userName');
  const userAvatarElem = document.getElementById('userAvatar');
  const profileName = document.getElementById('profileName');

  const user = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) || null;
  const name = user ? (user.first_name + (user.last_name ? ` ${user.last_name}` : '')) : 'User';
  if (userNameElem) userNameElem.textContent = name;
  if (profileName) profileName.textContent = name;

  if (user && user.photo_url && userAvatarElem) {
    const img = document.createElement('img');
    img.src = user.photo_url;
    img.alt = 'Avatar';
    userAvatarElem.innerHTML = '';
    userAvatarElem.appendChild(img);
  }
  if (state.profile && state.profile.is_premium) {
    document.getElementById('profilePremiumTag').textContent = '⭐ Premium';
    document.getElementById('profilePremiumTag').classList.add('premium');
  }
}

/* ===================================================
   NAVIGATION
   =================================================== */
function switchTab(tabName) {
  triggerHaptic();
  document.querySelectorAll('.tab-page').forEach(page => page.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
  const targetPage = document.getElementById(`tab-${tabName}`);
  if (targetPage) targetPage.classList.add('active');
  const targetBtn = document.querySelector(`.nav-item[data-tab="${tabName}"]`);
  if (targetBtn) targetBtn.classList.add('active');
}

function triggerHaptic() {
  if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}

/* ===================================================
   DASHBOARD / SLEEP TIMER
   =================================================== */
function toggleSleepTimer() {
  triggerHaptic();
  if (!state.isSleeping) {
    state.isSleeping = true;
    state.sleepStartTime = new Date().toISOString();
    saveLocal();
    startLiveTimer();
    updateSleepTimerUI();
  } else {
    // Wake up → open log modal prefilled with timer data
    stopLiveTimer();
    const start = new Date(state.sleepStartTime);
    const end = new Date();
    const b = document.getElementById('sleepBedtime');
    const w = document.getElementById('sleepWaketime');
    b.value = formatTime(start);
    w.value = formatTime(end);
    state.isSleeping = false;
    state.sleepStartTime = null;
    saveLocal();
    updateSleepTimerUI();
    document.getElementById('sleepNote').placeholder = '';
    openSleepModal();
  }
}

function startLiveTimer() {
  if (liveTimerInterval) clearInterval(liveTimerInterval);
  liveTimerInterval = setInterval(updateLiveTimerDisplay, 1000);
  updateLiveTimerDisplay();
}

function stopLiveTimer() {
  if (liveTimerInterval) clearInterval(liveTimerInterval);
  liveTimerInterval = null;
}

function updateLiveTimerDisplay() {
  const el = document.getElementById('sleepTimerDisplay');
  if (!state.isSleeping || !state.sleepStartTime) {
    el.textContent = '00:00:00';
    return;
  }
  const diffMs = Math.max(0, Date.now() - new Date(state.sleepStartTime));
  const h = Math.floor(diffMs / 3600000).toString().padStart(2, '0');
  const m = Math.floor((diffMs % 3600000) / 60000).toString().padStart(2, '0');
  const s = Math.floor((diffMs % 60000) / 1000).toString().padStart(2, '0');
  el.textContent = `${h}:${m}:${s}`;
}

function updateSleepTimerUI() {
  const card = document.querySelector('.sleep-hero-card');
  const tag = document.getElementById('sleepStatusTag');
  const sub = document.getElementById('sleepHeroSub');
  const btn = document.getElementById('sleepActionBtn');
  const btnText = document.getElementById('sleepActionText');
  const moonIcon = document.getElementById('heroMoonIcon');

  if (state.isSleeping) {
    card.classList.add('sleeping');
    tag.textContent = t('sleeping');
    tag.style.color = '#34d399';
    sub.textContent = t('sleepingSub');
    btnText.textContent = t('wakeUp');
    btn.querySelector('i').className = 'fa-solid fa-sun';
    moonIcon.className = 'fa-solid fa-bed';
  } else {
    card.classList.remove('sleeping');
    tag.textContent = t('awake');
    tag.style.color = '#c7d2fe';
    sub.textContent = t('awakeSub');
    btnText.textContent = t('goSleep');
    btn.querySelector('i').className = 'fa-solid fa-bed';
    moonIcon.className = 'fa-solid fa-moon';
    document.getElementById('sleepTimerDisplay').textContent = '00:00:00';
  }

  const logs = (state.profile && state.profile.logs) || [];
  if (logs.length > 0) {
    const last = logs[0];
    document.getElementById('lastSleepHours').innerHTML = `${Number(last.duration).toFixed(1)} <small>${t('hoursShort')}</small>`;
    document.getElementById('lastSleepQuality').textContent = last.quality || t('qualityAuto');
    const sum = logs.slice(0, 7).reduce((acc, cur) => acc + Number(cur.duration || 0), 0);
    const avg = sum / Math.min(7, logs.length);
    document.getElementById('avgSleepHours').innerHTML = `${avg.toFixed(1)} <small>${t('hoursShort')}</small>`;
    document.getElementById('chartAvgTag').textContent = `${avg.toFixed(1)} ${t('hoursShort')} / ${t('lastNight').toLowerCase()}`;
  } else {
    document.getElementById('lastSleepHours').innerHTML = `--`;
    document.getElementById('lastSleepQuality').textContent = '--';
    document.getElementById('avgSleepHours').innerHTML = `--`;
  }
}

/* ===================================================
   WEEKLY BAR CHART (dashboard)
   =================================================== */
function renderWeeklyChart() {
  const container = document.getElementById('barChartContainer');
  if (!container) return;
  container.innerHTML = '';
  const logs = ((state.profile && state.profile.logs) || []).slice(0, 7).reverse();
  if (logs.length === 0) {
    container.innerHTML = `<p style="color:var(--text-secondary); text-align:center; padding:20px;">${t('journalEmpty')}</p>`;
    return;
  }
  const maxGoal = 10.0;
  const target = state.profile ? Number(state.profile.goal_duration || 8) : 8;
  logs.forEach(log => {
    const heightPercent = Math.min(100, (Number(log.duration) / maxGoal) * 100);
    const isTarget = Number(log.duration) >= target;
    const dayName = String(log.date || '').split(',')[0].slice(0, 2) || '--';
    const col = document.createElement('div');
    col.className = 'bar-col';
    col.innerHTML = `
      <span class="bar-val">${Number(log.duration).toFixed(1)}${t('hoursShort')}</span>
      <div class="bar-fill-wrap">
        <div class="bar-fill ${isTarget ? 'target-reached' : ''}" style="height: ${heightPercent}%"></div>
      </div>
      <span class="bar-label">${escapeHTML(dayName)}</span>
    `;
    container.appendChild(col);
  });
}

function renderDashboard() {
  updateSleepTimerUI();
  renderWeeklyChart();
}

/* ===================================================
   JOURNAL
   =================================================== */
function renderJournal() {
  const container = document.getElementById('journalList');
  if (!container) return;
  container.innerHTML = '';
  const logs = (state.profile && state.profile.logs) || [];
  if (logs.length === 0) {
    container.innerHTML = `<p style="color:var(--text-secondary); text-align:center; padding:20px;">${t('journalEmpty')}</p>`;
    return;
  }
  logs.forEach(log => {
    const card = document.createElement('div');
    card.className = 'journal-card';
    const score = log.score != null
      ? `<span class="journal-score ${Number(log.score) >= 80 ? 'good' : Number(log.score) >= 60 ? 'mid' : ''}">${Number(log.score)}</span>`
      : '';
    const factors = ['caffeine', 'screens', 'nap']
      .filter(k => log[k])
      .map(k => `<span class="factor-badge">${k === 'caffeine' ? '☕' : k === 'screens' ? '📱' : '😴'}</span>`)
      .join('');
    card.innerHTML = `
      <div class="journal-top">
        <span class="journal-date">${escapeHTML(log.date)}</span>
        ${score}
        <span class="journal-duration">${Number(log.duration).toFixed(1)} ${t('hoursShort')}</span>
      </div>
      <div class="journal-times">
        <i class="fa-solid fa-moon"></i> ${escapeHTML(log.bedtime)} — <i class="fa-solid fa-sun"></i> ${escapeHTML(log.waketime)} (${escapeHTML(log.quality || t('qualityAuto'))})
      </div>
      ${log.note ? `<p style="font-size:0.8rem; color:var(--text-secondary);">${escapeHTML(log.note)}</p>` : ''}
      ${factors ? `<div class="journal-factors">${factors}</div>` : ''}
    `;
    container.appendChild(card);
  });
}

/* ===================================================
   STATISTICS TAB
   =================================================== */
function switchStatsPeriod(days) {
  statsPeriod = days;
  document.querySelectorAll('.period-chip').forEach(ch => ch.classList.toggle('active', Number(ch.getAttribute('data-days')) === days));
  renderStats();
}

function renderStats() {
  const logs = ((state.profile && state.profile.logs) || []).slice(0, statsPeriod);
  const grid = document.getElementById('statsGrid');
  const scoreChart = document.getElementById('scoreChartContainer');
  const durChart = document.getElementById('durationChartContainer');
  const recsList = document.getElementById('recsList');
  if (!grid) return;

  if (logs.length === 0) {
    grid.innerHTML = `<div class="card" style="grid-column:1/-1; text-align:center; color:var(--text-secondary);">${t('journalEmpty')}</div>`;
    scoreChart.innerHTML = '';
    durChart.innerHTML = '';
    recsList.innerHTML = `<p style="color:var(--text-secondary);">${t('recsEmpty')}</p>`;
    return;
  }

  const durations = logs.map(l => Number(l.duration || 0));
  const scores = logs.map(l => Number(l.score || 0)).filter(s => s > 0);
  const avgDur = durations.reduce((a, b) => a + b, 0) / durations.length;
  const avgScore = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
  const bestScore = scores.length ? Math.max(...scores) : 0;
  const stdDev = Math.sqrt(durations.reduce((acc, d) => acc + Math.pow(d - avgDur, 2), 0) / durations.length);
  const consistency = stdDev <= 0.8 ? 90 : stdDev <= 1.5 ? 70 : stdDev <= 2.5 ? 45 : 25;

  const card = (icon, label, value, extra) => `
    <div class="stat-card card">
      <div class="stat-icon">${icon}</div>
      <div class="stat-body">
        <span class="stat-label">${label}</span>
        <span class="stat-value">${value}</span>
        ${extra ? `<span class="stat-extra">${extra}</span>` : ''}
      </div>
    </div>`;

  grid.innerHTML =
    card('⏱️', t('avgDuration'), `${avgDur.toFixed(1)} ${t('hoursShort')}`, t('targetHours') + ': ' + (state.profile ? Number(state.profile.goal_duration).toFixed(1) : '8.0')) +
    card('🎯', t('avgScore'), `${avgScore}/100`, '') +
    card('🏆', t('bestScore'), `${bestScore}/100`, '') +
    card('📐', t('consistency'), `${consistency}%`, '');

  // Sleep Score line chart (SVG)
  renderScoreChart(scoreChart, logs);
  // Duration bar chart
  renderDurationChart(durChart, logs);

  // Recommendations
  const target = state.profile ? Number(state.profile.goal_duration) : 8;
  const recs = [];
  if (avgDur < target - 0.5) recs.push(`⏱️ ${t('navSleep')}: ${t('avgDuration')} ${avgDur.toFixed(1)} ${t('hoursShort')} < ${target.toFixed(1)} ${t('hoursShort')}`);
  if (scores.length && avgScore < 70) recs.push(`💡 Sleep Score нижчий за 70 — спробуйте лягати раніше та прибрати телефон за годину до сну`);
  const late = logs.filter(l => String(l.bedtime || '23:59').localeCompare('23:30') > 0).length;
  if (late > logs.length / 2) recs.push(`🌙 Ви лягаєте пізніше 23:30 частіше, ніж половина ночей — зруште час сну на 15 хв раніше`);
  const caff = logs.filter(l => l.caffeine).length;
  if (caff > 0) recs.push(`☕ Кофеїн зафіксовано у ${caff} ночей — остання кава має бути за 8 год до сну`);
  recsList.innerHTML = recs.length
    ? recs.map(r => `<div class="rec-item"><i class="fa-solid fa-circle-check"></i><span>${r}</span></div>`).join('')
    : `<p style="color:var(--text-secondary);">${t('recsEmpty')}</p>`;
}

function renderScoreChart(container, logs) {
  container.innerHTML = '';
  const scores = logs.slice(0, 14).reverse().map(l => Number(l.score || 0));
  const maxScore = 100;
  const w = 320, h = 90, pad = 6;
  if (scores.length < 2) {
    container.innerHTML = `<p style="color:var(--text-secondary); text-align:center; padding:10px;">${t('journalEmpty')}</p>`;
    return;
  }
  const stepX = (w - pad * 2) / (scores.length - 1);
  const points = scores.map((s, i) => {
    const x = pad + i * stepX;
    const y = h - pad - (Math.min(s, maxScore) / maxScore) * (h - pad * 2);
    return { x, y };
  });
  const line = points.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const area = `M${points[0].x.toFixed(1)},${h - pad} L${line.replace(/ /g, ' L')} L${points[points.length - 1].x.toFixed(1)},${h - pad} Z`;
  const svg = `
    <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="width:100%; height:100%;">
      <defs>
        <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.45"/>
          <stop offset="100%" stop-color="var(--accent)" stop-opacity="0.02"/>
        </linearGradient>
      </defs>
      <line x1="${pad}" y1="${h - pad}" x2="${w - pad}" y2="${h - pad}" stroke="var(--text-secondary)" stroke-opacity="0.2" stroke-width="1"/>
      <path d="${area}" fill="url(#scoreGrad)"/>
      <polyline points="${line}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
      ${points.map(p => `<circle cx="${p.x}" cy="${p.y}" r="2.5" fill="var(--accent)"/>`).join('')}
    </svg>`;
  container.innerHTML = svg;
  const lastScore = scores[scores.length - 1];
  container.insertAdjacentHTML('beforeend',
    `<div class="score-summary">${t('avgScore')}: <b>${Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)}</b> · ${t('lastNight')}: <b>${lastScore}</b></div>`);
}

function renderDurationChart(container, logs) {
  container.innerHTML = '';
  const recent = logs.slice(0, 7).reverse();
  const target = state.profile ? Number(state.profile.goal_duration) : 8;
  const maxH = Math.max(10, ...recent.map(l => Number(l.duration || 0)));
  recent.forEach(log => {
    const h = Math.min(100, (Number(log.duration) / maxH) * 100);
    const ok = Number(log.duration) >= target;
    const col = document.createElement('div');
    col.className = 'dbar-col';
    col.innerHTML = `
      <div class="dbar-wrap">
        <div class="dbar-fill ${ok ? 'target-reached' : ''}" style="height:${h}%"></div>
      </div>
      <span class="dbar-label">${escapeHTML(String(log.date || '--').split(',')[0].slice(0, 2))}</span>`;
    container.appendChild(col);
  });
}

/* ===================================================
   PROFILE TAB
   =================================================== */
function renderProfile() {
  const p = state.profile;
  if (!p) return;
  document.getElementById('profileStreak').textContent = p.streak || 0;
  document.getElementById('profileLevel').textContent = p.level || 1;
  document.getElementById('profileXP').textContent = p.xp || 0;

  const goalsList = document.getElementById('goalsList');
  goalsList.innerHTML = `
    <div class="goal-row"><span>🌅 ${t('goalBedtimeLbl')}</span><b>${escapeHTML(p.goal_bedtime || '23:30')}</b></div>
    <div class="goal-row"><span>☀️ ${t('goalWaketimeLbl')}</span><b>${escapeHTML(p.goal_waketime || '07:30')}</b></div>
    <div class="goal-row"><span>⏱ ${t('goalDurationLbl')}</span><b>${Number(p.goal_duration || 8).toFixed(1)} ${t('hoursShort')}</b></div>
  `;

  const grid = document.getElementById('achievementsGrid');
  const owned = new Set(p.achievements || []);
  grid.innerHTML = ACH_ORDER.map(id => {
    const done = owned.has(id);
    return `
      <div class="ach-item ${done ? 'owned' : 'locked'}" title="${escapeHTML(t('ach_' + id))}">
        <span class="ach-icon">${ACH_ICONS[id] || '🎖️'}</span>
        <span class="ach-name">${escapeHTML(t('ach_' + id))}</span>
      </div>`;
  }).join('');

  document.getElementById('editGoalsBtn').onclick = openGoalsModal;
}

/* ===================================================
   MODALS: Sleep Log & Goals
   =================================================== */
function openSleepModal() {
  triggerHaptic();
  document.getElementById('sleepModal').classList.add('active');
}

function closeSleepModal() {
  document.getElementById('sleepModal').classList.remove('active');
}

function setRating(btn, val) {
  document.getElementById('sleepQuality').value = val;
  document.querySelectorAll('.rating-btn').forEach(b => b.classList.toggle('selected', Number(b.getAttribute('data-q')) <= val));
}

function toggleFactor(chip) {
  chip.classList.toggle('selected');
}

async function saveSleepLog(e) {
  e.preventDefault();
  const bedtime = document.getElementById('sleepBedtime').value;
  const waketime = document.getElementById('sleepWaketime').value;
  const quality = Number(document.getElementById('sleepQuality').value) || 0;
  const wakeups = Number(document.getElementById('sleepWakeups').value) || 0;
  const note = document.getElementById('sleepNote').value.trim();
  const factors = Array.from(document.querySelectorAll('.factor-chip.selected')).map(c => c.getAttribute('data-factor'));

  if (!bedtime || !waketime) return;

  const payload = {
    bedtime, waketime,
    quality, wakeups, note,
    caffeine: factors.includes('caffeine'),
    screens: factors.includes('screens'),
    nap: factors.includes('nap')
  };

  const btn = document.getElementById('sleepSaveBtn');
  btn.disabled = true;
  try {
    await apiLog(payload);
    closeSleepModal();
    document.getElementById('sleepForm').reset();
    setRating(null, 0);
    document.querySelectorAll('.rating-btn').forEach(b => b.classList.remove('selected'));
    document.querySelectorAll('.factor-chip').forEach(c => c.classList.remove('selected'));
    if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
    const data = await apiMe();
    state.profile = data;
    renderDashboard();
    renderJournal();
    renderStats();
    renderProfile();
  } catch (err) {
    if (tg && tg.showAlert) {
      tg.showAlert(t('saveFailed'));
    } else {
      alert(t('saveFailed'));
    }
  } finally {
    btn.disabled = false;
  }
}

function openGoalsModal() {
  const p = state.profile;
  if (!p) return;
  document.getElementById('goalBedtime').value = p.goal_bedtime || '23:30';
  document.getElementById('goalWaketime').value = p.goal_waketime || '07:30';
  document.getElementById('goalDuration').value = String(Number(p.goal_duration || 8).toFixed(1));
  document.getElementById('goalsModal').classList.add('active');
}

function closeGoalsModal() {
  document.getElementById('goalsModal').classList.remove('active');
}

async function saveGoals(e) {
  e.preventDefault();
  const payload = {
    goal_bedtime: document.getElementById('goalBedtime').value,
    goal_waketime: document.getElementById('goalWaketime').value,
    goal_duration: Number(document.getElementById('goalDuration').value)
  };
  try {
    await apiGoals(payload);
    const data = await apiMe();
    state.profile = data;
    closeGoalsModal();
    renderProfile();
    renderDashboard();
    if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
  } catch (err) {
    if (tg && tg.showAlert) tg.showAlert(t('saveFailed'));
    else alert(t('saveFailed'));
  }
}

/* ===================================================
   UTILS
   =================================================== */
function formatTime(dateObj) {
  const h = dateObj.getHours().toString().padStart(2, '0');
  const m = dateObj.getMinutes().toString().padStart(2, '0');
  return `${h}:${m}`;
}

function toggleTheme() {
  document.body.classList.toggle('light-theme');
  const icon = document.querySelector('#themeToggle i');
  if (document.body.classList.contains('light-theme')) {
    icon.className = 'fa-solid fa-moon';
  } else {
    icon.className = 'fa-solid fa-sun';
  }
}

/* ===================================================
   7-DAY SLEEP COURSE & AUDIO RELAX GENERATOR LOGIC
   (контент курсу — локально, доступ — з сервера)
   =================================================== */

const COURSE_DAYS = [
  {
    day: 1,
    title: "☀️ Світловий біохакінг & Мелатонін",
    subtitle: "Активація циркадного ритму та рецепторів сну",
    icon: "fa-sun",
    content: `
      <h4>Чому ви важко засинаєте?</h4>
      <p>Наш мозок виділяє <strong>мелатонін</strong> (гормон сну) тільки тоді, коли сітківка ока перестає отримувати синє спектральне світло (екрани смартфонів, телевізори, яскраве ЛЕД-освітлення).</p>

      <div class="highlight-box">
        <strong>⚡ Практичне завдання на сьогодні:</strong>
        <ul>
          <li><strong>Зранку:</strong> Отримайте 10-15 хвилин прямого сонячного світла впродовж 1 години після підйому. Це "перезапускає" біологічний годинник.</li>
          <li><strong>Ввечері:</strong> За 45 хвилин до сну увімкніть тьмяне тепле світло і відкладіть телефон.</li>
        </ul>
      </div>

      <h4>💡 Головний секрет:</h4>
      <p>Синє світло смартфонів блокує виділення мелатоніну майже на 80%. Використовуйте режим "Нічне світло / Night Shift" на телефоні після 20:00.</p>
    `
  },
  {
    day: 2,
    title: "🧘 US Navy 2-Min Technique (Військова методика)",
    subtitle: "Як заснути за 120 секунд в будь-яких умовах",
    icon: "fa-user-ninja",
    content: `
      <h4>Техніка засинання льотчиків ВМС США</h4>
      <p>Ця методика дозволяє заснути за 2 хвилини після 6 тижнів практики, навіть за наявності шуму чи стресу.</p>

      <div class="highlight-box">
        <strong>🧘 Покрокова інструкція:</strong>
        <ol style="padding-left: 20px; margin-top: 8px;">
          <li><strong>Розслаблення обличчя:</strong> Заплющте очі. Повільно розслабте чоло, щоки, щелепу та язик.</li>
          <li><strong>Опустіть плечі:</strong> Дозвольте плечам повністю "провалитися" в матрац. Розслабте руки від плечей до кінчиків пальців.</li>
          <li><strong>Видихніть:</strong> Розслабте грудну клітку та ноги — від стегон до литок і ступень.</li>
          <li><strong>Очистіть розум (10 сек):</strong> Уявіть, що ви лежите у човні на спокійній гладі озера під зоряним небом. Якщо виникають думки, повторюйте про себе: <em>"Не думай, не думай, не думай"</em>.</li>
        </ol>
      </div>
    `
  },
  {
    day: 3,
    title: "🫁 Техніка 4-7-8 & Активація спокою",
    subtitle: "Перемикання нервової системи в режим відновлення",
    icon: "fa-wind",
    content: `
      <h4>Активація вагусного нерва (Парасимпатика)</h4>
      <p>Коли ви подовжуєте видих, ваш серцевий ритм сповільнюється, а рівень кортизолу (гормону стресу) стрімко падає.</p>

      <div class="highlight-box">
        <strong>🌬️ Дихальна формула 4-7-8:</strong>
        <ul>
          <li><strong>4 сек:</strong> Спокійний вдих носом.</li>
          <li><strong>7 сек:</strong> Затримка дихання в легенях.</li>
          <li><strong>8 сек:</strong> Повільний видих ротом зі звуком "фу-у-у".</li>
        </ul>
        <p style="margin-top:8px;">Повторіть 4 повних цикли (займає всього 2 хвилини).</p>
      </div>

      <p>💡 Скористайтеся вкладкою <strong>"Релакс"</strong> у нашому Mini App, де вбудовано візуальний анімований таймер 4-7-8!</p>
    `
  },
  {
    day: 4,
    title: "☕ Кофеїнове вікно & Вечірнє харчування",
    subtitle: "Як кава та вечеря блокують фазу глибокого сну",
    icon: "fa-mug-hot",
    content: `
      <h4>Період напіввиведення кофеїну</h4>
      <p>Кофеїн блокує рецептори аденозину (речовини, яка накопичує втому). Період напіввиведення кофеїну становить <strong>6 годин</strong>, а повне виведення — до 12 годин!</p>

      <div class="highlight-box">
        <strong>🥗 Правила харчування для засинання:</strong>
        <ul>
          <li><strong>Остання кава:</strong> Не пізніше ніж за 7-8 годин до лягання спати (якщо спати о 23:00 — кава до 15:00).</li>
          <li><strong>Вечеря:</strong> За 2.5-3 години до сну. Уникайте важкого жирного м'яса та гострих страв.</li>
          <li><strong>Легкий перекус перед сном:</strong> Жменя мигдалю, банани або теплий ромашковий чай (містять магній та триптофан).</li>
        </ul>
      </div>
    `
  },
  {
    day: 5,
    title: "📝 Правило 20 хвилин & 'Коробка тривог'",
    subtitle: "Що робити, якщо крутишся в ліжку і не можеш заснути",
    icon: "fa-brain",
    content: `
      <h4>Чому не можна лежати без сну понад 20 хвилин?</h4>
      <p>Якщо ви довго лежите в ліжку й не засинаєте, мозок створює негативний нейронний зв'язок: <em>"Ліжко = місце тривоги й неспокою"</em>.</p>

      <div class="highlight-box">
        <strong>💡 Правило 20 хвилин:</strong>
        <p>Якщо ви не заснули за 20 хвилин — устаньте з ліжка. Підійдіть до крісла або дивану при приглушеному світлі та почитайте паперову книгу або послухайте заспокійливу музику. Повертайтеся в ліжко тільки коли з'явиться сонливість.</p>
      </div>

      <div class="highlight-box" style="border-left-color: var(--accent-purple);">
        <strong>📝 Техніка "Коробка тривог" (Brain Dump):</strong>
        <p>За 1 годину до сну візьміть блокнот і випишіть УСІ тривожні думки та список справ на завтра. Коли думки на папері, мозку більше не потрібно витрачати ресурс на їх утримання вночі.</p>
      </div>
    `
  },
  {
    day: 6,
    title: "❄️ Мікроклімат спальні & Глибокий сон",
    subtitle: "Терморегуляція тіла для глибокої фази NREM",
    icon: "fa-snowflake",
    content: `
      <h4>Як температура впливає на якість сну?</h4>
      <p>Щоб заснути, внутрішня температура тіла повинна знизитися приблизно на 1°C. Саме тому в теплій або задушливій кімнаті заснути майже неможливо.</p>

      <div class="highlight-box">
        <strong>🌡️ Оптимальний чек-лист спальні:</strong>
        <ul>
          <li><strong>Температура:</strong> 18-20°C (65-68°F).</li>
          <li><strong>Провітрювання:</strong> Відкрийте вікно на 10 хвилин перед сном для насичення киснем.</li>
          <li><strong>Темрява:</strong> Використовуйте щільні штори (Blackout) або маску для сну. Навіть слабкий діод від ТВ може зменшити глибину сну.</li>
          <li><strong>Гарячий душ за 1-1.5 год:</strong> Після теплого душу судини розширюються, тіло швидко віддає тепло і температура падає — це викликає сильну сонливість.</li>
        </ul>
      </div>
    `
  },
  {
    day: 7,
    title: "📜 Ідеальний вечірній ритуал & Фінал",
    subtitle: "Створення власного стійкого алгоритму засинання",
    icon: "fa-certificate",
    content: `
      <h4>Закріплення результату</h4>
      <p>Вітаємо на 7-му дні інтенсиву! Тепер ваша мета — об'єднати найкращі техніки у ваш щоденний приємний вечірній ритуал.</p>

      <div class="highlight-box">
        <strong>✨ Ваша ідеальна вечірня рутина (30 хвилин до сну):</strong>
        <ol style="padding-left: 20px; margin-top: 8px;">
          <li>Провітрити кімнату та вимкнути екрани.</li>
          <li>Виписати завдання на завтра в блокнот.</li>
          <li>Увімкнути релакс-звуки (дощ/океан) у цьому додатку.</li>
          <li>Зробити 4-7-8 дихання та застосувати Військову методику розслаблення тіла.</li>
        </ol>
      </div>

      <p style="text-align:center; font-weight:bold; color:var(--accent-emerald); margin-top:12px;">
        🎉 Ви пройшли 7-денний курс! Продовжуйте дотримуватися чек-листа щовечора!
      </p>
    `
  }
];

let activeLessonDay = 1;
let selectedTariffKey = '3m';

function renderCourseTab() {
  const paywallElem = document.getElementById('coursePaywall');
  const contentElem = document.getElementById('courseContent');
  const badgeText = document.getElementById('courseProgressText');
  const isPremium = !!(state.profile && state.profile.is_premium);

  if (!isPremium) {
    if (paywallElem) paywallElem.style.display = 'block';
    if (contentElem) contentElem.style.display = 'none';
    if (badgeText) badgeText.textContent = 'Преміум🔒';
    return;
  }

  if (paywallElem) paywallElem.style.display = 'none';
  if (contentElem) contentElem.style.display = 'block';

  if (!state.courseProgress) {
    state.courseProgress = { completedDays: [], checklist: {} };
  }
  const completed = state.courseProgress.completedDays || [];
  const count = completed.length;
  const percent = Math.round((count / 7) * 100);

  if (badgeText) badgeText.textContent = `${count}/7 Днів`;
  const pp = document.getElementById('courseProgressPercent');
  const pb = document.getElementById('courseProgressBar');
  if (pp) pp.textContent = `${percent}%`;
  if (pb) pb.style.width = `${percent}%`;

  const chk = state.courseProgress.checklist || {};
  let chkDoneCount = 0;
  const keys = ['air', 'screens', 'braindump', 'caffeine', 'relax'];
  keys.forEach(k => {
    const elem = document.getElementById(`chk-${k}`);
    if (elem) {
      elem.checked = !!chk[k];
      if (chk[k]) chkDoneCount++;
    }
  });
  const chkTag = document.getElementById('checklistCountTag');
  if (chkTag) chkTag.textContent = `${chkDoneCount}/${keys.length} виконано`;

  const grid = document.getElementById('courseDaysGrid');
  if (!grid) return;
  grid.innerHTML = '';

  COURSE_DAYS.forEach(item => {
    const isDone = completed.includes(item.day);
    const card = document.createElement('div');
    card.className = `day-card ${isDone ? 'completed' : ''}`;
    card.onclick = () => openLessonModal(item.day);

    card.innerHTML = `
      <div class="day-info">
        <div class="day-number-badge">
          ${isDone ? '<i class="fa-solid fa-check"></i>' : item.day}
        </div>
        <div class="day-texts">
          <h5>${item.title}</h5>
          <p>${item.subtitle}</p>
        </div>
      </div>
      <div class="day-status-icon">
        <i class="fa-solid ${isDone ? 'fa-circle-check' : 'fa-chevron-right'}"></i>
      </div>
    `;

    grid.appendChild(card);
  });
}

function toggleChecklistItem(checkbox, key) {
  triggerHaptic();
  if (!state.courseProgress) state.courseProgress = { completedDays: [], checklist: {} };
  if (!state.courseProgress.checklist) state.courseProgress.checklist = {};

  state.courseProgress.checklist[key] = checkbox.checked;
  saveLocal();

  const keys = ['air', 'screens', 'braindump', 'caffeine', 'relax'];
  const doneCount = keys.filter(k => state.courseProgress.checklist[k]).length;
  const chkTag = document.getElementById('checklistCountTag');
  if (chkTag) chkTag.textContent = `${doneCount}/${keys.length} виконано`;
}

function openLessonModal(dayNumber) {
  triggerHaptic();
  activeLessonDay = dayNumber;
  const lesson = COURSE_DAYS.find(d => d.day === dayNumber);
  if (!lesson) return;

  document.getElementById('lessonModalTitle').textContent = `${t('day')} ${lesson.day}: ${lesson.title}`;
  document.getElementById('lessonModalBody').innerHTML = lesson.content;

  const btn = document.getElementById('completeLessonBtn');
  const isDone = state.courseProgress.completedDays.includes(dayNumber);
  if (isDone) {
    btn.innerHTML = '<i class="fa-solid fa-check-double"></i> ' + t('done');
    btn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
  } else {
    btn.innerHTML = '<i class="fa-solid fa-check-circle"></i> ' + t('markDone');
    btn.style.background = 'linear-gradient(135deg, var(--accent-indigo), #4f46e5)';
  }

  document.getElementById('courseLessonModal').classList.add('active');
}

function closeLessonModal() {
  triggerHaptic();
  document.getElementById('courseLessonModal').classList.remove('active');
}

function toggleCompleteCurrentLesson() {
  triggerHaptic();
  if (!state.courseProgress.completedDays) state.courseProgress.completedDays = [];

  const idx = state.courseProgress.completedDays.indexOf(activeLessonDay);
  if (idx > -1) {
    state.courseProgress.completedDays.splice(idx, 1);
  } else {
    state.courseProgress.completedDays.push(activeLessonDay);
  }
  saveLocal();

  closeLessonModal();
  renderCourseTab();
}

/* ===================================================
   WEB AUDIO RELAXATION SOUND GENERATOR
   =================================================== */

function selectSoundPreset(preset) {
  triggerHaptic();
  currentSoundPreset = preset;

  document.querySelectorAll('.sound-chip').forEach(c => c.classList.remove('active'));
  const activeBtn = document.getElementById(`preset-${preset}`);
  if (activeBtn) activeBtn.classList.add('active');

  if (isAudioPlaying) {
    stopAudioPreset();
    playAudioPreset(preset);
  }
}

function toggleAudioPreset() {
  triggerHaptic();
  if (isAudioPlaying) {
    stopAudioPreset();
  } else {
    playAudioPreset(currentSoundPreset);
  }
}

function playAudioPreset(preset) {
  try {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }

    stopAudioPreset();

    const bufferSize = audioCtx.sampleRate * 2;
    const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
    const data = buffer.getChannelData(0);

    let lastOut = 0.0;
    for (let i = 0; i < bufferSize; i++) {
      const white = Math.random() * 2 - 1;
      if (preset === 'rain' || preset === 'ocean') {
        data[i] = (lastOut + (0.02 * white)) / 1.02;
        lastOut = data[i];
        data[i] *= 3.5;
      } else if (preset === 'forest') {
        data[i] = (lastOut + (0.01 * white)) / 1.01;
        lastOut = data[i];
        data[i] *= 2.5;
      } else {
        data[i] = white * 0.15;
      }
    }

    const noiseSource = audioCtx.createBufferSource();
    noiseSource.buffer = buffer;
    noiseSource.loop = true;

    const filter = audioCtx.createBiquadFilter();
    if (preset === 'rain') {
      filter.type = 'lowpass';
      filter.frequency.value = 800;
    } else if (preset === 'ocean') {
      filter.type = 'lowpass';
      filter.frequency.value = 400;

      const lfo = audioCtx.createOscillator();
      lfo.frequency.value = 0.12;
      const lfoGain = audioCtx.createGain();
      lfoGain.gain.value = 250;
      lfo.connect(lfoGain);
      lfoGain.connect(filter.frequency);
      lfo.start();
      activeNoiseNodes.push(lfo);
    } else if (preset === 'forest') {
      filter.type = 'bandpass';
      filter.frequency.value = 1200;
      filter.Q.value = 1.0;
    } else {
      filter.type = 'lowpass';
      filter.frequency.value = 1000;
    }

    const masterGain = audioCtx.createGain();
    masterGain.gain.value = 0.35;

    noiseSource.connect(filter);
    filter.connect(masterGain);
    masterGain.connect(audioCtx.destination);

    noiseSource.start();

    activeNoiseNodes.push(noiseSource, masterGain);
    isAudioPlaying = true;

    const btn = document.getElementById('soundToggleBtn');
    if (btn) {
      btn.innerHTML = '<i class="fa-solid fa-stop"></i> Вимкнути звук';
      btn.classList.add('playing');
    }
    const tag = document.getElementById('audioStatusTag');
    if (tag) {
      tag.textContent = '▶️ Звук лунає';
      tag.classList.add('active');
    }

  } catch (e) {
    console.error("Web Audio error", e);
  }
}

function stopAudioPreset() {
  activeNoiseNodes.forEach(node => {
    try {
      if (node.stop) node.stop();
      if (node.disconnect) node.disconnect();
    } catch (e) {}
  });
  activeNoiseNodes = [];
  isAudioPlaying = false;

  if (audioTimerTimeout) {
    clearTimeout(audioTimerTimeout);
    audioTimerTimeout = null;
  }

  const btn = document.getElementById('soundToggleBtn');
  if (btn) {
    btn.innerHTML = '<i class="fa-solid fa-play"></i> Увімкнути звук';
    btn.classList.remove('playing');
  }
  const tag = document.getElementById('audioStatusTag');
  if (tag) {
    tag.textContent = '⏸️ Вимкнено';
    tag.classList.remove('active');
  }
}

function setAudioTimer(minutesStr) {
  triggerHaptic();
  const mins = parseInt(minutesStr, 10);
  if (audioTimerTimeout) clearTimeout(audioTimerTimeout);

  if (mins > 0 && isAudioPlaying) {
    audioTimerTimeout = setTimeout(() => {
      stopAudioPreset();
    }, mins * 60 * 1000);
  }
}

/* ===================================================
   PAYWALL & SUBSCRIPTION HANDLERS
   =================================================== */

function selectTariff(cardElem, tariffKey) {
  triggerHaptic();
  selectedTariffKey = tariffKey;

  document.querySelectorAll('.pricing-card').forEach(c => c.classList.remove('active'));
  cardElem.classList.add('active');
}

function initiateSubscriptionPayment() {
  triggerHaptic();

  // Оплата та видача доступу відбуваються ВИКЛЮЧНО через Telegram-бота:
  // користувач оплачує 99 грн через Monobank, надсилає квитанцію боту,
  // а адміністратор підтверджує оплату та активує преміум.
  // Mini App НЕ надає доступ самостійно (щоб уникнути безкоштовного обходу оплати).
  const message =
    "Щоб придбати 7-денний інтенсив за 99 грн:\n\n" +
    "1️⃣ Поверніться в чат з ботом\n" +
    "2️⃣ Натисніть «🎓 7-Денний Інтенсив сну» → «Придбати доступ»\n" +
    "3️⃣ Оплатіть через Monobank і надішліть квитанцію боту\n\n" +
    "Після підтвердження оплати доступ відкриється автоматично.";

  if (tg && tg.showPopup) {
    tg.showPopup({
      title: "Придбати курс за 99 грн 💳",
      message: message,
      buttons: [
        { id: "close", type: "default", text: "Зрозуміло" }
      ]
    }, () => {
      if (tg.close) tg.close();
    });
  } else {
    alert(message);
  }
}