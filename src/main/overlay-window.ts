import { BrowserWindow, ipcMain, shell } from 'electron'
import { join } from 'path'
import { is } from '@electron-toolkit/utils'

let overlayWindow: BrowserWindow | null = null

// Registered once at module level: re-creating the overlay (tray reopen after
// Alt+F4) would otherwise throw "second handler" and break resizing for good.
ipcMain.handle('overlay:set-size', (_event, width: number, height: number) => {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    overlayWindow.setSize(width, height)
  }
})

function hardenOverlayNavigation(contents: Electron.WebContents): void {
  contents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) {
      void shell.openExternal(url)
    }
    return { action: 'deny' }
  })
  contents.on('will-navigate', (event, url) => {
    if (!/^file:|^data:|^about:/i.test(url)) {
      event.preventDefault()
    }
  })
}

export function createOverlayWindow(): BrowserWindow {
  overlayWindow = new BrowserWindow({
    width: 320,
    height: 250,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: true,
    skipTaskbar: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      sandbox: true
    }
  })
  hardenOverlayNavigation(overlayWindow.webContents)

  // Set initial position if saved (defaulting for now)
  overlayWindow.setPosition(40, 40)

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    overlayWindow.loadURL(`${process.env['ELECTRON_RENDERER_URL']}#/overlay-display`)
  } else {
    overlayWindow.loadFile(join(__dirname, '../renderer/index.html'), {
      hash: 'overlay-display'
    })
  }

  overlayWindow.on('closed', () => {
    overlayWindow = null
  })

  return overlayWindow
}

export function toggleOverlay(visible: boolean) {
  if (visible) {
    if (!overlayWindow) {
      createOverlayWindow()
    } else {
      overlayWindow.show()
    }
  } else {
    overlayWindow?.hide()
  }
}

export function getOverlayWindow() {
  return overlayWindow
}
