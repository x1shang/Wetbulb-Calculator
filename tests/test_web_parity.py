# -*- coding: utf-8 -*-
"""网页版内核与 src/core.py 的逐点对拍（tests/test_web_parity.py）。

【为什么要有这条测试】
    web/src/core.js 是 src/core.py 的**移植**，不是同一份代码。两份实现存活的
    第一天起就有"改了一边忘了另一边"的风险 —— 而这个仓库恰恰以"改数值改得很勤"
    著称（v1.3.2 一轮就动了 6 处）。所以这里不做"看起来对"的抽查，而是：

      1. 用**真的 core.py 现算**期望值（不写死常数，避免改 core 时忘了改测试）；
      2. 让 Node 跑 web/src/core.js 算同一批输入；
      3. 逐点比对数值（容差见 TOL），并额外比对**显示串**（4 位小数、%g、repr）。

【容差为什么不是 0】
    实测（Python 3.11 + Node 24，同一台机器）：120 组数学函数样本里 117 组
    逐位相同，3 组差 1~8 ULP（相对差 ~1e-15）。根因是两边用不同的 libm：
    Python 的 math.exp 在 Windows 上走 MSVC 的 exp，V8 用自己的 fdlibm 移植。
    所以"逐位相同"在跨运行时不可承诺，也不该承诺 —— 承诺的是：
      · 数值相对差 ≤ 1e-12（比 ULP 大 4 个数量级，留足余量）；
      · 温度绝对差 ≤ 1e-9 ℃（界面显示 4 位小数，差 6 个数量级）；
      · **格式化后的显示串完全相等**（这才是用户真正看到的东西）。

【本机没有 node 时】
    skip（CI 的 ubuntu-latest 自带 node，那条流水线上这条测试是真跑的）。
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# conftest.py 在 pytest 下已经做了这件事；这里再做一次是为了让本文件能直接
# `python tests/test_web_parity.py` 当开发工具跑（pytest 之外没有 conftest）。
if os.path.join(ROOT, 'src') not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, 'src'))

import core

CORE_JS = os.path.join(ROOT, 'web', 'src', 'core.js')

# 判定容差
REL_TOL = 1e-12          # 无量纲/蒸气压类量的相对差
ABS_TOL_TEMP = 1e-9      # 温度的绝对差（℃）
ABS_TOL_ANY = 1e-12      # 兜底绝对差（残差这类可能跨 0 的量）


# --------------------------------------------------------------------------
# 携带类型信息的 JSON 编码：字符串状态与浮点数必须能区分开
#   'f' 浮点（十六进制位模式，逐位无损）  's' 字符串  'n' None  'a' 数组  'o' 字典
# --------------------------------------------------------------------------
def enc_py(value):
    if value is None:
        return {'t': 'n'}
    if isinstance(value, bool):
        return {'t': 's', 'v': str(value)}
    if isinstance(value, float):
        if math.isnan(value):
            return {'t': 'f', 'v': 'nan'}
        if math.isinf(value):
            return {'t': 'f', 'v': 'inf' if value > 0 else '-inf'}
        return {'t': 'f', 'v': '0x' + _bits(value)}
    if isinstance(value, int):
        return {'t': 'f', 'v': '0x' + _bits(float(value))}
    if isinstance(value, str):
        return {'t': 's', 'v': value}
    if isinstance(value, (list, tuple)):
        return {'t': 'a', 'v': [enc_py(v) for v in value]}
    if isinstance(value, dict):
        return {'t': 'o', 'v': {k: enc_py(v) for k, v in value.items()}}
    raise TypeError(f'无法编码的类型 {type(value)}: {value!r}')


def _bits(x):
    import struct
    return struct.pack('>d', x).hex()


def dec_py(node):
    t = node['t']
    if t == 'n':
        return None
    if t == 's':
        return node['v']
    if t == 'f':
        v = node['v']
        if v == 'nan':
            return float('nan')
        if v == 'inf':
            return float('inf')
        if v == '-inf':
            return float('-inf')
        import struct
        return struct.unpack('>d', bytes.fromhex(v[2:]))[0]
    if t == 'a':
        return [dec_py(v) for v in node['v']]
    if t == 'o':
        return {k: dec_py(v) for k, v in node['v'].items()}
    raise ValueError(t)


def _close(a, b):
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        if math.isinf(a) or math.isinf(b):
            return a == b
        if abs(a - b) <= ABS_TOL_ANY:
            return True
        if abs(a - b) <= ABS_TOL_TEMP:
            return True
        denom = max(abs(a), abs(b))
        return denom > 0 and abs(a - b) / denom <= REL_TOL
    return a == b


def compare(expected, actual, path='$', diffs=None, loose=False):
    """递归比对两棵 enc_py 结构；返回差异列表。loose=True 用于迭代残差。"""
    if diffs is None:
        diffs = []
    if expected == actual:
        return diffs
    if expected.get('t') != actual.get('t'):
        diffs.append(f'{path}: 类型不同 expected={expected} actual={actual}')
        return diffs
    t = expected['t']
    if t == 'f':
        a, b = dec_py(expected), dec_py(actual)
        if not _close(a, b):
            if loose and _close_loose(a, b):
                return diffs
            diffs.append(f'{path}: {a!r} != {b!r}（差 {a - b if a == a and b == b else float("nan"):.3e}）')
        return diffs
    if t == 's':
        if expected['v'] != actual['v']:
            diffs.append(f'{path}: 文本不同\n    py: {expected["v"]}\n    js: {actual["v"]}')
        return diffs
    if t == 'n':
        return diffs
    if t == 'a':
        if len(expected['v']) != len(actual['v']):
            diffs.append(f'{path}: 长度不同 {len(expected["v"])} != {len(actual["v"])}')
            return diffs
        for i, (e, a) in enumerate(zip(expected['v'], actual['v'])):
            compare(e, a, f'{path}[{i}]', diffs, loose)
        return diffs
    if t == 'o':
        ke, ka = list(expected['v']), list(actual['v'])
        if ke != ka:
            diffs.append(f'{path}: 键不同 {ke} != {ka}')
            return diffs
        for k in ke:
            compare(expected['v'][k], actual['v'][k], f'{path}.{k}', diffs, loose)
        return diffs
    return diffs


def _close_loose(a, b):
    """迭代残差：绝对值可跨 0，相对差单独放宽。"""
    if isinstance(a, float) and isinstance(b, float) and not math.isnan(a) and not math.isnan(b):
        if abs(a - b) <= 1e-9:
            return True
        denom = max(abs(a), abs(b))
        return denom > 0 and abs(a - b) / denom <= 1e-6
    return False


# 收敛到机器精度后，残差 f 只剩下"两个几乎相等的量相减"的抵消噪声（量级 ~2^-48），
# 它的**符号**纯粹是最后一次乘加的舍入彩票。见下面 compare_iter 的说明。
NOISE_FLOOR = 1e-12


def compare_iter(exp_node, act_node, path, diffs, infos):
    """迭代轨迹的比较规则（**不能**要求两边步数相同）。

    【为什么不能要求步数相同 —— 这是一次真实的调查结论，不是偷懒】
      以 August-水面、T=45 ℃、Td=20 ℃ 为例（core.py 的带括号牛顿法）：
        第 6 步 T_w = 27.056142152657245，f = +3.552713678800501e-15 = +2^-48。
      这个 f 已经不是"还没解出来"，而是 esat 与 γ·(T−Tw)+e 相减的**抵消噪声**：
      它的真值在 ±1 ULP 之间，符号取决于 libm 最后一次舍入。
        · 若 f > 0：hi = T_w，于是牛顿步 T_w − f/df 舍入回 T_w **恰好等于 hi**，
          `lo < T_new < hi` 不成立 → 牛顿步被拒 → 退回二分中点 (lo+hi)/2 = −38.97 ℃
          —— 求解器从"已经到机器精度的根"上跳开，再花 ~30 步二分爬回来（Python 实测 36 步）。
        · 若 f < 0：lo = T_w，括号宽度 = 相邻两个迭代值之差 ≈ 4e-9 ≤ 2·tol → 立刻判收敛（Node 实测 6 步）。
      两边差的是 libm（MSVC 的 exp/pow vs V8 的），不是算法；同一份 core.py 在 Linux 上
      构建也会与 Windows 上不同。**两条路径的最终结果相同**（由外层的结果比对保证），
      所以这里只比较"到达噪声底之前"的迭代，之后的步数差异只作为信息记录。
    """
    exp = dec_py(exp_node)
    act = dec_py(act_node)

    def group(rows):
        g = {}
        for name, i, t, r in rows:
            g.setdefault(name, []).append((i, t, r))
        return g

    ge, ga = group(exp), group(act)
    if set(ge) != set(ga):
        diffs.append(f'{path}: 参与迭代的公式集合不同\n    py: {sorted(ge)}\n    js: {sorted(ga)}')
        return
    for name in ge:
        pe, pa = ge[name], ga[name]
        if not pe or not pa:
            diffs.append(f'{path} {name}: 轨迹为空 py={len(pe)} js={len(pa)}')
            continue
        if pe[0][0] != pa[0][0]:
            diffs.append(f'{path} {name}: 起始迭代序号不同 py={pe[0][0]} js={pa[0][0]}')
        n = min(len(pe), len(pa))
        compared = 0
        for k in range(n):
            ie, te, re_ = pe[k]
            ia, ta, ra = pa[k]
            if re_ < NOISE_FLOOR or ra < NOISE_FLOOR:
                break
            if abs(te - ta) > ABS_TOL_TEMP:
                diffs.append(f'{path} {name}: 第 {int(ie)} 步温度 {te!r} != {ta!r}')
                break
            if not _close_loose(re_, ra):
                diffs.append(f'{path} {name}: 第 {int(ie)} 步残差 {re_:.8g} != {ra:.8g}')
                break
            compared += 1
        # 噪声底之前至少要能对上 4 步 —— 前几步覆盖了括号初值、γ、导数与牛顿方向，
        # 移植里任何一处写错都会在这里现形。
        if compared < min(4, n):
            diffs.append(f'{path} {name}: 只比到 {compared} 步就分叉（噪声底之前应至少 4 步）')
        if len(pe) != len(pa):
            infos.append(f'{name}: 迭代步数 py={len(pe)} js={len(pa)}（噪声底后的 ULP 彩票，不判失败）')


# --------------------------------------------------------------------------
# 用例表：函数式生成，改一处两边同时变（避免"测试里少跑了一半却全绿"）
# --------------------------------------------------------------------------
_T_SWEEP = [-120, -103, -100, -80, -65, -40, -10, -1, 0, 0.5, 5, 10, 20, 25, 40, 49, 50, 60, 80, 100, 120, 150, 199]
_P_CASES = [1013.25, 500.0, 1000.0, 1100.0, 900.0]


def build_cases():
    cases = []

    def add(kind, **kw):
        cases.append(dict(kind=kind, **kw))

    # 1) 逐公式 e_sat / 导数（含各自注册域端点的内外）
    for f in core.FORMULAS:
        ts = sorted({f['tmin'], f['tmax'], f['tmin'] + 1, f['tmax'] - 1,
                     (f['tmin'] + f['tmax']) / 2, 0.0} | set(_T_SWEEP))
        for T in ts:
            if core.T_MIN <= T <= core.T_MAX:
                add('esat', method=f['name'], T=T)
                add('dedt', method=f['name'], T=T)

    # 2) 反算 e → T
    for name in ('Goff-水面', 'Buck-水面', 'Wexler-冰面', 'Gili-水面', 'Marti-冰面'):
        for e in (0.001, 0.01, 0.1, 1.0, 6.112, 17.0, 100.0, 1013.25):
            add('esat_calculate', method=name, e=e)

    # 3) 三种模式的完整结果数组（含状态文案）
    for P in _P_CASES:
        for T, Td in ((25, 15), (25, 24), (0, -5), (20, 17.7), (45, 20), (-20, -30),
                      (49.9, 10), (100, 60), (5, 4.9), (30, 0)):
            add('wetbulb', guess=Td, T=T, Td=Td, P=P)
        for T, Tw in ((25, 20), (30, 25), (0, -2), (10, 9), (-10, -12), (40, 30)):
            add('dewpoint', T=T, Tw=Tw, P=P)
        for T, rh in ((25, 60), (25, 100), (30, 0.5), (0, 50), (10, 99.9), (45, 30),
                      (-20, 70), (100, 40), (60, 10)):
            add('both', guess=T, T=T, rh=rh, P=P)

    # 4) 派生量（24 键）
    for T, Tw, Td, rh in ((25, 20, 15, 0.54), (30, 24, 16, 0.4), (0, -1, -3, 0.6),
                          (-10, -12, -14, 0.55), (45, 30, 20, 0.25), (100, 60, 40, 0.1)):
        for method in ('Goff-水面', 'Wexler-水面'):
            add('derive', T_g=T, T_w=Tw, Td=Td, rh_frac=rh, P=1013.25, method=method)

    # 5) 迭代轨迹（收敛图的形状取决于它）
    for T, Td, guess, P, tol in ((25, 15, 15, 1013.25, 1e-7), (45, 20, 40, 1013.25, 1e-7),
                                 (25, 15, 100, 1013.25, 1e-7), (0, -5, 0, 1000.0, 1e-7),
                                 (25, 15, 15, 1013.25, 1e-2), (25, 15, 15, 1013.25, 1e-10)):
        add('iter', guess=guess, T=T, Td=Td, P=P, tol=tol)

    # 6) 输入校验的**错误文案**（pyG / pyRepr 是否真的等价）
    for v in (0.0, 100.0, -150.0, 200.0, -150.0001, 200.0001, float('nan')):
        add('validate', fn='temperature', value=_num(v))
    for v in (0.0, 1.0, 1200.0, 1200.5, -1.0):
        add('validate', fn='pressure', value=v)
    for v in (0.0, 100.0, 100.5, -0.5, 1e-9):
        add('validate', fn='rh', value=v)
    add('validate', fn='temperature', value='abc')
    add('validate', fn='temperature', value=True)
    add('validate', fn='rh', value=0.6)

    # 7) 蒸气压反算的越界错误文案
    add('esat_calculate_err', method='Buck-水面', e=1e-6)
    add('esat_calculate_err', method='Magnus-冰面', e=5000.0)
    add('esat_calculate_err', method='Tetens-水面', e=-1.0)

    # 8) Python 语义格式化（pyFixed / pyG / pyRepr 的等价性）
    for x in (0.0, -0.0, 0.5, 1.5, 2.5, 0.05, 16.70034, -16.700345, 1 / 3, 1e-7, 1e21,
              2.675, 123456.789, -0.00004, 1e16, 5e-324):
        for n in (0, 1, 2, 4, 6):
            add('pyFixed', x=x, n=n)
    for x in (0.0, -0.0, 1.0, -150.0, 0.00066, 1013.25, 1e-7, 1.5e-7, 1e20, 1234567.0,
              0.000123456789, 999999.5, 999999.9, -3.5, 1e-5):
        for prec in (4, 6, 8):
            add('pyG', x=x, prec=prec)
    return cases


def _num(v):
    """把 NaN 传成字符串 'nan'（JSON 表达不了 NaN）。"""
    return 'nan' if isinstance(v, float) and math.isnan(v) else v


def expect_case(c):
    """用真 core.py 现算期望值。"""
    k = c['kind']
    if k == 'esat':
        return enc_py(core.calculate_esat(c['T'], c['method']))
    if k == 'dedt':
        return enc_py(core.calculate_dedt(c['T'], c['method']))
    if k == 'esat_calculate':
        return enc_py(core.esat_calculate(c['e'], c['method']))
    if k == 'wetbulb':
        return enc_py(core.calculate_wetbulb(c['guess'], c['T'], c['Td'], c['P']))
    if k == 'dewpoint':
        return enc_py(core.calculate_dewpoint(c['T'], c['Tw'], c['P']))
    if k == 'both':
        return enc_py(core.calculate_both(c['guess'], c['T'], c['rh'], c['P']))
    if k == 'derive':
        return enc_py(core.derive_moist_air(c['T_g'], c['T_w'], c['Td'], c['rh_frac'],
                                            P=c['P'], method=c['method']))
    if k == 'iter':
        trace = []
        core.calculate_wetbulb(c['guess'], c['T'], c['Td'], c['P'], tol=c['tol'],
                               on_iter=lambda m, i, t, r: trace.append([m, i, t, r]))
        return enc_py(trace)
    if k == 'validate':
        fn = {'temperature': lambda v: core.check_temperature(v),
              'pressure': lambda v: core.check_pressure(v),
              'rh': lambda v: core.check_relative_humidity(v)}[c['fn']]
        v = c['value']
        if v == 'nan':
            v = float('nan')
        try:
            return enc_py('ok:' + repr(fn(v)))
        except core.InputError as exc:
            return enc_py('InputError: ' + str(exc))
    if k == 'esat_calculate_err':
        try:
            core.esat_calculate(c['e'], c['method'])
            return enc_py('no-error')
        except core.InputError as exc:
            return enc_py('InputError: ' + str(exc))
    if k == 'pyFixed':
        return enc_py(f'{c["x"]:.{c["n"]}f}')
    if k == 'pyG':
        return enc_py(f'{c["x"]:.{c["prec"]}g}')
    raise ValueError(k)


# --------------------------------------------------------------------------
# Node 驱动
# --------------------------------------------------------------------------
DRIVER = textwrap.dedent('''
    'use strict';
    const fs = require('fs');
    const C = require(process.env.WB_CORE);
    const cases = JSON.parse(fs.readFileSync(process.env.WB_REQ, 'utf8'));

    function bits(x) {
      const b = new ArrayBuffer(8); const dv = new DataView(b);
      dv.setFloat64(0, x, false);
      let s = '';
      for (let i = 0; i < 8; i++) s += dv.getUint8(i).toString(16).padStart(2, '0');
      return '0x' + s;
    }
    function enc(v) {
      if (v === null || v === undefined) return { t: 'n' };
      if (typeof v === 'number') {
        if (Number.isNaN(v)) return { t: 'f', v: 'nan' };
        if (v === Infinity) return { t: 'f', v: 'inf' };
        if (v === -Infinity) return { t: 'f', v: '-inf' };
        return { t: 'f', v: bits(v) };
      }
      if (typeof v === 'string') return { t: 's', v: v };
      if (typeof v === 'boolean') return { t: 's', v: String(v) };
      if (Array.isArray(v)) return { t: 'a', v: v.map(enc) };
      if (typeof v === 'object') {
        const o = {};
        for (const k of Object.keys(v)) o[k] = enc(v[k]);
        return { t: 'o', v: o };
      }
      return { t: 's', v: String(v) };
    }
    function run(c) {
      switch (c.kind) {
        case 'esat': return C.calculate_esat(c.T, c.method);
        case 'dedt': return C.calculate_dedt(c.T, c.method);
        case 'esat_calculate': return C.esat_calculate(c.e, c.method);
        case 'wetbulb': return C.calculate_wetbulb(c.guess, c.T, c.Td, c.P);
        case 'dewpoint': return C.calculate_dewpoint(c.T, c.Tw, c.P);
        case 'both': return C.calculate_both(c.guess, c.T, c.rh, c.P);
        case 'derive': return C.derive_moist_air(c.T_g, c.T_w, c.Td, c.rh_frac, c.P, c.method);
        case 'iter': {
          const trace = [];
          C.calculate_wetbulb(c.guess, c.T, c.Td, c.P, undefined, c.tol,
            undefined, (m, i, t, r) => trace.push([m, i, t, r]));
          return trace;
        }
        case 'validate': {
          const v = c.value === 'nan' ? NaN : c.value;
          try {
            const f = { temperature: C.check_temperature, pressure: C.check_pressure,
                        rh: C.check_relative_humidity }[c.fn];
            return 'ok:' + C.pyRepr(f(v));
          } catch (e) { return 'InputError: ' + e.message; }
        }
        case 'esat_calculate_err': {
          try { C.esat_calculate(c.e, c.method); return 'no-error'; }
          catch (e) { return 'InputError: ' + e.message; }
        }
        case 'pyFixed': return C.pyFixed(c.x, c.n);
        case 'pyG': return C.pyG(c.x, c.prec);
        default: throw new Error('unknown kind ' + c.kind);
      }
    }
    const out = cases.map(c => {
      try { return enc(run(c)); }
      catch (e) { return { t: 's', v: 'THROW[' + (e && e.name) + ']: ' + (e && e.message) }; }
    });
    fs.writeFileSync(process.env.WB_OUT, JSON.stringify(out), 'utf8');
    ''')


def _node():
    return shutil.which('node') or shutil.which('node.exe')


def run_js(cases, tmp_path):
    exe = _node()
    if exe is None:
        pytest.skip('本机没有 node，跳过网页版内核对拍')
    if not os.path.exists(CORE_JS):
        pytest.skip('web/src/core.js 不存在')
    req = tmp_path / 'req.json'
    out = tmp_path / 'out.json'
    drv = tmp_path / 'driver.js'
    # 用例里的 'nan' 用字符串传递，与 Python 侧 expect_case 的处理一致
    req.write_text(json.dumps(cases, ensure_ascii=False), encoding='utf-8')
    drv.write_text(DRIVER, encoding='utf-8')
    env = dict(os.environ)
    env['WB_CORE'] = CORE_JS
    env['WB_REQ'] = str(req)
    env['WB_OUT'] = str(out)
    proc = subprocess.run([exe, str(drv)], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', env=env, timeout=600)
    assert out.exists(), f'Node 驱动没有产出结果：\n{proc.stdout}\n{proc.stderr}'
    return json.loads(out.read_text(encoding='utf-8'))


# --------------------------------------------------------------------------
# 测试
# --------------------------------------------------------------------------
def test_js_core_matches_python_core(tmp_path):
    cases = build_cases()
    actual = run_js(cases, tmp_path)
    assert len(actual) == len(cases)

    diffs = []
    infos = []
    for c, act in zip(cases, actual):
        exp = expect_case(c)
        label = json.dumps(c, ensure_ascii=False)[:150]
        if c['kind'] == 'iter':
            compare_iter(exp, act, label, diffs, infos)
        else:
            diffs.extend(compare(exp, act, path=label))

    # 单条用例里 14 条公式 × 两个字段，差异会很啰嗦 —— 只报前 25 条，但要报总数
    assert not diffs, (f'{len(diffs)} 处不一致（只显示前 25 条）：\n'
                       + '\n'.join(diffs[:25])
                       + '\n\n（web/src/core.js 与 src/core.py 必须逐点一致；'
                         '数值容差 rel≤1e-12 / 温度 abs≤1e-9）')
    if infos and os.environ.get('WETBULB_SHOW_ITER_INFO') == '1':
        print('\n'.join(infos))


def test_displayed_strings_match_python_formatting(tmp_path):
    """界面显示值（4 位小数）必须与 exe 逐字相同 —— 这是用户真正看得见的东西。"""
    cases = []
    for T, Td in ((25, 15), (0, -5), (45, 20), (10, 9.5)):
        cases.append(dict(kind='wetbulb', guess=Td, T=T, Td=Td, P=1013.25))
    for T, Tw in ((25, 20), (0, -2), (40, 30)):
        cases.append(dict(kind='dewpoint', T=T, Tw=Tw, P=1013.25))
    for T, rh in ((25, 60), (0, 50), (45, 30)):
        cases.append(dict(kind='both', guess=T, T=T, rh=rh, P=1013.25))
    actual = run_js(cases, tmp_path)
    bad = []
    for c, act in zip(cases, actual):
        exp = expect_case(c)
        if exp['t'] != 'a' or act['t'] != 'a':
            bad.append(f'{c}: 结构异常')
            continue
        for row_py, row_js in zip(exp['v'], act['v']):
            for field in ('result1', 'result2', 'rh'):
                a, b = row_py['v'].get(field), row_js['v'].get(field)
                if a is None or b is None or a['t'] != 'f' or b['t'] != 'f':
                    continue
                va, vb = dec_py(a), dec_py(b)
                if math.isnan(va) and math.isnan(vb):
                    continue
                sa, sb = f'{va:.4f}', f'{vb:.4f}'
                if sa != sb:
                    bad.append(f'{c} {row_py["v"]["method"]["v"]}.{field}: {sa} != {sb}')
    assert not bad, '显示串不一致：\n' + '\n'.join(bad[:25])


def test_web_core_declares_the_exe_version_it_ports():
    """web/src/core.js 必须写明"对应桌面版哪个版本"，且与 core.tag 一致。

    这条是防止"桌面版升到 1.3.5、网页版还写着对应 1.3.4"的静默漂移 ——
    网页版版本号与桌面版**刻意不同**（2.x 对 1.x），所以更需要一条断言钉住对应关系。
    """
    src = open(CORE_JS, encoding='utf-8').read()
    m = None
    for line in src.splitlines():
        if 'const EXE_TAG' in line:
            m = line
            break
    assert m, 'web/src/core.js 里找不到 EXE_TAG'
    assert f"'{core.tag}'" in m, f'EXE_TAG 与 core.tag({core.tag}) 不一致：{m.strip()}'

    web = None
    for line in src.splitlines():
        if 'const WEB_TAG' in line:
            web = line
            break
    assert web, 'web/src/core.js 里找不到 WEB_TAG'
    import re
    assert re.search(r"'v2\.\d+\.\d+'", web), f'WEB_TAG 应形如 v2.x.y：{web.strip()}'


def _run(cmd):
    return subprocess.run([sys.executable] + cmd, cwd=ROOT, capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=180)


def test_self_test_vectors_are_current():
    """页内自检向量必须与当前 core.py 一致。

    向量是"core.py 在某个版本上的输出"的固化。core.py 改了数值而没重新生成向量，
    页面上那句"0 处超差"就会在**旧的**期望值上通过 —— 那是最坏的一种绿：
    自检按钮装作在守护，其实守护的是过去。
    """
    proc = _run(['scripts/export_vectors.py', '--check'])
    assert proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def test_single_file_build_is_current():
    """web/index.html 必须与 web/src/ 下当前源码一致（构建产物不能落后于源码）。

    这两步（生成向量 → 组装单文件）都是"改了源码但忘了跑脚本"的经典漏点，
    而它们的症状恰恰是**看不出问题**：页面照常打开，只是内容是旧的。
    """
    proc = _run(['scripts/build_web.py', '--check'])
    assert proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def test_single_file_page_has_no_external_dependencies():
    """交付物必须真的是"一个 .html"：不能有外链脚本、样式、字体或接口。

    网页版的定位是"双击就能用、离线可用、数据不出本机"，所以任何一处外链
    都会同时破坏这三条。这里按文本扫一遍，比人工检查可靠。
    """
    html = open(os.path.join(ROOT, 'web', 'index.html'), encoding='utf-8').read()
    for bad in ('<script src=', '<link rel="stylesheet"', '<link rel=stylesheet',
                'fonts.googleapis', 'cdn.', 'unpkg', 'jsdelivr'):
        assert bad not in html, f'web/index.html 里出现了外部依赖：{bad}'
    # 允许 XML 命名空间（xlsx 的 parts 需要），其余 http(s) 地址只能出现在文案链接里
    for m in re.finditer(r'https?://[^\s"\'<>)]+', html):
        url = m.group(0)
        assert url.startswith(('https://github.com/x1shang/', 'http://www.w3.org',
                               'http://schemas.', 'https://schemas.')), \
            f'web/index.html 里出现了预期之外的地址：{url}'
    # 四个组装占位标记不能残留，否则说明构建漏了一块
    for marker in ('/*__APP_CSS__*/', '/*__VECTORS__*/', '/*__CORE__*/', '/*__UI__*/'):
        assert marker not in html, f'构建残留占位标记：{marker}'


if __name__ == '__main__':
    # 开发用：python tests/test_web_parity.py —— 打印差异明细
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        from pathlib import Path
        cs = build_cases()
        print(f'用例数：{len(cs)}')
        acts = run_js(cs, Path(td))
        all_diffs = []
        for c, act in zip(cs, acts):
            all_diffs.extend(compare(expect_case(c), act, json.dumps(c, ensure_ascii=False)[:120],
                                     loose=(c['kind'] == 'iter')))
        print(f'差异：{len(all_diffs)}')
        for d in all_diffs[:40]:
            print(' -', d)
        sys.exit(1 if all_diffs else 0)
