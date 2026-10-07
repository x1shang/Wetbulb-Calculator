# -*- coding: utf-8 -*-
"""pytest 根配置。

把仓库根、src/、tests/ 加入 sys.path，使 tests/ 下可以 `import core`，
也可以 `import reference_values`。

core.py 只依赖标准库，所以整套测试不需要 PySide2 / pandas / matplotlib，
CI 可以在空白机器上直接跑（见 .github/workflows/tests.yml）。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (ROOT, os.path.join(ROOT, 'src'), os.path.join(ROOT, 'tests')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
