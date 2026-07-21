'use strict';
/*
 * runAgent — pojedyncza pętla agentowa (tool-use) niezależna od providera.
 * Używa neutralnego formatu wiadomości i warstwy llm (Anthropic lub Ollama).
 * Neutralne wiadomości:
 *   { role:'user', content:string }
 *   { role:'assistant', content:string, toolCalls:[{id,name,input}] }
 *   { role:'tool', results:[{id,name,output,image?}] }
 */
const llm = require('./llm');

async function runAgent(opts) {
  const { name, model, system, tools, handlers, ctx, abortRef = { stopped: false }, maxSteps = 14, maxTokens = 2048, onStep } = opts;
  let messages = opts.messages.slice();

  ctx.emit('jarvis:agent', { name, status: 'thinking', step: 0 });

  for (let step = 0; step < maxSteps; step++) {
    if (abortRef.stopped) { ctx.emit('jarvis:agent', { name, status: 'stopped' }); return { text: '⏹️ Zatrzymano.', messages, stopped: true }; }

    const resp = await llm.chat(ctx.settings, { model, system, messages, tools, maxTokens });
    messages.push({ role: 'assistant', content: resp.text, toolCalls: resp.toolCalls });

    if (resp.stopReason === 'pause') continue;
    if (resp.stopReason !== 'tool_use' || !resp.toolCalls.length) {
      ctx.emit('jarvis:agent', { name, status: 'done', step: step + 1 });
      return { text: resp.text || '…', messages };
    }

    const results = [];
    for (const tc of resp.toolCalls) {
      if (abortRef.stopped) break;
      const handler = handlers[tc.name];
      ctx.emit('jarvis:agent', { name, status: 'acting', tool: tc.name, step: step + 1 });
      if (onStep) onStep({ tool: tc.name, input: tc.input });
      let output;
      try { output = handler ? await handler(tc.input || {}, ctx) : { ok: false, error: 'Nieznane narzędzie: ' + tc.name }; }
      catch (e) { output = { ok: false, error: (e && e.message) || String(e) }; }
      const image = output && output.__image_base64;
      results.push({ id: tc.id, name: tc.name, output, image });
    }
    messages.push({ role: 'tool', results });
  }

  ctx.emit('jarvis:agent', { name, status: 'done', note: 'limit-kroków' });
  return { text: 'Osiągnięto limit kroków agenta.', messages };
}

module.exports = { runAgent };
