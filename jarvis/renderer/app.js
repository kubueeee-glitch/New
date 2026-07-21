'use strict';
/* Jarvis — logika interfejsu (renderer). Cała komunikacja z systemem idzie
 * przez bezpieczny mostek window.jarvis (patrz preload.js). */
const J = window.jarvis;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? '' : s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

let settings = null;
let history = [];           // {role:'user'|'ai', content}
let busy = false;
const metrics = { msgs: 0, tokens: 0, agentRuns: 0, start: Date.now() };
const AGENTS = [
  { id: 'Jarvis', icon: '🧠' }, { id: 'Researcher', icon: '🔎' },
  { id: 'Operator', icon: '🖱️' }, { id: 'Guard', icon: '🛡️' }, { id: 'Archivist', icon: '🗂️' }
];
const MODELS = ['claude-opus-4-8', 'claude-sonnet-5', 'claude-haiku-4-5-20251001'];
const CHIPS = ['Która godzina?', 'Zrób research: najlepsze GPU do 2000 zł', 'Otwórz YouTube', 'Sprawdź uruchomione procesy', 'Ile mam wolnego RAM-u?'];

// ================= INIT =================
init();
async function init() {
  settings = await J.getSettings();
  applyTheme();
  renderSwarm();
  renderChips();
  wireWindow();
  wireInput();
  wirePanels();
  wireModal();
  subscribe();
  startClock();
  Voice.init();
  Sphere.init();
  renderDocuments();
  renderSkillsPanel();
  renderMetrics();
  updateCounter();
  $('wname').textContent = settings.userName || 'Sir';
  updateApiLed();
  setInterval(renderMetrics, 4000);
}

function applyTheme() { document.body.className = 'theme-' + (settings.theme || 'green'); }
function updateApiLed() {
  if (settings.provider === 'ollama') {
    $('led-api').classList.add('on');
    $('api-label').textContent = 'Ollama: ' + (settings.ollamaModel || 'lokalnie');
    return;
  }
  const ok = settings.apiKey && settings.apiKey.trim().length > 10;
  $('led-api').classList.toggle('on', ok);
  $('api-label').textContent = ok ? 'Claude: gotowe' : 'API: brak klucza';
}

// ================= SWARM =================
function renderSwarm() {
  $('swarm-list').innerHTML = AGENTS.map(a => `
    <div class="agent-card" id="ag-${a.id}">
      <div class="agent-top">
        <div class="agent-ic">${a.icon}</div>
        <div class="agent-name">${a.id}</div>
        <div class="agent-led" id="led-${a.id}"></div>
      </div>
      <div class="agent-task" id="task-${a.id}">bezczynny</div>
      <div class="agent-bar"><i id="bar-${a.id}"></i></div>
      <div class="agent-meta" id="meta-${a.id}"></div>
    </div>`).join('');
}
function updateAgent(p) {
  const card = $('ag-' + p.name); if (!card) return;
  const led = $('led-' + p.name);
  led.className = 'agent-led ' + (p.status || '');
  const working = ['working', 'thinking', 'acting'].includes(p.status);
  card.classList.toggle('active', working);
  if (p.task) $('task-' + p.name).textContent = p.task;
  else if (p.status === 'done') $('task-' + p.name).textContent = 'gotowe ✔';
  else if (p.status === 'idle') $('task-' + p.name).textContent = 'bezczynny';
  const meta = $('meta-' + p.name);
  meta.textContent = [p.tool ? '🔧 ' + p.tool : '', p.step ? 'krok ' + p.step : ''].filter(Boolean).join(' · ');
  if (p.step) $('bar-' + p.name).style.width = Math.min(100, p.step * 12) + '%';
  if (p.status === 'done' || p.status === 'idle') { $('bar-' + p.name).style.width = p.status === 'done' ? '100%' : '0'; }
  refreshActiveCount();
  reflectReactor();
}
function refreshActiveCount() {
  const n = AGENTS.filter(a => $('led-' + a.id).classList.contains('working') || $('led-' + a.id).classList.contains('acting') || $('led-' + a.id).classList.contains('thinking')).length;
  $('agents-active').textContent = n;
  $('swarm-count').textContent = n ? n + ' pracuje' : 'idle';
}

// ================= REACTOR =================
let automationActive = false;
function setReactor(state, sub) {
  $('reactor').dataset.state = state;
  const labels = { idle: 'GOTOWY', thinking: 'MYŚLĘ', acting: 'DZIAŁAM', listening: 'SŁUCHAM', speaking: 'MÓWIĘ' };
  $('reactor-state').textContent = labels[state] || state.toUpperCase();
  const tok = $('tok-state'); if (tok) tok.textContent = (labels[state] || state).toUpperCase();
  if (sub != null) $('reactor-sub').textContent = sub;
  Sphere.setState(state);
}
function reflectReactor() {
  if (Voice.speaking) return setReactor('speaking');
  if (Voice.listening) return setReactor('listening');
  if (automationActive) return setReactor('acting', 'Steruję komputerem…');
  if (busy) return setReactor('thinking', 'Przetwarzam…');
  setReactor('idle', 'Powiedz „Hej Jarvis” albo napisz polecenie.');
}

// ================= METRICS / DOCS / SKILLS =================
function fmt(n) { return n >= 1000 ? (n / 1000).toFixed(1).replace('.0', '') + 'K' : String(n); }
function renderMetrics() {
  const upMin = Math.floor((Date.now() - metrics.start) / 60000);
  const rows = [
    { l: 'Rozmowy', v: fmt(metrics.msgs), p: Math.min(100, metrics.msgs * 4) },
    { l: 'Tokeny ~', v: fmt(metrics.tokens), p: Math.min(100, metrics.tokens / 200) },
    { l: 'Zadania agentów', v: fmt(metrics.agentRuns), p: Math.min(100, metrics.agentRuns * 8) },
    { l: 'Uptime (min)', v: fmt(upMin), p: Math.min(100, upMin) }
  ];
  const el = $('metrics'); if (!el) return;
  el.innerHTML = rows.map(r => `<div class="metric"><div class="metric-top"><span class="metric-l">${r.l}</span><span class="metric-v">${r.v}</span></div><div class="metric-bar"><i style="width:${r.p}%"></i></div></div>`).join('');
}
function updateCounter() { const el = $('big-counter'); if (el) el.textContent = metrics.tokens.toLocaleString('pl-PL'); }
async function renderDocuments() {
  const el = $('documents'); if (!el) return;
  const topics = await J.listKnowledge();
  el.innerHTML = topics.length
    ? topics.map(t => `<div class="doc" data-doc="${esc(t.name)}"><div class="doc-n">◆ ${esc(t.name)}</div><div class="doc-s">${esc(t.summary || '')}</div></div>`).join('')
    : '<div class="empty-note">Brak dokumentów. Zleć research — raporty wylądują tu jako notatki-graf.</div>';
  el.querySelectorAll('[data-doc]').forEach(b => b.onclick = async () => { const r = await J.getKnowledge(b.dataset.doc); if (r.ok) { openPanel('knowledge'); showDoc(b.dataset.doc, r.content); } });
}
async function renderSkillsPanel() {
  const el = $('skills-list'); if (!el) return;
  const skills = await J.listSkills();
  el.innerHTML = skills.length
    ? skills.map(s => `<div class="skill"><div class="skill-n">▸ ${esc(s.name)}</div><div class="skill-s">${esc(s.description || '')}</div></div>`).join('')
    : '<div class="empty-note">Brak skilli. Dodaj folder ze SKILL.md w katalogu skills/.</div>';
}

// ================= SPHERE (voice viz) =================
const Sphere = {
  cv: null, ctx: null, pts: [], state: 'idle', raf: null, rot: 0, W: 0, H: 0, dpr: 1,
  init() {
    this.cv = $('sphere'); if (!this.cv) return;
    this.ctx = this.cv.getContext('2d');
    this.resize(); window.addEventListener('resize', () => this.resize());
    const N = 520;
    for (let i = 0; i < N; i++) {
      const y = 1 - (i / (N - 1)) * 2;
      const r = Math.sqrt(1 - y * y);
      const th = i * 2.399963;
      this.pts.push({ x: Math.cos(th) * r, y, z: Math.sin(th) * r });
    }
    this.loop();
  },
  resize() {
    if (!this.cv) return;
    this.dpr = window.devicePixelRatio || 1;
    this.W = this.cv.clientWidth; this.H = this.cv.clientHeight;
    this.cv.width = this.W * this.dpr; this.cv.height = this.H * this.dpr;
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
  },
  setState(s) { this.state = s; },
  loop() {
    const c = this.ctx; if (!c) return;
    const cx = this.W / 2, cy = this.H / 2;
    const base = Math.min(this.W, this.H) * 0.32;
    const energy = (this.state === 'listening' || this.state === 'speaking') ? (0.5 + Voice.energy * 0.9)
      : this.state === 'thinking' ? 0.55 : this.state === 'acting' ? 0.6 : 0.32;
    const spd = this.state === 'thinking' ? 0.028 : this.state === 'acting' ? 0.02 : this.state === 'idle' ? 0.006 : 0.014;
    this.rot += spd;
    const col = getComputedStyle(document.body).getPropertyValue('--ac').trim() || '#39ff9e';
    c.clearRect(0, 0, this.W, this.H);
    const rad = base * (0.85 + energy * 0.5);
    const cosR = Math.cos(this.rot), sinR = Math.sin(this.rot);
    const tilt = 0.42;
    for (const p of this.pts) {
      const x1 = p.x * cosR - p.z * sinR;
      const z1 = p.x * sinR + p.z * cosR;
      const y1 = p.y * Math.cos(tilt) - z1 * Math.sin(tilt);
      const z2 = p.y * Math.sin(tilt) + z1 * Math.cos(tilt);
      const persp = 1 / (2 - z2);
      const sx = cx + x1 * rad * persp * 1.4;
      const sy = cy + y1 * rad * persp * 1.4;
      const depth = (z2 + 1) / 2;
      const size = 0.6 + depth * 1.9;
      c.globalAlpha = 0.15 + depth * 0.85;
      c.fillStyle = col;
      c.beginPath(); c.arc(sx, sy, size, 0, 6.2832); c.fill();
    }
    c.globalAlpha = 1;
    this.raf = requestAnimationFrame(() => this.loop());
  }
};

// ================= CHAT =================
function renderChips() { $('chips').innerHTML = CHIPS.map(c => `<button class="chip">${esc(c)}</button>`).join(''); document.querySelectorAll('#chips .chip').forEach(b => b.onclick = () => { $('input').value = b.textContent; send(); }); }
function addMsg(role, content, actions) {
  const w = $('welcome'); if (w) w.remove();
  const chat = $('chat');
  const av = role === 'user' ? '🧑' : '🧠';
  let toolHtml = '';
  if (actions && actions.length) toolHtml = '<div>' + actions.map(a => `<span class="tool-chip"><b>${esc(a.agent)}</b> ${esc(a.task).slice(0, 60)}</span>`).join('') + '</div>';
  const el = document.createElement('div');
  el.className = 'msg ' + (role === 'user' ? 'user' : 'ai');
  el.innerHTML = `<div class="msg-av">${av}</div><div class="msg-body"><div class="msg-bubble">${esc(content)}</div>${toolHtml}<div class="msg-time">${new Date().toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' })}</div></div>`;
  chat.appendChild(el); chat.scrollTop = chat.scrollHeight;
}
let typingEl = null;
function showTyping() { const chat = $('chat'); typingEl = document.createElement('div'); typingEl.className = 'msg ai'; typingEl.innerHTML = `<div class="msg-av">🧠</div><div class="msg-body"><div class="msg-bubble" style="color:var(--t3)">…</div></div>`; chat.appendChild(typingEl); chat.scrollTop = chat.scrollHeight; }
function hideTyping() { if (typingEl) { typingEl.remove(); typingEl = null; } }

async function send() {
  const ta = $('input'); const text = ta.value.trim();
  if (!text || busy) return;
  if (settings.provider !== 'ollama' && (!settings.apiKey || settings.apiKey.trim().length < 10)) { toast('🔑 Dodaj klucz API lub przełącz na Ollamę (za darmo) w Ustawieniach.'); openPanel('settings'); return; }
  ta.value = ''; ta.style.height = 'auto';
  addMsg('user', text); history.push({ role: 'user', content: text });
  metrics.msgs++; metrics.tokens += Math.ceil(text.length / 4);
  busy = true; reflectReactor(); showTyping();
  updateAgent({ name: 'Jarvis', status: 'thinking', task: 'analizuję polecenie' });
  try {
    const res = await J.send(text, history);
    hideTyping();
    if (res.error) { addMsg('ai', '⚠️ ' + (res.message || 'Błąd.')); }
    else {
      addMsg('ai', res.reply, res.actions);
      history.push({ role: 'ai', content: res.reply });
      metrics.tokens += Math.ceil((res.reply || '').length / 4);
      metrics.agentRuns += (res.actions || []).length;
      if (settings.voiceEnabled) Voice.speak(res.reply);
      renderDocuments();
    }
  } catch (e) { hideTyping(); addMsg('ai', '⚠️ ' + (e.message || e)); }
  updateCounter(); renderMetrics();
  busy = false;
  AGENTS.forEach(a => { const l = $('led-' + a.id); if (l && !Voice.speaking) { l.className = 'agent-led'; } });
  updateAgent({ name: 'Jarvis', status: 'idle' });
  reflectReactor();
}

// ================= EVENTS =================
function subscribe() {
  J.on('jarvis:agent', updateAgent);
  J.on('jarvis:confirm', showConfirm);
  J.on('jarvis:stopped', () => { toast('⏹️ Zatrzymano.'); busy = false; automationActive = false; $('auto-warn').classList.remove('on'); AGENTS.forEach(a => $('led-' + a.id).className = 'agent-led'); reflectReactor(); });
  J.on('jarvis:event', (p) => {
    if (!p) return;
    if (p.type === 'automation') { automationActive = p.active; $('auto-warn').classList.toggle('on', p.active); reflectReactor(); }
    else if (p.type === 'scan') toast((p.entry.verdict === 'clean' ? '✔ ' : '⚠️ ') + 'Skan: ' + (p.entry.verdict));
    else if (p.type === 'security') toast('🛡️ ' + p.message);
    else if (p.type === 'memory') toast('🧠 Zapamiętano.');
    else if (p.type === 'skill') toast('⚡ Skill: ' + p.name);
    else if (p.type === 'knowledge') { toast('📚 Wiedza: ' + p.name); renderDocuments(); }
    else if (p.type === 'quarantine') toast('🧷 Kwarantanna: ' + p.from);
  });
}

// ================= WINDOW / INPUT =================
function wireWindow() {
  $('btn-min').onclick = () => J.winMinimize();
  $('btn-close').onclick = () => J.winClose();
  let top = false; $('btn-top').onclick = () => { top = !top; J.winToggleTop(top); $('btn-top').style.color = top ? 'var(--ac)' : ''; };
}
function wireInput() {
  const ta = $('input');
  ta.addEventListener('input', () => { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 110) + 'px'; });
  ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
  $('send').onclick = send;
  $('mic').onclick = () => Voice.toggleMic();
}

// ================= PANELS =================
function wirePanels() {
  document.querySelectorAll('[data-panel]').forEach(b => b.onclick = () => openPanel(b.dataset.panel));
  document.querySelectorAll('[data-close]').forEach(b => b.onclick = closePanels);
  $('overlay').onclick = closePanels;
}
function openPanel(name) {
  closePanels(); $('overlay').classList.add('on'); $('panel-' + name).classList.add('on');
  if (name === 'settings') renderSettings();
  if (name === 'knowledge') renderKnowledge();
  if (name === 'security') renderSecurity();
  if (name === 'log') renderLog();
}
function closePanels() { $('overlay').classList.remove('on'); document.querySelectorAll('.panel').forEach(p => p.classList.remove('on')); }

function renderSettings() {
  const s = settings;
  const modelSel = (key) => `<select data-model="${key}">${MODELS.map(m => `<option ${((s.models && s.models[key]) === m) ? 'selected' : ''}>${m}</option>`).join('')}</select>`;
  const tog = (key, label) => `<div class="switch"><span>${label}</span><div class="tog ${s[key] ? 'on' : ''}" data-tog="${key}"><i></i></div></div>`;
  $('settings-body').innerHTML = `
    <div class="field"><label>Jak mam się do Ciebie zwracać</label><input id="set-userName" value="${esc(s.userName)}"></div>
    <div class="field"><label>Silnik AI (mózg Jarvisa)</label><select id="set-provider">
      <option value="anthropic" ${s.provider !== 'ollama' ? 'selected' : ''}>Anthropic Claude (płatne API)</option>
      <option value="ollama" ${s.provider === 'ollama' ? 'selected' : ''}>Ollama — lokalnie, za darmo</option>
    </select><div class="hint">Ollama = model na Twoim komputerze: 0 zł, offline, prywatnie. Wymaga zainstalowania z ollama.com.</div></div>
    <div id="box-ollama" style="display:${s.provider === 'ollama' ? 'block' : 'none'}">
      <div class="field"><label>Adres Ollama</label><input id="set-ollamaUrl" value="${esc(s.ollamaUrl)}" placeholder="http://localhost:11434"></div>
      <div class="field"><label>Model Ollama</label><input id="set-ollamaModel" value="${esc(s.ollamaModel)}" placeholder="qwen2.5:7b"><div class="hint">Najpierw pobierz model, np. w terminalu: <b>ollama pull qwen2.5:7b</b> (dobra obsługa narzędzi). Mocniejszy: qwen2.5:14b.</div></div>
    </div>
    <div id="box-anthropic" style="display:${s.provider === 'ollama' ? 'none' : 'block'}">
      <div class="field"><label>Klucz API Anthropic</label><input id="set-apiKey" type="password" value="${esc(s.apiKey)}" placeholder="sk-ant-..."><div class="hint">Uzyskasz go na console.anthropic.com (płatne za użycie). Przechowywany lokalnie.</div></div>
    </div>
    <div class="field"><label>Klucz API VirusTotal (skaner)</label><input id="set-vtKey" type="password" value="${esc(s.virusTotalKey)}" placeholder="opcjonalny"><div class="hint">Darmowy na virustotal.com — bez niego skanowanie plików nie działa.</div></div>
    <div class="field"><label>Model — Jarvis (orkiestrator)</label>${modelSel('orchestrator')}</div>
    <div class="row2">
      <div class="field"><label>Operator</label>${modelSel('Operator')}</div>
      <div class="field"><label>Researcher</label>${modelSel('Researcher')}</div>
    </div>
    <div class="row2">
      <div class="field"><label>Guard</label>${modelSel('Guard')}</div>
      <div class="field"><label>Archivist</label>${modelSel('Archivist')}</div>
    </div>
    <div class="field"><label>Folder Obsidian vault (pamięć)</label><input id="set-vault" value="${esc(s.vaultPath || '')}" placeholder="np. C:\\Users\\Ty\\ObsidianVault"><div class="hint">Puste = pamięć lokalna w aplikacji. Podaj ścieżkę, by notatki-graf zapisywały się w Twoim vaultcie Obsidian (z <b>[[wikilinkami]]</b>).</div></div>
    <div class="field"><label>Lokalny serwer głosu (opcjonalnie)</label><input id="set-localVoice" value="${esc(s.localVoiceUrl || '')}" placeholder="http://localhost:8000"><div class="hint">Adres lokalnego STT/TTS (faster-whisper + Kokoro), jeśli go postawisz. Puste = głos z przeglądarki.</div></div>
    <div class="field"><label>Motyw</label><select id="set-theme">${['green', 'cyan', 'amber', 'violet'].map(t => `<option ${s.theme === t ? 'selected' : ''}>${t}</option>`).join('')}</select></div>
    <div class="field"><label>Głos Jarvisa (synteza mowy)</label><select id="set-voice"></select></div>
    ${tog('voiceEnabled', '🔊 Mowa włączona')}
    ${tog('wakeWord', '🎙️ Wake word „Hej Jarvis”')}
    ${tog('continuousListen', '👂 Nasłuch ciągły')}
    ${tog('watchDownloads', '🛡️ Auto-skan folderu Pobrane')}
    ${tog('autoStart', '🚀 Uruchamiaj ze startem systemu')}
    <button class="btn" id="set-save" style="margin-top:8px">Zapisz ustawienia</button>
    <div style="height:22px"></div>
    <div class="swarm-h" style="margin:0 0 10px"><span>Pamięć długoterminowa</span></div>
    <div id="mem-list"></div>`;
  fillVoices();
  document.querySelectorAll('#settings-body .tog').forEach(t => t.onclick = () => t.classList.toggle('on'));
  $('set-provider').onchange = (e) => {
    const ol = e.target.value === 'ollama';
    $('box-ollama').style.display = ol ? 'block' : 'none';
    $('box-anthropic').style.display = ol ? 'none' : 'block';
  };
  $('set-save').onclick = saveSettings;
  loadMemory();
}
function fillVoices() {
  const sel = $('set-voice'); if (!sel) return;
  const voices = (window.speechSynthesis && speechSynthesis.getVoices()) || [];
  const pl = voices.filter(v => /pl/i.test(v.lang));
  const list = (pl.length ? pl : voices);
  sel.innerHTML = '<option value="">(domyślny systemowy)</option>' + list.map(v => `<option ${settings.voiceName === v.name ? 'selected' : ''}>${esc(v.name)}</option>`).join('');
}
async function saveSettings() {
  const s = Object.assign({}, settings);
  s.userName = $('set-userName').value.trim() || 'Sir';
  s.provider = $('set-provider').value;
  s.apiKey = $('set-apiKey').value.trim();
  s.ollamaUrl = $('set-ollamaUrl').value.trim() || 'http://localhost:11434';
  s.ollamaModel = $('set-ollamaModel').value.trim() || 'qwen2.5:7b';
  s.virusTotalKey = $('set-vtKey').value.trim();
  s.vaultPath = $('set-vault').value.trim();
  s.localVoiceUrl = $('set-localVoice').value.trim();
  s.theme = $('set-theme').value;
  s.voiceName = $('set-voice').value;
  s.models = Object.assign({}, s.models);
  document.querySelectorAll('#settings-body [data-model]').forEach(el => s.models[el.dataset.model] = el.value);
  document.querySelectorAll('#settings-body .tog').forEach(t => s[t.dataset.tog] = t.classList.contains('on'));
  settings = await J.setSettings(s);
  applyTheme(); updateApiLed(); $('wname').textContent = settings.userName;
  Voice.applySettings(); renderDocuments();
  toast('✅ Zapisano.'); closePanels();
}
async function loadMemory() {
  const mem = await J.getMemory();
  $('mem-list').innerHTML = mem.length ? mem.map(m => `<div class="list-item"><div class="li-top"><span>${esc(m.text)}</span><button class="li-del" data-mem="${m.id}">usuń</button></div><div class="li-sub">${esc(m.date || '')}</div></div>`).join('') : '<div class="empty-note">Pamięć jest pusta. Powiedz „zapamiętaj, że…”.</div>';
  document.querySelectorAll('[data-mem]').forEach(b => b.onclick = async () => { await J.deleteMemory(b.dataset.mem); loadMemory(); });
}

async function renderKnowledge() {
  const topics = await J.listKnowledge();
  $('knowledge-body').innerHTML = topics.length
    ? topics.map(t => `<div class="list-item"><div class="li-top"><b data-kn="${esc(t.name)}" style="cursor:pointer;color:var(--ac)">${esc(t.name)}</b><button class="li-del" data-kndel="${esc(t.name)}">usuń</button></div><div class="li-sub">${esc(t.summary || '')}</div></div>`).join('')
    : '<div class="empty-note">Brak zapisanych tematów. Poproś Jarvisa o research — wiedza pojawi się tutaj i będzie się pogłębiać.</div>';
  document.querySelectorAll('[data-kn]').forEach(b => b.onclick = async () => { const r = await J.getKnowledge(b.dataset.kn); if (r.ok) showDoc(b.dataset.kn, r.content); });
  document.querySelectorAll('[data-kndel]').forEach(b => b.onclick = async () => { await J.deleteKnowledge(b.dataset.kndel); renderKnowledge(); });
}
function showDoc(name, content) {
  $('knowledge-body').innerHTML = `<button class="btn ghost" id="kn-back" style="margin-bottom:14px">← Wróć</button><div class="list-item" style="white-space:pre-wrap;line-height:1.6">${esc(content)}</div>`;
  $('kn-back').onclick = renderKnowledge;
}
async function renderSecurity() {
  const scans = await J.securityRecent(); const quar = await J.quarantineList();
  $('security-body').innerHTML = `
    <div class="swarm-h" style="margin:0 0 10px"><span>Ostatnie skany</span></div>
    ${scans.length ? scans.map(s => `<div class="list-item"><div class="li-top"><span>${esc((s.path || '').split(/[\\\/]/).pop())}</span><span class="verdict ${s.verdict}">${s.verdict}</span></div><div class="li-sub">${new Date(s.ts).toLocaleString('pl-PL')}</div></div>`).join('') : '<div class="empty-note">Brak skanów. Dodaj klucz VirusTotal i poproś Guarda o skan pliku.</div>'}
    <div class="swarm-h" style="margin:18px 0 10px"><span>Kwarantanna</span></div>
    ${quar.length ? quar.map(q => `<div class="list-item">${esc(q.name)}</div>`).join('') : '<div class="empty-note">Kwarantanna pusta.</div>'}`;
}
async function renderLog() {
  const log = await J.getLog();
  $('log-body').innerHTML = log.length ? log.map(e => `<div class="list-item"><div class="li-top"><b style="color:var(--ac)">${esc(e.type)}</b><span class="li-sub">${new Date(e.ts).toLocaleTimeString('pl-PL')}</span></div><div class="li-sub">${esc(JSON.stringify(rest(e)).slice(0, 160))}</div></div>`).join('') : '<div class="empty-note">Brak akcji w logu.</div>';
}
function rest(e) { const c = Object.assign({}, e); delete c.type; delete c.ts; return c; }

// ================= CONFIRM MODAL =================
let confirmId = null;
function showConfirm(p) {
  confirmId = p.id;
  $('m-title').textContent = p.title || 'Potwierdzenie';
  $('m-msg').textContent = p.message || '';
  $('m-ic').textContent = p.danger ? '⚠️' : '❓';
  const cmd = $('m-cmd');
  if (p.command) { cmd.style.display = 'block'; cmd.textContent = p.command; } else cmd.style.display = 'none';
  $('m-ok').textContent = p.danger ? 'Tak, wykonaj' : 'Wykonaj';
  $('modal-ovl').classList.add('on');
}
function wireModal() {
  $('m-ok').onclick = () => { if (confirmId) J.confirmResponse(confirmId, true); $('modal-ovl').classList.remove('on'); confirmId = null; };
  $('m-cancel').onclick = () => { if (confirmId) J.confirmResponse(confirmId, false); $('modal-ovl').classList.remove('on'); confirmId = null; };
}

// ================= MISC =================
function startClock() { const t = () => $('clock').textContent = new Date().toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit', second: '2-digit' }); t(); setInterval(t, 1000); }
async function pollSysStats() {
  // lekki podgląd — używamy narzędzia przez zwykłą ścieżkę tylko jeśli klucza brak, więc pomijamy API; pokażemy z performance jeśli dostępne
  try { if (performance && performance.memory) { const m = performance.memory; $('stat-sys').textContent = 'RAM UI: ' + Math.round(m.usedJSHeapSize / 1048576) + ' MB'; } } catch {}
}
let toastT = null;
function toast(msg) { const el = $('toast'); el.textContent = msg; el.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => el.classList.remove('on'), 2600); }

// ================= VOICE =================
const Voice = {
  speaking: false, listening: false, energy: 0, rec: null, vizBars: [], vizRAF: null, audioCtx: null, analyser: null, micStream: null, recActive: false,
  init() {
    this.populateVoicesLater();
    if (settings.wakeWord || settings.continuousListen) this.startContinuous();
  },
  populateVoicesLater() { if (window.speechSynthesis) { speechSynthesis.onvoiceschanged = () => { if ($('set-voice')) fillVoices(); }; } },
  applySettings() { this.stopContinuous(); if (settings.wakeWord || settings.continuousListen) this.startContinuous(); },

  speak(text) {
    if (!window.speechSynthesis || !settings.voiceEnabled) return;
    try {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(String(text).replace(/[*_`#]/g, '').slice(0, 600));
      u.lang = 'pl-PL';
      const voices = speechSynthesis.getVoices();
      const v = voices.find(v => v.name === settings.voiceName) || voices.find(v => /pl/i.test(v.lang));
      if (v) u.voice = v;
      u.onstart = () => { this.speaking = true; reflectReactor(); this.fakeViz(); };
      u.onend = () => { this.speaking = false; this.stopViz(); reflectReactor(); };
      speechSynthesis.speak(u);
    } catch (e) { /* brak TTS */ }
  },

  _makeRec() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { toast('🎙️ Rozpoznawanie mowy niedostępne w tym środowisku. Użyj pola tekstowego.'); return null; }
    const r = new SR(); r.lang = 'pl-PL'; r.interimResults = true; r.maxAlternatives = 1; return r;
  },

  toggleMic() {
    if (this.recActive) { this.stopAll(); return; }
    this.startCommand();
  },

  startCommand() {
    const r = this._makeRec(); if (!r) return;
    this.recActive = true; this.listening = true; $('mic').classList.add('on'); $('led-mic').classList.add('rec'); reflectReactor(); this.liveViz();
    r.continuous = false;
    let finalText = '';
    r.onresult = (e) => { finalText = ''; for (let i = 0; i < e.results.length; i++) finalText += e.results[i][0].transcript; $('input').value = finalText; };
    r.onerror = (e) => { toast('🎙️ Błąd mikrofonu: ' + e.error + ' (używam trybu tekstowego).'); };
    r.onend = () => { this.recActive = false; this.listening = false; $('mic').classList.remove('on'); $('led-mic').classList.remove('rec'); this.stopViz(); reflectReactor(); const t = $('input').value.trim(); if (t) send(); };
    try { r.start(); this.rec = r; } catch { this.recActive = false; }
  },

  // Ciągły nasłuch z wykrywaniem wake worda
  startContinuous() {
    const r = this._makeRec(); if (!r) return;
    r.continuous = true; r.interimResults = true;
    let armed = false, cmdBuf = '';
    r.onresult = (e) => {
      let txt = '';
      for (let i = e.resultIndex; i < e.results.length; i++) txt += e.results[i][0].transcript;
      const low = txt.toLowerCase();
      if (!armed && /(jarvis|dżarwis|dzarwis|jarwis)/.test(low)) {
        armed = true; cmdBuf = low.split(/jarvis|dżarwis|dzarwis|jarwis/).pop(); beep(); this.listening = true; $('led-mic').classList.add('rec'); reflectReactor();
      } else if (armed) { cmdBuf = txt; $('input').value = txt.trim(); }
      if (armed && e.results[e.results.length - 1].isFinal) {
        const cmd = cmdBuf.trim(); armed = false; this.listening = false; $('led-mic').classList.remove('rec'); reflectReactor();
        if (cmd.length > 1) { $('input').value = cmd; send(); }
      }
    };
    r.onerror = (e) => { /* np. 'network' w niektórych buildach — degradacja do tekstu */ if (e.error === 'not-allowed') toast('🎙️ Brak dostępu do mikrofonu.'); };
    r.onend = () => { if (settings.wakeWord || settings.continuousListen) { try { r.start(); } catch {} } };
    try { r.start(); this.rec = r; } catch {}
  },
  stopContinuous() { try { if (this.rec) { this.rec.onend = null; this.rec.stop(); } } catch {} this.rec = null; },
  stopAll() { try { if (this.rec) this.rec.stop(); } catch {} this.recActive = false; this.listening = false; $('mic').classList.remove('on'); $('led-mic').classList.remove('rec'); this.stopViz(); reflectReactor(); },

  // Wizualizacja audio z mikrofonu (real) — best effort
  async liveViz() {
    try {
      if (!this.micStream) this.micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.audioCtx = this.audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const src = this.audioCtx.createMediaStreamSource(this.micStream);
      this.analyser = this.audioCtx.createAnalyser(); this.analyser.fftSize = 64; src.connect(this.analyser);
      const data = new Uint8Array(this.analyser.frequencyBinCount);
      const loop = () => { if (!this.listening) return; this.analyser.getByteFrequencyData(data); let sum = 0; for (const v of data) sum += v; this.energy = (sum / data.length) / 255; this.vizRAF = requestAnimationFrame(loop); };
      loop();
    } catch { this.fakeViz(); }
  },
  fakeViz() { const loop = () => { if (!this.speaking && !this.listening) { this.energy = 0; return; } this.energy = 0.25 + Math.random() * 0.55; this.vizRAF = requestAnimationFrame(() => setTimeout(loop, 60)); }; loop(); },
  stopViz() { if (this.vizRAF) cancelAnimationFrame(this.vizRAF); this.energy = 0; }
};

function beep() { try { const c = Voice.audioCtx || new (window.AudioContext || window.webkitAudioContext)(); Voice.audioCtx = c; const o = c.createOscillator(), g = c.createGain(); o.frequency.value = 880; o.connect(g); g.connect(c.destination); g.gain.value = .06; o.start(); o.stop(c.currentTime + .12); } catch {} }
