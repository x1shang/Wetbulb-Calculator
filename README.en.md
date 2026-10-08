# WetBulb Calculator

> Meteorological calculations | 14 formulas | Iteration plots | Excel batch processing

![tests](https://github.com/x1shang/Wetbulb-Calculator/actions/workflows/tests.yml/badge.svg)

[中文版 →](README.md)

Developed by the RDFZ precipitation-phase research team. Calculate wet-bulb temperature,
dew point and derived moist-air parameters using three input modes and configurable units.

## Installation

Download the GUI `WetBulbCalculator-v1.3.3.exe` or console `WetBulbCLI-v1.3.3.exe`
from [Releases](https://github.com/x1shang/Wetbulb-Calculator/releases).
The example workbook, licenses and SHA256 checksums are separate release assets.

### 1.3.3 updates!

- JSON command-line interface without GUI dependencies.
- Invalid spreadsheet rows now contain Excel error cells and explanations.
- Automated GUI and batch tests, plus packaged application checks from a Chinese path.
- Versioned executables and tag-triggered CI releases.
- Compact About dialog and consolidated scientific documentation.

## Source and CLI

The GUI requires Python 3.10. The standard-library-only core/CLI is tested on 3.10 and 3.12.

```powershell
python -m pip install -r requirements.txt
python main.py
python main.py --cli --mode rh --temperature 25 --value 60 --pressure 1013.25
```

Modes name the known value: `dewpoint`, `wetbulb`, or `rh`.
Use Celsius, hPa and RH percent. `--method "Goff-水面"` selects one formula.
For `rh`, result1/result2 are dew point/wet bulb; otherwise result1 is the requested temperature.
Results are JSON; unavailable formulas retain text statuses. Invalid input exits with code 2 and a JSON error on stderr.
The console executable accepts the same arguments without `--cli`.

## Batch calculations

Place one input xlsx beside the GUI executable (project root for source runs).
Keep A/B/C column headers for dry bulb, known value and pressure; choose the mode and units in the GUI.
Results are appended and saved to `result_<input>.xlsx`; an existing result with that name is overwritten.
Files starting with `result_` or `~$` are ignored. Invalid rows produce `#VALUE!` plus an error explanation.
The input is preserved. Goff water/ice is selected by the dry-bulb temperature sign.

## Development

Install requirements-dev.txt and run `pwsh -File run_tests.ps1`.
Windows CI requires the GUI tests to run; local runs skip them if dependencies are unavailable.
To build, install requirements-build.txt in Python 3.10 at an ASCII path and run
`pwsh -File build.ps1 -Python (Get-Command python).Source`.
The committed spec produces and smoke-tests both executables. Builds are not guaranteed bit-for-bit identical.
Push a new tag matching core.tag to trigger a tested release. Historical tag rewrites are documented below.

## Documentation and licensing

- [Accuracy, limitations and references](docs/精度与参考文献.md)
- [Project history and historical rewrite](docs/项目编年史.md)
- [Release notes](RELEASE_NOTES.md)
- [MIT license for project source](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md)

Fluent Widgets is used throughout the GUI; scipy and colorthief are required and declared dependencies.
The combined GUI includes GPLv3 components; the project's MIT license does not replace their licenses.
