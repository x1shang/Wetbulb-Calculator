# -*- coding: utf-8 -*-
"""
core.py — 湿球计算器计算核心（注册表模式，sample.py 的精简注释版）
=================================================================
统一管理公式族(_FAMILY_TABLE)与公式注册表(FORMULAS)，提供全部计算 API。
main.py 通过 `from core import ...` 调用本模块。

核心概念：
  公式族 family  = 公式的“形态”（magnus/goff/wexler/gili/marti），
                  在 _FAMILY_TABLE 中注册 求值 esat / 求导 dedt / 反算 invert 函数。
  公式   formula = 一族下的具体系数+适用区间，用 register_formula() 登记一行。

新增公式：register_formula('名字', '族名', (系数...), 最低温, 最高温)
新增公式族：在 _FAMILY_TABLE 加一项（esat/dedt 必填，invert 可选，缺省走二分）。
"""
import os
import sys
import math
import json

# ------------------------------ 配置 ------------------------------
def resource_path(relative_path):
    """资源定位：exe 打包后(_MEIPASS)与开发目录均可。"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def cfg_file_path(for_write=False):
    """用户配置文件 cfg.json 的定位（支持手动配置）：
    打包成 exe 后，若 exe 旁存在 cfg.json 则优先使用它；for_write=True
    （保存配置）时始终写 exe 旁，保证用户修改持久化。
    开发环境使用 resource_path()（脚本/工作目录）。"""
    if hasattr(sys, '_MEIPASS'):
        side = os.path.join(os.path.dirname(sys.executable), 'cfg.json')
        if for_write or os.path.exists(side):
            return side
    return resource_path('cfg.json')

def _read_cfg():
    """读取整个 cfg.json；失败返回空 dict。"""
    try:
        with open(cfg_file_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def load_g_value():
    """读 cfg.json 的重力加速度 g（格式 {"g": 9.81}），失败回退 9.81。"""
    return _read_cfg().get('g', 9.81)

def save_g_value(g_value):
    """把 g 写回 cfg.json；保留文件中的其他键（如 title_color）。"""
    try:
        cfg = _read_cfg()
        cfg['g'] = g_value
        with open(cfg_file_path(for_write=True), 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存g值失败: {str(e)}")

tag = "v1.3.1"          # 版本号（与 about.py 中文本保持同步）
                        # v1.3.1 = 数值缺陷修复 + 引擎层输入校验 + 外部参照回归。
                        # 修复了 Gili/Goff2 的系数与 goff 族解析导数，
                        # 因此 v1.3.1 的数值结果与 v1.3.0 **不同**，不能用同一版本号发布。
tot = 1e-7              # 默认迭代精度
g = load_g_value()      # 重力加速度
                        # 注意：g 目前只用于界面占位符与 cfg.json，不参与任何公式计算。

# ------------------------------ 物理常数 ------------------------------
# 比热容/气体常数一律用 J/(kg·K)（比气体常数），不要与摩尔气体常数混用。
R_UNIVERSAL = 8.314462618       # 摩尔气体常数 J/(mol·K)
MV = 18.01528                   # 水汽摩尔质量 g/mol
MD = 28.9647                    # 干空气摩尔质量 g/mol
RD = 1000 * R_UNIVERSAL / MD    # 干空气比气体常数 ≈ 287.05 J/(kg·K)
RV = 1000 * R_UNIVERSAL / MV    # 水汽比气体常数   ≈ 461.52 J/(kg·K)
EPSILON = MV / MD               # 分子量比 Mv/Md ≈ 0.62197

# ------------------------------ 输入校验 ------------------------------
# 引擎层必须自证输入合法：main.py 的 check_input 只保护交互路径，
# 批量计算（process_excel_file）与本模块被 import 调用时都不经过它。
T_MIN, T_MAX = -150.0, 200.0    # ℃，与界面温度输入域一致
P_MIN, P_MAX = 1.0, 1200.0      # hPa，界面限 500~1100，引擎放宽以兼容高原等低气压场景
RH_MAX = 100.0                  # %
# 相对湿度下界是开区间：RH=0 时 e=0，露点无定义。


class InputError(ValueError):
    """物理上不可能的输入。引擎层抛出，由 UI（错误条）或批量计算（记空）处理。"""


def _finite(value, name):
    """返回 float(value)；非数值或 NaN/±inf 一律拒绝。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{name}必须是数值（收到 {value!r}）")
    v = float(value)
    if not math.isfinite(v):
        raise InputError(f"{name}必须是有限数值（收到 {value!r}）")
    return v


def check_temperature(value, name='温度'):
    """温度（℃）校验：有限且落在 [-150, 200]。"""
    v = _finite(value, name)
    if not (T_MIN <= v <= T_MAX):
        raise InputError(f"{name}需在 [{T_MIN:g}, {T_MAX:g}] ℃ 范围内（收到 {v:g}）")
    return v


def check_pressure(value):
    """大气压强（hPa）校验：有限且大于 0。"""
    v = _finite(value, '大气压强')
    if not (P_MIN <= v <= P_MAX):
        raise InputError(f"大气压强需在 [{P_MIN:g}, {P_MAX:g}] hPa 范围内（收到 {v:g}）")
    return v


def check_relative_humidity(value):
    """相对湿度（%）校验：有限且落在 (0, 100]。"""
    v = _finite(value, '相对湿度')
    if not (0.0 < v <= RH_MAX):
        raise InputError(f"相对湿度需在 (0, {RH_MAX:g}] % 范围内（收到 {v:g}）")
    return v


# -------------------------- 公式族计算函数 --------------------------
# 每个 _esat_xxx(T, coeff) 求饱和水蒸气压 e_sat(hPa)；_dedt_xxx 求其导数。
# T 为摄氏度；coeff 为系数元组（无系数传 ()）。

def _esat_magnus(T, coeff):
    """Magnus 型：e_sat = A·exp(B·T/(C+T))"""
    A, B, C = coeff
    return A * math.exp(B * T / (C + T))

def _dedt_magnus(T, coeff):
    A, B, C = coeff
    return _esat_magnus(T, coeff) * (B * C) / (C + T) ** 2

def _invert_magnus(e, coeff):
    """Magnus 型解析反算：由 e 直接解 T。"""
    A, B, C = coeff
    t1 = math.log(e / A)
    return C * t1 / (B - t1)

def _esat_goff(T, coeff):
    """Goff 型：log10(e_sat) 多项式。"""
    A, B, C, D, E, F, G, H, I = coeff
    Tk = T + 273.15
    return 10 ** (B * (1 - A / Tk) + C * math.log10(Tk / A) +
                  D * (1 - 10 ** (E * (Tk / A - 1))) +
                  F * (10 ** (G * (1 - A / Tk)) - 1) +
                  I * (1 - Tk / A) + H)

def _dedt_goff(T, coeff):
    """Goff 型解析导数。
    对 u = log10(e_sat) 逐项求导（e_sat = 10^u ⇒ de/dT = e·ln10·du/dT）：
      B·(1-A/Tk)        -> +B·A/Tk²
      C·log10(Tk/A)     -> +C/(Tk·ln10)            ← 旧版误写为 C/A·log10(Tk/A)·ln10
      D·(1-10^(E(Tk/A-1))) -> -D·E·ln10·10^(E(Tk/A-1))/A
      F·(10^(G(1-A/Tk))-1) -> +A·F·G·ln10·10^(G(1-A/Tk))/Tk²
      I·(1-Tk/A)        -> -I/A
    旧版的第二项使 goff 族三条公式的导数最大偏差达 18%~40%（Goff2-水面 40%），
    根不变但牛顿迭代的收敛质量与"可视化拟合"展示的斜率都是错的。"""
    A, B, C, D, E, F, G, H, I = coeff
    Tk = T + 273.15
    d = (B * A / Tk ** 2 + C / (Tk * math.log(10)) -
         D * E / A * math.log(10) * 10 ** (E * (Tk / A - 1)) +
         A * F * G / Tk ** 2 * 10 ** (G * (1 - A / Tk)) * math.log(10) - I / A)
    return _esat_goff(T, coeff) * math.log(10) * d

def _esat_wexler(T, coeff):
    """Wexler 型：ln(e_sat) 多项式，结果 /100 由 Pa 换算 hPa。"""
    A, B, C, D, E, F, G = coeff
    Tk = T + 273.15
    ln_e = (A / Tk + B + C * Tk + D * Tk ** 2 + E * Tk ** 3 +
            F * Tk ** 4 + G * math.log(Tk))
    return math.exp(ln_e) / 100

def _dedt_wexler(T, coeff):
    A, B, C, D, E, F, G = coeff
    Tk = T + 273.15
    return _esat_wexler(T, coeff) * (-A / Tk ** 2 + C + 2 * D * Tk +
                                     3 * E * Tk ** 2 + 4 * F * Tk ** 3 + G / Tk)

def _esat_gili(T, coeff):
    """Gili 型经验式。
    e_sat = 1013.25 · 10^[0.00141966 - 3.142305(1000/Tk - 1000/373.16)
                          + 8.2·lg(373.16/Tk) - 0.0024804(373.16 - Tk)]
    前因子是 373.16 K（水沸点）处的饱和水汽压，按定义 = 1 atm = 1013.25 hPa。
    旧版写成 980.66（= 1 工程大气压 1 at 的 hPa 数，疑为单位混淆），
    导致全区间恒定偏低约 3.0%（与公开饱和水汽压表对比：0/10/20 ℃ 均 -2.97~-3.04%）。
    改为 1013.25 后残差降到 +0.18~+0.25%。
    注：原始文献未取得，此处依据"参考点自洽性 + 实测残差"判定，
    详见 tests/test_esat_reference.py 的 Gili 用例与 README 的精度表。"""
    Tk = T + 273.15
    return 1013.25 * 10 ** (0.00141966 - 3.142305 * (1e3 / Tk - 1e3 / 373.16) +
                            8.2 * math.log10(373.16 / Tk) - 0.0024804 * (373.16 - Tk))

def _dedt_gili(T, coeff):
    Tk = T + 273.15
    e = _esat_gili(T, coeff)
    return e * math.log(10) * (3142.305 / Tk ** 2 - 3.561215 / Tk + 0.0024804)

def _esat_marti(T, coeff):
    """Marti 型经验式（冰面）。"""
    Tk = T + 273.15
    return 10 ** (-2663.5 / Tk + 12.537) / 100

def _dedt_marti(T, coeff):
    Tk = T + 273.15
    return _esat_marti(T, coeff) * math.log(10) * 2663.5 / Tk ** 2

# 公式族注册表：family -> 能力函数（esat/dedt 必填，invert 可选）
_FAMILY_TABLE = {
    'magnus': dict(esat=_esat_magnus, dedt=_dedt_magnus, invert=_invert_magnus),
    'goff':   dict(esat=_esat_goff,   dedt=_dedt_goff),
    'wexler': dict(esat=_esat_wexler, dedt=_dedt_wexler),
    'gili':   dict(esat=_esat_gili,   dedt=_dedt_gili),
    'marti':  dict(esat=_esat_marti,  dedt=_dedt_marti),
}

# ---------------------------- 公式注册表 ----------------------------
# 每行 dict: {name, family, coeff, tmin, tmax}
FORMULAS = []
_FORMULA_INDEX = {}

def register_formula(name, family, coeff, tmin, tmax):
    """登记一个公式。name 全程序唯一；family 必须是 _FAMILY_TABLE 的键。"""
    if family not in _FAMILY_TABLE:
        raise ValueError(f"未知公式族: {family}，可选 {list(_FAMILY_TABLE)}")
    if name in _FORMULA_INDEX:
        raise ValueError(f"公式已存在: {name}")
    entry = dict(name=name, family=family, coeff=tuple(coeff), tmin=tmin, tmax=tmax)
    FORMULAS.append(entry)
    _FORMULA_INDEX[name] = entry
    return entry

def get_formula(name):
    """按名字查公式（O(1)）。"""
    return _FORMULA_INDEX[name]

def iter_formulas():
    """遍历全部公式（按注册顺序）。"""
    return iter(FORMULAS)

# 14 个公式（顺序 = 原 methods 顺序；原 MAGNUS/GOFF/WEXLER 三字典已并入）
register_formula('Goff-水面',    'goff',   (273.15, 10.79574, -5.02808, 1.50475e-4, -8.2969, 0.42873e-3, 4.76955, 0.78614, 0), -10, 100)
register_formula('Wexler-水面',  'wexler', (-5800.2206, 1.3914993, -0.048640239, 0.41764768e-4, -0.14452093e-7, 0, 6.5459673), -10, 200)
register_formula('Buck-水面',    'magnus', (6.1121, 17.502, 240.97), 0, 80)
register_formula('Tetens-水面',  'magnus', (6.1078, 17.269, 237.3), 0, 50)
register_formula('Magnus-水面',  'magnus', (6.112, 17.62, 243.12), 0, 60)
register_formula('August-水面',  'magnus', (6.1094, 17.625, 243.04), 0, 60)
register_formula('Arden-水面',   'magnus', (6.1121, 18.678, 257.14), 0, 100)
register_formula('Gili-水面',    'gili',   (), -10, 20)
# Goff2-水面 = Goff-Gratch(1946) 水面式，参考温度 A=373.16 K、lg(1013.246)。
# 旧版第 4 个系数写成 1.3816e-5（标准值为 1.3816e-7，差 100 倍），
# 使该项在低温段严重超重：0 ℃ -3.5%、10 ℃ -1.7%、20 ℃ -0.9%，50 ℃ 才收敛。
register_formula('Goff2-水面',   'goff',   (373.15, 7.90298, -5.02808, 1.3816e-7, -11.344, 0.0081328, 3.49149, 3.0057149, 0), -10, 100)
register_formula('Goff-冰面',    'goff',   (273.15, 9.09718, 3.56654, 0, 0, 0, 0, 0.78614, 0.876793), -100, 10)
register_formula('Wexler-冰面',  'wexler', (-5674.5359, 6.3925247, -0.009677843, 0.62215701e-6, 0.20747825e-8, -0.9484024e-12, 4.1635019), -150, 10)
register_formula('Magnus-冰面',  'magnus', (6.112, 22.46, 272.62), -65, 0)
register_formula('Buck-冰面',    'magnus', (6.1115, 22.452, 272.55), -80, 0)
register_formula('Marti-冰面',   'marti',  (), -150, 0)

# ---------------------------- 公共计算 API ---------------------------
def calculate_esat(T, method='Magnus-水面'):
    """饱和水蒸气压 e_sat(hPa)，T 为摄氏度。"""
    f = get_formula(method)
    return _FAMILY_TABLE[f['family']]['esat'](T, f['coeff'])

def calculate_dedt(T, method, delta=1e-3):
    """d e_sat/dT：优先解析导数，未注册的族回退中心差分。"""
    f = get_formula(method)
    dedt = _FAMILY_TABLE[f['family']]['dedt']
    if dedt:
        return dedt(T, f['coeff'])
    return (calculate_esat(T + delta, method) - calculate_esat(T - delta, method)) / (2 * delta)

def esat_calculate(e, method, max_iter=500, tol=1e-6, mint=None, maxt=None):
    """由蒸气压 e(hPa) 反求温度 T(℃)：有解析反算则直算，否则二分。
    二分按区间宽度 ≤ 2·tol 收敛（返回误差 ≤ tol，与 e_sat 斜率无关）。

    mint/maxt 缺省取本工具的**全域温度域** [T_MIN, T_MAX]（= [-150, 200]），
    而不是公式自己声明的 [tmin, tmax]：反算天生要略微越出公式声明的适用域——
    例如 Buck-水面 声明 0~80 ℃，但 0 ℃ 且 RH<100% 时露点必然为负。
    用公式声明域去截断会让"0 ℃、RH=60%"这种日常输入直接报错。

    真正的病态输入（e 小到全域下界都达不到、或大于上界）在这里抛 InputError，
    而不是像旧版那样把二分下界 -150 ℃ 当成"露点温度"正常返回。"""
    f = get_formula(method)
    lo = T_MIN if mint is None else float(mint)
    hi = T_MAX if maxt is None else float(maxt)
    e = _finite(e, '蒸气压')
    if e <= 0:
        raise InputError(f"蒸气压必须大于 0（收到 {e:g} hPa）")
    e_lo, e_hi = calculate_esat(lo, method), calculate_esat(hi, method)
    if e < e_lo:
        raise InputError(
            f"{method} 在 {lo:g} ℃ 处的饱和蒸气压为 {e_lo:.4g} hPa，"
            f"已高于给定的蒸气压 {e:.4g} hPa —— 所需露点低于本工具温度域下界 {lo:g} ℃")
    if e > e_hi:
        raise InputError(
            f"{method} 在 {hi:g} ℃ 处的饱和蒸气压为 {e_hi:.4g} hPa，"
            f"低于给定的蒸气压 {e:.4g} hPa —— 所需露点高于本工具温度域上界 {hi:g} ℃")
    invert = _FAMILY_TABLE[f['family']].get('invert')
    if invert:
        return min(max(invert(e, f['coeff']), lo), hi)
    for _ in range(max_iter):
        t = (lo + hi) / 2
        if (hi - lo) <= 2 * tol:
            return t
        if calculate_esat(t, method) - e > 0:
            hi = t
        else:
            lo = t
    return (lo + hi) / 2

def _add(results, on_result, method, result1, result2=None, rh=None):
    """结果收集：写入列表，并可选通知回调（对接 CalculatorMemory.add_result）。"""
    entry = dict(method=method, result1=result1, result2=result2, rh=rh)
    results.append(entry)
    if on_result:
        on_result(entry)
    return entry

def _solve_wetbulb(T_dry, e, P, guess, formula, max_iter, tol, on_iter=None):
    """共享牛顿迭代：解湿球方程 e_sat(Tw) − γ·(T_dry−Tw) = e。
    返回 (T_w, 状态)；状态 ∈ {ok, 残差过大, 未收敛, 数值溢出, 错误:…}。"""
    name = formula['name']
    fam = _FAMILY_TABLE[formula['family']]
    esat, dedt = fam['esat'], fam['dedt']
    k1, k2 = 0.000667, 0.000667 * 0.00115 * P
    T_w = guess
    try:
        for it in range(max_iter):
            e_sat = esat(T_w, formula['coeff'])
            gamma = k1 * (1 + 0.00115 * T_w) * P
            f = e_sat - gamma * (T_dry - T_w) - e
            df_dT = dedt(T_w, formula['coeff']) + gamma - k2 * (T_dry - T_w)
            T_new = T_w - f / df_dT
            if on_iter:
                on_iter(name, it + 1, T_w, abs(f))
            if abs(T_new - T_w) < tol and it >= 4:
                return T_new, 'ok'
            if abs(f) > 1e3:
                return T_w, '残差过大'
            T_w = T_new
        return T_w, '未收敛'
    except OverflowError:
        return guess, '数值溢出'
    except Exception as ex:
        return guess, f'错误: {ex}'

def calculate_wetbulb(initial_guess, T, Td, P=1013.25, max_iter=50, tol=1e-6,
                      on_result=None, on_iter=None):
    """模式0：已知干球 T、露点 Td，求湿球温度（逐公式）。返回结果列表。

    适用域按真正参与计算的 T 与 Td 判定。旧版拿 initial_guess 去比对 tmin/tmax
    ——那是牛顿迭代的起点，是用户随手填的数，与公式是否适用无关。"""
    check_temperature(T, '干球温度')
    check_temperature(Td, '露点温度')
    check_pressure(P)
    results = []
    for f in FORMULAS:
        name = f['name']
        if not (f['tmin'] <= T <= f['tmax'] and f['tmin'] <= Td <= f['tmax']):
            _add(results, on_result, name, '不适用')
            continue
        e = calculate_esat(Td, name)
        T_w, status = _solve_wetbulb(T, e, P, initial_guess, f, max_iter, tol, on_iter)
        if status == 'ok':
            rh = e / calculate_esat(T, name)
            _add(results, on_result, name, T_w, rh=rh) if 0 <= rh <= 1 \
                else _add(results, on_result, name, '结果不符常理')
        else:
            _add(results, on_result, name, status)
    return results

def calculate_dewpoint(T_g, T_w, P, max_iter=500, tol=1e-6,
                       on_result=None, on_iter=None):
    """模式1：已知干球 T_g、湿球 T_w，求露点温度。"""
    check_temperature(T_g, '干球温度')
    check_temperature(T_w, '湿球温度')
    check_pressure(P)
    results = []
    for f in FORMULAS:
        name = f['name']
        # 两个温度只要有一个落在公式适用域外，这条公式就不适用（旧版写成 and，
        # 等于"两个都在域外才判不适用"，会让冰面公式在 13.3 ℃ 这类暖端照常出数）。
        if (T_w < f['tmin'] or T_w > f['tmax']) or (T_g < f['tmin'] or T_g > f['tmax']):
            _add(results, on_result, name, '不适用')
            continue
        es_wet = calculate_esat(T_w, name)
        es_dry = calculate_esat(T_g, name)
        e = es_wet - 0.000667 * (1 + 0.00115 * T_w) * P * (T_g - T_w)
        rh = e / es_dry
        if e >= es_dry or rh >= 1:
            _add(results, on_result, name, T_g, rh=1)
        else:
            try:
                Td = esat_calculate(e, name, max_iter, tol)
                _add(results, on_result, name, Td, rh=rh)
            except ZeroDivisionError:
                _add(results, on_result, name, T_g, rh=rh)
            except InputError as ex:
                _add(results, on_result, name, str(ex))
            except Exception:
                _add(results, on_result, name, '计算失败')
    return results

def calculate_both(initial_guess, T_g, rh, P=1013.25, max_iter=50, tol=1e-6,
                   on_result=None, on_iter=None):
    """模式2：已知干球 T_g、相对湿度 rh(%)，同时求露点与湿球。"""
    check_temperature(T_g, '干球温度')
    check_relative_humidity(rh)
    check_pressure(P)
    results = []
    rh_d = rh / 100
    for f in FORMULAS:
        name = f['name']
        if not (f['tmin'] <= T_g <= f['tmax']):
            _add(results, on_result, name, '不适用')
            continue
        try:
            e = calculate_esat(T_g, name) * rh_d
            Td = esat_calculate(e, name, max_iter, tol)
            T_w, status = _solve_wetbulb(T_g, e, P, initial_guess, f, max_iter, tol, on_iter)
            if status == 'ok':
                _add(results, on_result, name, Td, T_w)
            elif status == '残差过大':
                _add(results, on_result, name, Td, '湿球残差过大')
            elif status == '未收敛':
                _add(results, on_result, name, Td, '湿球未收敛')
            elif status == '数值溢出':
                _add(results, on_result, name, '数值溢出')
            else:
                _add(results, on_result, name, status)
        except OverflowError:
            _add(results, on_result, name, '数值溢出')
        except Exception as ex:
            _add(results, on_result, name, f'错误: {ex}')
    return results

# ------------------------ 扩展气象参数（派生量） ------------------------
def derive_moist_air(T_g, T_w, Td, rh, P=1013.25, method='Goff-水面'):
    """由干球 T_g(℃)、湿球 T_w(℃)、露点 Td(℃)、相对湿度 rh(0~1)、压强 P(hPa)
    推导"常用气象参数"面板的全部派生量，返回 dict。

    T_w 仅用于取湿球饱和水汽压 esw；Td 决定实际水汽压 e；rh 仅用于 LCL。
    比热容与气体常数一律用 J/(kg·K)（比气体常数），不得与摩尔气体常数混用。

    返回字段（单位见括注）：
      e/es/esw(hPa)  P_dry(hPa)  x(-)  gamma_mix(-)  v_sound(m/s)
      ro_dry/ro_vapor/ro(kg/m³)  dm1(g/kg)  L_v(kJ/kg)  han(kJ/kg)
      sat_mixing_ratio(g/kg)  absolute_humidity(g/m³)  specific_humidity(g/kg)
      q(kg/kg)  virtual_temp_K/theta_K/theta_e_K/theta_v_K(K)
      t_lcl_C(℃)  p_lcl_hPa(hPa)   —— rh<=0 或 LCL 不可解时为 nan
    """
    check_temperature(T_g, '干球温度')
    check_temperature(T_w, '湿球温度')
    check_temperature(Td, '露点温度')
    check_pressure(P)
    rh = _finite(rh, '相对湿度')
    if not (0.0 <= rh <= 1.0):
        raise InputError(f"相对湿度（小数）需在 [0, 1] 范围内（收到 {rh:g}）")

    T_g_K = T_g + 273.15
    Cp = 1004.7463 + 0.05 * T_g      # 干空气定压比热 (J/(kg·K))
    Cpw = 1864                       # 水汽定压比热   (J/(kg·K))
    # 定容比热必须由"比气体常数"换算：Cv = Cp - Rd。
    # 旧版写 Cv = Cp - R（R 是 8.314 的摩尔气体常数），量纲不匹配，
    # 使湿空气绝热指数 gamma_mix ≈ 1.008 而不是 ≈ 1.40，声速 295 m/s（正确 ≈ 347 m/s）。
    Cv = Cp - RD
    Cvw = Cpw - RV
    ups = EPSILON
    upsilon = (1 - ups) / ups        # 0.6078，虚温系数

    es = calculate_esat(T_g, method)
    esw = calculate_esat(T_w, method)
    e = calculate_esat(Td, method)
    P_dry = P - e
    x = e / P                                            # 水汽摩尔分数
    gamma_mix = ((1 - x) * Cp + x * Cpw) / ((1 - x) * Cv + x * Cvw)
    M_mix = ((1 - x) * MD + x * MV) / 1000               # 湿空气平均摩尔质量 kg/mol
    v_sound = (gamma_mix * R_UNIVERSAL * T_g_K / M_mix) ** 0.5

    ro_dry = P_dry * 100 / (RD * T_g_K)
    # 水汽密度由"实际水汽压 e"决定；旧版误用 esw（湿球饱和水汽压），
    # 使水蒸气密度、含湿量、空气密度在未饱和时系统性偏大。
    ro_vapor = e * 100 / (RV * T_g_K)
    ro = ro_dry + ro_vapor
    dm = ro_vapor / ro_dry            # 混合率 = ρv/ρd = ε·e/(P-e)
    dm1 = dm * 1000
    L_v = 2500.8 - 2.3665 * T_g - 0.0023 * T_g ** 2 + 1.87e-5 * T_g ** 3 - 4.2e-8 * T_g ** 4
    han = Cp / 1000 * T_g + (L_v + Cpw / 1000 * T_g) * dm   # kJ/kg 干空气

    # 饱和混合率用饱和水汽压 es（旧版误用实际水汽压 e，得到的是"混合率"而不是"饱和混合率"）
    sat_mixing_ratio = ups * (es / (P - es)) * 1000 if P > es else 0
    absolute_humidity = (e * 100) / (RV * T_g_K) * 1e3
    specific_humidity = (ups * e) / (P - (1 - ups) * e) * 1000 if P > (1 - ups) * e else 0

    q = specific_humidity / 1000
    virtual_temp_K = T_g_K * (1 + upsilon * q)
    theta_K = T_g_K * (1000 / P) ** (RD / Cp)
    # L_v 上面以 kJ/kg 计，指数里必须换算成 J/kg（旧版直接用 kJ/kg，
    # 相当于潜热被缩小 1000 倍，相当位温退化成位温）。
    theta_e_K = theta_K * math.exp(L_v * 1000 * q / (Cp * T_g_K))
    theta_v_K = theta_K * (1 + upsilon * q)

    try:
        t_lcl_C = 1 / (1 / (Td - 56) - math.log(rh) / 800) + 56
        p_lcl_hPa = P * ((t_lcl_C + 273.15) / T_g_K) ** (Cp / RD)
    except (ValueError, ZeroDivisionError, OverflowError):
        t_lcl_C = p_lcl_hPa = float('nan')

    return dict(
        e=e, es=es, esw=esw, P_dry=P_dry, x=x, gamma_mix=gamma_mix, v_sound=v_sound,
        ro_dry=ro_dry, ro_vapor=ro_vapor, ro=ro, dm=dm, dm1=dm1, L_v=L_v, han=han,
        sat_mixing_ratio=sat_mixing_ratio, absolute_humidity=absolute_humidity,
        specific_humidity=specific_humidity, q=q,
        virtual_temp_K=virtual_temp_K, theta_K=theta_K, theta_e_K=theta_e_K,
        theta_v_K=theta_v_K, t_lcl_C=t_lcl_C, p_lcl_hPa=p_lcl_hPa,
    )


# ------------------------------ 自检 ------------------------------
if __name__ == '__main__':
    # 等价性回归：确认重构没有改变 Goff-水面 的数值（对照主程序 v1.2.2 的已知结果）。
    # 注意这是"自我回归"，构造上发现不了继承来的系统偏差——
    # 正确性验证（对照 WMO/ASHRAE 公开参考值）在 tests/ 里，由 CI 执行：
    #     python -m pytest -q
    w = {r['method']: r for r in calculate_wetbulb(15, 25, 15)}
    assert abs(w['Goff-水面']['result1'] - 18.6186) < 1e-3
    d = {r['method']: r for r in calculate_dewpoint(25, 20, 1013.25)}
    assert abs(d['Goff-水面']['result1'] - 17.4430) < 1e-3
    b = {r['method']: r for r in calculate_both(25, 25, 60)}
    assert abs(b['Goff-水面']['result1'] - 16.7003) < 1e-3
    assert abs(b['Goff-水面']['result2'] - 19.5676) < 1e-3
    print(f"[core 等价性回归 OK] tag={tag}, 公式数={len(FORMULAS)}")
    print("  正确性验证请运行: python -m pytest -q")
