# -*- coding: utf-8 -*-
"""export_vectors.py — 用真的 src/core.py 生成网页版的页内自检向量。

【它解决什么问题】
    web/src/core.js 是 core.py 的移植。移植最怕的不是"当初写错"（一次对拍就能发现），
    而是**以后改歪**：core.py 修了一处数值，网页版没跟上，而用户看不出区别。
    所以把"core.py 在某个版本上的输出"固化成一包向量塞进网页里，页面上有个
    「数值自检」按钮，任何人（包括我）点一下就能看到：
        对拍 351 项 · 0 处超差 · 对应桌面版 v1.3.5 · 用时 6.0 ms
    （351 是当前实际项数；总数随下面几张用例表自动变化，不要把这个数字当契约。）
    而 tests/test_web_parity.py 会在 CI 里检查这包向量**与当前 core.py 仍然对得上**
    —— core.py 一改而没重新生成，测试就红。

【用法】
    python scripts/export_vectors.py            # 写入 web/src/vectors.js
    python scripts/export_vectors.py --check    # 只检查是否过期（CI 用），不写盘

【为什么存成字符串】
    浮点数的十进制往返是有损的：直接写 JSON 数字会经过一轮 repr/parse。
    这里统一写 Python 的 repr（17 位有效数字，可无损往返），JS 侧用 Number() 读回来，
    再用相对容差比对 —— 与 tests/test_web_parity.py 同一套口径。
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, 'src') not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, 'src'))

import core  # noqa: E402

OUT = os.path.join(ROOT, 'web', 'src', 'vectors.js')

# 这三处输入要覆盖：三种模式 × 各自最容易踩坑的温度
MODE_CASES = [
    # (mode, T_g, value, P)
    (0, 25.0, 15.0, 1013.25),
    (0, 0.0, -5.0, 1013.25),
    (0, 45.0, 20.0, 1013.25),
    (1, 25.0, 20.0, 1013.25),
    (1, 10.0, 9.0, 1000.0),
    (2, 25.0, 60.0, 1013.25),
    (2, 30.0, 0.5, 1013.25),
    (2, -20.0, 70.0, 1013.25),
]

VALIDATE_CASES = [
    ('temperature', 25.0),
    ('temperature', -150.0001),
    ('temperature', 200.0001),
    ('temperature', float('nan')),
    ('pressure', 0.0),
    ('pressure', 1200.5),
    ('rh', 0.0),
    ('rh', 100.5),
    ('rh', 0.6),
]

FORMAT_CASES = [
    ('fixed', 16.70034, 4), ('fixed', -16.700345, 4), ('fixed', 0.0, 4), ('fixed', -0.0, 4),
    ('fixed', 2.5, 0), ('fixed', 0.5, 0), ('fixed', 1 / 3, 6), ('fixed', 1013.2464, 2),
    ('g', -150.0, 6), ('g', 1013.25, 6), ('g', 0.00066, 6), ('g', 1e-7, 6),
    ('g', 1.5e-7, 6), ('g', 1234567.0, 6), ('g', 0.03, 6), ('g', 1e-5, 6),
]

DERIVE_CASES = [
    (25.0, 20.0, 15.0, 0.54, 1013.25, 'Goff-水面'),
    (0.0, -1.0, -3.0, 0.6, 1013.25, 'Goff-水面'),
    (45.0, 30.0, 20.0, 0.25, 1000.0, 'Wexler-水面'),
]

# 派生量里挑出"用户会在面板上真看到"的键（下面列表当前 22 个，与 ui.js 的派生量面板对齐）
DERIVE_KEYS = ['es', 'esw', 'e', 'P_dry', 'absolute_humidity', 'specific_humidity',
               'ro_dry', 'ro_vapor', 'ro', 'han', 'L_v', 'dm1', 'sat_mixing_ratio',
               'theta_K', 'theta_e_K', 'virtual_temp_K', 'theta_v_K',
               't_lcl_C', 'p_lcl_hPa', 'x', 'gamma_mix', 'v_sound']


def fmt_temp(value):
    """界面显示串：与 main.py 的 `f"{display_temp:.4f}{unit}"` 同口径（只取数值部分）。

    None（该模式下没有第二个结果）要输出**空串**而不是字符串 'None' ——
    界面那边对 None 渲染的也是空单元格，两边必须对得上。
    """
    if value is None:
        return ''
    if isinstance(value, float):
        return f'{value:.4f}'
    return str(value)


def build():
    esat, dedt, modes, validate, fmt, derive = [], [], [], [], [], []

    # 1) 逐公式的 e_sat / 导数（每条公式取域内三点 + 0 ℃）
    for f in core.FORMULAS:
        tmin, tmax = f['tmin'], f['tmax']
        for T in sorted({tmin, tmin + (tmax - tmin) * 0.25, (tmin + tmax) / 2,
                         tmin + (tmax - tmin) * 0.75, tmax, 0.0}):
            if not (core.T_MIN <= T <= core.T_MAX):
                continue
            esat.append([f['name'], T, repr(core.calculate_esat(T, f['name']))])
            dedt.append([f['name'], T, repr(core.calculate_dedt(T, f['name']))])

    # 2) 三种模式的完整结果（14 行 × 8 组输入）
    for mode, T_g, value, P in MODE_CASES:
        if mode == 0:
            rows = core.calculate_wetbulb(value, T_g, value, P)
        elif mode == 1:
            rows = core.calculate_dewpoint(T_g, value, P)
        else:
            rows = core.calculate_both(T_g, T_g, value, P)
        modes.append([mode, T_g, value, P,
                      [[r['method'], fmt_temp(r['result1']), fmt_temp(r['result2']),
                        None if r['rh'] is None else repr(r['rh'])] for r in rows]])

    # 3) 校验错误文案（pyG / pyRepr 的等价性靠这一组守）
    for fn, value in VALIDATE_CASES:
        fns = {'temperature': core.check_temperature, 'pressure': core.check_pressure,
               'rh': core.check_relative_humidity}
        try:
            fns[fn](value)
            msg = 'ok'
        except core.InputError as exc:
            msg = str(exc)
        validate.append([fn, repr(value), msg])

    # 4) Python 语义格式化
    for kind, x, n in FORMAT_CASES:
        text = f'{x:.{n}f}' if kind == 'fixed' else f'{x:.{n}g}'
        fmt.append([kind, repr(x), n, text])

    # 5) 派生量
    for T_g, T_w, Td, rh, P, method in DERIVE_CASES:
        d = core.derive_moist_air(T_g, T_w, Td, rh, P=P, method=method)
        derive.append([T_g, T_w, Td, rh, P, method,
                       [[k, repr(d[k])] for k in DERIVE_KEYS]])

    total = len(esat) + len(dedt) + sum(len(m[4]) for m in modes) + len(validate) \
        + len(fmt) + sum(len(d[6]) for d in derive)
    return {
        'generated_by': 'scripts/export_vectors.py',
        'exe_tag': core.tag,
        'tolerance': {'rel': 1e-12, 'abs_temp': 1e-9},
        'total': total,
        'esat': esat, 'dedt': dedt, 'modes': modes,
        'validate': validate, 'fmt': fmt, 'derive': derive,
    }


HEADER = '''/* =====================================================================
 * vectors.js — 页内「数值自检」用的黄金向量（**自动生成，请勿手改**）
 * =====================================================================
 *   由 scripts/export_vectors.py 用真的 src/core.py 生成，对应桌面版 {exe_tag}。
 *   用途：网页版的 JS 内核是 core.py 的移植，这份向量让"移植有没有漂移"这件事
 *   在浏览器里就能自证 —— 点界面上的「数值自检」即可看到逐项结果。
 *
 *   重新生成：python scripts/export_vectors.py
 *   过期检查：python scripts/export_vectors.py --check   （CI 里由
 *             tests/test_web_parity.py::test_self_test_vectors_are_current 执行）
 *
 *   浮点一律存 Python repr 字符串：十进制往返无损，JS 侧用 Number() 读回后
 *   按相对容差比对（rel {rel:g} / 温度 abs {abs_temp:g}）。
 * ===================================================================== */
'''


def render(data):
    header = HEADER.format(exe_tag=data['exe_tag'], rel=data['tolerance']['rel'],
                           abs_temp=data['tolerance']['abs_temp'])
    body = json.dumps(data, ensure_ascii=False, separators=(',', ':'), indent=1)
    return (header
            + '(function (root) {\n'
              "  'use strict';\n"
            + '  const V = ' + body + ';\n'
            + '  root.WB_VECTORS = V;\n'
            + "  if (typeof module !== 'undefined' && module.exports) module.exports = V;\n"
              "})(typeof globalThis !== 'undefined' ? globalThis : this);\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description='生成网页版页内自检向量')
    parser.add_argument('--check', action='store_true', help='只检查是否过期，不写盘')
    args = parser.parse_args(argv)

    data = build()
    text = render(data)
    if args.check:
        if not os.path.exists(OUT):
            print(f'[过期] {OUT} 不存在', file=sys.stderr)
            return 1
        old = open(OUT, encoding='utf-8').read()
        if old != text:
            print('[过期] web/src/vectors.js 与当前 core.py 不一致，'
                  '请运行 python scripts/export_vectors.py', file=sys.stderr)
            return 1
        print(f'[最新] 向量与 core.py {data["exe_tag"]} 一致（{data["total"]} 项）')
        return 0

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print(f'已写入 {os.path.relpath(OUT, ROOT)}：{data["total"]} 项，'
          f'esat {len(data["esat"])} / dedt {len(data["dedt"])} / '
          f'模式行 {sum(len(m[4]) for m in data["modes"])} / 校验 {len(data["validate"])} / '
          f'格式 {len(data["fmt"])} / 派生 {sum(len(d[6]) for d in data["derive"])}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
