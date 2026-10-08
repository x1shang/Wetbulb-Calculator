# -*- coding: utf-8 -*-
"""工程卫生的可执行检查。

审计报告里"产物与授权卫生""验证没有被基础设施化"两条，落到这个仓库就是
下面这几件具体的事。把它们写成断言，才能保证"修一次"变成"一直成立"。
"""
import os
import re
import subprocess
import sys
import textwrap
import json
import tempfile

import pytest

import core

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 仓库结构（v1.3.3 起）。改结构就要改这张表——它是"我们声称的布局"的唯一出处。
# 构建与发版资产（spec、requirements-build、scripts/、两个 workflow）同样列在这里：
# 它们各自有专项断言，但"文件还在不在"只有这张表能守住。
EXPECTED_LAYOUT = [
    'main.py',
    'src/core.py',
    'src/ui/calculator1.py',
    'src/ui/unit.py',
    'src/ui/about.py',
    'assets/app.ico',
    'assets/err.ico',
    'assets/cfg.json',
    'assets/screenshots/k1.png',
    'examples/example.xlsx',
    'legacy/sample.py',
    'tests/reference_values.py',
    'docs/项目编年史.md',
    'docs/精度与参考文献.md',
    'README.md',
    'README.en.md',
    'RELEASE_NOTES.md',
    'THIRD_PARTY_NOTICES.md',
    'LICENSE',
    'requirements.txt',
    'requirements-dev.txt',
    'requirements-build.txt',
    'run_tests.ps1',
    'build.ps1',
    'WetBulbCalculator.spec',
    'conftest.py',
    'scripts/version_info.py',
    'scripts/collect_licenses.py',
    'scripts/verify_cli.py',
    '.gitignore',
    '.gitattributes',
    '.github/workflows/tests.yml',
    '.github/workflows/release.yml',
]

# 整理前散落在仓库根目录、现在必须已经归位的文件
STALE_ROOT_FILES = [
    'core.py', 'calculator1.py', 'unit.py', 'about.py', 'sample.py',
    'app.ico', 'err.ico', 'cfg.json', 'test.xlsx', '制造执行文件.txt',
    '项目编年史.md', '改进操作说明书.md',
]


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def _source_files():
    """main.py 加上 src/ 下全部 .py（用于静态扫描）。路径统一用正斜杠。"""
    files = ['main.py']
    for dp, dirs, names in os.walk(os.path.join(ROOT, 'src')):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        files += [os.path.relpath(os.path.join(dp, n), ROOT).replace(os.sep, '/')
                  for n in names if n.endswith('.py')]
    return sorted(files)


def test_core_has_no_gui_dependencies():
    """core.py 必须保持零 GUI 依赖（审计肯定过的那条架构性质）。
    正是这一点让 CI 能在装不上 PySide2 的 Linux 空白机器上验证计算核心。"""
    src = _read('src/core.py')
    for forbidden in ('PySide2', 'qfluentwidgets', 'matplotlib', 'pandas', 'numpy'):
        assert forbidden not in src, f"core.py 不应依赖 {forbidden}"


def test_core_selfcheck_passes():
    """`python core.py` 是零依赖的等价性回归入口，必须能以 0 退出。"""
    proc = subprocess.run([sys.executable, 'src/core.py'], cwd=ROOT,
                          capture_output=True, text=True, timeout=120,
                          encoding='utf-8', errors='replace')
    assert proc.returncode == 0, f"core.py 自检失败：\n{proc.stdout}\n{proc.stderr}"
    assert 'OK' in proc.stdout


def test_repository_layout_is_where_we_say_it_is():
    """文件必须待在表格里说的地方，且不再散落在仓库根目录。"""
    missing = [p for p in EXPECTED_LAYOUT if not os.path.exists(os.path.join(ROOT, p))]
    assert not missing, "以下文件不在预期位置：\n" + "\n".join(missing)
    stale = [p for p in STALE_ROOT_FILES if os.path.exists(os.path.join(ROOT, p))]
    assert not stale, "以下文件仍散落在仓库根目录（应已归类）：\n" + "\n".join(stale)


def test_every_resource_path_argument_exists():
    """源码里每个 resource_path(...) 的实参都必须指向真实存在的文件。

    resource_path 的失败是**静默**的：QIcon 找不到图标就只是不显示图标，
    cfg.json 读不到就用默认值 —— 正因为它不报错，才必须用断言钉住。
    这条测试就是为了守住"整理目录之后资源路径还对不对"。
    """
    consts = dict(re.findall(r"^([A-Z_][A-Z0-9_]*)\s*=\s*'([^']+)'",
                             _read('src/core.py'), re.M))
    checked, missing = 0, []
    for rel in _source_files():
        src = _read(rel)
        # 跳过整行注释：注释里出现的 resource_path(...) 是历史说明，不是真实调用。
        code = '\n'.join(ln for ln in src.splitlines() if not ln.lstrip().startswith('#'))
        for arg in re.findall(r"resource_path\(\s*(?:'([^']+)'|([A-Z_][A-Z0-9_]*))\s*\)", code):
            literal, name = arg
            target = literal or consts.get(name)
            if target is None:
                missing.append(f"{rel}: 无法解析 resource_path({name})")
                continue
            checked += 1
            if not os.path.exists(os.path.join(ROOT, target)):
                missing.append(f"{rel}: resource_path({name or repr(literal)}) -> {target} 不存在")
    assert checked >= 3, f"只找到 {checked} 处 resource_path(...)，扫描逻辑可能失效了"
    assert not missing, "资源路径失效：\n" + "\n".join(missing)


def test_config_helpers_are_defined_only_once():
    """resource_path / cfg_file_path / load_title_color 只能在 core.py 里实现一次。

    整理前 src/ui/calculator1.py 有一份逐字重复的副本，"配置到底读哪一份"
    取决于谁先被 import —— 这种重复比错误更难发现。
    """
    owners = {'resource_path': [], 'cfg_file_path': [], 'load_title_color': []}
    for rel in _source_files():
        src = _read(rel)
        for name in owners:
            if re.search(rf'^def\s+{name}\s*\(', src, re.M):
                owners[name].append(rel)
    for name, where in owners.items():
        assert where == ['src/core.py'], f"{name} 的定义出现在 {where}，应只在 src/core.py"


def test_gravity_setting_is_fully_removed():
    """B-20 收尾：'本地重力加速度' 连界面、配置与读写函数一起删除，不得复活。

    它自 v1.2.0 出现起就没进过任何公式，却让用户以为"改了它结果会更准"。
    而本工具用到的物理量都不含 g；唯一沾边的 mmHg/cmHg 是**定义值**
    （1 mmHg = 133.322387415 Pa），与重力加速度无关 —— 也就是说这个参数
    在物理上无处可用，不是"暂时没接上"。

    扫描时按 `#` 截断，跳过注释：源码里允许用注释记录这段历史，
    但不允许标识符重新出现在真正的代码里。
    """
    cfg = json.loads(_read('assets/cfg.json'))
    assert 'g' not in cfg, f"assets/cfg.json 里不该再有 g 键：{cfg}"

    pattern = re.compile(r'LineEdit_4|label_6|load_g_value|save_g_value|update_g_value')
    offenders = []
    for rel in _source_files():
        for i, line in enumerate(_read(rel).splitlines(), 1):
            if pattern.search(line.split('#', 1)[0]):
                offenders.append(f"{rel}:{i}: {line.strip()}")
    assert not offenders, ("重力加速度设置的残骸还在代码里：\n" + "\n".join(offenders)
                           + "\n（若只是注释里的历史说明，请确认它确实在 # 之后）")


def test_build_script_gives_pyinstaller_the_module_search_paths():
    spec = _read('WetBulbCalculator.spec')
    assert "pathex=['src', 'src/ui']" in spec
    assert "version='build/version.txt'" in spec
    assert "'LICENSE'" in spec and "'THIRD_PARTY_NOTICES.md'" in spec
    assert 'WetBulbCalculator.spec' in _read('build.ps1')


def test_no_personal_absolute_paths():
    # Inspect shipped/tracked text only; local todo and virtual environments are private.
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    pattern = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]|(?<![A-Za-z0-9:/])/(?:home|Users|mnt|opt|tmp)/")
    offenders = []
    for rel in paths:
        if rel == 'tests/test_repo_hygiene.py' or not rel.endswith(('.py', '.md', '.json', '.txt', '.ps1', '.yml', '.spec')):
            continue
        for number, line in enumerate(_read(rel).splitlines(), 1):
            if pattern.search(line):
                offenders.append(f'{rel}:{number}: {line.strip()}')
    assert not offenders, '\n'.join(offenders)


def _requirement_lines(text):
    """只取真正的依赖行，忽略注释——否则注释里提到 PySide2 也会被当成依赖。"""
    return [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith('#')]


def test_dev_requirements_ship_pytest():
    assert any('pytest' in ln for ln in _requirement_lines(_read('requirements-dev.txt')))


def test_runtime_requirements_do_not_pin_uninstallable_gui_stack():
    """运行依赖钉着 PySide2==5.15.2.1（Python ≤3.10 才有轮子），
    所以测试依赖清单必须与它分开，否则 CI 在 3.11+ 上装不上。"""
    runtime = _requirement_lines(_read('requirements.txt'))
    dev = _requirement_lines(_read('requirements-dev.txt'))
    assert any('PySide2' in ln for ln in runtime), "requirements.txt 应保留 GUI 运行依赖"
    assert not any('PySide2' in ln for ln in dev), \
        f"requirements-dev.txt 不该带 GUI 依赖，实际有：{dev}"
    assert not any('pandas' in ln or 'matplotlib' in ln for ln in dev)


def test_runtime_requirements_constrain_numpy_below_2():
    """matplotlib 3.5.3 是针对 NumPy 1.x 编译的 C 扩展，
    元数据里只要求 numpy>=1.17、没有上界；不写上界，空白机器上 pip 会装
    NumPy 2.x，程序连 `import matplotlib.pyplot` 都过不去。"""
    numpy_lines = [ln.replace(' ', '') for ln in _requirement_lines(_read('requirements.txt'))
                   if ln.lower().startswith('numpy')]
    assert numpy_lines, "requirements.txt 必须显式约束 numpy（否则全新安装装到 NumPy 2.x 就崩）"
    assert all('<2' in ln for ln in numpy_lines), \
        f"numpy 必须有 <2 上界，实际是：{numpy_lines}"


def test_readme_states_a_python_version_that_can_actually_install():
    assert 'Python 3.10' in _read('README.md')


def test_readme_links_public_docs():
    for name in ('项目编年史.md', '精度与参考文献.md'):
        assert 'docs/' + name in _read('README.md')


def test_tag_constant_matches_release(tmp_path):
    """core.py 的 tag 是版本号的唯一来源，不能与其他文件里写的版本号打架。"""
    readme = _read('README.md')
    assert core.tag in readme, f"README 未提到当前版本 {core.tag}"


def test_gui_full_calculation_flow():
    """在 offscreen 平台走一遍**完整计算流程**（两种模式），断言结果真的显示出来了。

    这一条是 B-07 的回归测试。原缺陷：`CalculatorMemory.show_results` 读模块全局
    `main_window.temperature_unit`，而那个全局只在"以 __main__ 运行"时是**实例**
    （文件底部 `main_window = main_window()` 把类名覆盖掉了）；一旦被 import，
    它就是**类**，取属性抛 AttributeError，而 validate_and_calculate 的兜底 except
    把异常变成一条错误条 —— **界面什么都不显示，也不报错**。
    所以这里的断言是 rows > 0，而不只是"没抛异常"。
    """
    exe = _gui_interpreter()
    if exe is None:
        pytest.skip('本机没有装齐 GUI 依赖（PySide2 + NumPy 1.x）的解释器')
    code = textwrap.dedent('''
        import os, sys
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        import main
        from PySide2.QtWidgets import QApplication
        app = QApplication(sys.argv)
        main.main_window.createErrorInfoBar = lambda self, msg, *a, **k: print("ERRBAR:", msg)
        w = main.main_window()
        w.show()

        # 模式 0：已知露点求湿球
        w.ComboBox.setCurrentIndex(0)
        w.LineEdit_3.setText("25"); w.LineEdit.setText("15"); w.LineEdit_2.setText("1013.25")
        app.processEvents()
        w.validate_and_calculate()
        app.processEvents()
        rows0 = w.list_model.stringList()
        print("MODE0_ROWS", len(rows0))
        print("MODE0_GOFF", [r for r in rows0 if r.startswith("Goff-水面")])

        # 模式 2：已知相对湿度同时求露点与湿球
        # 注意：ComboBox 的 currentIndexChanged 同时连了 clearall()，切模式会清空输入框
        # （这是设计如此），所以三个输入框都要在切换之后重新填。
        w.ComboBox.setCurrentIndex(2)
        app.processEvents()
        w.LineEdit_3.setText("25"); w.LineEdit.setText("60"); w.LineEdit_2.setText("1013.25")
        app.processEvents()
        w.validate_and_calculate()
        app.processEvents()
        rows2 = w.list_model.stringList()
        print("MODE2_ROWS", len(rows2))
        print("MODE2_GOFF", [r for r in rows2 if r.startswith("Goff-水面")])

        # 模式 0（边界值）：干球 0 ℃ / 露点 −5 ℃
        # 【为什么单独列一条】v1.3.2 的 check_input 改成"返回换算到标准单位后的数值"，
        # 若调用方仍写成 `if not self.check_input(...)`，**0 ℃ 会被 `not 0.0` 判成失败** ——
        # 点"计算"毫无反应、连错误条都没有。0 ℃ 是最常见的输入之一，必须钉住。
        w.ComboBox.setCurrentIndex(0)
        app.processEvents()
        w.LineEdit_3.setText("0"); w.LineEdit.setText("-5"); w.LineEdit_2.setText("1013.25")
        app.processEvents()
        w.validate_and_calculate()
        app.processEvents()
        rows_zero = w.list_model.stringList()
        print("MODE0_ZERO_ROWS", len(rows_zero))
        print("MODE0_ZERO_GOFF", [r for r in rows_zero if r.startswith("Goff-水面")])
    ''')
    proc, records = _run_probe(exe, code)
    assert records, _probe_failed(proc, records)
    out = '\n'.join(records)
    assert 'ERRBAR' not in out, f"计算过程弹出了错误条（说明异常被吞掉了）：\n{out}"
    # 表头 1 行 + 14 条公式；注意列表末尾还有一行空串，所以是 16
    assert 'MODE0_ROWS 16' in out, f"模式0 没有把结果填进列表：\n{out}"
    assert 'MODE2_ROWS 16' in out, f"模式2 没有把结果填进列表：\n{out}"
    assert 'MODE0_ZERO_ROWS 16' in out, (
        f"干球 0 ℃（合法输入）没有出结果：多半是 check_input 的返回值被当布尔量用了"
        f"（`not 0.0` 为真 → 静默返回）：\n{out}")

    # 数值锚点：期望值由 core 现算，不写死常数。
    # 【为什么改】原实现写死 "18.6186" 并声称"与编年史记录的实测值一致"——
    # 于是每次修数值都得同步改这条测试，而它是 GUI 回归、本该只关心
    # "界面有没有把结果渲染出来"。现在把"算得对不对"交给 core 现算的值，
    # 这条测试就只剩它真正的职责：界面链路通不通、显示值与 core 是否一致。
    want0 = {r['method']: r['result1'] for r in core.calculate_wetbulb(15, 25, 15)}['Goff-水面']
    want2 = {r['method']: r for r in core.calculate_both(20, 25, 60)}['Goff-水面']
    assert f"{want0:.4f}℃" in out, (
        f"模式0 界面显示的 Goff-水面 结果与 core 现算的 {want0:.4f}℃ 不一致：\n{out}")
    assert f"{want2['result1']:.4f}℃" in out and f"{want2['result2']:.4f}℃" in out, (
        f"模式2 界面显示的 Goff-水面 结果与 core 现算的 "
        f"{want2['result1']:.4f}/{want2['result2']:.4f}℃ 不一致：\n{out}")


def test_main_does_not_rebind_core_globals():
    """main.py 不得用 `global X` 去改从 core 导入的量。

    这条规则是从一次真实的 CI 失败里总结出来的：
    `global tot; tot = 10**(-value)` 让 pyflakes 4.0.2 在 **Python 3.12** 上把
    `from core import tot` 报成 unused，而在 3.10/3.11 上不报——同一个提交在两个
    矩阵任务里得到相反结论（CI 首次运行就是这样：3.10 全绿、3.12 红）。
    根因是它同时是"死状态"：core 的计算函数按 `tol=` 参数取值，
    改 core 的模块变量不影响任何一次计算。main.py 现在自己持有 `tot`。
    """
    src = _read('main.py')
    imported = set()
    for m in re.finditer(r'from core import \(([^)]*)\)', src, re.S):
        for part in m.group(1).split(','):
            part = part.strip()
            if part:
                imported.add(part.split(' as ')[-1].strip())
    assert imported, "没有解析出 main.py 从 core 导入的名字"
    declared_global = set(re.findall(r'^\s*global\s+([A-Za-z_][A-Za-z0-9_]*)', src, re.M))
    clash = sorted(imported & declared_global)
    assert not clash, (
        f"main.py 用 global 重绑了从 core 导入的名字：{clash} —— "
        f"那是死状态，且会让静态检查在不同 Python 版本上给出相反结论")


def test_main_uses_only_existing_derive_keys():
    """main.py 里每一处 derived['...'] 都必须是 derive_moist_air 真正返回的键。

    这类拼写错通常只在用户点开
    "扩展参数" 时才炸——所以用静态比对把它拦在提交之前。这条断言正是
    为了守住"把 GUI 里的计算搬进 core 之后，GUI 侧仍取得到值"。
    （main.py 里那个 24 键的派生量字典统一叫 derived，不与 `_run_calc` 回调里的
    单字母 `d` 混淆，这样下面的正则才有确定的含义。）
    """
    src = _read('main.py')
    used = set(re.findall(r"\bderived\['([A-Za-z_][A-Za-z0-9_]*)'\]", src))
    assert used, "没有在 main.py 里找到任何 derived['...'] 取用（是不是又搬回 GUI 了？）"
    returned = set(core.derive_moist_air(25.0, 20.0, 15.0, 0.54, 1013.25).keys())
    missing = sorted(used - returned)
    assert not missing, (
        f"main.py 取了 derive_moist_air 不返回的键：{missing}；"
        f"实际可用的键：{sorted(returned)}")
    unused = sorted(returned - used)
    assert len(unused) <= 4, (
        f"core.derive_moist_air 返回了 {len(unused)} 个界面从不使用的键：{unused}"
        f"——要么接上界面，要么从返回值里删掉")


def _gui_interpreter():
    """找一个同时装齐 GUI 依赖与 NumPy 1.x 的解释器；找不到就返回 None。

    两个条件缺一不可：Python ≤3.10（PySide2 只提供到 3.10 的轮子）与 NumPy 1.x
    （matplotlib 3.5.3 是针对 NumPy 1.x 编译的）。
    Windows CI 设置 WETBULB_REQUIRE_GUI=1，依赖缺失时失败；纯核心任务允许跳过。
    """
    probe_src = textwrap.dedent('''
        import importlib.util as u
        ok = all(u.find_spec(m) for m in
                 ("PySide2", "qfluentwidgets", "matplotlib", "openpyxl", "numpy", "scipy", "colorthief"))
        if ok:
            import numpy
            ok = numpy.__version__.split(".")[0] == "1"
        print("READY" if ok else "MISSING")
    ''')
    candidates = [
        os.environ.get('WETBULB_BUILD_PYTHON'),
        os.environ.get('WETBULB_GUI_PYTHON'),                         # 手动指定（任意路径）
        os.path.join(ROOT, '.venv-build', 'Scripts', 'python.exe'),   # 打包/自测用的 3.10 环境
        sys.executable,
    ]
    for exe in candidates:
        if not exe or not os.path.exists(exe):
            continue
        try:
            probe = subprocess.run([exe, '-c', probe_src], capture_output=True, text=True,
                                   timeout=240, encoding='utf-8', errors='replace')
        except (OSError, subprocess.SubprocessError):
            continue
        if 'READY' in (probe.stdout or ''):
            return exe
    if os.environ.get("WETBULB_REQUIRE_GUI") == "1":
        pytest.fail("GUI dependencies required but unavailable")
    return None


def _run_probe(exe, code, timeout=300):
    """在子进程里跑一段探针代码，把它的 print 输出取回来 —— **不经控制台编码**。

    这是 B-22 的修复。此前父进程写死 `encoding='utf-8'` 去读子进程的 stdout，
    而子进程在中文 Windows 上按 **cp936** 写管道：'℃' 被写成 GBK 字节，父进程按
    UTF-8 解码成 'Goff-\u02ee\ufffd\ufffd'，于是 `Goff-水面 18.6186℃` 那行
    永远断言不过 —— 本地恒红、CI 恒绿（CI 上没有 GUI 解释器，这条测试直接 skip）。
    一条"守 B-07 静默不显示"的回归测试一旦习惯性发红，它的报警就没人看了。

    现在探针把结果写进 **UTF-8 JSON 文件**，父进程读文件断言：既不受控制台
    codepage 影响，也不依赖 PYTHONIOENCODING 有没有被设对。
    顺带把子进程环境的 PYTHONUTF8 也打开（双保险，且 stdout 仍留作诊断）。

    返回 (CompletedProcess, records)。records 为 None 表示探针没能写出结果
    （多半是子进程崩了）——调用方应把它当成失败，并打印 proc.stderr。
    """
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    with tempfile.TemporaryDirectory(prefix='wetbulb-probe-') as td:
        out_path = os.path.join(td, 'probe.json')
        env['WETBULB_PROBE_OUT'] = out_path
        # 探针里所有 print(...) 都变成"收集一行"，最后由 wrapper 统一写成 JSON。
        wrapper = (
            "import json, os\n"
            "_records = []\n"
            "print = lambda *a, **k: _records.append(' '.join(str(x) for x in a))\n"
            + textwrap.dedent(code) + "\n"
            "with open(os.environ['WETBULB_PROBE_OUT'], 'w', encoding='utf-8') as _f:\n"
            "    json.dump(_records, _f, ensure_ascii=False)\n")
        try:
            proc = subprocess.run([exe, '-c', wrapper], cwd=ROOT, capture_output=True,
                                  text=True, timeout=timeout, encoding='utf-8',
                                  errors='replace', env=env)
        except subprocess.TimeoutExpired as e:
            # 超时也算"探针没写出结果"，交给调用方报错时带上 timeout 信息
            return e, None
        records = None
        if os.path.exists(out_path):
            with open(out_path, encoding='utf-8') as f:
                records = json.load(f)
    return proc, records


def _probe_failed(proc, records):
    """探针失败时的统一报错文本（含 stdout/stderr，便于定位）。"""
    tail = '' if proc is None else f"\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    return f"探针没有写出结果文件（子进程崩了或超时）：{records}{tail}"


def test_main_import_still_works_when_gui_stack_is_available():
    """若本机装齐了 GUI 依赖，则 `import main` 必须成功。

    这是"空白机器照 README 能不能跑起来"的第一道闸，第二道见下一条
    （真的把窗口构造出来）。本机没有合适解释器时 skip。
    """
    exe = _gui_interpreter()
    if exe is None:
        pytest.skip('本机没有装齐 GUI 依赖（PySide2 + NumPy 1.x）的解释器')
    proc, records = _run_probe(exe, 'import main; print("IMPORT_OK")')
    assert records, _probe_failed(proc, records)
    assert any('IMPORT_OK' in r for r in records), (
        f"import main 失败（{exe}）：\n{records}\n{getattr(proc, 'stderr', '')}")


def test_gui_windows_construct_offscreen():
    """用 offscreen 平台把主窗口与两个对话框**真的构造一遍**（不进事件循环）。

    这是 GUI 能被自动化覆盖到的极限，但覆盖的正是整理目录最容易改坏的东西：
    资源路径（图标）、assets/cfg.json（主题色）、以及全部控件与信号连接。
    构造成功 = 这些路径都还是对的。
    """
    exe = _gui_interpreter()
    if exe is None:
        pytest.skip('本机没有装齐 GUI 依赖（PySide2 + NumPy 1.x）的解释器')
    code = textwrap.dedent('''
        import os, sys
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        import main
        from PySide2.QtWidgets import QApplication
        app = QApplication(sys.argv)
        w = main.main_window()
        w.show()
        about = main.AboutDialog()
        about.show()
        unit = main.UnitDialog(w)
        app.processEvents()
        print("WINDOW_OK")
        print("title=", w.windowTitle())
        print("icon_null=", w.windowIcon().isNull())     # 图标没加载成功就会是 True
        print("about_version=", about.label.text())
        print("about_validation=", about.validation.text())
        print("about_compact=", about.height() < 400)
        print("gravity_widget_gone=", not hasattr(w, "LineEdit_4") and not hasattr(w, "label_6"))
    ''')
    proc, records = _run_probe(exe, code)
    assert records, _probe_failed(proc, records)
    out = '\n'.join(records)
    assert 'WINDOW_OK' in out, f"GUI 构造失败（{exe}）：\n{out}"
    assert 'icon_null= False' in out, (
        f"主窗口图标没加载成功 —— resource_path(APP_ICON) 多半指错了：\n{out}")
    assert '经过IAPWS-95 + MK2005 + Stull + ASHRAE + Bolton五源交叉验证' in out
    assert 'about_compact= True' in out
    assert 'gravity_widget_gone= True' in out, (
        f"主窗口里还能找到 LineEdit_4 / label_6 —— 重力加速度控件没删干净：\n{out}")
