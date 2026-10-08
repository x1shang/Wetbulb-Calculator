# -*- coding: utf-8 -*-
"""注册域全域扫描：每条公式在**自己注册的整个区间**上对 IAPWS 官方方程的偏差。

这一层补上 `test_esat_reference.py` 的结构性缺口：
  · 那张公开表只在 10 个离散点取值，域端点根本没人看；
  · 表的本身偏差有 0.02%~0.10%，会混进公式的偏差里。

本文件对每条公式在 [tmin, tmax] 上等距取 241 个点逐点比较，断言
"域内最大偏差 ≤ DOMAIN_TOL[公式]"。README 的精度表第三列就是这里的实测值。
"""
import math

import pytest

import core
from reference_iapws import (DOMAIN_TOL, ice_hpa, mk_ice_pa, mk_water_pa,
                             reference_hpa, water_hpa)

SAMPLES = 241   # 含两端点


def scan(name, samples=SAMPLES):
    """返回 (最大绝对偏差%, 出现温度℃)。"""
    f = core.get_formula(name)
    lo, hi = f['tmin'], f['tmax']
    worst, where = 0.0, lo
    for k in range(samples):
        T = lo + (hi - lo) * k / (samples - 1)
        try:
            got = core.calculate_esat(T, name)
        except (OverflowError, ZeroDivisionError):
            continue
        ref = reference_hpa(name, T)
        if ref <= 0:
            continue
        dev = abs((got - ref) / ref * 100)
        if dev > worst:
            worst, where = dev, T
    return worst, where


# ------------------------------------------------------------ 参照式自身的可信度

@pytest.mark.parametrize('T', [-50, -40, -30, -20, -10, 0])
def test_two_independent_reference_formulations_agree_on_ice(T):
    """IAPWS-2011 与 Murphy & Koop (2005) 在冰面上必须互差 < 0.05%。

    两个独立来源若互不吻合，用它们当"真值"就没有意义。
    """
    a, b = ice_hpa(T), mk_ice_pa(T + 273.15) / 100.0
    assert abs(a - b) / b * 100 < 0.05, f"{T} ℃：IAPWS {a:.6f} vs MK2005 {b:.6f}"


@pytest.mark.parametrize('T', [-10, 0, 10, 20, 30, 40, 50, 60])
def test_two_independent_reference_formulations_agree_on_water(T):
    """水面上互差 < 0.05%（−10~60 ℃ 区间；更高温 MK2005 已超出其声明域）。"""
    a, b = water_hpa(T), mk_water_pa(T + 273.15) / 100.0
    assert abs(a - b) / b * 100 < 0.05, f"{T} ℃：IAPWS {a:.6f} vs MK2005 {b:.6f}"


def test_iapws_water_reproduces_the_steam_point():
    """IAPWS-95 在 ITS-90 的 100.000 ℃ 上给出 101.418 kPa（不是 101.325 kPa）。

    这一条不是吹毛求疵：常压沸点是 99.974 ℃，所以"100 ℃ 的饱和蒸气压 = 1 atm"
    是老温标下的说法。旧版参考表把它当成真值写进 WATER_REF[100]=1013.25，
    比 IAPWS 低 0.09% —— 这正是"表本身也有偏差"的量化证据。
    """
    assert water_hpa(100.0) == pytest.approx(1014.18, abs=0.05)
    assert water_hpa(99.974) == pytest.approx(1013.25, abs=0.05)


def test_iapws_ice_reproduces_the_triple_point():
    """IAPWS-2011 在三相点 273.16 K 上给出 611.657 Pa（定义值）。"""
    assert ice_hpa(0.01) == pytest.approx(6.11657, abs=1e-5)


# ---------------------------------------------------------------- 全域精度断言

@pytest.mark.parametrize('name', sorted(DOMAIN_TOL))
def test_domain_wide_deviation_within_tolerance(name):
    """注册域全域内的最大偏差必须落在声明容差内。"""
    worst, where = scan(name)
    assert worst <= DOMAIN_TOL[name], (
        f"{name} 在注册域内最大偏差 {worst:.3f}%（出现在 {where:.1f} ℃），"
        f"超过声明容差 {DOMAIN_TOL[name]}%")


def test_every_formula_has_a_declared_tolerance():
    """不许有公式漏进容差表——"没被测量"和"测过没问题"是两回事。"""
    names = {f['name'] for f in core.iter_formulas()}
    assert names == set(DOMAIN_TOL), (
        f"容差表与公式表不一致：只在公式里 {names - set(DOMAIN_TOL)}，"
        f"只在容差表里 {set(DOMAIN_TOL) - names}")


# ------------------------------------------------- README 精度表与实测值对账

def test_readme_table_matches_measurement():
    """README「实测能力与精度」表里的注册域与最大偏差必须与实测一致。

    README 里"哪条公式在哪个温度偏多少"还散落在更新说明等其它表格里，
    所以这里**只切出精度表那一节**再解析，避免匹配到别的表。
    """
    import os
    import re
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, 'README.md'), encoding='utf-8') as f:
        readme = f.read()
    start = readme.index('### 饱和水汽压公式实测偏差')
    end = readme.index('###', start + 10)
    section = readme[start:end]

    for name in sorted(DOMAIN_TOL):
        worst, where = scan(name)
        row = re.search(r'^\|\s*' + re.escape(name) + r'[^|]*\|([^|]*)\|([^|]*)\|',
                        section, re.M)
        assert row, f"README 的精度表里没有 {name} 这一行"
        m = re.search(r'(\d+(?:\.\d+)?)\s*%', row.group(2))
        assert m, f"README 精度表 {name} 行的偏差列读不出数字：{row.group(2)!r}"
        claimed = float(m.group(1))
        assert worst - 0.005 <= claimed, (
            f"{name}：README 写最大偏差 {claimed}%，实测 {worst:.3f}%（{where:.1f} ℃）"
            f"—— 表里的数字比实测小，属于过度声明")
        assert claimed <= max(DOMAIN_TOL[name] * 1.6, worst * 1.6 + 0.02), (
            f"{name}：README 写最大偏差 {claimed}%，实测只有 {worst:.3f}%"
            f"—— 表里的数字明显过时，请同步")
        # 注册域也必须与 core 一致（表里写 0~100 而实际注册成 0~50 属于文档骗人）
        f = core.get_formula(name)
        # README 用的是排版减号 U+2212，先归一化再解析，否则 −80 会被读成 80
        dom_text = row.group(1).replace('\u2212', '-').replace('\u2013', '-')
        nums = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', dom_text)]
        assert len(nums) >= 2, f"README 精度表 {name} 行读不出注册域：{row.group(1)!r}"
        assert nums[0] == f['tmin'] and nums[1] == f['tmax'], (
            f"{name}：README 写注册域 [{nums[0]:g}, {nums[1]:g}]，"
            f"core 里实际是 [{f['tmin']:g}, {f['tmax']:g}]")
