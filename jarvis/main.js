'use strict';
/*
 * Jarvis — proces główny (Electron / Node).
 * Trzyma okno HUD, tray, globalne skróty, trwałość danych w userData,
 * oraz uruchamia orkiestratora wieloagentowego i wykonuje narzędzia OS.
 * Renderer odpowiada wyłącznie za interfejs i głos (TTS/STT).
 */
const { app, BrowserWindow, ipcMain, Tray, Menu, globalShortcut, Notification, desktopCapturer, shell, dialog, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');

const isDev = process.argv.includes('--dev');

// ---------- Trwałość danych (userData) ----------
let DATA_DIR;
function dataPath(...p) { return path.join(DATA_DIR, ...p); }
function ensureDirs() {
  DATA_DIR = app.getPath('userData');
  for (const d of ['', 'knowledge', 'quarantine', 'skills']) {
    const full = dataPath(d);
    if (!fs.existsSync(full)) fs.mkdirSync(full, { recursive: true });
  }
}
function readJSON(file, fallback) {
  try { return JSON.parse(fs.readFileSync(dataPath(file), 'utf8')); }
  catch { return fallback; }
}
function writeJSON(file, obj) {
  try { fs.writeFileSync(dataPath(file), JSON.stringify(obj, null, 2)); return true; }
  catch (e) { console.error('writeJSON', file, e); return false; }
}

const DEFAULT_SETTINGS = {
  userName: 'Sir',
  provider: 'anthropic',           // 'anthropic' | 'ollama'
  apiKey: '',
  ollamaUrl: 'http://localhost:11434',
  ollamaModel: 'qwen2.5:7b',
  virusTotalKey: '',
  vaultPath: '',                   // folder Obsidian vault dla bazy wiedzy (puste = lokalnie)
  localVoiceUrl: '',               // opcjonalny lokalny serwer STT/TTS (faster-whisper/Kokoro)
  models: {
    orchestrator: 'claude-opus-4-8',
    Operator: 'claude-opus-4-8',
    Researcher: 'claude-sonnet-5',
    Guard: 'claude-sonnet-5',
    Archivist: 'claude-sonnet-5'
  },
  voiceEnabled: true,
  voiceName: '',
  wakeWord: true,
  continuousListen: false,
  autoStart: false,
  watchDownloads: false,
  theme: 'green',
  maxParallelAgents: 4
};

const store = {
  settings() { return Object.assign({}, DEFAULT_SETTINGS, readJSON('settings.json', {}), { models: Object.assign({}, DEFAULT_SETTINGS.models, (readJSON('settings.json', {}).models) || {}) }); },
  saveSettings(s) { return writeJSON('settings.json', s); },
  memory() { return readJSON('memory.json', []); },
  saveMemory(m) { return writeJSON('memory.json', m); },
  notes() { return readJSON('notes.json', []); },
  saveNotes(n) { return writeJSON('notes.json', n); },
  macros() { return readJSON('macros.json', []); },
  saveMacros(m) { return writeJSON('macros.json', m); },
  log() { return readJSON('actionlog.json', []); },
  appendLog(entry) {
    const l = readJSON('actionlog.json', []);
    l.unshift(Object.assign({ ts: Date.now() }, entry));
    writeJSON('actionlog.json', l.slice(0, 500));
  },
  dataPath
};

// ---------- Okno ----------
let win = null;
let tray = null;

function createWindow() {
  win = new BrowserWindow({
    width: 1180,
    height: 760,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    backgroundColor: '#04060a',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      // getUserMedia (mikrofon) + WASM (Vosk) w rendererze
      backgroundThrottling: false
    }
  });
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  win.once('ready-to-show', () => win.show());
  win.on('closed', () => { win = null; });
  if (isDev) win.webContents.openDevTools({ mode: 'detach' });
}

function emit(channel, payload) {
  if (win && !win.isDestroyed()) win.webContents.send(channel, payload);
}

// ---------- Tray ----------
function buildTray() {
  try {
    const iconPath = path.join(__dirname, 'assets', 'tray.png');
    const icon = fs.existsSync(iconPath) ? nativeImage.createFromPath(iconPath) : nativeImage.createEmpty();
    tray = new Tray(icon);
    const menu = Menu.buildFromTemplate([
      { label: 'Pokaż Jarvisa', click: () => { if (win) { win.show(); win.focus(); } else createWindow(); } },
      { label: 'Zatrzymaj automatyzację (STOP)', click: () => emit('jarvis:stop', {}) },
      { type: 'separator' },
      { label: 'Zakończ', click: () => { app.isQuitting = true; app.quit(); } }
    ]);
    tray.setToolTip('Jarvis');
    tray.setContextMenu(menu);
    tray.on('double-click', () => { if (win) { win.show(); win.focus(); } else createWindow(); });
  } catch (e) { console.error('tray', e); }
}

// ---------- Powiadomienia ----------
function notify(title, body) {
  try { if (Notification.isSupported()) new Notification({ title: title || 'Jarvis', body: body || '' }).show(); }
  catch (e) { console.error('notify', e); }
}

// ---------- Potwierdzenia akcji nieodwracalnych ----------
const pendingConfirms = new Map();
function requestConfirm(details) {
  // details: { title, message, danger, command }
  return new Promise((resolve) => {
    const id = 'cf_' + Date.now() + '_' + Math.random().toString(36).slice(2);
    pendingConfirms.set(id, resolve);
    emit('jarvis:confirm', Object.assign({ id }, details));
    // fallback: natywny dialog, gdyby UI nie odpowiedziało (30 s)
    setTimeout(() => {
      if (pendingConfirms.has(id)) {
        pendingConfirms.delete(id);
        resolve(false);
      }
    }, 60000);
  });
}
ipcMain.on('jarvis:confirm-response', (_e, { id, approved }) => {
  const resolve = pendingConfirms.get(id);
  if (resolve) { pendingConfirms.delete(id); resolve(!!approved); }
});

// ---------- Zrzut ekranu (dla wizji) ----------
async function captureScreen() {
  const sources = await desktopCapturer.getSources({
    types: ['screen'],
    thumbnailSize: { width: 1280, height: 800 }
  });
  if (!sources.length) throw new Error('Brak dostępnego ekranu do przechwycenia.');
  const png = sources[0].thumbnail.toPNG();
  return png.toString('base64');
}

// ---------- Kontekst dla narzędzi/agentów ----------
const toolCtx = {
  store,
  emit,
  notify,
  confirm: requestConfirm,
  captureScreen,
  shell,
  get settings() { return store.settings(); }
};

// ---------- Wpięcie narzędzi i agentów ----------
const system = require('./tools/system');
const automation = require('./tools/automation');
const security = require('./tools/security');
const knowledge = require('./tools/knowledge');
const websearch = require('./tools/websearch');
const skills = require('./tools/skills');
const { Orchestrator } = require('./agents/orchestrator');

// zbiór wszystkich handlerów narzędzi
const allHandlers = Object.assign({},
  system.handlers, automation.handlers, security.handlers, knowledge.handlers, websearch.handlers, skills.handlers
);
const toolSchemas = {
  system: system.schemas,
  automation: automation.schemas,
  security: security.schemas,
  knowledge: knowledge.schemas,
  web: websearch.schemas,
  skills: skills.schemas
};

let orchestrator = null;
function getOrchestrator() {
  if (!orchestrator) {
    orchestrator = new Orchestrator({ ctx: toolCtx, handlers: allHandlers, toolSchemas });
  }
  return orchestrator;
}

// ---------- IPC: rozmowa ----------
ipcMain.handle('jarvis:send', async (_e, { text, history }) => {
  const s = store.settings();
  if (s.provider !== 'ollama' && (!s.apiKey || s.apiKey.trim().length < 10)) {
    return { error: 'no-key', message: 'Dodaj klucz API Anthropic w Ustawieniach — albo przełącz się na Ollamę (za darmo).' };
  }
  try {
    const result = await getOrchestrator().run(text, history || []);
    return { ok: true, reply: result.reply, actions: result.actions };
  } catch (err) {
    console.error('jarvis:send', err);
    return { error: 'runtime', message: err && err.message ? err.message : String(err) };
  }
});

ipcMain.on('jarvis:stop', () => { if (orchestrator) orchestrator.stop(); emit('jarvis:stopped', {}); });

// ---------- IPC: ustawienia i panele ----------
ipcMain.handle('settings:get', () => store.settings());
ipcMain.handle('settings:set', (_e, s) => {
  store.saveSettings(s);
  applyRuntimeSettings(s);
  return store.settings();
});
ipcMain.handle('memory:get', () => store.memory());
ipcMain.handle('memory:delete', (_e, id) => { store.saveMemory(store.memory().filter(m => m.id !== id)); return store.memory(); });
ipcMain.handle('notes:get', () => store.notes());
ipcMain.handle('log:get', () => store.log());
ipcMain.handle('knowledge:list', () => knowledge.listTopics(store));
ipcMain.handle('knowledge:get', (_e, name) => knowledge.readTopicFile(store, name));
ipcMain.handle('knowledge:delete', (_e, name) => knowledge.deleteTopicFile(store, name));
ipcMain.handle('security:recent', () => security.recentScans(store));
ipcMain.handle('security:quarantine-list', () => security.quarantineList(store));
ipcMain.handle('skills:list', () => skills.listSkills(toolCtx));

// ---------- IPC: okno ----------
ipcMain.on('win:minimize', () => win && win.minimize());
ipcMain.on('win:close', () => win && win.hide());
ipcMain.on('win:toggle-top', (_e, on) => win && win.setAlwaysOnTop(!!on));

// ---------- Ustawienia runtime (autostart, watcher) ----------
function applyRuntimeSettings(s) {
  try {
    app.setLoginItemSettings({ openAtLogin: !!s.autoStart });
  } catch (e) { console.error('autostart', e); }
  security.setWatch(!!s.watchDownloads, toolCtx);
}

// ---------- Skróty globalne ----------
function registerShortcuts() {
  try {
    globalShortcut.register('CommandOrControl+Shift+J', () => {
      if (win) { if (win.isVisible()) win.hide(); else { win.show(); win.focus(); } }
      else createWindow();
    });
    globalShortcut.register('CommandOrControl+Shift+X', () => {
      if (orchestrator) orchestrator.stop();
      emit('jarvis:stopped', {});
      notify('Jarvis', 'Automatyzacja zatrzymana.');
    });
  } catch (e) { console.error('shortcuts', e); }
}

// ---------- Cykl życia ----------
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => { if (win) { win.show(); win.focus(); } });

  app.whenReady().then(() => {
    ensureDirs();
    createWindow();
    buildTray();
    registerShortcuts();
    applyRuntimeSettings(store.settings());
    app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
  });

  app.on('window-all-closed', (e) => {
    // zostaje w tray — nie zamykamy
    if (!app.isQuitting) { /* keep running */ }
    else if (process.platform !== 'darwin') app.quit();
  });

  app.on('will-quit', () => globalShortcut.unregisterAll());
}
