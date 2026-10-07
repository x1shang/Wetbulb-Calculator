# -*- coding: utf-8 -*-
"""饱和水汽压：对公开参考值的外部验证 + 三处已确认缺陷的回归。

对应审计报告的核心指控："core.py 的自检对照的是自己上一版的输出，
构造上无法发现继承来的偏差"。本文件把那 3 处偏差变成会失败的断言。
"""
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

def test_gili_prefactor_is_atmospheric_pressure():
    """Gili 前因子曾经是 980.66（1 工程大气压），导致全区间恒定偏低 3%。

    该式的参考点是 373.16 K（水沸点），那里饱和水汽压按定义 = 1 atm = 1013.25 hPa。
    """
    for T in (0, 10, 20):
        got = core.calculate_esat(T, 'Gili-水面')
        dev = (got - WATER_REF[T]) / WATER_REF[T] * 100
        assert abs(dev) < 0.5, f"Gili-水面 @ {T} ℃ 偏差 {dev:+.3f}%（曾为 -3.0%）"


def test_gili_no_longer_low_by_three_percent():
    """把"恒定低 3%"这一具体症状钉死：不能只是"偏差变小了"。"""
    for T in (0, 10, 20):
        got = core.calculate_esat(T, 'Gili-水面')
        assert got > WATER_REF[T] * 0.99, (
            f"Gili-水面 @ {T} ℃ = {got:.4f} hPa 仍低于参考值 1% 以上")


def test_goff2_fourth_coefficient_is_1_3816e_7():
    """Goff-Gratch 水面式第 4 个系数标准值为 1.3816e-7；旧版写成 1.3816e-5（差 100 倍）。"""
    coeff = core.get_formula('Goff2-水面')['coeff']
    assert coeff[3] == pytest.approx(1.3816e-7, rel=1e-6), \
        f"Goff2-水面 第 4 个系数 = {coeff[3]!r}，应为 1.3816e-7"
    for T in (0, 10, 20, 30, 40, 50, 100):
        got = core.calculate_esat(T, 'Goff2-水面')
        dev = (got - WATER_REF[T]) / WATER_REF[T] * 100
        assert abs(dev) < 0.2, f"Goff2-水面 @ {T} ℃ 偏差 {dev:+.3f}%（0 ℃ 曾为 -3.48%）"


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
# 把"已知的不足"写成断言：如果哪天某个公式被修正了，这里会失败并提醒你
# 同步更新 README 的"实测精度"表——而不是让 README 悄悄过期。
# --------------------------------------------------------------------------

def test_known_limits_arden_degrades_at_high_temperature():
    """Arden-水面 在高温端显著偏离（注册域 0~100 ℃ 名不副实）。"""
    dev50 = (core.calculate_esat(50, 'Arden-水面') - WATER_REF[50]) / WATER_REF[50] * 100
    dev100 = (core.calculate_esat(100, 'Arden-水面') - WATER_REF[100]) / WATER_REF[100] * 100
    assert dev50 > 1.0, (
        f"Arden-水面 @50 ℃ 偏差仅 {dev50:+.2f}%——若公式已被修正，"
        f"请同步更新 README 的实测精度表与本断言")
    assert dev100 > 5.0, f"Arden-水面 @100 ℃ 偏差仅 {dev100:+.2f}%（预期 >5%）"


def test_known_limits_marti_deviates_when_cold():
    """Marti-冰面 是粗经验式，低温端偏差随温度下降而增大。"""
    dev = (core.calculate_esat(-50, 'Marti-冰面') - ICE_REF[-50]) / ICE_REF[-50] * 100
    assert 0.5 < dev < 3.0, f"Marti-冰面 @-50 ℃ 偏差 {dev:+.2f}%（文档记载约 +1.3%）"
