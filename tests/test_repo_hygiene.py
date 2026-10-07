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

import pytest

import core

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def test_core_has_no_gui_dependencies():
    """core.py 必须保持零 GUI 依赖（审计肯定过的那条架构性质）。
    正是这一点让 CI 能在装不上 PySide2 的 Linux 空白机器上验证计算核心。"""
    src = _read('core.py')
    for forbidden in ('PySide2', 'qfluentwidgets', 'matplotlib', 'pandas', 'numpy'):
        assert forbidden not in src, f"core.py 不应依赖 {forbidden}"


def test_core_selfcheck_passes():
    """`python core.py` 是零依赖的等价性回归入口，必须能以 0 退出。"""
    proc = subprocess.run([sys.executable, 'core.py'], cwd=ROOT,
                          capture_output=True, text=True, timeout=120,
                          encoding='utf-8', errors='replace')
    assert proc.returncode == 0, f"core.py 自检失败：\n{proc.stdout}\n{proc.stderr}"
    assert 'OK' in proc.stdout


def test_no_personal_absolute_paths():
    """个人绝对路径（C:/Users/<用户名>/…）既泄露信息，也让别人无法复现构建。"""
    pattern = re.compile(r'[A-Za-z]:[\\/]Users[\\/][^\\/\s"\']+', re.IGNORECASE)
    offenders = []
    for name in os.listdir(ROOT):
        if not name.endswith(('.py', '.md', '.json', '.txt', '.ps1', '.yml')):
            continue
        for i, line in enumerate(_read(name).splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{name}:{i}: {line.strip()}")
    assert not offenders, "发现个人绝对路径：\n" + "\n".join(offenders)


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


def test_main_import_still_works_when_gui_stack_is_available():
    """若本机装齐了 GUI 依赖，则 `import main` 必须成功。

    这是"空白机器照 README 能不能跑起来"的第一道闸（第二道是启动窗口）。
    CI 上装不上 PySide2（只提供到 Python 3.10 的轮子），因此这里会 skip ——
    它服务于本地提交前自查。按第 ⑤ 步建好 `.venv-build` 之后，它会自动开始跑。

    解释器必须同时满足：Python ≤3.10（PySide2 有轮子）与 NumPy 1.x
    （matplotlib 3.5.3 / pandas 1.3.5 是针对 NumPy 1.x 编译的）。
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
        os.path.join(ROOT, '.venv-build', 'Scripts', 'python.exe'),   # 第⑤步建立的打包环境
        sys.executable,
        r'D:\dsh\init\.py310\python.exe',
    ]
    ready = None
    for exe in candidates:
        if not exe or not os.path.exists(exe):
            continue
        try:
            probe = subprocess.run([exe, '-c', probe_src], capture_output=True, text=True,
                                   timeout=240, encoding='utf-8', errors='replace')
        except (OSError, subprocess.SubprocessError):
            continue
        if 'READY' in (probe.stdout or ''):
            ready = exe
            break
    if ready is None:
        pytest.skip('本机没有装齐 GUI 依赖（PySide2 + NumPy 1.x）的解释器')
    proc = subprocess.run([ready, '-c', 'import main; print("IMPORT_OK")'],
                          cwd=ROOT, capture_output=True, text=True, timeout=300,
                          encoding='utf-8', errors='replace')
    assert 'IMPORT_OK' in (proc.stdout or ''), (
        f"import main 失败（{ready}）：\n{proc.stdout}\n{proc.stderr}")
