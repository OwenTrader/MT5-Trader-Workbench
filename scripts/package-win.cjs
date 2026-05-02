const fs = require('node:fs')
const path = require('node:path')
const { spawnSync } = require('node:child_process')

const repoRoot = path.resolve(__dirname, '..')
const packageJsonPath = path.join(repoRoot, 'package.json')
const statePath = path.join(repoRoot, '.build-version.json')
const electronBuilderCliPath = path.join(repoRoot, 'node_modules', 'electron-builder', 'cli.js')
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

function main() {
  const packageJson = readJson(packageJsonPath)
  const productName = packageJson.build?.productName ?? packageJson.name
  const lastBuildNumber = readLastBuildNumber()
  const nextBuildNumber = lastBuildNumber + 1
  const buildVersion = `${packageJson.version}.${nextBuildNumber}`
  const artifactName = `${productName} Setup ${buildVersion}.exe`

  console.log(`[package:win] build number: ${nextBuildNumber}`)
  console.log(`[package:win] build version: ${buildVersion}`)
  console.log(`[package:win] artifact: ${artifactName}`)

  if (isDryRun) {
    return
  }

  const result = spawnSync(process.execPath, [electronBuilderCliPath, '--win'], {
    cwd: repoRoot,
    env: {
      ...process.env,
      BUILD_NUMBER: String(nextBuildNumber)
    },
    stdio: 'inherit'
  })

  if (result.status !== 0) {
    process.exit(result.status ?? 1)
  }

  writeState(nextBuildNumber, buildVersion)
}

main()
