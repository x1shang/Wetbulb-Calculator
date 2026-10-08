[CmdletBinding()]
param([string]$Python = $env:WETBULB_BUILD_PYTHON)
$ErrorActionPreference = 'Stop'
if (-not $Python) { $Python = (Get-Command python -ErrorAction Stop).Source }
$Python = (Get-Command $Python -ErrorAction Stop).Source
if ($Python -match '[^\x00-\x7F]') { throw 'Use a Python 3.10 environment in an ASCII path (WETBULB_BUILD_PYTHON).' }
Push-Location $PSScriptRoot
try {
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:WETBULB_GUI_PYTHON = $Python
    $env:WETBULB_REQUIRE_GUI = '1'
    & $Python -c 'import sys, PyInstaller; assert sys.version_info[:2] == (3, 10); assert PyInstaller.__version__ == "6.11.1"'
    if ($LASTEXITCODE -ne 0) { throw 'Requires Python 3.10 and requirements-build.txt.' }
    & $Python -m pytest -q -rs
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    & $Python -m pyflakes main.py src/core.py src/cli.py src/batch.py src/gui_smoke.py
    if ($LASTEXITCODE -ne 0) { throw 'Static checks failed.' }
    & $Python scripts/version_info.py
    if ($LASTEXITCODE -ne 0) { throw 'Version generation failed.' }
    & $Python scripts/collect_licenses.py
    if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
    & $Python -m PyInstaller --noconfirm --clean WetBulbCalculator.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
    $tag = & $Python src/cli.py --version
    $exe = Join-Path $PSScriptRoot "dist/WetBulbCalculator-$tag.exe"
    $cli = Join-Path $PSScriptRoot "dist/WetBulbCLI-$tag.exe"
    if ((Get-Item $exe).VersionInfo.ProductVersion -ne $tag) { throw 'PE version mismatch.' }
    $warnings = Get-Content 'build/WetBulbCalculator/warn-WetBulbCalculator.txt'
    if ($warnings -match '^missing module named (core|calculator1|unit|about|batch|cli|gui_smoke) - imported by') { throw 'Missing local module.' }
    # Smoke-test the actual executable from a non-ASCII directory.
    $smokeDir = Join-Path $PSScriptRoot 'dist/中文路径验证'
    New-Item -ItemType Directory -Force $smokeDir | Out-Null
    $smokeExe = Join-Path $smokeDir "WetBulbCalculator-$tag.exe"
    Copy-Item -LiteralPath $exe -Destination $smokeExe -Force
    $report = Join-Path $smokeDir ('smoke-' + [guid]::NewGuid().ToString() + '.json')
    $env:QT_QPA_PLATFORM = 'offscreen'
    $proc = Start-Process -FilePath $smokeExe -ArgumentList @('--smoke-test', ('"' + $report + '"')) -WindowStyle Hidden -PassThru
    if (-not $proc.WaitForExit(120000)) { $proc.Kill(); throw 'Packaged GUI timed out.' }
    if ($proc.ExitCode -ne 0 -or -not (Test-Path $report)) { throw 'Packaged GUI smoke test failed.' }
    $result = Get-Content $report -Raw | ConvertFrom-Json
    if ($result.version -ne $tag -or $result.batch -ne 'ok') { throw 'Smoke report mismatch.' }
    & $Python scripts/verify_cli.py $cli $tag
    if ($LASTEXITCODE -ne 0) { throw 'Packaged CLI failed.' }
    Copy-Item LICENSE, THIRD_PARTY_NOTICES.md, examples/example.xlsx -Destination dist -Force
    Copy-Item build/THIRD_PARTY_LICENSES.txt -Destination dist -Force
    $assets = @($exe, $cli)
    $hashes = foreach ($asset in $assets) { "$( (Get-FileHash $asset -Algorithm SHA256).Hash.ToLower() )  $(Split-Path $asset -Leaf)" }
    $hashes | Set-Content dist/SHA256SUMS.txt -Encoding utf8
    Write-Host "Built and verified $tag"
} finally { Pop-Location }
