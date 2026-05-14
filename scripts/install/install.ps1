param(
  [string]$LiftHome = $(if ($env:LIFT_HOME) { $env:LIFT_HOME } else { Join-Path $HOME ".lift" }),
  [string]$LiftBinDir = $(if ($env:LIFT_BIN_DIR) { $env:LIFT_BIN_DIR } else { Join-Path $HOME ".local\bin" }),
  [string]$LiftSource = $(if ($env:LIFT_SOURCE) { $env:LIFT_SOURCE } else { (Get-Location).Path }),
  [string]$PythonBin = $(if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" })
)

$pyproject = Join-Path $LiftSource "pyproject.toml"
if (!(Test-Path $pyproject)) {
  Write-Error "Lift source not found at $LiftSource. Run this from the repo root or set LIFT_SOURCE."
  exit 1
}

$venvDir = Join-Path $LiftHome "venv"
New-Item -ItemType Directory -Force -Path $LiftHome | Out-Null
New-Item -ItemType Directory -Force -Path $LiftBinDir | Out-Null

& $PythonBin -m venv $venvDir
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"
& $venvPython -m pip install --upgrade pip
& $venvPip install $LiftSource

$launcher = Join-Path $LiftBinDir "lift.cmd"
$liftExe = Join-Path $venvDir "Scripts\lift.exe"
"@echo off`r`n`"$liftExe`" %*" | Set-Content -Encoding ASCII $launcher

Write-Host "Lift installed."
Write-Host "Launcher: $launcher"
Write-Host "Home: $LiftHome"
Write-Host ""
Write-Host "Make sure $LiftBinDir is on PATH, then run:"
Write-Host "  lift doctor"
