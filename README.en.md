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

- **Verifiable precision.** Of the 14 formulas, Goff / Goff-Gratch / Wexler agree with
  the WMO reference table to **within 0.09 %**. Every number in this README is re-checked
  by CI on every push — see [Measured accuracy](#measured-accuracy) below.
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

### Saturation vapour pressure vs the WMO / Smithsonian reference table

| Formula | Registered range | Max deviation | Worst point |
|---|---|---:|---|
| Goff (water) | −10 – 100 ℃ | 0.09 % | 15 ℃ |
| Goff-Gratch 1946 (water) | −10 – 100 ℃ | 0.09 % | 0 ℃ |
| Wexler (water) | −10 – 200 ℃ | 0.09 % | 100 ℃ |
| Tetens (water) | 0 – 50 ℃ | 0.09 % | 40 ℃ |
| August (water) | 0 – 60 ℃ | 0.23 % | 20 ℃ |
| Buck (water) | 0 – 80 ℃ | 0.24 % | 50 ℃ |
| Magnus (water) | 0 – 60 ℃ | 0.27 % | 20 ℃ |
| Gili (water) | −10 – 20 ℃ | 0.28 % | 15 ℃ |
| Arden/Buck-1996 (water) | 0 – 100 ℃ (**usable only to ~25 ℃**) | 1.0 % @25 ℃, 3.6 % @50 ℃, 12.7 % @100 ℃ | 100 ℃ |
| Goff-Gratch (ice) | −100 – 10 ℃ | 0.09 % | −50 ℃ |
| Wexler (ice) | −150 – 10 ℃ | 0.04 % | −40 ℃ |
| Magnus (ice) | −65 – 0 ℃ | 0.02 % | −50 ℃ |
| Buck (ice) | −80 – 0 ℃ | 0.03 % | −20 ℃ |
| Marti (ice) | −150 – 0 ℃ | 1.29 % | −50 ℃ |

> The reason Goff / Goff-Gratch / Wexler can vouch for the reference table: they are
> independent published formulations and they agree with it to ≤0.09 %, so table and
> formulas corroborate each other instead of one citing the other.
> **Arden is a special case** — see [Known limitations](#known-limitations).

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
| ASHRAE adiabatic-saturation equation | the **definition** of thermodynamic wet-bulb temperature | **0.45 K** (@50 ℃ / 10 % RH; ≈0.05 K at room temperature) |
| Stull (2011) empirical fit | fully independent published formula, no shared code | 0.91 K |
| ASHRAE / Vaisala dew-point tables | published table values | 0.30 K (within assertion tolerance) |

> This project solves the meteorological psychrometric equation
> `e = e_sat(T_w) − A·p·(T − T_w)`, `A = 0.000667(1 + 0.00115·T_w)`.
> Its difference from the ASHRAE definition is the error of that approximation itself:
> a smooth, monotonic 0.01 → 0.45 K drift with rising temperature and drier air. If that
> difference ever becomes erratic or changes sign, the solver is broken and CI says so.

---

## Installation and running

Download the latest release — that is all most users need.

Stable releases: `v1.1.3`, `v1.2.2`, `v1.3.0`, `v1.3.1`.
Do **not** use `v1.0.0`, `v1.0.1` or `v1.2.0`: they contain serious bugs.

### v1.3.1 — numerical-fix release

> **v1.3.1 does not produce the same numbers as v1.3.0**, because three formula defects
> were fixed. Use v1.3.1 or later.

- **Fixed** — `Gili`: the leading factor was 980.66 (1 technical atmosphere) instead of
  1013.25 hPa, which made the formula read a constant **3.0 % low** over its whole range.
  Now within **0.28 %**.
- **Fixed** — `Goff-Gratch 1946`: the 4th coefficient was `1.3816e-5` instead of
  `1.3816e-7` (a factor of 100), making the cold end read −3.5 % at 0 ℃ and −1.7 % at 10 ℃.
  Now within 0.09 % everywhere.
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
  actually used; `tests/` with external-reference regression (247 assertions); GitHub
  Actions CI; `run_tests.ps1`.

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
python -m pytest -q                  # correctness vs WMO/ASHRAE references (247 assertions)
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
2. **`Arden` is unusable when hot.** Its coefficients come from Buck's (1996) **three**-parameter
   form `e_s = 6.1121·exp[(18.678 − T/234.5)·T/(257.14 + T)]`, but it is registered with the
   **two**-parameter `magnus` family, which drops the `−T/234.5` correction: +1.0 % at 25 ℃,
   +3.6 % at 50 ℃, +12.7 % at 100 ℃. Documented only; fixing it properly requires adding a
   three-parameter family.
3. **The wet-bulb equation is the psychrometric approximation.** It differs from the ASHRAE
   adiabatic-saturation definition by 0.01–0.45 K (growing with temperature). A strict
   thermodynamic wet-bulb temperature would require the adiabatic-saturation equation.
4. **Below 0 ℃ the wet bulb is still computed over water.** A real ventilated psychrometer
   forms an ice bulb; here the selected formula family is used unchanged, so results diverge
   across 0 ℃ depending on the formula chosen.
5. **The LCL uses a common Celsius variant of Bolton's formula** (`T_d − 56` in ℃ rather than
   K). It agrees with the "LCL ≈ 125·(T − T_d) m" rule of thumb to within 1.2 K but differs
   from the strict Bolton solution by about 1 K and has not been checked against an external
   truth value.
6. **The gravity setting does not enter any calculation.** It is only written to `cfg.json`
   and shown as a placeholder. The v1.2.0 release note claiming it improves accuracy is wrong
   and has been corrected.
7. **Batch calculation does not checkpoint.** `result_*.xlsx` is written only after the whole
   table is processed.
8. **The GUI is not covered in CI.** `main.py` needs PySide2, so CI only compiles it. Locally,
   `tests/test_repo_hygiene.py` constructs the real windows on an offscreen Qt platform when a
   suitable interpreter is available; interactions (unit dialog, batch writing) still need a
   human.
9. **The psychrometric coefficient A is not the WMO one.** This project uses
   `0.000667(1+0.00115·t_w)`, which comes from FAO *Frost Protection* Annex 3 (citing
   Fritschen & Gay, 1979) — **not** from WMO-No. 8, which specifies the Assmann form
   `A = 6.53e-4(1+0.000944·t_w)` over water and `5.75e-4` over ice. Measured effect of
   switching: deviation from the ASHRAE definition drops from **0.452 K to 0.265 K**.
   Not changed yet, because WMO gives *two different* coefficients for water and ice and this
   tool does not currently distinguish the phase — a phase-judgement call.
10. **`Gili` carries an unexplained term.** Its exponent includes a `+0.00141966` that appears in
    no source I could find (the Chinese engineering-literature version of the same formula has
    `2.0057173 = lg 101.325` instead, with P in kPa — which does confirm the v1.3.1 prefactor
    fix). Removing it would cut the deviation from the reference table from **0.276 % to
    0.147 %**. Not changed yet.

> Full citations for all 14 formulas, per-entry verification status, and the quantified
> comparison for items 9–10 are in [`docs/精度与参考文献.md`](docs/精度与参考文献.md) (Chinese).
>
> ⚠️ Verification corrected three attributions: this project's two `Wexler` coefficient sets
> are exactly **Hyland & Wexler (1983)**, not Wexler (1976); `Goff` is **1957**, not the
> frequently miscited 1965; `Marti` is **Marti & Mauersberger (1993)**; and the `Magnus`
> water/ice forms are verbatim **WMO-No. 8 Annex 4.B equations (4.B.1)/(4.B.3)**.

---

> 🌈 Scientific computing, finally elegant | complex meteorological parameters within reach
