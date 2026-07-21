'use strict';
/* Provider Anthropic — tłumaczy neutralny format wiadomości na Claude API
 * i zwraca znormalizowaną odpowiedź { text, toolCalls, stopReason }. */
const API_URL = 'https://api.anthropic.com/v1/messages';

async function chat({ settings, model, system, messages, tools, maxTokens = 2048 }) {
  const body = { model, max_tokens: maxTokens, system, messages: toAnthropic(messages) };
  if (tools && tools.length) body.tools = tools; // schematy już w formacie Anthropic

  const res = await fetch(API_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-api-key': (settings.apiKey || '').trim(), 'anthropic-version': '2023-06-01' },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    let msg = 'HTTP ' + res.status;
    try { const j = await res.json(); msg = j?.error?.message || msg; } catch {}
    if (/401|authentication|invalid x-api-key/i.test(msg)) throw new Error('Klucz API Anthropic jest nieprawidłowy (Ustawienia).');
    if (/429|rate|overloaded/i.test(msg)) throw new Error('Za dużo zapytań lub przeciążenie — spróbuj za chwilę.');
    if (/credit|balance/i.test(msg)) throw new Error('Brak środków na koncie Anthropic. Doładuj konto albo przełącz się na Ollamę (za darmo).');
    throw new Error(msg);
  }
  const data = await res.json();
  const content = data.content || [];
  const text = content.filter(b => b.type === 'text').map(b => b.text).join('\n').trim();
  const toolCalls = content.filter(b => b.type === 'tool_use').map(b => ({ id: b.id, name: b.name, input: b.input || {} }));
  const stopReason = data.stop_reason === 'tool_use' ? 'tool_use' : data.stop_reason === 'pause_turn' ? 'pause' : 'end';
  return { text, toolCalls, stopReason };
}

function toAnthropic(messages) {
  const out = [];
  for (const m of messages) {
    if (m.role === 'user') out.push({ role: 'user', content: m.content });
    else if (m.role === 'assistant') {
      const content = [];
      if (m.content) content.push({ type: 'text', text: m.content });
      for (const tc of (m.toolCalls || [])) content.push({ type: 'tool_use', id: tc.id, name: tc.name, input: tc.input || {} });
      if (!content.length) content.push({ type: 'text', text: '…' });
      out.push({ role: 'assistant', content });
    } else if (m.role === 'tool') {
      const content = (m.results || []).map(r => {
        const blocks = [{ type: 'text', text: JSON.stringify(r.output).slice(0, 6000) }];
        if (r.image) blocks.push({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: r.image } });
        return { type: 'tool_result', tool_use_id: r.id, content: blocks, is_error: r.output && r.output.ok === false };
      });
      out.push({ role: 'user', content });
    }
  }
  return out;
}

module.exports = { chat };
