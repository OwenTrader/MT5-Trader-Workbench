// @vitest-environment node

import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

describe('packaging configuration', () => {
  const packageJsonPath = path.resolve(__dirname, '../../package.json')
  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'))
  const build = packageJson.build

  it('contains valid electron-builder Windows and NSIS configuration', () => {
    expect(build).toBeDefined()
    expect(build.productName).toBe('MT5 Trader Workbench')

    // Windows target configuration
    expect(build.win).toBeDefined()
    expect(build.win.target).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          target: 'nsis',
          arch: expect.arrayContaining(['x64']),
        }),
      ])
    )
    expect(build.win.icon).toBe('resources/app-icon.ico')

    // NSIS wizard settings
    const nsis = build.nsis
    expect(nsis).toBeDefined()
    expect(nsis.oneClick).toBe(false)
    expect(nsis.allowToChangeInstallationDirectory).toBe(true)
    expect(nsis.allowElevation).toBe(true)
    expect(nsis.perMachine).toBe(false)
    expect(nsis.createDesktopShortcut).toBe('always')
    expect(nsis.createStartMenuShortcut).toBe(true)
    expect(nsis.shortcutName).toBe('MT5 Trader Workbench')
    expect(nsis.installerIcon).toBe('resources/app-icon.ico')
    expect(nsis.uninstallerIcon).toBe('resources/app-icon.ico')
    expect(nsis.deleteAppDataOnUninstall).toBe(false)
    expect(nsis.runAfterFinish).toBe(true)
  })

  it('points to valid icon and custom nsis script files on disk', () => {
    const rootDir = path.resolve(__dirname, '../..')
    const nsis = build.nsis

    expect(fs.existsSync(path.join(rootDir, nsis.installerIcon))).toBe(true)
    expect(fs.existsSync(path.join(rootDir, nsis.uninstallerIcon))).toBe(true)

    if (nsis.include) {
      expect(fs.existsSync(path.join(rootDir, nsis.include))).toBe(true)
    }
  })
})
