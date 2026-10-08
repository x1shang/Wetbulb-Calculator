# Versioned GUI and console executables built from the same core.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

sys.path.insert(0, str(Path(SPECPATH) / 'src'))
from core import tag

datas = [('assets', 'assets'), ('LICENSE', '.'), ('THIRD_PARTY_NOTICES.md', '.'),
         ('build/THIRD_PARTY_LICENSES.txt', '.'),
         ('examples/example.xlsx', 'examples')]
for package in ('PySide2', 'shiboken2', 'qfluentwidgets', 'numpy', 'scipy',
                'matplotlib', 'PIL', 'openpyxl'):
    datas += collect_data_files(package, includes=['**/LICENSE*', '**/COPYING*', '**/license*'])
for distribution in ('PySide2', 'shiboken2', 'PySide2-Fluent-Widgets', 'numpy',
                     'scipy', 'matplotlib', 'Pillow', 'openpyxl', 'colorthief'):
    datas += copy_metadata(distribution)
a = Analysis(['main.py'], pathex=['src', 'src/ui'], binaries=[], datas=datas,
             hiddenimports=['gui_smoke'], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='WetBulbCalculator-' + tag,
          debug=False, strip=False, upx=False, console=False,
          icon='assets/app.ico', version='build/version.txt')
c = Analysis(['src/cli.py'], pathex=['src'], binaries=[],
             datas=[('LICENSE', '.'), ('build/THIRD_PARTY_LICENSES.txt', '.')], hiddenimports=[], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=[])
cli = EXE(PYZ(c.pure), c.scripts, c.binaries, c.datas, [], name='WetBulbCLI-' + tag,
          debug=False, strip=False, upx=False, console=True, version='build/version.txt')
