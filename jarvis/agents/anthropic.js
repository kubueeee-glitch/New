'use strict';
/*
 * Cienki klient Claude API (Node fetch — bez CORS, klucz zostaje w procesie
 * głównym). Wzorowany na wywołaniu z HabitFlow (index.html), rozszerzony o
 * narzędzia (tool_use) i wyszukiwanie serwerowe web_search.
 */
const API_URL = 'https://api.anthropic.com/v1/messages';

async function callClaude({ apiKey, model, system, messages, tools, maxTokens = 2048 }) {
  const body = { model, max_tokens: maxTokens, system, messages };
  if (tools && tools.length) body.tools = tools;

  const res = await fetch(API_URL, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify(body)
  });

  if (!res.ok) {
    let msg = 'HTTP ' + res.status;
    try { const j = await res.json(); msg = j?.error?.message || msg; } catch {}
    if (/401|authentication|invalid x-api-key/i.test(msg)) throw new Error('Klucz API Anthropic jest nieprawidłowy (sprawdź w Ustawieniach).');
    if (/429|rate|overloaded/i.test(msg)) throw new Error('Za dużo zapytań lub przeciążenie — spróbuj za chwilę.');
    if (/credit|balance/i.test(msg)) throw new Error('Brak środków na koncie Anthropic.');
    throw new Error(msg);
  }
  return res.json();
}

module.exports = { callClaude };
