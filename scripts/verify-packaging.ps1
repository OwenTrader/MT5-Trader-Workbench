$Hardened = $args -contains '-Hardened'

$backendDir = "python_service/dist/mt5_service"
$exe = Join-Path $backendDir "mt5_service.exe"
$internalDir = Join-Path $backendDir "_internal"
$awakeningScriptsDir = Join-Path $internalDir "external/awakening_system/scripts"
$helpDir = "resources/help"
$requiredHelpFiles = @(
  "user-guide.zh-CN.html",
  "user-guide.en.html"
)
$requiredAwakeningScripts = @(
  "gold_analysis.py",
  "wave_analysis.py",
  "elliott_wave.py",
  "pa_wave_fusion.py",
  "smc_snapshot.py",
  "scenario_playbook.py",
  "institutional_render.py",
  "economic_calendar.py"
)

if (-not (Test-Path $backendDir -PathType Container)) {
  throw "Missing Python backend directory: $backendDir"
}

if (-not (Test-Path $exe -PathType Leaf)) {
  throw "Missing Python backend artifact: $exe"
}

if (-not (Test-Path $internalDir -PathType Container)) {
  throw "Missing bundled Python runtime directory: $internalDir"
}

$internalFileCount = @(Get-ChildItem $internalDir -Recurse -File).Count
if ($internalFileCount -eq 0) {
  throw "Bundled Python runtime directory is empty: $internalDir"
}

if ($Hardened) {
  $bundledProjectSourceFiles = @(Get-ChildItem $backendDir -Recurse -File -Include '*.py' | Where-Object {
      $_.FullName -like "*\_internal\app\*" -or
      $_.FullName -like "*\_internal\external\awakening_system\scripts\*"
    })

  if ($bundledProjectSourceFiles.Count -gt 0) {
    $fileList = ($bundledProjectSourceFiles | Select-Object -ExpandProperty FullName) -join "`n"
    throw "Hardened package contains project Python source files:`n$fileList"
  }
} else {
  if (-not (Test-Path $awakeningScriptsDir -PathType Container)) {
    throw "Missing bundled awakening scripts directory: $awakeningScriptsDir"
  }

  foreach ($scriptName in $requiredAwakeningScripts) {
    $scriptPath = Join-Path $awakeningScriptsDir $scriptName
    if (-not (Test-Path $scriptPath -PathType Leaf)) {
      throw "Missing bundled awakening script: $scriptPath"
    }
  }
}

if (-not (Test-Path $helpDir -PathType Container)) {
  throw "Missing help directory: $helpDir"
}

foreach ($helpFile in $requiredHelpFiles) {
  $helpPath = Join-Path $helpDir $helpFile
  if (-not (Test-Path $helpPath -PathType Leaf)) {
    throw "Missing help document: $helpPath"
  }
}

$packageJson = Get-Content "package.json" -Raw | ConvertFrom-Json
$resourceEntry = @($packageJson.build.extraResources | Where-Object { $_.to -eq 'mt5_service' }) | Select-Object -First 1
$helpEntry = @($packageJson.build.extraResources | Where-Object { $_.to -eq 'help' }) | Select-Object -First 1

if (-not $resourceEntry) {
  throw 'Missing extraResources entry for mt5_service'
}

if ($resourceEntry.from -ne 'python_service/dist/mt5_service') {
  throw 'Electron extraResources path is not aligned with python output path'
}

if (-not $helpEntry) {
  throw 'Missing extraResources entry for help'
}

if ($helpEntry.from -ne 'resources/help') {
  throw 'Electron extraResources path is not aligned with help source path'
}

[pscustomobject]@{
  BackendDirectory = (Resolve-Path $backendDir).Path
  ExecutablePath = (Resolve-Path $exe).Path
  ExecutableLength = (Get-Item $exe).Length
  ExecutableLastWriteTime = (Get-Item $exe).LastWriteTime
  InternalFileCount = $internalFileCount
  Hardened = $Hardened
  AwakeningScriptsDirectory = if (Test-Path $awakeningScriptsDir -PathType Container) { (Resolve-Path $awakeningScriptsDir).Path } else { $null }
  HelpDirectory = (Resolve-Path $helpDir).Path
} | Select-Object BackendDirectory, ExecutablePath, ExecutableLength, ExecutableLastWriteTime, InternalFileCount, Hardened, AwakeningScriptsDirectory, HelpDirectory
