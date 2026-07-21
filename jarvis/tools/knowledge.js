'use strict';
/*
 * Pamięć długoterminowa, notatki, baza wiedzy (research), data/godzina,
 * bezpieczny kalkulator (bez eval) oraz makra.
 * web_search jest narzędziem serwerowym Anthropic (dodawanym w runnerze dla
 * agenta Researcher) — tutaj obsługujemy zapis/odczyt wyników do knowledge/.
 */
const fs = require('fs');
const path = require('path');

function slug(s) { return String(s || 'temat').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'temat'; }

// ---------- Pamięć ----------
function remember(input, ctx) {
  const text = (input.text || '').trim();
  if (!text) return { ok: false, error: 'Podaj treść do zapamiętania.' };
  const mem = ctx.store.memory();
  mem.push({ id: 'm_' + Date.now() + Math.random().toString(36).slice(2, 6), text, date: new Date().toISOString().slice(0, 10) });
  ctx.store.saveMemory(mem);
  ctx.emit('jarvis:event', { type: 'memory', text });
  return { ok: true, message: 'Zapamiętałem.' };
}
function forget(input, ctx) {
  const q = (input.query || '').toLowerCase();
  const mem = ctx.store.memory();
  const before = mem.length;
  const kept = mem.filter(m => !m.text.toLowerCase().includes(q));
  ctx.store.saveMemory(kept);
  return { ok: true, message: `Usunięto ${before - kept.length} wpis(y/ów) z pamięci.` };
}

// ---------- Notatki ----------
function addNote(input, ctx) {
  const text = (input.text || '').trim();
  if (!text) return { ok: false, error: 'Pusta notatka.' };
  const notes = ctx.store.notes();
  notes.unshift({ id: 'n_' + Date.now(), text, ts: Date.now() });
  ctx.store.saveNotes(notes);
  return { ok: true, message: 'Notatka zapisana.' };
}
function listNotes(_input, ctx) { return { ok: true, notes: ctx.store.notes().slice(0, 50) }; }
function deleteNote(input, ctx) {
  ctx.store.saveNotes(ctx.store.notes().filter(n => n.id !== input.id));
  return { ok: true, message: 'Usunięto notatkę.' };
}

// ---------- Baza wiedzy ----------
function topicPath(store, name) { return store.dataPath('knowledge', slug(name) + '.md'); }
function saveTopic(input, ctx) {
  const name = (input.name || '').trim();
  const content = (input.content || '').trim();
  if (!name || !content) return { ok: false, error: 'Podaj nazwę tematu i treść.' };
  const fp = topicPath(ctx.store, name);
  const exists = fs.existsSync(fp);
  const stamp = new Date().toISOString().slice(0, 16).replace('T', ' ');
  try {
    if (exists) {
      // pogłębianie istniejącej wiedzy — dopisujemy datowaną sekcję
      fs.appendFileSync(fp, `\n\n---\n## Aktualizacja ${stamp}\n${content}\n`);
    } else {
      fs.writeFileSync(fp, `# ${name}\n_utworzono ${stamp}_\n\n${content}\n`);
    }
    ctx.emit('jarvis:event', { type: 'knowledge', name });
    return { ok: true, message: exists ? `Pogłębiono wiedzę o temacie „${name}”.` : `Zapisano nowy temat „${name}”.` };
  } catch (e) { return { ok: false, error: e.message }; }
}
function readTopic(input, ctx) {
  const fp = topicPath(ctx.store, input.name || '');
  if (!fs.existsSync(fp)) return { ok: false, error: 'Brak takiego tematu w bazie wiedzy.' };
  try { return { ok: true, name: input.name, content: fs.readFileSync(fp, 'utf8').slice(0, 8000) }; }
  catch (e) { return { ok: false, error: e.message }; }
}

// pomocnicze dla IPC / promptu
function listTopics(store) {
  try {
    return fs.readdirSync(store.dataPath('knowledge')).filter(f => f.endsWith('.md')).map(f => {
      const full = store.dataPath('knowledge', f);
      let first = ''; try { const c = fs.readFileSync(full, 'utf8'); first = (c.split('\n').find(l => l && !l.startsWith('#') && !l.startsWith('_')) || '').slice(0, 120); } catch {}
      return { file: f, name: f.replace(/\.md$/, ''), summary: first };
    });
  } catch { return []; }
}
function readTopicFile(store, name) { const fp = store.dataPath('knowledge', name.endsWith('.md') ? name : name + '.md'); try { return { ok: true, content: fs.readFileSync(fp, 'utf8') }; } catch (e) { return { ok: false, error: e.message }; } }
function deleteTopicFile(store, name) { const fp = store.dataPath('knowledge', name.endsWith('.md') ? name : name + '.md'); try { fs.unlinkSync(fp); return { ok: true }; } catch (e) { return { ok: false, error: e.message }; } }

// ---------- Data/godzina ----------
function getDatetime() {
  const d = new Date();
  return { ok: true, iso: d.toISOString(), local: d.toLocaleString('pl-PL'), weekday: d.toLocaleDateString('pl-PL', { weekday: 'long' }) };
}

// ---------- Bezpieczny kalkulator (shunting-yard, bez eval) ----------
function calculate(input) {
  try { const v = evalExpr(String(input.expression || '')); return { ok: true, result: v }; }
  catch (e) { return { ok: false, error: 'Nie umiem policzyć: ' + e.message }; }
}
function evalExpr(expr) {
  const tokens = expr.match(/\d+\.?\d*|[+\-*/%^()]/g);
  if (!tokens) throw new Error('puste wyrażenie');
  const prec = { '+': 1, '-': 1, '*': 2, '/': 2, '%': 2, '^': 3 };
  const out = [], ops = [];
  for (const t of tokens) {
    if (/^\d/.test(t)) out.push(parseFloat(t));
    else if (t === '(') ops.push(t);
    else if (t === ')') { while (ops.length && ops[ops.length - 1] !== '(') apply(out, ops.pop()); ops.pop(); }
    else { while (ops.length && prec[ops[ops.length - 1]] >= prec[t] && ops[ops.length - 1] !== '(') apply(out, ops.pop()); ops.push(t); }
  }
  while (ops.length) apply(out, ops.pop());
  if (out.length !== 1) throw new Error('błędne wyrażenie');
  return out[0];
}
function apply(stack, op) {
  const b = stack.pop(), a = stack.pop();
  if (a === undefined || b === undefined) throw new Error('błędne wyrażenie');
  switch (op) {
    case '+': stack.push(a + b); break;
    case '-': stack.push(a - b); break;
    case '*': stack.push(a * b); break;
    case '/': stack.push(a / b); break;
    case '%': stack.push(a % b); break;
    case '^': stack.push(Math.pow(a, b)); break;
    default: throw new Error('operator ' + op);
  }
}

// ---------- Makra ----------
function listMacros(_input, ctx) { return { ok: true, macros: ctx.store.macros() }; }
function saveMacro(input, ctx) {
  const macros = ctx.store.macros().filter(m => m.name !== input.name);
  macros.push({ name: input.name, steps: input.steps || [] });
  ctx.store.saveMacros(macros);
  return { ok: true, message: `Zapisano makro „${input.name}”.` };
}

const schemas = [
  { name: 'remember', description: 'Zapamiętuje trwały fakt o użytkowniku lub jego preferencjach (pamięć długoterminowa). Używaj, gdy użytkownik prosi „zapamiętaj” lub podaje ważną informację o sobie.', input_schema: { type: 'object', properties: { text: { type: 'string' } }, required: ['text'] } },
  { name: 'forget', description: 'Usuwa z pamięci fakty pasujące do zapytania.', input_schema: { type: 'object', properties: { query: { type: 'string' } }, required: ['query'] } },
  { name: 'add_note', description: 'Dodaje szybką notatkę.', input_schema: { type: 'object', properties: { text: { type: 'string' } }, required: ['text'] } },
  { name: 'list_notes', description: 'Zwraca zapisane notatki.', input_schema: { type: 'object', properties: {} } },
  { name: 'delete_note', description: 'Usuwa notatkę po id.', input_schema: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'] } },
  { name: 'save_topic', description: 'Zapisuje wynik researchu do bazy wiedzy jako temat (Markdown). Jeśli temat istnieje, POGŁĘBIA go (dopisuje nową sekcję). Zawsze dołączaj źródła.', input_schema: { type: 'object', properties: { name: { type: 'string' }, content: { type: 'string' } }, required: ['name', 'content'] } },
  { name: 'read_topic', description: 'Odczytuje zapisany temat z bazy wiedzy, aby wykorzystać wcześniej zebraną wiedzę.', input_schema: { type: 'object', properties: { name: { type: 'string' } }, required: ['name'] } },
  { name: 'get_datetime', description: 'Zwraca aktualną datę i godzinę.', input_schema: { type: 'object', properties: {} } },
  { name: 'calculate', description: 'Oblicza wyrażenie matematyczne (+ - * / % ^, nawiasy).', input_schema: { type: 'object', properties: { expression: { type: 'string' } }, required: ['expression'] } },
  { name: 'list_macros', description: 'Lista zapisanych makr (rutyn).', input_schema: { type: 'object', properties: {} } },
  { name: 'save_macro', description: 'Zapisuje nazwane makro — sekwencję kroków w języku naturalnym do późniejszego wywołania.', input_schema: { type: 'object', properties: { name: { type: 'string' }, steps: { type: 'array', items: { type: 'string' } } }, required: ['name', 'steps'] } }
];

const handlers = {
  remember, forget,
  add_note: addNote, list_notes: listNotes, delete_note: deleteNote,
  save_topic: saveTopic, read_topic: readTopic,
  get_datetime: () => getDatetime(),
  calculate: (input) => calculate(input),
  list_macros: listMacros, save_macro: saveMacro
};

module.exports = { schemas, handlers, listTopics, readTopicFile, deleteTopicFile };
