# -*- coding: utf-8 -*-
"""网页版端到端回归（tests/test_web_e2e.py）——用真实 Chromium 打开 file:// 的 web/index.html。

【为什么需要这一层】
    tests/test_web_parity.py 只证明"JS 内核算得和 core.py 一样"。但用户点的是按钮、
    看的是表格 —— 从"输入框里的字符串"到"屏幕上那串数字"之间还有单位换算、校验分支、
    模式切换、渲染这一整条链，任何一环断了都算白算（桌面版 B-07 就是"算完了但界面
    什么都不显示"：异常被兜底 except 吞掉，列表里一行都没有）。

【本机没有 playwright / 浏览器时】
    skip。**注意 skip 与通过不是一回事**：这一层从上线到 2026-10 一直没进 CI，
    结果"强调色取色器 100% 点不动"这种一整块死控件没人发现（数值有
    test_web_parity 守，界面链路当时一条都没守）。现在 .github/workflows/tests.yml
    的 web-e2e job 会装 playwright + chromium 专门跑本文件，所以**在 CI 上它必须真跑**，
    看到 skip 就说明那条流水线坏了。
    本机要真跑：pip install playwright openpyxl && playwright install chromium

【数值锚点不写死】
    期望值一律用 core.py 现算 —— 与桌面版 GUI 回归（test_repo_hygiene）同一套原则：
    改数值时不该同时改测试里的常数。
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, 'src') not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, 'src'))

import core  # noqa: E402

INDEX = os.path.join(ROOT, 'web', 'index.html')


def _playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    return sync_playwright


@pytest.fixture(scope='module')
def browser():
    sp = _playwright()
    if sp is None:
        pytest.skip('本机没有装 playwright，跳过网页版端到端回归')
    if not os.path.exists(INDEX):
        pytest.skip('web/index.html 不存在（请先运行 python scripts/build_web.py）')
    with sp() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:                                  # 浏览器没下载等
            pytest.skip(f'无法启动 Chromium：{exc}')
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    ctx = browser.new_context(viewport={'width': 1480, 'height': 1000}, accept_downloads=True)
    pg = ctx.new_page()
    errors = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.on('console', lambda m: errors.append('console.' + m.type + ': ' + m.text)
          if m.type == 'error' else None)
    pg._wb_errors = errors
    pg.goto('file:///' + INDEX.replace('\\', '/'))
    pg.wait_for_timeout(700)
    yield pg
    ctx.close()


def _flat(text):
    return ' '.join(text.split())


def test_page_loads_without_errors_and_computes(page):
    """打开就该有结果：14 行、首行是 Goff-水面、数值与 core.py 一致。"""
    assert not page._wb_errors, f'页面报错：{page._wb_errors}'

    rows = page.eval_on_selector_all('#results-body tr', 'els => els.length')
    assert rows == len(core.FORMULAS), f'结果表应有 {len(core.FORMULAS)} 行，实际 {rows}'

    want = {r['method']: r['result1'] for r in core.calculate_wetbulb(15, 25, 15)}['Goff-水面']
    first = _flat(page.eval_on_selector('#results-body tr:nth-child(1)', 'el => el.innerText'))
    assert 'Goff-水面' in first
    assert f'{want:.4f}' in first, f'首行显示的湿球温度与 core.py 的 {want:.4f} 不一致：{first}'
    assert 'ok' in first

    # 迭代图必须真的画出来了（桌面版那张 matplotlib 图的等价物）
    assert page.eval_on_selector_all('#chart-host path[stroke-width="2"]', 'els => els.length') > 0
    assert page.eval_on_selector_all('#chart-legend .legend-item', 'els => els.length') > 0


def test_three_modes_and_status_texts(page):
    """三种模式的表头、结果与状态文案；不适用/异常的条数要能对上 core.py。"""
    # 模式 2：25 ℃ / 60% —— 与 README 的例子同一组数
    page.click('.segmented button[data-mode="2"]')
    page.wait_for_timeout(200)
    page.fill('#in-dry', '25'); page.fill('#in-other', '60'); page.fill('#in-pressure', '1013.25')
    page.click('#btn-calc'); page.wait_for_timeout(400)
    head = _flat(page.eval_on_selector('#results-table thead', 'el => el.innerText'))
    assert '露点温度' in head and '湿球温度' in head, head
    both = {r['method']: r for r in core.calculate_both(25, 25, 60)}['Goff-水面']
    first = _flat(page.eval_on_selector('#results-body tr:nth-child(1)', 'el => el.innerText'))
    assert f'{both["result1"]:.4f}' in first and f'{both["result2"]:.4f}' in first, first

    # 模式 1：已知湿球求露点 —— 表头是露点，且迭代区隐藏（桌面版行为）
    page.click('.segmented button[data-mode="1"]')
    page.wait_for_timeout(200)
    assert page.eval_on_selector('#iteration-box', "el => el.classList.contains('hidden')"), \
        '模式 1 应隐藏迭代区（与桌面版一致）'
    page.fill('#in-dry', '25'); page.fill('#in-other', '20'); page.fill('#in-pressure', '1013.25')
    page.click('#btn-calc'); page.wait_for_timeout(400)
    want = {r['method']: r['result1'] for r in core.calculate_dewpoint(25, 20, 1013.25)}['Goff-水面']
    first = _flat(page.eval_on_selector('#results-body tr:nth-child(1)', 'el => el.innerText'))
    assert f'{want:.4f}' in first, first

    # 冰面公式在暖端必须写"不适用"（注册域上界 0 ℃），而不是给个数
    na = page.eval_on_selector_all('#results-body tr.row-na td.method',
                                   'els => els.map(e => e.innerText.trim())')
    assert any('冰面' in m for m in na), f'25 ℃ 时冰面公式应判不适用，实际不适用的是 {na}'


def test_derived_panel_matches_core(page):
    """点结果行 → 24 项派生量，抽查几个与 core.derive_moist_air 对得上。"""
    page.click('#results-body tr:nth-child(1)')
    page.wait_for_timeout(400)
    items = page.eval_on_selector_all('#derived-host .kv', 'els => els.length')
    assert items >= 24, f'派生量面板应有 ≥24 项，实际 {items}'

    d = core.derive_moist_air(25.0, 18.5958, 15.0, 0.5382, 1013.25, 'Goff-水面')
    text = _flat(page.eval_on_selector('#derived-host', 'el => el.innerText'))
    assert f'{d["han"]:.2f}' in text, f'焓值 {d["han"]:.2f} 没出现在派生量面板里'
    assert f'{d["absolute_humidity"]:.3f}' in text
    assert 'lcl' in text


def test_unit_switch_converts_displayed_values(page):
    """切到 K + mmHg：显示值要按新单位换算，占位符与区间提示也要跟着变。"""
    page.click('#btn-units'); page.wait_for_timeout(300)
    page.click("label.radio-card:has(input[value='K'])")
    page.click("label.radio-card:has(input[value='mmHg'])")
    page.click('#btn-units-ok'); page.wait_for_timeout(500)
    assert page.eval_on_selector('#chip-units', 'el => el.innerText').replace(' ', '') == 'K·mmHg'
    assert page.eval_on_selector('#in-dry', 'el => el.placeholder') == '123.15~473.15K'
    assert page.eval_on_selector('#in-pressure', 'el => el.placeholder') == '375~825mmHg'

    # 25 ℃ → 298.15 K：湿球 18.5958 ℃ 应显示为 291.7458 K
    want_k = 18.5958 + 273.15
    page.fill('#in-dry', '25'); page.fill('#in-other', '15'); page.fill('#in-pressure', '760')
    page.click('#btn-calc'); page.wait_for_timeout(400)
    first = _flat(page.eval_on_selector('#results-body tr:nth-child(1)', 'el => el.innerText'))
    assert f'{want_k:.4f}' in first, f'K 单位下的显示值不对：{first}'


def test_input_validation_matches_desktop_messages(page):
    """输入校验的文案要与 main.py 的 check_input 一致（这几句是用户唯一能看到的诊断）。"""
    page.click('#btn-clear'); page.wait_for_timeout(150)
    page.fill('#in-dry', '25'); page.fill('#in-other', '30'); page.fill('#in-pressure', '1013.25')
    page.click('#btn-calc'); page.wait_for_timeout(300)
    assert '露点温度不能高于干球温度！' in _flat(page.eval_on_selector_all('.toast .t-msg',
                                                                      'els => els.map(e => e.innerText)')[-1])

    page.fill('#in-other', '60%'); page.click('#btn-calc'); page.wait_for_timeout(250)
    last = _flat(page.eval_on_selector_all('.toast .t-msg', 'els => els.map(e => e.innerText)')[-1])
    assert '必须是有效数字' in last and '60%' in last, last

    # 科学计数法：这一条钉的是桌面版 v1.3.2 修掉的"校验的是过滤掉非数字字符的串、
    # 算的是原文本"。当年的做法会把 '1e3' 过滤成 '13' 去校验（于是按 13 放行或误报），
    # 计算时却按 1000 算。现在校验的必须是同一个数：
    #   · '1e3' = 1000 ℃ → 超 [−150, 200] 区间，应报**范围**错误（而不是"必须是有效数字"）；
    #   · '1.5e1' = 15 ℃ → 应当正常算出结果。
    page.fill('#in-other', '1e3'); page.click('#btn-calc'); page.wait_for_timeout(250)
    last = _flat(page.eval_on_selector_all('.toast .t-msg', 'els => els.map(e => e.innerText)')[-1])
    assert '必须是有效数字' not in last, f'1e3 被当成非法文本了：{last}'
    assert '范围内' in last and '200.00' in last, f'1e3=1000 ℃ 应报区间错误，实际：{last}'

    page.fill('#in-dry', '25'); page.fill('#in-other', '1.5e1'); page.fill('#in-pressure', '1013.25')
    page.click('#btn-calc'); page.wait_for_timeout(400)
    want = {r['method']: r['result1'] for r in core.calculate_wetbulb(15, 25, 15)}['Goff-水面']
    row = _flat(page.eval_on_selector('#results-body tr:nth-child(1)', 'el => el.innerText'))
    assert f'{want:.4f}' in row, f'1.5e1（=15）没算出与 core.py 一致的结果：{row}'


def test_self_test_runs_and_reports_zero_deviation(page):
    """页内数值自检：351 项与 core.py 生成的黄金向量对拍，必须 0 处超差。"""
    page.click('#btn-selftest')
    page.wait_for_timeout(900)
    summary = page.eval_on_selector('#selftest-summary', 'el => el.innerText')
    assert '0 处超差' in summary, f'数值自检未通过：{summary}'
    rows = page.eval_on_selector_all('#selftest-host .st-row', 'els => els.map(e => e.innerText)')
    assert len(rows) >= 5, rows
    assert all('全部一致' in r for r in rows), rows


def test_batch_import_csv_marks_bad_rows(page, tmp_path):
    """批量：A/B/C 表头、合法行给值、非法行 #VALUE! + 原因（对齐 src/batch.py 的规则）。"""
    csv = 'A,B,C\n25,15,1013.25\n0,-5,1013.25\nabc,15,1013.25\n'
    f = tmp_path / 'in.csv'
    f.write_text(csv, encoding='utf-8')
    page.click('#tab-batch'); page.wait_for_timeout(200)
    page.set_input_files('#file-input', str(f))
    page.wait_for_timeout(1200)

    assert page.eval_on_selector('#stat-total', 'el => el.innerText') == '3'
    assert page.eval_on_selector('#stat-ok', 'el => el.innerText') == '2'
    assert page.eval_on_selector('#stat-bad', 'el => el.innerText') == '1'
    body = page.eval_on_selector('#batch-body', 'el => el.innerText')
    assert '#VALUE!' in body and "could not convert string to float: 'abc'" in body

    # 数值必须与 core.py 一致（批量用的是 Goff-水面 / 冰面二选一）
    want = {r['method']: r['result1'] for r in core.calculate_wetbulb(15, 25, 15)}['Goff-水面']
    assert f'{want:.4f}' in body, body


def test_batch_xlsx_export_is_readable(page, tmp_path):
    """导出的 xlsx 要能被 openpyxl 打开（网页版自己写的 zip/xml 必须真的合规）。"""
    openpyxl = pytest.importorskip('openpyxl')
    csv = 'A,B,C\n25,15,1013.25\n30,20,1000\n'
    f = tmp_path / 'in.csv'
    f.write_text(csv, encoding='utf-8')
    page.click('#tab-batch'); page.wait_for_timeout(200)
    page.set_input_files('#file-input', str(f))
    page.wait_for_timeout(1000)
    with page.expect_download() as dl:
        page.click('#btn-batch-xlsx')
    out = tmp_path / 'out.xlsx'
    dl.value.save_as(str(out))
    assert dl.value.suggested_filename == 'result_in.xlsx', dl.value.suggested_filename

    wb = openpyxl.load_workbook(str(out))
    ws = wb.active
    head = [c.value for c in ws[1]]
    assert head[:4] == ['干球℃', '露点℃', '大气hPa', '湿球℃'], head
    assert head[4] == '错误'
    want = {r['method']: r['result1'] for r in core.calculate_wetbulb(15, 25, 15)}['Goff-水面']
    assert abs(float(ws.cell(2, 4).value) - want) < 1e-3


def test_share_link_replays_inputs(page, browser):
    """分享链接：新开页面打开带 #calc?... 的地址，输入、单位、精度、初值都要还原。"""
    ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
    pg = ctx.new_page()
    pg.goto('file:///' + INDEX.replace('\\', '/') + '#calc?m=2&t=30&o=80&p=1000&tol=9&st=Tn')
    pg.wait_for_timeout(900)
    # 分段按钮的文字里有 <br>（"已知相对<br>湿度"），所以按"去掉所有空白"来比
    mode_text = ''.join(pg.eval_on_selector('.segmented button[aria-pressed="true"]',
                                            'el => el.innerText').split())
    assert mode_text == '已知相对湿度', mode_text
    assert pg.eval_on_selector('#in-dry', 'el => el.value') == '30'
    assert pg.eval_on_selector('#in-other', 'el => el.value') == '80'
    assert pg.eval_on_selector('#tol-readout', 'el => el.innerText') == '1e-9'
    assert pg.eval_on_selector('#in-strategy', 'el => el.value') == 'Tn'
    row = _flat(pg.eval_on_selector('#results-body tr:nth-child(1)', 'el => el.innerText'))
    want = {r['method']: r for r in core.calculate_both(30, 30, 80, 1000)}['Goff-水面']
    assert f'{want["result1"]:.4f}' in row and f'{want["result2"]:.4f}' in row, row
    ctx.close()


def test_no_horizontal_overflow_and_glass_applied(page):
    """版式体检：不出现横向滚动条；玻璃效果确实生效（而不是退化成一层灰）。"""
    assert page.evaluate('document.documentElement.scrollWidth - window.innerWidth') <= 1
    blurred = page.evaluate("""
        [...document.querySelectorAll('.glass')].filter(e => {
          const s = getComputedStyle(e);
          return (s.backdropFilter || s.webkitBackdropFilter || '').includes('blur');
        }).length""")
    total = page.evaluate("document.querySelectorAll('.glass').length")
    assert total > 6 and blurred == total, f'{blurred}/{total} 个玻璃面没有 backdrop-filter'
    # 强调色来自 cfg.json 的默认值（71, 148, 157）—— 与桌面版同一个品牌色
    assert page.eval_on_selector('#accent-input', 'el => el.value') == '#47949d'


def test_no_external_requests_page_is_self_contained(page):
    """单文件必须真的自给自足：不能有外链脚本/样式/字体（离线可用是硬要求）。"""
    html = open(INDEX, encoding='utf-8').read()
    for bad in ('<script src=', '<link rel="stylesheet"', 'analytics', 'cdn.'):
        assert bad not in html, f'index.html 里出现了外部依赖：{bad}'
    assert 'http://' not in html.replace('http://www.w3.org', '').replace('http://schemas.', ''), \
        'index.html 里出现了 http:// 外部地址（除了 XML 命名空间）'


def test_single_file_still_works_when_copied_elsewhere(browser, tmp_path):
    """把 index.html 单独拷到别处（模拟"发到群里/邮件附件"）仍要能算。

    这一条防的是"其实偷偷依赖同目录的某个文件"——那类依赖在开发时看不出来，
    一旦用户只保存了 html 就整页失效。
    """
    import shutil
    copy = tmp_path / 'wetbulb.html'
    shutil.copyfile(INDEX, str(copy))
    ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
    pg = ctx.new_page()
    errors = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.goto('file:///' + str(copy).replace('\\', '/'))
    pg.wait_for_timeout(900)
    assert not errors, f'单独拷出去后页面报错：{errors}'
    rows = pg.eval_on_selector_all('#results-body tr', 'els => els.length')
    assert rows == len(core.FORMULAS), f'拷贝后没有算出结果（{rows} 行）'
    page_selftest = pg.eval_on_selector('#chip-web-version', 'el => el.innerText')
    assert 'v2.0.0' in page_selftest, page_selftest
    ctx.close()


def test_accent_picker_actually_applies(page):
    """强调色取色器必须真的能改色（回归：曾经 100% 点不动）。

    2026-10 第三方复核发现：web/src/ui.js 的取色器回调里写了
        const r = ..., g2 = ..., b = ...;
        applyAccent(r + ', ' + g + ', ' + b);     ← g 未定义
    'use strict' 下每次拖动抛 ReferenceError，强调色纹丝不动，而当时 e2e 里
    **没有任何一条用例碰过这个控件**，所以整套测试一直全绿。这条就是补上那个盲点：
    它同时断言"没报错"和"颜色真的变了"——只看其中一个都拦不住这个 bug。
    """
    page.click('#btn-units')
    page.wait_for_timeout(350)
    before = page.eval_on_selector('html', "el => getComputedStyle(el).getPropertyValue('--accent')").strip()
    assert before == '71, 148, 157', before

    page.eval_on_selector('#accent-input', """el => {
        el.value = '#d94f4f';
        el.dispatchEvent(new Event('input', {bubbles: true}));
    }""")
    page.wait_for_timeout(350)

    assert not [e for e in page._wb_errors if 'pageerror' in e], \
        f'拖动取色器时页面报错：{page._wb_errors}'
    after = page.eval_on_selector('html', "el => getComputedStyle(el).getPropertyValue('--accent')").strip()
    assert after == '217, 79, 79', f'强调色没跟着取色器变：{before} → {after}'
    assert page.eval_on_selector('#accent-readout', 'el => el.innerText').strip() == 'rgb(217, 79, 79)'
    # --accent-2（渐变亮部）与 --accent-text（当文字用的一支）都要跟着重算
    assert page.eval_on_selector('html', "el => getComputedStyle(el).getPropertyValue('--accent-2')").strip() \
        == '233, 153, 153'

    page.click('#btn-accent-reset')
    page.wait_for_timeout(300)
    assert page.eval_on_selector('html', "el => getComputedStyle(el).getPropertyValue('--accent')").strip() \
        == '71, 148, 157', '「恢复默认」没有回到品牌色'


def test_iteration_chart_axis_stays_in_celsius(page):
    """迭代图的纵轴与悬浮读数必须写死 ℃，不跟随上方温标（回归：曾经三处自相矛盾）。

    曲线数据来自 core.js 的 _solve_wetbulb，恒为 ℃。曾经的写法是"轴标题拼 state.tempUnit、
    悬浮读数按 fromCelsius 换算"，于是切到 ℉ 之后：轴标题说 ℉、刻度数字是 ℃、读数是 ℉。
    现在一律写死 ℃，与桌面版 plt.ylabel('温度估计值 (°C)') 的行为一致。
    """
    page.click('#btn-units')
    page.wait_for_timeout(350)
    page.click("label.radio-card:has(input[value='℉'])")
    page.click('#btn-units-ok')
    page.wait_for_timeout(400)
    assert '℉' in page.eval_on_selector('#chip-units', 'el => el.innerText')

    page.fill('#in-dry', '77')          # 77 ℉ = 25 ℃
    page.fill('#in-other', '15')
    page.fill('#in-pressure', '1013.25')
    page.click('#btn-calc')
    page.wait_for_timeout(600)

    titles = page.eval_on_selector_all('#chart-host text', 'els => els.map(e => e.textContent)')
    assert '温度估计值 (℃)' in titles, f'纵轴标题不是写死的 ℃：{titles}'
    assert not any('℉' in t for t in titles), f'迭代图轴标题跟着温标变了：{titles}'

    # 悬浮读数：把鼠标挪到第一个迭代点上，读数也必须是 ℃
    page.eval_on_selector('#chart-host', "el => el.scrollIntoView({block: 'center'})")
    page.wait_for_timeout(250)
    cx, cy = page.eval_on_selector('#chart-host circle',
                                   'el => [Number(el.getAttribute("cx")), Number(el.getAttribute("cy"))]')
    left, top = page.eval_on_selector('#chart-host',
                                      'el => { const r = el.getBoundingClientRect(); return [r.left, r.top]; }')
    page.mouse.move(left + cx, top + cy)
    page.wait_for_timeout(300)
    tip = page.eval_on_selector('#chart-tip', 'el => el.textContent')
    assert 'T_w =' in tip, f'悬浮读数没出现：{tip!r}'
    assert '℃' in tip and '℉' not in tip, f'悬浮读数跟着温标换算了：{tip!r}'
