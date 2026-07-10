# Local mirror of the CI release build. Run from the Pyba repo root:
#   .\.venv\Scripts\Activate.ps1; .\packaging\build-local.ps1
#
# Note: dev venv is Python 3.14, CI uses 3.13. If PyInstaller errors here,
# build in a throwaway 3.13 venv:  py -3.13 -m venv .venv-build
# For a debug build with visible tracebacks:  $env:PYBA_CONSOLE = "1"

$ErrorActionPreference = "Stop"

pip install ..\deadlock-eos . ".[dev]" "pyinstaller>=6.11"   # NON-editable, mirrors CI
if ($LASTEXITCODE -ne 0) { exit 1 }

python -m pytest
if ($LASTEXITCODE -ne 0) { exit 1 }

$env:PYBA_DUMPS_SRC = (Resolve-Path "..\deadlock-eos\data\dumps").Path
pyinstaller pyba.spec --noconfirm
if ($LASTEXITCODE -ne 0) { exit 1 }

$version = python -c "import pyba; print(pyba.__version__)"
Compress-Archive -Force -Path dist\Pyba -DestinationPath "dist\Pyba-$version-win64.zip"
Write-Host "Built dist\Pyba\Pyba.exe and dist\Pyba-$version-win64.zip"
