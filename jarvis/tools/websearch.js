'use strict';
/*
 * Darmowe wyszukiwanie w internecie przez DuckDuckGo (HTML, bez klucza API).
 * Wspólne dla wszystkich providerów — dzięki temu research działa też z Ollamą
 * bez płatnego narzędzia serwerowego. Zwraca tytuły, URL-e i skróty wyników.
 */

function strip(html) {
  return String(html || '')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ').trim();
}

async function webSearch(input) {
  const q = (input.query || '').trim();
  if (!q) return { ok: false, error: 'Podaj zapytanie.' };
  try {
    const res = await fetch('https://html.duckduckgo.com/html/?q=' + encodeURIComponent(q), {
      method: 'POST',
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'content-type': 'application/x-www-form-urlencoded' },
      body: 'q=' + encodeURIComponent(q)
    });
    if (!res.ok) return { ok: false, error: 'Wyszukiwarka HTTP ' + res.status };
    const html = await res.text();
    const results = [];
    const re = /<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/g;
    let m;
    while ((m = re.exec(html)) && results.length < 6) {
      let url = m[1];
      const ud = url.match(/[?&]uddg=([^&]+)/);
      if (ud) { try { url = decodeURIComponent(ud[1]); } catch {} }
      results.push({ title: strip(m[2]), url, snippet: '' });
    }
    const sre = /class="result__snippet"[^>]*>([\s\S]*?)<\/a>/g;
    let s, i = 0;
    while ((s = sre.exec(html)) && i < results.length) { results[i].snippet = strip(s[1]).slice(0, 300); i++; }
    if (!results.length) return { ok: true, results: [], message: 'Brak wyników (lub zmienił się format wyszukiwarki).' };
    return { ok: true, query: q, results };
  } catch (e) {
    return { ok: false, error: 'Błąd wyszukiwania: ' + e.message + ' (wymaga internetu).' };
  }
}

const schemas = [
  { name: 'web_search', description: 'Wyszukuje informacje w internecie (DuckDuckGo, za darmo). Zwraca tytuły, adresy URL i skróty. Używaj do researchu, a wyniki cytuj z URL-ami.', input_schema: { type: 'object', properties: { query: { type: 'string' } }, required: ['query'] } }
];
const handlers = { web_search: (input) => webSearch(input) };

module.exports = { schemas, handlers };
