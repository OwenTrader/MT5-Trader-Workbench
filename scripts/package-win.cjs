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

function main() {
  const packageJson = readJson(packageJsonPath)
  const productName = packageJson.build?.productName ?? packageJson.name
  const lastBuildNumber = readLastBuildNumber()
  const nextBuildNumber = lastBuildNumber + 1
  const buildVersion = `${packageJson.version}.${nextBuildNumber}`
  const artifactName = `${productName} Setup ${buildVersion}.exe`
  ensureLocalBuildDirectories()
  seedLocalElectronBuilderCache()

  console.log(`[package:win] build number: ${nextBuildNumber}`)
  console.log(`[package:win] build version: ${buildVersion}`)
  console.log(`[package:win] artifact: ${artifactName}`)
  console.log(`[package:win] electron-builder cache: ${localCacheRoot}`)
  console.log(`[package:win] temp dir: ${localTempDir}`)

  if (isDryRun) {
    return
  }

  const result = spawnSync(process.execPath, [electronBuilderCliPath, '--win'], {
    cwd: repoRoot,
    env: {
      ...process.env,
      BUILD_NUMBER: String(nextBuildNumber),
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
