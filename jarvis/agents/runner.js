'use strict';
/*
 * runAgent — pojedyncza pętla agentowa tool_use dla jednego agenta.
 * Obsługuje: wykonywanie narzędzi lokalnych, obrazy w wynikach (wizja),
 * stop_reason 'pause_turn' (długie narzędzia serwerowe), przerwanie (abortRef)
 * i limit kroków. Raportuje status do UI przez ctx.emit('jarvis:agent', ...).
 */
const { callClaude } = require('./anthropic');

async function runAgent(opts) {
  const {
    name, model, system, tools, handlers, ctx, apiKey,
    abortRef = { stopped: false }, maxSteps = 14, maxTokens = 2048,
    onStep
  } = opts;
  let messages = opts.messages.slice();

  ctx.emit('jarvis:agent', { name, status: 'thinking', step: 0 });

  for (let step = 0; step < maxSteps; step++) {
    if (abortRef.stopped) { ctx.emit('jarvis:agent', { name, status: 'stopped' }); return { text: '⏹️ Zatrzymano.', messages, stopped: true }; }

    const resp = await callClaude({ apiKey, model, system, messages, tools, maxTokens });
    messages.push({ role: 'assistant', content: resp.content });

    // stop_reason pause_turn — kontynuuj bez dokładania wyników
    if (resp.stop_reason === 'pause_turn') { continue; }

    if (resp.stop_reason !== 'tool_use') {
      const text = extractText(resp.content);
      ctx.emit('jarvis:agent', { name, status: 'done', step: step + 1 });
      return { text, messages };
    }

    // Wykonaj wszystkie lokalne narzędzia z tej tury
    const toolUses = resp.content.filter(b => b.type === 'tool_use');
    const toolResults = [];
    for (const tu of toolUses) {
      if (abortRef.stopped) break;
      const handler = handlers[tu.name];
      ctx.emit('jarvis:agent', { name, status: 'acting', tool: tu.name, step: step + 1 });
      if (onStep) onStep({ tool: tu.name, input: tu.input });
      let result;
      try {
        result = handler ? await handler(tu.input || {}, ctx) : { ok: false, error: 'Nieznane narzędzie: ' + tu.name };
      } catch (e) {
        result = { ok: false, error: (e && e.message) || String(e) };
      }
      toolResults.push(buildToolResult(tu.id, result));
    }
    messages.push({ role: 'user', content: toolResults });
  }

  ctx.emit('jarvis:agent', { name, status: 'done', note: 'limit-kroków' });
  return { text: 'Osiągnięto limit kroków agenta.', messages };
}

function extractText(content) {
  return (content || []).filter(b => b.type === 'text').map(b => b.text).join('\n').trim() || '…';
}

// Buduje blok tool_result; jeśli wynik zawiera obraz (__image_base64),
// dołącza go jako blok image (dla modelu z wizją).
function buildToolResult(toolUseId, result) {
  const img = result && result.__image_base64;
  const clean = Object.assign({}, result);
  delete clean.__image_base64;
  const content = [{ type: 'text', text: JSON.stringify(clean).slice(0, 6000) }];
  if (img) content.push({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: img } });
  return { type: 'tool_result', tool_use_id: toolUseId, content, is_error: result && result.ok === false };
}

module.exports = { runAgent, extractText };
