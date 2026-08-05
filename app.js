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
  ]
};

let liveTimerInterval = null;
let breathingInterval = null;
let isBreathingRunning = false;

// DOM Loaded Initialization
document.addEventListener('DOMContentLoaded', () => {
  loadState();
  initTelegramUser();
  calculateSleepCycles();
  renderWeeklyChart();
  renderJournal();
  updateSleepTimerUI();

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

// SLEEP CYCLES CALCULATOR
function calculateSleepCycles() {
  const now = new Date();
  document.getElementById('currentTimeShort').textContent = formatTime(now);

  const container = document.getElementById('cyclesChips');
  container.innerHTML = '';

  // Calculate wake up times for 3, 4, 5, 6 sleep cycles (90 min each + 15 min to fall asleep)
  const cycles = [3, 4, 5, 6]; // 4.5h, 6h, 7.5h, 9h
  cycles.forEach(c => {
    const wakeTime = new Date(now.getTime() + (c * 90 + 15) * 60 * 1000);
    const chip = document.createElement('div');
    chip.className = 'cycle-chip';
    chip.innerHTML = `
      <strong>${formatTime(wakeTime)}</strong>
      <span>${c * 1.5} год (${c} ц)</span>
    `;
    container.appendChild(chip);
  });
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

// BREATHING EXERCISE (4-7-8 Technique)
function toggleBreathingExercise() {
  triggerHaptic();
  const circle = document.getElementById('breathCircle');
  const text = document.getElementById('breathText');
  const instruction = document.getElementById('breathInstruction');
  const btn = document.getElementById('breathStartBtn');

  if (!isBreathingRunning) {
    isBreathingRunning = true;
    btn.innerHTML = '<i class="fa-solid fa-stop"></i> Зупинити';
    
    let phase = 0; // 0: Inhale 4s, 1: Hold 7s, 2: Exhale 8s
    
    const runCycle = () => {
      if (!isBreathingRunning) return;

      if (phase === 0) {
        // Inhale 4s
        text.textContent = 'Вдих...';
        instruction.textContent = 'Повільно вдихайте носом (4 сек)';
        circle.style.transform = 'scale(1.5)';
        circle.style.backgroundColor = '#818cf8';
        setTimeout(() => {
          if (isBreathingRunning) { phase = 1; runCycle(); }
        }, 4000);
      } else if (phase === 1) {
        // Hold 7s
        text.textContent = 'Затримка';
        instruction.textContent = 'Затримайте дихання (7 сек)';
        circle.style.transform = 'scale(1.5)';
        circle.style.backgroundColor = '#c084fc';
        setTimeout(() => {
          if (isBreathingRunning) { phase = 2; runCycle(); }
        }, 7000);
      } else if (phase === 2) {
        // Exhale 8s
        text.textContent = 'Видих...';
        instruction.textContent = 'Повільно видихайте ротом (8 сек)';
        circle.style.transform = 'scale(1)';
        circle.style.backgroundColor = '#34d399';
        setTimeout(() => {
          if (isBreathingRunning) { phase = 0; runCycle(); }
        }, 8000);
      }
    };

    runCycle();
  } else {
    isBreathingRunning = false;
    btn.innerHTML = '<i class="fa-solid fa-play"></i> Розпочати вправу';
    text.textContent = 'Старт';
    instruction.textContent = 'Натисніть "Розпочати", щоб розслабитися';
    circle.style.transform = 'scale(1)';
  }
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
