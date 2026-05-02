$pyproject = Get-Content "python_service/pyproject.toml" -Raw
$requirements = Get-Content "python_service/requirements.txt" | Where-Object { $_ -and -not $_.StartsWith('#') }

$dependencyBlock = [regex]::Match($pyproject, 'dependencies\s*=\s*\[(?<items>.*?)\]', 'Singleline').Groups['items'].Value
if (-not $dependencyBlock) {
  throw 'pyproject.toml missing dependencies block'
}

$normalize = {
  param([string]$name)

  return (($name -split '[<>=!~;\[]')[0]).Trim().ToLowerInvariant()
}

$pyprojectDeps = [regex]::Matches($dependencyBlock, '"([^"]+)"') |
  ForEach-Object { & $normalize $_.Groups[1].Value }
$requirementsDeps = $requirements | ForEach-Object { & $normalize $_ }

$missingFromPyproject = $requirementsDeps | Where-Object { $_ -notin $pyprojectDeps }
$missingFromRequirements = $pyprojectDeps | Where-Object { $_ -notin $requirementsDeps }

if ($missingFromPyproject.Count -gt 0) {
  throw "pyproject.toml missing: $($missingFromPyproject -join ', ')"
}

if ($missingFromRequirements.Count -gt 0) {
  throw "requirements.txt missing: $($missingFromRequirements -join ', ')"
}
