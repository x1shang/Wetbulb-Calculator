/* =====================================================================
 * ui.js — 湿球计算器 网页版 v2.0.0 · 界面与交互
 * =====================================================================
 * 【分工】
 *   core.js   计算内核（src/core.py 的移植，纯函数、不碰 DOM）
 *   vectors.js 页内自检的黄金向量（由 scripts/export_vectors.py 生成）
 *   本文件    所有界面行为：状态、单位换算、输入校验、结果渲染、派生量、
 *             迭代图、批量导入导出、公式档案、导出与分享、本地记忆。
 *
 * 【与桌面版 main.py 的对应关系】
 *   main_window.validate_and_calculate  → compute()
 *   main_window.check_input             → checkInput()
 *   main_window.changetemp/changepre    → toCelsius/toHpa（与其反函数）
 *   CalculatorMemory.show_results       → renderResults()
 *   CalculatorMemory.add_iteration      → memory.iterations（供图表用）
 *   on_list_item_clicked（派生量面板）  → selectRow() / renderDerived()
 *   CalculatorMemory.show_convergence   → drawChart()
 *   UnitDialog / AboutDialog            → 设置弹窗 / 关于视图
 *   批量计算（src/batch.py）            → CSV / XLSX 导入导出
 *
 * 【有意与桌面版不同的地方（关于视图里也列了）】
 *   1. 切模式、改单位不再清空输入框（桌面版 clearall() 会清空）；
 *   2. 结果表头按模式语义书写（桌面版模式 1 也会写「| 相对湿度」）；
 *   3. 批量计算改为浏览器内导入导出 CSV / XLSX；
 *   4. 迭代图是可交互 SVG，内嵌而非弹窗；
 *   5. 新增数值自检、公式档案、导出、分享链接、本地记忆。
 * 除这些之外，术语、模式名、单位、状态文案、A/B/C 列约定、Goff 水面/冰面
 * 选定规则、#VALUE! 错误规则都**逐条对齐**桌面版。
 * ===================================================================== */

(function () {
  'use strict';

  const C = window.WBCore;
  const V = window.WB_VECTORS;
  const $ = (id) => document.getElementById(id);

  /* ==================== 1. 常量（对齐 main.py） ==================== */

  // 单位换算的**唯一定义**（main.py 顶部）：1 mmHg = 133.322387415 Pa 是定义值
  const MMHG_HPA = 133.322387415 / 100;
  const CMHG_HPA = MMHG_HPA * 10;
  const UI_P_MIN_HPA = 500.0, UI_P_MAX_HPA = 1100.0;   // 交互路径的压强域
  const UI_T_MIN_C = -150.0, UI_T_MAX_C = 200.0;       // 与 core.T_MIN / T_MAX 一致
  const ACCENT_DEFAULT = '71, 148, 157';               // assets/cfg.json 的 title_color
  const STORAGE_KEY = 'wetbulb-web/v2/state';
  const REPO_URL = 'https://github.com/x1shang/Wetbulb-Calculator';
  const RELEASES_URL = REPO_URL + '/releases';

  // 三种模式（名称与桌面版 ComboBox 的三项逐字一致）
  const MODES = [
    { id: 0, name: '已知露点求湿球', other: '露点温度', r1: '湿球温度', r2: null },
    { id: 1, name: '已知湿球求露点', other: '湿球温度', r1: '露点温度', r2: null },
    { id: 2, name: '已知相对湿度', other: '相对湿度', r1: '露点温度', r2: '湿球温度' },
  ];
  // 单位映射（与 UnitDialog.update_units 的表逐项一致）
  const PRESSURE_UNITS = { Pa: [50000, 110000], hPa: [500, 1100], mmHg: [375, 825], cmHg: [37.5, 82.5], bar: [0.5, 1.1] };
  const TEMP_UNITS = { K: [123.15, 473.15], '℃': [-150, 200], '℉': [-238, 392] };

  // 迭代曲线的配色：按公式注册顺序取色，保证同一公式在任何一次计算里同色。
  // 分两套是因为"当线条颜色好看"与"当文字颜色能读"要求相反：浅色玻璃上要用压暗过的
  // 一支（纯 #47949d 在浅底上只有 2.8:1），深色背景上则要用鲜亮的一支。
  const PALETTE = ['#47949d', '#5aa9c9', '#7f8fe0', '#a07fd6', '#c96fa8', '#e0736f', '#e0975f',
    '#d9b64e', '#a8c05a', '#6fc17a', '#4fb99b', '#3f9fb5', '#6b8fd0', '#9a7fc9'];
  const PALETTE_LIGHT = PALETTE.map((hex) => {
    const n = parseInt(hex.slice(1), 16);
    const mix = (c) => Math.round(c * 0.78);
    return '#' + [mix((n >> 16) & 255), mix((n >> 8) & 255), mix(n & 255)]
      .map((c) => c.toString(16).padStart(2, '0')).join('');
  });
  function palette() { return state.theme === 'dark' ? PALETTE : PALETTE_LIGHT; }
  function methodColor(method) {
    const i = Math.max(0, C.FORMULAS.findIndex((f) => f.name === method));
    return palette()[i % palette().length];
  }

  /* ==================== 2. 状态 ==================== */

  const state = {
    mode: 0,
    tempUnit: '℃',
    pressureUnit: 'hPa',
    precision: 7,                 // 桌面版 dial 默认 7 → tol = 1e-7
    strategy: 'Td',               // Tw=Td / Tw=T-n
    theme: 'light',
    accent: ACCENT_DEFAULT,
    tab: 'calc',
    selected: null,               // 选中的公式名
    results: [],
    iterations: {},               // 公式 → {iterations, temperatures, residuals}
    solved: null,                 // 本次计算的 T / other / P（标准单位 ℃ / hPa）
    inputs: { t: '25', other: '15', p: '1013.25' },
    batch: null,                  // {name, headers, rows, results}
  };

  const tol = () => Math.pow(10, -state.precision);

  /* ==================== 3. 单位换算（main.py 的四个函数） ==================== */

  function toCelsius(v) {
    if (state.tempUnit === 'K') return v - 273.15;
    if (state.tempUnit === '℉') return (v - 32) * 5 / 9;
    return v;
  }
  function fromCelsius(v) {
    if (state.tempUnit === 'K') return v + 273.15;
    if (state.tempUnit === '℉') return v * 9 / 5 + 32;
    return v;
  }
  function toHpa(p) {
    switch (state.pressureUnit) {
      case 'Pa': return p / 100;
      case 'mmHg': return p * MMHG_HPA;
      case 'cmHg': return p * CMHG_HPA;
      case 'bar': return p * 1000;
      default: return p;
    }
  }
  function fromHpa(p) {
    switch (state.pressureUnit) {
      case 'Pa': return p * 100;
      case 'mmHg': return p / MMHG_HPA;
      case 'cmHg': return p / CMHG_HPA;
      case 'bar': return p / 1000;
      default: return p;
    }
  }

  /* ==================== 4. 输入解析与校验 ==================== */

  /**
   * Python float() 的等价解析。
   * 【为什么不能直接用 Number()】Number('0x10') === 16 而 Python float('0x10') 抛错；
   * Number('60%') 是 NaN 但 Python 也是抛错（这条一致）；Number('1_0') 是 NaN 而
   * Python float('1_0') === 10.0（PEP 515 支持下划线）；Number('') === 0 而 Python
   * float('') 抛错。解析口径不一致 = "校验的数和算的数不是同一个"，
   * 这正是桌面版 v1.3.2 修掉的那类缺陷（B-25/B-26）。
   */
  const RE_FLOAT = /^[+-]?(?:\d(?:_?\d)*)?(?:\.(?:\d(?:_?\d)*)?)?(?:[eE][+-]?\d(?:_?\d)*)?$/;
  function pyFloatParse(text) {
    const s = String(text).trim();
    if (s === '') return { ok: false, empty: true };
    if (/^[+-]?inf(inity)?$/i.test(s)) return { ok: true, value: s[0] === '-' ? -Infinity : Infinity };
    if (/^[+-]?nan$/i.test(s)) return { ok: true, value: NaN };
    if (!RE_FLOAT.test(s)) return { ok: false };
    if (!/\d/.test(s)) return { ok: false };          // 只有符号/小数点不算数
    const v = parseFloat(s.replace(/_/g, ''));
    if (Number.isNaN(v)) return { ok: false };
    return { ok: true, value: v };
  }

  /**
   * 对应 main_window.check_input：解析、换算到 ℃/hPa、检查区间。
   * 成功返回 {value: 换算后的数值}，失败弹错误条并返回 null。
   * 【与桌面版的一处差异】桌面版失败时会 clear() 输入框；这里保留文本并标红，
   * 因为用户多半只是打错一个字符，清空反而要他重打一遍。
   */
  function checkInput(el, fieldName) {
    const raw = el.value;
    if (raw.trim() === '') {
      toast('error', fieldName + '不能为空！');
      markInvalid(el, true);
      el.focus();
      return null;
    }
    const parsed = pyFloatParse(raw);
    if (!parsed.ok) {
      toast('error', fieldName + '必须是有效数字（收到「' + raw.trim() + '」）');
      markInvalid(el, true);
      el.focus();
      return null;
    }
    const value = parsed.value;
    if (!Number.isFinite(value)) {
      toast('error', fieldName + '必须是有限数值（收不到 NaN / 无穷大）');
      markInvalid(el, true);
      el.focus();
      return null;
    }
    markInvalid(el, false);

    if (fieldName.indexOf('温度') >= 0) {
      const value_C = toCelsius(value);
      if (!(UI_T_MIN_C <= value_C && value_C <= UI_T_MAX_C)) {
        const minUi = fromCelsius(UI_T_MIN_C), maxUi = fromCelsius(UI_T_MAX_C);
        toast('error', fieldName + '需在 [' + minUi.toFixed(2) + ', ' + maxUi.toFixed(2) + ']'
          + state.tempUnit + ' 范围内');
        markInvalid(el, true);
        return null;
      }
      return { value: value_C };
    }

    if (fieldName.indexOf('压强') >= 0) {
      const value_hPa = toHpa(value);
      if (!(UI_P_MIN_HPA <= value_hPa && value_hPa <= UI_P_MAX_HPA)) {
        const minUi = fromHpa(UI_P_MIN_HPA), maxUi = fromHpa(UI_P_MAX_HPA);
        toast('error', fieldName + '需在 [' + minUi.toFixed(2) + ', ' + maxUi.toFixed(2) + ']'
          + state.pressureUnit + ' 范围内');
        markInvalid(el, true);
        return null;
      }
      return { value: value_hPa };
    }

    if (fieldName.indexOf('相对湿度') >= 0) {
      // 与 core.check_relative_humidity 一致：下界是开区间（RH=0 时露点无定义）
      if (!(0.0 < value && value <= 100.0)) {
        toast('error', '相对湿度必须在 (0, 100] % 之间！');
        markInvalid(el, true);
        return null;
      }
      return { value: value };
    }
    return { value: value };
  }

  function markInvalid(el, bad) {
    if (bad) el.classList.add('invalid');
    else el.classList.remove('invalid');
  }

  /* ==================== 5. 计算流程（validate_and_calculate） ==================== */

  function initialGuess(T, T_other) {
    if (state.strategy === 'Tn') return T < 0 ? T - 2 : T - 5;
    return T_other;
  }

  function compute() {
    const mode = state.mode;
    const T = checkInput($('in-dry'), '干球温度');
    if (T === null) return;
    const targetLabel = $('label-other').textContent.replace(/\s/g, '').replace(/：$/, '');
    const other = checkInput($('in-other'), targetLabel);
    if (other === null) return;
    const P = checkInput($('in-pressure'), '大气压强');
    if (P === null) return;

    if (mode <= 1 && other.value >= T.value) {
      toast('error', targetLabel + '不能高于干球温度！');
      return;
    }

    state.inputs = { t: $('in-dry').value, other: $('in-other').value, p: $('in-pressure').value };

    const memory = { results: [], iterations: {} };
    const on_result = (row) => memory.results.push(row);
    const on_iter = (method, iteration, T_w, residual) => {
      if (!memory.iterations[method]) {
        memory.iterations[method] = { iterations: [], temperatures: [], residuals: [] };
      }
      const d = memory.iterations[method];
      d.iterations.push(iteration);
      d.temperatures.push(T_w);
      d.residuals.push(Math.abs(residual));
    };

    try {
      if (mode === 0) {
        C.calculate_wetbulb(initialGuess(T.value, other.value), T.value, other.value, P.value,
          undefined, tol(), on_result, on_iter);
      } else if (mode === 1) {
        C.calculate_dewpoint(T.value, other.value, P.value, undefined, tol(), on_result, on_iter);
      } else {
        C.calculate_both(initialGuess(T.value, T.value), T.value, other.value, P.value,
          undefined, tol(), on_result, on_iter);
      }
    } catch (ex) {
      toast('error', ex && ex.message ? ex.message : String(ex));
      return;
    }

    state.results = memory.results;
    state.iterations = memory.iterations;
    state.solved = { T: T.value, other: other.value, P: P.value };
    if (state.selected && !memory.results.some((r) => r.method === state.selected)) state.selected = null;
    renderResults();
    renderDerived();
    drawChart();
    saveState();
  }

  function clearAll() {
    $('in-dry').value = '';
    $('in-other').value = '';
    $('in-pressure').value = '';
    ['in-dry', 'in-other', 'in-pressure'].forEach((id) => markInvalid($(id), false));
    state.results = [];
    state.iterations = {};
    state.selected = null;
    state.solved = null;
    $('in-dry').focus();
    renderResults();
    renderDerived();
    drawChart();
  }

  /* ==================== 6. 结果渲染 ==================== */

  function isNum(v) { return typeof v === 'number' && Number.isFinite(v); }

  function statusOf(row, mode) {
    const okNumeric = isNum(row.result1) && (mode === 2 ? (isNum(row.result2) || typeof row.result2 === 'string') : true);
    if (typeof row.result1 !== 'number') {
      const s = String(row.result1);
      if (s === '不适用') return { kind: 'na', text: '不适用', tip: '干球或已知量落在该公式的注册域之外' };
      if (s === '状态不成立') return { kind: 'warn', text: '状态不成立', tip: '水汽分压已达总压：该组合物理上不成立（不是湿空气）' };
      if (s === '结果不符常理') return { kind: 'warn', text: '结果不符常理', tip: '算出的相对湿度不在 [0,100%] 内' };
      if (/^错误[:：]/.test(s) || s === '计算失败' || s === '数值溢出') return { kind: 'bad', text: s.slice(0, 14), tip: s };
      return { kind: 'bad', text: '越界/异常', tip: s };
    }
    if (mode === 2) {
      if (row.result2 === '湿球残差过大') return { kind: 'warn', text: '湿球残差过大', tip: '湿球方程在该区间无解' };
      if (row.result2 === '湿球未收敛') return { kind: 'warn', text: '湿球未收敛', tip: '迭代达到上限仍未收敛' };
      if (typeof row.result2 !== 'number') return { kind: 'warn', text: String(row.result2).slice(0, 12), tip: String(row.result2) };
    }
    if (!okNumeric) return { kind: 'warn', text: '部分可用', tip: '' };
    return { kind: 'ok', text: 'ok', tip: '' };
  }

  function fmtTemp(v) {
    if (!isNum(v)) return String(v);
    return C.pyFixed(fromCelsius(v), 4) + state.tempUnit;
  }
  function fmtRh(v) {
    if (v === null || v === undefined || !isNum(v)) return '';
    return C.pyFixed(v * 100, 2) + '%';
  }

  function renderResults() {
    const mode = state.mode;
    const info = MODES[mode];
    const body = $('results-body');
    const empty = $('results-empty');
    const wrap = $('results-wrap');
    body.innerHTML = '';

    // 表头：按模式决定列（桌面版把两个字段都印在一行里，这里做成表格更易读）
    $('th-result1').textContent = info.r1;
    const th2 = $('th-result2'), thRh = $('th-rh');
    if (mode === 2) {
      th2.textContent = info.r2; th2.classList.remove('hidden');
      thRh.classList.add('hidden');
    } else {
      th2.classList.add('hidden');
      thRh.classList.remove('hidden');
    }
    $('results-title').textContent = '逐公式结果 · ' + info.name;

    if (!state.results.length) {
      empty.classList.remove('hidden');
      wrap.classList.add('hidden');
      $('results-note').textContent = '';
      return;
    }
    empty.classList.add('hidden');
    wrap.classList.remove('hidden');

    let countOk = 0, countNa = 0, countBad = 0;
    state.results.forEach((row) => {
      const f = C.get_formula(row.method);
      const status = statusOf(row, mode);
      if (status.kind === 'ok') countOk++;
      else if (status.kind === 'na') countNa++;
      else countBad++;

      const tr = document.createElement('tr');
      tr.className = 'row-' + status.kind;

      const tdMethod = document.createElement('td');
      tdMethod.className = 'method';
      // 与迭代图同色的圆点：让"表里这一行"与"图上那条线"一眼对得上
      const dot = document.createElement('span');
      dot.className = 'method-dot';
      dot.style.background = methodColor(row.method);
      tdMethod.appendChild(dot);
      tdMethod.appendChild(document.createTextNode(row.method));
      if (f) tr.title = row.method + '｜族：' + f.family + '｜注册域 ' + f.tmin + '~' + f.tmax + ' ℃';
      tr.appendChild(tdMethod);

      const tdDomain = document.createElement('td');
      tdDomain.className = 'dim mono tiny';
      tdDomain.textContent = f ? (f.tmin + '~' + f.tmax + '℃') : '—';
      tr.appendChild(tdDomain);

      const tdR1 = document.createElement('td');
      tdR1.className = 'num';
      if (isNum(row.result1)) tdR1.textContent = fmtTemp(row.result1);
      else { tdR1.textContent = String(row.result1); tdR1.className = 'dim'; tdR1.style.whiteSpace = 'normal'; tdR1.style.maxWidth = '340px'; }
      tr.appendChild(tdR1);

      if (mode === 2) {
        const tdR2 = document.createElement('td');
        tdR2.className = 'num';
        if (isNum(row.result2)) tdR2.textContent = fmtTemp(row.result2);
        else { tdR2.textContent = String(row.result2); tdR2.className = 'dim'; }
        tr.appendChild(tdR2);
      } else {
        const tdRh = document.createElement('td');
        tdRh.className = 'num dim';
        tdRh.textContent = fmtRh(row.rh) || '—';
        tr.appendChild(tdRh);
      }

      const tdSt = document.createElement('td');
      const badge = document.createElement('span');
      badge.className = 'badge ' + status.kind;
      badge.innerHTML = '<span class="pip"></span>';
      badge.appendChild(document.createTextNode(status.text));
      if (status.tip) badge.title = status.tip;
      tdSt.appendChild(badge);
      tr.appendChild(tdSt);

      tr.addEventListener('click', () => selectRow(row.method));
      if (row.method === state.selected) tr.classList.add('selected');
      body.appendChild(tr);
    });

    const s = state.solved;
    $('results-note').textContent =
      '干球 ' + C.pyFixed(fromCelsius(s.T), 4) + state.tempUnit
      + ' · ' + MODES[mode].other + ' ' + (mode === 2 ? C.pyFixed(s.other, 2) + '%' : C.pyFixed(fromCelsius(s.other), 4) + state.tempUnit)
      + ' · ' + C.pyFixed(fromHpa(s.P), 2) + ' ' + state.pressureUnit
      + '　|　适用 ' + countOk + ' 条 · 不适用 ' + countNa + ' 条 · 异常 ' + countBad + ' 条'
      + '　|　迭代容差 1e-' + state.precision + '　|　初值策略 ' + (state.strategy === 'Tn' ? 'Tw=T-n' : 'Tw=Td');
  }

  /* ==================== 7. 常用气象参数（24 项派生量） ==================== */

  // 分组与格式：数值格式逐项对齐 main.py 的 on_list_item_clicked
  function derivedSpec() {
    const pu = state.pressureUnit, tu = state.tempUnit;
    const P = (v) => C.pyFixed(fromHpa(v), 2);
    const P1 = (v) => C.pyFixed(fromHpa(v), 1);
    const T = (v) => (Number.isFinite(v) ? C.pyFixed(fromCelsius(v), 2) : null);
    return [
      { g: '湿度', k: 'rh', label: '相对湿度', unit: '%', sub: '由该公式的 e / es 得出', f: (v) => C.pyFixed(v * 100, 2) },
      { g: '湿度', k: 'absolute_humidity', label: '绝对湿度', unit: 'g/m³', sub: null, f: (v) => C.pyFixed(v, 3) },
      { g: '湿度', k: 'specific_humidity', label: '比湿', unit: 'g/kg', sub: '水汽质量分数 ×1000', f: (v) => C.pyFixed(v, 3) },
      { g: '湿度', k: 'q', label: '比湿', unit: 'kg/kg', sub: '与上面同一个量的 kg/kg 口径', f: (v) => C.pyFixed(v, 6) },
      { g: '湿度', k: 'dm1', label: '含湿量', unit: 'g/kg', sub: 'ρv/ρd ×1000', f: (v) => C.pyFixed(v, 3) },
      { g: '湿度', k: 'dm', label: '混合率', unit: '—', sub: 'ρv/ρd（比值口径）', f: (v) => C.pyFixed(v, 6) },
      { g: '湿度', k: 'sat_mixing_ratio', label: '饱和混合率', unit: 'g/kg', sub: '用饱和水汽压 es 算的', f: (v) => C.pyFixed(v, 3) },
      { g: '湿度', k: 'x', label: '水蒸气摩尔分数', unit: '%', sub: 'e/P', f: (v) => C.pyFixed(v * 100, 1) },

      { g: '蒸气压', k: 'e', label: '蒸气压', unit: pu, sub: '由露点算出', f: P },
      { g: '蒸气压', k: 'es', label: '饱和蒸气压', unit: pu, sub: '干球温度处', f: P },
      { g: '蒸气压', k: 'esw', label: '湿球蒸气压', unit: pu, sub: '湿球温度处', f: P },
      { g: '蒸气压', k: 'P_dry', label: '干空气分压', unit: pu, sub: 'P − e', f: P1 },

      { g: '密度', k: 'ro_dry', label: '干空气密度', unit: 'kg/m³', sub: null, f: (v) => C.pyFixed(v, 3) },
      { g: '密度', k: 'ro_vapor', label: '水蒸气密度', unit: 'kg/m³', sub: '由实际水汽压 e 决定', f: (v) => C.pyFixed(v, 3) },
      { g: '密度', k: 'ro', label: '空气密度', unit: 'kg/m³', sub: '干空气 + 水蒸气', f: (v) => C.pyFixed(v, 3) },

      { g: '能量', k: 'han', label: '焓值', unit: 'kJ/kg', sub: '相对 0 ℃ 干空气与 0 ℃ 液态水', f: (v) => C.pyFixed(v, 2) },
      { g: '能量', k: 'L_v', label: '蒸发潜热', unit: 'kJ/kg', sub: null, f: (v) => C.pyFixed(v, 1) },

      { g: '温度', k: 'virtual_temp_K', label: '虚温', unit: tu, sub: 'TV = T(1+0.608q)', f: (v) => T(v - 273.15) },
      { g: '温度', k: 'theta_K', label: '位温', unit: tu, sub: 'θ = T(1000/P)^(Rd/Cp)', f: (v) => T(v - 273.15) },
      { g: '温度', k: 'theta_e_K', label: '相当位温', unit: tu, sub: '简化式 θ·exp(Lv·q/(Cp·T))', f: (v) => T(v - 273.15) },
      { g: '温度', k: 'theta_v_K', label: '虚位温', unit: tu, sub: 'θ(1+0.608q)', f: (v) => T(v - 273.15) },
      { g: '温度', k: 't_lcl_C', label: 'lcl 温度', unit: tu, sub: '抬升凝结高度（Bolton 1980 式21）', f: (v) => T(v) },

      { g: '其它', k: 'p_lcl_hPa', label: 'lcl 压强', unit: pu, sub: '凝结高度处的气压', f: (v) => (Number.isFinite(v) ? C.pyFixed(fromHpa(v), 1) : null) },
      { g: '其它', k: 'gamma_mix', label: '湿空气绝热指数', unit: '—', sub: '由比热比定义', f: (v) => C.pyFixed(v, 2) },
      { g: '其它', k: 'v_sound', label: '空气中声速', unit: 'm/s', sub: '√(γ·R·T/M)', f: (v) => C.pyFixed(v, 1) },
    ];
  }

  function selectRow(method) {
    state.selected = method;
    renderResults();
    renderDerived();
    const card = $('derived-card');
    if (card && card.scrollIntoView) card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function renderDerived() {
    const host = $('derived-host');
    const empty = $('derived-empty');
    const chip = $('derived-method');
    host.innerHTML = '';

    const mode = state.mode;
    const row = state.results.find((r) => r.method === state.selected);
    if (!row || !state.solved) {
      host.classList.add('hidden');
      empty.classList.remove('hidden');
      chip.textContent = '点结果表任意一行';
      return;
    }
    if (!isNum(row.result1) || (mode === 2 && !isNum(row.result2))) {
      host.classList.add('hidden');
      empty.classList.remove('hidden');
      empty.textContent = '该行没有可用的数值结果，无法推导派生量';
      return;
    }
    const s = state.solved;
    let Td, Tw, rh;
    if (mode === 0) { Td = s.other; Tw = row.result1; rh = row.rh; }
    else if (mode === 1) { Tw = s.other; Td = row.result1; rh = row.rh; }
    else { Td = row.result1; Tw = row.result2; rh = (row.rh === null || row.rh === undefined) ? s.other / 100 : row.rh; }
    if (rh === null || rh === undefined) {
      host.classList.add('hidden');
      empty.classList.remove('hidden');
      empty.textContent = '该行没有给出相对湿度，无法推导派生量';
      return;
    }

    let d;
    try {
      d = C.derive_moist_air(s.T, Tw, Td, rh, s.P, row.method);
    } catch (ex) {
      host.classList.add('hidden');
      empty.classList.remove('hidden');
      empty.textContent = '派生量计算失败：' + ex.message;
      return;
    }
    d.rh = rh;

    empty.classList.add('hidden');
    host.classList.remove('hidden');
    chip.textContent = row.method + ' · ' + MODES[mode].name;

    let currentGroup = null;
    derivedSpec().forEach((spec) => {
      if (spec.g !== currentGroup) {
        currentGroup = spec.g;
        const h = document.createElement('div');
        h.className = 'derived-group';
        h.innerHTML = '<h4>' + spec.g + '</h4>';
        host.appendChild(h);
      }
      const raw = d[spec.k];
      const text = spec.f(raw);
      const cell = document.createElement('div');
      cell.className = 'kv';
      const k = document.createElement('span');
      k.className = 'k';
      k.textContent = spec.label;
      if (spec.sub) {
        const small = document.createElement('small');
        small.textContent = spec.sub;
        k.appendChild(small);
      }
      const v = document.createElement('span');
      v.className = 'v';
      v.textContent = (text === null || text === 'nan') ? '—' : text;
      const u = document.createElement('span');
      u.className = 'u';
      u.textContent = spec.unit;
      v.appendChild(u);
      cell.appendChild(k);
      cell.appendChild(v);
      host.appendChild(cell);
    });
  }

  /* ==================== 8. 提示条（InfoBar 的网页版） ==================== */

  const ICONS = {
    success: '#i-check',
    error: '#i-alert',
    info: '#i-info',
  };
  function toast(kind, message, title) {
    const box = document.createElement('div');
    box.className = 'toast ' + kind;
    box.innerHTML =
      '<svg class="t-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
      'stroke-linecap="round" stroke-linejoin="round"><use href="' + (ICONS[kind] || ICONS.info) + '"/></svg>' +
      '<div class="t-body"><div class="t-title"></div><div class="t-msg"></div></div>' +
      '<button class="t-close" type="button" aria-label="关闭">×</button>';
    box.querySelector('.t-title').textContent = title || (kind === 'error' ? '错误！' : kind === 'success' ? '处理成功！' : '提示');
    box.querySelector('.t-msg').textContent = message;
    const close = () => { box.classList.add('out'); setTimeout(() => box.remove(), 260); };
    box.querySelector('.t-close').addEventListener('click', close);
    $('toasts').appendChild(box);
    setTimeout(close, kind === 'error' ? 7000 : 4200);
    return box;
  }

  /* ==================== 9. 主题 / 强调色 / 本地记忆 ==================== */

  /** 强调色的"当文字用"版本：浅底压暗 22%、深底向白提亮 55%。 */
  function accentTextFor(parts, theme) {
    if (theme === 'dark') return parts.map((c) => Math.round(c + (255 - c) * 0.55)).join(', ');
    return parts.map((c) => Math.round(c * 0.78)).join(', ');
  }

  function applyAccent(rgbTriplet) {
    state.accent = rgbTriplet;
    const parts = rgbTriplet.split(',').map((x) => parseInt(x.trim(), 10));
    document.documentElement.style.setProperty('--accent', parts.join(', '));
    // 亮部：把三个通道各向 255 靠一点，得到同色系的浅色渐变端点
    const light = parts.map((c) => Math.round(c + (255 - c) * 0.42)).join(', ');
    document.documentElement.style.setProperty('--accent-2', light);
    // 强调色**当文字用**时的版本：浅底压暗、深底提亮。纯强调色在浅玻璃上实测只有
    // 2.8:1（WCAG AA 要 4.5:1），所以品牌色本身不动，只换"当文字"的这一支。
    document.documentElement.style.setProperty('--accent-text', accentTextFor(parts, state.theme));
    const inp = $('accent-input');
    const readout = $('accent-readout');
    if (inp) inp.value = '#' + parts.map((c) => c.toString(16).padStart(2, '0')).join('');
    if (readout) readout.textContent = 'rgb(' + parts.join(', ') + ')';
  }

  function applyTheme(theme) {
    state.theme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    // 主题变了，强调色的"文字版本"也要跟着换（浅底压暗 / 深底提亮）
    const parts = state.accent.split(',').map((x) => parseInt(x.trim(), 10));
    if (parts.length === 3 && parts.every((c) => Number.isFinite(c))) {
      document.documentElement.style.setProperty('--accent-text', accentTextFor(parts, theme));
    }
    const use = $('theme-icon');
    if (use) use.setAttribute('href', theme === 'dark' ? '#i-sun' : '#i-moon');
    const btn = $('btn-theme');
    if (btn) btn.title = theme === 'dark' ? '切换到浅色主题' : '切换到深色主题';
  }

  function saveState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        mode: state.mode, tempUnit: state.tempUnit, pressureUnit: state.pressureUnit,
        precision: state.precision, strategy: state.strategy, theme: state.theme,
        accent: state.accent, inputs: state.inputs, tab: state.tab,
      }));
    } catch (e) { /* 无痕模式等场景下写不了，忽略即可 */ }
  }

  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (e) { return null; }
  }

  /* ==================== 10. 单位与标签刷新 ==================== */

  function refreshUnitLabels() {
    const tRange = TEMP_UNITS[state.tempUnit];
    const pRange = PRESSURE_UNITS[state.pressureUnit];
    const tHint = tRange[0] + '~' + tRange[1] + state.tempUnit;
    const pHint = pRange[0] + '~' + pRange[1] + state.pressureUnit;
    $('unit-dry').textContent = state.tempUnit;
    $('unit-other').textContent = state.mode === 2 ? '%' : state.tempUnit;
    $('unit-pressure').textContent = state.pressureUnit;
    $('hint-dry').textContent = tHint;
    $('hint-pressure').textContent = pHint;
    $('hint-other').textContent = state.mode === 2 ? '0~100%' : tHint;
    $('in-dry').placeholder = tHint;
    $('in-other').placeholder = state.mode === 2 ? '0~100%' : tHint;
    $('in-pressure').placeholder = pHint;
    $('chip-units').textContent = state.tempUnit + ' · ' + state.pressureUnit;
    $('tol-readout').textContent = '1e-' + state.precision;
    $('batch-mode-chip').textContent = '模式：' + MODES[state.mode].name;
  }

  function setMode(mode, opts) {
    state.mode = mode;
    document.querySelectorAll('.segmented button').forEach((b) => {
      b.setAttribute('aria-pressed', String(Number(b.dataset.mode) === mode));
    });
    $('label-other').textContent = MODES[mode].other + '：';
    $('in-other').setAttribute('aria-label', MODES[mode].other);
    $('iteration-box').classList.toggle('hidden', mode === 1);   // 桌面版模式1隐藏迭代区
    refreshUnitLabels();
    if (opts && opts.recompute) {
      state.selected = null;
      renderResults();
      renderDerived();
      drawChart();
    }
  }

  /* ==================== 11. 标签页 ==================== */

  function setTab(name) {
    state.tab = name;
    const tabs = { calc: 'view-calc', batch: 'view-batch', formulas: 'view-formulas', about: 'view-about' };
    Object.entries(tabs).forEach(([key, viewId]) => {
      const tab = $('tab-' + key), view = $(viewId);
      const on = key === name;
      tab.setAttribute('aria-selected', String(on));
      view.classList.toggle('active', on);
    });
    saveState();
  }
  function onTabKey(e) {
    const order = ['calc', 'batch', 'formulas', 'about'];
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const cur = order.indexOf(state.tab);
    const next = order[(cur + (e.key === 'ArrowRight' ? 1 : order.length - 1)) % order.length];
    setTab(next);
    $('tab-' + next).focus();
  }

  /* ==================== 12. 导出下载的小工具 ==================== */

  function download(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  }
  function downloadText(text, filename, mime) {
    download(new Blob([text], { type: (mime || 'text/plain') + ';charset=utf-8' }), filename);
  }
  function stamp() {
    const d = new Date();
    const p = (n) => String(n).padStart(2, '0');
    return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + '-' + p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds());
  }

  /* ==================== 13. 迭代可视化（对应 show_convergence） ==================== */

  const chartState = { hidden: new Set() };

  function renderChartMethodOptions() {
    const sel = $('chart-method');
    const methods = Object.keys(state.iterations || {});
    const prev = sel.value;
    sel.innerHTML = '';
    const all = document.createElement('option');
    all.value = '';
    all.textContent = methods.length > 1 ? '全部公式（' + methods.length + ' 条）' : (methods[0] || '全部公式');
    sel.appendChild(all);
    methods.forEach((m) => {
      const o = document.createElement('option');
      o.value = m;
      o.textContent = m;
      sel.appendChild(o);
    });
    if (prev && methods.indexOf(prev) >= 0) sel.value = prev;
  }

  function seriesFor() {
    const want = $('chart-method').value;
    const out = [];
    Object.entries(state.iterations || {}).forEach(([method, d]) => {
      if (want && method !== want) return;
      if (chartState.hidden.has(method)) return;
      if (d.iterations.length <= 1) return;      // 桌面版同样跳过只有一次迭代的数据
      out.push({
        method: method,
        iters: d.iterations.slice(1),             // 略去第 1 个点（那是用户填的初值本身）
        temps: d.temperatures.slice(1),
        residuals: d.residuals.slice(1),
        color: methodColor(method),
      });
    });
    return out;
  }

  function drawChart() {
    const host = $('chart-host');
    const empty = $('chart-empty');
    const tip = $('chart-tip');
    const series = seriesFor();
    renderChartMethodOptions();

    if (!series.length) {
      host.classList.add('hidden');
      empty.classList.remove('hidden');
      if (state.results.length && $('chart-method').value) {
        empty.textContent = '这条公式只迭代了一次（或没有参与迭代），没有可画的收敛过程';
      } else {
        empty.textContent = '先计算，再点这一栏看牛顿迭代的收敛过程';
      }
      $('chart-legend').innerHTML = '';
      return;
    }
    empty.classList.add('hidden');
    host.classList.remove('hidden');

    const W = Math.max(560, host.clientWidth || 880);
    const H = Math.max(240, host.clientHeight || 320);
    const padL = 54, padR = 14, padT = 16, padB = 36, gap = 34;
    const panelW = (W - padL - padR - gap) / 2;
    const plotH = H - padT - padB;

    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.setAttribute('font-family', 'ui-monospace, Consolas, monospace');

    const bg = document.createElementNS(svgNS, 'rect');
    bg.setAttribute('x', 0); bg.setAttribute('y', 0);
    bg.setAttribute('width', W); bg.setAttribute('height', H);
    bg.setAttribute('fill', 'none');
    svg.appendChild(bg);

    const allIters = series.flatMap((s) => s.iters);
    const xMin = Math.min.apply(null, allIters), xMax = Math.max.apply(null, allIters);
    const xSpan = Math.max(1, xMax - xMin);

    function ticksX() {
      const n = 5, out = [];
      for (let i = 0; i <= n; i++) out.push(Math.round(xMin + (xSpan * i) / n));
      return Array.from(new Set(out));
    }
    function ticksY(min, max, log) {
      const out = [];
      if (log) {
        const lo = Math.floor(Math.log10(min)), hi = Math.ceil(Math.log10(max));
        const step = Math.max(1, Math.ceil((hi - lo) / 4));
        for (let e = lo; e <= hi; e += step) out.push(Math.pow(10, e));
        if (out.length < 2) out.push(max);
      } else {
        for (let i = 0; i <= 4; i++) out.push(min + ((max - min) * i) / 4);
      }
      return out;
    }
    function fmtTick(v, log) {
      if (log) { const e = Math.round(Math.log10(v)); return '1e' + (e < 0 ? '-' + Math.abs(e) : '+' + e); }
      return Math.abs(v) >= 1000 || (Math.abs(v) < 0.01 && v !== 0) ? v.toExponential(1) : C.pyFixed(v, Math.abs(v) < 10 ? 2 : 0);
    }

    function panel(x0, seriesList, valueOf, yTitle, log) {
      const g = document.createElementNS(svgNS, 'g');
      svg.appendChild(g);
      const vals = [];
      seriesList.forEach((s) => {
        for (let i = 0; i < s.iters.length; i++) {
          const v = valueOf(s, i);
          if (Number.isFinite(v)) vals.push(v);
        }
      });
      if (!vals.length) return;
      let yMin = Math.min.apply(null, vals), yMax = Math.max.apply(null, vals);
      if (log) {
        const floor = 1e-16;
        yMin = Math.max(yMin, floor); yMax = Math.max(yMax, floor * 10);
        yMin = Math.min(yMin, yMax);
      } else {
        const pad = (yMax - yMin) * 0.08 || 1;
        yMin -= pad; yMax += pad;
      }
      const yPos = (v) => {
        if (log) {
          const lo = Math.log10(yMin), hi = Math.log10(yMax);
          return padT + plotH - ((Math.log10(Math.max(v, yMin)) - lo) / Math.max(1e-9, hi - lo)) * plotH;
        }
        return padT + plotH - ((v - yMin) / Math.max(1e-9, yMax - yMin)) * plotH;
      };
      const xPos = (v) => x0 + ((v - xMin) / xSpan) * panelW;

      // 网格与刻度
      ticksY(yMin, yMax, log).forEach((t) => {
        const y = yPos(t);
        if (y < padT - 1 || y > padT + plotH + 1) return;
        const line = document.createElementNS(svgNS, 'line');
        line.setAttribute('x1', x0); line.setAttribute('x2', x0 + panelW);
        line.setAttribute('y1', y); line.setAttribute('y2', y);
        line.setAttribute('stroke', 'currentColor');
        line.setAttribute('stroke-opacity', '0.12');
        line.setAttribute('stroke-dasharray', '3 4');
        g.appendChild(line);
        const tx = document.createElementNS(svgNS, 'text');
        tx.setAttribute('x', x0 - 8); tx.setAttribute('y', y + 3.5);
        tx.setAttribute('text-anchor', 'end');
        tx.setAttribute('fill', 'currentColor'); tx.setAttribute('fill-opacity', '0.5');
        tx.setAttribute('font-size', '10.5');
        tx.textContent = fmtTick(t, log);
        g.appendChild(tx);
      });
      ticksX().forEach((t) => {
        const x = xPos(t);
        const tx = document.createElementNS(svgNS, 'text');
        tx.setAttribute('x', x); tx.setAttribute('y', padT + plotH + 17);
        tx.setAttribute('text-anchor', 'middle');
        tx.setAttribute('fill', 'currentColor'); tx.setAttribute('fill-opacity', '0.5');
        tx.setAttribute('font-size', '10.5');
        tx.textContent = String(t);
        g.appendChild(tx);
      });
      // 轴
      const axis = document.createElementNS(svgNS, 'path');
      axis.setAttribute('d', 'M' + x0 + ' ' + padT + 'V' + (padT + plotH) + 'H' + (x0 + panelW));
      axis.setAttribute('fill', 'none');
      axis.setAttribute('stroke', 'currentColor'); axis.setAttribute('stroke-opacity', '0.25');
      g.appendChild(axis);
      // 轴标题
      const title = document.createElementNS(svgNS, 'text');
      title.setAttribute('x', x0 + panelW / 2); title.setAttribute('y', padT + plotH + 32);
      title.setAttribute('text-anchor', 'middle');
      title.setAttribute('fill', 'currentColor'); title.setAttribute('fill-opacity', '0.62');
      title.setAttribute('font-size', '11.5');
      title.setAttribute('font-family', 'system-ui, "Microsoft YaHei", sans-serif');
      title.textContent = '迭代次数';
      g.appendChild(title);
      const t2 = document.createElementNS(svgNS, 'text');
      t2.setAttribute('x', x0 + 4); t2.setAttribute('y', padT - 4);
      t2.setAttribute('fill', 'currentColor'); t2.setAttribute('fill-opacity', '0.62');
      t2.setAttribute('font-size', '11.5');
      t2.setAttribute('font-family', 'system-ui, "Microsoft YaHei", sans-serif');
      t2.textContent = yTitle;
      g.appendChild(t2);

      // 曲线
      seriesList.forEach((s) => {
        const pts = [];
        for (let i = 0; i < s.iters.length; i++) {
          const v = valueOf(s, i);
          if (!Number.isFinite(v)) continue;
          pts.push([xPos(s.iters[i]), yPos(v)]);
        }
        if (!pts.length) return;
        const path = document.createElementNS(svgNS, 'path');
        path.setAttribute('d', pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(2) + ' ' + p[1].toFixed(2)).join(' '));
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke', s.color);
        path.setAttribute('stroke-width', '2');
        path.setAttribute('stroke-linecap', 'round');
        path.setAttribute('stroke-linejoin', 'round');
        path.setAttribute('stroke-opacity', '0.95');
        g.appendChild(path);
        pts.forEach((p, i) => {
          const c = document.createElementNS(svgNS, 'circle');
          c.setAttribute('cx', p[0]); c.setAttribute('cy', p[1]);
          c.setAttribute('r', '2.6');
          c.setAttribute('fill', s.color);
          c.setAttribute('stroke', '#ffffff'); c.setAttribute('stroke-width', '1.1');
          c.setAttribute('stroke-opacity', '0.85');
          c.__point = { s: s, i: i };
          g.appendChild(c);
        });
      });
    }

    // 纵轴与悬浮读数一律写死 ℃，**不跟随当前温标** —— 与桌面版一致
    // （main.py 的 plt.ylabel('温度估计值 (°C)') 也是写死的）。
    // 曾经这里写成 state.tempUnit：曲线数据来自 core.js 的 _solve_wetbulb，恒为 ℃，
    // 于是切到 ℉ 后出现"轴标题说 ℉、刻度数字是 ℃、悬浮读数又按 ℉ 换算"的三处自相矛盾。
    // 初值策略（Tw=Td / Tw=T-n）本来就只影响迭代路径，这张图是内部收敛过程，不是面向用户的温度读数。
    panel(padL, series, (s, i) => s.temps[i], '温度估计值 (℃)', false);
    panel(padL + panelW + gap, series, (s, i) => s.residuals[i],
      '残差（' + ($('chart-log').checked ? '对数' : '线性') + '）', $('chart-log').checked);

    // 悬浮读数
    const showTip = (evt) => {
      const rect = host.getBoundingClientRect();
      const px = evt.clientX - rect.left, py = evt.clientY - rect.top;
      let best = null, bestD = 22;
      svg.querySelectorAll('circle').forEach((c) => {
        const dx = Number(c.getAttribute('cx')) - px, dy = Number(c.getAttribute('cy')) - py;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d < bestD) { bestD = d; best = c.__point; }
      });
      if (!best) { tip.classList.remove('show'); return; }
      const s = best.s, i = best.i;
      tip.innerHTML = '<b>' + s.method + '</b><br>迭代 ' + s.iters[i]
        + '<br>T_w = ' + C.pyFixed(s.temps[i], 4) + '℃'
        + '<br>|f| = ' + s.residuals[i].toExponential(3);
      // 提示框与图表在同一张卡片里（.glass 是定位祖先），所以要用 host 在卡片内的偏移
      tip.style.left = (host.offsetLeft + px) + 'px';
      tip.style.top = (host.offsetTop + py) + 'px';
      tip.classList.add('show');
    };
    svg.addEventListener('mousemove', showTip);
    svg.addEventListener('mouseleave', () => tip.classList.remove('show'));

    host.innerHTML = '';
    host.appendChild(svg);

    // 图例（可点击隐藏）
    const legend = $('chart-legend');
    legend.innerHTML = '';
    Object.keys(state.iterations || {}).forEach((method) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'legend-item';
      item.setAttribute('aria-pressed', String(!chartState.hidden.has(method)));
      item.style.color = methodColor(method);
      item.innerHTML = '<span class="legend-swatch"></span>';
      const label = document.createElement('span');
      label.style.color = 'var(--ink-2)';
      label.textContent = method;
      item.appendChild(label);
      item.addEventListener('click', () => {
        if (chartState.hidden.has(method)) chartState.hidden.delete(method);
        else chartState.hidden.add(method);
        drawChart();
      });
      legend.appendChild(item);
    });
  }

  /* ==================== 14. 结果导出（JSON / CSV / 分享链接） ==================== */

  const MODE_CLI_NAME = { 0: 'dewpoint', 1: 'wetbulb', 2: 'rh' };

  function jsonPayload() {
    // 结构对齐 cli.py 的输出：{version, mode, results}，再补上网页版自己的上下文
    return {
      version: C.WEB_TAG,
      exe_version: C.EXE_TAG,
      core: 'src/core.py ' + C.EXE_TAG,
      mode: MODE_CLI_NAME[state.mode],
      mode_cn: MODES[state.mode].name,
      units: { temperature: state.tempUnit, pressure: state.pressureUnit },
      precision: state.precision,
      iteration: { tolerance: tol(), initial_guess: state.strategy === 'Tn' ? 'Tw=T-n' : 'Tw=Td' },
      inputs: state.solved ? {
        dry_bulb_C: state.solved.T,
        other: state.solved.other,
        pressure_hPa: state.solved.P,
      } : null,
      results: state.results.map((r) => ({
        method: r.method, result1: r.result1, result2: r.result2, rh: r.rh,
      })),
    };
  }

  function exportJson() {
    if (!state.results.length) { toast('error', '还没有结果可以导出，先点「计算」。'); return; }
    downloadText(JSON.stringify(jsonPayload(), null, 2),
      'wetbulb-' + MODE_CLI_NAME[state.mode] + '-' + stamp() + '.json', 'application/json');
    toast('success', '已导出 JSON（结构与桌面版命令行接口一致）');
  }

  function exportCsv() {
    if (!state.results.length) { toast('error', '还没有结果可以导出，先点「计算」。'); return; }
    const info = MODES[state.mode];
    const head = ['公式', '族', '注册域/℃', info.r1 + '(' + state.tempUnit + ')'];
    if (state.mode === 2) head.push(info.r2 + '(' + state.tempUnit + ')');
    else head.push('相对湿度(%)');
    head.push('状态');
    const rows = [head];
    state.results.forEach((r) => {
      const f = C.get_formula(r.method);
      const st = statusOf(r, state.mode);
      const line = [r.method, f ? f.family : '', f ? f.tmin + '~' + f.tmax : ''];
      line.push(isNum(r.result1) ? C.pyFixed(fromCelsius(r.result1), 4) : String(r.result1));
      if (state.mode === 2) line.push(isNum(r.result2) ? C.pyFixed(fromCelsius(r.result2), 4) : String(r.result2));
      else line.push(isNum(r.rh) ? C.pyFixed(r.rh * 100, 2) : '');
      line.push(st.text);
      rows.push(line);
    });
    const csv = '\uFEFF' + rows.map((r) => r.map(csvCell).join(',')).join('\r\n');
    downloadText(csv, 'wetbulb-' + MODE_CLI_NAME[state.mode] + '-' + stamp() + '.csv', 'text/csv');
    toast('success', '已导出 CSV');
  }

  function csvCell(v) {
    const s = String(v === null || v === undefined ? '' : v);
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  function shareLink() {
    const p = new URLSearchParams();
    p.set('m', String(state.mode));
    p.set('t', $('in-dry').value.trim());
    p.set('o', $('in-other').value.trim());
    p.set('p', $('in-pressure').value.trim());
    p.set('tu', state.tempUnit);
    p.set('pu', state.pressureUnit);
    p.set('tol', String(state.precision));
    p.set('st', state.strategy);
    p.set('ac', state.accent);
    const url = location.origin + location.pathname + location.search + '#calc?' + p.toString();

    // 复制按"能成功"的顺序试三种办法：
    //   1) 临时 textarea + execCommand —— **同步**执行，保留着用户手势，file:// 下也能用；
    //   2) Clipboard API —— 现代浏览器，但要求安全上下文与权限；
    //   3) 都不行就把链接弹出来让用户自己复制（本地打开一个 html 时确实可能两种都被拒）。
    try {
      const ta = document.createElement('textarea');
      ta.value = url;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.top = '-1000px';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand && document.execCommand('copy');
      ta.remove();
      if (ok) {
        toast('success', '分享链接已复制到剪贴板（打开后会自动填好并算出结果）');
        return;
      }
    } catch (e) { /* 换下一种办法 */ }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(
        () => toast('success', '分享链接已复制到剪贴板（打开后会自动填好并算出结果）'),
        () => window.prompt('复制这个链接：', url));
      return;
    }
    window.prompt('复制这个链接：', url);
  }

  function readUrlParams() {
    const h = location.hash || '';
    if (h.indexOf('#calc?') !== 0) return false;
    const p = new URLSearchParams(h.slice(6));
    const t = p.get('t'), o = p.get('o'), pr = p.get('p');
    if (t !== null) state.inputs.t = t;
    if (o !== null) state.inputs.other = o;
    if (pr !== null) state.inputs.p = pr;
    if (p.get('m') !== null) state.mode = Number(p.get('m')) || 0;
    if (p.get('tu')) state.tempUnit = p.get('tu');
    if (p.get('pu')) state.pressureUnit = p.get('pu');
    if (p.get('tol')) state.precision = Math.min(10, Math.max(2, Number(p.get('tol')) || 7));
    if (p.get('st')) state.strategy = p.get('st') === 'Tn' ? 'Tn' : 'Td';
    if (p.get('ac')) applyAccent(p.get('ac'));
    return true;
  }

  /* ==================== 15. 结果卡片 PNG（替代桌面版的"截屏"） ==================== */

  function drawResultCard() {
    if (!state.results.length) { toast('error', '还没有结果，先点「计算」再导出卡片。'); return; }
    const scale = 2;
    const W = 1180;
    const info = MODES[state.mode];
    const rows = state.results;
    const derived = derivedRowsForCard();
    const headH = 176;
    const tableTop = headH + 34;
    const rowH = 30;
    const tableH = rowH * (rows.length + 1) + 16;
    const derivedTop = tableTop + tableH + 30;
    const derivedRowH = 26;
    const derivedCols = derived.length ? 3 : 0;
    const derivedRowsCount = derived.length ? Math.ceil(derived[0].items.length / derivedCols) : 0;
    const derivedH = derived.length ? derived.length * (30 + derivedRowsCount * derivedRowH) + 10 : 0;
    const H = derivedTop + derivedH + 92;

    const cv = document.createElement('canvas');
    cv.width = W * scale;
    cv.height = H * scale;
    const ctx = cv.getContext('2d');
    ctx.scale(scale, scale);
    const accent = state.accent.split(',').map((x) => parseInt(x.trim(), 10));
    const acc = 'rgb(' + accent.join(',') + ')';
    const accLight = 'rgba(' + accent.join(',') + ',0.12)';

    // 背景
    const g = ctx.createLinearGradient(0, 0, W, H);
    g.addColorStop(0, '#f4f9fa'); g.addColorStop(1, '#e6eff2');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = acc;
    ctx.fillRect(0, 0, W, 8);

    ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = acc;
    ctx.font = '700 30px "Microsoft YaHei", system-ui, sans-serif';
    ctx.fillText('湿球计算器 · 结果卡片', 48, 70);
    ctx.fillStyle = '#5d7a82';
    ctx.font = '500 15px "Microsoft YaHei", system-ui, sans-serif';
    ctx.fillText('WetBulb Calculator · 网页版 ' + C.WEB_TAG + '（数值内核对应桌面版 ' + C.EXE_TAG + '）', 48, 96);

    // 输入摘要
    const s = state.solved || {};
    const chips = [
      '模式：' + info.name,
      '干球 ' + C.pyFixed(fromCelsius(s.T), 4) + state.tempUnit,
      info.other + ' ' + (state.mode === 2 ? C.pyFixed(s.other, 2) + '%' : C.pyFixed(fromCelsius(s.other), 4) + state.tempUnit),
      '压强 ' + C.pyFixed(fromHpa(s.P), 2) + state.pressureUnit,
      '容差 1e-' + state.precision,
      '初值 ' + (state.strategy === 'Tn' ? 'Tw=T-n' : 'Tw=Td'),
    ];
    let cx = 48;
    ctx.font = '600 14px "Microsoft YaHei", system-ui, sans-serif';
    chips.forEach((c) => {
      const w = ctx.measureText(c).width + 26;
      ctx.fillStyle = accLight;
      roundRect(ctx, cx, 118, w, 32, 16);
      ctx.fill();
      ctx.strokeStyle = 'rgba(' + accent.join(',') + ',0.34)';
      ctx.lineWidth = 1;
      roundRect(ctx, cx, 118, w, 32, 16);
      ctx.stroke();
      ctx.fillStyle = '#26454c';
      ctx.fillText(c, cx + 13, 139);
      cx += w + 10;
    });
    ctx.fillStyle = '#8ba3a9';
    ctx.font = '500 12.5px ui-monospace, Consolas, monospace';
    ctx.fillText(new Date().toLocaleString('zh-CN'), W - 48 - ctx.measureText(new Date().toLocaleString('zh-CN')).width, 139);

    // 结果表
    ctx.fillStyle = '#35525a';
    ctx.font = '700 15px "Microsoft YaHei", system-ui, sans-serif';
    ctx.fillText('逐公式结果（' + rows.length + ' 条）', 48, tableTop - 12);
    const cols = state.mode === 2
      ? [{ t: '公式', w: 190 }, { t: '适用域/℃', w: 110 }, { t: info.r1 + '/' + state.tempUnit, w: 180 },
         { t: info.r2 + '/' + state.tempUnit, w: 180 }, { t: '状态', w: 0 }]
      : [{ t: '公式', w: 190 }, { t: '适用域/℃', w: 110 }, { t: info.r1 + '/' + state.tempUnit, w: 180 },
         { t: '相对湿度', w: 180 }, { t: '状态', w: 0 }];
    drawTable(ctx, 48, tableTop, W - 96, cols, rows, rowH, acc, accent);

    // 派生量
    if (derived.length) {
      ctx.fillStyle = '#35525a';
      ctx.font = '700 15px "Microsoft YaHei", system-ui, sans-serif';
      ctx.fillText('常用气象参数（' + state.selected + '）', 48, derivedTop - 10);
      let y = derivedTop + 10;
      const colW = (W - 96) / 3;
      derived.forEach((grp) => {
        ctx.fillStyle = acc;
        ctx.font = '700 13px "Microsoft YaHei", system-ui, sans-serif';
        ctx.fillText(grp.g, 48, y + 12);
        y += 26;
        grp.items.forEach((it, i) => {
          const col = i % 3, row = Math.floor(i / 3);
          const x = 48 + col * colW;
          const yy = y + row * derivedRowH;
          ctx.fillStyle = '#5d7a82';
          ctx.font = '500 12.5px "Microsoft YaHei", system-ui, sans-serif';
          ctx.fillText(it.label, x, yy + 12);
          ctx.fillStyle = '#10262b';
          ctx.font = '700 13px ui-monospace, Consolas, monospace';
          const val = it.value + (it.unit && it.unit !== '—' ? ' ' + it.unit : '');
          ctx.fillText(val, x + colW - 20 - ctx.measureText(val).width, yy + 12);
        });
        y += Math.ceil(grp.items.length / 3) * derivedRowH + 6;
      });
    }

    // 页脚
    const fy = H - 34;
    ctx.fillStyle = '#8ba3a9';
    ctx.font = '500 12px "Microsoft YaHei", system-ui, sans-serif';
    ctx.fillText('由「湿球计算器 网页版 ' + C.WEB_TAG + '」生成 · 数值内核移植自 src/core.py ' + C.EXE_TAG
      + ' 并与桌面版逐点对拍 · ' + REPO_URL, 48, fy);
    ctx.fillText('科学计算结果应结合适用范围与独立验证使用（MIT License）', 48, fy + 18);

    cv.toBlob((blob) => {
      download(blob, 'wetbulb-card-' + stamp() + '.png');
      toast('success', '结果卡片已保存为 PNG');
    }, 'image/png');
  }

  function derivedRowsForCard() {
    if (!state.selected) return [];
    const row = state.results.find((r) => r.method === state.selected);
    if (!row) return [];
    const s = state.solved;
    let Td, Tw, rh;
    if (state.mode === 0) { Td = s.other; Tw = row.result1; rh = row.rh; }
    else if (state.mode === 1) { Tw = s.other; Td = row.result1; rh = row.rh; }
    else { Td = row.result1; Tw = row.result2; rh = (row.rh === null || row.rh === undefined) ? s.other / 100 : row.rh; }
    if (!isNum(row.result1) || rh === null || rh === undefined) return [];
    if (state.mode === 2 && !isNum(row.result2)) return [];
    let d;
    try { d = C.derive_moist_air(s.T, Tw, Td, rh, s.P, row.method); } catch (e) { return []; }
    d.rh = rh;
    const groups = [];
    derivedSpec().forEach((spec) => {
      let g = groups.find((x) => x.g === spec.g);
      if (!g) { g = { g: spec.g, items: [] }; groups.push(g); }
      const txt = spec.f(d[spec.k]);
      g.items.push({ label: spec.label, value: (txt === null || txt === 'nan') ? '—' : txt, unit: spec.unit });
    });
    return groups;
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function drawTable(ctx, x, y, w, cols, rows, rowH, acc, accent) {
    const total = cols.reduce((a, c) => a + c.w, 0);
    cols[cols.length - 1].w = Math.max(70, w - total);
    // 表头
    ctx.fillStyle = 'rgba(' + accent.join(',') + ',0.10)';
    roundRect(ctx, x, y, w, rowH + 6, 10);
    ctx.fill();
    ctx.fillStyle = '#35525a';
    ctx.font = '700 12.5px "Microsoft YaHei", system-ui, sans-serif';
    let cx = x + 12;
    cols.forEach((c) => { ctx.fillText(c.t, cx, y + 20); cx += c.w; });
    let ry = y + rowH + 6;
    rows.forEach((r, i) => {
      if (i % 2 === 1) { ctx.fillStyle = 'rgba(0,0,0,0.035)'; ctx.fillRect(x, ry, w, rowH - 2); }
      const st = statusOf(r, state.mode);
      const f = C.get_formula(r.method);
      ctx.font = '650 12.5px "Microsoft YaHei", system-ui, sans-serif';
      ctx.fillStyle = '#10262b';
      let cxx = x + 12;
      ctx.fillText(r.method, cxx, ry + 20); cxx += cols[0].w;
      ctx.font = '500 11.5px ui-monospace, Consolas, monospace';
      ctx.fillStyle = '#8ba3a9';
      ctx.fillText(f ? f.tmin + '~' + f.tmax : '—', cxx, ry + 20); cxx += cols[1].w;
      ctx.font = '700 12.5px ui-monospace, Consolas, monospace';
      ctx.fillStyle = '#10262b';
      const v1 = isNum(r.result1) ? C.pyFixed(fromCelsius(r.result1), 4) + state.tempUnit : String(r.result1).slice(0, 22);
      ctx.fillText(v1, cxx, ry + 20); cxx += cols[2].w;
      if (state.mode === 2) {
        const v2 = isNum(r.result2) ? C.pyFixed(fromCelsius(r.result2), 4) + state.tempUnit : String(r.result2).slice(0, 22);
        ctx.fillText(v2, cxx, ry + 20); cxx += cols[3].w;
      } else {
        const v2 = isNum(r.rh) ? C.pyFixed(r.rh * 100, 2) + '%' : '—';
        ctx.fillText(v2, cxx, ry + 20); cxx += cols[3].w;
      }
      const colorMap = { ok: '#168a60', na: '#8ba3a9', warn: '#be7614', bad: '#be3a3a' };
      ctx.fillStyle = colorMap[st.kind];
      ctx.font = '700 12px "Microsoft YaHei", system-ui, sans-serif';
      ctx.fillText(st.text.slice(0, 16), cxx, ry + 20);
      ctx.strokeStyle = 'rgba(0,0,0,0.06)';
      ctx.beginPath(); ctx.moveTo(x, ry + rowH - 2); ctx.lineTo(x + w, ry + rowH - 2); ctx.stroke();
      ry += rowH;
    });
  }

  /* ==================== 16. 图表 PNG 导出 ==================== */

  function exportChartPng() {
    const host = $('chart-host');
    const svg = host.querySelector('svg');
    if (!svg) { toast('error', '先计算，等图上出现曲线再导出。'); return; }
    // 内联当前主题的文本颜色，保证导出的 SVG 单独打开也正常
    const clone = svg.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('color', state.theme === 'dark' ? '#eaf5f7' : '#35525a');
    const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bg.setAttribute('x', 0); bg.setAttribute('y', 0);
    bg.setAttribute('width', clone.getAttribute('width'));
    bg.setAttribute('height', clone.getAttribute('height'));
    bg.setAttribute('fill', state.theme === 'dark' ? '#0d1f24' : '#f7fbfc');
    clone.insertBefore(bg, clone.firstChild);
    const xml = new XMLSerializer().serializeToString(clone);
    const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml);
    const img = new Image();
    img.onload = () => {
      const scale = 2;
      const cv = document.createElement('canvas');
      cv.width = img.width * scale;
      cv.height = img.height * scale;
      const ctx = cv.getContext('2d');
      ctx.scale(scale, scale);
      ctx.drawImage(img, 0, 0);
      cv.toBlob((blob) => {
        download(blob, 'wetbulb-iterations-' + stamp() + '.png');
        toast('success', '迭代图已保存为 PNG');
      }, 'image/png');
    };
    img.onerror = () => toast('error', '这张图导出失败，可以直接对页面截图。');
    img.src = url;
  }

  /* ==================== 17. 批量计算（CSV / XLSX） ==================== */

  function parseCSV(text) {
    text = text.replace(/^\uFEFF/, '');
    const rows = [];
    let row = [], field = '', inQ = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (inQ) {
        if (ch === '"') {
          if (text[i + 1] === '"') { field += '"'; i++; } else inQ = false;
        } else field += ch;
      } else if (ch === '"') inQ = true;
      else if (ch === ',') { row.push(field); field = ''; }
      else if (ch === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
      else if (ch !== '\r') field += ch;
    }
    if (field !== '' || row.length) { row.push(field); rows.push(row); }
    return rows.filter((r) => r.some((c) => String(c).trim() !== ''));
  }

  async function inflateRaw(bytes) {
    if (typeof DecompressionStream === 'undefined') {
      throw new Error('这个浏览器不支持解压 xlsx（缺少 DecompressionStream）。请把表格另存为 CSV 再导入。');
    }
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }

  /** 极简 ZIP 读取：只够读 xlsx（中央目录 + 存储/Deflate 两种方式）。 */
  async function unzip(buf) {
    const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
    let eocd = -1;
    for (let i = buf.length - 22; i >= Math.max(0, buf.length - 66000); i--) {
      if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('不是有效的 xlsx（找不到 ZIP 结尾记录）');
    const count = dv.getUint16(eocd + 10, true);
    let off = dv.getUint32(eocd + 16, true);
    const out = {};
    const td = new TextDecoder('utf-8');
    for (let i = 0; i < count; i++) {
      if (dv.getUint32(off, true) !== 0x02014b50) throw new Error('ZIP 中央目录损坏');
      const method = dv.getUint16(off + 10, true);
      const compSize = dv.getUint32(off + 20, true);
      const nameLen = dv.getUint16(off + 28, true);
      const extraLen = dv.getUint16(off + 30, true);
      const commentLen = dv.getUint16(off + 32, true);
      const localOff = dv.getUint32(off + 42, true);
      const name = td.decode(buf.subarray(off + 46, off + 46 + nameLen));
      const lnameLen = dv.getUint16(localOff + 26, true);
      const lextraLen = dv.getUint16(localOff + 28, true);
      const dataStart = localOff + 30 + lnameLen + lextraLen;
      const raw = buf.subarray(dataStart, dataStart + compSize);
      out[name] = (method === 0) ? raw : (method === 8 ? await inflateRaw(raw)
        : (() => { throw new Error('不支持的 ZIP 压缩方式：' + method); })());
      off += 46 + nameLen + extraLen + commentLen;
    }
    return out;
  }

  function colToIndex(letters) {
    let n = 0;
    for (let i = 0; i < letters.length; i++) n = n * 26 + (letters.charCodeAt(i) - 64);
    return n - 1;
  }

  function parseSheetXml(xml, shared) {
    const doc = new DOMParser().parseFromString(xml, 'application/xml');
    if (doc.getElementsByTagName('parsererror').length) throw new Error('工作表 XML 解析失败');
    const rows = [];
    const rowEls = doc.getElementsByTagName('row');
    for (let r = 0; r < rowEls.length; r++) {
      const cells = [];
      const cEls = rowEls[r].getElementsByTagName('c');
      for (let k = 0; k < cEls.length; k++) {
        const c = cEls[k];
        const ref = c.getAttribute('r') || '';
        const idx = ref ? colToIndex(ref.replace(/[0-9]/g, '')) : cells.length;
        const t = c.getAttribute('t');
        let val = null;
        if (t === 'inlineStr') {
          const ts = c.getElementsByTagName('t');
          let s = '';
          for (let q = 0; q < ts.length; q++) s += ts[q].textContent;
          val = s;
        } else {
          const vEl = c.getElementsByTagName('v')[0];
          if (vEl) {
            const raw = vEl.textContent;
            if (t === 's') { const si = parseInt(raw, 10); val = shared && shared[si] !== undefined ? shared[si] : ''; }
            else if (t === 'str') val = raw;
            else if (t === 'b') val = raw === '1';
            else { const n = Number(raw); val = Number.isNaN(n) ? raw : n; }
          }
        }
        cells[idx] = val;
      }
      rows.push(cells);
    }
    return rows;
  }

  async function readXlsx(file) {
    const buf = new Uint8Array(await file.arrayBuffer());
    const entries = await unzip(buf);
    const td = new TextDecoder('utf-8');
    let shared = null;
    if (entries['xl/sharedStrings.xml']) {
      const doc = new DOMParser().parseFromString(td.decode(entries['xl/sharedStrings.xml']), 'application/xml');
      const sis = doc.getElementsByTagName('si');
      shared = [];
      for (let i = 0; i < sis.length; i++) {
        const ts = sis[i].getElementsByTagName('t');
        let s = '';
        for (let q = 0; q < ts.length; q++) s += ts[q].textContent;
        shared.push(s);
      }
    }
    const sheetNames = Object.keys(entries)
      .filter((n) => /^xl\/worksheets\/sheet\d+\.xml$/.test(n))
      .sort((a, b) => parseInt(a.match(/(\d+)/)[1], 10) - parseInt(b.match(/(\d+)/)[1], 10));
    if (!sheetNames.length) throw new Error('xlsx 里找不到工作表');
    return parseSheetXml(td.decode(entries[sheetNames[0]]), shared);
  }

  function toFloatCell(v) {
    if (typeof v === 'number') return v;
    if (typeof v === 'boolean') throw new Error("float() argument must be a string or a real number, not 'bool'");
    if (v === undefined || v === null) throw new Error("float() argument must be a string or a real number, not 'NoneType'");
    // 空串与文本走同一条路：消息格式与 Python 的 float('') / float('abc') 一致，
    // 因为这句话会原样写进导出文件的「错误」列。
    const p = pyFloatParse(v);
    if (!p.ok || Number.isNaN(p.value)) throw new Error("could not convert string to float: '" + String(v) + "'");
    if (!Number.isFinite(p.value)) throw new Error('运算溢出');
    return p.value;
  }

  async function runBatch(rows, fileName) {
    const headers = (rows[0] || []).map((h) => String(h === null || h === undefined ? '' : h).trim());
    if (!['A', 'B', 'C'].every((n) => headers.indexOf(n) >= 0)) {
      toast('error', '表格必须包含 A、B、C 三列表头（与桌面版批量计算的约定一致）。');
      return;
    }
    const colA = headers.indexOf('A'), colB = headers.indexOf('B'), colC = headers.indexOf('C');
    const mode = state.mode;
    const dataRows = rows.slice(1);
    const out = [];
    let ok = 0, bad = 0;

    $('batch-progress-wrap').classList.remove('hidden');
    $('batch-stats').classList.remove('hidden');
    $('batch-actions').classList.remove('hidden');
    $('batch-scroll').classList.remove('hidden');

    for (let r = 0; r < dataRows.length; r++) {
      const raw = dataRows[r];
      let results = null, error = null;
      try {
        const t = toCelsius(toFloatCell(raw[colA]));
        const p = toHpa(toFloatCell(raw[colC]));
        const value = mode === 2 ? toFloatCell(raw[colB]) : toCelsius(toFloatCell(raw[colB]));
        let rowsOut;
        if (mode === 0) rowsOut = C.calculate_wetbulb(value, t, value, p);
        else if (mode === 1) rowsOut = C.calculate_dewpoint(t, value, p);
        else rowsOut = C.calculate_both(t, t, value, p);
        const method = t >= 0 ? 'Goff-水面' : 'Goff-冰面';
        const hit = rowsOut.find((x) => x.method === method);
        const values = mode === 2 ? [hit.result1, hit.result2] : [hit.result1];
        for (const v of values) {
          if (typeof v !== 'number' || !Number.isFinite(v)) throw new Error(values.map((x) => String(x)).join(' / '));
        }
        results = values;
        ok++;
      } catch (ex) {
        error = ex && ex.message ? ex.message : String(ex);
        bad++;
      }
      out.push({ raw: [raw[colA], raw[colB], raw[colC]], results: results, error: error });
      if (r % 40 === 0 || r === dataRows.length - 1) {
        const pct = dataRows.length ? ((r + 1) / dataRows.length) * 100 : 100;
        $('batch-progress').style.width = pct.toFixed(1) + '%';
        $('batch-progress-text').textContent = '已处理 ' + (r + 1) + ' / ' + dataRows.length + ' 行';
        await new Promise((res) => setTimeout(res, 0));
      }
    }

    state.batch = { name: fileName, headers: headers, rows: out, mode: mode };
    $('stat-total').textContent = String(dataRows.length);
    $('stat-ok').textContent = String(ok);
    $('stat-bad').textContent = String(bad);
    $('batch-filename').textContent = '导出文件名：result_' + fileName.replace(/\.[^.]+$/, '') + '.{csv,xlsx}';
    renderBatchPreview();
    setTimeout(() => $('batch-progress-wrap').classList.add('hidden'), 700);
    toast('success', '批量计算完成：' + dataRows.length + ' 行，成功 ' + ok + ' 行，非法 ' + bad + ' 行');
  }

  function batchLabels() {
    const tu = state.tempUnit, pu = state.pressureUnit, mode = state.mode;
    const resultNames = mode === 0 ? ['湿球'] : mode === 1 ? ['露点'] : ['露点', '湿球'];
    return {
      inputs: ['干球' + tu, (mode === 2 ? '相对湿度%' : (mode === 0 ? '露点' : '湿球') + tu), '大气' + pu],
      results: resultNames.map((n) => n + tu),
      error: '错误',
    };
  }

  function batchOutputTable() {
    const b = state.batch;
    if (!b) return null;
    const L = batchLabels();
    const head = L.inputs.concat(L.results).concat([L.error]);
    const rows = b.rows.map((r) => {
      const line = r.raw.slice();
      if (r.error) {
        L.results.forEach(() => line.push('#VALUE!'));
        line.push(r.error);
      } else {
        r.results.forEach((v) => line.push(C.pyFixed(fromCelsius(v), 4)));
        line.push('');
      }
      return line;
    });
    return { head: head, rows: rows };
  }

  function renderBatchPreview() {
    const b = state.batch;
    const L = batchLabels();
    const head = $('batch-head'), body = $('batch-body');
    head.innerHTML = ''; body.innerHTML = '';
    if (!b) return;
    L.inputs.forEach((t) => { const th = document.createElement('th'); th.textContent = t; head.appendChild(th); });
    L.results.forEach((t) => { const th = document.createElement('th'); th.textContent = t; head.appendChild(th); });
    const thErr = document.createElement('th'); thErr.textContent = L.error; head.appendChild(thErr);

    b.rows.slice(0, 500).forEach((r) => {
      const tr = document.createElement('tr');
      if (r.error) tr.className = 'err';
      r.raw.forEach((v) => {
        const td = document.createElement('td');
        td.className = 'num';
        td.textContent = v === undefined || v === null ? '' : String(v);
        tr.appendChild(td);
      });
      if (r.error) {
        L.results.forEach(() => {
          const td = document.createElement('td');
          td.className = 'num'; td.textContent = '#VALUE!';
          tr.appendChild(td);
        });
      } else {
        r.results.forEach((v) => {
          const td = document.createElement('td');
          td.className = 'num'; td.textContent = C.pyFixed(fromCelsius(v), 4);
          tr.appendChild(td);
        });
      }
      const tdErr = document.createElement('td');
      tdErr.textContent = r.error || '';
      tr.appendChild(tdErr);
      body.appendChild(tr);
    });
    if (b.rows.length > 500) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 3 + L.results.length + 1;
      td.className = 'dim';
      td.textContent = '（预览只显示前 500 行，导出文件包含全部 ' + b.rows.length + ' 行）';
      tr.appendChild(td);
      body.appendChild(tr);
    }
  }

  function exportBatchCsv() {
    const t = batchOutputTable();
    if (!t) { toast('error', '还没有批量结果，先导入一个 CSV / XLSX。'); return; }
    const csv = '\uFEFF' + [t.head].concat(t.rows).map((r) => r.map(csvCell).join(',')).join('\r\n');
    downloadText(csv, 'result_' + state.batch.name.replace(/\.[^.]+$/, '') + '.csv', 'text/csv');
    toast('success', '已导出 result_' + state.batch.name.replace(/\.[^.]+$/, '') + '.csv');
  }

  function crc32(bytes) {
    let c, table = crc32.table;
    if (!table) {
      table = crc32.table = new Uint32Array(256);
      for (let n = 0; n < 256; n++) {
        c = n;
        for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
        table[n] = c >>> 0;
      }
    }
    let crc = 0xFFFFFFFF;
    for (let i = 0; i < bytes.length; i++) crc = table[(crc ^ bytes[i]) & 0xFF] ^ (crc >>> 8);
    return (crc ^ 0xFFFFFFFF) >>> 0;
  }

  /** 极简 ZIP 打包：全部用"存储"方式（method 0），Excel 能正常打开。 */
  function zip(files) {
    const enc = new TextEncoder();
    const parts = [], central = [];
    let offset = 0;
    files.forEach((f) => {
      const name = enc.encode(f.name);
      const data = typeof f.data === 'string' ? enc.encode(f.data) : f.data;
      const crc = crc32(data);
      const local = new Uint8Array(30 + name.length);
      const dv = new DataView(local.buffer);
      dv.setUint32(0, 0x04034b50, true);
      dv.setUint16(4, 20, true);
      dv.setUint16(6, 0x0800, true);            // 文件名按 UTF-8
      dv.setUint16(8, 0, true);                 // 存储
      dv.setUint16(10, 0, true); dv.setUint16(12, 0, true);
      dv.setUint32(14, crc, true);
      dv.setUint32(18, data.length, true);
      dv.setUint32(22, data.length, true);
      dv.setUint16(26, name.length, true);
      dv.setUint16(28, 0, true);
      local.set(name, 30);
      parts.push(local, data);

      const cd = new Uint8Array(46 + name.length);
      const cdv = new DataView(cd.buffer);
      cdv.setUint32(0, 0x02014b50, true);
      cdv.setUint16(4, 20, true); cdv.setUint16(6, 20, true);
      cdv.setUint16(8, 0x0800, true);
      cdv.setUint16(10, 0, true);
      cdv.setUint16(12, 0, true); cdv.setUint16(14, 0, true);
      cdv.setUint32(16, crc, true);
      cdv.setUint32(20, data.length, true);
      cdv.setUint32(24, data.length, true);
      cdv.setUint16(28, name.length, true);
      cdv.setUint32(42, offset, true);
      cd.set(name, 46);
      central.push(cd);
      offset += local.length + data.length;
    });
    const cdSize = central.reduce((a, b) => a + b.length, 0);
    const end = new Uint8Array(22);
    const edv = new DataView(end.buffer);
    edv.setUint32(0, 0x06054b50, true);
    edv.setUint16(8, files.length, true);
    edv.setUint16(10, files.length, true);
    edv.setUint32(12, cdSize, true);
    edv.setUint32(16, offset, true);
    const all = parts.concat(central, [end]);
    const total = all.reduce((a, b) => a + b.length, 0);
    const out = new Uint8Array(total);
    let pos = 0;
    all.forEach((b) => { out.set(b, pos); pos += b.length; });
    return out;
  }

  function xmlEsc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&apos;');
  }

  function colName(i) {
    let s = '';
    i += 1;
    while (i > 0) { const m = (i - 1) % 26; s = String.fromCharCode(65 + m) + s; i = Math.floor((i - 1) / 26); }
    return s;
  }

  function exportBatchXlsx() {
    const t = batchOutputTable();
    if (!t) { toast('error', '还没有批量结果，先导入一个 CSV / XLSX。'); return; }
    const rows = [t.head].concat(t.rows);
    const sheetRows = rows.map((row, r) => {
      const cells = row.map((v, c) => {
        const ref = colName(c) + (r + 1);
        const num = (typeof v === 'number') ? v : (String(v).trim() !== '' && /^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(String(v).trim()) ? Number(String(v).trim()) : null);
        if (num !== null && String(v).trim() !== '' && !/#VALUE!/.test(String(v))) {
          return '<c r="' + ref + '"><v>' + num + '</v></c>';
        }
        if (String(v) === '') return '';
        return '<c r="' + ref + '" t="inlineStr"><is><t xml:space="preserve">' + xmlEsc(v) + '</t></is></c>';
      }).join('');
      return '<row r="' + (r + 1) + '">' + cells + '</row>';
    }).join('');

    const files = [
      {
        name: '[Content_Types].xml', data:
          '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
          '<Default Extension="xml" ContentType="application/xml"/>' +
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
          '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' +
          '</Types>'
      },
      {
        name: '_rels/.rels', data:
          '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
          '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>' +
          '</Relationships>'
      },
      {
        name: 'xl/workbook.xml', data:
          '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ' +
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
          '<sheets><sheet name="结果" sheetId="1" r:id="rId1"/></sheets></workbook>'
      },
      {
        name: 'xl/_rels/workbook.xml.rels', data:
          '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
          '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>' +
          '</Relationships>'
      },
      {
        name: 'xl/worksheets/sheet1.xml', data:
          '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
          '<sheetData>' + sheetRows + '</sheetData></worksheet>'
      },
    ];
    const bytes = zip(files);
    download(new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }),
      'result_' + state.batch.name.replace(/\.[^.]+$/, '') + '.xlsx');
    toast('success', '已导出 xlsx（与桌面版的 result_ 命名一致）');
  }

  async function handleFile(file) {
    if (!file) return;
    try {
      const lower = file.name.toLowerCase();
      let rows;
      if (lower.endsWith('.csv')) {
        rows = parseCSV(await file.text());
      } else if (lower.endsWith('.xlsx')) {
        rows = await readXlsx(file);
      } else {
        toast('error', '只支持 .csv 与 .xlsx（与桌面版批量计算的输入格式对齐）。');
        return;
      }
      if (!rows.length) { toast('error', '这个文件里没有读到任何数据。'); return; }
      toast('info', '已读取 ' + file.name + '：' + (rows.length - 1) + ' 行数据，开始计算…');
      await runBatch(rows, file.name);
    } catch (ex) {
      toast('error', '读取失败：' + (ex && ex.message ? ex.message : String(ex)));
    }
  }

  function downloadSampleCsv() {
    downloadText(SAMPLE_CSV, 'wetbulb-sample.csv', 'text/csv');
    toast('success', '示例 CSV 已下载（表头 A/B/C，最后两行故意是非法行，用来演示 #VALUE!）');
  }

  /* ==================== 18. 公式档案 ==================== */

  const FORMULA_NOTES = {
    'Goff-水面': 'Goff-Gratch (1946) 水面式，参考温度 273.15 K。气象学里最常被引用的"老标准"。',
    'Wexler-水面': 'Hyland & Wexler (1983) 水面式，ln(e) 的多项式。注册域到 200 ℃，是 14 条里最宽的。',
    'Buck-水面': 'Buck (1981) 水面式。原注册域到 80 ℃，但实测 60 ℃ 偏 +0.37%、70 ℃ +0.70%、80 ℃ +1.11%（对照 IAPWS-95），v1.3.2 把上界收到 50 ℃。',
    'Tetens-水面': 'Tetens 经验式（中文教材最常见的版本）。',
    'Magnus-水面': 'Magnus 型，Alduchov & Eskridge 系数，日常气象计算的通用选择。',
    'August-水面': 'August-Roche-Magnus 型，与 Magnus 型同族、系数略不同。',
    'Arden-水面': '即 Buck (1996) 三参数式 —— "Arden" 是作者 Arden L. Buck 的名字，不是另一个人。旧版误把它塞进两参数族，丢掉 −T/234.5 修正项，会给出 25 ℃ +0.91%、50 ℃ +3.51%、100 ℃ +12.56% 的系统性偏高；v1.3.2 起按原式实现并新增 buck96 族。',
    'Gili-水面': '纪利公式 —— 中文给排水/冷却塔工程经验式，**不是气象学公式**。出处：周西华、梁茵、王小毛、周令昌《饱和水蒸汽分压力经验公式的比较》，辽宁工程技术大学学报 2007, 26(3): 331–333，公式 (7)；GB/T 50392-2016 第 5.1 节亦采用。注意名字是「纪利」不是「吉利」。参考温度取 373.15 K 是有意偏离原文的 373.16 K —— 实测更接近 IAPWS-95。−10~120 ℃ 全域最大偏差 0.158%。',
    'Goff2-水面': 'Goff-Gratch (1946) 的另一版：参考温度 373.15 K、lg(1013.246)。旧版第 4 个系数误写成 1.3816e-5（标准值 1.3816e-7，差 100 倍），使低温段严重超重：0 ℃ −3.5%、10 ℃ −1.7%、20 ℃ −0.9%。',
    'Goff-冰面': 'Goff-Gratch 冰面式。上界 0 ℃ —— 常压下 0 ℃ 以上不存在冰面，冰面式在正温上给的是"霜点"。',
    'Wexler-冰面': 'Hyland & Wexler (1983) 冰面式，文献声明域 173.15~273.15 K（−100~0 ℃）。旧版下界取到 −150 ℃，在 −150 ℃ 处已偏 +0.47%，v1.3.2 收到 −100 ℃。',
    'Magnus-冰面': 'Magnus 型冰面式，下界 −65 ℃。',
    'Buck-冰面': 'Buck 冰面式，下界 −80 ℃。',
    'Marti-冰面': 'Marti & Mauersberger (1993)，拟合区间 170~273 K（−103~0 ℃）。旧版下界 −150 ℃ 处偏 −9.93%，外推已失效，v1.3.2 收到 −103 ℃。',
  };

  const FAMILY_NOTES = {
    magnus: { form: 'e_sat = A·exp(B·T / (C + T))', note: '两参数 Magnus 型；**有解析反算**，所以求露点时不用二分。' },
    goff: { form: 'log₁₀(e_sat) = 多项式(Tk)', note: 'Goff-Gratch 型：对数域上的多项式和，含 10^x 修正项。' },
    wexler: { form: 'ln(e_sat) = 多项式(Tk)，结果 ÷100 由 Pa 换算 hPa', note: 'Hyland & Wexler 型。' },
    gili: { form: 'e_sat = 1013.25 · 10^[−3.142305(1000/Tk − 1000/373.15) + 8.2·lg(373.15/Tk) − 0.0024804(373.15 − Tk)]', note: '纪利公式形式（给排水工程）。' },
    marti: { form: 'e_sat = 10^(−2663.5/Tk + 12.537) / 100', note: 'Marti & Mauersberger 冰面拟合式。' },
    buck96: { form: 'e_sat = A·exp[(B − T/C)·T / (D + T)]', note: 'Buck (1996) 三参数式；比两参数式多一个 −T/C 修正项。' },
  };

  function renderFormulaArchive() {
    const host = $('formula-list');
    host.innerHTML = '';
    $('formula-count').textContent = C.FORMULAS.length + ' 条公式 · 6 个公式族';
    C.FORMULAS.forEach((f, i) => {
      const item = document.createElement('div');
      item.className = 'formula-item';
      const left = document.createElement('div');
      left.className = 'formula-name';
      const name = document.createElement('span');
      name.textContent = f.name;
      name.style.color = palette()[i % palette().length];
      const badges = document.createElement('div');
      badges.className = 'row';
      badges.innerHTML = '<span class="chip muted tiny">' + f.family + '</span>'
        + '<span class="chip muted tiny">' + f.tmin + '~' + f.tmax + ' ℃</span>'
        + '<span class="chip muted tiny">A₀=' + f.a0 + '</span>';
      left.appendChild(name);
      left.appendChild(badges);
      const right = document.createElement('div');
      right.className = 'formula-meta';
      const coef = f.coeff.length ? f.coeff.map((c) => String(c)).join(', ') : '（无系数：形式固定）';
      right.innerHTML = '<div class="coef">系数：' + coef + '</div>'
        + '<div class="coef">湿度计 A 系数基准 a₀ = ' + f.a0
        + '（水面 0.000660 / 冰面 0.000582，FAO《Frost Protection》Vol.1 附录 3 式 A3.15 / A3.16）</div>'
        + '<div>' + (FORMULA_NOTES[f.name] || '') + '</div>';
      item.appendChild(left);
      item.appendChild(right);
      host.appendChild(item);
    });

    const fam = $('family-list');
    fam.innerHTML = '';
    Object.keys(FAMILY_NOTES).forEach((key) => {
      const info = FAMILY_NOTES[key];
      const count = C.FORMULAS.filter((f) => f.family === key).length;
      const item = document.createElement('div');
      item.className = 'formula-item';
      item.innerHTML = '<div class="formula-name"><span>' + key + '</span>'
        + '<div class="row"><span class="chip muted tiny">' + count + ' 条公式</span></div></div>'
        + '<div class="formula-meta"><div class="coef">' + info.form + '</div><div>' + info.note + '</div></div>';
      fam.appendChild(item);
    });
  }

  /* ==================== 19. 数值自检（用 core.py 的黄金向量对拍） ==================== */

  function closeEnough(a, b, tempLike) {
    if (Number.isNaN(a) && Number.isNaN(b)) return true;
    if (!Number.isFinite(a) || !Number.isFinite(b)) return a === b;
    const d = Math.abs(a - b);
    if (tempLike && d <= V.tolerance.abs_temp) return true;
    if (d <= 1e-9) return true;
    const denom = Math.max(Math.abs(a), Math.abs(b));
    return denom > 0 && d / denom <= V.tolerance.rel;
  }

  function runSelfTest() {
    const t0 = performance.now();
    const cats = [];
    const add = (name, total, failed, maxDev, detail) => cats.push({ name: name, total: total, failed: failed, maxDev: maxDev, detail: detail });

    // 1) e_sat 与导数
    ['esat', 'dedt'].forEach((kind) => {
      let failed = 0, maxDev = 0, first = '';
      V[kind].forEach((c) => {
        const method = c[0], T = c[1], want = Number(c[2]);
        let got;
        try { got = kind === 'esat' ? C.calculate_esat(T, method) : C.calculate_dedt(T, method); }
        catch (e) { got = NaN; }
        const dev = Math.abs(got - want) / Math.max(Math.abs(want), 1e-300);
        if (Number.isFinite(dev)) maxDev = Math.max(maxDev, dev);
        if (!closeEnough(got, want, false)) { failed++; if (!first) first = method + ' @' + T + ' ℃：得到 ' + got + '，应为 ' + want; }
      });
      add(kind === 'esat' ? '饱和水汽压 e_sat' : '导数 de/dT', V[kind].length, failed, maxDev, first);
    });

    // 2) 三种模式的完整结果（比的是界面显示串）
    let failed = 0, first = '', rows = 0;
    V.modes.forEach((c) => {
      const mode = c[0], T = c[1], value = c[2], P = c[3], expect = c[4];
      let got;
      try {
        if (mode === 0) got = C.calculate_wetbulb(value, T, value, P);
        else if (mode === 1) got = C.calculate_dewpoint(T, value, P);
        else got = C.calculate_both(T, T, value, P);
      } catch (e) { got = []; }
      expect.forEach((e) => {
        rows++;
        const method = e[0], r1 = e[1], r2 = e[2], rhRepr = e[3];
        const hit = got.find((x) => x.method === method);
        const text1 = hit ? (typeof hit.result1 === 'number' ? C.pyFixed(hit.result1, 4) : String(hit.result1)) : '(缺失)';
        const text2 = hit ? (hit.result2 === null || hit.result2 === undefined ? '' : (typeof hit.result2 === 'number' ? C.pyFixed(hit.result2, 4) : String(hit.result2))) : '';
        if (text1 !== r1 || text2 !== r2) {
          failed++;
          if (!first) first = '模式' + mode + ' ' + method + '：得到 [' + text1 + ', ' + text2 + ']，应为 [' + r1 + ', ' + r2 + ']';
        } else if (rhRepr !== 'None' && rhRepr !== null && hit && typeof hit.rh === 'number') {
          const want = Number(rhRepr);
          if (!closeEnough(hit.rh, want, false)) {
            failed++;
            if (!first) first = '模式' + mode + ' ' + method + ' 的 rh：得到 ' + hit.rh + '，应为 ' + want;
          }
        }
      });
    });
    add('三种模式的逐公式结果', rows, failed, 0, first);

    // 3) 输入校验的错误文案
    failed = 0; first = '';
    V.validate.forEach((c) => {
      const fn = c[0], valueRepr = c[1], want = c[2];
      const value = valueRepr === 'nan' ? NaN : (valueRepr === 'inf' ? Infinity : Number(valueRepr));
      const fns = { temperature: C.check_temperature, pressure: C.check_pressure, rh: C.check_relative_humidity };
      let got;
      try { fns[fn](value); got = 'ok'; }
      catch (e) { got = e.message; }
      if (got !== want) { failed++; if (!first) first = fn + '(' + valueRepr + ')：得到「' + got + '」，应为「' + want + '」'; }
    });
    add('输入校验的错误文案', V.validate.length, failed, 0, first);

    // 4) Python 语义格式化（4 位小数的显示串、%g）
    failed = 0; first = '';
    V.fmt.forEach((c) => {
      const kind = c[0], xRepr = c[1], n = c[2], want = c[3];
      const x = xRepr === '-0.0' ? -0 : Number(xRepr);
      const got = kind === 'fixed' ? C.pyFixed(x, n) : C.pyG(x, n);
      if (got !== want) { failed++; if (!first) first = kind + '(' + xRepr + ', ' + n + ')：得到 ' + got + '，应为 ' + want; }
    });
    add('Python 语义格式化', V.fmt.length, failed, 0, first);

    // 5) 派生量
    failed = 0; let maxDevD = 0; first = ''; let count = 0;
    V.derive.forEach((c) => {
      const d = C.derive_moist_air(c[0], c[1], c[2], c[3], c[4], c[5]);
      c[6].forEach((pair) => {
        count++;
        const key = pair[0], want = Number(pair[1]), got = d[key];
        if (Number.isNaN(want) && Number.isNaN(got)) return;
        const dev = Math.abs(got - want) / Math.max(Math.abs(want), 1e-300);
        if (Number.isFinite(dev)) maxDevD = Math.max(maxDevD, dev);
        if (!closeEnough(got, want, false)) {
          failed++;
          if (!first) first = key + '：得到 ' + got + '，应为 ' + want;
        }
      });
    });
    add('常用气象参数（派生量）', count, failed, maxDevD, first);

    const total = cats.reduce((a, c) => a + c.total, 0);
    const bad = cats.reduce((a, c) => a + c.failed, 0);
    const ms = (performance.now() - t0).toFixed(1);

    const host = $('selftest-host');
    host.innerHTML = '';
    cats.forEach((c) => {
      const row = document.createElement('div');
      row.className = 'st-row';
      const name = document.createElement('span');
      name.className = 'name';
      name.textContent = c.name;
      const val = document.createElement('span');
      val.className = 'val';
      val.textContent = c.total + ' 项'
        + (c.maxDev ? ' · 最大相对偏差 ' + c.maxDev.toExponential(1) : '')
        + (c.detail ? ' · ' + c.detail.slice(0, 120) : '');
      const pill = document.createElement('span');
      pill.className = 'pill badge ' + (c.failed ? 'bad' : 'ok');
      pill.innerHTML = '<span class="pip"></span>' + (c.failed ? c.failed + ' 项超差' : '全部一致');
      row.appendChild(name);
      row.appendChild(val);
      row.appendChild(pill);
      host.appendChild(row);
    });

    const summary = '对拍 ' + total + ' 项 · ' + (bad ? bad + ' 项超差' : '0 处超差')
      + ' · 对应桌面版 ' + C.EXE_TAG + ' · 用时 ' + ms + ' ms';
    $('selftest-summary').textContent = summary;
    if (bad) toast('error', '数值自检发现 ' + bad + ' 项不一致，网页版内核与 core.py ' + C.EXE_TAG + ' 有偏差。');
    else toast('success', '数值自检通过：' + summary);
    return { total: total, bad: bad };
  }

  /* ==================== 21. 事件绑定 ==================== */

  function bindEvents() {
    // 模式
    document.querySelectorAll('.segmented button').forEach((b) => {
      b.addEventListener('click', () => {
        setMode(Number(b.dataset.mode), { recompute: false });
        // 桌面版切模式会清空；这里保留输入、只清结果，避免旧模式的结果被误读
        state.results = [];
        state.iterations = {};
        state.selected = null;
        state.solved = null;
        renderResults();
        renderDerived();
        drawChart();
        saveState();
      });
    });

    // 输入框：Enter 计算；聚焦时选中全部，方便直接覆盖
    ['in-dry', 'in-other', 'in-pressure'].forEach((id) => {
      const el = $(id);
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); compute(); }
      });
      el.addEventListener('input', () => { markInvalid(el, false); });
      el.addEventListener('focus', () => el.select());
    });

    $('btn-calc').addEventListener('click', compute);
    $('btn-clear').addEventListener('click', clearAll);

    // 精度与初值
    $('in-precision').addEventListener('input', () => {
      state.precision = Number($('in-precision').value);
      $('tol-readout').textContent = '1e-' + state.precision;
      saveState();
    });
    $('in-strategy').addEventListener('change', () => {
      state.strategy = $('in-strategy').value;
      saveState();
    });

    // 结果导出
    $('btn-json').addEventListener('click', exportJson);
    $('btn-csv').addEventListener('click', exportCsv);
    $('btn-png').addEventListener('click', drawResultCard);
    $('btn-share').addEventListener('click', shareLink);

    // 图表
    $('chart-method').addEventListener('change', drawChart);
    $('chart-log').addEventListener('change', drawChart);
    $('btn-chart-png').addEventListener('click', exportChartPng);

    // 标签页（左右方向键在标签之间移动是 tablist 的无障碍约定）
    ['calc', 'batch', 'formulas', 'about'].forEach((name) => {
      const tab = $('tab-' + name);
      tab.addEventListener('click', () => setTab(name));
      tab.addEventListener('keydown', onTabKey);
    });

    // 主题
    $('btn-theme').addEventListener('click', () => {
      applyTheme(state.theme === 'dark' ? 'light' : 'dark');
      saveState();
    });

    // 单位弹窗
    const modal = $('modal-units');
    const openUnits = () => {
      document.querySelector('input[name="pu"][value="' + state.pressureUnit + '"]').checked = true;
      document.querySelector('input[name="tu"][value="' + state.tempUnit + '"]').checked = true;
      modal.classList.add('show');
    };
    const closeUnits = () => modal.classList.remove('show');
    $('btn-units').addEventListener('click', openUnits);
    $('btn-units-cancel').addEventListener('click', closeUnits);
    modal.addEventListener('click', (e) => { if (e.target === modal) closeUnits(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeUnits(); });
    $('btn-units-ok').addEventListener('click', () => {
      const pu = document.querySelector('input[name="pu"]:checked').value;
      const tu = document.querySelector('input[name="tu"]:checked').value;
      state.pressureUnit = pu;
      state.tempUnit = tu;
      refreshUnitLabels();
      closeUnits();
      saveState();
      if (state.results.length) {
        renderResults();
        renderDerived();
        toast('info', '单位已切换为 ' + tu + ' / ' + pu + '，结果与派生量已按新单位重绘。'
          + '（桌面版此时会清空输入框，网页版选择保留。）');
      } else {
        toast('success', '单位已切换为 ' + tu + ' / ' + pu);
      }
    });

    // 强调色
    $('accent-input').addEventListener('input', () => {
      const hex = $('accent-input').value;
      // 三个通道变量的名字必须与下面这行一致。曾经这里写作 g 而上面声明的是 g2，
      // 'use strict' 下抛 ReferenceError: g is not defined —— 取色器 100% 点不动，
      // 而 e2e 里没有任何一条用例碰过它，所以整套测试一直全绿。
      const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
      applyAccent(r + ', ' + g + ', ' + b);
      saveState();
    });
    $('btn-accent-reset').addEventListener('click', () => {
      applyAccent(ACCENT_DEFAULT);
      saveState();
      toast('info', '强调色已恢复为 assets/cfg.json 的默认值 rgb(71, 148, 157)');
    });

    // 批量计算
    const dz = $('dropzone'), fi = $('file-input');
    dz.addEventListener('click', () => fi.click());
    dz.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fi.click(); } });
    ['dragenter', 'dragover'].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add('over'); }));
    ['dragleave', 'drop'].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove('over'); }));
    dz.addEventListener('drop', (e) => {
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      handleFile(f);
    });
    fi.addEventListener('change', () => { handleFile(fi.files[0]); fi.value = ''; });
    $('btn-sample').addEventListener('click', downloadSampleCsv);
    $('btn-batch-csv').addEventListener('click', exportBatchCsv);
    $('btn-batch-xlsx').addEventListener('click', exportBatchXlsx);
    $('btn-batch-clear').addEventListener('click', () => {
      state.batch = null;
      ['batch-actions', 'batch-stats', 'batch-scroll', 'batch-progress-wrap'].forEach((id) => $(id).classList.add('hidden'));
      $('batch-body').innerHTML = '';
      $('batch-head').innerHTML = '';
      toast('info', '批量结果已清空');
    });

    // 自检
    $('btn-selftest').addEventListener('click', () => { setTab('about'); runSelfTest(); });
    $('btn-selftest-2').addEventListener('click', runSelfTest);

    // 窗口尺寸变化时重画图表
    let t = null;
    window.addEventListener('resize', () => {
      clearTimeout(t);
      t = setTimeout(() => { if (state.results.length) drawChart(); }, 160);
    });

    // 链接统一从常量取，避免同一个 URL 在文件里抄好几遍
    $('link-repo-top').href = REPO_URL;
  }

  const SAMPLE_CSV = 'A,B,C\n' +
    '25,15,1013.25\n' +
    '25,20,1013.25\n' +
    '30,25,1000\n' +
    '20,10,1013.25\n' +
    '10,5,900\n' +
    '0,-5,1013.25\n' +
    '-10,-15,1013.25\n' +
    '35,30,1013.25\n' +
    'abc,15,1013.25\n' +
    '25,99,1013.25\n';

  /* ==================== 22. 启动 ==================== */

  function init() {
    // 1) 版本号一律从内核常量取，避免"文档写 2.0.0、代码写 2.0.1"
    const webTag = C.WEB_TAG, exeTag = C.EXE_TAG;
    ['chip-web-version', 'about-web-tag', 'footer-web-tag'].forEach((id) => { $(id).textContent = (id === 'chip-web-version' ? '网页版 ' : '') + webTag; });
    ['about-exe-tag', 'footer-exe-tag'].forEach((id) => { $(id).textContent = exeTag; });
    document.title = '湿球计算器 · WetBulb Calculator（网页版 ' + webTag + '）';

    // 2) 恢复本地记忆，其次读 URL 参数（分享链接优先）
    const saved = loadState();
    if (saved) {
      if (typeof saved.mode === 'number') state.mode = saved.mode;
      state.precision = saved.precision || state.precision;
      state.strategy = saved.strategy || state.strategy;
      state.tempUnit = saved.tempUnit || state.tempUnit;
      state.pressureUnit = saved.pressureUnit || state.pressureUnit;
      state.inputs = saved.inputs || state.inputs;
      applyTheme(saved.theme || 'light');
      applyAccent(saved.accent || ACCENT_DEFAULT);
      state.tab = saved.tab || 'calc';
    } else {
      applyTheme(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      applyAccent(ACCENT_DEFAULT);
    }
    readUrlParams();     // 分享链接里的参数优先于本地记忆

    $('in-precision').value = String(state.precision);
    $('in-strategy').value = state.strategy;
    $('in-dry').value = state.inputs.t;
    $('in-other').value = state.inputs.other;
    $('in-pressure').value = state.inputs.p;
    setMode(state.mode, {});
    refreshUnitLabels();
    $('chart-log').checked = true;

    // 3) 事件绑定
    bindEvents();

    // 4) 静态内容（公式档案 / 族说明 / 迭代图公式下拉）
    renderFormulaArchive();
    renderChartMethodOptions();

    // 5) 首屏自动算一次 —— 打开就有东西看，且立刻能验证内核是活的
    setTab(state.tab);
    compute();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
