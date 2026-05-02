// @vitest-environment node

import { describe, expect, it, vi } from 'vitest'

import { createShutdownController } from './shutdown-coordinator'

async function flushMicrotasks(iterations = 4): Promise<void> {
  for (let index = 0; index < iterations; index += 1) {
    await Promise.resolve()
  }
}

describe('shutdown coordinator', () => {
  it('reuses one in-flight cleanup across repeated quit hooks', async () => {
    let resolveCleanup: (() => void) | null = null
    const cleanup = vi.fn(() => new Promise<void>((resolve) => {
      resolveCleanup = resolve
    }))
    const resumeQuit = vi.fn()
    const log = vi.fn()

    const controller = createShutdownController({ cleanup, resumeQuit, log })
    const firstEvent = { preventDefault: vi.fn() }
    const secondEvent = { preventDefault: vi.fn() }

    controller.handleBeforeQuit(firstEvent, 'before-quit-first')
    controller.handleBeforeQuit(secondEvent, 'before-quit-second')

    expect(firstEvent.preventDefault).toHaveBeenCalledTimes(1)
    expect(secondEvent.preventDefault).toHaveBeenCalledTimes(1)
    expect(cleanup).toHaveBeenCalledTimes(1)
    expect(cleanup).toHaveBeenCalledWith('before-quit-first')

    resolveCleanup?.()
    await flushMicrotasks()

    expect(resumeQuit).toHaveBeenCalledTimes(1)
    expect(log).toHaveBeenCalledWith('cleanup:reuse (before-quit-second)')
  })

  it('marks tray-triggered quit so window close is not hidden', () => {
    const controller = createShutdownController({
      cleanup: vi.fn(async () => {}),
      resumeQuit: vi.fn(),
      log: vi.fn()
    })

    expect(controller.isQuitRequested()).toBe(false)
    controller.markQuitRequested('tray-menu')
    expect(controller.isQuitRequested()).toBe(true)
  })
})
