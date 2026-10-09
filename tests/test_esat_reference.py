# -*- coding: utf-8 -*-
"""饱和水汽压：对公开参考值的外部验证 + 三处已确认缺陷的回归。

对应审计报告的核心指控："core.py 的自检对照的是自己上一版的输出，
构造上无法发现继承来的偏差"。本文件把那 3 处偏差变成会失败的断言。
"""
import math

import pytest

import core
from reference_values import (
    ICE_REF, ICE_TOL, WATER_CHECK_RANGE, WATER_REF, WATER_TOL,
)


def _water_points(name):
    f = core.get_formula(name)
    lo, hi = WATER_CHECK_RANGE.get(name, (f['tmin'], f['tmax']))
    lo = max(lo, f['tmin'])
    hi = min(hi, f['tmax'])
    return sorted(t for t in WATER_REF if lo <= t <= hi)


def _ice_points(name):
    f = core.get_formula(name)
    return sorted(t for t in ICE_REF if f['tmin'] <= t <= f['tmax'])


WATER_CASES = [(n, t) for n in WATER_TOL for t in _water_points(n)]
ICE_CASES = [(n, t) for n in ICE_TOL for t in _ice_points(n)]


@pytest.mark.parametrize('name,T', WATER_CASES)
def test_water_esat_matches_reference(name, T):
    """水面公式 vs WMO/Smithsonian 参考值。"""
    got = core.calculate_esat(T, name)
    ref = WATER_REF[T]
    dev = abs(got - ref) / ref * 100
    assert dev <= WATER_TOL[name], (
        f"{name} @ {T} ℃：计算值 {got:.5f} hPa，参考值 {ref:.5f} hPa，"
        f"偏差 {dev:.3f}% > 容差 {WATER_TOL[name]}%")


@pytest.mark.parametrize('name,T', ICE_CASES)
def test_ice_esat_matches_reference(name, T):
    """冰面公式 vs WMO/Smithsonian 参考值。"""
    got = core.calculate_esat(T, name)
    ref = ICE_REF[T]
    dev = abs(got - ref) / ref * 100
    assert dev <= ICE_TOL[name], (
        f"{name} @ {T} ℃：计算值 {got:.5f} hPa，参考值 {ref:.5f} hPa，"
        f"偏差 {dev:.3f}% > 容差 {ICE_TOL[name]}%")


# --------------------------------------------------------------------------
# 三处已确认缺陷的定点回归（每一条都对应一次真实的、曾经存在的错误）
# --------------------------------------------------------------------------

def test_gili_is_self_consistent_at_its_reference_point():
    """纪利公式在自己的参考温度上必须**精确**给出 1 atm。

    该式的构造前提：T_ref = 373.15 K 处三项修正同时归零，指数只剩常数项；
    而本实现的指数里没有常数项，所以结果必须精确等于前因子 1013.25。

    这条守的正是 B-17 → B-32 整场事故的根因：v1.3.0/v1.3.1 在指数里挂着
    legacy 传下来的 `+0.00141966`（原文 `0.0141966` 的 1/10），于是参考点上
    得到 `1013.25 × 10^0.00141966 = 1016.57 hPa`（+0.33%）——
    **公式与自己的参考值打架**，而当时没有任何断言在看这件事。

    这里用 `abs=` 而不是 `rel=`：参考点上必须一位不差。
    """
    # 先做结构性断言：三项修正在参考点上各自精确归零。
    # 比只看结果更能指向根因（"指数里混进了常数项"）。
    Tref = 373.15
    assert -3.142305 * (1e3 / Tref - 1e3 / Tref) == 0.0
    assert 8.2 * math.log10(Tref / Tref) == 0.0
    assert -0.0024804 * (Tref - Tref) == 0.0

    got = core.calculate_esat(100.0, 'Gili-水面')
    assert got == pytest.approx(1013.25, abs=1e-9), (
        f"Gili-水面 在参考点 373.15 K 上给出 {got!r}，应为 1013.25 hPa —— "
        f"指数里多半又混进了常数项")

    # 参考点两侧必须单调（防"把指数常数挪进前因子"这类等价绕法蒙混过关）
    assert core.calculate_esat(99.0, 'Gili-水面') < got < core.calculate_esat(101.0, 'Gili-水面')


def test_goff2_is_self_consistent_at_its_own_reference_point():
    """Goff2 在**它自己的**参考温度 Tk = A 上必须精确给出 10^H。

    注意断言点是实现自己的 A = 373.15 K（100.00 ℃），**不是**原文的 373.16 K。
    本实现有意采用现代温标的 373.15 K：373.16 K 是旧温标蒸汽点（配 es=1013.246），
    与 `Tk = t + 273.15` 混用反而更差（实测 −10~100 ℃ 由 0.115% 恶化到 0.171%），
    理由见 `core._esat_gili` 的 docstring 与 docs/精度与参考文献.md。
    所以在 373.16 K（100.01 ℃）上该式给出 1013.6077 hPa —— 这**不是**缺陷。
    """
    coeff = core.get_formula('Goff2-水面')['coeff']
    A, H = coeff[0], coeff[7]
    assert A == pytest.approx(373.15), "Goff2 参考温度一旦改动，本节全部理由都要重算"
    ref = 10 ** H                          # 3.0057149 -> 1013.2460047850847
    # H 本身只保留 7 位小数，所以 10**H 与 1013.246 差 ~4.8e-6；
    # 容差取 1e-4 仍能区分"lg(1013.246)"与"lg(1013.25)"（后者差 0.004 hPa）。
    assert ref == pytest.approx(1013.246, abs=1e-4), \
        f"H = lg(1013.246) 的前提被破坏：10**{H} = {ref!r}"
    got = core.calculate_esat(A - 273.15, 'Goff2-水面')
    assert got == pytest.approx(ref, abs=1e-9), (
        f"Goff2-水面 在参考点 {A} K 上给出 {got!r}，应为 {ref!r}")


def test_gili_matches_reference_within_half_a_percent():
    """把"恒定低 3%"这一具体症状钉死：不能只是"偏差变小了"。

    当年实测 −3.04% 的算术来源（2026-10 已溯到原文）：
    指数常数被抄成 `0.00141966`（原文 `0.0141966`）→
    `980.66 × 10^0.00141966 = 983.87 hPa`，比 1013.25 低 2.90%。
    **注意与旧记述的区别：错的是指数常数，不是前因子 980.66**
    （980.66 hPa = 原文的 98066 Pa，本来就对）。
    """
    for T in (0, 10, 15, 20):
        got = core.calculate_esat(T, 'Gili-水面')
        dev = (got - WATER_REF[T]) / WATER_REF[T] * 100
        assert abs(dev) < 0.5, f"Gili-水面 @ {T} ℃ 偏差 {dev:+.3f}%（曾为 -3.04%）"


def test_goff2_fourth_coefficient_is_1_3816e_7():
    """Goff-Gratch 水面式第 4 个系数标准值为 1.3816e-7；旧版写成 1.3816e-5（差 100 倍）。"""
    coeff = core.get_formula('Goff2-水面')['coeff']
    assert coeff[3] == pytest.approx(1.3816e-7, rel=1e-6), \
        f"Goff2-水面 第 4 个系数 = {coeff[3]!r}，应为 1.3816e-7"
    for T in (0, 10, 20, 30, 40, 50, 100):
        got = core.calculate_esat(T, 'Goff2-水面')
        dev = (got - WATER_REF[T]) / WATER_REF[T] * 100
        assert abs(dev) < 0.2, f"Goff2-水面 @ {T} ℃ 偏差 {dev:+.3f}%（0 ℃ 曾为 -3.48%）"


def test_arden_uses_the_three_parameter_form():
    """Arden-水面 的系数是 Buck (1996) 的**三参数**式，必须按原式实现。

    旧版把它塞进 magnus 两参数族，丢掉 `−T/234.5` 修正项，
    在 25 ℃ 偏 +0.91%、50 ℃ 偏 +3.51%、100 ℃ 偏 +12.56%（对照 IAPWS-95）。
    """
    f = core.get_formula('Arden-水面')
    assert f['family'] == 'buck96', \
        f"Arden-水面 应在 buck96 三参数族，实际在 {f['family']!r}"
    assert f['coeff'] == (6.1121, 18.678, 234.5, 257.14)
    # 三参数与两参数在高温端的差别必须真的体现出来
    for T in (5, 25, 40, 50):
        got = core.calculate_esat(T, 'Arden-水面')
        dev = (got - WATER_REF[T]) / WATER_REF[T] * 100
        assert abs(dev) < 0.5, f"Arden-水面 @ {T} ℃ 偏差 {dev:+.3f}%（旧版 50 ℃ 为 +3.6%）"
    # 与 Buck-水面 是同一个作者的一对公式：三参数式应当优于两参数式
    dev3 = abs(core.calculate_esat(50, 'Arden-水面') - WATER_REF[50]) / WATER_REF[50]
    dev2 = abs(core.calculate_esat(50, 'Buck-水面') - WATER_REF[50]) / WATER_REF[50]
    assert dev3 < dev2, f"50 ℃：三参数式偏差 {dev3*100:.3f}% 未优于两参数式 {dev2*100:.3f}%"


@pytest.mark.parametrize('name', [f['name'] for f in core.iter_formulas()])
def test_analytic_derivative_matches_central_difference(name):
    """解析导数 vs 中心差分。

    goff 族的导数第二项曾写成 C/A·log10(Tk/A)·ln10（正确为 C/(Tk·ln10)），
    使 Goff-水面 26%、Goff2-水面 40%、Goff-冰面 18% 的斜率是错的——
    根不变，所以只跑"结果对不对"永远发现不了，只有导数本身能暴露它。
    """
    f = core.get_formula(name)
    tol = 1e-6
    lo, hi = f['tmin'], f['tmax']
    checked = 0
    for k in range(1, 12):
        T = lo + (hi - lo) * k / 12
        if abs(T) < 1e-9:
            T = 1.0
        analytic = core.calculate_dedt(T, name)
        h = 1e-4
        numeric = (core.calculate_esat(T + h, name) -
                   core.calculate_esat(T - h, name)) / (2 * h)
        rel = abs(analytic - numeric) / abs(numeric)
        assert rel < tol, (
            f"{name} @ {T:.3f} ℃：解析导数 {analytic:.6g} vs 中心差分 {numeric:.6g}，"
            f"相对误差 {rel:.3e}")
        checked += 1
    assert checked == 11


def test_gili_analytic_derivative_uses_closed_form():
    """Gili 没有注册解析反算，但注册了 dedt；确认它走的是解析分支而不是差分回退。"""
    f = core.get_formula('Gili-水面')
    assert core._FAMILY_TABLE[f['family']]['dedt'] is core._dedt_gili


# --------------------------------------------------------------------------
# 适用域：注册域不得超过来源文献自己声明的有效域
# --------------------------------------------------------------------------

def test_registered_ranges_do_not_exceed_source_formulations():
    """注册域是"引擎判不适用"的依据，写宽了就等于替用户宣布"这里也能用"。

    v1.3.1 及以前有 4 处越界，实测（对照 IAPWS-95 / IAPWS-2011）：

      · Buck-水面      注册 0~80 ℃  但在 80 ℃ 偏 +1.11%（Buck 1981 只声明 −20~+50）
      · Arden-水面     注册 0~100 ℃ 但在 100 ℃ 偏 +12.56%（Buck 1996 三参数式 −20~+50）
      · Wexler-冰面    注册 −150~10 ℃ 在 −150 ℃ 偏 +0.47%（Hyland & Wexler 173.15 K 起）
      · Marti-冰面     注册 −150~0 ℃ 在 −150 ℃ 偏 −9.93%（Marti & Mauersberger 170~273 K）
      · Goff-冰面/Wexler-冰面 注册到 +10 ℃ —— 常压下 0 ℃ 以上不存在冰面

    本表是"来源文献有效域"的上界；注册域可以更保守（更窄），但不能更宽。
    """
    source = {
        'Goff-水面':   (-50, 100),
        'Wexler-水面': (-10, 200),   # 保守取 −10（超冷水面），来源为 0~200
        'Buck-水面':   (-20, 50),
        'Tetens-水面': (0, 50),
        'Magnus-水面': (-45, 60),
        'August-水面': (-40, 60),    # 来源 −40~50，本项目保守取 0~60 见下方例外
        'Arden-水面':  (-20, 50),
        # 周西华等 (2007) 辽宁工程技术大学学报 26(3):331–333 公式 (7)「纪利公式」。
        # 该文结论明确把纪利公式的适用范围写到 0~120 ℃；GB/T 50392-2016 第 5.1 节
        # 声明 0~100 ℃ 并明说"0 ℃ 以下用纪利公式会出现不合理结果"，故下界取 0。
        'Gili-水面':   (0, 120),
        'Goff2-水面':  (-50, 100),
        'Goff-冰面':   (-100, 0),
        'Wexler-冰面': (-100, 0),
        'Magnus-冰面': (-65, 0),
        'Buck-冰面':   (-80, 0),
        'Marti-冰面':  (-103, 0),
    }
    for f in core.iter_formulas():
        slo, shi = source[f['name']]
        assert f['tmin'] >= slo - 1e-9 and f['tmax'] <= shi + 1e-9, (
            f"{f['name']} 注册域 [{f['tmin']:g}, {f['tmax']:g}] 超出来源有效域 "
            f"[{slo:g}, {shi:g}]")


@pytest.mark.parametrize('name,T', [
    ('Buck-水面', 55.0),      # 旧注册上界 80
    ('Arden-水面', 55.0),     # 旧注册上界 100
    ('Goff-冰面', 5.0),       # 旧注册上界 10
    ('Wexler-冰面', 5.0),     # 旧注册上界 10
    ('Wexler-冰面', -110.0),  # 旧注册下界 −150
    ('Marti-冰面', -110.0),   # 旧注册下界 −150
])
def test_narrowed_ranges_report_not_applicable(name, T):
    """把 4 处收窄过的域端点钉住：域外的温度必须判"不适用"，而不是"照常给数"。"""
    res = {r['method']: r for r in core.calculate_both(T - 1, T, 60)}
    assert res[name]['result1'] == '不适用', (
        f"{name} 在 {T:g} ℃ 下给出了 {res[name]['result1']!r}，应为「不适用」")


def test_ice_formulas_are_not_applicable_above_freezing():
    """冰面公式的注册上界一律为 0 ℃：常压下 0 ℃ 以上不存在冰面。

    旧版 Goff-冰面 / Wexler-冰面 注册到 +10 ℃，于是"已知相对湿度"模式在 5 ℃
    会照常给出一串"冰面露点/霜点"，与水面公式的结果并列展示。
    """
    for f in core.iter_formulas():
        if '冰面' in f['name']:
            assert f['tmax'] == 0, f"{f['name']} 的注册上界为 {f['tmax']:g}，应为 0"
    res = {r['method']: r for r in core.calculate_both(0, 5, 60)}
    for name, r in res.items():
        if '冰面' in name:
            assert r['result1'] == '不适用', f"{name} 在 +5 ℃ 下给出了 {r['result1']!r}"
    # 0 ℃ 整点上冰面公式仍应可用（两种相态在这一点的结果都要给出来）
    res0 = {r['method']: r for r in core.calculate_both(-1, 0, 60)}
    assert all(res0[n]['result1'] != '不适用'
               for n in res0 if '冰面' in n), "0 ℃ 整点上冰面公式应可用"


def test_known_limits_marti_deviates_when_cold():
    """Marti-冰面 是粗经验式，低温端偏差随温度下降而增大。"""
    dev = (core.calculate_esat(-50, 'Marti-冰面') - ICE_REF[-50]) / ICE_REF[-50] * 100
    assert 0.5 < dev < 3.0, f"Marti-冰面 @-50 ℃ 偏差 {dev:+.2f}%（文档记载约 +1.3%）"
