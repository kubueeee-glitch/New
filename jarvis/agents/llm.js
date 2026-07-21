'use strict';
/* Wybór providera na podstawie ustawień. Jeden punkt wejścia dla runnera. */
const anthropic = require('./providers/anthropic');
const ollama = require('./providers/ollama');

function providerFor(settings) {
  return (settings.provider === 'ollama') ? ollama : anthropic;
}

async function chat(settings, opts) {
  const p = providerFor(settings);
  return p.chat(Object.assign({ settings }, opts));
}

module.exports = { chat, providerFor };
