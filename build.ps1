<#
    build.ps1 —— 打包 WetBulbCalculator.exe

    用法：
        pwsh -File build.ps1
        pwsh -File build.ps1 -Python 'D:\pyenv\wb310\Scripts\python.exe'
        $env:WETBULB_BUILD_PYTHON = '...\python.exe'; pwsh -File build.ps1

    ────────────────────────────────────────────────────────────────────────
    唯一的坑：**解释器必须在纯 ASCII 路径下**

    PySide2 把自己的包目录交给 Qt 时要经过一次窄字符(ANSI)转换，非 ASCII 路径会被
    写成 "???"。PyInstaller 的 Qt 钩子会读 QLibraryInfo.PluginsPath，拿到那个坏路径后
    直接报：

        Exception: Qt plugin directory 'D:/.../???/.../PySide2/plugins' does not exist!

    实测两点（都是踩过才写下来的）：
      · 给 PyInstaller 设 QT_PLUGIN_PATH **没用** —— 那个变量只影响 Qt 运行时的插件加载，
        不影响 QLibraryInfo 返回什么。程序启动那一次能用它绕过去，打包这一次不行。
      · **项目目录是不是中文无所谓**，只要解释器在 ASCII 路径下就能打包成功。
        所以本项目目录里的 .venv-build（路径含"晴雨表"）不能用来打包，
        本脚本会自动跳过它。

    另外：PyInstaller 的产物**不是逐位可复现**的（不同构建路径/时间会让 SHA256 不同），
    所以 release 说明里的哈希只能用来核对"你下载到的就是当次构建的那个文件"，
    不能用来核对"两次构建结果相同"。
#>
[CmdletBinding()]
param(
    [string]$Python = $env:WETBULB_BUILD_PYTHON,
    [string]$Name   = 'WetBulbCalculator'
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

# ------------------------------------------------------- 1) 找一个合格的解释器
Write-Step '寻找打包解释器（必须在纯 ASCII 路径下，且装齐依赖 + NumPy 1.x）'
$probe = 'import importlib.util as u, sys; ' +
         'mods=("PySide2","qfluentwidgets","matplotlib","pandas","numpy","openpyxl","PyInstaller");' +
         'ok=all(u.find_spec(m) for m in mods);' +
         'import numpy as n; ok = ok and n.__version__.split(".")[0]=="1";' +
         'print("READY" if ok else "MISSING", sys.version.split()[0])'

$candidates = @()
if ($Python) { $candidates += $Python }
$candidates += @(
    (Join-Path $root '.venv-build\Scripts\python.exe'),
    'D:\dsh\init\.venv-qyb310\Scripts\python.exe'
)

$py = $null
foreach ($c in $candidates) {
    if (-not $c -or -not (Test-Path $c)) { continue }
    $full = (Resolve-Path $c).Path
    if ($full -match '[^\x00-\x7F]') {
        Write-Host "    跳过（解释器路径含非 ASCII，会触发上面那个坑）：$full" -ForegroundColor DarkYellow
        continue
    }
    $out = (& $full -c $probe 2>&1 | Select-Object -Last 1)
    if ("$out" -like 'READY*') { $py = $full; Write-Host "    使用 $full   ($out)" -ForegroundColor Green; break }
    Write-Host "    跳过（依赖不全）：$full  -> $out" -ForegroundColor DarkYellow
}
if (-not $py) {
    throw @"
找不到合格的打包解释器。做法：
  1) 建一个**纯 ASCII 路径**下的 Python 3.10 环境，例如：
       D:\pyenv\wb310
     （注意：项目目录里的 .venv-build 不行——它的路径含"晴雨表"）
  2) 在该环境里：
       python -m pip install -r requirements.txt pyinstaller
  3) 再跑本脚本，或指定：
       pwsh -File build.ps1 -Python 'D:\pyenv\wb310\Scripts\python.exe'
"@
}

Push-Location $root
try {
    # --------------------------------------------------- 2) 先自证代码是绿的
    # 测试只需要 pytest + 标准库（不需要 PySide2），所以单独挑一个能跑 pytest 的解释器：
    # 打包环境里通常没有 pytest，这不该成为打包的阻碍。
    Write-Step '先跑一遍检查（不要打包一个自己都没验过的树）'
    $testPy = $null
    foreach ($c in @($py, 'python', 'py')) {
        if (-not $c) { continue }
        try {
            $v = & $c -c 'import pytest; print("PYTEST_OK", pytest.__version__)' 2>&1 | Select-Object -Last 1
        } catch { continue }
        if ("$v" -like 'PYTEST_OK*') { $testPy = $c; break }
    }
    if ($testPy) {
        & $testPy -m pytest -q 2>&1 | Select-Object -Last 3 | ForEach-Object { Write-Host "    $_" }
        if ($LASTEXITCODE -ne 0) { throw '测试未通过，已中止打包。' }
    } else {
        Write-Host '    警告：本机找不到可跑 pytest 的解释器，跳过测试步骤。' -ForegroundColor Yellow
        Write-Host '    （请务必先手工执行 pwsh -File run_tests.ps1 —— 别打包一个没验过的树）' -ForegroundColor Yellow
    }

    # --------------------------------------------------- 3) 打包
    Write-Step "开始打包 $Name.exe"
    & $py -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name $Name `
        --icon assets/app.ico `
        --add-data "assets/app.ico;assets" `
        --add-data "assets/err.ico;assets" `
        --add-data "assets/cfg.json;assets" `
        main.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 打包失败。' }

    $exe = Join-Path $root "dist\$Name.exe"
    if (-not (Test-Path $exe)) { throw "没有找到产物：$exe" }

    Write-Step '打包结果'
    $f = Get-Item $exe
    Write-Host ("    路径   : {0}" -f $f.FullName) -ForegroundColor Green
    Write-Host ("    大小   : {0:N2} MB ({1} 字节)" -f ($f.Length / 1MB), $f.Length)
    Write-Host ("    SHA256 : {0}" -f (Get-FileHash $exe -Algorithm SHA256).Hash)

    Write-Host ''
    Write-Host '提醒 —— 这两道闸只能人工过（脚本替不了你）：' -ForegroundColor Yellow
    Write-Host '  1) 双击 dist\WetBulbCalculator.exe，三种模式各算一次，再试一次批量计算'
    Write-Host '  2) 把它复制到一个**含中文的文件夹**里再双击一次（v1.3.1 修过 B-21，应能启动）'
}
finally {
    Pop-Location
}
