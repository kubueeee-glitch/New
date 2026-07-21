'use strict';
/*
 * THE BRAIN — architektura „skills".
 * Skill = folder z plikiem SKILL.md. Jarvis widzi tylko krótki indeks
 * (nazwa + opis) wszystkich skilli, a pełną treść wczytuje na żądanie
 * narzędziem load_skill — „ładuje tylko to, czego akurat potrzebuje".
 *
 * Skille czytane są z dwóch miejsc:
 *   - <app>/skills           (dostarczone z aplikacją, przykładowe)
 *   - <userData>/skills      (własne skille użytkownika)
 */
const fs = require('fs');
const path = require('path');

function skillDirs(ctx) {
  const dirs = [];
  try { dirs.push(path.join(__dirname, '..', 'skills')); } catch {}
  try { dirs.push(ctx.store.dataPath('skills')); } catch {}
  return dirs;
}

function parseSkill(md) {
  // Obsługa prostego front-matter (--- name: ... description: ... ---) lub
  // pierwszego nagłówka + pierwszego akapitu.
  let name = '', description = '';
  const fm = md.match(/^---\s*([\s\S]*?)\s*---/);
  if (fm) {
    const n = fm[1].match(/name:\s*(.+)/i); if (n) name = n[1].trim();
    const d = fm[1].match(/description:\s*(.+)/i); if (d) description = d[1].trim();
  }
  if (!name) { const h = md.match(/^#\s+(.+)/m); if (h) name = h[1].trim(); }
  if (!description) { const p = md.split('\n').find(l => l.trim() && !l.startsWith('#') && !l.startsWith('---')); if (p) description = p.trim().slice(0, 160); }
  return { name, description };
}

function listSkills(ctx) {
  const out = [];
  const seen = new Set();
  for (const dir of skillDirs(ctx)) {
    let entries = [];
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { continue; }
    for (const e of entries) {
      if (!e.isDirectory()) continue;
      const mdPath = path.join(dir, e.name, 'SKILL.md');
      if (!fs.existsSync(mdPath)) continue;
      const id = e.name.toLowerCase();
      if (seen.has(id)) continue; seen.add(id);
      let meta = { name: e.name, description: '' };
      try { meta = Object.assign(meta, parseSkill(fs.readFileSync(mdPath, 'utf8'))); } catch {}
      out.push({ id: e.name, name: meta.name || e.name, description: meta.description, path: mdPath });
    }
  }
  return out;
}

function skillsIndex(ctx) {
  const s = listSkills(ctx);
  if (!s.length) return '(brak skilli)';
  return s.map(x => `- ${x.name}: ${x.description}`).join('\n');
}

function loadSkill(input, ctx) {
  const want = (input.name || '').toLowerCase();
  const skill = listSkills(ctx).find(s => s.name.toLowerCase() === want || s.id.toLowerCase() === want);
  if (!skill) return { ok: false, error: 'Nie znaleziono skilla „' + input.name + '”.' };
  try {
    const content = fs.readFileSync(skill.path, 'utf8');
    ctx.emit('jarvis:event', { type: 'skill', name: skill.name });
    return { ok: true, name: skill.name, content: content.slice(0, 8000) };
  } catch (e) { return { ok: false, error: e.message }; }
}

const schemas = [
  { name: 'load_skill', description: 'Wczytuje pełną instrukcję wybranego skilla (SKILL.md), gdy zadanie tego wymaga. Najpierw sprawdź indeks skilli w prompcie, potem wczytaj właściwy.', input_schema: { type: 'object', properties: { name: { type: 'string' } }, required: ['name'] } }
];
const handlers = { load_skill: loadSkill };

module.exports = { schemas, handlers, listSkills, skillsIndex };
