# -*- coding: utf-8 -*-
"""湿球 / 露点求解：与独立来源交叉验证，并钉住"适用域判定"与"极端温度能力"两处行为。"""
import math

import pytest

import core
from reference_values import DEWPOINT_REF, EXTREME_COVERAGE


def stull_wetbulb(T, rh):
    """Stull R. (2011) 湿球温度经验式（℃）。

    与本站的做法完全独立（它是对湿度图的整体拟合，本站是解湿球方程的牛顿迭代），
    因此是本项目唯一的"第二个来源"。适用 -20~50 ℃、RH 5~99%、海平面 1013.25 hPa。
    """
    return (T * math.atan(0.151977 * math.sqrt(rh + 8.313659))
            + math.atan(T + rh)
            - math.atan(rh - 1.676331)
            + 0.00391838 * rh ** 1.5 * math.atan(0.023101 * rh)
            - 4.686035)


def ashrae_wetbulb(T, rh, P=1013.25, method='Goff-水面'):
    """ASHRAE Fundamentals 绝热饱和（adiabatic saturation）湿球温度，℃。

    这是湿球温度的严格定义式：W = [(2501−2.326Tw)·Ws(Tw) − 1.006(T−Tw)]
    / [2501 + 1.86T − 4.186Tw]。它不含"湿度计方程"所用的 Lewis 关系近似，
    因此可以作为本站实现的外部参照——两者的差就是那个近似本身的误差。
    这里复用 core 的 e_sat，只替换方程，从而单独检验求解器与方程形式。
    """
    esat = lambda t: core.calculate_esat(t, method)
    e = esat(T) * rh / 100.0
    W = 0.622 * e / (P - e)

    def residual(Tw):
        esw = esat(Tw)
        Ws = 0.622 * esw / (P - esw)
        D = 2501 + 1.86 * T - 4.186 * Tw
        return ((2501 - 2.326 * Tw) * Ws - 1.006 * (T - Tw)) / D - W

    # residual 对 Tw 单调递增：Tw→T 时为正，Tw 很低时为负
    lo, hi = -150.0, T
    for _ in range(200):
        mid = (lo + hi) / 2
        if residual(mid) > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def _by_method(results):
    return {r['method']: r for r in results}


def _count_usable(T_g, rh):
    """在给定干球温度/相对湿度下，14 条公式里有几条同时给出露点与湿球的数值结果。"""
    res = core.calculate_both(10, T_g, rh)
    return sum(1 for r in res
               if isinstance(r.get('result1'), float) and isinstance(r.get('result2'), float))


# ---------------------------------------------------------------- 湿球温度

@pytest.mark.parametrize('T,rh', [
    (0, 20), (0, 60), (10, 50), (20, 80), (25, 60), (30, 30), (40, 20), (50, 40),
])
def test_wetbulb_matches_stull_2011(T, rh):
    """湿球温度 vs Stull(2011) —— 第二来源（与本站零共享代码）。

    容差 1.0 K 是"粗查"而非精度声明：Stull 式本身是对湿度图的拟合，
    实测它与下方 ASHRAE 严格定义式之间就差 ~0.7 K，本站与它的差
    因此被两个误差共同放大（实测包络 ≤ 0.91 K）。它的价值在于：
    量纲写错、符号写反、e_sat 系统性偏差这类**大错**都会让它立刻变红。
    精度声明由 test_wetbulb_matches_ashrae_adiabatic_saturation 承担。
    """
    res = _by_method(core.calculate_both(T - 5, T, rh, P=1013.25))
    got = res['Goff-水面']['result2']
    want = stull_wetbulb(T, rh)
    assert isinstance(got, float), f"Goff-水面 未给出湿球温度：{got!r}"
    assert abs(got - want) < 1.0, (
        f"干球 {T} ℃ / RH {rh}%：本站 {got:.3f} ℃ vs Stull(2011) {want:.3f} ℃，"
        f"相差 {abs(got - want):.3f} K")


@pytest.mark.parametrize('T,rh', [
    (-10, 40), (0, 10), (0, 60), (10, 30), (20, 50), (25, 10), (30, 90), (40, 20), (50, 10),
])
def test_wetbulb_matches_ashrae_adiabatic_saturation(T, rh):
    """湿球温度 vs ASHRAE 绝热饱和定义式 —— 严格参照，容差 0.5 K。

    本站解的是气象学湿度计方程 e = e_sw − A·p·(T − T_w)，
    用了 Lewis 关系近似；与严格定义式的差应当有界、随温度升高和变干而增大
    （实测 0.01 ~ 0.45 K，T=50 ℃/RH=10% 处最大）。若这个差变成随机跳变或反号，
    说明求解器出了问题，而不是近似本身。
    """
    res = _by_method(core.calculate_both(T - 5, T, rh, P=1013.25))
    got = res['Goff-水面']['result2']
    want = ashrae_wetbulb(T, rh)
    assert isinstance(got, float), f"Goff-水面 未给出湿球温度：{got!r}"
    assert abs(got - want) < 0.5, (
        f"干球 {T} ℃ / RH {rh}%：本站 {got:.3f} ℃ vs ASHRAE {want:.3f} ℃，"
        f"相差 {abs(got - want):.3f} K")


def test_wetbulb_satisfies_psychrometric_equation():
    """结果必须真的满足湿球方程 e_sat(Tw) − A·P(T−Tw) = e，而不只是"看起来合理"。

    方程里的 A 从 `core.psychrometer_A` 取，测试里**不另抄一份常数** ——
    抄一份就等于把 B-02 那类"两处常数不一致"重新请回来。
    """
    T, Td, P = 25.0, 15.0, 1013.25
    res = _by_method(core.calculate_wetbulb(15, T, Td, P))
    for name in ('Goff-水面', 'Wexler-水面', 'Magnus-水面'):
        Tw = res[name]['result1']
        assert isinstance(Tw, float), f"{name}: {Tw!r}"
        e = core.calculate_esat(Td, name)
        a0 = core.get_formula(name)['a0']
        residual = (core.calculate_esat(Tw, name)
                    - core.psychrometer_A(Tw, a0) * P * (T - Tw) - e)
        assert abs(residual) < 1e-3, f"{name}: 湿球方程残差 {residual:.3e} hPa"


def test_psychrometer_a_follows_the_cited_source():
    """湿度计方程 A 系数必须等于所引出处（FAO《Frost Protection》附录 3）的值。

    附录 3 式 A3.15（水面）与式 A3.16（冰面/霜球）分别给出
        A = 0.000660·(1 + 0.00115·t_w)  和  A = 0.000582·(1 + 0.00115·t_f)。
    历史缺陷 B-02：牛顿求导项用的是 0.00066、γ 用的是 0.000667，
    当年的"修复"把两边统一到了错的那一个（0.000667）。这里把两边一起钉住：
    既钉基准值，也钉"每条公式取的是自己相态的那一个"。
    """
    assert core.A0_WATER == 0.000660
    assert core.A0_ICE == 0.000582
    assert core.A_T_COEF == 0.00115
    for f in core.iter_formulas():
        want = core.A0_ICE if '冰面' in f['name'] else core.A0_WATER
        assert f['a0'] == want, (
            f"{f['name']} 的 A 基准值 {f['a0']!r} 与相态不符（应为 {want!r}）")
        assert core.psychrometer_A(20.0, f['a0']) == pytest.approx(
            want * (1 + 0.00115 * 20.0), rel=1e-15)


def test_wetbulb_residual_is_zero_for_every_applicable_formula():
    """每条真正出数的公式（含冰面公式）都必须把自己的湿球方程解到残差 ~0。"""
    checked = 0
    for T, Td in [(25, 15), (5, 0), (-5, -10), (-20, -25), (40, 30)]:
        for r in core.calculate_wetbulb(Td, T, Td, 1013.25):
            Tw = r['result1']
            if not isinstance(Tw, float):
                continue
            name = r['method']
            e = core.calculate_esat(Td, name)
            a0 = core.get_formula(name)['a0']
            residual = (core.calculate_esat(Tw, name)
                        - core.psychrometer_A(Tw, a0) * 1013.25 * (T - Tw) - e)
            assert abs(residual) < 1e-3, f"{name} @ T={T}, Td={Td}: 残差 {residual:.3e}"
            checked += 1
    assert checked > 20, f"只检查到 {checked} 条公式结果，取样不足"


# ---------------------------------------------- 求解器：精度与初值无关性（v1.3.2）

def test_solver_result_does_not_depend_on_initial_guess():
    """**结果的条数与数值都不得取决于迭代初值。**

    这是 v1.3.1 只做了一半的那件事：适用域判定已改成按温度判定，但**求解器**
    还挂在初值上——旧版裸牛顿从发散初值出发就报「未收敛」，于是同一个输入，
    下拉框选 "Tw=Td" 还是 "Tw=T-n" 会改变你在列表里看到几行。
    实测（T=45 ℃/RH=60%）旧版：初值 0~40 → 8 条，初值 100 → 4 条，初值 199 → 0 条。

    现在求解器是「带括号的牛顿法」：f 在该区间严格单调，根唯一，
    括号法保证收敛。初值只影响迭代路径（收敛图），不影响结果。
    """
    guesses = (-149, -100, -50, 0, 5, 10, 15, 25, 40, 60, 100, 150, 199)
    for T, rh in [(-150, 60), (-100, 60), (-80, 60), (-20, 50), (0, 60), (25, 60),
                  (45, 60), (150, 50), (200, 50)]:
        ref = {r['method']: (r['result1'], r['result2'])
               for r in core.calculate_both(guesses[0], T, rh)}
        for g in guesses[1:]:
            got = {r['method']: (r['result1'], r['result2'])
                   for r in core.calculate_both(g, T, rh)}
            # 「哪几条公式出数」必须逐条一致 —— 这才是旧版真正会变的东西
            assert {k for k, v in got.items() if isinstance(v[0], float)} == \
                   {k for k, v in ref.items() if isinstance(v[0], float)}, \
                   f"T={T} ℃ / RH={rh}%：初值 {g} 改变了「哪些公式出数」"
            # 数值只允许差在浮点末位（迭代路径不同，最后一位可以不同）
            for k, v in ref.items():
                if not isinstance(v[0], float):
                    assert got[k] == v, f"{T}/{rh}% 初值{g} {k}: {got[k]!r} != {v!r}"
                    continue
                assert abs(got[k][0] - v[0]) < 1e-9, f"{T}/{rh}% 初值{g} {k} 露点差 {got[k][0]-v[0]:.3e}"
                assert abs(got[k][1] - v[1]) < 1e-9, f"{T}/{rh}% 初值{g} {k} 湿球差 {got[k][1]-v[1]:.3e}"


def test_solver_matches_independent_root_finder():
    """`_solve_wetbulb` 本身必须精确到机器精度（误差全部来自方程形式，不是算法）。

    用 scipy 不可得时的场景（CI 只装 pytest），这里用一个独立的**二分+牛顿**
    实现做对照——它只依赖 core 的 e_sat，与 core 的求解器零共享代码。
    """
    f = core.get_formula('Goff-水面')
    a0 = f['a0']
    P = 1013.25
    worst = 0.0
    checked = 0
    for T in (-10, 0, 10, 25, 40, 50):
        for rh in (5, 20, 50, 80, 99):
            e = core.calculate_esat(T, 'Goff-水面') * rh / 100

            def residual(tw):
                return (core.calculate_esat(tw, 'Goff-水面')
                        - core.psychrometer_A(tw, a0) * P * (T - tw) - e)

            lo, hi = -149.999, T
            assert residual(lo) < 0 <= residual(hi)
            for _ in range(200):                      # 纯二分，独立于 core 的牛顿
                mid = (lo + hi) / 2
                if residual(mid) > 0:
                    hi = mid
                else:
                    lo = mid
            ref = (lo + hi) / 2
            for guess in (-149, 0, 15, 60):
                got, status = core._solve_wetbulb(T, e, P, guess, f, 50, 1e-10)
                assert status == 'ok', f"T={T}, RH={rh}, 初值={guess}: {status}"
                worst = max(worst, abs(got - ref))
                checked += 1
    assert checked == 120, f"只检查到 {checked} 次"
    assert worst < 1e-7, f"求解器与独立二分求根最大差 {worst:.3e} K"


def test_infeasible_state_is_rejected_not_answered():
    """水汽分压不能达到总压。高温 + 常压下 RH 是"不可能达到"的数值。

    150 ℃ 时 e_sat ≈ 4760 hPa，而 P = 1013.25 hPa：RH=50% 要求 e = 2380 hPa > P，
    水早就沸腾了，不存在这种混合气。旧版要么靠求解器意外发散（恰好也报错），
    要么给出一个数——前者是运气，后者是错。现在明确拒绝。
    """
    for T, rh in [(150, 50), (200, 50), (120, 90), (110, 100)]:
        for r in core.calculate_both(10, T, rh, P=1013.25):
            if not isinstance(r['result1'], float):
                continue
            raise AssertionError(
                f"T={T} ℃ / RH={rh}% 下 {r['method']} 给出了 {r['result1']!r}，"
                f"而该状态下 e ≥ P，物理上不成立")
    # 同一组输入在足够高的压强下必须能算（证明拒绝的是状态而不是温度）
    ok = [r for r in core.calculate_both(10, 100, 100, P=1200.0)
          if isinstance(r.get('result2'), float)]
    assert ok, "把压强提到 1200 hPa 后，100 ℃/RH 100% 应当有公式能算出来"
    # 正常的常温常压状态一根汗毛都不该受影响
    normal = {r['method']: r for r in core.calculate_both(15, 25, 60)}
    assert isinstance(normal['Goff-水面']['result2'], float)


def test_wetbulb_is_between_dewpoint_and_dry_bulb():
    """物理约束：Td ≤ Tw ≤ T。"""
    for T, Td in [(25, 15), (30, 25), (10, 5), (35, 30)]:
        res = core.calculate_wetbulb(T - 5, T, Td, 1013.25)
        for r in res:
            v = r['result1']
            if isinstance(v, float):
                assert Td - 1e-6 <= v <= T + 1e-6, \
                    f"{r['method']} @ T={T}, Td={Td}: Tw={v} 不在 [Td, T] 内"


# ---------------------------------------------------------------- 露点温度

@pytest.mark.parametrize('T,rh,want', DEWPOINT_REF)
def test_dewpoint_matches_reference_table(T, rh, want):
    """露点 vs ASHRAE/Vaisala 湿度换算表（容差 0.3 K）。"""
    res = _by_method(core.calculate_both(T - 5, T, rh, P=1013.25))
    got = res['Goff-水面']['result1']
    assert isinstance(got, float), f"Goff-水面 未给出露点：{got!r}"
    assert abs(got - want) < 0.3, f"干球 {T} ℃ / RH {rh}%：本站 {got:.3f} ℃ vs 表值 {want} ℃"


def test_dewpoint_round_trip():
    """反算必须自洽：e_sat(求出的 Td) 与实际水汽压 e 相等。"""
    for T, rh in [(25, 60), (10, 40), (-5, 70), (35, 90)]:
        res = _by_method(core.calculate_both(T - 5, T, rh, P=1013.25))
        for name, r in res.items():
            Td = r['result1']
            if not isinstance(Td, float):
                continue
            e_target = core.calculate_esat(T, name) * rh / 100
            e_got = core.calculate_esat(Td, name)
            rel = abs(e_got - e_target) / e_target
            assert rel < 1e-4, f"{name} @ T={T}, RH={rh}%: 往返相对误差 {rel:.2e}"


def test_dewpoint_increases_with_temperature_at_fixed_rh():
    """固定 RH 下露点随干球温度单调上升。"""
    prev = None
    for T in (-10, 0, 10, 20, 30, 40, 50):
        got = _by_method(core.calculate_both(T - 5, T, 50, P=1013.25))['Goff-水面']['result1']
        assert isinstance(got, float), f"T={T} 未给出露点：{got!r}"
        if prev is not None:
            assert got > prev, f"T={T} 的露点 {got} 未高于前一档 {prev}"
        prev = got


# ------------------------------------------------- 适用域判定（审计发现的行为缺陷）

def test_applicability_does_not_depend_on_initial_guess():
    """审计发现：旧版拿 initial_guess（用户随手填的迭代初值）去比对公式的 tmin/tmax，
    于是"哪些公式适用"取决于初值。现在按真正参与计算的 T 与 Td 判定，
    换初值只能改变迭代路径，不能改变适用与否。"""
    statuses = []
    for guess in (-100, 0, 5, 15, 30, 80):
        statuses.append({r['method']: isinstance(r['result1'], float)
                         for r in core.calculate_wetbulb(guess, 25, 15)})
    first = statuses[0]
    for guess, s in zip((-100, 0, 5, 15, 30, 80), statuses):
        assert s == first, f"initial_guess={guess} 改变了适用域判定：{s} != {first}"


def test_ice_formulas_not_used_when_dewpoint_is_warm():
    """Td=15 ℃ 时冰面公式必须判'不适用'；旧版在初值恰好落在冰面域内时照常出数。"""
    res = _by_method(core.calculate_wetbulb(5, 25, 15))
    ice = {k: v['result1'] for k, v in res.items() if '冰面' in k}
    assert ice, "没有找到冰面公式"
    for name, v in ice.items():
        assert v == '不适用', f"{name} 在 Td=15 ℃ 下给出了 {v!r}"


def test_ice_formulas_not_used_when_dry_bulb_is_warm():
    """模式1 的适用域判定旧版写成 and（"两个都在域外才不适用"），
    于是 T=25 ℃ / Tw=5 ℃ 这种"恰好一个越界"的输入会让冰面公式参与 25 ℃ 的计算。"""
    res = _by_method(core.calculate_dewpoint(25, 5, 1013.25))
    for name, r in res.items():
        if '冰面' in name:
            assert r['result1'] == '不适用', f"{name} 在干球 25 ℃ 下给出了 {r['result1']!r}"


def test_water_formulas_respect_registered_range():
    """注册域外的温度必须判'不适用'，而不是照常给数。"""
    # Magnus-水面 注册 0~60 ℃；Tg=-20 ℃ 时应为不适用
    res = _by_method(core.calculate_both(-20, -20, 60))
    assert res['Magnus-水面']['result1'] == '不适用'
    assert res['Goff-冰面']['result1'] != '不适用'


# ------------------------------------------------------------- 极端温度能力

@pytest.mark.parametrize('T,rh,want', EXTREME_COVERAGE)
def test_extreme_coverage_matches_readme_table(T, rh, want):
    """README「实测能力」表就是这张断言表；两者必须同步。

    这张表是 README 里"覆盖 -150~200 ℃"那句过度声明的替代品：
    注册区间撑得起那句话，实际可用公式数撑不起。
    """
    got = _count_usable(T, rh)
    assert got == want, f"干球 {T} ℃ / RH {rh}%：实测 {got} 条给出结果，表里写的是 {want} 条"


def test_high_temperature_has_no_solution_at_all():
    """150/200 ℃ 且 RH=50% 时，14 条公式一条都给不出结果 —— 这是必须写进 README 的事实。"""
    for T in (150, 200):
        assert _count_usable(T, 50) == 0


def test_formula_count_is_stable():
    """公式条数变化必须被察觉（README 的"14 种国际公式"是有出处的数字）。"""
    assert len(list(core.iter_formulas())) == 14
