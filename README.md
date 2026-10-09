# WetBulb Calculator (湿球计算器)

> 科研级气象参数计算工具 | 支持 14 种国际公式 | 可视化迭代过程 | 支持批量计算

![tests](https://github.com/x1shang/Wetbulb-Calculator/actions/workflows/tests.yml/badge.svg)

[English version →](README.en.md)

开发团队：RDFZ 降水相态研究性学习小组

---

## ⚡ 30 秒试一下

不用装 Python、不用开界面。到 [Releases](https://github.com/x1shang/Wetbulb-Calculator/releases) 下载
**`WetBulbCLI-*.exe`**（约 6.5 MB，**零第三方依赖**），然后一条命令：

```powershell
.\WetBulbCLI-v1.3.4.exe --mode rh --temperature 25 --value 60
```

输出是 JSON（25 ℃ / 相对湿度 60 %，**逐公式**给出露点与湿球）：

```json
{"version": "v1.3.4", "mode": "rh", "results": [
  {"method": "Goff-水面",   "result1": 16.7003, "result2": 19.5488},
  {"method": "Wexler-水面", "result1": 16.7011, "result2": 19.5490},
  {"method": "Buck-水面",   "result1": 16.6993, "result2": 19.5497},
  {"method": "Gili-水面",   "result1": 16.6998, "result2": 19.5504},
  {"method": "Goff-冰面",   "result1": "不适用", "result2": null}
]}
```

（`Gili-水面` 即**纪利公式**，属中文给排水/冷却塔工程式，原文见
[精度与参考文献](docs/精度与参考文献.md)。超出注册域的公式保留 `"不适用"`。）

`--mode` 换成 `dewpoint` / `wetbulb` 就是另外两种模式；`--help` 看全部参数；错误输入会写入 stderr 并返回退出码 2。

**想先确认它算得准不准？** → [`docs/精度与参考文献.md`](docs/精度与参考文献.md)：14 条公式在各自注册区间上的实测偏差表、五方独立参照（IAPWS-95 / Murphy & Koop 2005 / WMO 表 / ASHRAE / Stull 2011）、以及**明写的已知局限**。

**算得不对、或想加一条公式？** → [开一个 Issue](https://github.com/x1shang/Wetbulb-Calculator/issues/new/choose)，模板会问我要的四件事（场景 / 期望值与依据 / 实际结果 / 版本）。能复现的算例我会直接加进 `tests/` 当回归用例。

---

## 项目简介
湿球计算器是一款基于气象学公式的图形化工具，用于计算湿球温度、露点温度及相关气象参数。支持多种饱和水蒸气压力计算公式，提供单位转换、迭代过程可视化及详细参数分析功能。
本项目作为我们降水相态的温度廓线研究的子项目，为主项目提供了强大的技术支持。提供本软件即旨在提供各类气象学研究的得力工具。

## 🔥 不只是一个湿球计算器。

- **三种模式**：已知露点求湿球、已知湿球求露点、已知相对湿度求两者。
- **14 种公式**：支持单位转换、迭代可视化与扩展参数。
- **批量计算**：Excel 输入，非法行显示错误单元格，其他行继续计算。
- **命令行接口**：无需打开 GUI，输出 JSON，便于脚本集成。

计算范围、实测精度、定义差异及参考文献统一见 [精度与参考文献](docs/精度与参考文献.md)。
历史版本变化见 [项目编年史](docs/项目编年史.md)。

---

## 安装与运行

从 [Releases](https://github.com/x1shang/Wetbulb-Calculator/releases) 下载正式版。
GUI 资产为 `WetBulbCalculator-v1.3.4.exe`，命令行资产为 `WetBulbCLI-v1.3.4.exe`。
同页提供 `example.xlsx`、LICENSE、第三方声明和 SHA256SUMS.txt。

### 1.3.4 更新内容！

- **更正**：查得「纪利公式」（原误称"吉利公式"）的原始文献，并更正 v1.3.1 对该式的根因记述——
  真正的错是指数常数被抄成原文的 1/10，**前因子 980.66 本来就对**。
- **新增**：纪利公式适用域上界 20 ℃ → **120 ℃**（下界仍为 −10 ℃），20~120 ℃ 现在会给出结果。
  本版**唯一的行为变更，且是纯新增**（没有温度失去可用性）。
- **未改数值**：本版没有任何数值修复；已逐点对拍 v1.3.3（14 条公式 × 701 点，0 处不同）。
- **验证**：新增纪利公式与 Goff-Gratch 在各自参考点上的自洽性断言。
- **文档**：精度与参考文献补全书目与证据等级，编年史新增 2026-10 出处复核一节。

### 源码运行

GUI 使用 **Python 3.10**；核心与 CLI 无第三方依赖，CI 验证 Python 3.10 / 3.12。

```powershell
python -m pip install -r requirements.txt
python main.py
```

Fluent Widgets 用于按钮、输入框、提示条等控件，必须安装；`colorthief` 和 `scipy` 已显式列入依赖。

### 命令行

```powershell
python main.py --cli --mode rh --temperature 25 --value 60 --pressure 1013.25
python src/cli.py --mode dewpoint --temperature 25 --value 15
.\WetBulbCLI-v1.3.4.exe --mode wetbulb --temperature 25 --value 20
```

`--mode` 表示已知量：`dewpoint`（露点）、`wetbulb`（湿球）或 `rh`（相对湿度）。
温度为 ℃，压力为 hPa，RH 为百分数。可用 `--method "Goff-水面"` 只输出一种公式。
JSON 包含版本、模式及逐公式结果；`rh` 模式的 result1/result2 分别为露点/湿球，其余模式 result1 为所求温度。
不适用的公式保留文字状态；输入错误写入 stderr 并返回退出码 2，成功返回 0。`--version` 查看版本。

---

## 批量计算使用方法

1. 将下载的 `example.xlsx` 放在 exe 同一目录；源码运行时放在项目根目录。
2. 第一行保留 A、B、C 表头；依次填干球温度、当前模式的已知量和大气压强。
3. 在 GUI 选择模式与单位，点击批量计算。

目录中保留一个输入 xlsx；`result_` 与 `~$` 开头的文件会被忽略。
结果另存为 `result_原文件名.xlsx`，同名结果再次计算时会覆盖；输入文件不变。
输出追加结果列，非法行写入 `#VALUE!` 和“错误”原因列。采用 Goff 水面（干球 ≥0 ℃）或冰面公式。
整表完成后才写盘，中途退出需重跑。

---

## 开发与验证

```powershell
python -m pip install -r requirements-dev.txt
pwsh -File run_tests.ps1
```

核心测试比较外部参照；Windows CI 另装完整依赖并强制执行 GUI 测试。
本地缺少 GUI 环境时会明确跳过；可设置 `WETBULB_GUI_PYTHON` 指向 Python 3.10。
自动检查覆盖窗口构造、三种计算模式、批量文件与非法行；视觉效果仍需人工检查。

### 打包与发布

在 **ASCII 路径**的 Python 3.10 环境安装构建依赖：

```powershell
python -m pip install -r requirements-build.txt
$env:WETBULB_BUILD_PYTHON = (Get-Command python).Source
pwsh -File build.ps1
```

`WetBulbCalculator.spec` 入库维护。构建先运行测试，再生成版本指纹，最后验证实际 exe 并输出 SHA256。
依赖和构建工具固定关键版本；不承诺不同路径或时间的产物逐字节相同。

发布顺序：commit → 新 tag → push → 检查 tests/release 工作流 → Release。
`core.tag` 必须与 tag 一致；发布任务只在构建测试通过后上传资产。
每版使用新 tag，通常不移动；历史重写例外见编年史。
Release 说明维护在 [RELEASE_NOTES.md](RELEASE_NOTES.md)。构建产物不提交到 Git。

### 目录结构

```text
main.py             GUI 入口与 CLI 分流
src/core.py         零依赖计算核心
src/cli.py          JSON 命令行
src/batch.py        共享 Excel 计算
src/ui/            界面
assets/ examples/  资源与样表
tests/             核心、CLI、GUI 与批量回归
docs/              科学依据与历史
```

---

## 声明

本项目使用 [MIT LICENSE](LICENSE)。第三方依赖及其许可证见 [第三方声明](THIRD_PARTY_NOTICES.md)。
转发时请注明项目出处；科学计算结果应结合适用范围与独立验证使用。

> 🌈 科学计算从未如此优雅 | 让复杂的气象参数触手可及
