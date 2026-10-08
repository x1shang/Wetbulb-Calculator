# WetBulb Calculator

> A psychrometric calculator for wet-bulb and dew-point temperature | 14 international
> saturation-vapour-pressure formulas | visualised iteration | batch calculation

![tests](https://github.com/x1shang/Wetbulb-Calculator/actions/workflows/tests.yml/badge.svg)

[中文说明 →](README.md)

Developed by the RDFZ Precipitation-Phase Study Group (RDFZ 降水相态研究性学习小组).

---

## What it is

WetBulb Calculator is a desktop tool for computing wet-bulb temperature, dew-point
temperature and a set of derived moist-air parameters. It ships 14 published
saturation-vapour-pressure formulas, unit conversion (℃ / ℉ / K and hPa / Pa / mmHg /
cmHg / bar), a live plot of the Newton iteration, and one-click batch calculation over
an xlsx file.

It is a sub-project of our precipitation-phase temperature-profile work, released in the
hope that it is useful to other people doing meteorology.

## Highlights

- **Verifiable precision.** The 14 formulas are compared against the **IAPWS official
  equations** across each formula's entire registered range; the reference-grade ones
  (Goff, Wexler) stay within **0.06 %**, and even the coarsest (`Marti`, ice) is stated at
  2.01 %. Every number in this README is re-checked by CI on every push —
  see [Measured accuracy](#measured-accuracy) below.
- **Three modes:** dew point → wet bulb, wet bulb → dew point, and relative humidity → both.
- **Batch calculation** over a whole xlsx column at once.
- **20+ derived parameters** per result: enthalpy, mixing ratio, virtual temperature,
  potential temperature, speed of sound, LCL, and more.
- **Full unit support** for temperature and pressure, switchable at runtime.
- **Input validation in the engine, not just the GUI.** Temperature ∈ [−150, 200] ℃,
  pressure ∈ (0, 1200] hPa and relative humidity ∈ (0, 100] % are enforced inside the
  computation core, so the batch path is protected too. Invalid input produces an explicit
  error instead of a number.
- **Applicability by temperature, not by guess.** A formula is marked "not applicable"
  based on the temperatures actually used in the calculation, not on the initial guess the
  user happened to type.

---

## Measured accuracy

> Every table below is recomputed by `python -m pytest -q`. The numbers in the tables *are*
> the numbers in the assertions — if the code regresses, CI turns red rather than the
> documentation going quietly stale.

### Saturation vapour pressure vs the IAPWS official equations, swept over each formula's **entire registered range**

| Formula | Registered range | Max deviation | Worst point |
|---|---|---:|---|
| Goff (water) | −10 – 100 ℃ | 0.06 % | 68 ℃ |
| Goff-Gratch 1946 (water) | −10 – 100 ℃ | 0.12 % | −10 ℃ |
| Wexler (water) | −10 – 200 ℃ | 0.02 % | 40 ℃ |
| Arden / Buck-1996 3-parameter (water) | 0 – 50 ℃ | 0.04 % | 30 ℃ |
| Buck (water) | 0 – 50 ℃ | 0.14 % | 50 ℃ |
| Tetens (water) | 0 – 50 ℃ | 0.15 % | 45 ℃ |
| Magnus (water) | 0 – 60 ℃ | 0.31 % | 28 ℃ |
| August (water) | 0 – 60 ℃ | 0.38 % | 60 ℃ |
| Gili (water) | −10 – 20 ℃ | 0.14 % | −10 ℃ |
| Wexler (ice) | −100 – 0 ℃ | 0.03 % | −47 ℃ |
| Goff-Gratch (ice) | −100 – 0 ℃ | 0.12 % | −100 ℃ |
| Magnus (ice) | −65 – 0 ℃ | 0.20 % | −65 ℃ |
| Buck (ice) | −80 – 0 ℃ | 0.83 % | −80 ℃ |
| Marti (ice) | −103 – 0 ℃ | 2.01 % | −82 ℃ |

> **How this table is produced.** `tests/test_esat_domain_sweep.py` samples 241 evenly spaced
> points across each formula's *own* registered interval and compares them against the
> **IAPWS-95** saturation line (Wagner & Pruß 2002) for water and the **IAPWS 2011**
> sublimation-pressure equation for ice. The worst deviation is the third column.
>
> Why not the published meteorological table any more: that table's tabulated values are
> themselves 0.02 %–0.10 % low relative to IAPWS (there is an assertion quantifying this),
> and it only has 10 sample points — **the domain endpoints were never examined**. That is
> how `Marti (ice)` sat at −9.93 % at −150 ℃ for so long (it was registered down to −150 ℃
> while its fit only covers 170–273 K). The published table is kept as a **second,
> independent** reference in `tests/test_esat_reference.py`.
>
> **Two coarse formulas deserve attention:** `Buck (ice)` is 0.83 % off at −80 ℃ and
> `Marti (ice)` 2.01 % at −82 ℃. That is each formula's own accuracy, not an implementation
> bug; their registered ranges were narrowed in v1.3.2 to what their sources actually claim.
>
> **`Arden (water)` is no longer the mislabelled one.** Since v1.3.2 it implements Buck's
> (1996) three-parameter form verbatim, giving ≤ 0.04 % over 0–50 ℃ (it used to be
> +3.51 % at 50 ℃ and +12.56 % at 100 ℃).

### How many formulas actually return a result at temperature extremes

| Dry-bulb | RH | Formulas returning a result |
|---|---:|---:|
| −150 ℃ | 60 % | **0 / 14** |
| −100 ℃ | 60 % | 3 / 14 |
| −80 ℃ | 60 % | 4 / 14 |
| 0 ℃ | 60 % | **14 / 14** |
| 45 ℃ | 60 % | 8 / 14 |
| +150 ℃ | 50 % | **0 / 14** |
| +200 ℃ | 50 % | **0 / 14** |

> Do not be misled by "registered range −150 – 200 ℃": at +150 and +200 ℃ **not a single
> formula returns a result**. The practically usable range is roughly −80 – 50 ℃; outside
> it the GUI says "not applicable" rather than inventing a number.

### Independent cross-checks of the wet-bulb temperature

| Reference | What it is | Max deviation observed |
|---|---|---|
| ASHRAE adiabatic-saturation equation | the **definition** of thermodynamic wet-bulb temperature | **0.42 K** (@50 ℃ / 5 % RH; ≈0.25 K over 0–30 ℃) |
| Stull (2011) empirical fit | fully independent published formula, no shared code | 1.77 K (@ −8 ℃ / 10 % RH — that is **Stull's own** error) |
| ASHRAE / Vaisala dew-point tables | published table values | 0.30 K (within assertion tolerance) |

> This project solves the meteorological psychrometric equation
> `e = e_sat(T_w) − A·p·(T − T_w)` with
> `A = 0.000660(1 + 0.00115·T_w)` over water and `0.000582(1 + 0.00115·T_f)` over ice,
> taken verbatim from FAO *Frost Protection* Appendix 3, Eqs. (A3.15)/(A3.16).
> Its difference from the ASHRAE definition is the error of that approximation itself:
> a smooth, monotonic 0.02 → 0.42 K drift with rising temperature and drier air. If that
> difference ever becomes erratic or changes sign, the solver is broken and CI says so.
>
> **The Newton solver itself is exact**: it agrees with an independent `scipy.brentq` root
> to 8×10⁻¹⁴ K and leaves an equation residual of 9×10⁻¹⁴ hPa. All of the error above comes
> from the equation form, none from the algorithm.
>
> **The 1.77 K in the Stull row is not this project's error**: at that same grid point this
> project is within 0.05 K of the ASHRAE definition. Stull (2011) itself drifts in the
> cold/dry corner, which is exactly why that row is only a coarse sanity check.

---

## Installation and running

Download the latest release — that is all most users need.

Stable releases: `v1.1.3`, `v1.2.2`, `v1.3.0`, `v1.3.1`, `v1.3.2`.
Do **not** use `v1.0.0`, `v1.0.1` or `v1.2.0`: they contain serious bugs.

### v1.3.2 — second numerical-fix release (full formula re-derivation)

> **v1.3.2 does not produce the same numbers as v1.3.1.** One formula constant, one
> equation coefficient, three derived-quantity physics errors and five over-wide
> applicability ranges were fixed. **Use v1.3.2 or later.**
>
> Wet-bulb temperature, mode-1 dew point, enthalpy, speed of sound and LCL all change.
> The **mode-2 dew point does not** (it only inverts `e_sat`, independently of the
> psychrometric equation).

- **Fixed** — `Gili (water)`: removed the `+0.00141966` term in the exponent, which has no
  traceable source. v1.3.1 only changed the leading factor (980.66 → 1013.25) and left the
  actual defect in place: with that term the formula returns **1016.57 hPa at its own
  reference point 373.15 K**, where it must by construction return 1013.25 hPa (1 atm).
  Root cause: the legacy code read `980.66·10^(0.00141966+…)`, but 980.665 hPa (1 technical
  atmosphere) pairs with `lg(1013.25/980.665) = 0.0141966` — `0.00141966` is exactly that
  value divided by 10. Reference temperature also corrected to 373.15 K per the one source
  located. Full-range deviation **0.28 % → 0.14 %**.
- **Fixed** — the **A coefficient of the psychrometric equation** went from `0.000667` back
  to the value in the cited source (FAO *Frost Protection* Appendix 3), `0.000660`. This is
  the continuation of the project's own bug B-02: the derivative term used `0.00066` while γ
  used `0.000667`, and the "fix" at the time standardised both on the **wrong** one. The ice
  coefficient `0.000582` from the same appendix (Eq. A3.16) is now used for ice formulas --
  the appendix answers the question the README used to list as undecided. Max deviation vs
  the ASHRAE definition **0.52 K → 0.42 K** (0.25 K over 0–30 ℃).
- **Fixed** — `Arden (water)`: its coefficients are Buck's (1996) **three-parameter** form but
  were squeezed into the two-parameter `magnus` family, dropping the `−T/234.5` correction
  (+0.91 % at 25 ℃, +3.51 % at 50 ℃, **+12.56 %** at 100 ℃). A new `buck96` family now
  implements it verbatim: ≤ 0.04 % over 0–50 ℃.
- **Fixed** — **enthalpy** used the *vapour* specific heat where the *liquid* one is required.
  `h = c_pa·T + w·(L_v(T) + c_w·T)` needs `c_w = 4.186 kJ/(kg·K)`, not 1.864. At 25 ℃ /
  RH ≈ 54 %: 51.63 → **52.25 kJ/kg** (ASHRAE's standard form gives 52.27; the old value was
  1.23 % low).
- **Fixed** — the mixing basis for the **moist-air adiabatic index**. Specific heats are
  per unit *mass*, so they must be weighted by **mass** fraction; the old code weighted them
  by *mole* fraction. γ 1.397006 → **1.397846**, speed of sound 346.885 → **346.989 m/s**.
- **Fixed** — **LCL** now uses Bolton's (1980) published Eq. (21), with `T` and `T_d` in
  **kelvin**. The old code used a Celsius variant that also substituted `ln(RH)` for
  `ln(T/T_d)` and was off by up to +2.6 K (+0.93 K at 25 ℃/15 ℃). Now 25 ℃/15 ℃ gives
  **12.72 ℃**, within 0.03 K of the `125(T−T_d)` m rule of thumb.
- **Fixed** — **five over-wide registered ranges** (the registered range is what the engine
  uses to decide "not applicable", so declaring it too wide tells the user a formula works
  where it does not):

  | Formula | Was | Now | Deviation outside the old range |
  |---|---|---|---|
  | Buck (water) | 0 – 80 ℃ | 0 – 50 ℃ | +1.11 % at 80 ℃ |
  | Arden (water) | 0 – 100 ℃ | 0 – 50 ℃ | +12.56 % at 100 ℃ |
  | Wexler (ice) | −150 – 10 ℃ | −100 – 0 ℃ | +0.47 % at −150 ℃ |
  | Marti (ice) | −150 – 0 ℃ | −103 – 0 ℃ | −9.93 % at −150 ℃ |
  | Goff-Gratch (ice) | −100 – 10 ℃ | −100 – 0 ℃ | ice does not exist above 0 ℃ |

  > The last row is a behaviour change: at, say, +5 ℃ the ice formulas now report
  > **"not applicable"** instead of displaying a frost point next to the water results.
  > At exactly 0 ℃ both phases are still available (the 14/14 row above is unchanged).
- **Added** — a **full-domain sweep per formula** (`tests/test_esat_domain_sweep.py` +
  `tests/reference_iapws.py`) against the IAPWS official equations, replacing "10 discrete
  sample points".
- **Added** — the README accuracy table is now **reconciled automatically**: if a number in
  it is smaller than the measurement, CI turns red.

### v1.3.1 — numerical-fix release

> **v1.3.1 does not produce the same numbers as v1.3.0**, because three formula defects
> were fixed. Use v1.3.1 or later.

- **Fixed** — `Gili`: the leading factor was 980.66 (1 technical atmosphere) instead of
  1013.25 hPa, which made the formula read a constant **3.0 % low** over its whole range.
  Now within 0.28 %.
  > ⚠️ **This only treated the symptom** — the real cause was the decimal-shifted constant
  > term on the same line, removed in v1.3.2 (see above).
- **Fixed** — `Goff-Gratch 1946`: the 4th coefficient was `1.3816e-5` instead of
  `1.3816e-7` (a factor of 100), making the cold end read −3.5 % at 0 ℃ and −1.7 % at 10 ℃.
  Now within 0.12 % everywhere.
- **Fixed** — the analytic derivative of the `goff` family had a wrong second term, so the
  *slope* was wrong by 40 % (Goff2), 26 % (Goff) and 18 % (Goff ice). The root was
  unaffected, which is exactly why checking only the results never caught it.
- **Fixed** — three derived quantities in the extended-parameter panel: speed of sound
  (specific heat capacity was combined with the *molar* gas constant: 295 → 347 m/s),
  vapour density and mixing ratio (used the wet-bulb saturation pressure instead of the
  actual vapour pressure), saturated mixing ratio (11.89 → 20.08 g/kg).
- **Fixed** — dimensional error in the latent-heat term of equivalent potential
  temperature (`L_v` in kJ/kg divided by `Cp` in J/(kg·K) shrank the latent heat by 1000×,
  collapsing θe into θ).
- **Fixed** — **the application could not start at all from a directory whose path contains
  non-ASCII characters** (e.g. a Chinese folder name). PySide2 passes its own path through a
  narrow-character conversion, so `…\晴雨表\` became `…\???\`, `QLibraryInfo` reported a
  non-existent plugin directory, and Qt aborted with
  `Could not find the Qt platform plugin "windows"`. Fixed by exporting the real path via
  `QT_PLUGIN_PATH`. Details in `main.py`.
- **Added** — engine-level input validation; applicability determined by the temperatures
  actually used; `tests/` with external-reference regression (254 assertions at v1.3.1; 299 now); GitHub
  Actions CI; `run_tests.ps1`.
- **Removed** — **the "local gravity" input** (widget, the `g` key in `cfg.json`, and its
  read/write helpers). It never entered a single calculation since v1.2.0 (see the known
  limitations and B-20 in `docs/项目编年史.md`), and no quantity this tool computes depends
  on `g` — the only related unit, mmHg/cmHg, is a **defined** value
  (1 mmHg = 133.322387415 Pa) and has nothing to do with gravity. A box that silently
  changes nothing is worse than no box at all.
- **Fixed** — **the packaged exe crashed on launch** (`ModuleNotFoundError: No module named
  'calculator1'`). `build.ps1` passed `--add-data` (assets) but no `--paths`, while `main.py`
  injects `src/` and `src/ui/` into `sys.path` at **runtime** — invisible to PyInstaller's
  static analysis. As a result `core`/`calculator1`/`unit`/`about` were all absent from the
  bundle (all four listed in `build/*/warn-*.txt`). The build now passes
  `--paths "src" --paths "src/ui"`, verifies the warn file afterwards and aborts if a local
  module is missing; a regression guard was added to `tests/test_repo_hygiene.py`.
- **Fixed** — the relative-humidity parameter of `calculate_both` and `derive_moist_air` had
  the same name with different units (percent vs fraction). Now renamed to `rh_pct` /
  `rh_frac` and pinned by tests.
- **Fixed** — the GUI regression test was permanently red locally and green in CI on Chinese
  Windows (child wrote cp936 into the pipe, parent decoded UTF-8, so `℃` became mojibake).
  The probe now writes UTF-8 JSON to a file, and `PYTHONUTF8=1` is set in `run_tests.ps1`/CI.

### Source dependencies

- **Python 3.6 – 3.10 (3.10 recommended)**
  > `PySide2==5.15.2.1` only publishes wheels up to Python 3.10; **3.11+ cannot install it**.
- Runtime / packaging dependencies (`requirements.txt`):
  ```
  matplotlib==3.5.3
  openpyxl==3.1.3
  pandas==1.3.5
  PySide2==5.15.2.1
  PySide2_Fluent_Widgets==1.7.6
  numpy>=1.21,<2     # upper bound is mandatory; see below
  ```
  > **The NumPy upper bound is not optional.** matplotlib 3.5.3 and pandas 1.3.5 are C
  > extensions compiled against NumPy 1.x and their metadata only requires `numpy>=1.17`
  > with no upper bound, so a fresh install pulls NumPy 2.x and
  > `import matplotlib.pyplot` fails with `AttributeError: _ARRAY_API not found`.
- **Running the computation core or the tests needs none of the above**: `src/core.py`
  depends only on the standard library, and the tests need only `pytest`
  (`requirements-dev.txt`).

### Running from source

```powershell
python -m venv .venv                  # with a Python 3.10 interpreter
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

---

## Development and verification

### One command for all checks (local)

```powershell
pwsh -File run_tests.ps1
```

It runs, in order: syntax compilation → static analysis → core equivalence regression →
correctness verification against published reference values.

### Running the pieces separately

```bash
python src/core.py                   # equivalence regression (stdlib only)
python -m pytest -q                  # correctness vs IAPWS/ASHRAE references (299 assertions)
python -m pyflakes main.py src/core.py   # undefined names / unused imports
```

> The split matters: `python src/core.py` is a **self-regression** — it only compares against
> the previous version's own output, so it cannot discover an inherited bias. **Correctness
> must be anchored to external references**, which is what `tests/` does.

### CI

`.github/workflows/tests.yml` runs on every push and pull request on a clean Linux machine,
across Python 3.10 and 3.12: core regression, reference-value verification, syntax
compilation of every source file, and static analysis. **The only thing that decides
pass/fail is the exit code** — no printed message is read, because `print("verified")` is
not a test.

**The green badge at the top** comes from that run. It is not an image file but a live SVG:

```
https://github.com/<user>/<repo>/actions/workflows/<workflow-filename>/badge.svg
```

One line in the README (`![tests](that-url)`) renders it; it reads `passing` (green) when CI
passes and `failing` (red) when it does not. Note the URL uses the **file name**
(`tests.yml`), not the `name:` inside the workflow.

### Building the exe

```powershell
pwsh -File build.ps1
```

The script picks a suitable Python environment, runs the tests first, builds, and prints the
size and SHA256.

> ⚠️ **The one hard requirement: the packaging interpreter must live on a pure-ASCII path.**
> PySide2 passes its own package directory through a narrow-character conversion, so a
> non-ASCII path turns into `???`, and PyInstaller's Qt hook then fails with
> `Qt plugin directory '.../???/...' does not exist!`.
>
> Two measured facts worth not re-discovering: exporting `QT_PLUGIN_PATH` **does not help** —
> that variable only affects plugin *loading* at runtime, not what `QLibraryInfo` returns;
> and the **project** path being non-ASCII is fine, only the interpreter's path must be clean.
> Hence `.venv-build` inside this repo cannot be used for packaging, and the script skips it.
>
> Also: PyInstaller output is **not bit-reproducible** — different build paths or times give
> different SHA256 values. The hash in a release note only proves that the file you downloaded
> is the one that was built.

### Repository layout

```
main.py            entry point: GUI, event wiring, unit conversion, batch calculation
src/core.py        computation core: formula registry, solvers, validation, derived
                   parameters — zero GUI dependencies
src/ui/            pyuic5-generated interface code (calculator1.py, unit.py, about.py)
assets/            app.ico, err.ico, default cfg.json, screenshots
examples/          sample batch input
tests/             external-reference regression suite (pytest)
docs/              project chronicle, improvement handbook, references, CI primer
legacy/sample.py   pre-refactor reference implementation (kept for reading, unused)
conftest.py        lets tests/ import core
run_tests.ps1      local one-command check
build.ps1          local exe packaging (see "Building the exe")
```

### Adding a formula

```python
register_formula('name', 'family', (coefficients…), min_temp, max_temp)
```

A *family* (`magnus` / `goff` / `wexler` / `gili` / `marti`) supplies `esat`, `dedt`
(analytic derivative) and optionally `invert`. After registering a formula, add a row to
the tolerance table in `tests/test_esat_reference.py` so CI keeps an eye on its accuracy.

---

## Batch calculation

1. Choose a calculation mode and units on the main page.
2. Copy dry-bulb temperature into column A of the xlsx, the dew point / wet bulb / relative
   humidity (whichever the mode needs) into column B, and pressure into column C.
3. Click *batch calculate*.

**Notes**

- Keep exactly one xlsx file in the same folder as the executable.
- The first row must contain columns A, B and C.
- Results are written to a new file.
- Batch mode uses `Goff (water)` for dry-bulb ≥ 0 ℃ and `Goff (ice)` below 0 ℃. A row with
  invalid input is left blank; it does not abort the whole file.

---

## Artifact and licensing policy

> This section is a contract with our future selves. The git history already carries ~98 MB
> of build output (`dist/湿球温度计.exe` 47 MB, `build/*.pkg` 47 MB) that cannot be removed
> and must not happen again.

1. **Generated files never enter history.** `dist/`, `build/`, `*.exe`, `*.pkg`, `*.pyz` go
   to release assets or are built at release time. Before committing a file larger than
   5 MB, ask whether it belongs in history.
2. **One version, one tag; tags never move.** `v1.3.0` must always point at the same commit.
   Fix a bug and cut a new tag — never `git tag -d` and recreate.
3. **Every release note answers three questions:** what changed (user-visible), which bugs
   were fixed (with symptoms), and what is known to be broken.
4. **Licence.** MIT — see `LICENSE`. Third-party material must be credited with its licence.
5. **Attribution.** Contributors appear both in the Copyright line of `LICENSE` and in the
   contributor list of this README.

---

## Disclaimer

- Released under the MIT licence.
- Please credit the source when reposting on social media.
- The software aims to give the most accurate result available, but over-reliance on it
  will make you miss scientific discoveries.
- All parameters reflect the state of the literature as of April 2025.

---

## Known limitations

> This section is as important as the accuracy tables above: **if a tool cannot state its
> own boundaries, its output cannot be trusted.** Each item below is backed by an assertion
> or a code comment — none of it is hearsay.

1. **The hot end is unusable.** At +150 ℃ and +200 ℃ none of the 14 formulas returns a
   result. The registered range reaches 200 ℃; that is a declaration, not a capability.
2. **The wet-bulb equation is the psychrometric approximation.** It differs from the ASHRAE
   adiabatic-saturation definition by 0.02–0.42 K (growing with temperature and drier air;
   about 0.25 K over 0–30 ℃). A strictly thermodynamic wet-bulb temperature would require
   the adiabatic-saturation equation. This is the **largest error source** in the tool, and
   the only one that is a *definition choice* rather than an implementation defect.
3. **The A coefficient follows the selected phase.** Water families use FAO's `0.000660`,
   ice families `0.000582` (Appendix 3, Eqs. A3.15/A3.16). But the wet bulb's own saturation
   pressure still comes from the selected family's `e_sat`: picking `Goff (water)` at a dry
   bulb of −5 ℃ computes a *supercooled-water* wet bulb, not an ice bulb. A real ventilated
   psychrometer forms an ice bulb when it freezes, so results diverge across 0 ℃ depending
   on the family chosen — **which family to use is the user's call**.
4. **Relative humidity must be greater than 0 %.** The accepted range is `(0, 100]`, so
   `RH = 0` is rejected outright instead of returning a fake number. Physically, dry air is a
   legitimate input (no dew point, wet bulb = dry bulb), so a status value would be more
   generous — but the old code answered `RH = 0` with `−150 ℃` (the bisection floor), and
   refusing is safer than guessing. Use a tiny value such as 0.001 % if you need the dry limit,
   or use mode 0/1 instead.
5. **The psychrometric coefficient A is not the WMO one.** This project uses FAO
   *Frost Protection* Appendix 3: `0.000660(1+0.00115·t_w)` over water and
   `0.000582(1+0.00115·t_f)` over ice — **not** WMO-No. 8, which specifies the Assmann form
   `A = 6.53e-4(1+0.000944·t_w)` over water and `5.75e-4` over ice. The theoretical value is
   `A ≈ c_p/(εL)` ≈ 6.46–6.47×10⁻⁴. Measured effect of switching to the WMO water
   coefficient: max deviation from the ASHRAE definition falls from **0.42 K to 0.29 K**
   (0.25 → 0.16 K over 0–30 ℃). FAO is kept because that is what the code and docs cite;
   switching standards is a researcher's call, and it is a one-line change to `A0_WATER`.
6. **Equivalent potential temperature uses the simplified form** `θe = θ·exp(L_v·q/(c_p·T))`.
   It differs from the strict Bolton (1980) Eq. (38) by about **−1.4 %** (−4.5 K at 25 ℃ /
   54 % RH). These are *different definitions*, not one right and one wrong, so the panel
   keeps the current one and states the difference.
7. **The `L_v(T)` quartic fit** gives 2440.5 kJ/kg at 25 ℃ (IAPWS: 2441.8, −0.05 %) and is
   within 0.18 % over its whole range. Its origin could not be verified, but the deviation
   is far smaller than items 2 and 6.
8. **Batch calculation does not checkpoint.** `result_*.xlsx` is written only after the whole
   table is processed.
9. **The GUI is not covered in CI.** `main.py` needs PySide2, so CI only compiles it. Locally,
   `tests/test_repo_hygiene.py` constructs the real windows on an offscreen Qt platform and
   runs both calculation modes end to end when a suitable interpreter is available;
   interactions (unit dialog, batch writing) still need a human. Those three GUI tests are
   **always skipped in CI** (PySide2 cannot be installed there — see the workflow comment and
   B-23): "CI is green" proves the engine and repo hygiene, not the interface.
   `run_tests.ps1` prints exactly which tests were skipped, and you can point
   `WETBULB_GUI_PYTHON` at the 3.10 interpreter to run them locally.
10. **Two coarse ice formulas.** `Buck (ice)` is 0.83 % off at its registered endpoint of
    −80 ℃ and `Marti (ice)` 2.01 % at −82 ℃ (vs IAPWS-2011). That is each formula's own
    accuracy and their ranges are already narrowed to their sources' claims, but near those
    temperatures **do not compare them side by side with the reference-grade formulas**.
11. **`Gili`'s original source is still unverified.** Only a Chinese HVAC/cooling-tower
    engineering paper with the same family of formula could be located
    (`lg P = 2.0057173 − 3.142305(10³/T − 10³/373.15) + 8.2·lg(373.15/T) − 0.0024804(100 − t)`,
    P in kPa). v1.3.2 implements exactly that form (reference temperature 373.15 K, no
    constant term in the exponent) and the full-range deviation is 0.14 %, but the
    **attribution itself remains unverified** — use it cautiously above 20 ℃.

> Full citations for all 14 formulas, per-entry verification status, and the quantified
> comparisons for items 2, 5, 6 and 11 are in
> [`docs/精度与参考文献.md`](docs/精度与参考文献.md) (Chinese).
>
> ⚠️ Verification corrected three attributions: this project's two `Wexler` coefficient sets
> are exactly **Hyland & Wexler (1983)**, not Wexler (1976); `Goff` is **1957**, not the
> frequently miscited 1965; `Marti` is **Marti & Mauersberger (1993)**; and the `Magnus`
> water/ice forms are verbatim **WMO-No. 8 Annex 4.B equations (4.B.1)/(4.B.3)**.

---

> 🌈 Scientific computing, finally elegant | complex meteorological parameters within reach
