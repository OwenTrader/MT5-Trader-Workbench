import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electron', {
  openExternal: (target: string) => ipcRenderer.invoke('app:openExternal', target),
  openUserGuide: (locale?: string) => ipcRenderer.invoke('app:open-user-guide', locale),
  getBackendStartupDiagnostics: () => ipcRenderer.invoke('app:get-backend-startup-diagnostics'),
  ipcRenderer: {
    send: (channel: string, data: any) => ipcRenderer.send(channel, data),
    invoke: (channel: string, ...args: any[]) => ipcRenderer.invoke(channel, ...args),
    on: (channel: string, func: (...args: any[]) => void) => {
      const subscription = (_event: any, ...args: any[]) => func(...args)
      ipcRenderer.on(channel, subscription)
      return () => ipcRenderer.removeListener(channel, subscription)
    },
    removeListener: (channel: string, func: (...args: any[]) => void) => {
      ipcRenderer.removeListener(channel, func)
    }
  },
})
