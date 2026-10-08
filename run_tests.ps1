<#
    run_tests.ps1 —— 本地一键跑全部检查（CI 的前置条件）。
    用法：  pwsh -File run_tests.ps1
    退出码：0 = 全绿；非 0 = 有检查失败。

    为什么要有这个脚本：CI 的价值在于"不用人记得跑"，但本地一键脚本
    比 CI 更早交付价值 —— 提交前先跑一遍，就不会把红的推上去。
#>
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Push-Location $root
$failed = @()

# B-22：控制台是 cp936 时，子进程写出的中文（'℃' 等）会被按 GBK 编码，
# 若父进程按 UTF-8 读就会得到乱码 —— 曾经让 GUI 回归在本机恒红、在 CI 恒绿。
# 这里把整条链路的编码固定成 UTF-8（测试侧还额外改成读 UTF-8 JSON 文件，双保险）。
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

function Step($name, $block) {
    Write-Host ""
    Write-Host "==> $name" -ForegroundColor Cyan
    & $block
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    [失败] $name（退出码 $LASTEXITCODE）" -ForegroundColor Red
        $script:failed += $name
    } else {
        Write-Host "    [通过] $name" -ForegroundColor Green
    }
}

Step '语法检查（含 GUI 入口）' {
    python -m py_compile main.py src/core.py src/ui/calculator1.py src/ui/unit.py src/ui/about.py legacy/sample.py
}

Step '静态检查（未定义名/未使用导入）' {
    python -m pyflakes main.py src/core.py
}

Step '计算核心等价性回归' {
    python src/core.py
}

Step '计算核心正确性验证 + GUI 回归（对照公开参考值）' {
    # -rs：把每个 skip 的原因打出来。GUI 三条测试在没有 PySide2 的机器上会 skip，
    # 而"skip 了却只看总绿"正是 B-23 —— 所以这里把跳过的事实显式捞出来。
    $out = & python -m pytest -q -rs 2>&1
    $out | Select-Object -Last 15 | ForEach-Object { Write-Host "    $_" }
    $script:hadSkip = [bool]($out | Select-String -Pattern '\d+ skipped' -Quiet)
}

Write-Host ""
if ($hadSkip) {
    Write-Host "注意：本次有测试被 skip。" -ForegroundColor Yellow
    Write-Host "      GUI 三条（import main / offscreen 窗口构造 / 完整计算流程）只有在装了" -ForegroundColor Yellow
    Write-Host "      PySide2 + NumPy 1.x 的 Python ≤3.10 环境里才真的跑；CI 上必然 skip。" -ForegroundColor Yellow
    Write-Host "      也就是说：这里的「绿」不包含 GUI 覆盖（README「已知限制」第 8 条）。" -ForegroundColor Yellow
    Write-Host "      要补上，把 WETBULB_GUI_PYTHON 指向那个解释器再跑一次。" -ForegroundColor Yellow
}
if ($failed.Count -gt 0) {
    Write-Host "有 $($failed.Count) 项检查未通过：$($failed -join '、')" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "全部检查通过。" -ForegroundColor Green
Pop-Location
exit 0
