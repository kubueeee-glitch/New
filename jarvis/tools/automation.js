'use strict';
/*
 * Automatyzacja GUI: mysz, klawiatura, okna (nut-js) oraz wizja ekranu.
 * nut-js jest ładowany leniwie i z pełną obsługą błędów — brak biblioteki
 * nie wywala aplikacji, tylko zwraca czytelny komunikat.
 * screenshot_and_see zwraca obraz (base64 PNG), który runner dołącza do
 * tool_result jako blok image dla modelu z wizją.
 */
let _nut = undefined;
function nut() {
  if (_nut === undefined) { try { _nut = require('@nut-tree-fork/nut-js'); } catch { _nut = null; } }
  return _nut;
}
function needNut() { const n = nut(); if (!n) throw new Error('Automatyzacja wymaga biblioteki nut-js. Uruchom `npm install` (może wymagać narzędzi build).'); return n; }

function markActive(ctx, active) { try { ctx.emit('jarvis:event', { type: 'automation', active }); } catch {} }

// mapowanie przyjaznych nazw klawiszy → nut Key
function mapKey(n, name) {
  const K = n.Key;
  const m = {
    ctrl: K.LeftControl, control: K.LeftControl, alt: K.LeftAlt, shift: K.LeftShift,
    win: K.LeftSuper, cmd: K.LeftSuper, super: K.LeftSuper, meta: K.LeftSuper,
    enter: K.Enter, return: K.Return, tab: K.Tab, esc: K.Escape, escape: K.Escape,
    space: K.Space, backspace: K.Backspace, delete: K.Delete, del: K.Delete,
    up: K.Up, down: K.Down, left: K.Left, right: K.Right,
    home: K.Home, end: K.End, pageup: K.PageUp, pagedown: K.PageDown
  };
  const key = String(name).toLowerCase();
  if (m[key]) return m[key];
  if (key.length === 1) {
    const up = key.toUpperCase();
    if (K[up] !== undefined) return K[up];
    if (/[0-9]/.test(key) && K['Num' + key] !== undefined) return K['Num' + key];
  }
  const cap = key.charAt(0).toUpperCase() + key.slice(1);
  if (K[cap] !== undefined) return K[cap];
  throw new Error('Nieznany klawisz: ' + name);
}

async function mouseMove(input, ctx) {
  const n = needNut(); markActive(ctx, true);
  try { await n.mouse.setPosition(new n.Point(input.x | 0, input.y | 0)); return { ok: true, message: `Kursor → (${input.x|0}, ${input.y|0})` }; }
  finally { markActive(ctx, false); }
}

async function mouseClick(input, ctx) {
  const n = needNut(); markActive(ctx, true);
  try {
    if (input.x != null && input.y != null) await n.mouse.setPosition(new n.Point(input.x | 0, input.y | 0));
    const right = (input.button || 'left').toLowerCase() === 'right';
    if (input.double) { await (right ? n.mouse.rightClick() : n.mouse.doubleClick(n.Button.LEFT)); }
    else { await (right ? n.mouse.rightClick() : n.mouse.leftClick()); }
    ctx.store.appendLog({ type: 'click', x: input.x, y: input.y, button: right ? 'right' : 'left' });
    return { ok: true, message: `Kliknięto ${right ? 'PPM' : 'LPM'}${input.double ? ' (podwójnie)' : ''}` };
  } finally { markActive(ctx, false); }
}

async function mouseDrag(input, ctx) {
  const n = needNut(); markActive(ctx, true);
  try {
    await n.mouse.setPosition(new n.Point(input.fromX | 0, input.fromY | 0));
    await n.mouse.pressButton(n.Button.LEFT);
    await n.mouse.setPosition(new n.Point(input.toX | 0, input.toY | 0));
    await n.mouse.releaseButton(n.Button.LEFT);
    return { ok: true, message: 'Przeciągnięto.' };
  } finally { markActive(ctx, false); }
}

async function typeText(input, ctx) {
  const n = needNut(); markActive(ctx, true);
  try { await n.keyboard.type(input.text || ''); ctx.store.appendLog({ type: 'type', len: (input.text||'').length }); return { ok: true, message: `Wpisano ${(input.text||'').length} znaków.` }; }
  finally { markActive(ctx, false); }
}

async function pressKeys(input, ctx) {
  const n = needNut(); markActive(ctx, true);
  try {
    let keys = input.keys;
    if (typeof keys === 'string') keys = keys.split('+').map(s => s.trim()).filter(Boolean);
    if (!Array.isArray(keys) || !keys.length) return { ok: false, error: 'Podaj klawisze, np. ["Ctrl","C"].' };
    const mapped = keys.map(k => mapKey(n, k));
    for (const k of mapped) await n.keyboard.pressKey(k);
    for (const k of mapped.reverse()) await n.keyboard.releaseKey(k);
    ctx.store.appendLog({ type: 'hotkey', keys });
    return { ok: true, message: 'Skrót: ' + keys.join('+') };
  } finally { markActive(ctx, false); }
}

async function scroll(input, ctx) {
  const n = needNut(); markActive(ctx, true);
  try {
    const amt = Math.abs(input.amount || 3);
    const dir = (input.direction || 'down').toLowerCase();
    if (dir === 'down') await n.mouse.scrollDown(amt);
    else if (dir === 'up') await n.mouse.scrollUp(amt);
    else if (dir === 'left') await n.mouse.scrollLeft(amt);
    else if (dir === 'right') await n.mouse.scrollRight(amt);
    return { ok: true, message: `Przewinięto ${dir} o ${amt}` };
  } finally { markActive(ctx, false); }
}

async function screenshotAndSee(_input, ctx) {
  try {
    const b64 = await ctx.captureScreen();
    return { ok: true, note: 'Zrzut ekranu wykonany — analizuję obraz.', __image_base64: b64 };
  } catch (e) { return { ok: false, error: 'Nie udało się przechwycić ekranu: ' + e.message }; }
}

async function listWindows() {
  const n = nut(); if (!n || !n.getWindows) return { ok: false, error: 'Lista okien niedostępna (brak nut-js).' };
  try {
    const wins = await n.getWindows();
    const titles = [];
    for (const w of wins.slice(0, 40)) { try { titles.push(await w.getTitle()); } catch {} }
    return { ok: true, windows: titles.filter(Boolean) };
  } catch (e) { return { ok: false, error: e.message }; }
}

async function focusWindow(input, ctx) {
  const n = nut(); if (!n || !n.getWindows) return { ok: false, error: 'Sterowanie oknami niedostępne (brak nut-js).' };
  try {
    const wins = await n.getWindows();
    const want = (input.title || '').toLowerCase();
    for (const w of wins) {
      let t = ''; try { t = await w.getTitle(); } catch {}
      if (t && t.toLowerCase().includes(want)) {
        if (typeof w.focus === 'function') await w.focus();
        ctx.store.appendLog({ type: 'focus_window', title: t });
        return { ok: true, message: `Aktywowano okno: ${t}` };
      }
    }
    return { ok: false, error: `Nie znaleziono okna zawierającego „${input.title}”.` };
  } catch (e) { return { ok: false, error: e.message }; }
}

const schemas = [
  { name: 'screenshot_and_see', description: 'Robi zrzut ekranu i przekazuje go modelowi do analizy wizualnej. Użyj, aby zobaczyć co jest na ekranie przed klikaniem, albo gdy użytkownik pyta „co widzę na ekranie”.', input_schema: { type: 'object', properties: {} } },
  { name: 'mouse_move', description: 'Przesuwa kursor myszy do współrzędnych ekranu (piksele).', input_schema: { type: 'object', properties: { x: { type: 'number' }, y: { type: 'number' } }, required: ['x', 'y'] } },
  { name: 'mouse_click', description: 'Klika myszą w bieżącym miejscu lub w podanych współrzędnych. button: left/right, double: true dla podwójnego kliknięcia.', input_schema: { type: 'object', properties: { x: { type: 'number' }, y: { type: 'number' }, button: { type: 'string', enum: ['left', 'right'] }, double: { type: 'boolean' } } } },
  { name: 'mouse_drag', description: 'Przeciąga myszą od jednego punktu do drugiego (przytrzymany LPM).', input_schema: { type: 'object', properties: { fromX: { type: 'number' }, fromY: { type: 'number' }, toX: { type: 'number' }, toY: { type: 'number' } }, required: ['fromX', 'fromY', 'toX', 'toY'] } },
  { name: 'type_text', description: 'Wpisuje podany tekst na klawiaturze (do aktywnego pola).', input_schema: { type: 'object', properties: { text: { type: 'string' } }, required: ['text'] } },
  { name: 'press_keys', description: 'Wciska kombinację klawiszy, np. ["Ctrl","C"] albo "Alt+Tab".', input_schema: { type: 'object', properties: { keys: { type: 'array', items: { type: 'string' } } }, required: ['keys'] } },
  { name: 'scroll', description: 'Przewija ekran w danym kierunku.', input_schema: { type: 'object', properties: { direction: { type: 'string', enum: ['up', 'down', 'left', 'right'] }, amount: { type: 'number' } } } },
  { name: 'list_windows', description: 'Zwraca listę tytułów otwartych okien.', input_schema: { type: 'object', properties: {} } },
  { name: 'focus_window', description: 'Aktywuje (przenosi na wierzch) okno, którego tytuł zawiera podany tekst.', input_schema: { type: 'object', properties: { title: { type: 'string' } }, required: ['title'] } }
];

const handlers = {
  screenshot_and_see: screenshotAndSee,
  mouse_move: mouseMove,
  mouse_click: mouseClick,
  mouse_drag: mouseDrag,
  type_text: typeText,
  press_keys: pressKeys,
  scroll: scroll,
  list_windows: () => listWindows(),
  focus_window: focusWindow
};

module.exports = { schemas, handlers };
