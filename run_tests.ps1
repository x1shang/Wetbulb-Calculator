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

Step '计算核心正确性验证（对照公开参考值）' {
    python -m pytest -q
}

Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host "有 $($failed.Count) 项检查未通过：$($failed -join '、')" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "全部检查通过。" -ForegroundColor Green
Pop-Location
exit 0
