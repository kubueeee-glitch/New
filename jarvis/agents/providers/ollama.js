'use strict';
/* Provider Ollama — lokalny model (za darmo, offline). Tłumaczy neutralny
 * format na Ollama /api/chat (z obsługą narzędzi) i zwraca znormalizowaną
 * odpowiedź { text, toolCalls, stopReason }. */

async function chat({ settings, system, messages, tools, maxTokens = 2048 }) {
  const base = (settings.ollamaUrl || 'http://localhost:11434').replace(/\/+$/, '');
  const url = base + '/api/chat';
  const body = {
    model: settings.ollamaModel || 'qwen2.5:7b',
    stream: false,
    messages: toOllama(system, messages),
    options: { num_predict: maxTokens }
  };
  // Ollama nie zna narzędzi serwerowych (mają pole type) — pomijamy je.
  const useTools = (tools || []).filter(t => !t.type);
  if (useTools.length) body.tools = useTools.map(t => ({ type: 'function', function: { name: t.name, description: t.description, parameters: t.input_schema || { type: 'object', properties: {} } } }));

  let res;
  try {
    res = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  } catch (e) {
    throw new Error('Nie mogę połączyć się z Ollamą (' + base + '). Czy jest uruchomiona? Zainstaluj z ollama.com i uruchom `ollama serve`.');
  }
  if (!res.ok) {
    let t = ''; try { t = await res.text(); } catch {}
    if (res.status === 404) throw new Error('Model „' + body.model + '” nie jest pobrany. Uruchom: ollama pull ' + body.model);
    throw new Error('Ollama HTTP ' + res.status + (t ? ': ' + t.slice(0, 200) : ''));
  }
  const data = await res.json();
  const msg = data.message || {};
  const text = (msg.content || '').trim();
  const toolCalls = (msg.tool_calls || []).map((tc, i) => ({
    id: 'oc_' + Date.now() + '_' + i,
    name: tc.function && tc.function.name,
    input: parseArgs(tc.function && tc.function.arguments)
  })).filter(tc => tc.name);
  return { text, toolCalls, stopReason: toolCalls.length ? 'tool_use' : 'end' };
}

function toOllama(system, messages) {
  const out = [];
  if (system) out.push({ role: 'system', content: system });
  for (const m of messages) {
    if (m.role === 'user') out.push({ role: 'user', content: m.content });
    else if (m.role === 'assistant') {
      const o = { role: 'assistant', content: m.content || '' };
      if (m.toolCalls && m.toolCalls.length) o.tool_calls = m.toolCalls.map(tc => ({ function: { name: tc.name, arguments: tc.input || {} } }));
      out.push(o);
    } else if (m.role === 'tool') {
      for (const r of (m.results || [])) out.push({ role: 'tool', content: JSON.stringify(stripImage(r.output)).slice(0, 4000) });
    }
  }
  return out;
}

function stripImage(o) { if (o && o.__image_base64) { const c = Object.assign({}, o); delete c.__image_base64; return c; } return o; }
function parseArgs(a) { if (!a) return {}; if (typeof a === 'object') return a; try { return JSON.parse(a); } catch { return {}; } }

module.exports = { chat };
