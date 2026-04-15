'use strict';

// ── CONFIG ──────────────────────────────────────────────────────────────────
const GEMINI_BASE = 'https://generativelanguage.googleapis.com/v1beta/models';
const SYSTEM_PROMPT = `Jesteś asystentem AI o nazwie PhoneAI. Pomagasz użytkownikowi sterować telefonem przez komendy w języku polskim.
Masz dostęp do funkcji sterowania telefonem. Używaj ich zawsze gdy polecenie użytkownika tego wymaga.
Odpowiadaj WYŁĄCZNIE po polsku. Bądź zwięzły i konkretny — max 2 zdania po wykonaniu akcji.
Jeśli polecenie jest niemożliwe, powiedz dlaczego i zaproponuj alternatywę.
Możesz wykonać kilka akcji jednocześnie jeśli użytkownik tego chce.`;

// ── STATE ────────────────────────────────────────────────────────────────────
const S = {
  apiKey: localStorage.getItem('phoneai_key') || '',
  model:  localStorage.getItem('phoneai_model') || 'gemini-2.0-flash',
  history: [],
  busy: false,
  wakeLock: null,
  torchStream: null,
};

// ── FUNCTION DECLARATIONS ────────────────────────────────────────────────────
const PHONE_FNS = [
  {
    name: 'vibrate',
    description: 'Wibruje telefonem. Wywołaj gdy użytkownik chce wibrację lub przetestować haptykę.',
    parameters: {
      type: 'object',
      properties: {
        pattern:  { type: 'array', items: { type: 'number' }, description: 'Wzorzec [ms_on,ms_off,ms_on…]. Np [200,100,200].' },
        duration: { type: 'number', description: 'Czas wibracji ms gdy nie podano wzorca.' }
      }
    }
  },
  {
    name: 'speak',
    description: 'Odczytuje tekst na głos (Text-to-Speech). Użyj gdy użytkownik chce słyszeć wiadomość lub tekst.',
    parameters: {
      type: 'object',
      properties: {
        text:  { type: 'string', description: 'Tekst do przeczytania.' },
        lang:  { type: 'string', description: 'Język: pl-PL, en-US, de-DE… Domyślnie pl-PL.' },
        rate:  { type: 'number', description: 'Prędkość mowy 0.5–2.0. Domyślnie 1.' },
        pitch: { type: 'number', description: 'Ton głosu 0.5–2.0. Domyślnie 1.' }
      },
      required: ['text']
    }
  },
  {
    name: 'openApp',
    description: 'Otwiera aplikację lub stronę. Dostępne: youtube, maps, whatsapp, instagram, facebook, messenger, twitter, spotify, gmail, drive, docs, sheets, calendar, telegram, tiktok, netflix, reddit, wikipedia, google, translate. Dla telefonu użyj phone, dla SMS użyj sms.',
    parameters: {
      type: 'object',
      properties: {
        appName: { type: 'string', description: 'Nazwa aplikacji/serwisu.' },
        query:   { type: 'string', description: 'Zapytanie wyszukiwania (YouTube, Maps, Google, Wikipedia itp).' },
        phone:   { type: 'string', description: 'Numer telefonu (WhatsApp, telefon, SMS).' },
        text:    { type: 'string', description: 'Tekst wiadomości (WhatsApp, SMS).' },
        email:   { type: 'string', description: 'Adres e-mail (Gmail, email).' }
      },
      required: ['appName']
    }
  },
  {
    name: 'getLocation',
    description: 'Pobiera aktualną lokalizację GPS. Użyj gdy użytkownik pyta gdzie jest lub chce mapę.',
    parameters: { type: 'object', properties: {} }
  },
  {
    name: 'showNotification',
    description: 'Wyświetla powiadomienie push na telefonie.',
    parameters: {
      type: 'object',
      properties: {
        title: { type: 'string', description: 'Tytuł powiadomienia.' },
        body:  { type: 'string', description: 'Treść powiadomienia.' }
      },
      required: ['title', 'body']
    }
  },
  {
    name: 'takePicture',
    description: 'Robi zdjęcie aparatem telefonu i wyświetla je w czacie.',
    parameters: {
      type: 'object',
      properties: {
        facingMode: { type: 'string', description: '"environment" = tylny (domyślny), "user" = przedni/selfie.' }
      }
    }
  },
  {
    name: 'flashLight',
    description: 'Włącza lub wyłącza latarkę telefonu.',
    parameters: {
      type: 'object',
      properties: {
        enabled: { type: 'boolean', description: 'true = włącz, false = wyłącz.' }
      },
      required: ['enabled']
    }
  },
  {
    name: 'getDeviceInfo',
    description: 'Pobiera informacje o urządzeniu: OS, ekran, RAM, CPU, sieć, baterię.',
    parameters: { type: 'object', properties: {} }
  },
  {
    name: 'getBattery',
    description: 'Sprawdza poziom baterii i stan ładowania.',
    parameters: { type: 'object', properties: {} }
  },
  {
    name: 'setWakeLock',
    description: 'Zapobiega wygaszeniu ekranu lub zezwala na wygaszenie.',
    parameters: {
      type: 'object',
      properties: {
        enabled: { type: 'boolean', description: 'true = ekran nie zgaśnie, false = normalne działanie.' }
      },
      required: ['enabled']
    }
  },
  {
    name: 'copyToClipboard',
    description: 'Kopiuje tekst do schowka.',
    parameters: {
      type: 'object',
      properties: {
        text: { type: 'string', description: 'Tekst do skopiowania.' }
      },
      required: ['text']
    }
  },
  {
    name: 'readClipboard',
    description: 'Odczytuje zawartość schowka.',
    parameters: { type: 'object', properties: {} }
  },
  {
    name: 'playSound',
    description: 'Odgrywa dźwięk. Typy: beep, success, error, notification, alarm.',
    parameters: {
      type: 'object',
      properties: {
        type:      { type: 'string', description: 'Typ dźwięku: beep, success, error, notification, alarm.' },
        frequency: { type: 'number', description: 'Częstotliwość Hz dla niestandardowego dźwięku.' },
        duration:  { type: 'number', description: 'Czas trwania ms. Domyślnie 500.' }
      }
    }
  },
  {
    name: 'shareContent',
    description: 'Udostępnia treść przez systemowy dialog udostępniania.',
    parameters: {
      type: 'object',
      properties: {
        title: { type: 'string' },
        text:  { type: 'string' },
        url:   { type: 'string' }
      }
    }
  },
  {
    name: 'searchWeb',
    description: 'Wyszukuje coś w Google.',
    parameters: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Zapytanie do wyszukania.' }
      },
      required: ['query']
    }
  }
];

// ── PHONE ACTION HANDLERS ────────────────────────────────────────────────────
async function execFn(name, args = {}) {
  const H = {

    vibrate: async ({ pattern, duration = 600 }) => {
      if (!navigator.vibrate) return err('Wibracje nie są obsługiwane');
      navigator.vibrate(pattern ?? [duration]);
      return ok(`Wibracja ${pattern ? JSON.stringify(pattern) : duration + 'ms'}`);
    },

    speak: ({ text, lang = 'pl-PL', rate = 1, pitch = 1 }) =>
      new Promise(res => {
        if (!window.speechSynthesis) return res(err('TTS nie jest obsługiwany'));
        speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        Object.assign(u, { lang, rate, pitch });
        u.onend = () => res(ok('Tekst przeczytany'));
        u.onerror = e => res(err(e.error));
        speechSynthesis.speak(u);
      }),

    openApp: ({ appName, query, phone, text, email }) => {
      const n = appName.toLowerCase().replace(/\s+/g, '');
      const p = phone?.replace(/\D/g, '');
      const q = query ? encodeURIComponent(query) : '';
      const t = text  ? encodeURIComponent(text)  : '';
      const e = email ? encodeURIComponent(email) : '';
      const map = {
        youtube:      q ? `https://www.youtube.com/results?search_query=${q}` : 'https://www.youtube.com',
        youtubemusic: 'https://music.youtube.com',
        maps:         q ? `https://maps.google.com/?q=${q}` : 'https://maps.google.com',
        googlemaps:   q ? `https://maps.google.com/?q=${q}` : 'https://maps.google.com',
        whatsapp:     p ? `https://wa.me/${p}${t ? '?text=' + t : ''}` : 'https://web.whatsapp.com',
        instagram:    'https://www.instagram.com',
        facebook:     'https://www.facebook.com',
        messenger:    'https://www.messenger.com',
        twitter:      'https://www.twitter.com',
        x:            'https://www.x.com',
        spotify:      'https://open.spotify.com',
        gmail:        e ? `https://mail.google.com/mail/u/0/?to=${e}` : 'https://mail.google.com',
        email:        e ? `mailto:${email}${t ? '?body=' + t : ''}` : null,
        mail:         e ? `mailto:${email}` : null,
        drive:        'https://drive.google.com',
        docs:         'https://docs.google.com/document/',
        sheets:       'https://docs.google.com/spreadsheets/',
        calendar:     'https://calendar.google.com',
        telegram:     'https://web.telegram.org',
        tiktok:       'https://www.tiktok.com',
        netflix:      'https://www.netflix.com',
        reddit:       'https://www.reddit.com',
        wikipedia:    q ? `https://pl.wikipedia.org/wiki/${q}` : 'https://pl.wikipedia.org',
        google:       q ? `https://www.google.com/search?q=${q}` : 'https://www.google.com',
        translate:    q ? `https://translate.google.com/?text=${q}` : 'https://translate.google.com',
        phone:        p ? `tel:${p}` : null,
        telefon:      p ? `tel:${p}` : null,
        sms:          p ? `sms:${p}${t ? '?body=' + t : ''}` : null,
      };
      const url = map[n];
      if (!url) return err(`Nie znam "${appName}". Dostępne: YouTube, Maps, WhatsApp, Spotify, Gmail, Telegram…`);
      window.open(url, '_blank');
      return ok(`Otwarto ${appName}`);
    },

    getLocation: () =>
      new Promise(res => {
        if (!navigator.geolocation) return res(err('GPS nie jest obsługiwany'));
        navigator.geolocation.getCurrentPosition(
          p => res({ ok: true, lat: p.coords.latitude, lng: p.coords.longitude,
                     accuracy: Math.round(p.coords.accuracy) + 'm',
                     mapsUrl: `https://maps.google.com/?q=${p.coords.latitude},${p.coords.longitude}` }),
          e => res(err(e.message))
        );
      }),

    showNotification: async ({ title, body }) => {
      if (!('Notification' in window)) return err('Powiadomienia nie są obsługiwane');
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') return err('Brak uprawnień do powiadomień');
      if ('serviceWorker' in navigator) {
        const sw = await navigator.serviceWorker.ready;
        await sw.showNotification(title, { body, icon: './icon.svg' });
      } else {
        new Notification(title, { body });
      }
      return ok('Powiadomienie wysłane');
    },

    takePicture: async ({ facingMode = 'environment' }) => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode } });
        const video  = Object.assign(document.createElement('video'), { srcObject: stream, muted: true });
        await new Promise(r => { video.onloadedmetadata = r; });
        await video.play();
        const canvas = document.createElement('canvas');
        canvas.width  = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        stream.getTracks().forEach(t => t.stop());
        showPhoto(canvas.toDataURL('image/jpeg', 0.85));
        return ok('Zdjęcie zrobione — ' + (facingMode === 'user' ? 'aparat przedni' : 'aparat tylny'));
      } catch(e) { return err(e.message); }
    },

    flashLight: async ({ enabled }) => {
      try {
        if (!enabled) {
          S.torchStream?.getTracks().forEach(t => t.stop());
          S.torchStream = null;
          return ok('Latarka wyłączona');
        }
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
        const track  = stream.getVideoTracks()[0];
        if (!track.getCapabilities().torch) {
          stream.getTracks().forEach(t => t.stop());
          return err('Latarka nie jest obsługiwana na tym urządzeniu');
        }
        await track.applyConstraints({ advanced: [{ torch: true }] });
        S.torchStream = stream;
        return ok('Latarka włączona');
      } catch(e) { return err(e.message); }
    },

    getDeviceInfo: async () => {
      const d = {
        os:      (/Android/.test(navigator.userAgent) ? 'Android' : /iPhone|iPad/.test(navigator.userAgent) ? 'iOS' : 'Desktop'),
        browser: (/Chrome/.test(navigator.userAgent) ? 'Chrome' : /Firefox/.test(navigator.userAgent) ? 'Firefox' : /Safari/.test(navigator.userAgent) ? 'Safari' : 'Other'),
        language: navigator.language,
        online:   navigator.onLine,
        screen:  `${screen.width}×${screen.height} px`,
        dpr:      window.devicePixelRatio + 'x',
        ram:      navigator.deviceMemory ? navigator.deviceMemory + ' GB' : '—',
        cpu:      (navigator.hardwareConcurrency || '—') + ' rdzeni',
      };
      if (navigator.connection) {
        d.network = navigator.connection.effectiveType;
        d.downlink = navigator.connection.downlink + ' Mbps';
      }
      if ('getBattery' in navigator) {
        const b = await navigator.getBattery();
        d.battery  = Math.round(b.level * 100) + '%';
        d.charging = b.charging ? 'ładuje się' : 'na baterii';
      }
      return { ok: true, ...d };
    },

    getBattery: async () => {
      if (!('getBattery' in navigator)) return err('Battery API nie jest obsługiwane');
      const b = await navigator.getBattery();
      return {
        ok: true,
        level:          Math.round(b.level * 100) + '%',
        charging:       b.charging,
        chargingTime:   b.chargingTime === Infinity   ? '∞'  : Math.round(b.chargingTime / 60)   + ' min',
        dischargingTime: b.dischargingTime === Infinity ? '∞' : Math.round(b.dischargingTime / 60) + ' min'
      };
    },

    setWakeLock: async ({ enabled }) => {
      if (!('wakeLock' in navigator)) return err('Wake Lock nie jest obsługiwany');
      if (enabled) {
        try { S.wakeLock = await navigator.wakeLock.request('screen'); return ok('Ekran nie zgaśnie'); }
        catch(e) { return err(e.message); }
      }
      if (S.wakeLock) { await S.wakeLock.release(); S.wakeLock = null; }
      return ok('Normalne wygaszanie ekranu przywrócone');
    },

    copyToClipboard: async ({ text }) => {
      try { await navigator.clipboard.writeText(text); return ok('Skopiowano do schowka'); }
      catch(e) { return err(e.message); }
    },

    readClipboard: async () => {
      try { const t = await navigator.clipboard.readText(); return { ok: true, text: t }; }
      catch(e) { return err(e.message); }
    },

    playSound: ({ type = 'beep', frequency = 440, duration = 500 }) => {
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator(), gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        const P = { beep:['sine',880], success:['sine',523], error:['sawtooth',220], notification:['sine',660], alarm:['square',440] };
        const [wt, fr] = P[type] || ['sine', frequency];
        osc.type = wt; osc.frequency.value = fr;
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration / 1000);
        osc.start(); osc.stop(ctx.currentTime + duration / 1000);
        return ok(`Dźwięk "${type}" odtworzony`);
      } catch(e) { return err(e.message); }
    },

    shareContent: async ({ title, text, url }) => {
      if (!navigator.share) return err('Web Share nie jest obsługiwany');
      try { await navigator.share({ title, text, url }); return ok('Udostępniono'); }
      catch(e) { return err(e.message); }
    },

    searchWeb: ({ query }) => {
      window.open(`https://www.google.com/search?q=${encodeURIComponent(query)}`, '_blank');
      return ok(`Wyszukano: ${query}`);
    }
  };

  try {
    const handler = H[name];
    if (!handler) return err(`Nieznana funkcja: ${name}`);
    return await handler(args);
  } catch(e) { return err(e.message); }
}

const ok  = msg  => ({ ok: true,  message: msg });
const err = msg  => ({ ok: false, error: msg });

// ── GEMINI API ───────────────────────────────────────────────────────────────
async function callGemini(contents) {
  const url  = `${GEMINI_BASE}/${S.model}:generateContent?key=${S.apiKey}`;
  const body = {
    system_instruction: { parts: [{ text: SYSTEM_PROMPT }] },
    contents,
    tools: [{ functionDeclarations: PHONE_FNS }],
    generationConfig: { temperature: 0.7, maxOutputTokens: 1024 }
  };
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error?.message || `HTTP ${res.status}`);
  return data;
}

async function processMessage(userText) {
  if (S.busy) return;
  S.busy = true;

  const input = document.getElementById('messageInput');
  const send  = document.getElementById('sendBtn');
  input.value = ''; resizeInput();
  send.disabled = true;

  addMsg('user', userText);
  S.history.push({ role: 'user', parts: [{ text: userText }] });

  showTyping(true);
  setStatus('Myślę…');

  try {
    let resp      = await callGemini(S.history);
    let candidate = resp.candidates?.[0];
    if (!candidate) throw new Error('Brak odpowiedzi od AI');

    let parts = candidate.content.parts;

    // Function-calling loop
    while (parts.some(p => p.functionCall)) {
      S.history.push({ role: 'model', parts });
      const results = [];
      for (const p of parts) {
        if (!p.functionCall) continue;
        const { name, args } = p.functionCall;
        setStatus(`Wykonuję: ${name}…`);
        const result = await execFn(name, args || {});
        results.push({ functionResponse: { name, response: result } });
      }
      S.history.push({ role: 'user', parts: results });
      resp      = await callGemini(S.history);
      candidate = resp.candidates?.[0];
      if (!candidate) throw new Error('Brak odpowiedzi po wykonaniu akcji');
      parts     = candidate.content.parts;
    }

    S.history.push({ role: 'model', parts });
    const text = parts.find(p => p.text)?.text || 'Gotowe.';
    showTyping(false);
    setStatus('Gotowy');
    addMsg('ai', text);

  } catch(e) {
    showTyping(false);
    setStatus('Błąd');
    addMsg('ai', `❌ ${e.message}\n\nSprawdź czy klucz API jest poprawny w Ustawieniach.`);
  } finally {
    S.busy = false;
    send.disabled = false;
    input.focus();
  }
}

// ── UI HELPERS ───────────────────────────────────────────────────────────────
function addMsg(role, text) {
  const chat = document.getElementById('chatMessages');
  // Remove welcome placeholder
  const welcome = chat.querySelector('.welcome-msg');
  if (welcome) welcome.remove();

  const div = document.createElement('div');
  div.className = `msg msg-${role}`;
  if (role === 'ai') {
    div.innerHTML = `
      <div class="msg-avatar-wrap"><div class="ai-dot-sm"></div></div>
      <div class="msg-bubble">${md(text)}</div>`;
  } else {
    div.innerHTML = `<div class="msg-bubble">${esc(text)}</div>`;
  }
  chat.appendChild(div);
  chat.scrollTo({ top: chat.scrollHeight, behavior: 'smooth' });
  return div;
}

function esc(t) {
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function md(t) {
  return esc(t)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

function showTyping(show) {
  document.getElementById('typingIndicator').classList.toggle('hidden', !show);
  const chat = document.getElementById('chatMessages');
  chat.scrollTo({ top: chat.scrollHeight, behavior: 'smooth' });
}

function setStatus(txt) {
  document.getElementById('aiStatus').textContent = txt;
}

function showPhoto(dataUrl) {
  const preview = document.getElementById('photoPreview');
  document.getElementById('photoImg').src = dataUrl;
  preview.classList.remove('hidden');
}

function resizeInput() {
  const el = document.getElementById('messageInput');
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// ── SETTINGS ─────────────────────────────────────────────────────────────────
function openSettings() {
  document.getElementById('apiKeyEdit').value = S.apiKey;
  document.getElementById('modelSelect').value = S.model;
  document.getElementById('settingsPanel').classList.remove('hidden');
}

function closeSettings() {
  document.getElementById('settingsPanel').classList.add('hidden');
}

function saveSettings() {
  const key   = document.getElementById('apiKeyEdit').value.trim();
  const model = document.getElementById('modelSelect').value;
  if (!key) { alert('Podaj klucz API!'); return; }
  S.apiKey = key; S.model = model;
  localStorage.setItem('phoneai_key',   key);
  localStorage.setItem('phoneai_model', model);
  closeSettings();
  setStatus('Gotowy');
}

// ── VOICE INPUT ───────────────────────────────────────────────────────────────
function toggleVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { addMsg('ai', '❌ Rozpoznawanie mowy nie jest obsługiwane w tej przeglądarce. Użyj Chrome na Androidzie.'); return; }
  if (S.listening) { S.rec?.stop(); return; }
  const rec = new SR();
  rec.lang = 'pl-PL'; rec.continuous = false; rec.interimResults = false;
  rec.onstart  = () => { S.listening = true;  document.getElementById('voiceBtn').classList.add('listening');    setStatus('Słucham…'); };
  rec.onend    = () => { S.listening = false; document.getElementById('voiceBtn').classList.remove('listening'); setStatus('Gotowy'); };
  rec.onerror  = () => { S.listening = false; document.getElementById('voiceBtn').classList.remove('listening'); setStatus('Gotowy'); };
  rec.onresult = e => {
    const txt = e.results[0][0].transcript.trim();
    if (txt) { document.getElementById('messageInput').value = txt; resizeInput(); sendMessage(); }
  };
  S.rec = rec;
  rec.start();
}

// ── SEND MESSAGE ──────────────────────────────────────────────────────────────
function sendMessage() {
  const input = document.getElementById('messageInput');
  const text  = input.value.trim();
  if (!text || S.busy) return;
  processMessage(text);
}

// ── INIT ──────────────────────────────────────────────────────────────────────
function init() {
  // PWA Service Worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js').catch(() => {});
  }

  // Show correct screen
  if (S.apiKey) {
    document.getElementById('setup').classList.remove('on');
    document.getElementById('main').classList.add('on');
    addWelcome();
  } else {
    document.getElementById('setup').classList.add('on');
    document.getElementById('main').classList.remove('on');
  }

  // Setup screen — save key
  document.getElementById('saveKeyBtn').addEventListener('click', () => {
    const key = document.getElementById('apiKeyInput').value.trim();
    if (!key) { alert('Wklej klucz API Gemini!'); return; }
    S.apiKey = key;
    localStorage.setItem('phoneai_key', key);
    document.getElementById('setup').classList.remove('on');
    document.getElementById('main').classList.add('on');
    addWelcome();
  });
  document.getElementById('apiKeyInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('saveKeyBtn').click();
  });

  // Main screen controls
  document.getElementById('settingsBtn').addEventListener('click', openSettings);
  document.getElementById('closeSettings').addEventListener('click', closeSettings);
  document.getElementById('saveSettings').addEventListener('click', saveSettings);
  document.getElementById('clearChat').addEventListener('click', () => {
    S.history = [];
    const chat = document.getElementById('chatMessages');
    chat.innerHTML = '';
    addWelcome();
    closeSettings();
  });
  document.getElementById('settingsPanel').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeSettings();
  });

  document.getElementById('closePhoto').addEventListener('click', () => {
    document.getElementById('photoPreview').classList.add('hidden');
  });

  // Send
  document.getElementById('sendBtn').addEventListener('click', sendMessage);
  document.getElementById('messageInput').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  document.getElementById('messageInput').addEventListener('input', resizeInput);

  // Voice
  document.getElementById('voiceBtn').addEventListener('click', toggleVoice);

  // Quick actions
  document.querySelectorAll('.qa-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const cmd = chip.dataset.cmd;
      if (cmd && !S.busy) processMessage(cmd);
    });
  });
}

function addWelcome() {
  const chat = document.getElementById('chatMessages');
  chat.innerHTML = `
    <div class="welcome-msg">
      <div class="w-icon">🤖</div>
      <h3>Cześć! Jestem PhoneAI</h3>
      <p>Steruj swoim telefonem przez AI. Napisz co mam zrobić lub użyj skrótów powyżej.</p>
    </div>`;
}

document.addEventListener('DOMContentLoaded', init);
