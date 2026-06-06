// @vitest-environment node

import { EventEmitter } from 'node:events'
import type { ChildProcess } from 'node:child_process'
import path from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { electronAppMock, httpGetMock, execFileSyncMock, spawnMock } = vi.hoisted(() => ({
  electronAppMock: {
    isPackaged: false,
    getAppPath: vi.fn(() => 'E:/ai/tradingtoolByElec'),
    getPath: vi.fn((name: string) => {
      if (name === 'userData') {
        return 'C:/Users/Test/AppData/Roaming/MT5 Trader Workbench'
      }

      return ''
    })
  },
  httpGetMock: vi.fn(),
  execFileSyncMock: vi.fn(),
  spawnMock: vi.fn()
}))

vi.mock('electron', () => ({
  app: electronAppMock
}))

vi.mock('node:http', () => ({
  default: {
    get: httpGetMock
  }
}))

vi.mock('node:child_process', async () => {
  const actual = await vi.importActual<typeof import('node:child_process')>('node:child_process')
  return {
    ...actual,
    spawn: spawnMock,
    execFileSync: execFileSyncMock
  }
})

import { isBackendHealthy, startPythonService, stopPythonService, waitForBackendHealth } from './python-service'
import { getPackagedBackendExecutablePath } from './packaging-paths'

type MockRequest = EventEmitter & {
  destroy: (error?: Error) => void
}

type MockResponse = EventEmitter & {
  statusCode?: number
  resume: () => void
}

type MockChildProcess = EventEmitter & ChildProcess & {
  kill: ReturnType<typeof vi.fn>
  pid: number
  killed: boolean
  exitCode: number | null
  stdout: EventEmitter
  stderr: EventEmitter
}

function createRequest(
): MockRequest {
  const request = new EventEmitter() as MockRequest
  request.destroy = vi.fn((error?: Error) => {
    if (error) {
      queueMicrotask(() => request.emit('error', error))
    }
  })

  return request
}

function mockHealthResponse(statusCode: number): void {
  httpGetMock.mockImplementation((_url, _options, callback) => {
    const request = createRequest()
    queueMicrotask(() => {
      const response = new EventEmitter() as MockResponse
      response.statusCode = statusCode
      response.resume = vi.fn()
      callback(response)
    })
    return request
  })
}

function mockHealthFailure(): void {
  httpGetMock.mockImplementation(() => {
    const request = createRequest()
    queueMicrotask(() => request.emit('error', new Error('connect ECONNREFUSED')))
    return request
  })
}

function createChildProcess(pid = 1234): MockChildProcess {
  const childProcess = new EventEmitter() as MockChildProcess
  childProcess.pid = pid
  childProcess.killed = false
  childProcess.exitCode = null
  childProcess.stdout = new EventEmitter()
  childProcess.stderr = new EventEmitter()
  ;(childProcess.stdout as EventEmitter & { setEncoding: (encoding: string) => void }).setEncoding = vi.fn()
  ;(childProcess.stderr as EventEmitter & { setEncoding: (encoding: string) => void }).setEncoding = vi.fn()
  childProcess.kill = vi.fn(() => {
    childProcess.killed = true
    return true
  })
  return childProcess
}

describe('python-service startup health checks', () => {
  beforeEach(() => {
    httpGetMock.mockReset()
    execFileSyncMock.mockReset()
    spawnMock.mockReset()
    vi.restoreAllMocks()
    electronAppMock.isPackaged = false
    electronAppMock.getAppPath.mockReset()
    electronAppMock.getAppPath.mockReturnValue('E:/ai/tradingtoolByElec')
    electronAppMock.getPath.mockReset()
    electronAppMock.getPath.mockImplementation((name: string) => {
      if (name === 'userData') {
        return 'C:/Users/Test/AppData/Roaming/MT5 Trader Workbench'
      }

      return ''
    })
    Object.defineProperty(process, 'resourcesPath', {
      value: 'C:/Program Files/MT5 Trader Workbench/resources',
      configurable: true
    })
  })

  it('treats a 200 health response as healthy', async () => {
    mockHealthResponse(200)

    await expect(isBackendHealthy()).resolves.toBe(true)
    expect(httpGetMock).toHaveBeenCalledTimes(1)
  })

  it('rejects early when the backend process exits before becoming healthy', async () => {
    mockHealthFailure()

    const childProcess = new EventEmitter() as ChildProcess
    ;(childProcess as ChildProcess & { exitCode: number | null }).exitCode = null

    const startupPromise = waitForBackendHealth({
      childProcess,
      timeoutMs: 500,
      intervalMs: 25
    })

    setTimeout(() => {
      ;(childProcess as ChildProcess & { exitCode: number | null }).exitCode = 1
      childProcess.emit('close', 1, null)
    }, 10)

    await expect(startupPromise).rejects.toThrow(/exited before becoming healthy/i)
  })

  it('uses the packaged backend executable naming convention', () => {
    expect(getPackagedBackendExecutablePath('C:/app/resources')).toBe(
      path.join('C:/app/resources', 'mt5_service', 'mt5_service.exe')
    )
  })

  it('kills the backend port when requested during shutdown', async () => {
    await stopPythonService({ killPort: true, reason: 'test-port-cleanup' })

    expect(execFileSyncMock).toHaveBeenCalledTimes(1)
  })

  it('waits for graceful backend child shutdown before resolving', async () => {
    const childProcess = createChildProcess(4321)
    spawnMock.mockReturnValue(childProcess)

    startPythonService()

    const stopPromise = stopPythonService({ reason: 'graceful-test' })

    expect(childProcess.kill).toHaveBeenCalledTimes(1)
    expect(execFileSyncMock).not.toHaveBeenCalled()

    childProcess.exitCode = 0
    childProcess.emit('close', 0, null)

    await expect(stopPromise).resolves.toBeUndefined()
    expect(execFileSyncMock).not.toHaveBeenCalled()
  })

  it('passes the electron parent pid to the backend process', () => {
    const childProcess = createChildProcess(2468)
    spawnMock.mockReturnValue(childProcess)

    startPythonService()

    expect(spawnMock).toHaveBeenCalledTimes(1)
    const spawnOptions = spawnMock.mock.calls[0]?.[2]
    expect(spawnOptions?.env?.PARENT_PID).toBe(String(process.pid))
  })

  it('passes development quant paths to the backend process environment', () => {
    const childProcess = createChildProcess(9753)
    spawnMock.mockReturnValue(childProcess)

    startPythonService()

    const spawnOptions = spawnMock.mock.calls[0]?.[2]
    expect(spawnOptions?.env?.PYTHON_QUANT_DATA_DIR).toBe(
      path.join('E:/ai/tradingtoolByElec', 'storage', 'python_quant')
    )
    expect(spawnOptions?.env?.PYTHON_QUANT_STRATEGIES_DIR).toBe(
      path.join('E:/ai/tradingtoolByElec', 'storage', 'python_quant', 'strategies')
    )
    expect(spawnOptions?.env?.PYTHON_QUANT_JOBS_PATH).toBe(
      path.join('E:/ai/tradingtoolByElec', 'storage', 'python_quant', 'jobs.json')
    )
    expect(spawnOptions?.env?.PYTHON_QUANT_MARKET_DATA_PATH).toBe(
      path.join('E:/ai/tradingtoolByElec', 'storage', 'python_quant', 'market_data.sqlite3')
    )
  })

  it('passes packaged quant paths to the backend process environment', () => {
    electronAppMock.isPackaged = true
    const childProcess = createChildProcess(8642)
    spawnMock.mockReturnValue(childProcess)

    startPythonService()

    const spawnOptions = spawnMock.mock.calls[0]?.[2]
    expect(spawnOptions?.env?.PYTHON_QUANT_DATA_DIR).toBe(
      path.join('C:/Users/Test/AppData/Roaming/MT5 Trader Workbench', 'storage', 'python_quant')
    )
    expect(spawnOptions?.env?.PYTHON_QUANT_STRATEGIES_DIR).toBe(
      path.join('C:/Users/Test/AppData/Roaming/MT5 Trader Workbench', 'storage', 'python_quant', 'strategies')
    )
    expect(spawnOptions?.env?.PYTHON_QUANT_JOBS_PATH).toBe(
      path.join('C:/Users/Test/AppData/Roaming/MT5 Trader Workbench', 'storage', 'python_quant', 'jobs.json')
    )
    expect(spawnOptions?.env?.PYTHON_QUANT_MARKET_DATA_PATH).toBe(
      path.join('C:/Users/Test/AppData/Roaming/MT5 Trader Workbench', 'storage', 'python_quant', 'market_data.sqlite3')
    )
  })

  it('force-kills the backend process tree when graceful shutdown stalls', async () => {
    vi.useFakeTimers()
    const childProcess = createChildProcess(5678)
    spawnMock.mockReturnValue(childProcess)

    startPythonService()

    const stopPromise = stopPythonService({ killPort: true, reason: 'force-kill-test' })

    await vi.advanceTimersByTimeAsync(3000)
    childProcess.exitCode = 1
    childProcess.emit('close', 1, null)
    await stopPromise

    expect(execFileSyncMock).toHaveBeenCalledTimes(2)
    expect(execFileSyncMock).toHaveBeenNthCalledWith(1, 'taskkill.exe', ['/PID', '5678', '/T', '/F'], { stdio: 'ignore' })
    expect(execFileSyncMock).toHaveBeenNthCalledWith(
      2,
      'powershell.exe',
      [
        '-NoProfile',
        '-Command',
        'Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }'
      ],
      { stdio: 'ignore' }
    )
    vi.useRealTimers()
  })
})
