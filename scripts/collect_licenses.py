"""Collect installed distribution license files and metadata for redistribution."""
from importlib import metadata
from pathlib import Path
import sys

sections = ['Third-party package metadata and license texts\n']
for dist in sorted(metadata.distributions(), key=lambda d: d.metadata['Name'].lower()):
    sections.append(f"\n{'=' * 72}\n{dist.metadata['Name']} {dist.version}\n")
    for key in ('License', 'License-Expression', 'Home-page', 'Project-URL'):
        for value in dist.metadata.get_all(key, []):
            sections.append(f'{key}: {value}\n')
    for path in dist.files or []:
        if any(token in path.name.lower() for token in ('license', 'copying', 'copyright')):
            source = Path(dist.locate_file(path))
            if source.is_file() and source.suffix.lower() not in ('.py', '.pyc', '.dll', '.exe'):
                sections.append(f'\n--- {path} ---\n' + source.read_text(encoding='utf-8', errors='replace') + '\n')
for root in (Path(sys.base_prefix), Path(sys.base_prefix).parent):
    for path in root.glob('LICENSE*'):
        if path.is_file():
            sections.append('\nPython runtime license\n' + path.read_text(encoding='utf-8', errors='replace'))
Path('build').mkdir(exist_ok=True)
Path('build/THIRD_PARTY_LICENSES.txt').write_text(''.join(sections), encoding='utf-8')
