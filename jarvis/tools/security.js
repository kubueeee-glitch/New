'use strict';
/*
 * Warstwa bezpieczeństwa (uczciwie: skaner, NIE pełny antywirus).
 * - scan_file: SHA-256 + zapytanie do VirusTotal (klucz użytkownika)
 * - watcher folderu Pobrane (chokidar) z auto-skanem
 * - list_processes: podgląd procesów z prostą heurystyką
 * - kwarantanna: przeniesienie podejrzanego pliku (za potwierdzeniem)
 * Nie zastępuje Windows Defendera i go nie wyłącza — współpracuje z nim.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { exec } = require('child_process');

let watcher = null;

function sha256(file) {
  return new Promise((resolve, reject) => {
    const h = crypto.createHash('sha256');
    const s = fs.createReadStream(file);
    s.on('error', reject);
    s.on('data', d => h.update(d));
    s.on('end', () => resolve(h.digest('hex')));
  });
}

function scansFile(store) { return store.dataPath('scans.json'); }
function readScans(store) { try { return JSON.parse(fs.readFileSync(scansFile(store), 'utf8')); } catch { return []; } }
function pushScan(store, entry) {
  const l = readScans(store); l.unshift(Object.assign({ ts: Date.now() }, entry));
  try { fs.writeFileSync(scansFile(store), JSON.stringify(l.slice(0, 200), null, 2)); } catch {}
}

async function vtLookup(hash, apiKey) {
  const res = await fetch('https://www.virustotal.com/api/v3/files/' + hash, {
    headers: { 'x-apikey': apiKey }
  });
  if (res.status === 404) return { found: false };
  if (res.status === 401) throw new Error('Nieprawidłowy klucz VirusTotal.');
  if (res.status === 429) throw new Error('Limit zapytań VirusTotal (darmowy plan: 4/min).');
  if (!res.ok) throw new Error('VirusTotal HTTP ' + res.status);
  const data = await res.json();
  const stats = data.data?.attributes?.last_analysis_stats || {};
  return { found: true, stats, name: data.data?.attributes?.meaningful_name };
}

async function scanFile(input, ctx) {
  const p = expand(input.path || '');
  if (!p || !fs.existsSync(p)) return { ok: false, error: 'Plik nie istnieje: ' + p };
  const s = ctx.settings;
  if (!s.virusTotalKey) return { ok: false, error: 'Dodaj klucz VirusTotal w Ustawieniach (darmowy na virustotal.com).' };
  try {
    const hash = await sha256(p);
    const r = await vtLookup(hash, s.virusTotalKey.trim());
    if (!r.found) {
      const entry = { path: p, hash, verdict: 'unknown' };
      pushScan(ctx.store, entry); ctx.emit('jarvis:event', { type: 'scan', entry });
      return { ok: true, verdict: 'unknown', message: 'Plik nieznany w bazie VirusTotal (brak wcześniejszej analizy). To nie jest gwarancja bezpieczeństwa.' };
    }
    const mal = r.stats.malicious || 0, susp = r.stats.suspicious || 0;
    const verdict = mal > 0 ? 'malicious' : susp > 0 ? 'suspicious' : 'clean';
    const entry = { path: p, hash, verdict, malicious: mal, suspicious: susp };
    pushScan(ctx.store, entry); ctx.emit('jarvis:event', { type: 'scan', entry });
    const msg = verdict === 'clean'
      ? `Czysty ✔ (0 wykryć, ${sumStats(r.stats)} silników).`
      : `⚠️ ${mal} silników oznaczyło plik jako złośliwy, ${susp} jako podejrzany. Rozważ kwarantannę.`;
    if (verdict !== 'clean') ctx.notify('Jarvis — bezpieczeństwo', path.basename(p) + ': ' + msg);
    return { ok: true, verdict, malicious: mal, suspicious: susp, message: msg };
  } catch (e) { return { ok: false, error: e.message }; }
}
function sumStats(s) { return (s.malicious || 0) + (s.suspicious || 0) + (s.harmless || 0) + (s.undetected || 0); }

async function listProcesses(_input) {
  return new Promise((resolve) => {
    const cmd = process.platform === 'win32'
      ? 'tasklist /fo csv /nh'
      : 'ps -eo comm,pmem,pcpu --sort=-pmem';
    exec(cmd, { timeout: 15000, windowsHide: true, maxBuffer: 2 * 1024 * 1024 }, (err, stdout) => {
      if (err) return resolve({ ok: false, error: err.message });
      let procs = [];
      if (process.platform === 'win32') {
        procs = (stdout || '').split(/\r?\n/).filter(Boolean).slice(0, 60).map(line => {
          const cols = line.split('","').map(c => c.replace(/^"|"$/g, ''));
          return { name: cols[0], pid: cols[1], mem: cols[4] };
        });
      } else {
        const lines = (stdout || '').split(/\r?\n/).filter(Boolean).slice(1, 60);
        procs = lines.map(l => { const p = l.trim().split(/\s+/); return { name: p[0], mem: p[1] + '%', cpu: p[2] + '%' }; });
      }
      resolve({ ok: true, count: procs.length, processes: procs });
    });
  });
}

async function quarantine(input, ctx) {
  const p = expand(input.path || '');
  if (!p || !fs.existsSync(p)) return { ok: false, error: 'Plik nie istnieje: ' + p };
  const approved = await ctx.confirm({ title: 'Kwarantanna', message: `Przenieść do kwarantanny?\n${p}`, danger: false });
  if (!approved) return { ok: false, error: 'Anulowano.' };
  try {
    const dest = ctx.store.dataPath('quarantine', Date.now() + '_' + path.basename(p));
    fs.renameSync(p, dest);
    ctx.store.appendLog({ type: 'quarantine', from: p, to: dest });
    ctx.emit('jarvis:event', { type: 'quarantine', from: p });
    return { ok: true, message: 'Plik przeniesiony do kwarantanny.' };
  } catch (e) { return { ok: false, error: e.message }; }
}

// ---------- Watcher folderu Pobrane ----------
function downloadsDir() {
  const home = os.homedir();
  const candidates = [path.join(home, 'Downloads'), path.join(home, 'Pobrane')];
  for (const c of candidates) if (fs.existsSync(c)) return c;
  return candidates[0];
}
function setWatch(on, ctx) {
  try { if (watcher) { watcher.close(); watcher = null; } } catch {}
  if (!on) return;
  let chokidar; try { chokidar = require('chokidar'); } catch { ctx.emit('jarvis:event', { type: 'security', message: 'Watcher wymaga pakietu chokidar.' }); return; }
  const dir = downloadsDir();
  watcher = chokidar.watch(dir, { ignoreInitial: true, depth: 0, awaitWriteFinish: { stabilityThreshold: 2000, pollInterval: 300 } });
  watcher.on('add', async (fp) => {
    ctx.emit('jarvis:event', { type: 'security', message: 'Nowy plik w Pobranych: ' + path.basename(fp) + ' — skanuję...' });
    const r = await scanFile({ path: fp }, ctx);
    if (r.ok && r.verdict && r.verdict !== 'clean' && r.verdict !== 'unknown') {
      ctx.notify('Jarvis — UWAGA', path.basename(fp) + ': ' + r.message);
    }
  });
}

function recentScans(store) { return readScans(store).slice(0, 50); }
function quarantineList(store) {
  try { return fs.readdirSync(store.dataPath('quarantine')).map(n => ({ name: n })); } catch { return []; }
}

function expand(p) { return p && p.startsWith('~') ? path.join(os.homedir(), p.slice(1)) : p; }

const schemas = [
  { name: 'scan_file', description: 'Skanuje plik pod kątem złośliwości: liczy SHA-256 i sprawdza w VirusTotal. Zwraca werdykt (clean/suspicious/malicious/unknown).', input_schema: { type: 'object', properties: { path: { type: 'string' } }, required: ['path'] } },
  { name: 'list_processes', description: 'Zwraca listę uruchomionych procesów (podgląd bezpieczeństwa).', input_schema: { type: 'object', properties: {} } },
  { name: 'quarantine_file', description: 'Przenosi podejrzany plik do kwarantanny (za potwierdzeniem użytkownika).', input_schema: { type: 'object', properties: { path: { type: 'string' } }, required: ['path'] } }
];

const handlers = {
  scan_file: scanFile,
  list_processes: (input) => listProcesses(input),
  quarantine_file: quarantine
};

module.exports = { schemas, handlers, setWatch, recentScans, quarantineList };
