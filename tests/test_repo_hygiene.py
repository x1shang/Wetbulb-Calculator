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

# 仓库结构（v1.3.1 起）。改结构就要改这张表——它是"我们声称的布局"的唯一出处。
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
    'LICENSE',
    'requirements.txt',
    'requirements-dev.txt',
    'run_tests.ps1',
    'build.ps1',
    'conftest.py',
    '.gitignore',
    '.gitattributes',
    '.github/workflows/tests.yml',
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
    """打包必须把 src/ 与 src/ui/ 交给 PyInstaller —— 否则 exe 一启动就 ModuleNotFoundError。

    这是一次实测事故：build.ps1 第一版只传了 `--add-data`（资源文件）而没传 `--paths`，
    PyInstaller 于是把 `core` / `calculator1` / `unit` / `about` 全部记成
    "missing module ... imported by main.py"（`build/WetBulbCalculator/warn-*.txt` 里四条齐全），
    打出来的 exe 双击即弹：

        ModuleNotFoundError: No module named 'calculator1'

    根因：main.py 里的 `sys.path.insert(...)` 是**运行时**行为，PyInstaller 的静态分析
    看不见它 —— 它只认 `--paths`（等价于 spec 里的 `pathex`）与 `--hidden-import`。
    """
    script = _read('build.ps1')
    dirs = [os.path.normpath(os.path.join(ROOT, p.strip('/\\')))
            for p in re.findall(r"--paths\s+['\"]?([^'\"\s`]+)", script)]
    assert dirs, "build.ps1 没给 PyInstaller 任何 --paths（打包会漏掉 src/ 与 src/ui/ 下的模块）"

    # main.py 从源码树里 import 的每个本地模块，都必须能在 main.py 所在目录
    # （PyInstaller 总会有）或某个 --paths 目录里被静态解析到。
    main_src = _read('main.py')
    names = set(re.findall(r'^\s*from\s+([A-Za-z_]\w*)\s+import', main_src, re.M))
    names |= set(re.findall(r'^\s*import\s+([A-Za-z_]\w*)\s*$', main_src, re.M))
    root = os.path.normpath(ROOT)
    resolved = {}
    for name in sorted(names):
        for d in [root, *dirs]:
            if os.path.exists(os.path.join(d, name + '.py')):
                resolved[name] = d
                break
    local = sorted(n for n, d in resolved.items() if d != root)
    assert local == ['about', 'calculator1', 'core', 'unit'], (
        f"只有 {local} 能被 PyInstaller 静态解析到；core/calculator1/unit/about "
        f"四个都应当靠 --paths 命中（当前 --paths = {dirs}）")

    # WetBulbCalculator.spec 是 **build.ps1 的产物**（.gitignore 里 `*.spec`），不进仓库，
    # 所以只在它存在时（本机刚打过包）顺手核对一遍 pathex；干净检出/CI 上没有它是正常的。
    spec_path = os.path.join(ROOT, 'WetBulbCalculator.spec')
    if os.path.exists(spec_path):
        m = re.search(r'pathex=\[(.*?)\]', _read('WetBulbCalculator.spec'), re.S)
        spec_dirs = [e if os.path.isabs(e) else os.path.normpath(os.path.join(ROOT, e))
                     for e in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1) if m else '')]
        for name in local:
            assert any(os.path.exists(os.path.join(d, name + '.py'))
                       for d in [root, *spec_dirs]), (
                f"WetBulbCalculator.spec 的 pathex 解析不到 {name}.py（当前 {spec_dirs}）："
                "直接用 spec 打包同样会漏模块")


def test_no_personal_absolute_paths():
    """个人绝对路径（形如 C: 盘下的 Users 目录）既泄露信息，也让别人无法复现构建。

    v1.3.1 起递归扫描全部子目录（此前只看仓库根），并跳过 .venv-build：
    那是本地的虚拟环境，里面的绝对路径属于本机环境，不是仓库内容。
    例外：定义这条检测的**本文件自身**被跳过 —— 它的正则字面量必然会命中自己。
    """
    pattern = re.compile(r'[A-Za-z]:[\\/]Users[\\/][^\\/\s"\']+', re.IGNORECASE)
    skip_dirs = {'.git', '.venv-build', '.venv', 'venv', '__pycache__',
                 '.pytest_cache', '.idea', 'dist', 'build'}
    skip_files = {os.path.abspath(__file__)}
    exts = ('.py', '.md', '.json', '.txt', '.ps1', '.yml', '.yaml', '.cfg', '.toml')
    offenders = []
    for dp, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in names:
            if not name.endswith(exts):
                continue
            path = os.path.join(dp, name)
            if os.path.abspath(path) in skip_files:
                continue
            rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
            try:
                with open(path, encoding='utf-8') as f:
                    lines = f.read().splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(lines, 1):
                if pattern.search(line):
                    offenders.append(f"{rel}:{i}: {line.strip()}")
    assert not offenders, "发现个人绝对路径：\n" + "\n".join(offenders)

    # B-27：上面那条正则只认 C:\Users\...，而"本机路径"还有一种更隐蔽的形态 ——
    # 把项目自己的虚拟环境绝对路径写进注释（例如调试 Qt 插件时那条实测记录），
    # 它对别人毫无用处、还会泄露目录结构。只扫**发货文件**（main.py 与 src/**）：
    # tests/ 里的解释器探测候选是有意保留的本机提示，不算泄漏。
    venv_pattern = re.compile(r'[A-Za-z]:[\\/][^\s"\'<>]*?[\\/]\.?venv[\w.-]*[\\/]',
                              re.IGNORECASE)
    leaked = []
    for rel in [p for p in _source_files() if p == 'main.py' or p.startswith('src/')]:
        for i, line in enumerate(_read(rel).splitlines(), 1):
            if venv_pattern.search(line):
                leaked.append(f"{rel}:{i}: {line.strip()}")
    assert not leaked, ("发货文件里出现了本机虚拟环境的绝对路径（请改成通用示例路径）：\n"
                        + "\n".join(leaked))


def _git(*args):
    """运行 git 并返回 stdout；不可用时 skip。

    必须显式指定 utf-8：仓库里有中文文件名，而 Windows 上 subprocess 的
    默认编码是 gbk，会在解码阶段炸掉（stdout 变成 None）。
    """
    try:
        proc = subprocess.run(['git', *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=120,
                              encoding='utf-8', errors='replace')
    except (OSError, subprocess.SubprocessError):
        pytest.skip('git 不可用')
    if proc.returncode != 0:
        pytest.skip('当前目录不是 git 工作区')
    return proc.stdout


def test_no_tracked_file_is_gitignored():
    """`.gitignore` 只对"还没被跟踪"的文件生效：已被跟踪又被忽略的文件
    就是审计报告说的"漏网之鱼"。命令与判定方式取自审计报告附录 A。"""
    leaked = [ln for ln in _git('ls-files', '-i', '-c', '--exclude-standard').splitlines()
              if ln.strip()]
    assert not leaked, "以下文件已被跟踪却仍在 .gitignore 里：\n" + "\n".join(leaked)


def test_no_bytecode_is_committed():
    """__pycache__ 会出现在任意层级；只写 /__pycache__/* 会漏掉 tests/ 下的那些。"""
    bad = [ln for ln in _git('ls-files').splitlines()
           if '__pycache__' in ln or ln.endswith(('.pyc', '.pyo'))]
    assert not bad, "字节码文件被跟踪了：\n" + "\n".join(bad)


def test_gitattributes_pins_line_endings():
    """CI 在 Linux 上跑、开发在 Windows 上做：行尾必须由仓库决定，不由本机配置决定。"""
    path = os.path.join(ROOT, '.gitattributes')
    assert os.path.exists(path), "缺少 .gitattributes：行尾会随各人的 core.autocrlf 漂移"
    assert 'text=auto' in _read('.gitattributes')


def test_ci_workflow_exists_and_runs_the_suite():
    path = '.github/workflows/tests.yml'
    assert os.path.exists(os.path.join(ROOT, path)), f"缺少 {path}"
    src = _read(path)
    assert 'pytest' in src, "CI 必须真的跑 pytest"
    assert 'core.py' in src, "CI 必须跑零依赖的等价性回归"


def test_ci_workflow_declares_read_only_permissions():
    """最小权限：CI 只需要读代码。"""
    src = _read('.github/workflows/tests.yml')
    assert re.search(r'permissions:\s*\n\s*contents:\s*read', src), \
        "workflow 顶层应声明 permissions: contents: read"


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
    """matplotlib 3.5.3 / pandas 1.3.5 是针对 NumPy 1.x 编译的 C 扩展，
    元数据里只要求 numpy>=1.17、没有上界；不写上界，空白机器上 pip 会装
    NumPy 2.x，程序连 `import matplotlib.pyplot` 都过不去。"""
    numpy_lines = [ln.replace(' ', '') for ln in _requirement_lines(_read('requirements.txt'))
                   if ln.lower().startswith('numpy')]
    assert numpy_lines, "requirements.txt 必须显式约束 numpy（否则全新安装装到 NumPy 2.x 就崩）"
    assert all('<2' in ln for ln in numpy_lines), \
        f"numpy 必须有 <2 上界，实际是：{numpy_lines}"


def test_readme_states_a_python_version_that_can_actually_install():
    """README 曾声称支持"Python 3.6 及以上"，而 PySide2==5.15.2.1 在 3.11+ 上没有轮子。"""
    readme = _read('README.md')
    assert '3.6+' not in readme, "README 不应再声称支持 Python 3.6+（PySide2 装不上）"
    m = re.search(r'Python\s*3\.(\d+)\s*[–~-]\s*3\.(\d+)', readme)
    assert m, "README 应写明实际支持的 Python 版本区间"


def test_readme_test_count_matches_reality():
    """README 里写的"N 条断言"必须等于实际收集到的用例数。

    数字一过期，文档就开始骗人——而"文档里写着 236 条、实际只有 12 条"
    正是审计报告批评的那类不一致。这里让它自动对账。
    """
    m = re.search(r'(\d+)\s*条断言', _read('README.md'))
    assert m, "README 应写明测试用例数（例如「239 条断言」）"
    claimed = int(m.group(1))

    proc = subprocess.run([sys.executable, '-m', 'pytest', '-q', '--collect-only'],
                          cwd=ROOT, capture_output=True, text=True, timeout=300,
                          encoding='utf-8', errors='replace')
    assert proc.returncode == 0, f"收集用例失败：\n{proc.stdout}\n{proc.stderr}"
    found = re.search(r'(\d+)\s+tests?\s+collected', proc.stdout)
    assert found, f"无法解析收集结果：{proc.stdout[-400:]}"
    actual = int(found.group(1))
    assert actual == claimed, (
        f"README 写的是 {claimed} 条，实际收集到 {actual} 条 —— 请同步更新 README "
        f"（「开发与验证」「1.3.1 更新内容」两处）")


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
    ''')
    proc, records = _run_probe(exe, code)
    assert records, _probe_failed(proc, records)
    out = '\n'.join(records)
    assert 'ERRBAR' not in out, f"计算过程弹出了错误条（说明异常被吞掉了）：\n{out}"
    # 表头 1 行 + 14 条公式；注意列表末尾还有一行空串，所以是 16
    assert 'MODE0_ROWS 16' in out, f"模式0 没有把结果填进列表：\n{out}"
    assert 'MODE2_ROWS 16' in out, f"模式2 没有把结果填进列表：\n{out}"
    # 数值锚点：与 docs/项目编年史.md 记录的实测值一致（干 25 / 露 15 → Goff-水面 18.6186 ℃）
    assert "MODE0_GOFF ['Goff-水面:  18.6186℃  " in out, (
        f"模式0 的 Goff-水面 结果与编年史记录的 18.6186 不一致：\n{out}")


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

    GUI 不在 CI 覆盖范围内（装不上 PySide2），而这类拼写错只在用户点开
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
    （matplotlib 3.5.3 / pandas 1.3.5 是针对 NumPy 1.x 编译的）。
    CI 上两个都满足不了，所以依赖它的用例会 skip —— 它们服务于本地提交前自查。
    """
    probe_src = textwrap.dedent('''
        import importlib.util as u
        ok = all(u.find_spec(m) for m in
                 ("PySide2", "qfluentwidgets", "matplotlib", "pandas", "numpy"))
        if ok:
            import numpy
            ok = numpy.__version__.split(".")[0] == "1"
        print("READY" if ok else "MISSING")
    ''')
    candidates = [
        os.environ.get('WETBULB_GUI_PYTHON'),                         # 手动指定（任意路径）
        os.path.join(ROOT, '.venv-build', 'Scripts', 'python.exe'),   # 打包/自测用的 3.10 环境
        sys.executable,
        r'D:\dsh\init\.venv-qyb310\Scripts\python.exe',               # build.ps1 挑中的打包环境
        r'D:\dsh\init\.py310\python.exe',
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
        print("about_refs_chars=", len(about.references.toPlainText()))
        print("about_refs_width=", about.references.width())
        print("about_has_grades=", all(
            k in about.references.toPlainText()
            for k in ("WMO-No. 8", "ASHRAE", "Stull", "Goff", "Hyland", "Buck",
                      "Marti", "Murphy", "Fritschen", "周西华")))
        print("gravity_widget_gone=", not hasattr(w, "LineEdit_4") and not hasattr(w, "label_6"))
    ''')
    proc, records = _run_probe(exe, code)
    assert records, _probe_failed(proc, records)
    out = '\n'.join(records)
    assert 'WINDOW_OK' in out, f"GUI 构造失败（{exe}）：\n{out}"
    assert 'icon_null= False' in out, (
        f"主窗口图标没加载成功 —— resource_path(APP_ICON) 多半指错了：\n{out}")
    # 关于框里的参考文献必须是"真的写进去了"，而不是空白面板
    assert 'about_has_grades= True' in out, (
        f"关于框的参考文献面板缺内容（应包含 WMO/ASHRAE/Stull/Goff/Wexler/Buck 与周西华）：\n{out}")
    assert 'about_refs_chars= 0' not in out, f"参考文献面板是空的：\n{out}"
    assert 'gravity_widget_gone= True' in out, (
        f"主窗口里还能找到 LineEdit_4 / label_6 —— 重力加速度控件没删干净：\n{out}")
