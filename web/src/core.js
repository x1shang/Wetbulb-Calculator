/* =====================================================================
 * core.js — 湿球计算器计算核心（src/core.py 的逐行移植版）
 * =====================================================================
 * 【本文件的定位】
 *   这是 src/core.py **v1.3.4 的 1:1 移植**，不是"另写一遍"。移植规则只有三条，
 *   违反任何一条都会让网页版与 exe 算出不同的数：
 *
 *     1. 函数名、参数名、参数顺序、默认值与 src/core.py 完全一致；
 *     2. **运算顺序与括号不改**（浮点加减不满足结合律，`a+b+c` 与 `a+(b+c)`
 *        在最后一位上可以不同）；
 *     3. Python 与 JS 的**语义差**必须显式补齐（见下）。
 *
 * 【必须显式补齐的语义差（这些都是"静默算错"的坑，不是风格问题）】
 *   · 溢出：Python `math.exp` / `10 ** x` 溢出会抛 OverflowError，调用方据此
 *     返回「数值溢出」；JS Math.exp / Math.pow 只返回 Infinity，**不抛**。
 *     所以每个 _esat_* 出口都要过 _finiteOrOverflow()，否则界面会拿 Infinity
 *     当结果往下算。
 *   · 开方/对数：Python math.log(负数) 抛 ValueError，JS 返回 NaN。本模块用到的
 *     调用点（log(e/A)、log10(Tk/A)、log(Tk)）在合法输入下恒正，不做额外包装，
 *     但 _polish_root 仍按 Python 一样把非有限值当成"这一步没帮上忙"。
 *   · 格式化：Python 的 f"{x:.4f}" 是**对二进制精确值做四舍六入五成双**，
 *     而 JS toFixed 在十进制中点上是"远离零"，且 -0.0 会丢符号。这里用 BigInt
 *     精确十进制展开实现 pyFixed()，逐位与 Python 相同（含 -0.0000）。
 *   · repr / %g：错误消息里出现 {value!r}、{x:g}，用 pyG() / pyRepr() 复刻。
 *
 * 【与 core.py 的对应关系（便于将来同步）】
 *   core.py 段落                     本文件段落
 *   ------------------------------   ------------------------------
 *   配置 / tag / tot                  §1 配置
 *   物理常数 / 湿度计系数             §2 物理常数
 *   输入校验                          §3 输入校验
 *   公式族计算函数                    §4 公式族
 *   公式注册表 + 14 条公式            §5 注册表
 *   公共计算 API                      §6 公共 API
 *   扩展气象参数                      §7 派生量
 *
 * 【同步约定】core.py 改数值时必须同步本文件，并重跑：
 *   python -m pytest tests/test_web_parity.py -q
 * 该测试会用真 core.py 现算的期望值逐点比对这里的输出，并检查页内自检向量是否过期。
 * ===================================================================== */

(function (root) {
  'use strict';

  /* ==================== §0 Python 语义辅助（格式化 / repr） ==================== */

  /** 把 double 精确拆成 mantissa × 2^exp（用于精确十进制格式化）。 */
  function _decompose(x) {
    const buf = new ArrayBuffer(8);
    const dv = new DataView(buf);
    dv.setFloat64(0, x, false);
    const hi = dv.getUint32(0, false);
    const lo = dv.getUint32(4, false);
    const sign = (hi >>> 31) === 1;
    const expBits = (hi >>> 20) & 0x7ff;
    let mant = (BigInt(hi & 0xfffff) << 32n) | BigInt(lo);
    let e;
    if (expBits === 0) {
      e = -1074;                       // 次正规数
    } else {
      mant |= (1n << 52n);
      e = expBits - 1075;
    }
    return { sign: sign, mant: mant, e: e };
  }

  /**
   * Python `f"{x:.n f}"` 的等价实现：
   *   · 对**精确二进制值**做十进制舍入（不是先转字符串再修）；
   *   · 中点按"四舍六入五成双"（Python 与 IEEE 的默认）；
   *   · 保留 -0.0 的负号（Python 打印 "-0.0000"）；
   *   · inf/nan 按 Python 输出 'inf' / 'nan'（不带 4 位小数）。
   */
  function pyFixed(x, n) {
    if (typeof x !== 'number') x = Number(x);
    if (Number.isNaN(x)) return 'nan';
    if (x === Infinity) return 'inf';
    if (x === -Infinity) return '-inf';
    const d = _decompose(x);
    let num = d.mant;
    let den = 1n;
    if (d.e >= 0) num = d.mant << BigInt(d.e);
    else den = 1n << BigInt(-d.e);
    num *= 10n ** BigInt(n);
    let q = num / den;
    const r = num % den;
    const twice = r * 2n;
    if (twice > den) q += 1n;
    else if (twice === den && q % 2n === 1n) q += 1n;   // 中点 → 取偶
    let s = q.toString();
    if (n > 0) {
      while (s.length <= n) s = '0' + s;
      s = s.slice(0, s.length - n) + '.' + s.slice(s.length - n);
    }
    if (d.sign) s = '-' + s;                            // -0.0 也要带负号
    return s;
  }

  /** Python `f"{x:g}"`（默认 6 位有效数字）的等价实现。 */
  function pyG(x, prec) {
    if (prec === undefined) prec = 6;
    if (typeof x !== 'number') x = Number(x);
    if (Number.isNaN(x)) return 'nan';
    if (x === Infinity) return 'inf';
    if (x === -Infinity) return '-inf';
    const neg = (x < 0) || Object.is(x, -0);
    const ax = Math.abs(x);
    if (ax === 0) return neg ? '-0' : '0';
    // 用 toExponential 拿到"舍入到 prec 位有效数字之后"的指数，
    // 与 CPython 的 %g 用它决定定点/科学计数法的口径一致。
    const sci = ax.toExponential(prec - 1);
    const parts = sci.split('e');
    const digits = parts[0].replace('.', '');
    let X = parseInt(parts[1], 10);
    let out;
    if (X < -4 || X >= prec) {
      let mant = digits.replace(/0+$/, '');
      if (mant.length === 0) mant = '0';
      if (mant.length > 1) mant = mant[0] + '.' + mant.slice(1);
      const sign = X < 0 ? '-' : '+';
      const absX = Math.abs(X).toString().padStart(2, '0');
      out = mant + 'e' + sign + absX;
    } else {
      let s = digits;
      if (X >= 0) {
        while (s.length <= X) s += '0';
        s = s.slice(0, X + 1) + (X + 1 < s.length ? '.' + s.slice(X + 1) : '');
      } else {
        s = '0.' + '0'.repeat(-X - 1) + s;
      }
      if (s.indexOf('.') >= 0) s = s.replace(/0+$/, '').replace(/\.$/, '');
      out = s;
    }
    return neg ? '-' + out : out;
  }

  /** Python `repr()` 的近似等价（只用于错误消息里的 {value!r}）。 */
  function pyRepr(v) {
    if (v === null || v === undefined) return 'None';
    if (typeof v === 'string') return "'" + v.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'";
    if (typeof v === 'boolean') return v ? 'True' : 'False';
    if (typeof v === 'number') {
      if (Number.isNaN(v)) return 'nan';
      if (v === Infinity) return 'inf';
      if (v === -Infinity) return '-inf';
      let s = String(v);
      if (Number.isInteger(v) && Math.abs(v) < 1e16 && s.indexOf('e') < 0) s += '.0';
      s = s.replace(/e([+-])(\d)$/, 'e$10$2');          // 1e-7 → 1e-07
      return s;
    }
    if (Array.isArray(v)) return '[' + v.map(pyRepr).join(', ') + ']';
    if (typeof v === 'object') return '{' + Object.keys(v).map(k => pyRepr(k) + ': ' + pyRepr(v[k])).join(', ') + '}';
    return String(v);
  }

  /* ==================== §1 配置 ==================== */

  // 网页版自己的版本号：与 Python 的 core.tag **刻意分开**。
  // 规则：网页版 v2.x.y 对应桌面版（exe）v1.x.y —— 桌面版升到 1.3.6 时网页版升 2.0.1。
  // 这么做的原因：两边的发布节奏与内容不一致，共用一个号会让人分不清
  // "网页版落后了"还是"桌面版修了网页版没有的东西"。
  // 【发布时注意】桌面版的 git tag 仍然只有一套（v1.x.y）。网页版的 2.x.y 不单独打 tag，
  // 而是写进该次 Release 的说明里 —— 见 README「版本号怎么读」。
  const WEB_TAG = 'v2.0.0';
  const EXE_TAG = 'v1.3.5';      // 本移植对应的 src/core.py 版本（与 core.tag 一致）

  const tot = 1e-7;              // 默认迭代精度（core.py 的 tot）

  /* ==================== §2 物理常数与湿度计系数 ==================== */

  const R_UNIVERSAL = 8.314462618;   // 摩尔气体常数 J/(mol·K)
  const MV = 18.01528;               // 水汽摩尔质量 g/mol
  const MD = 28.9647;                // 干空气摩尔质量 g/mol
  const RD = 1000 * R_UNIVERSAL / MD;// 干空气比气体常数
  const RV = 1000 * R_UNIVERSAL / MV;// 水汽比气体常数
  const EPSILON = MV / MD;
  const CP_DRY0 = 1004.7463, CP_DRY_SLOPE = 0.05;
  const CP_VAPOR = 1864.0;
  const CP_LIQUID = 4186.0;          // 液态水定压比热（焓值潜热项必须用它）

  const A0_WATER = 0.000660;         // FAO 附录 3 式 A3.15
  const A0_ICE = 0.000582;           // FAO 附录 3 式 A3.16
  const A_T_COEF = 0.00115;

  const T_MIN = -150.0, T_MAX = 200.0;
  const P_MIN = 1.0, P_MAX = 1200.0;
  const RH_MAX = 100.0;

  /* ==================== §3 输入校验 ==================== */

  /** 物理上不可能的输入（对应 core.InputError）。 */
  class InputError extends Error {
    constructor(message) {
      super(message);
      this.name = 'InputError';
    }
  }

  /** 数值溢出（对应 Python 的 OverflowError；name 刻意一致，便于 catch 分支判断）。 */
  class NumericOverflow extends Error {
    constructor(message) {
      super(message || 'math range error');
      this.name = 'OverflowError';
    }
  }

  /** 结果非有限即视为溢出 —— 这是 JS 与 Python 之间最关键的一处语义补齐。 */
  function _finiteOrOverflow(v) {
    if (typeof v !== 'number' || Number.isNaN(v) || !Number.isFinite(v)) throw new NumericOverflow();
    return v;
  }

  function _finite(value, name) {
    // 注意分支顺序：Python 的 isinstance 检查**接受** NaN（它确实是 float），
    // NaN 是在 isfinite 那一步被拒的。所以这里不能把 NaN 归到"必须是数值"里 ——
    // 两条消息不一样，界面照抄给用户看的就是这两句。
    if (typeof value !== 'number') {
      throw new InputError(name + '必须是数值（收到 ' + pyRepr(value) + '）');
    }
    if (!Number.isFinite(value)) {
      throw new InputError(name + '必须是有限数值（收到 ' + pyRepr(value) + '）');
    }
    return value;
  }

  function check_temperature(value, name) {
    if (name === undefined) name = '温度';
    const v = _finite(value, name);
    if (!(T_MIN <= v && v <= T_MAX)) {
      throw new InputError(name + '需在 [' + pyG(T_MIN) + ', ' + pyG(T_MAX) + '] ℃ 范围内（收到 ' + pyG(v) + '）');
    }
    return v;
  }

  function check_pressure(value) {
    const v = _finite(value, '大气压强');
    if (!(P_MIN <= v && v <= P_MAX)) {
      throw new InputError('大气压强需在 [' + pyG(P_MIN) + ', ' + pyG(P_MAX) + '] hPa 范围内（收到 ' + pyG(v) + '）');
    }
    return v;
  }

  function check_relative_humidity(rh_pct) {
    const v = _finite(rh_pct, '相对湿度');
    if (!(0.0 < v && v <= RH_MAX)) {
      throw new InputError('相对湿度需在 (0, ' + pyG(RH_MAX) + '] % 范围内（收到 ' + pyG(v) + '）');
    }
    return v;
  }

  /* ==================== §4 公式族计算函数 ==================== */

  function _esat_magnus(T, coeff) {
    const A = coeff[0], B = coeff[1], C = coeff[2];
    return _finiteOrOverflow(A * Math.exp(B * T / (C + T)));
  }

  function _dedt_magnus(T, coeff) {
    const A = coeff[0], B = coeff[1], C = coeff[2];
    return _finiteOrOverflow(_esat_magnus(T, coeff) * (B * C) / Math.pow(C + T, 2));
  }

  function _invert_magnus(e, coeff) {
    const A = coeff[0], B = coeff[1], C = coeff[2];
    const t1 = Math.log(e / A);
    return C * t1 / (B - t1);
  }

  function _esat_goff(T, coeff) {
    const A = coeff[0], B = coeff[1], C = coeff[2], D = coeff[3], E = coeff[4],
      F = coeff[5], G = coeff[6], H = coeff[7], I = coeff[8];
    const Tk = T + 273.15;
    return _finiteOrOverflow(Math.pow(10, B * (1 - A / Tk) + C * Math.log10(Tk / A) +
      D * (1 - Math.pow(10, E * (Tk / A - 1))) +
      F * (Math.pow(10, G * (1 - A / Tk)) - 1) +
      I * (1 - Tk / A) + H));
  }

  function _dedt_goff(T, coeff) {
    const A = coeff[0], B = coeff[1], C = coeff[2], D = coeff[3], E = coeff[4],
      F = coeff[5], G = coeff[6], I = coeff[8];
    const Tk = T + 273.15;
    const d = (B * A / Math.pow(Tk, 2) + C / (Tk * Math.log(10)) -
      D * E / A * Math.log(10) * Math.pow(10, E * (Tk / A - 1)) +
      A * F * G / Math.pow(Tk, 2) * Math.pow(10, G * (1 - A / Tk)) * Math.log(10) - I / A);
    return _finiteOrOverflow(_esat_goff(T, coeff) * Math.log(10) * d);
  }

  function _esat_wexler(T, coeff) {
    const A = coeff[0], B = coeff[1], C = coeff[2], D = coeff[3], E = coeff[4],
      F = coeff[5], G = coeff[6];
    const Tk = T + 273.15;
    const ln_e = (A / Tk + B + C * Tk + D * Math.pow(Tk, 2) + E * Math.pow(Tk, 3) +
      F * Math.pow(Tk, 4) + G * Math.log(Tk));
    return _finiteOrOverflow(Math.exp(ln_e) / 100);
  }

  function _dedt_wexler(T, coeff) {
    const A = coeff[0], C = coeff[2], D = coeff[3], E = coeff[4], F = coeff[5], G = coeff[6];
    const Tk = T + 273.15;
    return _finiteOrOverflow(_esat_wexler(T, coeff) * (-A / Math.pow(Tk, 2) + C + 2 * D * Tk +
      3 * E * Math.pow(Tk, 2) + 4 * F * Math.pow(Tk, 3) + G / Tk));
  }

  /**
   * 纪利公式（中文给排水/冷却塔工程经验式）。出处与「有意偏离原文之处」见
   * src/core.py 的同名函数 docstring —— 那里记着 2026-10 的原文核对结论：
   * 名称是「纪利」不是「吉利」；前因子 980.66 hPa 本来就对，当年抄错的是
   * 指数常数（0.0141966 被抄成 0.00141966）；参考温度取 373.15 K 是有意偏离
   * 原文 373.16 K，实测更接近 IAPWS-95。数值与本函数一字不改地对应。
   */
  function _esat_gili(T, coeff) {
    const Tk = T + 273.15;
    return _finiteOrOverflow(1013.25 * Math.pow(10, -3.142305 * (1e3 / Tk - 1e3 / 373.15) +
      8.2 * Math.log10(373.15 / Tk) - 0.0024804 * (373.15 - Tk)));
  }

  function _dedt_gili(T, coeff) {
    const Tk = T + 273.15;
    const e = _esat_gili(T, coeff);
    return _finiteOrOverflow(e * Math.log(10) * (3142.305 / Math.pow(Tk, 2) - 3.561215 / Tk + 0.0024804));
  }

  /** Buck (1996) 三参数水面式（Arden-水面 用它）。 */
  function _esat_buck96(T, coeff) {
    const A = coeff[0], B = coeff[1], C = coeff[2], D = coeff[3];
    return _finiteOrOverflow(A * Math.exp((B - T / C) * T / (D + T)));
  }

  function _dedt_buck96(T, coeff) {
    const B = coeff[1], C = coeff[2], D = coeff[3];
    const num = (B - 2 * T / C) * (D + T) - (B * T - T * T / C);
    return _finiteOrOverflow(_esat_buck96(T, coeff) * num / Math.pow(D + T, 2));
  }

  /** Marti 型经验式（冰面）。 */
  function _esat_marti(T, coeff) {
    const Tk = T + 273.15;
    return _finiteOrOverflow(Math.pow(10, -2663.5 / Tk + 12.537) / 100);
  }

  function _dedt_marti(T, coeff) {
    const Tk = T + 273.15;
    return _finiteOrOverflow(_esat_marti(T, coeff) * Math.log(10) * 2663.5 / Math.pow(Tk, 2));
  }

  // 公式族注册表（family → 能力函数）。顺序与 core.py 一致。
  const _FAMILY_TABLE = {
    'magnus': { esat: _esat_magnus, dedt: _dedt_magnus, invert: _invert_magnus },
    'goff': { esat: _esat_goff, dedt: _dedt_goff },
    'wexler': { esat: _esat_wexler, dedt: _dedt_wexler },
    'gili': { esat: _esat_gili, dedt: _dedt_gili },
    'marti': { esat: _esat_marti, dedt: _dedt_marti },
    'buck96': { esat: _esat_buck96, dedt: _dedt_buck96 },
  };

  /* ==================== §5 公式注册表 ==================== */

  const FORMULAS = [];
  const _FORMULA_INDEX = {};

  function register_formula(name, family, coeff, tmin, tmax, a0) {
    if (a0 === undefined) a0 = A0_WATER;
    if (!Object.prototype.hasOwnProperty.call(_FAMILY_TABLE, family)) {
      throw new Error('未知公式族: ' + family + '，可选 ' + pyRepr(Object.keys(_FAMILY_TABLE)));
    }
    if (Object.prototype.hasOwnProperty.call(_FORMULA_INDEX, name)) {
      throw new Error('公式已存在: ' + name);
    }
    const entry = { name: name, family: family, coeff: coeff, tmin: tmin, tmax: tmax, a0: a0 };
    FORMULAS.push(entry);
    _FORMULA_INDEX[name] = entry;
    return entry;
  }

  function get_formula(name) { return _FORMULA_INDEX[name]; }
  function iter_formulas() { return FORMULAS.slice(); }

  function psychrometer_A(T_w, a0) {
    return a0 * (1 + A_T_COEF * T_w);
  }

  // 14 条公式（顺序 = 原 methods 顺序 = core.py 注册顺序）。
  // 【注册域纪律】tmin/tmax 一律不超过来源文献自己声明的有效域；v1.3.2 收紧了 4 处，
  //   冰面公式上界一律 0 ℃（常压下 0 ℃ 以上不存在冰面，冰面式给的是"霜点"）。
  register_formula('Goff-水面', 'goff', [273.15, 10.79574, -5.02808, 1.50475e-4, -8.2969, 0.42873e-3, 4.76955, 0.78614, 0], -10, 100);
  register_formula('Wexler-水面', 'wexler', [-5800.2206, 1.3914993, -0.048640239, 0.41764768e-4, -0.14452093e-7, 0, 6.5459673], -10, 200);
  register_formula('Buck-水面', 'magnus', [6.1121, 17.502, 240.97], 0, 50);
  register_formula('Tetens-水面', 'magnus', [6.1078, 17.269, 237.3], 0, 50);
  register_formula('Magnus-水面', 'magnus', [6.112, 17.62, 243.12], 0, 60);
  register_formula('August-水面', 'magnus', [6.1094, 17.625, 243.04], 0, 60);
  register_formula('Arden-水面', 'buck96', [6.1121, 18.678, 234.5, 257.14], 0, 50);
  register_formula('Gili-水面', 'gili', [], -10, 120);
  register_formula('Goff2-水面', 'goff', [373.15, 7.90298, -5.02808, 1.3816e-7, -11.344, 0.0081328, 3.49149, 3.0057149, 0], -10, 100);
  register_formula('Goff-冰面', 'goff', [273.15, 9.09718, 3.56654, 0, 0, 0, 0, 0.78614, 0.876793], -100, 0, A0_ICE);
  register_formula('Wexler-冰面', 'wexler', [-5674.5359, 6.3925247, -0.009677843, 0.62215701e-6, 0.20747825e-8, -0.9484024e-12, 4.1635019], -100, 0, A0_ICE);
  register_formula('Magnus-冰面', 'magnus', [6.112, 22.46, 272.62], -65, 0, A0_ICE);
  register_formula('Buck-冰面', 'magnus', [6.1115, 22.452, 272.55], -80, 0, A0_ICE);
  register_formula('Marti-冰面', 'marti', [], -103, 0, A0_ICE);

  /* ==================== §6 公共计算 API ==================== */

  function calculate_esat(T, method) {
    if (method === undefined) method = 'Magnus-水面';
    const f = get_formula(method);
    return _FAMILY_TABLE[f.family].esat(T, f.coeff);
  }

  function calculate_dedt(T, method, delta) {
    if (delta === undefined) delta = 1e-3;
    const f = get_formula(method);
    const dedt = _FAMILY_TABLE[f.family].dedt;
    if (dedt) return dedt(T, f.coeff);
    return (calculate_esat(T + delta, method) - calculate_esat(T - delta, method)) / (2 * delta);
  }

  /**
   * 由蒸气压 e(hPa) 反求温度 T(℃)。
   * 区间缺省取**全域** [T_MIN, T_MAX] 而不是公式自己的声明域 —— 反算天生要略微越界
   * （Buck-水面 声明 0~50 ℃，但 0 ℃ 且 RH<100% 时露点必然为负）。见 core.py 注释。
   */
  function esat_calculate(e, method, max_iter, tol, mint, maxt) {
    if (max_iter === undefined) max_iter = 500;
    if (tol === undefined) tol = 1e-6;
    const f = get_formula(method);
    const lo = (mint === undefined || mint === null) ? T_MIN : Number(mint);
    const hi = (maxt === undefined || maxt === null) ? T_MAX : Number(maxt);
    const ev = _finite(e, '蒸气压');
    if (ev <= 0) throw new InputError('蒸气压必须大于 0（收到 ' + pyG(ev) + ' hPa）');
    const e_lo = calculate_esat(lo, method), e_hi = calculate_esat(hi, method);
    if (ev < e_lo) {
      throw new InputError(method + ' 在 ' + pyG(lo) + ' ℃ 处的饱和蒸气压为 ' + pyG(e_lo, 4) +
        ' hPa，已高于给定的蒸气压 ' + pyG(ev, 4) + ' hPa —— 所需露点低于本工具温度域下界 ' + pyG(lo) + ' ℃');
    }
    if (ev > e_hi) {
      throw new InputError(method + ' 在 ' + pyG(hi) + ' ℃ 处的饱和蒸气压为 ' + pyG(e_hi, 4) +
        ' hPa，低于给定的蒸气压 ' + pyG(ev, 4) + ' hPa —— 所需露点高于本工具温度域上界 ' + pyG(hi) + ' ℃');
    }
    const invert = _FAMILY_TABLE[f.family].invert;
    if (invert) return Math.min(Math.max(invert(ev, f.coeff), lo), hi);
    let l = lo, h = hi;
    for (let i = 0; i < max_iter; i++) {
      const t = (l + h) / 2;
      if ((h - l) <= 2 * tol) return t;
      if (calculate_esat(t, method) - ev > 0) h = t;
      else l = t;
    }
    return (l + h) / 2;
  }

  function _add(results, on_result, method, result1, result2, rh) {
    const entry = {
      method: method,
      result1: result1,
      result2: result2 === undefined ? null : result2,
      rh: rh === undefined ? null : rh,
    };
    results.push(entry);
    if (on_result) on_result(entry);
    return entry;
  }

  /**
   * 括号已收窄到 ≤2·tol 之后，把结果推到机器精度（对应 core._polish_root）。
   * 每一步都要求 |f| **严格下降**，否则立刻停手 —— 最坏情况是"没帮上忙"，
   * 绝不会把已经很好的点改坏。
   */
  function _polish_root(T_w, f_and_df, lo, hi, steps) {
    if (steps === undefined) steps = 10;
    function abs_f(t) {
      try {
        const fv = f_and_df(t)[0];
        if (!Number.isFinite(fv)) return null;
        return Math.abs(fv);
      } catch (e) {
        return null;                       // 对应 Python 的 (OverflowError, ZeroDivisionError, ValueError)
      }
    }
    let best_t = T_w, best_f = abs_f(T_w);
    if (best_f === null) return T_w;
    const cap = Math.max(hi - lo, 1.0);
    for (let i = 0; i < steps; i++) {
      const r = f_and_df(best_t);
      const f = r[0], df_dT = r[1];
      if (f === 0.0 || df_dT <= 0) break;
      let step = f / df_dT;
      if (Math.abs(step) > cap) step = Math.sign(step) * cap;
      const t_new = best_t - step;
      const f_new = abs_f(t_new);
      if (f_new === null || f_new >= best_f) break;
      best_t = t_new;
      best_f = f_new;
    }
    return best_t;
  }

  /**
   * 解湿球方程 e_sat(Tw) − A·P·(T_dry−Tw) = e，A = a0(1+0.00115·Tw)。
   * 返回 [T_w, 状态]；状态 ∈ {ok, 残差过大, 未收敛, 数值溢出, 错误:…}。
   * 带括号的牛顿法：f(Tw) 严格单调 ⇒ 根唯一 ⇒ 结果不依赖初值，只影响迭代路径。
   */
  function _solve_wetbulb(T_dry, e, P, guess, formula, max_iter, tol, on_iter) {
    if (on_iter === undefined) on_iter = null;
    const name = formula.name;
    const fam = _FAMILY_TABLE[formula.family];
    const esat = fam.esat, dedt = fam.dedt;
    const a0 = formula.a0;
    const k2 = a0 * A_T_COEF * P;

    function f_and_df(T_w) {
      const e_sat = esat(T_w, formula.coeff);
      const gamma = a0 * (1 + A_T_COEF * T_w) * P;
      const f = e_sat - gamma * (T_dry - T_w) - e;
      const df_dT = dedt(T_w, formula.coeff) + gamma - k2 * (T_dry - T_w);
      return [f, df_dT];
    }

    let hi = T_dry;
    let lo = Math.max(T_MIN, T_dry - 150.0);
    let f_hi, f_lo;
    try {
      f_hi = f_and_df(hi)[0];
      f_lo = f_and_df(lo)[0];
    } catch (ex) {
      if (ex instanceof NumericOverflow) return [guess, '数值溢出'];
      return [guess, '错误: ' + ex.message];
    }
    if (f_hi < 0 || f_lo > 0) return [guess, '残差过大'];

    let T_w = Math.min(Math.max(guess, lo), hi);
    let best_t = T_w, best_f = null;
    try {
      for (let it = 0; it < max_iter; it++) {
        const r = f_and_df(T_w);
        const f = r[0], df_dT = r[1];
        if (on_iter) on_iter(name, it + 1, T_w, Math.abs(f));
        if (best_f === null || Math.abs(f) < best_f) { best_t = T_w; best_f = Math.abs(f); }
        if (f > 0) hi = T_w; else lo = T_w;
        if ((hi - lo) <= 2 * tol) {
          const mid = (lo + hi) / 2;
          const pick = best_f <= Math.abs(f_and_df(mid)[0]) ? best_t : mid;
          return [_polish_root(pick, f_and_df, lo, hi), 'ok'];
        }
        let T_new = null;
        if (df_dT > 0) T_new = T_w - f / df_dT;
        if (T_new === null || !(lo < T_new && T_new < hi)) T_new = (lo + hi) / 2;
        T_w = T_new;
      }
      return [_polish_root(best_t, f_and_df, lo, hi), '未收敛'];
    } catch (ex) {
      if (ex instanceof NumericOverflow) return [guess, '数值溢出'];
      return [guess, '错误: ' + ex.message];
    }
  }

  /** 水汽分压不能达到总压（道尔顿分压定律）。 */
  function _infeasible(e, P) {
    if (e >= P) return '状态不成立';
    return null;
  }

  /** 模式 0：已知干球 T、露点 Td，求湿球温度（逐公式）。 */
  function calculate_wetbulb(initial_guess, T, Td, P, max_iter, tol, on_result, on_iter) {
    if (P === undefined) P = 1013.25;
    if (max_iter === undefined) max_iter = 50;
    if (tol === undefined) tol = 1e-6;
    check_temperature(T, '干球温度');
    check_temperature(Td, '露点温度');
    check_pressure(P);
    const results = [];
    for (let i = 0; i < FORMULAS.length; i++) {
      const f = FORMULAS[i];
      const name = f.name;
      if (!(f.tmin <= T && T <= f.tmax && f.tmin <= Td && Td <= f.tmax)) {
        _add(results, on_result, name, '不适用');
        continue;
      }
      const e = calculate_esat(Td, name);
      const bad = _infeasible(e, P);
      if (bad) { _add(results, on_result, name, bad); continue; }
      const out = _solve_wetbulb(T, e, P, initial_guess, f, max_iter, tol, on_iter);
      const T_w = out[0], status = out[1];
      if (status === 'ok') {
        const rh = e / calculate_esat(T, name);
        if (0 <= rh && rh <= 1) _add(results, on_result, name, T_w, null, rh);
        else _add(results, on_result, name, '结果不符常理');
      } else {
        _add(results, on_result, name, status);
      }
    }
    return results;
  }

  /** 模式 1：已知干球 T_g、湿球 T_w，求露点温度。 */
  function calculate_dewpoint(T_g, T_w, P, max_iter, tol, on_result, on_iter) {
    if (max_iter === undefined) max_iter = 500;
    if (tol === undefined) tol = 1e-6;
    check_temperature(T_g, '干球温度');
    check_temperature(T_w, '湿球温度');
    check_pressure(P);
    const results = [];
    for (let i = 0; i < FORMULAS.length; i++) {
      const f = FORMULAS[i];
      const name = f.name;
      if ((T_w < f.tmin || T_w > f.tmax) || (T_g < f.tmin || T_g > f.tmax)) {
        _add(results, on_result, name, '不适用');
        continue;
      }
      const es_wet = calculate_esat(T_w, name);
      const es_dry = calculate_esat(T_g, name);
      const e = es_wet - psychrometer_A(T_w, f.a0) * P * (T_g - T_w);
      const rh = e / es_dry;
      const bad = _infeasible(e, P);
      if (bad) {
        _add(results, on_result, name, bad);
      } else if (e >= es_dry || rh >= 1) {
        _add(results, on_result, name, T_g, null, 1);
      } else {
        try {
          const Td = esat_calculate(e, name, max_iter, tol);
          _add(results, on_result, name, Td, null, rh);
        } catch (ex) {
          if (ex instanceof InputError) _add(results, on_result, name, ex.message);
          else _add(results, on_result, name, '计算失败');
        }
      }
    }
    return results;
  }

  /** 模式 2：已知干球 T_g、相对湿度 rh_pct（**百分数**，60 = 60%），同时求露点与湿球。 */
  function calculate_both(initial_guess, T_g, rh_pct, P, max_iter, tol, on_result, on_iter) {
    if (P === undefined) P = 1013.25;
    if (max_iter === undefined) max_iter = 50;
    if (tol === undefined) tol = 1e-6;
    check_temperature(T_g, '干球温度');
    check_relative_humidity(rh_pct);
    check_pressure(P);
    const results = [];
    const rh_frac = rh_pct / 100;
    for (let i = 0; i < FORMULAS.length; i++) {
      const f = FORMULAS[i];
      const name = f.name;
      if (!(f.tmin <= T_g && T_g <= f.tmax)) {
        _add(results, on_result, name, '不适用');
        continue;
      }
      try {
        const e = calculate_esat(T_g, name) * rh_frac;
        const bad = _infeasible(e, P);
        if (bad) { _add(results, on_result, name, bad); continue; }
        const Td = esat_calculate(e, name, max_iter, tol);
        const out = _solve_wetbulb(T_g, e, P, initial_guess, f, max_iter, tol, on_iter);
        const T_w = out[0], status = out[1];
        if (status === 'ok') _add(results, on_result, name, Td, T_w);
        else if (status === '残差过大') _add(results, on_result, name, Td, '湿球残差过大');
        else if (status === '未收敛') _add(results, on_result, name, Td, '湿球未收敛');
        else if (status === '数值溢出') _add(results, on_result, name, '数值溢出');
        else _add(results, on_result, name, status);
      } catch (ex) {
        if (ex instanceof NumericOverflow) _add(results, on_result, name, '数值溢出');
        else _add(results, on_result, name, '错误: ' + ex.message);
      }
    }
    return results;
  }

  /* ==================== §7 扩展气象参数（派生量） ==================== */

  /**
   * 由 T_g / T_w / Td / rh_frac（**小数**，0.6 = 60%）/ P 推导"常用气象参数"全部派生量。
   * 相对湿度在此处是小数、在 calculate_both 是百分数 —— 这个不同名是刻意的（B-24）。
   */
  function derive_moist_air(T_g, T_w, Td, rh_frac, P, method) {
    if (P === undefined) P = 1013.25;
    if (method === undefined) method = 'Goff-水面';
    check_temperature(T_g, '干球温度');
    check_temperature(T_w, '湿球温度');
    check_temperature(Td, '露点温度');
    check_pressure(P);
    const rh = _finite(rh_frac, '相对湿度');
    if (!(0.0 <= rh && rh <= 1.0)) {
      throw new InputError('相对湿度（小数，0.6 表示 60%）需在 [0, 1] 范围内（收到 ' + pyG(rh) + '）。' +
        '若手上是百分数，请改用 calculate_both(..., rh_pct=' + pyG(rh) + ') 那条入口。');
    }

    const T_g_K = T_g + 273.15;
    const Cp = CP_DRY0 + CP_DRY_SLOPE * T_g;
    const Cpw = CP_VAPOR;
    const Cv = Cp - RD;                 // 定容比热必须由"比气体常数"换算（旧版误用摩尔气体常数）
    const Cvw = Cpw - RV;
    const ups = EPSILON;
    const upsilon = (1 - ups) / ups;

    const es = calculate_esat(T_g, method);
    const esw = calculate_esat(T_w, method);
    const e = calculate_esat(Td, method);
    if (e >= P) {
      throw new InputError('水汽压 e = ' + pyG(e, 4) + ' hPa 不小于大气压 P = ' + pyG(P, 4) + ' hPa：' +
        '该（露点 ' + pyG(Td) + ' ℃，压强 ' + pyG(P) + ' hPa）组合物理上不成立。');
    }
    const P_dry = P - e;
    const x = e / P;
    const q_spec = ups * e / (P - (1 - ups) * e);            // 比湿（质量分数）
    const gamma_mix = ((1 - q_spec) * Cp + q_spec * Cpw) / ((1 - q_spec) * Cv + q_spec * Cvw);
    const M_mix = ((1 - x) * MD + x * MV) / 1000;
    const v_sound = Math.sqrt(gamma_mix * R_UNIVERSAL * T_g_K / M_mix);

    const ro_dry = P_dry * 100 / (RD * T_g_K);
    const ro_vapor = e * 100 / (RV * T_g_K);                 // 用水汽压 e，不是 esw
    const ro = ro_dry + ro_vapor;
    const dm = ro_vapor / ro_dry;
    const dm1 = dm * 1000;
    const L_v = 2500.8 - 2.3665 * T_g - 0.0023 * Math.pow(T_g, 2) + 1.87e-5 * Math.pow(T_g, 3) - 4.2e-8 * Math.pow(T_g, 4);
    const han = Cp / 1000 * T_g + (L_v + CP_LIQUID / 1000 * T_g) * dm;   // 潜热项用液态水比热

    const sat_mixing_ratio = P > es ? ups * (es / (P - es)) * 1000 : 0;
    const absolute_humidity = (e * 100) / (RV * T_g_K) * 1e3;
    const specific_humidity = q_spec * 1000;

    const q = q_spec;
    const virtual_temp_K = T_g_K * (1 + upsilon * q);
    const theta_K = T_g_K * Math.pow(1000 / P, RD / Cp);
    const theta_e_K = theta_K * Math.exp(L_v * 1000 * q / (Cp * T_g_K));   // 简化相当位温
    const theta_v_K = theta_K * (1 + upsilon * q);

    // 抬升凝结高度：Bolton (1980) 式 (21)，T、T_d 用开尔文
    let t_lcl_C, p_lcl_hPa;
    try {
      if (rh <= 0) throw new Error('rh=0 时露点无定义，LCL 不可解');
      const Td_K = Td + 273.15;
      const t_lcl_K = 1.0 / (1.0 / (Td_K - 56.0) + Math.log(T_g_K / Td_K) / 800.0) + 56.0;
      t_lcl_C = t_lcl_K - 273.15;
      p_lcl_hPa = P * Math.pow(t_lcl_K / T_g_K, Cp / RD);
      if (!Number.isFinite(t_lcl_C) || !Number.isFinite(p_lcl_hPa)) {
        t_lcl_C = NaN; p_lcl_hPa = NaN;
      }
    } catch (e2) {
      t_lcl_C = NaN; p_lcl_hPa = NaN;      // 对应 Python 的 (ValueError, ZeroDivisionError, OverflowError)
    }

    return {
      e: e, es: es, esw: esw, P_dry: P_dry, x: x, gamma_mix: gamma_mix, v_sound: v_sound,
      ro_dry: ro_dry, ro_vapor: ro_vapor, ro: ro, dm: dm, dm1: dm1, L_v: L_v, han: han,
      sat_mixing_ratio: sat_mixing_ratio, absolute_humidity: absolute_humidity,
      specific_humidity: specific_humidity, q: q,
      virtual_temp_K: virtual_temp_K, theta_K: theta_K, theta_e_K: theta_e_K,
      theta_v_K: theta_v_K, t_lcl_C: t_lcl_C, p_lcl_hPa: p_lcl_hPa,
    };
  }

  /* ==================== §8 导出 ==================== */

  const WBCore = {
    // 版本
    WEB_TAG: WEB_TAG, EXE_TAG: EXE_TAG, tag: EXE_TAG, tot: tot,
    // 常量
    R_UNIVERSAL: R_UNIVERSAL, MV: MV, MD: MD, RD: RD, RV: RV, EPSILON: EPSILON,
    CP_DRY0: CP_DRY0, CP_DRY_SLOPE: CP_DRY_SLOPE, CP_VAPOR: CP_VAPOR, CP_LIQUID: CP_LIQUID,
    A0_WATER: A0_WATER, A0_ICE: A0_ICE, A_T_COEF: A_T_COEF,
    T_MIN: T_MIN, T_MAX: T_MAX, P_MIN: P_MIN, P_MAX: P_MAX, RH_MAX: RH_MAX,
    // 类型
    InputError: InputError, NumericOverflow: NumericOverflow,
    // 校验
    check_temperature: check_temperature, check_pressure: check_pressure,
    check_relative_humidity: check_relative_humidity,
    // 注册表
    FORMULAS: FORMULAS, FAMILY_TABLE: _FAMILY_TABLE,
    register_formula: register_formula, get_formula: get_formula, iter_formulas: iter_formulas,
    psychrometer_A: psychrometer_A,
    // 计算
    calculate_esat: calculate_esat, calculate_dedt: calculate_dedt, esat_calculate: esat_calculate,
    calculate_wetbulb: calculate_wetbulb, calculate_dewpoint: calculate_dewpoint,
    calculate_both: calculate_both, derive_moist_air: derive_moist_air,
    // Python 语义格式化（界面层也用，保证显示与 exe 逐位一致）
    pyFixed: pyFixed, pyG: pyG, pyRepr: pyRepr,
  };

  root.WBCore = WBCore;
  if (typeof module !== 'undefined' && module.exports) module.exports = WBCore;
})(typeof globalThis !== 'undefined' ? globalThis : this);
