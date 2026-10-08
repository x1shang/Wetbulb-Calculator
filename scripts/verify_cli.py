"""Verify packaged console output, encoding and error exit codes."""
import json
import subprocess
import sys

exe, version = sys.argv[1:]
for mode, value in (('dewpoint', '15'), ('wetbulb', '20'), ('rh', '60')):
    proc = subprocess.run([exe, '--mode', mode, '--temperature', '25', '--value', value],
                          capture_output=True, encoding='utf-8', timeout=30)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result['version'] == version
    assert len(result['results']) == 14
    assert result['results'][0]['method'] == 'Goff-水面'
    assert isinstance(result['results'][0]['result1'], float)
proc = subprocess.run([exe, '--mode', 'rh', '--temperature', '25', '--value', '-1'],
                      capture_output=True, encoding='utf-8', timeout=30)
assert proc.returncode == 2
assert json.loads(proc.stderr)['error']
print('Packaged CLI: three modes, UTF-8 and error handling OK')
