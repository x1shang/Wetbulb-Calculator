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

tag = "v1.3.0"          # 版本号（与 about.py 中文本保持同步）
tot = 1e-7              # 默认迭代精度
g = load_g_value()      # 重力加速度

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
    A, B, C, D, E, F, G, H, I = coeff
    Tk = T + 273.15
    d = (B * A / Tk ** 2 + C / A * math.log10(Tk / A) * math.log(10) -
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
    """Gili 型经验式。"""
    Tk = T + 273.15
    return 980.66 * 10 ** (0.00141966 - 3.142305 * (1e3 / Tk - 1e3 / 373.16) +
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
register_formula('Goff2-水面',   'goff',   (373.15, 7.90298, -5.02808, 1.3816e-5, -11.344, 0.0081328, 3.49149, 3.0057149, 0), -10, 100)
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

def esat_calculate(e, method, max_iter=500, tol=1e-6, mint=-150, maxt=200):
    """由蒸气压 e(hPa) 反求温度 T(℃)：有解析反算则直算，否则二分。
    二分按区间宽度 ≤ 2·tol 收敛（返回误差 ≤ tol，与 e_sat 斜率无关）。"""
    f = get_formula(method)
    invert = _FAMILY_TABLE[f['family']].get('invert')
    if invert:
        return invert(e, f['coeff'])
    for _ in range(max_iter):
        t = (mint + maxt) / 2
        if (maxt - mint) <= 2 * tol:
            return t
        if calculate_esat(t, method) - e > 0:
            maxt = t
        else:
            mint = t
    return (mint + maxt) / 2

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
    """模式0：已知干球 T、露点 Td，求湿球温度（逐公式）。返回结果列表。"""
    results = []
    for f in FORMULAS:
        name = f['name']
        if not (f['tmin'] <= initial_guess <= f['tmax']):
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
    results = []
    for f in FORMULAS:
        name = f['name']
        if (T_w < f['tmin'] or T_w > f['tmax']) and (T_g < f['tmin'] or T_g > f['tmax']):
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
            except Exception:
                _add(results, on_result, name, '计算失败')
    return results

def calculate_both(initial_guess, T_g, rh, P=1013.25, max_iter=50, tol=1e-6,
                   on_result=None, on_iter=None):
    """模式2：已知干球 T_g、相对湿度 rh(%)，同时求露点与湿球。"""
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

# ------------------------------ 自检 ------------------------------
if __name__ == '__main__':
    # 与主程序 v1.2.2 已知结果对比（Goff-水面）
    w = {r['method']: r for r in calculate_wetbulb(15, 25, 15)}
    assert abs(w['Goff-水面']['result1'] - 18.6186) < 1e-3
    d = {r['method']: r for r in calculate_dewpoint(25, 20, 1013.25)}
    assert abs(d['Goff-水面']['result1'] - 17.4430) < 1e-3
    b = {r['method']: r for r in calculate_both(25, 25, 60)}
    assert abs(b['Goff-水面']['result1'] - 16.7003) < 1e-3
    assert abs(b['Goff-水面']['result2'] - 19.5676) < 1e-3
    print(f"[core self-check OK] tag={tag}, 公式数={len(FORMULAS)}")
