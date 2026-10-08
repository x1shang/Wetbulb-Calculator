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
# 目录约定（v1.3.1 起的仓库结构）：
#   src/      源码（本文件、src/ui/ 下的界面代码）
#   assets/   图标与默认配置（app.ico / err.ico / cfg.json）
#   tests/ docs/ legacy/ examples/
APP_ICON = 'assets/app.ico'
ERR_ICON = 'assets/err.ico'
CFG_JSON = 'assets/cfg.json'


def project_root():
    """开发环境下的项目根目录（src/core.py 的上两级）。

    用 __file__ 推导，而不是旧版的 os.path.abspath(".")：后者让"在哪个目录敲命令"
    决定能不能找到图标与配置——从别处跑 `python src/main.py` 会静默丢图标。
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative_path):
    """资源定位：exe 打包后(_MEIPASS)与开发目录均可。
    传入相对项目根的路径，例如 `resource_path(APP_ICON)`。"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(project_root(), relative_path)

def cfg_file_path(for_write=False):
    """用户配置文件 cfg.json 的定位（支持手动配置）：
    打包成 exe 后，若 exe 旁存在 cfg.json 则优先使用它；for_write=True
    （保存配置）时始终写 exe 旁，保证用户修改持久化。
    开发环境使用 resource_path(CFG_JSON)（即 assets/cfg.json）。"""
    if hasattr(sys, '_MEIPASS'):
        side = os.path.join(os.path.dirname(sys.executable), 'cfg.json')
        if for_write or os.path.exists(side):
            return side
    return resource_path(CFG_JSON)

def _read_cfg():
    """读取整个 cfg.json；失败返回空 dict。"""
    try:
        with open(cfg_file_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def load_title_color():
    """读 cfg.json 的标题颜色 title_color（格式 "R, G, B"）；
    未配置或格式非法时返回默认青色 rgb(71, 148, 157)。

    v1.3.1 起本函数只在这里实现一次：此前 src/ui/calculator1.py 里有一份
    逐字重复的副本，"配置到底读的是哪一份"取决于谁先被 import。
    """
    color = _read_cfg().get('title_color')
    if isinstance(color, str) and len(color.split(',')) == 3:
        return color.strip()
    return "71, 148, 157"

tag = "v1.3.3"          # 版本号（与 about.py 中文本保持同步）
                        # v1.3.1 = 数值缺陷修复 + 引擎层输入校验 + 外部参照回归。
                        # v1.3.2 = 逐条公式复算后的第二轮数值修复：
                        #   Gili 指数里无出处的 +0.00141966、湿度计方程 A 系数
                        #   （0.000667 → FAO 附录 3 的 0.000660/0.000582）、
                        #   焓值的液态水比热、γ 的混合口径、Bolton LCL、
                        #   4 处过宽的注册适用域、Arden 的三参数式。
                        #   因此 v1.3.2 的数值结果与 v1.3.1 **不同**，不能用同一版本号发布。
tot = 1e-7              # 默认迭代精度
                        # 【已移除 · 打包重建】此处原有一个 `g = load_g_value()`。
                        # 那个"本地重力加速度"从未参与任何计算（B-20），且本工具涉及
                        # 的物理量都不含 g —— 唯一可能用到的 mmHg/cmHg 是**定义值**
                        # （1 mmHg = 133.322387415 Pa），与重力加速度无关。
                        # 因此 g、cfg.json 里的 "g" 键与界面输入框一并删除。

# ------------------------------ 物理常数 ------------------------------
# 比热容/气体常数一律用 J/(kg·K)（比气体常数），不要与摩尔气体常数混用。
R_UNIVERSAL = 8.314462618       # 摩尔气体常数 J/(mol·K)
MV = 18.01528                   # 水汽摩尔质量 g/mol
MD = 28.9647                    # 干空气摩尔质量 g/mol
RD = 1000 * R_UNIVERSAL / MD    # 干空气比气体常数 ≈ 287.05 J/(kg·K)
RV = 1000 * R_UNIVERSAL / MV    # 水汽比气体常数   ≈ 461.52 J/(kg·K)
EPSILON = MV / MD               # 分子量比 Mv/Md ≈ 0.62197
CP_DRY0, CP_DRY_SLOPE = 1004.7463, 0.05   # 干空气定压比热 Cp(T)=1004.7463+0.05·T  J/(kg·K)
CP_VAPOR = 1864.0               # 水汽定压比热 J/(kg·K)（ASHRAE 记作 1.86 kJ/(kg·K)）
CP_LIQUID = 4186.0              # **液态水**定压比热 J/(kg·K)。
                                # 它不是水汽比热：焓值的潜热项必须用它（v1.3.2 修）

# ------------------------- 湿度计（湿球）方程系数 -------------------------
# 方程：e = e_s(T_w) − A·P·(T − T_w)，其中 A = A0·(1 + A_T_COEF·T_w)。
#
# A0 取自 **FAO《Frost Protection》Vol. 1 附录 3**（该附录注明转引
# Fritschen & Gay, 1979, *Environmental Instrumentation*）：
#     水面（式 A3.15）： A = 0.000660·(1 + 0.00115·T_w)
#     冰面/霜球（式 A3.16）：A = 0.000582·(1 + 0.00115·T_f)
# 同一份附录把水面与冰面**两个** A 都给了出来，因此"0 ℃ 以下该用哪个"
# 不需要另找依据，按公式族本身的相态取即可。
#
# v1.3.2 更正：水面此前用的是 0.000667。仓库 Bug 档案 B-02 记载
# "牛顿求导项系数 0.00066 与 γ 的 0.000667 不一致"，当时的处置是
# 把两边统一到 0.000667 —— 即统一到了错的那一个；FAO 原文是 0.000660。
# 两值相差 1.06%，对湿球温度的影响约 0.02~0.03 K。
A0_WATER = 0.000660
A0_ICE = 0.000582
A_T_COEF = 0.00115

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


def check_relative_humidity(rh_pct):
    """相对湿度校验：**百分数**（60 表示 60%），有限且落在 (0, 100]。

    参数名带 _pct 后缀是刻意的 —— 本模块另一处相对湿度（derive_moist_air 的 rh_frac）
    用的是小数，同名不同量纲曾经埋过雷（B-24）。
    """
    v = _finite(rh_pct, '相对湿度')
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
    """Gili 型经验式（中文暖通/冷却塔文献，非气象学）。
    e_sat = 1013.25 · 10^[−3.142305(1000/Tk − 1000/373.15)
                          + 8.2·lg(373.15/Tk) − 0.0024804(373.15 − Tk)]

    该式的构造前提是：参考温度 T_ref = 373.15 K 处 e_sat 按定义 = 1 atm
    = 101.325 kPa = 1013.25 hPa。所以指数里**不能**有常数项 —— 在 T_ref 处
    所有修正项都为 0，结果必须正好回到 1013.25。

    v1.3.2 更正两处（v1.3.1 只改了前因子，把真正的错因留下了）：
      1. 指数里多出的 `+0.00141966` 删除。它在任何文献里都查不到出处，
         效果是把结果整体放大 10^0.00141966 = 1.00327 倍，并且让该式在
         自己的参考点 373.15 K 上给出 1016.57 hPa 而不是 1013.25 —— 自相矛盾。
         追根：legacy/sample.py 写的是 `980.66·10^(0.00141966 + …)`，而
         980.665 hPa（= 1 工程大气压 1 at）配的常数应是 lg(1013.25/980.665)
         = 0.0141966。0.00141966 正是 0.0141966 的 1/10 —— 一次小数点错位。
         v1.3.1 把前因子 980.66 改成 1013.25（方向对，去掉 −3.0%），
         却没去掉那个常数项，于是从"偏低 3.0%"变成"偏高 ~0.17%"。
      2. 参考温度按本项目唯一找到的文献写法取 373.15 K（此前写 373.16 K）。
         见 docs/精度与参考文献.md 第六节第 1 条：文献形式为
         `lg P = 2.0057173 − 3.142305(10³/(t+273.15) − 10³/373.15) + …`，
         其中 2.0057173 = lg 101.325（P 单位 kPa），与 1013.25 hPa 前因子等价。

    改后全区间偏差 −0.13%~−0.07%（对照 IAPWS-95）。"""
    Tk = T + 273.15
    return 1013.25 * 10 ** (-3.142305 * (1e3 / Tk - 1e3 / 373.15) +
                            8.2 * math.log10(373.15 / Tk) - 0.0024804 * (373.15 - Tk))

def _dedt_gili(T, coeff):
    """Gili 型解析导数（常数项被删掉后导数形式不变：常数求导为 0）。"""
    Tk = T + 273.15
    e = _esat_gili(T, coeff)
    return e * math.log(10) * (3142.305 / Tk ** 2 - 3.561215 / Tk + 0.0024804)

def _esat_buck96(T, coeff):
    """Buck (1996) **三参数**水面式：e_sat = A·exp[(B − T/C)·T/(D + T)]

    三参数与两参数（magnus 族）差在一个 `−T/C` 修正项上：丢掉它会在高温端
    造成 25 ℃ +0.9%、50 ℃ +3.5%、100 ℃ +12.6% 的系统性偏高。
    v1.3.2 起 `Arden-水面` 用本族按原式实现，不再挤进 magnus 族。
    参考：Buck, A. L., *Buck Research CR-1A User's Manual*, Appendix 1（1996）。"""
    A, B, C, D = coeff
    return A * math.exp((B - T / C) * T / (D + T))

def _dedt_buck96(T, coeff):
    """d/dT[(B − T/C)·T/(D+T)] = [(B − 2T/C)(D+T) − (BT − T²/C)] / (D+T)²"""
    A, B, C, D = coeff
    num = (B - 2 * T / C) * (D + T) - (B * T - T * T / C)
    return _esat_buck96(T, coeff) * num / (D + T) ** 2


def _esat_marti(T, coeff):
    """Marti 型经验式（冰面）。"""
    Tk = T + 273.15
    return 10 ** (-2663.5 / Tk + 12.537) / 100

def _dedt_marti(T, coeff):
    Tk = T + 273.15
    return _esat_marti(T, coeff) * math.log(10) * 2663.5 / Tk ** 2

# 公式族注册表：family -> 能力函数（esat/dedt 必填，invert 可选）
_FAMILY_TABLE = {
    'magnus':  dict(esat=_esat_magnus,  dedt=_dedt_magnus,  invert=_invert_magnus),
    'goff':    dict(esat=_esat_goff,    dedt=_dedt_goff),
    'wexler':  dict(esat=_esat_wexler,  dedt=_dedt_wexler),
    'gili':    dict(esat=_esat_gili,    dedt=_dedt_gili),
    'marti':   dict(esat=_esat_marti,   dedt=_dedt_marti),
    'buck96':  dict(esat=_esat_buck96,  dedt=_dedt_buck96),
}

# ---------------------------- 公式注册表 ----------------------------
# 每行 dict: {name, family, coeff, tmin, tmax, a0}
#   a0 = 湿度计方程的 A 系数基准值（1/K），随相态取 FAO 附录 3 的水面/冰面值。

FORMULAS = []
_FORMULA_INDEX = {}

def register_formula(name, family, coeff, tmin, tmax, a0=A0_WATER):
    """登记一个公式。name 全程序唯一；family 必须是 _FAMILY_TABLE 的键。

    a0 是该公式对应的湿度计方程 A 系数基准值（水面 A0_WATER / 冰面 A0_ICE）。
    它是**公式的元数据而不是全局常量**：干湿表的湿球是"湿球"还是"冰球"，
    决定了 A 取哪一个（FAO 附录 3 式 A3.15 / A3.16）。
    """
    if family not in _FAMILY_TABLE:
        raise ValueError(f"未知公式族: {family}，可选 {list(_FAMILY_TABLE)}")
    if name in _FORMULA_INDEX:
        raise ValueError(f"公式已存在: {name}")
    entry = dict(name=name, family=family, coeff=tuple(coeff),
                 tmin=tmin, tmax=tmax, a0=a0)
    FORMULAS.append(entry)
    _FORMULA_INDEX[name] = entry
    return entry

def get_formula(name):
    """按名字查公式（O(1)）。"""
    return _FORMULA_INDEX[name]

def iter_formulas():
    """遍历全部公式（按注册顺序）。"""
    return iter(FORMULAS)

def psychrometer_A(T_w, a0):
    """湿度计方程系数 A = a0·(1 + 0.00115·T_w)，1/K。"""
    return a0 * (1 + A_T_COEF * T_w)

# 14 个公式（顺序 = 原 methods 顺序）。
# 注册域（tmin/tmax）一律**不超过来源文献自己声明的有效域** —— 引擎按它判"不适用"，
# 写宽了就等于替用户宣布"这个公式在这里也能用"。v1.3.2 收紧了 4 处（见各行注释）。
register_formula('Goff-水面',    'goff',   (273.15, 10.79574, -5.02808, 1.50475e-4, -8.2969, 0.42873e-3, 4.76955, 0.78614, 0), -10, 100)
register_formula('Wexler-水面',  'wexler', (-5800.2206, 1.3914993, -0.048640239, 0.41764768e-4, -0.14452093e-7, 0, 6.5459673), -10, 200)
# Buck-水面：原注册 0~80 ℃。Buck (1981) 水面式声明 −20~+50 ℃，
# 实测 60 ℃ +0.37%、70 ℃ +0.70%、80 ℃ +1.11%（对照 IAPWS-95）→ 上界收到 50。
register_formula('Buck-水面',    'magnus', (6.1121, 17.502, 240.97), 0, 50)
register_formula('Tetens-水面',  'magnus', (6.1078, 17.269, 237.3), 0, 50)
register_formula('Magnus-水面',  'magnus', (6.112, 17.62, 243.12), 0, 60)
register_formula('August-水面',  'magnus', (6.1094, 17.625, 243.04), 0, 60)
# Arden-水面：系数 (6.1121, 18.678, 234.5, 257.14) 是 Buck (1996) 的**三参数**式。
# 旧版把它塞进 magnus 两参数族，丢掉 −T/234.5 修正项 → 25 ℃ +0.91%、50 ℃ +3.51%、
# 100 ℃ +12.56%（对照 IAPWS-95）。v1.3.2 新增 buck96 三参数族按原式实现，
# 注册域随之收到 Buck 声明的 0~50 ℃（旧注册域 0~100 与实际能力不符）。
register_formula('Arden-水面',   'buck96', (6.1121, 18.678, 234.5, 257.14), 0, 50)
register_formula('Gili-水面',    'gili',   (), -10, 20)
# Goff2-水面 = Goff-Gratch(1946) 水面式，参考温度 A=373.15 K、lg(1013.246)。
# 旧版第 4 个系数写成 1.3816e-5（标准值为 1.3816e-7，差 100 倍），
# 使该项在低温段严重超重：0 ℃ -3.5%、10 ℃ -1.7%、20 ℃ -0.9%，50 ℃ 才收敛。
register_formula('Goff2-水面',   'goff',   (373.15, 7.90298, -5.02808, 1.3816e-7, -11.344, 0.0081328, 3.49149, 3.0057149, 0), -10, 100)
# 冰面公式的注册上界一律为 0 ℃ —— 常压下 0 ℃ 以上不存在冰面，
# 冰面式在 +T 上给的是"霜点"，不是可用的露点。旧版 Goff-冰面/Wexler-冰面
# 注册到 +10 ℃，会让界面在 5 ℃ 这类温度下照常给出"冰面露点"。
register_formula('Goff-冰面',    'goff',   (273.15, 9.09718, 3.56654, 0, 0, 0, 0, 0.78614, 0.876793), -100, 0, A0_ICE)
# Hyland & Wexler (1983) 冰面式声明有效域 173.15~273.15 K（−100~0 ℃）。
# 旧注册下界 −150 ℃ 处偏 +0.47%（对照 IAPWS-2011），已收到 −100。
register_formula('Wexler-冰面',  'wexler', (-5674.5359, 6.3925247, -0.009677843, 0.62215701e-6, 0.20747825e-8, -0.9484024e-12, 4.1635019), -100, 0, A0_ICE)
register_formula('Magnus-冰面',  'magnus', (6.112, 22.46, 272.62), -65, 0, A0_ICE)
register_formula('Buck-冰面',    'magnus', (6.1115, 22.452, 272.55), -80, 0, A0_ICE)
# Marti & Mauersberger (1993) 的拟合区间是 170~273 K（−103~0 ℃）。
# 旧注册下界 −150 ℃ 处偏 −9.93%（对照 IAPWS-2011，外推已失效），已收到 −103。
register_formula('Marti-冰面',   'marti',  (), -103, 0, A0_ICE)

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

def _polish_root(T_w, f_and_df, lo, hi, steps=10):
    """在括号已经收窄到 ≤2·tol 之后，把结果推到机器精度。

    为什么需要这一步：二分保证的是"括号宽度 ≤ 2·tol"，于是括号中点的误差上界
    就是 tol（默认 1e-6 ℃）——这个上界与初值有关，会以 1e-7 量级的形式漏进结果。
    而 f 单调、牛顿在根附近二次收敛，几步就能到 10⁻¹³ K。

    安全性：每一步都要求 |f| **严格下降**，否则立刻停手并返回当前最好点；
    另外单步幅度 capped 在 max(括号宽度, 1)。所以最坏情况是"没帮上忙"，
    绝不会把已经很好的点改坏。返回值的 |f| 因此单调不劣于输入点的 |f|。
    """
    def abs_f(t):
        try:
            return abs(f_and_df(t)[0])
        except (OverflowError, ZeroDivisionError, ValueError):
            return None

    best_t, best_f = T_w, abs_f(T_w)
    if best_f is None:
        return T_w
    cap = max(hi - lo, 1.0)
    for _ in range(steps):
        f, df_dT = f_and_df(best_t)
        if f == 0.0 or df_dT <= 0:
            break
        step = f / df_dT
        if abs(step) > cap:
            step = math.copysign(cap, step)
        t_new = best_t - step
        f_new = abs_f(t_new)
        if f_new is None or f_new >= best_f:
            break
        best_t, best_f = t_new, f_new
    return best_t


def _solve_wetbulb(T_dry, e, P, guess, formula, max_iter, tol, on_iter=None):
    """解湿球方程 e_sat(Tw) − A·P·(T_dry−Tw) = e，A = a0(1+0.00115·Tw)。

    返回 (T_w, 状态)；状态 ∈ {ok, 残差过大, 未收敛, 数值溢出, 错误:…}。
    a0 取自 formula['a0']（水面 0.000660 / 冰面 0.000582，FAO 附录 3）。

    【v1.3.2 起改用「带括号的牛顿法」】
    旧版是裸牛顿：从用户填的初值出发，发散就去报「未收敛」。后果不是"精度差一点"，
    而是**结果的条数取决于初值**——实测 T=45 ℃/RH=60% 时，
    初值取 0~40 给出 8 条结果、取 100 只给 4 条、取 199 一条都不给。
    v1.3.1 只把「适用域判定」从初值上摘了下来，**求解器这一半还挂在初值上**，
    于是界面上下拉框选 "Tw=Td" 还是 "Tw=T-n" 会改变你看到几行。

    修法：注意到 f(Tw) 在该区间上**严格单调递增**——e_sat 随 Tw 增大而增大，
    `−A·P·(T_dry−Tw)` 也随 Tw 增大而增大，而
    d/dTw[−a0(1+A_T_COEF·Tw)·P·(T−Tw)] = a0·P·[1 + A_T_COEF(2Tw − T)] 在本工具
    的温度域内恒正（要它为负需要 Tw < −400 ℃）。单调就意味着**根唯一**，
    用二分法一定能夹住它。

    所以这里把牛顿步套进一个不断收紧的括号 [lo, hi]：
      · lo/hi 初值取 [T_dry − 150, T_dry]，两端异号（f(lo) < 0 ≤ f(hi)）；
      · 每步先用 f 的符号收紧括号，再试牛顿步；
      · 牛顿步走出括号（或导数非正）就退回二分。
    收敛判据是**括号宽度 ≤ 2·tol**，因此返回值的误差有上界 tol，
    与斜率无关，也与初值无关。初值只影响迭代路径（也就是那张收敛图），
    不再影响结果本身。括号足够窄之后再补几步牛顿（_polish_root），
    把结果推到机器精度——这一步只是"更准"，不会更差。
    """
    name = formula['name']
    fam = _FAMILY_TABLE[formula['family']]
    esat, dedt = fam['esat'], fam['dedt']
    a0 = formula['a0']
    k2 = a0 * A_T_COEF * P          # dγ/dTw 的常数部分，提出循环

    def f_and_df(T_w):
        e_sat = esat(T_w, formula['coeff'])
        gamma = a0 * (1 + A_T_COEF * T_w) * P
        f = e_sat - gamma * (T_dry - T_w) - e
        df_dT = dedt(T_w, formula['coeff']) + gamma - k2 * (T_dry - T_w)
        return f, df_dT

    hi = T_dry
    lo = max(T_MIN, T_dry - 150.0)
    try:
        f_hi = f_and_df(hi)[0]
        f_lo = f_and_df(lo)[0]
    except OverflowError:
        return guess, '数值溢出'
    except Exception as ex:
        return guess, f'错误: {ex}'
    if f_hi < 0 or f_lo > 0:
        # 两端同号：方程在这个区间里无解。f(hi) < 0 对应 e 比干球饱和水汽压还大
        # （Td > T 的超饱和输入）；f(lo) > 0 对应 150 ℃ 的跨度都不够。
        return guess, '残差过大'

    T_w = min(max(guess, lo), hi)   # 初值也夹进括号，发散初值不再影响结果
    best_t, best_f = T_w, None      # 迭代过程中 |f| 最小的点（牛顿通常 3~5 步就到位）
    try:
        for it in range(max_iter):
            f, df_dT = f_and_df(T_w)
            if on_iter:
                on_iter(name, it + 1, T_w, abs(f))
            if best_f is None or abs(f) < best_f:
                best_t, best_f = T_w, abs(f)
            if f > 0:
                hi = T_w
            else:
                lo = T_w
            if (hi - lo) <= 2 * tol:
                # 括号中点保证误差 ≤ tol；迭代最好点通常已经到机器精度。
                # 取两者里 |f| 更小的那个再抛光，结果对任何初值都落在同一点上。
                mid = (lo + hi) / 2
                pick = best_t if best_f <= abs(f_and_df(mid)[0]) else mid
                return _polish_root(pick, f_and_df, lo, hi), 'ok'
            if df_dT > 0:
                T_new = T_w - f / df_dT
            else:
                T_new = None
            if T_new is None or not (lo < T_new < hi):
                T_new = (lo + hi) / 2
            T_w = T_new
        return _polish_root(best_t, f_and_df, lo, hi), '未收敛'
    except OverflowError:
        return guess, '数值溢出'
    except Exception as ex:
        return guess, f'错误: {ex}'

def _infeasible(e, P):
    """水汽分压不能达到总压（道尔顿分压定律）：达到了就不是湿空气而是纯水汽。

    返回给用户看的短消息，或者 None 表示没问题。
    现实里会撞上它的组合：高温 + 常压（150 ℃ 时 e_sat ≈ 4760 hPa > 1013 hPa，
    此时 RH=50% 要求 e = 2380 hPa > P —— 水早就沸腾了，不存在这种混合气）。
    """
    if e >= P:
        return '状态不成立'
    return None


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
        bad = _infeasible(e, P)
        if bad:
            _add(results, on_result, name, bad)
            continue
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
    """模式1：已知干球 T_g、湿球 T_w，求露点温度。

    每条公式用**它自己相态**的 A 系数（水面族 0.000660 / 冰面族 0.000582，
    FAO 附录 3 式 A3.15 / A3.16）—— 干湿表的湿球是"湿球"还是"冰球"
    本来就由所选的公式族决定。"""
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
        e = es_wet - psychrometer_A(T_w, f['a0']) * P * (T_g - T_w)
        rh = e / es_dry
        bad = _infeasible(e, P)
        if bad:
            _add(results, on_result, name, bad)
        elif e >= es_dry or rh >= 1:
            _add(results, on_result, name, T_g, rh=1)
        else:
            try:
                Td = esat_calculate(e, name, max_iter, tol)
                _add(results, on_result, name, Td, rh=rh)
            except InputError as ex:
                _add(results, on_result, name, str(ex))
            except Exception:
                _add(results, on_result, name, '计算失败')
    return results

def calculate_both(initial_guess, T_g, rh_pct, P=1013.25, max_iter=50, tol=1e-6,
                   on_result=None, on_iter=None):
    """模式2：已知干球 T_g、相对湿度 rh_pct(**百分数**，60 = 60%)，同时求露点与湿球。

    单位契约（B-24）：本函数的相对湿度参数是**百分数**，与 derive_moist_air 的
    rh_frac（**小数**）刻意不同名 —— 此前两处同名 rh 而量纲不同，
    `calculate_both(..., rh=60)` 与 `derive_moist_air(..., rh=0.6)` 并存会直接埋雷。
    """
    check_temperature(T_g, '干球温度')
    check_relative_humidity(rh_pct)
    check_pressure(P)
    results = []
    rh_frac = rh_pct / 100
    for f in FORMULAS:
        name = f['name']
        if not (f['tmin'] <= T_g <= f['tmax']):
            _add(results, on_result, name, '不适用')
            continue
        try:
            e = calculate_esat(T_g, name) * rh_frac
            bad = _infeasible(e, P)
            if bad:
                _add(results, on_result, name, bad)
                continue
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
def derive_moist_air(T_g, T_w, Td, rh_frac, P=1013.25, method='Goff-水面'):
    """由干球 T_g(℃)、湿球 T_w(℃)、露点 Td(℃)、相对湿度 rh_frac(**小数**，0.6 = 60%)、
    压强 P(hPa) 推导"常用气象参数"面板的全部派生量，返回 dict。

    单位契约（B-24）：本函数的相对湿度参数是**小数**，与 calculate_both 的
    rh_pct（**百分数**）刻意不同名 —— 此前两处同名 rh 而量纲不同，
    调用方按错的那个传值就会得到 InputError 或错结果。

    T_w 仅用于取湿球饱和水汽压 esw；Td 决定实际水汽压 e；rh_frac 只用于
    判断"干空气"这一退化情形（rh_frac<=0 时 LCL 无定义，返回 nan）。
    比热容与气体常数一律用 J/(kg·K)（比气体常数），不得与摩尔气体常数混用。

    返回字段（单位见括注）：
      e/es/esw(hPa)  P_dry(hPa)  x(-)  gamma_mix(-)  v_sound(m/s)
      ro_dry/ro_vapor/ro(kg/m³)  dm1(g/kg)  L_v(kJ/kg)  han(kJ/kg)
      sat_mixing_ratio(g/kg)  absolute_humidity(g/m³)  specific_humidity(g/kg)
      q(kg/kg)  virtual_temp_K/theta_K/theta_e_K/theta_v_K(K)
      t_lcl_C(℃)  p_lcl_hPa(hPa)   —— rh_frac<=0 或 LCL 不可解时为 nan
    """
    check_temperature(T_g, '干球温度')
    check_temperature(T_w, '湿球温度')
    check_temperature(Td, '露点温度')
    check_pressure(P)
    rh = _finite(rh_frac, '相对湿度')
    if not (0.0 <= rh <= 1.0):
        raise InputError(
            f"相对湿度（小数，0.6 表示 60%）需在 [0, 1] 范围内（收到 {rh:g}）。"
            f"若手上是百分数，请改用 calculate_both(..., rh_pct={rh:g}) 那条入口。")

    T_g_K = T_g + 273.15
    Cp = CP_DRY0 + CP_DRY_SLOPE * T_g   # 干空气定压比热 (J/(kg·K))
    Cpw = CP_VAPOR                      # 水汽定压比热   (J/(kg·K))
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
    # 水汽分压不可能达到或超过总压 —— 达到了就不是"湿空气"而是纯水汽。
    # 低气压 + 高露点（例如 P=500 hPa、Td=90 ℃）能构造出 e>P，旧版会一路算出
    # 负的干空气分压与负密度而不报错。这里明确拒绝。
    if e >= P:
        raise InputError(
            f"水汽压 e = {e:.4g} hPa 不小于大气压 P = {P:.4g} hPa："
            f"该（露点 {Td:g} ℃，压强 {P:g} hPa）组合物理上不成立。")
    P_dry = P - e
    x = e / P                                            # 水汽摩尔分数
    # 比湿 q（水汽的**质量分数**）。比热是"单位质量"的量，混合时必须用质量分数；
    # 旧版用摩尔分数 x 去配质量比热，属量纲口径混用（γ 偏小 0.06%，声速偏小 0.10 m/s）。
    q_spec = ups * e / (P - (1 - ups) * e)               # kg/kg
    gamma_mix = ((1 - q_spec) * Cp + q_spec * Cpw) / ((1 - q_spec) * Cv + q_spec * Cvw)
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
    # 湿空气焓（相对 0 ℃ 干空气 + 0 ℃ 液态水），kJ/kg 干空气：
    #     h = c_pa·T + w·h_v(T)，  h_v(T) = h_v(0) + c_pv·T = L_v(0) + c_pv·T
    # 而 L_v(T) = h_v(T) − h_l(T)，所以 h_v(T) − h_l(0) = L_v(T) + c_w·T。
    # 这里需要的是**液态水**比热 c_w = 4.186 kJ/(kg·K)，不是水汽比热 1.864。
    # 旧版写成 Cpw（水汽比热），等于把水汽焓的温度斜率少算了 (c_pv − c_w)，
    # 25 ℃ / RH≈54% 时焓值偏低 0.64 kJ/kg（−1.23%）。
    han = Cp / 1000 * T_g + (L_v + CP_LIQUID / 1000 * T_g) * dm

    # 饱和混合率用饱和水汽压 es（旧版误用实际水汽压 e，得到的是"混合率"而不是"饱和混合率"）
    sat_mixing_ratio = ups * (es / (P - es)) * 1000 if P > es else 0
    absolute_humidity = (e * 100) / (RV * T_g_K) * 1e3
    specific_humidity = q_spec * 1000

    q = q_spec
    virtual_temp_K = T_g_K * (1 + upsilon * q)
    theta_K = T_g_K * (1000 / P) ** (RD / Cp)
    # L_v 上面以 kJ/kg 计，指数里必须换算成 J/kg（旧版直接用 kJ/kg，
    # 相当于潜热被缩小 1000 倍，相当位温退化成位温）。
    # 注：这里用的是"简化相当位温"θ·exp(L_v·q/(c_p·T))。它与 Bolton (1980) 式 (38)
    # 的严格解相差约 −1.2%（25 ℃/RH 54% 时 −4.0 K）；两者是**不同的定义**，
    # 不是同一个量的对错。详见 docs/精度与参考文献.md 第五节。
    theta_e_K = theta_K * math.exp(L_v * 1000 * q / (Cp * T_g_K))
    theta_v_K = theta_K * (1 + upsilon * q)

    # 抬升凝结高度：Bolton, D. (1980), Mon. Wea. Rev. 108, 式 (21)
    #     T_LCL = 1 / (1/(T_d − 56) + ln(T/T_d)/800) + 56      （T、T_d 用**开尔文**）
    # 旧版用的是"T_d − 56 代入摄氏度、并用 ln(RH) 代替 ln(T/T_d)"的变体，
    # 与 Bolton 原式相差最多 +2.6 K（25 ℃/Td=15 ℃ 时 +0.93 K），
    # 也与常用经验规则 h ≈ 125(T−T_d) 米对不上。已按原式实现。
    try:
        if rh <= 0:
            raise ValueError('rh=0 时露点无定义，LCL 不可解')
        Td_K = Td + 273.15
        t_lcl_K = 1.0 / (1.0 / (Td_K - 56.0) + math.log(T_g_K / Td_K) / 800.0) + 56.0
        t_lcl_C = t_lcl_K - 273.15
        p_lcl_hPa = P * (t_lcl_K / T_g_K) ** (Cp / RD)
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
    # 自我回归（不是正确性验证）：四个数取自 v1.3.2 的实况，只用来发现
    # "谁把 core 改动了却没意识到"。它构造上发现不了继承来的系统偏差，
    # 真正的正确性验证在 tests/ 里（对照 IAPWS-95 / ASHRAE / Stull 外部参照）：
    #     python -m pytest -q
    #
    # 这四个数字在 v1.3.2 全部变过（v1.3.1 的值在括号里）：
    #   湿球：A 系数 0.000667 → FAO 附录 3 的 0.000660
    #   露点：同上（模式 1 直接用湿度计方程算 e）
    #   模式 2 的露点只走 e_sat 反算，与 A 无关，故未变
    w = {r['method']: r for r in calculate_wetbulb(15, 25, 15)}
    assert abs(w['Goff-水面']['result1'] - 18.5958) < 1e-3, w['Goff-水面']['result1']  # v1.3.1: 18.6186
    d = {r['method']: r for r in calculate_dewpoint(25, 20, 1013.25)}
    assert abs(d['Goff-水面']['result1'] - 17.4718) < 1e-3, d['Goff-水面']['result1']  # v1.3.1: 17.4430
    b = {r['method']: r for r in calculate_both(25, 25, 60)}
    assert abs(b['Goff-水面']['result1'] - 16.7003) < 1e-3, b['Goff-水面']['result1']
    assert abs(b['Goff-水面']['result2'] - 19.5488) < 1e-3, b['Goff-水面']['result2']  # v1.3.1: 19.5676
    print(f"[core 自回归 OK] tag={tag}, 公式数={len(FORMULAS)}")
    print("  正确性验证请运行: python -m pytest -q")
