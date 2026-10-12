# -*- coding: utf-8 -*-
"""界面层的跨实现对拍（tests/test_web_ui_parity.py）。

【为什么还要一条测试 —— tests/test_web_parity.py 不是已经对拍了吗】
    那条对拍的是 **计算内核**（web/src/core.js ↔ src/core.py）。但用户看到的数字
    还要经过另一层：**单位换算**与**批量规则**。这两层分别在
        main.py 的 changetemp/tempchange/changepre/prechange + UnitDialog.update_units
        src/batch.py 的列约定与 #VALUE! 规则
    与
        web/src/ui.js 的 toCelsius/fromCelsius/toHpa/fromHpa + PRESSURE_UNITS/TEMP_UNITS
        web/src/ui.js 的 runBatch / batchOutputTable
    里**各写了一遍**，而它们之间没有任何自动检查。

    这不是假想的风险：2026-10 的第三方复核正是从这一层找出三处不一（批量导出数值截到
    4 位小数、丢掉 A/B/C 之外的列、#VALUE! 写成文本），核心里一处都没有。单位换算尤其
    危险——系数写错时**核心仍然完全正确**，只有用户看到的数字是错的，而 core 对拍
    永远发现不了。

【本文件怎么比】
    两边是不同语言，不能互相 import，所以这里做**源码扫描**：从两份源码里抽出
    常量、区间与规则字面量再比对。这类测试的价值全在"改了一边忘了另一边时会不会红"，
    因此断言要落在**数值与字面量**上，不要落在格式与注释上。
"""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(ROOT, 'main.py')
BATCH_PY = os.path.join(ROOT, 'src', 'batch.py')
UI_JS = os.path.join(ROOT, 'web', 'src', 'ui.js')
SHELL_HTML = os.path.join(ROOT, 'web', 'src', 'shell.html')


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def _js_func(src, name):
    """取出 `function name(...) { ... }` 的函数体（按大括号配平，够用即可）。"""
    i = src.index('function ' + name + '(')
    j = src.index('{', i)
    depth, k = 0, j
    while k < len(src):
        if src[k] == '{':
            depth += 1
        elif src[k] == '}':
            depth -= 1
            if depth == 0:
                return src[j + 1:k]
        k += 1
    raise AssertionError(f'web/src/ui.js 里 {name} 的花括号不配平')


def _py_func(src, name):
    """取出一个 Python 函数的函数体（含缩进行），到下一个同级或更外层的语句为止。

    不能只按"行首无缩进"判断结束 —— main.py 里这几个换算函数都是**类方法**
    （`def` 缩进 4 格），下一个方法同样缩进 4 格，会被一并吞进来，
    于是"函数里出现过哪些数字"这件事就变成了"类里出现过哪些数字"。
    """
    i = src.index('def ' + name + '(')
    head_indent = len(src[:i].split('\n')[-1])
    j = src.index('\n', i) + 1
    out = []
    for line in src[j:].splitlines():
        if line.strip():
            indent = len(line) - len(line.lstrip())
            if indent <= head_indent:
                break
        out.append(line)
    return '\n'.join(out)


_NUM = re.compile(r'\d+(?:\.\d+)?')


def _numbers(text):
    return sorted({float(x) for x in _NUM.findall(text)})


# ---------------------------------------------------------------------------
# 1) 单位换算的系数
# ---------------------------------------------------------------------------
def test_mmhg_cmhg_factors_are_the_same_number_on_both_sides():
    """1 mmHg = 133.322387415 Pa 是**定义值**，两边必须逐位相同。

    它同时是"公布的区间"与"强制的区间"能不能对上的前提：375 mmHg × 1.33322 = 499.9575
    hPa < 500 会被拒，而对话框刚告诉用户 375 是下限 —— 当年就是因为两边各写了一份
    写死的 1.33322 才出这个矛盾（main.py 顶部注释记着这段历史）。
    """
    main = _read(MAIN_PY)
    ui = _read(UI_JS)

    m = re.search(r'MMHG_HPA\s*=\s*([\d.]+)\s*/\s*([\d.]+)', main)
    assert m, 'main.py 里找不到 MMHG_HPA 的定义'
    u = re.search(r'MMHG_HPA\s*=\s*([\d.]+)\s*/\s*([\d.]+)', ui)
    assert u, 'web/src/ui.js 里找不到 MMHG_HPA 的定义'

    main_val = float(m.group(1)) / float(m.group(2))
    ui_val = float(u.group(1)) / float(u.group(2))
    assert main_val == ui_val, f'MMHG_HPA 不一致：main.py={main_val!r} ui.js={ui_val!r}'
    assert main_val == pytest.approx(1.33322387415, rel=0, abs=0), main_val

    mc = re.search(r'CMHG_HPA\s*=\s*MMHG_HPA\s*\*\s*([\d.]+)', main)
    uc = re.search(r'CMHG_HPA\s*=\s*MMHG_HPA\s*\*\s*([\d.]+)', ui)
    assert mc and uc, '两边都要有 CMHG_HPA = MMHG_HPA * 10'
    assert float(mc.group(1)) == float(uc.group(1)), f'CMHG 倍数不一致：{mc.group(1)} vs {uc.group(1)}'


def test_unit_conversion_functions_use_the_same_numbers():
    """把四个换算函数的函数体里出现的**数值**抽出来比对。

    比"表达式逐字相同"更稳（两边变量名与除法间距本来就不同），又足以在任何人
    改动 273.15 / 32 / 5 / 9 / 100 / 1000 中的任何一个时变红。
    """
    main = _read(MAIN_PY)
    ui = _read(UI_JS)

    py_nums = set()
    for fn in ('changetemp', 'tempchange', 'changepre', 'prechange'):
        py_nums |= set(_numbers(_py_func(main, fn)))
    js_nums = set()
    for fn in ('toCelsius', 'fromCelsius', 'toHpa', 'fromHpa'):
        js_nums |= set(_numbers(_js_func(ui, fn)))

    # 台华氏/开尔文换算与 Pa/bar 的系数，两边都必须正好是这一组
    assert py_nums == {273.15, 32.0, 5.0, 9.0, 100.0, 1000.0}, f'main.py 的换算函数用了 {sorted(py_nums)}'
    assert js_nums == py_nums, (
        f'单位换算用到的数值两边不一致：\n  main.py = {sorted(py_nums)}\n  ui.js   = {sorted(js_nums)}\n'
        '（这是"核心完全正确、只有用户看到的数字错"的那一类改动）')


def test_unit_dialog_ranges_match():
    """设置单位对话框公布的 8 组 (单位, 下限, 上限) 必须逐值相同。"""
    main = _read(MAIN_PY)
    ui = _read(UI_JS)

    block = _py_func(main, 'update_units')
    py_rows = re.findall(r"\('([^']+)',\s*(-?[\d.]+),\s*(-?[\d.]+)\)", block)
    assert len(py_rows) == 8, f'main.py 的 update_units 里应恰好 8 组区间，实际 {len(py_rows)}: {py_rows}'
    py = {unit: (float(a), float(b)) for unit, a, b in py_rows}

    js = {}
    for const in ('PRESSURE_UNITS', 'TEMP_UNITS'):
        line = re.search(r'const ' + const + r'\s*=\s*\{(.*?)\};', ui, re.S)
        assert line, f'web/src/ui.js 里找不到 {const}'
        for unit, a, b in re.findall(r"'?([^'\[\]:,]+)'?\s*:\s*\[(-?[\d.]+),\s*(-?[\d.]+)\]", line.group(1)):
            js[unit.strip()] = (float(a), float(b))

    assert set(py) == set(js), f'单位集合不一致：main.py={sorted(py)} ui.js={sorted(js)}'
    for unit in py:
        assert py[unit] == js[unit], f'{unit} 的公布区间不一致：main.py={py[unit]} ui.js={js[unit]}'
    assert py['mmHg'] == (375.0, 825.0) and py['℉'] == (-238.0, 392.0)


def test_interactive_pressure_domain_matches():
    """交互路径真正强制的压强域（500~1100 hPa）两边必须相同。

    注意它与上面公布的 mmHg 375~825 是**两套口径**：界面按固定的 hPa 域反推。
    两边都刻意保留了这个设计（对话框里的 mmHg 数字是给用户看的换算值），
    所以这里钉的是"两边仍然一致"，不是"设计合理"。
    """
    main = _read(MAIN_PY)
    ui = _read(UI_JS)
    m = re.search(r'UI_P_MIN_HPA\s*,\s*UI_P_MAX_HPA\s*=\s*([\d.]+)\s*,\s*([\d.]+)', main)
    assert m, 'main.py 里找不到 UI_P_MIN_HPA / UI_P_MAX_HPA'
    u = re.search(r'UI_P_MIN_HPA\s*=\s*([\d.]+)\s*,\s*UI_P_MAX_HPA\s*=\s*([\d.]+)', ui)
    assert u, 'web/src/ui.js 里找不到 UI_P_MIN_HPA / UI_P_MAX_HPA'
    assert (float(m.group(1)), float(m.group(2))) == (float(u.group(1)), float(u.group(2))), \
        f'交互压强域不一致：main.py={m.groups()} ui.js={u.groups()}'

    mt = re.search(r'UI_T_MIN_C\s*,\s*UI_T_MAX_C\s*=\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)', main)
    ut = re.search(r'UI_T_MIN_C\s*=\s*(-?[\d.]+)\s*,\s*UI_T_MAX_C\s*=\s*(-?[\d.]+)', ui)
    if mt and ut:
        assert (float(mt.group(1)), float(mt.group(2))) == (float(ut.group(1)), float(ut.group(2))), \
            f'交互温度域不一致：main.py={mt.groups()} ui.js={ut.groups()}'


# ---------------------------------------------------------------------------
# 2) 批量计算的规则
# ---------------------------------------------------------------------------
def test_batch_column_and_result_conventions_match():
    """A/B/C 列约定、结果列名、错误列名、Goff 相态选择、#VALUE!、result_ 前缀。"""
    batch = _read(BATCH_PY)
    ui = _read(UI_JS)

    # A/B/C 三列表头的要求
    assert "('A', 'B', 'C')" in batch, 'src/batch.py 里应要求 A/B/C 表头'
    assert "['A', 'B', 'C']" in ui, 'web/src/ui.js 里应要求 A/B/C 表头'

    # 结果列名随模式变：模式2 两列，其余一列
    assert "('湿球',) if mode == 0 else ('露点',) if mode == 1 else ('露点', '湿球')" in batch
    assert "mode === 0 ? ['湿球'] : mode === 1 ? ['露点'] : ['露点', '湿球']" in ui

    # 错误列名与错误占位
    assert "'错误'" in batch and "error: '错误'" in ui

    # 相态选择：干球 ≥ 0 ℃ 用 Goff 水面，否则 Goff 冰面
    assert "'Goff-水面' if t >= 0 else 'Goff-冰面'" in batch
    assert "t >= 0 ? 'Goff-水面' : 'Goff-冰面'" in ui

    # 输出文件名前缀
    assert "'result_'" in batch or "'result_%s'" in batch or 'result_' in batch
    assert "result_" in ui

    # #VALUE! 的字面量与落位（结果列写它、原因写进「错误」列）
    assert "'#VALUE!'" in batch and "'#VALUE!'" in ui


def test_batch_error_messages_are_reproduced_verbatim():
    """Python 的原生异常文案会**逐字**写进导出文件的「错误」列，网页版必须复刻。

    这几句是用户唯一能看到的诊断；一旦网页版自己另写一套（"格式不正确"之类），
    同一份坏表在两个版本里会给出不同的错误列，而两边看起来都对。
    """
    ui = _read(UI_JS)
    for msg in ("could not convert string to float: '",
                "float() argument must be a string or a real number, not 'NoneType'"):
        assert msg in ui, f'web/src/ui.js 里应逐字复刻 Python 的这句话：{msg}'


def test_about_page_lists_the_known_batch_export_divergences():
    """「关于 → 与桌面版的有意差异」必须写明批量导出的三处不等价。

    这三处是**已知且有意保留**的（见本文件顶部说明）：数值截到 4 位小数、丢掉
    A/B/C 之外的列、#VALUE! 是文本而非 Excel 错误值。它们可以不改，但必须写出来 ——
    这条测试的作用就是让"哪天有人悄悄改掉了其中一条"或"哪天新增了一条却没写进关于页"
    都能被发现。
    """
    about = _read(SHELL_HTML)
    i = about.find('与桌面版的有意差异')
    assert i > 0, 'web/src/shell.html 里找不到「与桌面版的有意差异」清单'
    notice = about[i:i + 4000]

    for key, why in (('4 位小数', '批量导出把结果截到 4 位小数'),
                     ('三列', '批量导出只保留 A/B/C 三列、丢掉其余列'),
                     ('#VALUE!', '网页版写的是文本而不是 Excel 错误值'),
                     ('命令行接口', '网页版没有 CLI')):
        assert key in notice, f'关于页的「有意差异」清单里没写：{why}（找 {key!r}）'
    assert '子集' in notice, '关于页应明确说明"网页版是桌面版的子集"'
