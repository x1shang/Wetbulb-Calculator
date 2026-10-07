# -*- coding: utf-8 -*-
"""工程卫生的可执行检查。

审计报告里"产物与授权卫生""验证没有被基础设施化"两条，落到这个仓库就是
下面这几件具体的事。把它们写成断言，才能保证"修一次"变成"一直成立"。
"""
import os
import re
import subprocess
import sys

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
