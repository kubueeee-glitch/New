'use strict';
/*
 * Orchestrator (Jarvis) — rozmawia z użytkownikiem i deleguje pracę do
 * wyspecjalizowanych agentów. dispatch_agent uruchamia agenta NIEBLOKUJĄCO
 * (zwraca task_id od razu), więc kilku agentów biegnie równolegle;
 * collect_results czeka na wskazane zadania i zbiera wyniki.
 */
const { runAgent, extractText } = require('./runner');
const { buildRegistry } = require('./registry');
const knowledge = require('../tools/knowledge');

const DISPATCH_SCHEMAS = [
  {
    name: 'dispatch_agent',
    description: 'Uruchamia wyspecjalizowanego agenta do wykonania zadania. NIE blokuje — zwraca task_id natychmiast, więc możesz odpalić kilku agentów naraz (równolegle), a potem zebrać wyniki przez collect_results. Agenci: Researcher (research w internecie + baza wiedzy), Operator (sterowanie komputerem: aplikacje, klikanie, pisanie, pliki, system), Guard (skanowanie bezpieczeństwa, procesy, kwarantanna), Archivist (notatki, pamięć, pliki, makra).',
    input_schema: {
      type: 'object',
      properties: {
        agent: { type: 'string', enum: ['Researcher', 'Operator', 'Guard', 'Archivist'] },
        task: { type: 'string', description: 'Dokładne, samodzielne zadanie dla agenta (po polsku).' }
      },
      required: ['agent', 'task']
    }
  },
  {
    name: 'collect_results',
    description: 'Czeka na zakończenie agentów i zwraca ich wyniki. Podaj task_id z dispatch_agent; bez argumentu czeka na wszystkich aktywnych. Wywołaj PO odpaleniu wszystkich potrzebnych agentów, żeby wykorzystać równoległość.',
    input_schema: {
      type: 'object',
      properties: { task_ids: { type: 'array', items: { type: 'string' } } }
    }
  }
];

class Orchestrator {
  constructor({ ctx, handlers, toolSchemas }) {
    this.ctx = ctx;
    this.handlers = handlers;
    this.toolSchemas = toolSchemas;
    this.abortRef = { stopped: false };
  }

  stop() { this.abortRef.stopped = true; }

  buildSystemPrompt() {
    const s = this.ctx.settings;
    const mem = this.ctx.store.memory();
    const topics = knowledge.listTopics(this.ctx.store);
    const now = new Date().toLocaleString('pl-PL');
    const memBlock = mem.length ? mem.map(m => `- ${m.text}`).join('\n') : '(pusta)';
    const knowBlock = topics.length ? topics.map(t => `- ${t.name}: ${t.summary || ''}`).join('\n') : '(brak zapisanych tematów)';
    return `Nazywasz się Jarvis — osobisty asystent AI ${s.userName}. Mówisz po polsku, zwracasz się „${s.userName}".
Osobowość: rzeczowy, lojalny, spokojny, z nutą suchego brytyjskiego humoru. Konkretny, bez lania wody. Emoji oszczędnie.

Jesteś ORKIESTRATOREM zespołu agentów. Masz dwie drogi:
1. Proste sprawy (data, obliczenia, pamięć, notatki, krótka rozmowa) — załatw sam swoimi narzędziami lub po prostu odpowiedz.
2. Zadania wymagające działania — DELEGUJ do agentów przez dispatch_agent. Jeśli użytkownik prosi o kilka rzeczy naraz, odpal kilku agentów JEDNOCZEŚNIE (kilka wywołań dispatch_agent), a potem collect_results — pracują równolegle.

Agenci: Researcher (internet + wiedza), Operator (sterowanie komputerem), Guard (bezpieczeństwo/skan), Archivist (notatki/pamięć/pliki/makra).
Po zebraniu wyników zsyntetyzuj krótki, naturalny meldunek dla użytkownika.

Zasady: akcje nieodwracalne (usuwanie, wyłączenie komputera, polecenia powłoki) wymagają potwierdzenia — narzędzia same o nie proszą, nie obchodź tego. Bądź uczciwy o ograniczeniach.

Aktualny czas: ${now}
Pamięć długoterminowa o użytkowniku:
${memBlock}

Tematy w bazie wiedzy (możesz zlecić Researcherowi ich pogłębienie):
${knowBlock}`;
  }

  jarvisTools() {
    const kn = this.toolSchemas.knowledge;
    const instant = kn.filter(t => ['get_datetime', 'calculate', 'remember', 'forget', 'add_note', 'list_notes'].includes(t.name));
    return [...DISPATCH_SCHEMAS, ...instant];
  }

  makeHandlers() {
    const ctx = this.ctx;
    const s = ctx.settings;
    const registry = buildRegistry(this.toolSchemas);
    const models = s.models || {};
    const apiKey = s.apiKey.trim();
    const activeTasks = new Map();
    const abortRef = this.abortRef;
    const allHandlers = this.handlers;
    const actions = this._actions;

    const dispatch = async (input) => {
      const def = registry[input.agent];
      if (!def) return { ok: false, error: 'Nieznany agent: ' + input.agent };
      const id = 't_' + Date.now() + Math.random().toString(36).slice(2, 6);
      ctx.emit('jarvis:agent', { name: input.agent, status: 'working', task: input.task });
      actions.push({ agent: input.agent, task: input.task });
      const promise = runAgent({
        name: input.agent,
        model: models[def.model] || models[input.agent] || 'claude-sonnet-5',
        system: def.system(ctx),
        tools: def.tools(),
        handlers: allHandlers,
        ctx, apiKey, abortRef, maxSteps: 12
      }).then(r => ({ id, agent: input.agent, task: input.task, result: r.text }))
        .catch(e => ({ id, agent: input.agent, task: input.task, error: e.message }));
      activeTasks.set(id, { promise, agent: input.agent, task: input.task });
      return { ok: true, task_id: id, message: `Uruchomiono agenta ${input.agent}.` };
    };

    const collect = async (input) => {
      let ids = (input && input.task_ids && input.task_ids.length) ? input.task_ids : [...activeTasks.keys()];
      ids = ids.filter(id => activeTasks.has(id));
      if (!ids.length) return { ok: true, results: [], message: 'Brak aktywnych agentów.' };
      const results = await Promise.all(ids.map(id => activeTasks.get(id).promise));
      for (const id of ids) {
        const t = activeTasks.get(id);
        if (t) { ctx.emit('jarvis:agent', { name: t.agent, status: 'done' }); activeTasks.delete(id); }
      }
      return { ok: true, results };
    };

    // narzędzia natychmiastowe Jarvisa (bez delegacji)
    const instant = {};
    for (const nm of ['get_datetime', 'calculate', 'remember', 'forget', 'add_note', 'list_notes']) {
      if (allHandlers[nm]) instant[nm] = allHandlers[nm];
    }
    return Object.assign({ dispatch_agent: dispatch, collect_results: collect }, instant);
  }

  async run(userText, history) {
    this.abortRef.stopped = false;
    this._actions = [];
    const s = this.ctx.settings;
    const apiKey = s.apiKey.trim();
    const messages = mapHistory(history);
    messages.push({ role: 'user', content: userText });

    this.ctx.emit('jarvis:agent', { name: 'Jarvis', status: 'thinking' });
    const res = await runAgent({
      name: 'Jarvis',
      model: (s.models && s.models.orchestrator) || 'claude-opus-4-8',
      system: this.buildSystemPrompt(),
      tools: this.jarvisTools(),
      handlers: this.makeHandlers(),
      ctx: this.ctx,
      apiKey,
      abortRef: this.abortRef,
      maxSteps: 16,
      maxTokens: 2048
    });
    this.ctx.emit('jarvis:agent', { name: 'Jarvis', status: 'idle' });
    return { reply: res.text, actions: this._actions };
  }
}

function mapHistory(history) {
  return (history || []).slice(-16).map(m => ({
    role: m.role === 'ai' || m.role === 'assistant' ? 'assistant' : 'user',
    content: typeof m.content === 'string' ? m.content : String(m.content || '')
  }));
}

module.exports = { Orchestrator };
