import { app, shell, BrowserWindow, ipcMain, Tray, Menu, nativeImage, dialog, protocol } from 'electron'
import { join, isAbsolute, resolve, dirname } from 'path'
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
import { createShutdownController } from './shutdown-coordinator'

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
  let currentLanguage: MainLocale = 'zh-CN'

  // Roots the `local-file://` protocol is permitted to serve from. The renderer
  // registers extra roots (e.g. the user-chosen alert-sound directory) after
  // loading settings, preventing arbitrary local-file reads from XSS.
  const allowedLocalRoots = new Set<string>([
    app.getPath('userData'),
    app.isPackaged ? process.resourcesPath : app.getAppPath(),
  ])

  const logShutdown = (message: string): void => {
    console.log(`[shutdown] ${message}`)
  }

  // Window navigation hardening: the app only ever loads local content, so any
  // window.open or in-page navigation to a remote URL is denied; genuine http
  // links are routed through the validated openExternal path instead.
  const hardenWindowNavigation = (contents: Electron.WebContents): void => {
    contents.setWindowOpenHandler(({ url }) => {
      if (/^https?:\/\//i.test(url)) {
        void shell.openExternal(url)
      } else {
        console.error(`Blocked window.open to non-http target: ${url}`)
      }
      return { action: 'deny' }
    })
    contents.on('will-navigate', (event, url) => {
      if (!/^file:|^data:|^about:/i.test(url)) {
        console.error(`Blocked navigation to: ${url}`)
        event.preventDefault()
      }
    })
  }

  const shutdownController = createShutdownController({
    cleanup: async (reason) => {
      await stopPythonService({ killPort: true, reason })
    },
    resumeQuit: () => {
      app.quit()
    },
    log: logShutdown
  })

  const getPackagedDefaultSettingsPath = (): string => {
    return join(process.resourcesPath, 'storage', 'settings.json')
  }

  const getUserSettingsPath = (): string => {
    return join(app.getPath('userData'), 'storage', 'settings.json')
  }

  const getDevelopmentSettingsPath = (): string => {
    return join(app.getAppPath(), 'storage', 'settings.local.json')
  }

  const getDevelopmentDefaultSettingsPath = (): string => {
    return join(app.getAppPath(), 'storage', 'settings.default.json')
  }

  const getUserGuideFileName = (locale: MainLocale): string => {
    return locale === 'en' ? 'user-guide.en.html' : 'user-guide.zh-CN.html'
  }

  const getPackagedUserGuidePath = (locale: MainLocale): string => {
    return join(process.resourcesPath, 'help', getUserGuideFileName(locale))
  }

  const getDevelopmentUserGuidePath = (locale: MainLocale): string => {
    return join(app.getAppPath(), 'resources', 'help', getUserGuideFileName(locale))
  }

  const getUserGuidePath = (locale: MainLocale): string => {
    return app.isPackaged
      ? getPackagedUserGuidePath(locale)
      : getDevelopmentUserGuidePath(locale)
  }

  const getUserGuideSeenPath = (): string => {
    return join(app.getPath('userData'), 'storage', 'user-guide-seen.json')
  }

  const pathExists = async (target: string): Promise<boolean> => {
    try {
      await access(target)
      return true
    } catch {
      return false
    }
  }

  const ensureSettingsFile = async (): Promise<string> => {
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

  const getSettingsPath = async (): Promise<string> => {
    return ensureSettingsFile()
  }

  const getCurrentLanguage = async (): Promise<MainLocale> => {
    try {
      const raw = await readFile(await getSettingsPath(), 'utf-8')
      const parsed = JSON.parse(raw) as { language?: string }
      return parsed.language === 'en' ? 'en' : 'zh-CN'
    } catch {
      return 'zh-CN'
    }
  }

  const refreshLocalizedChrome = async (): Promise<void> => {
    currentLanguage = await getCurrentLanguage()
    mainWindow?.setTitle(tMain(currentLanguage, 'window.title'))

    if (tray) {
      tray.setToolTip(tMain(currentLanguage, 'tray.tooltip'))
    }

    updateTrayMenu()
  }

  const openUserGuide = async (locale: MainLocale = currentLanguage): Promise<void> => {
    const guidePath = getUserGuidePath(locale)
    if (!(await pathExists(guidePath))) {
      throw new Error(`User guide not found: ${guidePath}`)
    }

    const result = await shell.openPath(guidePath)
    if (result) {
      throw new Error(result)
    }
  }

  const maybeOpenUserGuideOnFirstLaunch = async (): Promise<void> => {
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

  const getAppIconPath = (): string => {
    return app.isPackaged
      ? join(process.resourcesPath, 'tray-icon.png')
      : join(app.getAppPath(), 'resources', 'tray-icon.png')
  }

  const updateTrayMenu = (): void => {
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
        shutdownController.markQuitRequested('tray-menu')
        void shutdownController.beginCleanup('tray-menu')
        app.quit()
      }}
    ])
    
    tray.setContextMenu(contextMenu)
  }

  const createTray = (): void => {
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

  const destroyTray = (): void => {
    if (!tray) {
      return
    }

    try {
      tray.destroy()
    } catch (error) {
      console.error('Failed to destroy tray:', error)
    }

    tray = null
  }

  const createWindow = async () => {
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

    // Custom app-level event (emitted from the tray); not in Electron's typed
    // event map, hence the cast.
    ;(app as unknown as NodeJS.EventEmitter).on('tray:toggle-overlay', () => {
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
      // Only remote http(s) URLs may be handed to the OS; anything else
      // (file://, smb://, custom protocols) could execute local content.
      if (typeof target !== 'string' || !/^https?:\/\//i.test(target)) {
        console.error(`openExternal blocked non-http(s) target: ${target}`)
        return
      }
      await shell.openExternal(target)
    })

    ipcMain.handle('app:open-user-guide', async (_event, locale?: string) => {
      const targetLocale: MainLocale = locale === 'en' ? 'en' : 'zh-CN'
      await openUserGuide(targetLocale)
    })

    ipcMain.handle('app:register-local-root', (_event, root: string) => {
      // The only legitimate use is exposing a user-chosen alert sound, so the
      // renderer may register the *directory of an audio file* -- nothing else.
      // Without this check any string would unlock local-file reads on it.
      if (typeof root !== 'string' || !root) {
        return
      }
      if (!/\.(mp3|wav|ogg|m4a|flac|aac)$/i.test(root)) {
        console.error(`register-local-root blocked non-audio path: ${root}`)
        return
      }
      allowedLocalRoots.add(dirname(resolve(root)))
    })

    // Create the window immediately so the user sees the UI without waiting for
    // the (potentially slow) backend / MT5 startup.
    mainWindow = new BrowserWindow({
      width: 1440,
      height: 900,
      minHeight: 700,
      show: false,
      icon: getAppIconPath(),
      webPreferences: {
        preload: join(__dirname, '../preload/index.js'),
        contextIsolation: true,
        sandbox: true,
      },
    })
    hardenWindowNavigation(mainWindow.webContents)
    await refreshLocalizedChrome()

    mainWindow.loadURL(
      'data:text/html;charset=utf-8,' +
        encodeURIComponent(
          '<!doctype html><html><head><meta charset="utf-8"><style>' +
            'html,body{height:100%;margin:0;background:#0b0e14;color:#9aa4b2;' +
            'font-family:system-ui,Segoe UI,Roboto,sans-serif;display:flex;' +
            'align-items:center;justify-content:center;font-size:14px}' +
            '.dot{display:inline-block;width:8px;height:8px;border-radius:50%;' +
            'background:#3b82f6;margin-right:8px;animation:p 1s infinite}' +
            '@keyframes p{0%,100%{opacity:.3}50%{opacity:1}}' +
            '</style></head><body><span class="dot"></span>正在启动 MT5 交易终端服务…</body></html>',
        ),
    )
    mainWindow.once('ready-to-show', () => mainWindow?.show())

    // Start the backend concurrently; swap to the real app once it is healthy.
    const backendReady = (async () => {
      try {
        if (is.dev) {
          await stopPythonService({ killPort: true, reason: 'dev-prestart-cleanup' })
          killBackendOnPort()
        }

        const backendAlreadyRunning = await isBackendHealthy()
        if (backendAlreadyRunning) {
          if (app.isPackaged) {
            // Packaged sessions should own the backend process so shutdown can reliably clean it up.
            killBackendOnPort()
          } else {
            markBackendHealthyReuse()
            console.log('Backend already healthy on port 8765, reusing existing service')
          }
        }

        const backendProcess = !backendAlreadyRunning || app.isPackaged ? startPythonService() : null
        await waitForBackendHealth({ childProcess: backendProcess })
      } catch (err) {
        markBackendStartupFailure(err)
        console.error('Failed to start backend:', err)
      }
    })()

    backendReady.finally(() => {
      if (!mainWindow || mainWindow.isDestroyed()) return
      if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
        mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
      } else {
        mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
      }
      // Open the user guide only after the real app has loaded.
      mainWindow.webContents.once('did-finish-load', () => {
        void maybeOpenUserGuideOnFirstLaunch()
      })
    })

    mainWindow.on('close', (event) => {
      if (!shutdownController.isQuitRequested()) {
        logShutdown('main-window:close intercepted -> hide')
        event.preventDefault()
        mainWindow?.hide()
      } else {
        logShutdown('main-window:close allowed -> quitting')
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
    logShutdown('window-all-closed')
    if (process.platform !== 'darwin') {
      app.quit()
    }
  })

  app.on('before-quit', (event) => {
    // Do NOT destroy the tray here: if shutdown is later cancelled by the
    // coordinator, the app would keep running with no way to reach the tray.
    shutdownController.handleBeforeQuit(event, 'before-quit')
  })

  app.on('will-quit', () => {
    logShutdown('will-quit')
    destroyTray()
  })

  app.whenReady().then(() => {
    protocol.registerFileProtocol('local-file', (request, callback) => {
      try {
        const decoded = decodeURIComponent(request.url.replace(/^local-file:\/\//, ''))
        const resolved = isAbsolute(decoded) ? resolve(decoded) : join(app.getPath('userData'), decoded)
        const normalized = resolved.replace(/\\/g, '/')
        // Compare with a trailing separator so a root can never match a
        // sibling directory that merely shares its prefix (C:/a/b vs C:/a/bX).
        const allowed = Array.from(allowedLocalRoots).some((root) => {
          const normalizedRoot = root.replace(/\\/g, '/')
          const boundedRoot = normalizedRoot.endsWith('/') ? normalizedRoot : normalizedRoot + '/'
          return normalized === normalizedRoot || normalized.startsWith(boundedRoot)
        })
        if (!allowed) {
          console.error(`local-file protocol blocked untrusted path: ${decoded}`)
          return callback('')
        }
        return callback(resolved)
      } catch (error) {
        console.error(error)
        return callback('')
      }
    })
  })
}
