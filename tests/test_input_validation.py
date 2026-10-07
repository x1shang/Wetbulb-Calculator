# -*- coding: utf-8 -*-
"""引擎层输入校验。

审计发现：旧版"校验只活在 GUI 回调里"，引擎层是裸的——
RH=120% 照常给数、P=0/-100 照常给数、RH=0 时二分族把下界 -150 ℃ 当成正常露点返回，
而批量计算（process_excel_file）根本不经过 check_input。

本文件确保"核心不依赖调用方守规矩"。
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
