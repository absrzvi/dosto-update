# P0 — Baseline Freeze

**Review baseline:** OBN `origin/master`, commit `8042c8d`, `pyproject.toml` version **2.3.12**
(the "3.2.12" in the commit subject is a typo in R&D's own commit message).
**Analysis worktree:** `.tmp/obn-origin-master/` (detached HEAD at `8042c8d`; local branches untouched).
**Date frozen:** 2026-06-27.

## Size (denominators)

| Metric | Value |
|---|---|
| Source files (`src/**.py`) | 76 |
| Source LOC | 11,974 |
| Test files (`tests/**.py`) | 53 |
| Test LOC | 9,440 |
| Test : source LOC ratio | 1.27 : 1 |
| Python target | ≥ 3.11 |

## Complexity (radon) — `radon_cc.txt`, `radon_mi.txt`

- **608 blocks analyzed; average cyclomatic complexity = A (3.81).**
- Grade distribution: **A 503, B 78, C 14, D 7, E 3, F 3.**
- **Maintainability Index: every file is grade A (≥34).** Worst: `report.py` (34.0), `snmpdevice.py`
  (37.5), `acksys.py` (37.6).
- **Headline:** OBN is *not* a complexity/spaghetti problem by standard metrics. The defect story is
  robustness/None-handling fragility in an otherwise structurally-simple codebase.

### Complexity hotspots cluster in `number_coaches()` across report variants
| Block | Grade |
|---|---|
| `VIAReport.number_coaches` | **F (59)** — worst block in the codebase |
| `DostoNeuReport.number_coaches` | **F (41)** |
| `CCJPAReport.number_coaches` | **E (35)** |
| `QueenslandReport.number_coaches` | **E (34)** |
| `CCJPAWD1 / ACE / Dani number_coaches` | D (21–27) |
| Non-report hotspots | `TIPG541Device._ssh` D(22), `togglepoe` C(18), `LldpArpWalker.walk` C(17), `SNMPDevice._snmp_parse_results` C(12) |

**Architectural signal:** each of the 14 customer report variants hand-rolls the hardest, most
bug-prone algorithm (topology walk → coach numbering) as its own high-complexity method. This is
where Bug 10 (DOSTO BFS loop) and the new numbering-fallback feature live, and it predicts the same
*class* of defect is latent in the other variants. Points toward "improve + refactor the report
layer's numbering into a shared, tested core."

## Code-health counts (src)

| Signal | Count |
|---|---|
| TODO/FIXME/HACK/XXX | 32 |
| `except Exception` (broad) | 6 |
| Bare `except:` | 0 |
| Functions total (`def`) | 515 |
| Functions with `->` return annotation | 213 (41%) |

Partial typing, no mypy in CI → type-safety is unenforced. (None-related bugs are the dominant field
defect class; enforced typing would have caught several.)

## Dependencies & CVEs — `pip_audit.txt`, `dependencies.txt`

- 25 runtime deps (pinned). **pip-audit: "No known vulnerabilities found."**
- **Provenance oddity to chase in P2:** `httpx2>=2.3.0` and `pytest-httpx2>=1.0.0` — non-standard
  renames of httpx / pytest-httpx (commit `2cddeef` "Fix references for HTTPX to HTTPX2 after
  vulnerability fixes"). Verify these are trusted/internal forks, not typosquats.

## Test baseline

- **Report-layer + validate tests: 280 passed, 1 xfailed, 2 xpassed** (the most decision-relevant
  suite — covers the report variants where complexity concentrates). Green.
- Device-vendor / walker / CLI tests **could not run in this Windows venv**: the installed
  `isc_dhcp_leases` wheel has a `SyntaxError` (invalid `\s` escape) under Python 3.11 — a third-party
  packaging bug in the local venv, **not** an OBN defect. These pass in CI on Debian. Treat any P3
  finding in the device chain as "static-only; not runtime-confirmed locally."

## CI posture (`.gitlab-ci.yml`)
pytest + coverage, radon complexity, **black --check**, **pip-audit**, package+install smoke test.
**No mypy. No ruff/bandit in CI** (those are pre-commit-only).
