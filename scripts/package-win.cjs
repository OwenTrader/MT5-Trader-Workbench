const fs = require('node:fs')
const path = require('node:path')
const { spawnSync } = require('node:child_process')

const repoRoot = path.resolve(__dirname, '..')
const packageJsonPath = path.join(repoRoot, 'package.json')
const statePath = path.join(repoRoot, '.build-version.json')
const electronBuilderCliPath = path.join(repoRoot, 'node_modules', 'electron-builder', 'cli.js')
const localCacheRoot = path.join(repoRoot, '.cache', 'electron-builder')
const localTempDir = path.join(localCacheRoot, 'temp')
const systemElectronBuilderCacheRoot = path.join('C:', 'Users', 'Administrator', 'AppData', 'Local', 'electron-builder', 'Cache')
const isDryRun = process.argv.includes('--dry-run')
const isDebugPackage = process.argv.includes('--debug')
const isHardenedPackage = process.argv.includes('--hardened')

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

function readLastBuildNumber() {
  if (!fs.existsSync(statePath)) {
    return 0
  }

  const state = readJson(statePath)
  const { lastBuildNumber = 0 } = state

  if (!Number.isInteger(lastBuildNumber) || lastBuildNumber < 0) {
    throw new Error(`Invalid lastBuildNumber in ${path.basename(statePath)}`)
  }

  return lastBuildNumber
}

function writeState(buildNumber, buildVersion) {
  const state = {
    lastBuildNumber: buildNumber,
    lastBuildVersion: buildVersion,
    updatedAt: new Date().toISOString()
  }

  fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`, 'utf8')
}

function ensureLocalBuildDirectories() {
  fs.mkdirSync(localCacheRoot, { recursive: true })
  fs.mkdirSync(localTempDir, { recursive: true })
}

function copyDirectoryContents(sourceDir, targetDir) {
  fs.mkdirSync(targetDir, { recursive: true })

  for (const entry of fs.readdirSync(sourceDir, { withFileTypes: true })) {
    const sourcePath = path.join(sourceDir, entry.name)
    const targetPath = path.join(targetDir, entry.name)

    if (entry.isDirectory()) {
      copyDirectoryContents(sourcePath, targetPath)
      continue
    }

    fs.copyFileSync(sourcePath, targetPath)
  }
}

function seedLocalElectronBuilderCache() {
  if (!fs.existsSync(systemElectronBuilderCacheRoot)) {
    console.log(`[package:win] system cache not found: ${systemElectronBuilderCacheRoot}`)
    return
  }

  const toolDirectories = ['winCodeSign', 'nsis']

  for (const directoryName of toolDirectories) {
    const sourceDir = path.join(systemElectronBuilderCacheRoot, directoryName)
    const targetDir = path.join(localCacheRoot, directoryName)

    if (!fs.existsSync(sourceDir)) {
      console.log(`[package:win] seed skipped, missing source: ${sourceDir}`)
      continue
    }

    console.log(`[package:win] seeding cache: ${directoryName}`)
    copyDirectoryContents(sourceDir, targetDir)
  }
}

function escapePowerShellSingleQuotedString(value) {
  return value.replace(/'/g, "''")
}

function stopProcessesUsingUnpackedOutput(outputDir) {
  const unpackedOutputDir = path.join(outputDir, 'win-unpacked')

  if (process.platform !== 'win32' || !fs.existsSync(unpackedOutputDir)) {
    return
  }

  const normalizedOutputDir = `${unpackedOutputDir}${path.sep}`.toLowerCase()
  const command = [
    `$root = '${escapePowerShellSingleQuotedString(normalizedOutputDir)}';`,
    'Get-CimInstance Win32_Process |',
    'Where-Object { $_.ExecutablePath -and $_.ExecutablePath.ToLowerInvariant().StartsWith($root) } |',
    'ForEach-Object {',
    '  Write-Host "[package:win] stopping stale packaged process: $($_.ProcessId) $($_.ExecutablePath)";',
    '  Stop-Process -Id $_.ProcessId -Force',
    '}'
  ].join(' ')

  spawnSync('powershell.exe', ['-NoProfile', '-Command', command], {
    cwd: repoRoot,
    stdio: 'inherit'
  })
}

function removePreviousOutputDirectory(outputDir) {
  if (!fs.existsSync(outputDir)) {
    return
  }

  console.log(`[package:win] removing previous output: ${outputDir}`)
  try {
    fs.rmSync(outputDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 1000 })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    throw new Error(
      `Unable to remove ${outputDir}. Close any running copy of the packaged app in that directory, then retry. ${message}`
    )
  }
}

function prepareOutputDirectory(outputDir) {
  stopProcessesUsingUnpackedOutput(outputDir)
  removePreviousOutputDirectory(outputDir)
}

function getOutputDirectory(buildVersion) {
  if (isDebugPackage) {
    return path.join(repoRoot, 'dist', 'debug')
  }

  return isHardenedPackage
    ? path.join(repoRoot, 'dist', 'hardened')
    : path.join(repoRoot, 'dist', buildVersion)
}

function main() {
  const packageJson = readJson(packageJsonPath)
  const productName = packageJson.build?.productName ?? packageJson.name
  const lastBuildNumber = readLastBuildNumber()
  const nextBuildNumber = lastBuildNumber + 1
  const buildVersion = `${packageJson.version}.${nextBuildNumber}`
  const artifactName = `${productName} Setup ${buildVersion}.exe`
  const outputDir = getOutputDirectory(buildVersion)
  ensureLocalBuildDirectories()
  seedLocalElectronBuilderCache()

  console.log(`[package:win] build number: ${nextBuildNumber}`)
  console.log(`[package:win] build version: ${buildVersion}`)
  console.log(`[package:win] artifact: ${artifactName}`)
  console.log(`[package:win] output dir: ${outputDir}`)
  console.log(`[package:win] hardened: ${isHardenedPackage ? 'yes' : 'no'}`)
  console.log(`[package:win] electron-builder cache: ${localCacheRoot}`)
  console.log(`[package:win] temp dir: ${localTempDir}`)

  if (isDryRun) {
    return
  }

  prepareOutputDirectory(outputDir)

  const result = spawnSync(process.execPath, [electronBuilderCliPath, '--win', `--config.directories.output=${outputDir}`], {
    cwd: repoRoot,
    env: {
      ...process.env,
      BUILD_NUMBER: String(nextBuildNumber),
      CSC_IDENTITY_AUTO_DISCOVERY: 'false',
      ELECTRON_BUILDER_CACHE: localCacheRoot,
      TEMP: localTempDir,
      TMP: localTempDir
    },
    stdio: 'inherit'
  })

  if (result.status !== 0) {
    process.exit(result.status ?? 1)
  }

  writeState(nextBuildNumber, buildVersion)
}

main()
