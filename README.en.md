# WetBulb Calculator

> Meteorological calculations | 14 formulas | Iteration plots | Excel batch processing

![tests](https://github.com/x1shang/Wetbulb-Calculator/actions/workflows/tests.yml/badge.svg)

[中文版 →](README.md)

Developed by the RDFZ precipitation-phase research team. Calculate wet-bulb temperature,
dew point and derived moist-air parameters using three input modes and configurable units.

## Installation

Download the GUI `WetBulbCalculator-v1.3.5.exe` or console `WetBulbCLI-v1.3.5.exe`
from [Releases](https://github.com/x1shang/Wetbulb-Calculator/releases).
The same page ships `WetBulbCalculator-web-v1.3.5.html` — the single-file web version —
plus the example workbook, licenses and SHA256 checksums.

### 1.3.5 updates!

- **New: a single-file web version** ([`web/index.html`](web/index.html), ~230 KB). Double-click to
  run, works offline, and every calculation happens in your browser — nothing is uploaded.
  Its numeric core (`web/src/core.js`) is a line-by-line port of `src/core.py`, verified by
  1035 cross-checked cases plus 351 golden vectors that are regenerated from the real `core.py`
  and can be re-run from a "self-test" button inside the page.
- **No desktop-side numerical changes.** Every formula, coefficient, registered range, solver and
  derived quantity is bit-for-bit identical to v1.3.4, so the two versions can be compared directly.
  The version number was raised only so the release workflow's `tag == core.tag` check can pass.
- **Two web-version UI defects fixed**: the accent-colour picker never applied (a strict-mode
  `ReferenceError` on every drag) and the iteration chart's axis was labelled in the selected
  temperature scale while its data stayed in °C. Both now have end-to-end regression tests.
- **CI now runs the browser layer.** `tests/test_web_e2e.py` used to be skipped everywhere; it is
  the only coverage for the UI chain, and its absence is exactly why the dead colour picker went
  unnoticed. A dedicated `web-e2e` job installs Playwright + Chromium and runs it on every push.
- **New `tests/test_web_ui_parity.py`** guards the layer the numeric parity test cannot see:
  unit-conversion constants/ranges and the batch column rules, each of which is written twice
  (Python and JavaScript). A wrong factor there leaves the core perfectly correct while the
  number on screen is wrong.
- **Documented web/desktop differences.** The web version is a **subset**: it has no CLI, its batch
  export rounds to 4 decimals, keeps only columns A/B/C, and writes `#VALUE!` as text rather than a
  real Excel error value. All of these are listed on the page's own "About" tab and in the Chinese README.

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

## Web version (single-file HTML)

`web/index.html` is a self-contained page: no server, no Python, no network requests. It covers all
three input modes, all 14 formulas and their "not applicable" rules, the same unit conversions
(°C/K/°F × Pa/hPa/mmHg/cmHg/bar), the same 24 derived quantities, the interactive iteration plot,
CSV/XLSX batch import and export with the A/B/C convention and `#VALUE!` rule, JSON/CSV export,
PNG result card, share links and local storage.

It has its own version number (`2.x.y`) so you can tell at a glance whether it lags the desktop
build; the repository itself only ever tags the desktop line (`v1.x.y`). See the Chinese README for
the full list of deliberate differences.

## Development

Install requirements-dev.txt and run `pwsh -File run_tests.ps1`.
Windows CI requires the GUI tests to run; local runs skip them if dependencies are unavailable.

Web-specific checks:

```powershell
python scripts/export_vectors.py --check    # golden vectors still match core.py
python scripts/build_web.py --check         # web/index.html is not stale
python -m pytest tests/test_web_ui_parity.py -q
python -m pytest tests/test_web_e2e.py -q   # needs: pip install playwright openpyxl
                                            #         playwright install chromium
```

To build, install requirements-build.txt in Python 3.10 at an ASCII path and run
`pwsh -File build.ps1 -Python (Get-Command python).Source`.
The committed spec produces and smoke-tests both executables, and the same script verifies and
copies the web page, so one release ships three assets. Builds are not guaranteed bit-for-bit identical.
Push a new tag matching core.tag to trigger a tested release. Historical tag rewrites are documented below.

## Documentation and licensing

- [Accuracy, limitations and references](docs/精度与参考文献.md)
- [Project history and historical rewrite](docs/项目编年史.md)
- [Release notes](RELEASE_NOTES.md)
- [MIT license for project source](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md)

Fluent Widgets is used throughout the GUI; scipy and colorthief are required and declared dependencies.
The combined GUI includes GPLv3 components; the project's MIT license does not replace their licenses.
