"""Generate Windows PE version information from the single version source."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from core import tag

numbers = tuple(map(int, tag.lstrip('v').split('.'))) + (0,)
Path('build').mkdir(exist_ok=True)
Path('build/version.txt').write_text(f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers!r}, prodvers={numbers!r},
    mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', 'WetBulb Calculator'),
    StringStruct('FileVersion', '{tag}'),
    StringStruct('ProductName', 'WetBulb Calculator'),
    StringStruct('ProductVersion', '{tag}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
''', encoding='utf-8')
