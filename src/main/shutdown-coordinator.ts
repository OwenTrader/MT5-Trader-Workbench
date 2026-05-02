type BeforeQuitEventLike = {
  preventDefault: () => void
}

type ShutdownControllerOptions = {
  cleanup: (reason: string) => Promise<void>
  resumeQuit: () => void
  log: (message: string) => void
}

export type ShutdownController = {
  markQuitRequested: (reason: string) => void
  isQuitRequested: () => boolean
  beginCleanup: (reason: string) => Promise<void>
  handleBeforeQuit: (event: BeforeQuitEventLike, reason: string) => void
}

export function createShutdownController({ cleanup, resumeQuit, log }: ShutdownControllerOptions): ShutdownController {
  let quitRequested = false
  let cleanupPromise: Promise<void> | null = null
  let resumeScheduled = false
  let quitResumed = false

  const beginCleanup = (reason: string): Promise<void> => {
    if (!cleanupPromise) {
      log(`cleanup:start (${reason})`)
      cleanupPromise = cleanup(reason)
        .then(() => {
          log(`cleanup:done (${reason})`)
        })
        .catch((error) => {
          const message = error instanceof Error ? error.message : String(error)
          log(`cleanup:error (${reason}) ${message}`)
          throw error
        })
    } else {
      log(`cleanup:reuse (${reason})`)
    }

    return cleanupPromise
  }

  const scheduleQuitResume = (): void => {
    if (resumeScheduled) {
      return
    }

    resumeScheduled = true
    void cleanupPromise?.finally(() => {
      quitResumed = true
      log('quit:resume')
      resumeQuit()
    })
  }

  return {
    markQuitRequested(reason: string) {
      quitRequested = true
      log(`quit-requested (${reason})`)
    },
    isQuitRequested() {
      return quitRequested
    },
    beginCleanup,
    handleBeforeQuit(event: BeforeQuitEventLike, reason: string) {
      log(`before-quit (${reason}) resumed=${quitResumed}`)
      quitRequested = true

      if (quitResumed) {
        return
      }

      event.preventDefault()
      void beginCleanup(reason)
      scheduleQuitResume()
    }
  }
}
