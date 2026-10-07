# -*- coding: utf-8 -*-
"""pytest 根配置。

把仓库根目录加入 sys.path，使 tests/ 下可以 `import core`。
core.py 只依赖标准库，所以整套测试不需要 PySide2 / pandas / matplotlib，
CI 可以在空白机器上直接跑（见 .github/workflows/tests.yml）。

tests/ 是脚本目录而非包：不写 __init__.py，pytest 用默认的 prepend 导入模式
会把 tests/ 放进 sys.path，因此 `import reference_values` 也能正常工作。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (ROOT, os.path.join(ROOT, 'tests')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
