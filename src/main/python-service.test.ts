// @vitest-environment node

import { EventEmitter } from 'node:events'
import type { ChildProcess } from 'node:child_process'
import path from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { httpGetMock, execFileSyncMock } = vi.hoisted(() => ({
  httpGetMock: vi.fn(),
  execFileSyncMock: vi.fn()
}))

vi.mock('electron', () => ({
  app: {
    isPackaged: false,
    getAppPath: () => 'E:/ai/tradingtoolByElec'
  }
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
    execFileSync: execFileSyncMock
  }
})

import { isBackendHealthy, stopPythonService, waitForBackendHealth } from './python-service'
import { getPackagedBackendExecutablePath } from './packaging-paths'

type MockRequest = EventEmitter & {
  destroy: (error?: Error) => void
}

type MockResponse = EventEmitter & {
  statusCode?: number
  resume: () => void
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

describe('python-service startup health checks', () => {
  beforeEach(() => {
    httpGetMock.mockReset()
    execFileSyncMock.mockReset()
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

  it('kills the backend port when requested during shutdown', () => {
    stopPythonService({ killPort: true })

    expect(execFileSyncMock).toHaveBeenCalledTimes(1)
  })
})
