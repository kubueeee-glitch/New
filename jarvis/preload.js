'use strict';
const { contextBridge, ipcRenderer } = require('electron');

// Bezpieczny, zawężony mostek — renderer nie ma dostępu do Node/fs bezpośrednio.
contextBridge.exposeInMainWorld('jarvis', {
  // rozmowa
  send: (text, history) => ipcRenderer.invoke('jarvis:send', { text, history }),
  stop: () => ipcRenderer.send('jarvis:stop'),

  // zdarzenia z procesu głównego → UI
  on: (channel, cb) => {
    const allowed = ['jarvis:event', 'jarvis:confirm', 'jarvis:stop', 'jarvis:stopped', 'jarvis:agent', 'jarvis:speak'];
    if (!allowed.includes(channel)) return () => {};
    const listener = (_e, payload) => cb(payload);
    ipcRenderer.on(channel, listener);
    return () => ipcRenderer.removeListener(channel, listener);
  },
  confirmResponse: (id, approved) => ipcRenderer.send('jarvis:confirm-response', { id, approved }),

  // ustawienia i panele
  getSettings: () => ipcRenderer.invoke('settings:get'),
  setSettings: (s) => ipcRenderer.invoke('settings:set', s),
  getMemory: () => ipcRenderer.invoke('memory:get'),
  deleteMemory: (id) => ipcRenderer.invoke('memory:delete', id),
  getNotes: () => ipcRenderer.invoke('notes:get'),
  getLog: () => ipcRenderer.invoke('log:get'),
  listKnowledge: () => ipcRenderer.invoke('knowledge:list'),
  getKnowledge: (name) => ipcRenderer.invoke('knowledge:get', name),
  deleteKnowledge: (name) => ipcRenderer.invoke('knowledge:delete', name),
  securityRecent: () => ipcRenderer.invoke('security:recent'),
  quarantineList: () => ipcRenderer.invoke('security:quarantine-list'),

  // sterowanie oknem
  winMinimize: () => ipcRenderer.send('win:minimize'),
  winClose: () => ipcRenderer.send('win:close'),
  winToggleTop: (on) => ipcRenderer.send('win:toggle-top', on)
});
