// @vitest-environment node

import path from 'node:path'
import { describe, expect, it } from 'vitest'

import { getPackagedBackendExecutablePath, getPackagedBackendWorkingDirectory } from './packaging-paths'

describe('packaging paths', () => {
  it('builds packaged backend paths from resources path', () => {
    expect(getPackagedBackendWorkingDirectory('C:/app/resources')).toBe(path.join('C:/app/resources', 'mt5_service'))
    expect(getPackagedBackendExecutablePath('C:/app/resources')).toBe(
      path.join('C:/app/resources', 'mt5_service', 'mt5_service.exe')
    )
  })
})
