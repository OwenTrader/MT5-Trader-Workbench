import { app } from 'electron'
import { spawn, ChildProcess } from 'node:child_process'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import http from 'node:http'

import { getPackagedBackendExecutablePath, getPackagedBackendWorkingDirectory } from './packaging-paths'

const BACKEND_HOST = '127.0.0.1'
const BACKEND_PORT = 8765
const BACKEND_HEALTH_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}/health`
const BACKEND_PRECHECK_TIMEOUT_MS = 1000
const BACKEND_STARTUP_TIMEOUT_MS = 15000
const BACKEND_POLL_INTERVAL_MS = 250
const MAX_BACKEND_LOG_LINES = 10

export type BackendStartupDiagnostics = {
  host: string
  port: number
  healthUrl: string
  workingDirectory: string
  executablePath: string
  settingsPath: string
  defaultSettingsPath: string
  isPackaged: boolean
  startedAt: string | null
  lastError: string | null
  recentLogs: string[]
}

function getPackagedDefaultSettingsPath(): string {
  return path.join(process.resourcesPath, 'storage', 'settings.json')
}

function getUserSettingsPath(): string {
  return path.join(app.getPath('userData'), 'storage', 'settings.json')
}

function getDevelopmentLocalSettingsPath(): string {
  return path.join(app.getAppPath(), 'storage', 'settings.local.json')
}

function getDevelopmentDefaultSettingsPath(): string {
  return path.join(app.getAppPath(), 'storage', 'settings.default.json')
}

function getBackendSettingsPath(): string {
  if (app.isPackaged) {
    return getUserSettingsPath()
  }

  return path.join(app.getAppPath(), 'storage', 'settings.local.json')
}

function getBackendDefaultSettingsPath(): string {
  if (app.isPackaged) {
    return getPackagedDefaultSettingsPath()
  }

  return getDevelopmentDefaultSettingsPath()
}

let pythonProcess: ChildProcess | null = null
let backendLogBuffer: string[] = []
let backendStartupDiagnostics: BackendStartupDiagnostics = createBackendStartupDiagnostics()

function createBackendStartupDiagnostics(): BackendStartupDiagnostics {
  const workingDirectory = getBackendWorkingDirectory()

  return {
    host: BACKEND_HOST,
    port: BACKEND_PORT,
    healthUrl: BACKEND_HEALTH_URL,
    workingDirectory,
    executablePath: app.isPackaged ? getPackagedBackendExecutablePath(process.resourcesPath) : 'python -m python_service.app.main',
    settingsPath: getBackendSettingsPath(),
    defaultSettingsPath: getBackendDefaultSettingsPath(),
    isPackaged: app.isPackaged,
    startedAt: null,
    lastError: null,
    recentLogs: []
  }
}

function syncBackendStartupDiagnostics(): void {
  backendStartupDiagnostics = {
    ...backendStartupDiagnostics,
    host: BACKEND_HOST,
    port: BACKEND_PORT,
    healthUrl: BACKEND_HEALTH_URL,
    workingDirectory: getBackendWorkingDirectory(),
    executablePath: app.isPackaged
      ? getPackagedBackendExecutablePath(process.resourcesPath)
      : 'python -m python_service.app.main',
    settingsPath: getBackendSettingsPath(),
    defaultSettingsPath: getBackendDefaultSettingsPath(),
    isPackaged: app.isPackaged,
    recentLogs: [...backendLogBuffer]
  }
}

function setBackendStartupError(message: string): void {
  syncBackendStartupDiagnostics()
  backendStartupDiagnostics = {
    ...backendStartupDiagnostics,
    lastError: message
  }
}

function getBackendWorkingDirectory(): string {
  return app.isPackaged
    ? getPackagedBackendWorkingDirectory(process.resourcesPath)
    : app.getAppPath()
}

function pushBackendLog(chunk: string): void {
  const lines = chunk
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  if (lines.length === 0) {
    return
  }

  backendLogBuffer.push(...lines)
  if (backendLogBuffer.length > MAX_BACKEND_LOG_LINES) {
    backendLogBuffer = backendLogBuffer.slice(-MAX_BACKEND_LOG_LINES)
  }

  syncBackendStartupDiagnostics()
}

function formatBackendStartupError(message: string): Error {
  if (backendLogBuffer.length === 0) {
    return new Error(message)
  }

  return new Error(`${message}\nBackend logs:\n${backendLogBuffer.join('\n')}`)
}

function pipeBackendOutput(stream: NodeJS.ReadableStream | null, method: 'log' | 'error'): void {
  if (!stream) {
    return
  }

  stream.setEncoding('utf8')
  stream.on('data', (chunk: string | Buffer) => {
    const text = typeof chunk === 'string' ? chunk : chunk.toString('utf8')
    pushBackendLog(text)

    const output = text.trimEnd()
    if (output) {
      console[method](`[backend] ${output}`)
    }
  })
}

function createHealthRequest(timeoutMs: number, onResult: (healthy: boolean) => void): http.ClientRequest {
  const req = http.get(BACKEND_HEALTH_URL, { timeout: timeoutMs }, (res) => {
    res.resume()
    onResult(res.statusCode === 200)
  })

  req.on('timeout', () => {
    req.destroy(new Error('Backend health probe timed out'))
  })

  req.on('error', () => {
    onResult(false)
  })

  return req
}

export function isBackendHealthy(timeoutMs = BACKEND_PRECHECK_TIMEOUT_MS): Promise<boolean> {
  return new Promise((resolve) => {
    let settled = false

    const finish = (healthy: boolean) => {
      if (settled) {
        return
      }

      settled = true
      resolve(healthy)
    }

    createHealthRequest(timeoutMs, finish)
  })
}

export function startPythonService(): ChildProcess {
  backendLogBuffer = []

  const backendWorkingDirectory = getBackendWorkingDirectory()
  const pythonExe = app.isPackaged
    ? getPackagedBackendExecutablePath(process.resourcesPath)
    : 'python'
  const args = app.isPackaged
    ? []
    : ['-m', 'python_service.app.main']
  const pythonPath = process.env.PYTHONPATH
    ? `${backendWorkingDirectory}${path.delimiter}${process.env.PYTHONPATH}`
    : backendWorkingDirectory

  backendStartupDiagnostics = {
    ...createBackendStartupDiagnostics(),
    startedAt: new Date().toISOString()
  }

  pythonProcess = spawn(pythonExe, args, {
    cwd: backendWorkingDirectory,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      PYTHONPATH: pythonPath,
      SETTINGS_FILE: getBackendSettingsPath(),
      DEFAULT_SETTINGS_FILE: getBackendDefaultSettingsPath()
    },
    windowsHide: true
  })

  pipeBackendOutput(pythonProcess.stdout, 'log')
  pipeBackendOutput(pythonProcess.stderr, 'error')

  pythonProcess.on('error', (err) => {
    const message = `Python process failed to start: ${err.message}`
    pushBackendLog(message)
    setBackendStartupError(message)
    console.error(message)
  })

  pythonProcess.on('close', (code, signal) => {
    const message = signal
      ? `Python process exited with signal ${signal}`
      : `Python process exited with code ${code}`
    pushBackendLog(message)
    if (code !== 0 || signal) {
      setBackendStartupError(message)
    }
    console.log(message)
  })

  return pythonProcess
}

export function stopPythonService() {
  if (pythonProcess) {
    pythonProcess.kill()
    pythonProcess = null
  }
}

export function markBackendStartupFailure(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error)
  setBackendStartupError(message)
}

export function markBackendHealthyReuse(): void {
  syncBackendStartupDiagnostics()
  backendStartupDiagnostics = {
    ...backendStartupDiagnostics,
    startedAt: new Date().toISOString(),
    lastError: null
  }
}

export function getBackendStartupDiagnostics(): BackendStartupDiagnostics {
  syncBackendStartupDiagnostics()
  return {
    ...backendStartupDiagnostics,
    recentLogs: [...backendStartupDiagnostics.recentLogs]
  }
}

export function killBackendOnPort(): void {
  try {
    if (process.platform === 'win32') {
      execFileSync(
        'powershell.exe',
        [
          '-NoProfile',
          '-Command',
          `Get-NetTCPConnection -LocalPort ${BACKEND_PORT} -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }`
        ],
        { stdio: 'ignore' }
      )
      return
    }

    execFileSync('sh', ['-lc', `lsof -ti tcp:${BACKEND_PORT} | xargs -r kill -9`], {
      stdio: 'ignore'
    })
  } catch {
  }
}

type WaitForBackendHealthOptions = {
  timeoutMs?: number
  intervalMs?: number
  childProcess?: ChildProcess | null
}

export function waitForBackendHealth({
  timeoutMs = BACKEND_STARTUP_TIMEOUT_MS,
  intervalMs = BACKEND_POLL_INTERVAL_MS,
  childProcess = pythonProcess
}: WaitForBackendHealthOptions = {}): Promise<void> {
  return new Promise((resolve, reject) => {
    if (childProcess && childProcess.exitCode !== null) {
      reject(
        formatBackendStartupError(
          `Backend exited before becoming healthy (exit code ${childProcess.exitCode})`
        )
      )
      return
    }

    const deadline = Date.now() + timeoutMs
    let timer: NodeJS.Timeout | null = null
    let settled = false

    const cleanup = () => {
      if (timer) {
        clearTimeout(timer)
        timer = null
      }

      childProcess?.off('error', onChildError)
      childProcess?.off('close', onChildClose)
    }

    const finish = (result: 'resolve' | 'reject', error?: Error) => {
      if (settled) {
        return
      }

      settled = true
      cleanup()

      if (result === 'resolve') {
        resolve()
      } else {
        reject(error)
      }
    }

    const onChildError = (error: Error) => {
      finish('reject', formatBackendStartupError(`Backend failed to spawn: ${error.message}`))
    }

    const onChildClose = (code: number | null, signal: NodeJS.Signals | null) => {
      const suffix = signal ? `signal ${signal}` : `exit code ${code ?? 'unknown'}`
      finish('reject', formatBackendStartupError(`Backend exited before becoming healthy (${suffix})`))
    }

    const poll = async () => {
      const healthy = await isBackendHealthy(Math.min(intervalMs, BACKEND_PRECHECK_TIMEOUT_MS))
      if (healthy) {
        finish('resolve')
        return
      }

      if (Date.now() >= deadline) {
        finish(
          'reject',
          formatBackendStartupError(`Backend health check timed out after ${timeoutMs}ms`)
        )
        return
      }

      timer = setTimeout(poll, intervalMs)
    }

    childProcess?.once('error', onChildError)
    childProcess?.once('close', onChildClose)

    void poll()
  })
}
