// Telegram WebApp SDK Initialization
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

// Dedicated Sleep Tracker State
let state = {
  targetGoal: 8.0, // Hours
  isSleeping: false,
  sleepStartTime: null, // ISO String
  selectedFactors: [],
  logs: [
    { id: 1, date: 'Середа, 5 серп.', bedtime: '23:30', waketime: '07:30', duration: 8.0, quality: '🚀 Відмінно', factors: ['🧘 Медитація', '📖 Читання'], note: 'Легкий підйом' },
    { id: 2, date: 'Вівторок, 4 серп.', bedtime: '00:15', waketime: '07:45', duration: 7.5, quality: '😊 Добре', factors: ['📱 Екран'], note: 'Пізно заснув' },
    { id: 3, date: 'Понеділок, 3 серп.', bedtime: '23:00', waketime: '07:00', duration: 8.0, quality: '🚀 Відмінно', factors: ['🧘 Медитація'], note: 'Чудовий сон' },
    { id: 4, date: 'Неділя, 2 серп.', bedtime: '01:00', waketime: '08:00', duration: 7.0, quality: '😐 Нормально', factors: ['☕ Кава пізно'], note: 'Довго засинав' },
    { id: 5, date: 'Субота, 1 серп.', bedtime: '23:45', waketime: '08:15', duration: 8.5, quality: '🚀 Відмінно', factors: ['🏃 Спорт'], note: 'Виспався на славу' },
    { id: 6, date: "П'ятниця, 31 лип.", bedtime: '00:30', waketime: '07:30', duration: 7.0, quality: '😊 Добре', factors: [], note: '' },
    { id: 7, date: 'Четвер, 30 лип.', bedtime: '23:15', waketime: '07:15', duration: 8.0, quality: '🚀 Відмінно', factors: ['📖 Читання'], note: 'Гарне самопочуття' }
  ],
  courseProgress: {
    completedDays: [1],
    checklist: { air: false, screens: false, braindump: false, caffeine: false, relax: false }
  }
};

let liveTimerInterval = null;
let breathingInterval = null;
let isBreathingRunning = false;

// Audio Ambient Sound Generator (Web Audio API)
let audioCtx = null;
let isAudioPlaying = false;
let currentSoundPreset = 'rain';
let activeNoiseNodes = [];
let audioTimerTimeout = null;

// DOM Loaded Initialization
document.addEventListener('DOMContentLoaded', () => {
  loadState();
  initTelegramUser();
  renderWeeklyChart();
  renderJournal();
  updateSleepTimerUI();

  // Render 7-Day Sleep Course & Checklist
  renderCourseTab();

  // Check if active sleep timer was running
  if (state.isSleeping && state.sleepStartTime) {
    startLiveTimer();
  }

  // Theme Toggle listener
  document.getElementById('themeToggle').addEventListener('click', toggleTheme);
});

// Telegram User Identification
function initTelegramUser() {
  const userNameElem = document.getElementById('userName');
  const userAvatarElem = document.getElementById('userAvatar');

  if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
    const user = tg.initDataUnsafe.user;
    userNameElem.textContent = user.first_name + (user.last_name ? ` ${user.last_name}` : '');
    
    if (user.photo_url) {
      userAvatarElem.innerHTML = `<img src="${user.photo_url}" alt="Avatar">`;
    }
  }
}

// LocalStorage Helper
function saveState() {
  localStorage.setItem('dedicated_sleep_tracker_state', JSON.stringify(state));
}

function loadState() {
  const saved = localStorage.getItem('dedicated_sleep_tracker_state');
  if (saved) {
    try {
      state = { ...state, ...JSON.parse(saved) };
    } catch (e) {
      console.error("Error loading saved state", e);
    }
  }
}

// Navigation & Tab Switching
function switchTab(tabName) {
  triggerHaptic();

  document.querySelectorAll('.tab-page').forEach(page => page.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));

  const targetPage = document.getElementById(`tab-${tabName}`);
  if (targetPage) targetPage.classList.add('active');

  const targetBtn = document.querySelector(`.nav-item[data-tab="${tabName}"]`);
  if (targetBtn) targetBtn.classList.add('active');
}

// Trigger Haptic Feedback
function triggerHaptic() {
  if (tg && tg.HapticFeedback) {
    tg.HapticFeedback.impactOccurred('light');
  }
}

// SLEEP TIMER LOGIC
function toggleSleepTimer() {
  triggerHaptic();

  if (!state.isSleeping) {
    // Start Sleep Timer
    state.isSleeping = true;
    state.sleepStartTime = new Date().toISOString();
    saveState();
    startLiveTimer();
    updateSleepTimerUI();
  } else {
    // Stop Sleep Timer & Save Log
    stopLiveTimer();
    const startTime = new Date(state.sleepStartTime);
    const endTime = new Date();

    const durationHours = Math.max(0.1, (endTime - startTime) / (1000 * 60 * 60));
    const roundedDuration = Math.round(durationHours * 10) / 10;

    const bedtimeStr = formatTime(startTime);
    const waketimeStr = formatTime(endTime);

    const nowStr = new Date().toLocaleDateString('uk-UA', { weekday: 'long', day: 'numeric', month: 'short' });
    const formattedDate = nowStr.charAt(0).toUpperCase() + nowStr.slice(1);

    const newLog = {
      id: Date.now(),
      date: formattedDate,
      bedtime: bedtimeStr,
      waketime: waketimeStr,
      duration: roundedDuration,
      quality: roundedDuration >= 7 ? '🚀 Відмінно' : '😊 Добре',
      factors: ['⏱️ Живий таймер'],
      note: 'Автоматично зафіксовано'
    };

    state.logs.unshift(newLog);
    state.isSleeping = false;
    state.sleepStartTime = null;
    saveState();

    updateSleepTimerUI();
    renderWeeklyChart();
    renderJournal();
  }
}

function startLiveTimer() {
  if (liveTimerInterval) clearInterval(liveTimerInterval);
  liveTimerInterval = setInterval(updateLiveTimerDisplay, 1000);
  updateLiveTimerDisplay();
}

function stopLiveTimer() {
  if (liveTimerInterval) clearInterval(liveTimerInterval);
}

function updateLiveTimerDisplay() {
  if (!state.isSleeping || !state.sleepStartTime) {
    document.getElementById('sleepTimerDisplay').textContent = '00:00:00';
    return;
  }

  const start = new Date(state.sleepStartTime);
  const now = new Date();
  const diffMs = Math.max(0, now - start);

  const hours = Math.floor(diffMs / (1000 * 60 * 60)).toString().padStart(2, '0');
  const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60)).toString().padStart(2, '0');
  const seconds = Math.floor((diffMs % (1000 * 60)) / 1000).toString().padStart(2, '0');

  document.getElementById('sleepTimerDisplay').textContent = `${hours}:${minutes}:${seconds}`;
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
    tag.textContent = '🌙 Ви зараз спите';
    tag.style.color = '#34d399';
    sub.textContent = 'Таймер сну активний. Натисніть, коли прокинетеся.';
    btnText.textContent = 'Прокинутися ☀️';
    btn.querySelector('i').className = 'fa-solid fa-sun';
    moonIcon.className = 'fa-solid fa-bed';
  } else {
    card.classList.remove('sleeping');
    tag.textContent = '☀️ Ви прокинулися';
    tag.style.color = '#c7d2fe';
    sub.textContent = 'Натисніть кнопку, коли лягаєте спати';
    btnText.textContent = 'Лягати спати';
    btn.querySelector('i').className = 'fa-solid fa-bed';
    moonIcon.className = 'fa-solid fa-moon';
    document.getElementById('sleepTimerDisplay').textContent = '00:00:00';
  }

  // Update last sleep and average stats
  if (state.logs.length > 0) {
    const last = state.logs[0];
    document.getElementById('lastSleepHours').innerHTML = `${last.duration.toFixed(1)} <small>год</small>`;
    document.getElementById('lastSleepQuality').textContent = last.quality;

    const sum = state.logs.slice(0, 7).reduce((acc, curr) => acc + curr.duration, 0);
    const avg = sum / Math.min(7, state.logs.length);
    document.getElementById('avgSleepHours').innerHTML = `${avg.toFixed(1)} <small>год</small>`;
    document.getElementById('chartAvgTag').textContent = `${avg.toFixed(1)} год / ніч`;
  }
}

// WEEKLY BAR CHART GENERATOR
function renderWeeklyChart() {
  const container = document.getElementById('barChartContainer');
  container.innerHTML = '';

  const recentLogs = state.logs.slice(0, 7).reverse();
  const maxGoal = 10.0;

  recentLogs.forEach(log => {
    const col = document.createElement('div');
    col.className = 'bar-col';

    const heightPercent = Math.min(100, (log.duration / maxGoal) * 100);
    const isTarget = log.duration >= state.targetGoal;

    const dayName = log.date.split(',')[0].slice(0, 2);

    col.innerHTML = `
      <span class="bar-val">${log.duration}г</span>
      <div class="bar-fill-wrap">
        <div class="bar-fill ${isTarget ? 'target-reached' : ''}" style="height: ${heightPercent}%"></div>
      </div>
      <span class="bar-label">${dayName}</span>
    `;

    container.appendChild(col);
  });
}

// JOURNAL & HISTORY
function renderJournal() {
  const container = document.getElementById('journalList');
  container.innerHTML = '';

  if (state.logs.length === 0) {
    container.innerHTML = '<p style="color:var(--text-secondary); text-align:center; padding:20px;">Немає записів сну</p>';
    return;
  }

  state.logs.forEach(log => {
    const card = document.createElement('div');
    card.className = 'journal-card';

    const factorsHTML = (log.factors || []).map(f => `<span class="factor-badge">${f}</span>`).join('');

    card.innerHTML = `
      <div class="journal-top">
        <span class="journal-date">${log.date}</span>
        <span class="journal-duration">${log.duration.toFixed(1)} год</span>
      </div>
      <div class="journal-times">
        <i class="fa-solid fa-moon"></i> ${log.bedtime} — <i class="fa-solid fa-sun"></i> ${log.waketime} (${log.quality})
      </div>
      ${log.note ? `<p style="font-size:0.8rem; color:var(--text-secondary);">${log.note}</p>` : ''}
      ${factorsHTML ? `<div class="journal-factors">${factorsHTML}</div>` : ''}
    `;

    container.appendChild(card);
  });
}

// MODAL CONTROLS & FACTORS
function openSleepModal() {
  document.getElementById('sleepModal').classList.add('active');
}

function closeSleepModal() {
  document.getElementById('sleepModal').classList.remove('active');
}

function toggleFactor(chip) {
  chip.classList.toggle('selected');
}

function saveSleepLog(e) {
  e.preventDefault();
  const bedtime = document.getElementById('sleepBedtime').value;
  const waketime = document.getElementById('sleepWaketime').value;
  const quality = document.getElementById('sleepQuality').value;
  const note = document.getElementById('sleepNote').value;

  // Selected factors
  const selectedChips = document.querySelectorAll('.factor-chip.selected');
  const factors = Array.from(selectedChips).map(c => c.getAttribute('data-factor'));

  if (!bedtime || !waketime) return;

  const [bH, bM] = bedtime.split(':').map(Number);
  const [wH, wM] = waketime.split(':').map(Number);

  let bedMin = bH * 60 + bM;
  let wakeMin = wH * 60 + wM;
  if (wakeMin < bedMin) wakeMin += 24 * 60;

  const durationHours = Math.round(((wakeMin - bedMin) / 60) * 10) / 10;

  const nowStr = new Date().toLocaleDateString('uk-UA', { weekday: 'long', day: 'numeric', month: 'short' });
  const formattedDate = nowStr.charAt(0).toUpperCase() + nowStr.slice(1);

  const newLog = {
    id: Date.now(),
    date: formattedDate,
    bedtime: bedtime,
    waketime: waketime,
    duration: durationHours,
    quality: quality,
    factors: factors,
    note: note ? note.trim() : ''
  };

  state.logs.unshift(newLog);
  saveState();

  renderWeeklyChart();
  renderJournal();
  updateSleepTimerUI();
  closeSleepModal();

  // Reset factors
  selectedChips.forEach(c => c.classList.remove('selected'));
  document.getElementById('sleepForm').reset();
}

// UTILS
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

  if (!state.isPremium) {
    if (paywallElem) paywallElem.style.display = 'block';
    if (contentElem) contentElem.style.display = 'none';
    if (badgeText) badgeText.textContent = 'Преміум🔒';
    return;
  }

  // Premium active
  if (paywallElem) paywallElem.style.display = 'none';
  if (contentElem) contentElem.style.display = 'block';

  if (!state.courseProgress) {
    state.courseProgress = { completedDays: [], checklist: {} };
  }
  const completed = state.courseProgress.completedDays || [];
  const count = completed.length;
  const percent = Math.round((count / 7) * 100);

  if (badgeText) badgeText.textContent = `${count}/7 Днів`;
  document.getElementById('courseProgressPercent').textContent = `${percent}%`;
  document.getElementById('courseProgressBar').style.width = `${percent}%`;

  // Render Evening Checklist
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

  // Render 7-Day Grid
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
  saveState();

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

  document.getElementById('lessonModalTitle').textContent = `День ${lesson.day}: ${lesson.title}`;
  document.getElementById('lessonModalBody').innerHTML = lesson.content;

  const btn = document.getElementById('completeLessonBtn');
  const isDone = state.courseProgress.completedDays.includes(dayNumber);
  if (isDone) {
    btn.innerHTML = '<i class="fa-solid fa-check-double"></i> Урок пройдено (натисніть, щоб скасувати)';
    btn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
  } else {
    btn.innerHTML = '<i class="fa-solid fa-check-circle"></i> Позначити урок пройденим';
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
  saveState();

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

    // Create Noise Buffer
    const bufferSize = audioCtx.sampleRate * 2;
    const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
    const data = buffer.getChannelData(0);

    let lastOut = 0.0;
    for (let i = 0; i < bufferSize; i++) {
      const white = Math.random() * 2 - 1;
      if (preset === 'rain' || preset === 'ocean') {
        // Pink / Brown noise filter simulation
        data[i] = (lastOut + (0.02 * white)) / 1.02;
        lastOut = data[i];
        data[i] *= 3.5;
      } else if (preset === 'forest') {
        // Soft nature noise
        data[i] = (lastOut + (0.01 * white)) / 1.01;
        lastOut = data[i];
        data[i] *= 2.5;
      } else {
        // Soft pink noise
        data[i] = white * 0.15;
      }
    }

    const noiseSource = audioCtx.createBufferSource();
    noiseSource.buffer = buffer;
    noiseSource.loop = true;

    // Filter Node
    const filter = audioCtx.createBiquadFilter();
    if (preset === 'rain') {
      filter.type = 'lowpass';
      filter.frequency.value = 800;
    } else if (preset === 'ocean') {
      filter.type = 'lowpass';
      filter.frequency.value = 400;

      // LFO modulation for ocean waves effect
      const lfo = audioCtx.createOscillator();
      lfo.frequency.value = 0.12; // 8 sec wave cycle
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

  if (tg && tg.showPopup) {
    tg.showPopup({
      title: "Придбати курс за 99 грн 💳",
      message: `Оплата 7-денного інтенсиву «Засинай за 5 хвилин» — 99 грн (разово).\n\nОберіть спосіб оплати або активуйте доступ:`,
      buttons: [
        { id: "pay_mono", type: "default", text: "Оплатити через Monobank (99 грн)" },
        { id: "demo", type: "ok", text: "Активувати демо-доступ" },
        { id: "cancel", type: "cancel", text: "Скасувати" }
      ]
    }, (btnId) => {
      if (btnId === 'pay_mono' || btnId === 'demo') {
        activateDemoPremium();
      }
    });
  } else {
    // Fallback in web browser
    const proceed = confirm(`Придбати 7-денний курс сну за 99 грн?\n\nНатисніть "ОК", щоб перейти до Monobank / Банку або увімкнути доступ.`);
    if (proceed) {
      activateDemoPremium();
    }
  }
}

function applyPromoCode() {
  triggerHaptic();
  const input = document.getElementById('promoInput');
  const feedback = document.getElementById('promoFeedback');
  if (!input || !feedback) return;

  const code = input.value.trim().toUpperCase();
  const validCodes = ['SLEEP2026', 'DEMO', 'PREMIUM', 'SLEEP', 'MONO'];

  if (validCodes.includes(code)) {
    feedback.className = 'promo-feedback success';
    feedback.textContent = '✅ Промокод активовано! Повний Преміум доступ відкрито 🎉';
    
    setTimeout(() => {
      activateDemoPremium();
    }, 800);
  } else {
    feedback.className = 'promo-feedback error';
    feedback.textContent = '❌ Невірний або застарілий промокод. Спробуйте SLEEP2026';
  }
}

function activateDemoPremium() {
  triggerHaptic();
  state.isPremium = true;
  saveState();
  renderCourseTab();

  if (tg && tg.showAlert) {
    tg.showAlert("🎉 Преміум підписку успішно активовано! Доступ до всіх 7 днів інтенсиву відкрито.");
  }
}


