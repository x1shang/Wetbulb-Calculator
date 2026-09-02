
import os
import sys
import math
import json

# ======================================================================
# 二、公式族计算器（FAMILY）：每种“公式形态”的求值/求导/反算函数
# ======================================================================
# 说明：下面每个 _esat_xxx(T, coeff) 返回“饱和水蒸气压 e_sat（hPa）”，
#       _dedt_xxx(T, coeff) 返回 e_sat 对温度 T 的导数 d e_sat/dT。
#       T 一律为摄氏度，coeff 是本族公式的系数元组（无系数时传空元组 ()）。
# 系数含义与单位（重要，新增公式时照抄即可）：
#   Magnus 族 (A, B, C)：e_sat = A·exp(B·T/(C+T))，A≈6.1(hPa)，B/C 为拟合常数
#   Goff   族 (A..I)    ：以 log10 多项式逼近，A 为参考温度(K)，H 为常数项
#   Wexler 族 (A..G)   ：以 ln 多项式逼近，结果需 /100 从 Pa 换算为 hPa
#   Gili / Marti       ：各自独立的经验式（无系数，coeff 传 ()）
# ----------------------------------------------------------------------

def _esat_magnus(T, coeff):
    """Magnus 型（指数式）：e_sat = A·exp(B·T/(C+T))"""
    A, B, C = coeff
    return A * math.exp(B * T / (C + T))

def _dedt_magnus(T, coeff):
    """Magnus 型解析导数：d e_sat/dT = e_sat·B·C/(C+T)²"""
    A, B, C = coeff
    return _esat_magnus(T, coeff) * (B * C) / (C + T) ** 2

def _invert_magnus(e, coeff):
    """Magnus 型解析反算：由蒸气压 e 直接解出温度 T（无需迭代）。
    公式推导：对 e=A·exp(BT/(C+T)) 两边取 ln → T = C·ln(e/A)/(B-ln(e/A))"""
    A, B, C = coeff
    t1 = math.log(e / A)
    return C * t1 / (B - t1)

def _esat_goff(T, coeff):
    """Goff 型（对数多项式）：log10(e_sat) = 多项求和 + H"""
    A, B, C, D, E, F, G, H, I = coeff
    Tk = T + 273.15                      # 摄氏 → 开尔文
    term1 = B * (1 - A / Tk)
    term2 = C * math.log10(Tk / A)
    term3 = D * (1 - 10 ** (E * (Tk / A - 1)))
    term4 = F * (10 ** (G * (1 - A / Tk)) - 1)
    term5 = I * (1 - Tk / A)
    return 10 ** (term1 + term2 + term3 + term4 + term5 + H)

def _dedt_goff(T, coeff):
    """Goff 型解析导数（链式法则：d e/dT = e·ln10·(d log10 e/dT)）"""
    A, B, C, D, E, F, G, H, I = coeff
    Tk = T + 273.15
    term1 = B * A / Tk ** 2
    term2 = C / A * math.log10(Tk / A) * math.log(10)
    term3 = -D * E / A * math.log(10) * 10 ** (E * (Tk / A - 1))
    term4 = A * F * G / Tk ** 2 * 10 ** (G * (1 - A / Tk)) * math.log(10)
    term5 = -I / A
    return _esat_goff(T, coeff) * math.log(10) * (term1 + term2 + term3 + term4 + term5)

def _esat_wexler(T, coeff):
    """Wexler 型（ln 多项式）：ln e_sat = Σ 项，结果 /100 从 Pa→hPa"""
    A, B, C, D, E, F, G = coeff
    Tk = T + 273.15
    ln_e = (A / Tk + B + C * Tk + D * Tk ** 2 + E * Tk ** 3 +
            F * Tk ** 4 + G * math.log(Tk))
    return math.exp(ln_e) / 100

def _dedt_wexler(T, coeff):
    """Wexler 型解析导数：d e/dT = e·(d ln e/dT)"""
    A, B, C, D, E, F, G = coeff
    Tk = T + 273.15
    d_ln = -A / Tk ** 2 + C + 2 * D * Tk + 3 * E * Tk ** 2 + 4 * F * Tk ** 3 + G / Tk
    return _esat_wexler(T, coeff) * d_ln

def _esat_gili(T, coeff):
    """Gili 型经验式（单位 hPa）"""
    Tk = T + 273.15
    t1 = -3.142305 * (1e3 / Tk - 1e3 / 373.16)
    t2 = 8.2 * math.log10(373.16 / Tk)
    t3 = -0.0024804 * (373.16 - Tk)
    return 980.66 * 10 ** (0.00141966 + t1 + t2 + t3)

def _dedt_gili(T, coeff):
    """Gili 型解析导数"""
    Tk = T + 273.15
    t1 = -3.142305 * (1e3 / Tk - 1e3 / 373.16)
    t2 = 8.2 * math.log10(373.16 / Tk)
    t3 = -0.0024804 * (373.16 - Tk)
    t4 = 3142.305 / Tk ** 2 - 3.561215 / Tk + 0.0024804
    return 980.66 * 10 ** (0.00141966 + t1 + t2 + t3) * math.log(10) * t4

def _esat_marti(T, coeff):
    """Marti 型经验式（冰面，单位 hPa）"""
    Tk = T + 273.15
    return 10 ** (-2663.5 / Tk + 12.537) / 100

def _dedt_marti(T, coeff):
    """Marti 型解析导数"""
    Tk = T + 273.15
    return _esat_marti(T, coeff) * math.log(10) * 2663.5 / Tk ** 2

# ----------------------------------------------------------------------
# 公式族注册表：family 名 → 该族的能力函数
#   键说明：
#     esat   : 必填，求 e_sat 的函数 (T, coeff) -> float
#     dedt   : 必填，求导数  的函数 (T, coeff) -> float
#     invert : 可选，解析反算  (e, coeff) -> T；缺省时 esat_calculate 用二分法
#   新增“公式族”的方法：照抄一行，填好三个函数即可。
# ----------------------------------------------------------------------
_FAMILY_TABLE = {
    'magnus': dict(esat=_esat_magnus, dedt=_dedt_magnus, invert=_invert_magnus),
    'goff':   dict(esat=_esat_goff,   dedt=_dedt_goff),
    'wexler': dict(esat=_esat_wexler, dedt=_dedt_wexler),
    'gili':   dict(esat=_esat_gili,   dedt=_dedt_gili),
    'marti':  dict(esat=_esat_marti,  dedt=_dedt_marti),
}

# ======================================================================
# 三、公式注册表（FORMULAS）：所有公式统一在这里登记
# ======================================================================
# 每行 = 一个 dict，字段说明：
#   name  : 显示名（全程序唯一，用于查表）
#   family: 属于哪个公式族（必须是 _FAMILY_TABLE 里的键）
#   coeff : 系数元组（顺序与上面族函数的解包顺序一致；无系数写 ()）
#   tmin/tmax: 适用温度区间（℃），用于“不适用”判断与公式筛选
#
# 【以后新增公式】只需追加一行 register_formula(...)，例如想注册一个
# 新的 Magnus 水面公式：
#   register_formula('MyNew-水面', 'magnus', (6.11, 17.6, 240.0), 0, 60)
# 若新公式形态没有现成族，则先在 _FAMILY_TABLE 里加一族（3个函数），再注册。
# ----------------------------------------------------------------------

FORMULAS = []          # 公式列表（保持注册顺序 = 展示顺序）
_FORMULA_INDEX = {}    # name -> 公式dict 的索引表（查表 O(1)）

def register_formula(name, family, coeff, tmin, tmax):
    """向注册表登记一个公式。返回登记好的公式 dict。"""
    if family not in _FAMILY_TABLE:
        raise ValueError(f"未知公式族: {family}，可选 {list(_FAMILY_TABLE)}")
    if name in _FORMULA_INDEX:
        raise ValueError(f"公式已存在: {name}")
    entry = dict(name=name, family=family, coeff=tuple(coeff), tmin=tmin, tmax=tmax) # tuple使得coeff变成元组
    FORMULAS.append(entry) # 在列表末尾增加项（即公式）
    _FORMULA_INDEX[name] = entry
    return entry

def get_formula(name):
    """按名字查公式，O(1) 查表。查不到抛 KeyError（调用方会转成错误提示）。"""
    return _FORMULA_INDEX[name]

# 统一注册表（顺序与原 methods 一致）
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

# 兼容旧代码习惯：如果你/旧代码里还写着 for name, condition in methods，
# 可用下面这个生成器替代（此处仅作说明，不再定义 methods 变量）。
def iter_formulas():
    """遍历全部公式（按注册顺序）。"""
    return iter(FORMULAS)

# ======================================================================
# 四、公共计算 API
# ======================================================================

def calculate_esat(T, method='Magnus-水面'):
    f = get_formula(method)
    return _FAMILY_TABLE[f['family']]['esat'](T, f['coeff'])

def calculate_dedt(T, method, delta=1e-3):
    """d e_sat/dT。优先用各族解析导数（快且精确）；
    未注册解析导数的族回退为中心差分。"""
    f = get_formula(method)
    dedt = _FAMILY_TABLE[f['family']]['dedt']
    if dedt:
        return dedt(T, f['coeff'])
    # 数值差分回退：(f(T+δ)-f(T-δ)) / 2δ （暂时没有使用以下代码的method）
    return (calculate_esat(T + delta, method) - calculate_esat(T - delta, method)) / (2 * delta)

def esat_calculate(e, method, max_iter=500, tol=1e-6, mint=-150, maxt=200):
    """由蒸气压 e（hPa）反求温度 T（℃）——“求露点”的核心。
    流程：能解析反算（如 Magnus 族）直接算；否则在 [mint, maxt] 上二分。
    收敛判据：区间宽度 ≤ 2·tol 即返回中点（误差 ≤ tol，且与 e_sat 斜率无关）。
    与原版的差异：
      不再强制迭代100次
      采取所求的温度值判断是否继续迭代而非利用气压判据，逻辑上更为通顺
      """
    f = get_formula(method)
    invert = _FAMILY_TABLE[f['family']].get('invert')
    if invert:
        return invert(e, f['coeff'])
    for _ in range(max_iter):
        t = (mint + maxt) / 2
        if (maxt - mint) <= 2 * tol:                # 区间足够窄 → 中点即答案
            return t
        if calculate_esat(t, method) - e > 0:
            maxt = t
        else:
            mint = t
    return (mint + maxt) / 2

def _add(results, on_result, method, result1, result2=None, rh=None):
    """结果收集小工具：同时写入 results 列表，并（可选）通知回调。
    条目的 dict 结构与主程序 CalculatorMemory.methods 完全一致，
    方便以后直接喂给 CalculatorMemory。"""
    entry = dict(method=method, result1=result1, result2=result2, rh=rh)
    results.append(entry)
    if on_result:
        on_result(entry)
    return entry

def _solve_wetbulb(T_dry, e, P, guess, formula, max_iter, tol, on_iter=None):
    """【共享牛顿迭代驱动】对单个公式求湿球温度。
    物理方程（湿球方程）：e_sat(Tw) − γ·(T_dry − Tw) = e
      其中 γ = 0.000667·(1+0.00115·Tw)·P 为干湿表常数，
      e 为“目标水汽压”（已知露点时 e=esat(Td)；已知 RH 时 e=esat(Td)·RH）。
    用牛顿法求根 f(Tw)=0：Tw_new = Tw − f / f'，f'=de_sat/dT + γ − 0.000667·0.00115·P·(T_dry−Tw)
    返回 (收敛值或最后值, 状态字符串)。状态 ∈ {ok, 残差过大, 未收敛, 数值溢出, 错误:…}
    效率点：γ 与 f' 中共用的常量 0.000667·0.00115·P 提到循环外计算一次。"""
    name = formula['name']
    fam = _FAMILY_TABLE[formula['family']]
    esat, dedt = fam['esat'], fam['dedt']
    k1, k2 = 0.000667, 0.000667 * 0.00115 * P     # 常量提出循环
    T_w = guess
    try:
        for it in range(max_iter):
            e_sat = esat(T_w, formula['coeff'])
            gamma = k1 * (1 + 0.00115 * T_w) * P
            f = e_sat - gamma * (T_dry - T_w) - e
            df_dT = dedt(T_w, formula['coeff']) + gamma - k2 * (T_dry - T_w)
            T_new = T_w - f / df_dT
            if on_iter:                            # 记录本次迭代（供收敛图）
                on_iter(name, it + 1, T_w, abs(f))
            if abs(T_new - T_w) < tol and it >= 4:  # 收敛（与原版一致，至少迭代5次）
                return T_new, 'ok'
            if abs(f) > 1e3:                        # 残差爆炸，判定发散
                return T_w, '残差过大'
            T_w = T_new
        return T_w, '未收敛'
    except OverflowError:
        return guess, '数值溢出'
    except Exception as ex:
        return guess, f'错误: {ex}'

def calculate_wetbulb(initial_guess, T, Td, P=1013.25, max_iter=50, tol=1e-6,
                      on_result=None, on_iter=None):
    """模式0：已知干球 T 与露点 Td，求湿球温度（对每个公式算一次）。
    返回结果列表；可选 on_result/on_iter 回调（对接 CalculatorMemory）。
    与原版差异：先判断适用区间再计算 e_sat（原版先算后判断，结果不变、更快）。"""
    results = []
    for f in FORMULAS:
        name = f['name']
        if not (f['tmin'] <= initial_guess <= f['tmax']):   # 初值不在公式适用域
            _add(results, on_result, name, '不适用')
            continue
        e = calculate_esat(Td, name)                        # 目标水汽压
        T_w, status = _solve_wetbulb(T, e, P, initial_guess, f, max_iter, tol, on_iter)
        if status == 'ok':
            rh = e / calculate_esat(T, name)                # 相对湿度校验
            if 0 <= rh <= 1:
                _add(results, on_result, name, T_w, rh=rh)
            else:
                _add(results, on_result, name, '结果不符常理')
        else:
            _add(results, on_result, name, status)
    return results

def calculate_dewpoint(T_g, T_w, P, max_iter=500, tol=1e-6,
                       on_result=None, on_iter=None):
    """模式1：已知干球 T_g 与湿球 T_w，求露点温度。
    由湿球方程反解水汽压 e，再用 esat_calculate 反求露点。"""
    results = []
    for f in FORMULAS:
        name = f['name']
        # 干球、湿球都在公式适用域之外 → 不适用（与原版逻辑一致）
        if (T_w < f['tmin'] or T_w > f['tmax']) and (T_g < f['tmin'] or T_g > f['tmax']):
            _add(results, on_result, name, '不适用')
            continue
        es_wet = calculate_esat(T_w, name)
        es_dry = calculate_esat(T_g, name)
        gamma = 0.000667 * (1 + 0.00115 * T_w) * P
        e = es_wet - gamma * (T_g - T_w)                    # 实际水汽压
        rh = e / es_dry
        if e >= es_dry or rh >= 1:                          # 达到饱和的极端情形
            _add(results, on_result, name, T_g, rh=1)
        else:
            try:
                Td = esat_calculate(e, name, max_iter, tol)
                _add(results, on_result, name, Td, rh=rh)
            except ZeroDivisionError:                       # 解析反算除零 → 回退
                _add(results, on_result, name, T_g, rh=rh)
            except Exception:
                _add(results, on_result, name, '计算失败')
    return results

def calculate_both(initial_guess, T_g, rh, P=1013.25, max_iter=50, tol=1e-6,
                   on_result=None, on_iter=None):
    """模式2：已知干球 T_g 与相对湿度 rh（%），同时求露点 + 湿球。
    先由 esat(T_g)·(rh/100) 得水汽压 → 反算露点，再牛顿求湿球。"""
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
            elif status == '数值溢出':                       # 与原版一致：只记 result1
                _add(results, on_result, name, '数值溢出')
            else:                                            # '错误: …' / '计算失败'
                _add(results, on_result, name, status)
        except OverflowError:
            _add(results, on_result, name, '数值溢出')
        except Exception as ex:
            _add(results, on_result, name, f'错误: {ex}')
    return results

# ======================================================================
# 五、自检与用法示例（python sample.py 运行）
# ======================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("sample.py 自检（对照主程序 v1.2.2 的已知结果）")
    print("=" * 60)

    # —— 1. 模式0：干球25℃、露点15℃、1013.25hPa → 湿球 ~18.6186℃ ——
    wet = {r['method']: r for r in calculate_wetbulb(15, 25, 15, 1013.25)}
    g0 = wet['Goff-水面']
    assert abs(g0['result1'] - 18.6186) < 1e-3, g0
    print(f"模式0 Goff-水面: 湿球={g0['result1']:.4f}℃  相对湿度={g0['rh']*100:.2f}%  [OK]")

    # —— 2. 模式1：干球25℃、湿球20℃ → 露点 ~17.4430℃ ——
    dp = {r['method']: r for r in calculate_dewpoint(25, 20, 1013.25)}
    g1 = dp['Goff-水面']
    assert abs(g1['result1'] - 17.4430) < 1e-3, g1
    print(f"模式1 Goff-水面: 露点={g1['result1']:.4f}℃  相对湿度={g1['rh']*100:.2f}%  [OK]")

    # —— 3. 模式2：干球25℃、RH=60% → 露点 ~16.7003℃、湿球 ~19.5676℃ ——
    both = {r['method']: r for r in calculate_both(25, 25, 60, 1013.25)}
    g2 = both['Goff-水面']
    assert abs(g2['result1'] - 16.7003) < 1e-3 and abs(g2['result2'] - 19.5676) < 1e-3, g2
    print(f"模式2 Goff-水面: 露点={g2['result1']:.4f}℃  湿球={g2['result2']:.4f}℃  [OK]")

    # —— 4. 全部 14 个公式的 e_sat 抽样（验证注册表路由正确）——
    print("\n各公式 e_sat(20℃) 一览（hPa）：")
    for f in FORMULAS:
        try:
            print(f"  {f['name']:<14} {calculate_esat(20, f['name']):>10.4f}")
        except Exception:
            print(f"  {f['name']:<14} （超出适用域/异常）")

    # —— 5. 演示：如何新增一个公式（取消注释即生效）——
    # register_formula('MyNew-水面', 'magnus', (6.11, 17.6, 240.0), 0, 60)
    # print('新增后公式总数:', len(FORMULAS))

    print("\n全部自检通过 [OK]  — 重构结果与主程序一致")
