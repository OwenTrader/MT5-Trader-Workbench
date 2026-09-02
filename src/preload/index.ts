import { contextBridge, ipcRenderer } from 'electron'

// Only these channels may be invoked / listened to from the renderer. The
// previous implementation exposed the full ipcRenderer, which meant any XSS in
// the renderer could call any main-process handler. Now the surface is fixed.
const INVOKE_WHITELIST = new Set<string>([
  'overlay:is-visible',
  'overlay:toggle-visible',
  'overlay:set-size',
  'dialog:openFile',
  'app:get-resources-path',
  'app:get-backend-startup-diagnostics',
  'app:openExternal',
  'app:open-user-guide',
  'settings:notify-update',
  'app:register-local-root',
])

const ON_WHITELIST = new Set<string>([
  'settings:changed',
  'overlay:visibility-changed',
])

function safeInvoke(channel: string, ...args: unknown[]): Promise<unknown> {
  if (!INVOKE_WHITELIST.has(channel)) {
    return Promise.reject(new Error(`Blocked IPC invoke to disallowed channel: ${channel}`))
  }
  return ipcRenderer.invoke(channel, ...args)
}

function safeOn(
  channel: string,
  func: (...args: unknown[]) => void,
): () => void {
  if (!ON_WHITELIST.has(channel)) {
    console.error(`Blocked IPC subscription to disallowed channel: ${channel}`)
    return () => {}
  }
  const subscription = (_event: unknown, ...args: unknown[]) => func(...args)
  ipcRenderer.on(channel, subscription)
  return () => ipcRenderer.removeListener(channel, subscription)
}

function safeRemoveListener(channel: string, func: (...args: unknown[]) => void): void {
  if (!ON_WHITELIST.has(channel)) return
  ipcRenderer.removeListener(channel, func)
}

contextBridge.exposeInMainWorld('electron', {
  ipcRenderer: {
    invoke: safeInvoke,
    on: safeOn,
    removeListener: safeRemoveListener,
  },
})
