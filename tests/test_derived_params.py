# -*- coding: utf-8 -*-
"""扩展气象参数（derive_moist_air）。

这些量原先写死在 main.py 的 GUI 回调里，本机装不上 PySide2 就一行也测不到。
审计点名的 4 处数值缺陷里有 3 处在这里（比热容误用摩尔气体常数、
水汽密度误用 esw、饱和混合率误用 e），外加一处当时没被发现、
由本次体检顺带查出的量纲错误（相当位温的潜热项）。
"""
import math

import pytest

import core


# 典型湿空气状态：干球 25 ℃、湿球 20 ℃、露点 15 ℃、1013.25 hPa
TG, TW, TD, P = 25.0, 20.0, 15.0, 1013.25
RH = core.calculate_esat(TD, 'Goff-水面') / core.calculate_esat(TG, 'Goff-水面')


def _d(**kw):
    args = dict(T_g=TG, T_w=TW, Td=TD, rh=RH, P=P, method='Goff-水面')
    args.update(kw)
    return core.derive_moist_air(**args)


def test_sound_speed_is_physical():
    """湿空气声速。

    旧版写 `Cv = Cp - R`（R 是 8.314 的**摩尔**气体常数，而 Cp 是 J/(kg·K) 的比热），
    量纲不匹配 → gamma_mix ≈ 1.008 而不是 ≈ 1.40 → 声速 295 m/s。
    25 ℃ 干空气的教科书值是 346 m/s。
    """
    d = _d()
    assert 1.39 < d['gamma_mix'] < 1.41, \
        f"湿空气绝热指数 {d['gamma_mix']:.4f} 不接近 1.40（旧版的错误值约 1.008）"
    assert 344 < d['v_sound'] < 350, \
        f"声速 {d['v_sound']:.1f} m/s 不在 25 ℃ 的合理区间（旧版的错误值约 295 m/s）"

    # 干极限：水汽≈0 时 gamma_mix → Cp/(Cp−Rd) ≈ 1.399，声速 → sqrt(γ·Rd·T)
    dry = core.derive_moist_air(TG, TG, -80.0, 1e-9, P)
    cp_dry = 1004.7463 + 0.05 * TG
    assert dry['gamma_mix'] == pytest.approx(cp_dry / (cp_dry - core.RD), rel=1e-4)
    assert dry['v_sound'] == pytest.approx(
        math.sqrt(dry['gamma_mix'] * core.RD * (TG + 273.15)), rel=1e-4)


def test_vapor_density_uses_actual_vapor_pressure():
    """ρv 必须由**实际**水汽压 e 决定；旧版误用 esw（湿球饱和水汽压），
    于是未饱和时水蒸气密度、含湿量、空气密度系统性偏大。"""
    d = _d()
    assert d['ro_vapor'] == pytest.approx(d['e'] * 100 / (core.RV * (TG + 273.15)), rel=1e-12)
    assert d['ro_vapor'] < d['esw'] * 100 / (core.RV * (TG + 273.15)), \
        "ρv 不该等于用 esw 算出的值"
    # 与绝对湿度自洽（同一个物理量，两个单位）
    assert d['ro_vapor'] * 1000 == pytest.approx(d['absolute_humidity'], rel=1e-12)
    assert d['ro'] == pytest.approx(d['ro_dry'] + d['ro_vapor'], rel=1e-12)


def test_saturation_mixing_ratio_uses_saturation_pressure():
    """饱和混合率必须用 es；旧版误用 e，算出来的其实是"混合率"
    （审计记录：错误值 11.89 g/kg，正确值 20.08 g/kg）。"""
    d = _d()
    eps = core.EPSILON
    assert d['sat_mixing_ratio'] == pytest.approx(
        eps * d['es'] / (P - d['es']) * 1000, rel=1e-12)
    assert d['dm1'] == pytest.approx(eps * d['e'] / (P - d['e']) * 1000, rel=1e-12)
    assert 20.0 < d['sat_mixing_ratio'] < 20.2, \
        f"饱和混合率 {d['sat_mixing_ratio']:.3f} g/kg（旧版约 11.89）"
    assert d['sat_mixing_ratio'] > d['dm1'], "未饱和时饱和混合率必须大于混合率"


def test_equivalent_potential_temperature_includes_latent_heat():
    """相当位温的潜热项量纲。

    L_v 以 kJ/kg 给出，而指数里的 Cp 是 J/(kg·K)；旧版直接写 L_v*q/(Cp*T)，
    相当于把潜热缩小 1000 倍，theta_e 退化成 theta（差值 < 0.1 K）。
    25 ℃ / RH≈54% 时正确的潜热贡献是几十 K 量级。
    """
    d = _d()
    excess = d['theta_e_K'] - d['theta_K']
    assert excess > 5.0, \
        f"θe − θ 只有 {excess:.3f} K —— 潜热项没有起作用（旧版约 0.03 K）"
    assert excess < 45.0, f"θe − θ = {excess:.3f} K 大得不合常理"


def test_potential_temperatures_are_physical():
    d = _d()
    assert d['theta_K'] < TG + 273.15                      # P < 1000 hPa 时 θ < T
    assert d['theta_v_K'] > d['theta_K']                   # 湿空气虚位温高于位温
    assert d['virtual_temp_K'] > TG + 273.15
    assert d['theta_e_K'] > d['theta_v_K']


def test_specific_humidity_and_mixing_ratio():
    d = _d()
    eps = core.EPSILON
    assert d['specific_humidity'] == pytest.approx(
        eps * d['e'] / (P - (1 - eps) * d['e']) * 1000, rel=1e-12)
    assert d['q'] == pytest.approx(d['specific_humidity'] / 1000, rel=1e-12)
    assert 0 < d['q'] < d['dm1'] / 1000, "比湿必须小于混合率"


def test_lcl_is_below_dewpoint_and_dry_bulb():
    """抬升凝结高度。

    注意物理直觉的坑：LCL 温度 **低于** 地面露点，而不是夹在 Td 与 T 之间。
    气块上升时温度按干绝热递减率下降（≈9.8 K/km），露点只因气压降低而
    缓慢下降（≈1.8 K/km），两者在更低处相遇——所以 T_LCL < Td < T。
    25 ℃ / Td=15 ℃ 时 T_LCL ≈ 12.8 ℃（Bolton 式精确解），
    与"LCL 高度 ≈ 125(T−Td) 米"的经验规则一致。
    """
    d = _d()
    assert d['t_lcl_C'] < TD, f"LCL {d['t_lcl_C']:.2f} ℃ 不应高于地面露点 {TD} ℃"
    assert d['t_lcl_C'] < TG
    assert d['p_lcl_hPa'] < P


def test_lcl_height_matches_rule_of_thumb():
    """LCL 高度经验规则 h ≈ 125·(T − Td) 米（干绝热递减率 9.8 K/km）：
    T=25 ℃ / Td=15 ℃ 时约 1250 m，对应降温 ≈12.3 K。"""
    d = _d()
    height_m = 125 * (TG - TD)
    expected = TG - 0.0098 * height_m
    assert d['t_lcl_C'] == pytest.approx(expected, abs=1.2)


def test_at_saturation_everything_collapses():
    """饱和时 e = es、混合率 = 饱和混合率、LCL 温度 = 干球温度。"""
    d = core.derive_moist_air(TG, TG, TG, 1.0, P)
    assert d['e'] == pytest.approx(d['es'], rel=1e-12)
    assert d['dm1'] == pytest.approx(d['sat_mixing_ratio'], rel=1e-12)
    assert d['t_lcl_C'] == pytest.approx(TG, abs=0.01)


def test_perfectly_dry_is_handled():
    """rh=0 时 LCL 无定义，必须返回 nan 而不是抛异常或给出假数值。"""
    d = core.derive_moist_air(TG, TG, -80.0, 0.0, P)
    assert math.isnan(d['t_lcl_C']) and math.isnan(d['p_lcl_hPa'])
    assert d['v_sound'] > 340


@pytest.mark.parametrize('kwargs', [
    dict(T_g=float('nan')), dict(T_w=float('inf')), dict(Td=-200),
    dict(P=0), dict(P=-1), dict(rh=1.5), dict(rh=-0.1), dict(rh=float('nan')),
])
def test_validation(kwargs):
    with pytest.raises(core.InputError):
        _d(**kwargs)
