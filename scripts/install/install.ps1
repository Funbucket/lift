param(
  [string]$LiftHome = $(if ($env:LIFT_HOME) { $env:LIFT_HOME } else { Join-Path $HOME ".lift" }),
  [string]$LiftBinDir = $(if ($env:LIFT_BIN_DIR) { $env:LIFT_BIN_DIR } else { Join-Path $HOME ".local\bin" }),
  [string]$LiftSource = $(if ($env:LIFT_SOURCE) { $env:LIFT_SOURCE } else { "" }),
  [string]$LiftPackage = $(if ($env:LIFT_PACKAGE) { $env:LIFT_PACKAGE } elseif ($env:LIFT_SOURCE) { $env:LIFT_SOURCE } else { "" }),
  [string]$LiftVersion = $(if ($env:LIFT_VERSION) { $env:LIFT_VERSION } else { "0.1.0" }),
  [string]$LiftPackageUrl = $(if ($env:LIFT_PACKAGE_URL) { $env:LIFT_PACKAGE_URL } else { "" }),
  [string]$LiftReleaseBaseUrl = $(if ($env:LIFT_RELEASE_BASE_URL) { $env:LIFT_RELEASE_BASE_URL } else { "" }),
  [string]$LiftDefaultReleaseBaseUrl = "https://github.com/Funbucket/lift/releases/latest/download",
  [string]$PythonBin = $(if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" })
)

if (!$LiftPackage) {
  $cwdPackage = (Get-Location).Path
  $cwdPyproject = Join-Path $cwdPackage "pyproject.toml"
  if ($LiftPackageUrl) {
    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    $LiftPackage = Join-Path $tempDir "lift_agent-$LiftVersion-py3-none-any.whl"
    Invoke-WebRequest -Uri $LiftPackageUrl -OutFile $LiftPackage
  } elseif ($LiftReleaseBaseUrl) {
    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    $LiftPackage = Join-Path $tempDir "lift_agent-$LiftVersion-py3-none-any.whl"
    Invoke-WebRequest -Uri "$LiftReleaseBaseUrl/lift_agent-$LiftVersion-py3-none-any.whl" -OutFile $LiftPackage
  } elseif ($LiftDefaultReleaseBaseUrl) {
    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    $LiftPackage = Join-Path $tempDir "lift_agent-$LiftVersion-py3-none-any.whl"
    Invoke-WebRequest -Uri "$LiftDefaultReleaseBaseUrl/lift_agent-$LiftVersion-py3-none-any.whl" -OutFile $LiftPackage
  } elseif (Test-Path $cwdPyproject) {
    $LiftPackage = $cwdPackage
  } else {
    Write-Error "Lift package not specified. Set LIFT_PACKAGE, LIFT_PACKAGE_URL, or LIFT_RELEASE_BASE_URL."
    exit 1
  }
}

$isDirectory = Test-Path $LiftPackage -PathType Container
$isFile = Test-Path $LiftPackage -PathType Leaf
if ($isDirectory) {
  $pyproject = Join-Path $LiftPackage "pyproject.toml"
  if (!(Test-Path $pyproject)) {
    Write-Error "Lift source not found at $LiftPackage. Run this from the repo root or set LIFT_PACKAGE."
    exit 1
  }
} elseif (!$isFile) {
  Write-Error "Lift package not found at $LiftPackage. Set LIFT_PACKAGE to a source directory, wheel, or sdist."
  exit 1
}

$venvDir = Join-Path $LiftHome "venv"
New-Item -ItemType Directory -Force -Path $LiftHome | Out-Null
New-Item -ItemType Directory -Force -Path $LiftBinDir | Out-Null

& $PythonBin -m venv $venvDir
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"
& $venvPython -m pip install --upgrade pip
& $venvPip install $LiftPackage

$launcher = Join-Path $LiftBinDir "lift.cmd"
$liftExe = Join-Path $venvDir "Scripts\lift.exe"
"@echo off`r`n`"$liftExe`" %*" | Set-Content -Encoding ASCII $launcher

Write-Host "Lift installed."
Write-Host "Launcher: $launcher"
Write-Host "Home: $LiftHome"
Write-Host "Package: $LiftPackage"
Write-Host "Version: $LiftVersion"
Write-Host ""
Write-Host "Make sure $LiftBinDir is on PATH, then run:"
Write-Host "  lift setup"
Write-Host "  lift doctor"
Write-Host "  lift quickstart"
