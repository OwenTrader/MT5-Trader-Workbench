import { app, shell, BrowserWindow, ipcMain, Tray, Menu, nativeImage, dialog, protocol } from 'electron'
import { join } from 'path'
import { mkdir, readFile, access, copyFile, writeFile } from 'fs/promises'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import { MainLocale, tMain } from './i18n'
import {
  isBackendHealthy,
  startPythonService,
  stopPythonService,
  waitForBackendHealth,
  killBackendOnPort,
  markBackendStartupFailure,
  markBackendHealthyReuse,
  getBackendStartupDiagnostics,
} from './python-service'
import { toggleOverlay, getOverlayWindow } from './overlay-window'
import { AWAKENING_DOCS } from './awakening-data'

const isSingleInstance = app.requestSingleInstanceLock()

if (!isSingleInstance) {
  app.exit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
  })

  let mainWindow: BrowserWindow | null = null
  let tray: Tray | null = null
  let isQuitting = false
  let currentLanguage: MainLocale = 'zh-CN'

  function getPackagedDefaultSettingsPath(): string {
    return join(process.resourcesPath, 'storage', 'settings.json')
  }

  function getUserSettingsPath(): string {
    return join(app.getPath('userData'), 'storage', 'settings.json')
  }

  function getDevelopmentSettingsPath(): string {
    return join(app.getAppPath(), 'storage', 'settings.local.json')
  }

  function getDevelopmentDefaultSettingsPath(): string {
    return join(app.getAppPath(), 'storage', 'settings.default.json')
  }

  function getUserGuideFileName(locale: MainLocale): string {
    return locale === 'en' ? 'user-guide.en.html' : 'user-guide.zh-CN.html'
  }

  function getPackagedUserGuidePath(locale: MainLocale): string {
    return join(process.resourcesPath, 'help', getUserGuideFileName(locale))
  }

  function getDevelopmentUserGuidePath(locale: MainLocale): string {
    return join(app.getAppPath(), 'resources', 'help', getUserGuideFileName(locale))
  }

  function getUserGuidePath(locale: MainLocale): string {
    return app.isPackaged
      ? getPackagedUserGuidePath(locale)
      : getDevelopmentUserGuidePath(locale)
  }

  function getUserGuideSeenPath(): string {
    return join(app.getPath('userData'), 'storage', 'user-guide-seen.json')
  }

  async function pathExists(target: string): Promise<boolean> {
    try {
      await access(target)
      return true
    } catch {
      return false
    }
  }

  async function ensureSettingsFile(): Promise<string> {
    if (!app.isPackaged) {
      const localPath = getDevelopmentSettingsPath()
      if (await pathExists(localPath)) {
        return localPath
      }

      return getDevelopmentDefaultSettingsPath()
    }

    const userSettingsPath = getUserSettingsPath()
    if (await pathExists(userSettingsPath)) {
      return userSettingsPath
    }

    await mkdir(join(app.getPath('userData'), 'storage'), { recursive: true })
    await copyFile(getPackagedDefaultSettingsPath(), userSettingsPath)
    return userSettingsPath
  }

  async function getSettingsPath(): Promise<string> {
    return ensureSettingsFile()
  }

  async function getCurrentLanguage(): Promise<MainLocale> {
    try {
      const raw = await readFile(await getSettingsPath(), 'utf-8')
      const parsed = JSON.parse(raw) as { language?: string }
      return parsed.language === 'en' ? 'en' : 'zh-CN'
    } catch {
      return 'zh-CN'
    }
  }

  async function refreshLocalizedChrome(): Promise<void> {
    currentLanguage = await getCurrentLanguage()
    mainWindow?.setTitle(tMain(currentLanguage, 'window.title'))

    if (tray) {
      tray.setToolTip(tMain(currentLanguage, 'tray.tooltip'))
    }

    updateTrayMenu()
  }

  async function openUserGuide(locale: MainLocale = currentLanguage): Promise<void> {
    const guidePath = getUserGuidePath(locale)
    if (!(await pathExists(guidePath))) {
      throw new Error(`User guide not found: ${guidePath}`)
    }

    const result = await shell.openPath(guidePath)
    if (result) {
      throw new Error(result)
    }
  }

  async function maybeOpenUserGuideOnFirstLaunch(): Promise<void> {
    if (!app.isPackaged) {
      return
    }

    const seenPath = getUserGuideSeenPath()
    if (await pathExists(seenPath)) {
      return
    }

    await mkdir(join(app.getPath('userData'), 'storage'), { recursive: true })

    try {
      await openUserGuide(currentLanguage)
      await writeFile(
        seenPath,
        `${JSON.stringify({ openedAt: new Date().toISOString(), locale: currentLanguage }, null, 2)}\n`,
        'utf-8'
      )
    } catch (err) {
      console.error('Failed to open user guide on first launch:', err)
    }
  }

  function getAppIconPath(): string {
    return app.isPackaged
      ? join(process.resourcesPath, 'tray-icon.png')
      : join(app.getAppPath(), 'resources', 'tray-icon.png')
  }

  function updateTrayMenu(): void {
    if (!tray) return
    
    const isOverlayVisible = getOverlayWindow()?.isVisible() ?? false
    
    const contextMenu = Menu.buildFromTemplate([
      { label: tMain(currentLanguage, 'tray.showWindow'), click: () => {
        if (mainWindow) {
          mainWindow.show()
          mainWindow.focus()
        }
      }},
      { 
        label: isOverlayVisible ? tMain(currentLanguage, 'tray.hideOverlay') : tMain(currentLanguage, 'tray.showOverlay'), 
        click: () => {
          app.emit('tray:toggle-overlay')
        }
      },
      { type: 'separator' },
      { label: tMain(currentLanguage, 'tray.quit'), click: () => {
        isQuitting = true
        stopPythonService()
        app.quit()
      }}
    ])
    
    tray.setContextMenu(contextMenu)
  }

  function createTray(): void {
    try {
      if (tray) {
        tray.destroy()
        tray = null
      }
      
      const iconPath = getAppIconPath()
      const icon = nativeImage.createFromPath(iconPath)
      
      if (icon.isEmpty()) {
        console.error(`Tray icon not found at: ${iconPath}. Please ensure 32x32 PNG file exists.`)
        const fallbackIcon = nativeImage.createFromDataURL('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAEUlEQVR42mP8z8BQz0ADMNQCAB6+AgBpgNo7AAAAAElFTkSuQmCC')
        tray = new Tray(fallbackIcon)
      } else {
        tray = new Tray(icon)
      }

      updateTrayMenu()
      
      tray.setToolTip(tMain(currentLanguage, 'tray.tooltip'))
      
      tray.on('double-click', () => {
        if (mainWindow) {
          mainWindow.show()
          mainWindow.focus()
        }
      })
    } catch (err) {
      console.error('Failed to create tray:', err)
    }
  }

  async function createWindow() {
    if (mainWindow) return
    
    Menu.setApplicationMenu(null)
    createTray()
    
    app.on('browser-window-created', (_, window) => {
      optimizer.watchWindowShortcuts(window)
    })

    const setOverlayVisible = (visible: boolean) => {
      toggleOverlay(visible)
      mainWindow?.webContents.send('overlay:visibility-changed', visible)
      updateTrayMenu()
    }

    app.on('tray:toggle-overlay', () => {
      const isVisible = getOverlayWindow()?.isVisible() ?? false
      setOverlayVisible(!isVisible)
    })

    ipcMain.handle('overlay:toggle-visible', (_event, visible: boolean) => {
      setOverlayVisible(visible)
    })

    ipcMain.handle('overlay:is-visible', () => {
      const win = getOverlayWindow()
      return win !== null && win.isVisible()
    })

    ipcMain.handle('settings:notify-update', async () => {
      BrowserWindow.getAllWindows().forEach((win) => {
        win.webContents.send('settings:changed')
      })

      await refreshLocalizedChrome()
    })

    ipcMain.handle('dialog:openFile', async (_event, options) => {
      const result = await dialog.showOpenDialog(mainWindow!, {
        properties: ['openFile'],
        ...options
      })
      if (!result.canceled && result.filePaths.length > 0) {
        return result.filePaths[0]
      }
      return null
    })

    ipcMain.handle('app:get-resources-path', () => {
      return app.isPackaged
        ? process.resourcesPath
        : join(app.getAppPath(), 'resources')
    })

    ipcMain.handle('app:get-backend-startup-diagnostics', () => {
      return getBackendStartupDiagnostics()
    })

    ipcMain.handle('app:openExternal', async (_event, target: string) => {
      await shell.openExternal(target)
    })

    ipcMain.handle('app:open-user-guide', async (_event, locale?: string) => {
      const targetLocale: MainLocale = locale === 'en' ? 'en' : 'zh-CN'
      await openUserGuide(targetLocale)
    })

    ipcMain.handle('awakening:list-files', async () => {
      try {
        return AWAKENING_DOCS.map(doc => doc.fileName)
      } catch (err) {
        console.error('Failed to load awakening data:', err)
        return []
      }
    })

    ipcMain.handle('awakening:read-file', async (_event, fileName: string) => {
      try {
        const doc = AWAKENING_DOCS.find(d => d.fileName === fileName)
        if (doc) {
          return doc.content
        }
        throw new Error(`File not found in internal storage: ${fileName}`)
      } catch (err) {
        console.error('Failed to read awakening file:', err)
        throw err
      }
    })

    try {
      if (is.dev) {
        stopPythonService()
        killBackendOnPort()
      }

      const backendAlreadyRunning = await isBackendHealthy()
      const backendProcess = backendAlreadyRunning ? null : startPythonService()

      if (backendAlreadyRunning) {
        markBackendHealthyReuse()
        console.log('Backend already healthy on port 8765, reusing existing service')
      }

      await waitForBackendHealth({ childProcess: backendProcess })
    } catch (err) {
      markBackendStartupFailure(err)
      console.error('Failed to start backend:', err)
    }

    mainWindow = new BrowserWindow({
      width: 1440,
      height: 900,
      icon: getAppIconPath(),
      webPreferences: {
        preload: join(__dirname, '../preload/index.js'),
      },
    })
    await refreshLocalizedChrome()
    
    if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
      mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
    } else {
      mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
    }

    mainWindow.webContents.once('did-finish-load', () => {
      void maybeOpenUserGuideOnFirstLaunch()
    })

    mainWindow.on('close', (event) => {
      if (!isQuitting) {
        event.preventDefault()
        mainWindow?.hide()
      }
      return false
    })

    setTimeout(() => setOverlayVisible(true), 1500)
  }

  app.whenReady().then(() => {
    electronApp.setAppUserModelId('com.tradingtool.elec')
    createWindow()
  })

  app.on('window-all-closed', () => {
    stopPythonService()
    if (process.platform !== 'darwin') {
      app.quit()
    }
  })

  app.on('before-quit', () => {
    isQuitting = true
    stopPythonService()
  })

  app.on('will-quit', () => {
    stopPythonService()
    if (tray) {
      try {
        tray.destroy()
      } catch (e) {
      }
      tray = null
    }
  })

  app.whenReady().then(() => {
    protocol.registerFileProtocol('local-file', (request, callback) => {
      const url = request.url.replace(/^local-file:\/\//, '')
      try {
        return callback(decodeURIComponent(url))
      } catch (error) {
        console.error(error)
      }
    })
  })
}
