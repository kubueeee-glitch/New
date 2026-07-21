'use strict';
/*
 * Narzędzia systemowe: otwieranie aplikacji/stron, sterowanie systemem,
 * schowek, statystyki, polecenia powłoki i operacje na plikach.
 * Akcje nieodwracalne (shutdown/restart, run_command, move/delete) wymagają
 * potwierdzenia przez ctx.confirm() i trafiają do logu akcji.
 */
const { exec } = require('child_process');
const os = require('os');
const fs = require('fs');
const path = require('path');
const { clipboard } = require('electron');

const PLATFORM = process.platform; // 'win32' | 'darwin' | 'linux'

function sh(cmd, opts = {}) {
  return new Promise((resolve) => {
    exec(cmd, Object.assign({ timeout: 20000, windowsHide: true, maxBuffer: 1024 * 1024 }, opts), (err, stdout, stderr) => {
      resolve({ err, stdout: (stdout || '').toString(), stderr: (stderr || '').toString() });
    });
  });
}

function lazyNut() {
  try { return require('@nut-tree-fork/nut-js'); } catch { return null; }
}

// Mapa popularnych aplikacji per system (można rozszerzać ścieżką od użytkownika)
const APP_MAP = {
  win32: {
    notatnik: 'notepad', notepad: 'notepad', kalkulator: 'calc', calc: 'calc',
    paint: 'mspaint', 'wiersz poleceń': 'cmd', cmd: 'cmd', powershell: 'powershell',
    eksplorator: 'explorer', explorer: 'explorer', 'menedżer zadań': 'taskmgr',
    ustawienia: 'start ms-settings:', word: 'winword', excel: 'excel'
  },
  darwin: {
    notatki: 'open -a Notes', kalkulator: 'open -a Calculator', safari: 'open -a Safari',
    terminal: 'open -a Terminal', finder: 'open -a Finder'
  },
  linux: {
    kalkulator: 'gnome-calculator', terminal: 'x-terminal-emulator', pliki: 'xdg-open ~'
  }
};

async function openApp(input, ctx) {
  const name = (input.name || '').trim();
  if (!name) return { ok: false, error: 'Podaj nazwę aplikacji.' };
  const map = APP_MAP[PLATFORM] || {};
  const key = name.toLowerCase();
  let cmd = map[key];
  if (!cmd) {
    // spróbuj potraktować jako nazwę wykonywalną / ścieżkę
    if (PLATFORM === 'win32') cmd = `start "" "${name}"`;
    else if (PLATFORM === 'darwin') cmd = `open -a "${name}"`;
    else cmd = `${name}`;
  }
  const r = await sh(cmd);
  ctx.store.appendLog({ type: 'open_app', name, ok: !r.err });
  if (r.err && r.stderr) return { ok: false, error: `Nie udało się otworzyć „${name}”: ${r.stderr.trim()}` };
  return { ok: true, message: `Otwarto: ${name}` };
}

async function openUrl(input, ctx) {
  let url = (input.url || '').trim();
  if (!url) return { ok: false, error: 'Podaj adres URL.' };
  if (!/^https?:\/\//i.test(url) && !/^[a-z]+:/i.test(url)) url = 'https://' + url;
  try { await ctx.shell.openExternal(url); ctx.store.appendLog({ type: 'open_url', url }); return { ok: true, message: `Otwarto ${url}` }; }
  catch (e) { return { ok: false, error: e.message }; }
}

async function systemControl(input, ctx) {
  const action = (input.action || '').toLowerCase();
  const nut = lazyNut();
  const pressKey = async (keyName) => {
    if (!nut) return false;
    try { await nut.keyboard.pressKey(nut.Key[keyName]); await nut.keyboard.releaseKey(nut.Key[keyName]); return true; }
    catch { return false; }
  };
  switch (action) {
    case 'volume_up': { const ok = await pressKey('AudioVolUp'); return okOrHint(ok, 'Głośność w górę'); }
    case 'volume_down': { const ok = await pressKey('AudioVolDown'); return okOrHint(ok, 'Głośność w dół'); }
    case 'mute': { const ok = await pressKey('AudioMute'); return okOrHint(ok, 'Wyciszenie przełączone'); }
    case 'media_play_pause': { const ok = await pressKey('AudioPlay'); return okOrHint(ok, 'Odtwarzanie/pauza'); }
    case 'media_next': { const ok = await pressKey('AudioNext'); return okOrHint(ok, 'Następny utwór'); }
    case 'media_prev': { const ok = await pressKey('AudioPrev'); return okOrHint(ok, 'Poprzedni utwór'); }
    case 'lock': { await lockScreen(); ctx.store.appendLog({ type: 'system', action }); return { ok: true, message: 'Ekran zablokowany' }; }
    case 'sleep': { await sleepSystem(); ctx.store.appendLog({ type: 'system', action }); return { ok: true, message: 'Usypianie...' }; }
    case 'shutdown':
    case 'restart': {
      const label = action === 'shutdown' ? 'wyłączyć komputer' : 'zrestartować komputer';
      const approved = await ctx.confirm({ title: 'Potwierdź', message: `Czy na pewno ${label}?`, danger: true });
      if (!approved) return { ok: false, error: 'Anulowano przez użytkownika.' };
      await powerAction(action);
      ctx.store.appendLog({ type: 'system', action, confirmed: true });
      return { ok: true, message: action === 'shutdown' ? 'Wyłączanie...' : 'Restart...' };
    }
    default: return { ok: false, error: `Nieznana akcja: ${action}` };
  }
  function okOrHint(ok, msg) { return ok ? { ok: true, message: msg } : { ok: false, error: 'Sterowanie mediami wymaga biblioteki nut-js (npm install).' }; }
}

async function lockScreen() {
  if (PLATFORM === 'win32') return sh('rundll32.exe user32.dll,LockWorkStation');
  if (PLATFORM === 'darwin') return sh('pmset displaysleepnow');
  return sh('loginctl lock-session || xdg-screensaver lock');
}
async function sleepSystem() {
  if (PLATFORM === 'win32') return sh('rundll32.exe powrprof.dll,SetSuspendState 0,1,0');
  if (PLATFORM === 'darwin') return sh('pmset sleepnow');
  return sh('systemctl suspend');
}
async function powerAction(action) {
  if (PLATFORM === 'win32') return sh(action === 'shutdown' ? 'shutdown /s /t 0' : 'shutdown /r /t 0');
  if (PLATFORM === 'darwin') return sh(`osascript -e 'tell app "System Events" to ${action === 'shutdown' ? 'shut down' : 'restart'}'`);
  return sh(action === 'shutdown' ? 'systemctl poweroff' : 'systemctl reboot');
}

function systemStats() {
  const mem = { total: os.totalmem(), free: os.freemem() };
  const cpus = os.cpus() || [];
  const load = os.loadavg ? os.loadavg() : [0, 0, 0];
  return {
    ok: true,
    platform: PLATFORM,
    hostname: os.hostname(),
    cpuModel: cpus[0] ? cpus[0].model : 'n/a',
    cpuCount: cpus.length,
    load1: load[0],
    memTotalGB: +(mem.total / 1073741824).toFixed(1),
    memFreeGB: +(mem.free / 1073741824).toFixed(1),
    memUsedPct: Math.round((1 - mem.free / mem.total) * 100),
    uptimeH: +(os.uptime() / 3600).toFixed(1)
  };
}

function clipboardRead() {
  try { return { ok: true, text: clipboard.readText() }; } catch (e) { return { ok: false, error: e.message }; }
}
function clipboardWrite(input) {
  try { clipboard.writeText(input.text || ''); return { ok: true, message: 'Zapisano do schowka.' }; } catch (e) { return { ok: false, error: e.message }; }
}

async function runCommand(input, ctx) {
  const command = (input.command || '').trim();
  if (!command) return { ok: false, error: 'Podaj polecenie.' };
  const approved = await ctx.confirm({
    title: 'Wykonać polecenie?',
    message: 'Jarvis chce uruchomić polecenie systemowe:',
    command,
    danger: true
  });
  if (!approved) return { ok: false, error: 'Anulowano przez użytkownika.' };
  const shellOpt = PLATFORM === 'win32' ? { shell: 'powershell.exe' } : {};
  const r = await sh(command, shellOpt);
  ctx.store.appendLog({ type: 'run_command', command, ok: !r.err });
  const out = (r.stdout || '') + (r.stderr ? '\n[stderr]\n' + r.stderr : '');
  return { ok: !r.err, output: out.slice(0, 4000) || '(brak wyjścia)', error: r.err ? (r.stderr || r.err.message) : undefined };
}

async function manageFiles(input, ctx) {
  const action = (input.action || '').toLowerCase();
  try {
    if (action === 'list') {
      const dir = expand(input.path || os.homedir());
      const items = fs.readdirSync(dir).slice(0, 200).map(n => {
        const full = path.join(dir, n);
        let stat = {}; try { stat = fs.statSync(full); } catch {}
        return { name: n, dir: !!stat.isDirectory && stat.isDirectory(), size: stat.size || 0 };
      });
      return { ok: true, path: dir, items };
    }
    if (action === 'search') {
      const root = expand(input.path || os.homedir());
      const q = (input.query || '').toLowerCase();
      const found = [];
      walk(root, 4, (f) => { if (path.basename(f).toLowerCase().includes(q)) found.push(f); return found.length < 50; });
      return { ok: true, matches: found };
    }
    if (action === 'open') {
      const p = expand(input.path || '');
      const err = await ctx.shell.openPath(p);
      ctx.store.appendLog({ type: 'file_open', path: p });
      return err ? { ok: false, error: err } : { ok: true, message: `Otwarto ${p}` };
    }
    if (action === 'move') {
      const from = expand(input.path), to = expand(input.dest);
      const approved = await ctx.confirm({ title: 'Przenieść plik?', message: `${from}\n→ ${to}`, danger: false });
      if (!approved) return { ok: false, error: 'Anulowano.' };
      fs.renameSync(from, to);
      ctx.store.appendLog({ type: 'file_move', from, to });
      return { ok: true, message: 'Przeniesiono.' };
    }
    if (action === 'delete') {
      const p = expand(input.path);
      const approved = await ctx.confirm({ title: 'Usunąć plik?', message: `Trwałe usunięcie:\n${p}`, danger: true });
      if (!approved) return { ok: false, error: 'Anulowano.' };
      fs.rmSync(p, { recursive: true, force: true });
      ctx.store.appendLog({ type: 'file_delete', path: p, confirmed: true });
      return { ok: true, message: 'Usunięto.' };
    }
    return { ok: false, error: `Nieznana akcja plikowa: ${action}` };
  } catch (e) { return { ok: false, error: e.message }; }
}

function expand(p) {
  if (!p) return p;
  if (p.startsWith('~')) return path.join(os.homedir(), p.slice(1));
  return p;
}
function walk(dir, depth, cb) {
  if (depth < 0) return;
  let entries = [];
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (!cb(full)) return;
    if (e.isDirectory() && !e.name.startsWith('.') && e.name !== 'node_modules') walk(full, depth - 1, cb);
  }
}

// ---------- Schematy narzędzi (format Anthropic) ----------
const schemas = [
  { name: 'open_app', description: 'Otwiera aplikację na komputerze po nazwie (np. Notatnik, Kalkulator, Spotify) lub ścieżce.', input_schema: { type: 'object', properties: { name: { type: 'string', description: 'Nazwa aplikacji lub ścieżka do pliku wykonywalnego.' } }, required: ['name'] } },
  { name: 'open_url', description: 'Otwiera adres URL w domyślnej przeglądarce.', input_schema: { type: 'object', properties: { url: { type: 'string' } }, required: ['url'] } },
  { name: 'system_control', description: 'Sterowanie systemem: głośność, multimedia, blokada, uśpienie, wyłączenie/restart (dwa ostatnie wymagają potwierdzenia użytkownika).', input_schema: { type: 'object', properties: { action: { type: 'string', enum: ['volume_up', 'volume_down', 'mute', 'media_play_pause', 'media_next', 'media_prev', 'lock', 'sleep', 'shutdown', 'restart'] } }, required: ['action'] } },
  { name: 'system_stats', description: 'Zwraca statystyki komputera: CPU, RAM, uptime, system.', input_schema: { type: 'object', properties: {} } },
  { name: 'clipboard_read', description: 'Odczytuje tekst ze schowka systemowego.', input_schema: { type: 'object', properties: {} } },
  { name: 'clipboard_write', description: 'Zapisuje tekst do schowka systemowego.', input_schema: { type: 'object', properties: { text: { type: 'string' } }, required: ['text'] } },
  { name: 'run_command', description: 'Wykonuje polecenie powłoki (PowerShell/shell). ZAWSZE prosi użytkownika o potwierdzenie i pokazuje dokładne polecenie. Używaj do zadań niedostępnych innymi narzędziami.', input_schema: { type: 'object', properties: { command: { type: 'string' } }, required: ['command'] } },
  { name: 'manage_files', description: 'Operacje na plikach: list (lista katalogu), search (szukanie po nazwie), open (otwórz), move (przenieś), delete (usuń). Move i delete wymagają potwierdzenia.', input_schema: { type: 'object', properties: { action: { type: 'string', enum: ['list', 'search', 'open', 'move', 'delete'] }, path: { type: 'string' }, query: { type: 'string' }, dest: { type: 'string' } }, required: ['action'] } }
];

const handlers = {
  open_app: openApp,
  open_url: openUrl,
  system_control: systemControl,
  system_stats: () => systemStats(),
  clipboard_read: () => clipboardRead(),
  clipboard_write: (input) => clipboardWrite(input),
  run_command: runCommand,
  manage_files: manageFiles
};

module.exports = { schemas, handlers };
