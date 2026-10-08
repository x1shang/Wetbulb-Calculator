# -*- coding: utf-8 -*-
"""引擎层输入校验。

审计发现：旧版"校验只活在 GUI 回调里"，引擎层是裸的——
RH=120% 照常给数、P=0/-100 照常给数、RH=0 时二分族把下界 -150 ℃ 当成正常露点返回，
而批量计算（process_excel_file）**不经过 GUI 的 check_input**。

不经过 GUI 校验 ≠ 没有校验：批量每一行都会走到 core，非法值由 core 抛 InputError，
批量侧靠 `except (ValueError, TypeError)` 把它记成空值、继续处理下一行（见
main.py 的 process_excel_file 与 test_input_error_is_a_value_error）。
本文件确保"核心不依赖调用方守规矩"，也确保批量不会因为一行脏数据整表中断。
"""
import math

import pytest

import core


# ------------------------------------------------------------ 非法输入必须报错

@pytest.mark.parametrize('rh', [120, -5, 0, float('nan'), float('inf'), '60'])
def test_calculate_both_rejects_bad_relative_humidity(rh):
    with pytest.raises(core.InputError):
        core.calculate_both(25, 25, rh)


@pytest.mark.parametrize('P', [0, -100, 0.5, 1300, float('nan'), float('inf')])
def test_calculate_both_rejects_bad_pressure(P):
    with pytest.raises(core.InputError):
        core.calculate_both(25, 25, 60, P=P)


@pytest.mark.parametrize('T', [float('nan'), float('inf'), -float('inf'), -151, 201, None])
def test_calculate_both_rejects_bad_temperature(T):
    with pytest.raises(core.InputError):
        core.calculate_both(25, T, 60)


def test_calculate_wetbulb_rejects_bad_inputs():
    with pytest.raises(core.InputError):
        core.calculate_wetbulb(15, float('inf'), 15)
    with pytest.raises(core.InputError):
        core.calculate_wetbulb(15, 25, float('nan'))
    with pytest.raises(core.InputError):
        core.calculate_wetbulb(15, 25, 15, P=0)


def test_calculate_dewpoint_rejects_bad_inputs():
    with pytest.raises(core.InputError):
        core.calculate_dewpoint(float('nan'), 20, 1013.25)
    with pytest.raises(core.InputError):
        core.calculate_dewpoint(25, 20, -1)


def test_esat_calculate_rejects_nonpositive_pressure():
    with pytest.raises(core.InputError):
        core.esat_calculate(0, 'Goff-水面')
    with pytest.raises(core.InputError):
        core.esat_calculate(-5, 'Goff-水面')


# ------------------------------------------------------------ 合法输入必须放行

@pytest.mark.parametrize('T', [-150, -80, 0, 25, 100, 200])
def test_valid_temperature_passes(T):
    assert core.check_temperature(T) == float(T)


@pytest.mark.parametrize('P', [1, 500, 1013.25, 1100, 1200])
def test_valid_pressure_passes(P):
    assert core.check_pressure(P) == float(P)


@pytest.mark.parametrize('rh', [0.001, 1, 50, 99.9, 100])
def test_valid_rh_passes(rh):
    assert core.check_relative_humidity(rh) == float(rh)


# ------------------------------------------------------------ 病态输入不再是假数值

def test_tiny_rh_does_not_return_the_bisection_floor():
    """旧版 RH 极小/为 0 时，二分族会把下界 -150 ℃ 当成"露点温度"正常返回。
    现在要么给出真实解（并自洽），要么明确报错——不允许出现"贴着边界的常数"。"""
    res = {r['method']: r['result1'] for r in core.calculate_both(25, 25, 0.001)}
    for name, v in res.items():
        if not isinstance(v, float):
            continue
        assert v > -150 + 1e-3, f"{name} 返回了二分下界 {v} —— 这是假数值不是解"
        e_target = core.calculate_esat(25, name) * 0.001 / 100
        assert math.isclose(core.calculate_esat(v, name), e_target, rel_tol=1e-4), \
            f"{name} 返回 {v}，但 e_sat({v}) 不等于目标水汽压"


def test_input_error_is_a_value_error():
    """InputError 继承 ValueError —— 批量计算里的 `except (ValueError, TypeError)`
    正是靠这一点把非法行记为 None，而不是让整个文件中断。"""
    assert issubclass(core.InputError, ValueError)


def test_input_error_message_names_the_field():
    """报错信息必须说清是哪个字段、什么范围——否则用户无从修正。"""
    with pytest.raises(core.InputError) as ei:
        core.calculate_both(25, 25, 150)
    msg = str(ei.value)
    assert '相对湿度' in msg and '100' in msg


# ------------------------------------------- 相对湿度的两种量纲（B-24）
# 同名不同量纲是这类代码里最容易埋的雷：同样叫 rh，
# calculate_both 收**百分数**（60 = 60%），derive_moist_air 收**小数**（0.6 = 60%）。
# 现在参数名分别是 rh_pct / rh_frac，下面把"名字 + 量纲"一起钉住：
# 谁把名字改回去、或者谁把小数传进百分数入口，这里都会立刻红。

def test_calculate_both_speaks_percent():
    """calculate_both 的相对湿度参数是百分数，且必须叫 rh_pct。

    量纲写错不会报错、只会算错 —— 所以这里同时用"名字"（TypeError）与"结果"
    （60 与 0.6 是两个完全不同的湿度）两条证据把契约钉住。
    """
    wet = {r['method']: r['result1'] for r in core.calculate_both(20, 25, rh_pct=60)}['Goff-水面']
    dry = {r['method']: r['result1'] for r in core.calculate_both(20, 25, rh_pct=0.6)}['Goff-水面']
    assert wet > 10, f"25 ℃ / 60% 的露点应约 16.7 ℃，实际 {wet}（把 60 当小数就会算错）"
    assert dry < 0, f"25 ℃ / 0.6% 的露点应远低于 0 ℃，实际 {dry}（把 0.6 当 60% 就会算错）"
    # 旧名字必须消失：仍然接受 rh= 说明这层契约没改干净
    with pytest.raises(TypeError):
        core.calculate_both(20, 25, rh=60)


def test_derive_moist_air_speaks_fraction():
    """derive_moist_air 的相对湿度参数是小数，且必须叫 rh_frac。"""
    d = core.derive_moist_air(25.0, 20.0, 15.0, rh_frac=0.54, P=1013.25)
    assert d['sat_mixing_ratio'] > 0
    with pytest.raises(core.InputError) as ei:
        core.derive_moist_air(25.0, 20.0, 15.0, rh_frac=54.0)
    # 报错要把量纲说清楚，否则调用方只会看到"需在 [0, 1] 范围内"而不知为何
    assert '小数' in str(ei.value)
    with pytest.raises(TypeError):
        core.derive_moist_air(25.0, 20.0, 15.0, rh=0.54)


def test_two_rh_entries_agree_at_the_same_humidity():
    """同一个物理湿度在两条入口上必须自洽（B-24 的行为证据）。

    calculate_both 用 rh_pct=60 反算出露点；把那个露点交给 derive_moist_air
    （rh_frac 是小数 0.60）后，它算出的水汽压必须回到 esat(25 ℃)×60%。
    这一步顺带覆盖了真实数据流："MODE2 算出的露点 → 扩展参数面板"。
    """
    method = 'Goff-水面'
    td = {r['method']: r['result1'] for r in core.calculate_both(20, 25, rh_pct=60)}[method]
    d = core.derive_moist_air(25.0, 20.0, td, rh_frac=0.60, P=1013.25)
    expected = core.calculate_esat(25, method) * 0.60
    assert d['e'] == pytest.approx(expected, rel=2e-3), (
        f"两条入口的湿度不一致：derive 的 e={d['e']}，而 60% × esat(25)={expected}")
