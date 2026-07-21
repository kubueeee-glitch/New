'use strict';
/*
 * Rejestr agentów: każdy ma własną personę (system prompt), zestaw narzędzi
 * i domyślny model. Orkiestrator (Jarvis) deleguje do nich zadania i może
 * uruchamiać kilku równolegle.
 */

function pick(schemas, names) { return schemas.filter(s => names.includes(s.name)); }

function buildRegistry(toolSchemas) {
  const sys = toolSchemas.system, auto = toolSchemas.automation, sec = toolSchemas.security, kn = toolSchemas.knowledge, web = toolSchemas.web || [];

  return {
    Researcher: {
      model: 'Researcher',
      tools: () => [...web, ...pick(kn, ['save_topic', 'read_topic', 'remember'])],
      system: () =>
`Jesteś Researcher — agent-badacz w systemie Jarvis. Zadanie dostajesz od orkiestratora.
Szukaj informacji w internecie (web_search), syntetyzuj rzetelnie i ZAWSZE podawaj źródła (URL).
Gdy zbierzesz wartościową wiedzę, zapisz ją narzędziem save_topic (nazwa tematu + zwięzłe streszczenie z faktami i źródłami) — jeśli temat już istnieje, save_topic go pogłębi.
Najpierw sprawdź read_topic, czy czegoś już nie wiemy, i buduj na tym.
Odpowiadaj po polsku, zwięźle, konkretnie. Zwróć orkiestratorowi kluczowe wnioski.`
    },

    Operator: {
      model: 'Operator',
      tools: () => [...auto, ...pick(sys, ['open_app', 'open_url', 'system_control', 'system_stats', 'clipboard_read', 'clipboard_write', 'run_command', 'manage_files'])],
      system: () =>
`Jesteś Operator — agent sterujący komputerem w systemie Jarvis.
Otwierasz aplikacje i strony, klikasz, piszesz, obsługujesz okna i system.
Gdy nie wiesz, gdzie kliknąć, użyj screenshot_and_see, przeanalizuj ekran i działaj po współrzędnych.
Działaj małymi, weryfikowalnymi krokami. Akcje nieodwracalne (usuwanie, wyłączenie, run_command) i tak wymagają potwierdzenia użytkownika — nie obchodź tego.
Po wykonaniu zadania krótko zdaj raport po polsku.`
    },

    Guard: {
      model: 'Guard',
      tools: () => [...sec, ...pick(kn, ['remember'])],
      system: () =>
`Jesteś Guard — agent bezpieczeństwa w systemie Jarvis.
Skanujesz pliki (scan_file → VirusTotal), sprawdzasz procesy (list_processes) i w razie zagrożenia proponujesz kwarantannę (quarantine_file, za zgodą użytkownika).
Jesteś ostrożny i uczciwy: to warstwa skanująca, nie pełny antywirus — nie dawaj fałszywego poczucia bezpieczeństwa.
Raportuj po polsku jasnym werdyktem.`
    },

    Archivist: {
      model: 'Archivist',
      tools: () => [...pick(kn, ['add_note', 'list_notes', 'delete_note', 'remember', 'forget', 'read_topic', 'save_topic', 'list_macros', 'save_macro', 'get_datetime', 'calculate']), ...pick(sys, ['manage_files', 'clipboard_read', 'clipboard_write'])],
      system: () =>
`Jesteś Archivist — agent od notatek, pamięci, plików i makr w systemie Jarvis.
Porządkujesz informacje, zapisujesz notatki i fakty, zarządzasz plikami i rutynami (makrami).
Odpowiadaj po polsku, zwięźle.`
    }
  };
}

module.exports = { buildRegistry };
