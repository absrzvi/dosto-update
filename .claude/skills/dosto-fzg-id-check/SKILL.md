---
name: dosto-fzg-id-check
description: Verify and (manually) fix the train_id template formula across all /etc/obn/template/nv6-*.cfg (or nv4-*.cfg) files on a DOSTO CCU. Detects the broken {%- set train_id = 128 + train_id -%} formula that produced the Fzg 133 cascade, plus mixed/stale hardcoded values. Computes the expected hardcoded value from the engineer-supplied Fzg ID, prints the exact in-chroot Python recipe to align all templates, and never edits the CCU directly. Use as Step 4c of the train-login workflow during commissioning, before any obn update c run, or whenever the OBN-patches cross-check (subsection A) flagged a template anomaly. Pairs with dosto-obn-patches (--persist mode) to fold template + OBN patches + vlan7 fixes into one chroot session.
---

# DOSTO Fzg ID Template Check

This skill is the canonical procedure for verifying and fixing the **`train_id` value rendered into every `/etc/obn/template/nv6-*.cfg`** (or `nv4-*.cfg`) file on a DOSTO NEU CCU.

OBN renders switch hostnames like `nv6-A1-v8-<train_id>` from these templates. Get the value wrong and `obn update c all` happily pushes the wrong-named config to every switch on the consist while reporting "success" — the same silent-fail mode that produced the Fzg 133 cascade in May 2026 (see [`reports/internal/105-update-report-2026-05-04.md`](../../../reports/internal/105-update-report-2026-05-04.md)).

## When to use

- **Commissioning a new train (Step 4c in [train-login-checklist.md](../../../train-login-checklist.md))** — verify `train_id` is hardcoded to the train's Fzg ID *before* any `obn update c all` push.
- **Whenever [`dosto-obn-patches`](../dosto-obn-patches/SKILL.md) cross-check A flagged the template** — `broken_formula` or `inconsistent` verdicts route here.
- **Before any `obn update c all`** — even on trains that "looked fine last time".
- **After a CCU reboot** — verify the templates survived the btrfs snapshot rollback.
- **When [fleet-status.md](../../../fleet-status.md) shows `train_id ok` as ❓ or 🔴** — fill it in.

## Output modes

Both default and `--json` modes share the same diagnostic procedure — `--json` is purely a formatter switch.

- **default — engineer-readable.** Diagnostic table + verdict + recipe-when-needed.
- **`--json` — machine-readable.** A single JSON line on stdout matching `skill_outputs[]` from [.claude/contracts/subagent-report.md](../../contracts/subagent-report.md). Subagents pass `--json`; engineers don't.

### `--json` shape

```json
{
  "skill": "dosto-fzg-id-check",
  "mode": "check",
  "schema_version": "1",
  "verdict": "all_match|broken_formula|hardcoded_wrong|inconsistent|templates_missing",
  "raw": {
    "fzg_input": 132,
    "expected_hardcoded": 132,
    "template_dir": "/etc/obn/template",
    "template_variant": "nv6",
    "template_glob": "nv6-*.cfg",
    "templates_found": 18,
    "templates_expected": 18,
    "train_id_lines_unique": ["{%- set train_id = 132 -%}"],
    "train_id_lines_count": 1,
    "broken_formula_count": 0,
    "hardcoded_count": 18,
    "rendered_train_id": 132,
    "backbone_discovery_train_id": 132,
    "preferred_fix_form": "hardcoded"
  },
  "recipe": null
}
```

`verdict` semantics:
- `all_match` — exactly one unique `train_id` line, hardcoded form, value equals `fzg_input`. ✅
- `broken_formula` — at least one template has `{%- set train_id = 128 + train_id -%}`. 🔴 same bug as Fzg 133 cascade.
- `hardcoded_wrong` — all templates hardcoded to a single value, but that value ≠ `fzg_input` (e.g. legacy `130` left over from a previous train). 🔴
- `inconsistent` — `train_id_lines_count > 1` (mixed templates from a partial fix). 🔴
- `templates_missing` — no `nv*-*.cfg` files at all. 🔴 wrong CCU image or wrong path.

`recipe` is non-null only when `verdict ∈ { broken_formula, hardcoded_wrong, inconsistent }`. Contains the multi-line in-chroot Python recipe with `<NDSU>`, `<FZG>`, and the variant glob already substituted.

`backbone_discovery_train_id` is informational only (the file is off-limits per the mar5 rule — see below). Never used to drive a fix.

`preferred_fix_form` defaults to `"hardcoded"` (Form 1: `{%- set train_id = <Fzg> -%}`). The skill prints an opt-in note for trains documented as decoupled (see "Edge cases" below).

## The mar5 rule (read this once)

The Fzg ID lives **only** in `/etc/obn/template/nv6-*.cfg` (or `nv4-*.cfg`). It must never be set in `/etc/obn/backbone-discovery.yaml` — that file is a deliberate workaround left in place for the mar5 migration and is treated as off-limits. See auto-memory `feedback_train_id_location.md`.

This skill therefore:
- Reads `backbone-discovery.yaml` for *informational* output only.
- Never proposes editing `backbone-discovery.yaml`.
- Always fixes templates by setting `train_id` to a hardcoded literal.

## Why hardcoded Form 1 over Form 2

Two valid "correct" forms exist in the runbook history:

| Form | Line | Effect at runtime |
|---|---|---|
| **1 (preferred)** | `{%- set train_id = <Fzg> -%}` | Renders to `<Fzg>` regardless of `backbone-discovery.yaml` |
| 2 (historical) | `{%- set train_id = train_id -%}` | Renders to whatever `backbone-discovery.yaml`'s `train_id:` says |

Form 1 was validated end-to-end on **Fzg 132 / box1-t10 on 2026-05-09**: all 18 templates set to `{%- set train_id = 132 -%}` → `obn validate -t sw` showed every switch hostname as `nv6-X-v8-132`, matching the Fzg. See handoff line 205.

Form 2 was the Fzg 133 historical fix, used *because* that train deliberately decouples `train_id` from Fzg ID (auto-memory `feedback_train_id_ip_mismatch.md`). On Fzg 133 with `backbone-discovery.yaml: train_id: 2`, Form 2 produces `train_id = 2` and hostnames `nv6-X-v8-2`. That's correct *for that train* but is the explicit edge case, not the default.

This skill defaults to Form 1. The recipe always emits Form 1 unless the engineer explicitly opts into Form 2 via `--decoupled` (see "Edge cases").

## nv6 vs nv4 detection

The skill auto-picks the variant based on what files exist:

| `ls /etc/obn/template/` shows | Treated as | Expected count |
|---|---|---|
| `nv6-*.cfg` only | nv6 (6-car DOSTO) | 18 |
| `nv4-*.cfg` only | nv4 (4-car DOSTO) | 12 |
| both present | abort — flag as anomaly |
| neither | `templates_missing` |

The engineer doesn't pass a `--variant` flag.

## Procedure

### 0. Inputs

You need:

- **Train#** (e.g. `4736-104` — the Nomad-internal primary identifier)
- **CCU IP** (e.g. `10.179.10.1`)

Fzg ID is derived from the fleet-status row via `python scripts/fleet_status_lookup.py lookup <train#> --require-fzg`. If the row's Fzg cell is `❓`, halt with: *"Fzg ID for `<train#>` missing in fleet-status — populate the Fzg column (from `train-ip-allocation-commission/<series>-xxx/<train#>/<train#>_IP-Port-Allocation.pdf` or physical inspection) before checking templates."*

Engineer may also pass a bare Fzg integer (`/dosto-fzg-id-check 132`) for ad-hoc work — in that case treat Fzg as authoritative and skip the fleet-status lookup.

**Series → Fzg shorthand** (reference only; runtime Fzg comes from fleet-status, not the formula):
- `4734-NNN → Fzg = NNN - 100`
- `4736-NNN → Fzg = NNN + 28`
- `4705-NNN → Fzg = NNN + 128`
- `4706-NNN → Fzg = NNN + 88`

### 1. Compute the expected hardcoded value

Trivial:

```python
expected_hardcoded = fzg_input
```

The expected line is `{%- set train_id = <fzg_input> -%}`.

### 2. Read live template state — single SSH heredoc

```bash
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip> '
echo "=== variant detection ==="
NV4=$(ls /etc/obn/template/nv4-*.cfg 2>/dev/null | wc -l)
NV6=$(ls /etc/obn/template/nv6-*.cfg 2>/dev/null | wc -l)
echo "NV4_COUNT=$NV4"
echo "NV6_COUNT=$NV6"

echo "=== unique train_id lines (variant chosen automatically) ==="
if [ "$NV6" -gt 0 ] && [ "$NV4" -eq 0 ]; then
  GLOB=/etc/obn/template/nv6-*.cfg
elif [ "$NV4" -gt 0 ] && [ "$NV6" -eq 0 ]; then
  GLOB=/etc/obn/template/nv4-*.cfg
else
  echo "VARIANT=AMBIGUOUS_OR_MISSING"
  GLOB=
fi
if [ -n "$GLOB" ]; then
  echo "GLOB=$GLOB"
  grep -h "^{%- set train_id" $GLOB | sort -u
fi

echo "=== broken-formula occurrences across both variants ==="
# Note: count via `grep -l ... | wc -l` directly. The earlier `grep -lc | awk -F:` form was broken
# on this CCU image — `grep -lc` emits filename-only output (no `path:count`), so awk -F: saw $2
# empty and undercounted to zero. Validated 2026-05-09 on box1-t47 (true count 18, reported 0).
# Also: an intermediate `BROKEN_FILES=$(...)` variable then `echo "$BROKEN_FILES" | wc -l` collapses
# newlines through SSH heredoc nesting and reports 1 instead of N. Direct pipe is robust.
BROKEN_FILE_COUNT=$(grep -l "{%- set train_id = 128 + train_id" /etc/obn/template/nv*-*.cfg 2>/dev/null | wc -l)
echo "BROKEN_FILE_COUNT=$BROKEN_FILE_COUNT"
if [ "$BROKEN_FILE_COUNT" -gt 0 ]; then
  echo "BROKEN_FILES_HEAD:"
  grep -l "{%- set train_id = 128 + train_id" /etc/obn/template/nv*-*.cfg 2>/dev/null | head -3
fi

echo "=== backbone-discovery.yaml train_id (informational only — mar5 says do not edit) ==="
grep -E "^[[:space:]]*train_id:" /etc/obn/backbone-discovery.yaml 2>/dev/null | head -1
'
```

Parse the output:

- `NV4_COUNT`, `NV6_COUNT` — pick the variant; if both > 0 or both == 0, set verdict accordingly.
- `GLOB` — confirms which set the analysis is using.
- The `grep -h ... | sort -u` block — gives `train_id_lines_unique`. Count of distinct lines = `train_id_lines_count`.
- `BROKEN_FILE_COUNT` — `broken_formula_count`.
- `train_id:` line from `backbone-discovery.yaml` — `backbone_discovery_train_id` (informational).

`hardcoded_count` is the number of unique lines that match `{%- set train_id = <integer> -%}` (no `+` operator). `templates_found` is `NV6_COUNT` or `NV4_COUNT` whichever was picked.

### 3. Diff and verdict

| `train_id_lines_count` | `broken_formula_count` | hardcoded value matches `fzg_input`? | Verdict |
|---|---|---|---|
| 1 | 0 | ✅ yes | `all_match` ✅ |
| any | ≥1 | n/a | `broken_formula` 🔴 |
| 1 | 0 | ❌ no | `hardcoded_wrong` 🔴 |
| >1 | any | mixed | `inconsistent` 🔴 |
| 0 / no files / both variants present | n/a | n/a | `templates_missing` 🔴 |

Print a status line:

```
Variant:           nv6 (18 templates expected, 18 found)
Unique train_id:   {%- set train_id = 132 -%}
Broken formula:    0 files
Backbone yaml:     train_id: 132   (informational only — mar5 rule)

Verdict: ✅ all_match — train_id renders as 132 (= Fzg).
```

Or, on the broken case:

```
Variant:           nv6 (18 templates expected, 18 found)
Unique train_id:   {%- set train_id = 128 + train_id -%}
Broken formula:    18 files
Backbone yaml:     train_id: 4

Verdict: 🔴 broken_formula — same bug as the Fzg 133 cascade.
        At runtime this renders train_id = 128 + 4 = 132 ≠ Fzg.
        Hostnames pushed to every switch would be nv6-X-v8-132, not Fzg-aligned.
        (For this train, expected Fzg = <FZG_INPUT>.)

Apply with: /dosto-fzg-id-check <fzg> --persist
```

### 4. Print the fix recipe (DO NOT EXECUTE IT)

If the verdict is `broken_formula`, `hardcoded_wrong`, or `inconsistent`, print the in-chroot recipe so the engineer runs it themselves. The Python heredoc style mirrors `dosto-vlan7-config` — `assert` first, then in-place rewrite — so the patch fails loudly if the template shape isn't what we read pre-chroot.

**Substitute these placeholders before printing:**
- `<NDSU>` → `/usr/sbin/nd-systemupdate.sh.dont` (fleet-standard) or `/usr/sbin/nd-systemupdate.sh` (auto-update-exposed). Use the same probe documented in [`dosto-obn-patches`](../dosto-obn-patches/SKILL.md) "Pre-recipe" section.
- `<FZG>` → the engineer-supplied Fzg ID (an integer)
- `<VARIANT_GLOB>` → either `nv6-*.cfg` or `nv4-*.cfg` from auto-detection
- `<TEMPLATES_EXPECTED>` → `18` for nv6, `12` for nv4

```bash
# === STEP 1: Drop into the persistent-edit chroot ===
sudo <NDSU> shell
# e.g. sudo /usr/sbin/nd-systemupdate.sh.dont shell  (fleet standard)
#      sudo /usr/sbin/nd-systemupdate.sh shell       (auto-update-exposed CCU — also do step 3.5
#                                                     from dosto-obn-patches --persist before exit)

# === STEP 2: INSIDE THE CHROOT, rewrite line 1 of every template ===
sudo python3 <<'PYEOF'
import glob, sys
paths = sorted(glob.glob('/etc/obn/template/<VARIANT_GLOB>'))
expected = <TEMPLATES_EXPECTED>
if len(paths) != expected:
    sys.exit(f'expected {expected} templates, got {len(paths)} — aborting (re-check variant)')
target = '{%- set train_id = <FZG> -%}\n'
replaced = 0
unchanged = 0
for p in paths:
    with open(p) as f:
        lines = f.readlines()
    if not lines:
        sys.exit(f'{p} is empty — aborting')
    if not lines[0].startswith('{%- set train_id'):
        sys.exit(f'first line of {p} is not a train_id directive — aborting')
    if lines[0] == target:
        unchanged += 1
        continue
    lines[0] = target
    with open(p, 'w') as f:
        f.writelines(lines)
    replaced += 1
print(f'PATCHED {replaced} templates, {unchanged} already correct, {len(paths)} total')
PYEOF

# === STEP 3: Verify inside the chroot ===
grep -h "^{%- set train_id" /etc/obn/template/<VARIANT_GLOB> | sort -u
# Expected output: exactly one line:
#   {%- set train_id = <FZG> -%}

# === STEP 4: Exit the chroot — promotes work → release → new run<N>, sets default GRUB entry ===
exit

# === STEP 5: Reboot into the new snapshot ===
sudo /usr/local/sbin/safe_reboot
```

The `assert`-style failure modes:
- Template count mismatch → engineer should re-check `--variant` was auto-detected correctly.
- First line is not a `train_id` directive → template was hand-edited or is a different OBN version; engineer should investigate before retrying.
- Empty file → corrupted snapshot.

All of these abort cleanly without writing anything.

### Decoupled-train mode (Form 2 — opt-in only)

If the train is documented as having `train_id ≠ Fzg ID` (currently confirmed only for **Fzg 133 / box1-t1**, see auto-memory `feedback_train_id_ip_mismatch.md`), the engineer can pass `--decoupled` to emit Form 2 instead:

```python
target = '{%- set train_id = train_id -%}\n'
```

The recipe then renders whatever `backbone-discovery.yaml` has, deferring to that file's `train_id:` value. Skill should print an explicit warning before printing this recipe:

```
🟡 --decoupled mode: the rendered train_id will come from backbone-discovery.yaml,
   not from the Fzg ID. This train's documented decoupling means hostnames will
   render as <variant>-X-v8-<backbone_discovery_train_id>=<N>, NOT <variant>-X-v8-<FZG>=<F>.
   Confirm this is what you want for this specific train before running the recipe.
```

Default behaviour (no flag) is always Form 1.

### 5. Post-Flight — verify the rendered output

**Mandatory rendered-output verification** (Karpathy Principle 4 — Goal-Driven Execution; see also [`CLAUDE.md` § Universal Principles](../../../CLAUDE.md)). The template fix is the *input*; the rendered switch hostnames OBN pushes to the consist are the *output*. Verifying the input alone is necessary but not sufficient — that's the failure mode that produced the Fzg 133 cascade.

After reboot, the engineer (or `dosto-commission-train` stage 10 `post_reboot_verify`) MUST verify all three of:

| Assertion | Probe | Pass criterion |
|---|---|---|
| **A. Input file unchanged from intent** | `grep -h "^{%- set train_id" /etc/obn/template/<variant_glob>` (one SSH session) | Exactly one unique line: `{%- set train_id = <FZG> -%}` |
| **B. Rendered hostnames match Fzg** | `sudo obn discover && sudo obn validate -t sw` (force-fresh, then read) | All N switches show config name `<variant>-X-v8-<FZG>` (where X is the position label) |
| **C. No regression on cross-checks** | `dosto-obn-patches --check --json` | Verdict == `all_persisted`, `train_id_template_consistent == true` |

**If A passes but B fails:** you're hitting the deep-cache problem (handoff lesson 15) — `obn validate` reads from `/tmp/discovery.json` produced by the every-5-minute backbone-discovery timer. Force a fresh poll: `sudo obn discover`, then re-check. If still failing after fresh discover, the chroot promote silently lost the changes — halt and investigate the btrfs subvol ID.

**If A fails but B passes:** very rare — means OBN is rendering from a different source than the template files (possibly `/data/auto-topology/upload/` cache wasn't cleared). Halt and investigate.

**`--json` output for Post-Flight** (consumed by `dosto-commission-train`'s stage 10):

```json
{
  "skill": "dosto-fzg-id-check",
  "mode": "post_flight",
  "schema_version": "1",
  "verdict": "all_match|input_only|rendered_mismatch|both_mismatch",
  "raw": {
    "fzg_input": 132,
    "input_assertion_a": {"pass": true, "unique_lines": ["{%- set train_id = 132 -%}"]},
    "rendered_assertion_b": {"pass": true, "rendered_hostnames": ["nv6-A1-v8-132", "nv6-A2-v8-132", "..."], "expected_pattern": "nv6-X-v8-132", "mismatches": []},
    "cross_check_assertion_c": {"pass": true, "obn_patches_verdict": "all_persisted"}
  }
}
```

`verdict` semantics:
- `all_match` — all three assertions pass. ✅
- `input_only` — A passes, B fails. 🟡 deep-cache or upload-cache issue.
- `rendered_mismatch` — A and B disagree (A says intended Fzg, B says different). 🔴 promote silently lost the change.
- `both_mismatch` — neither passes. 🔴 fix did not land at all.

### 6. Update [fleet-status.md](../../../fleet-status.md)

Per the orchestrator-as-sole-writer pattern, the skill prints the values; the engineer (or orchestrator) edits the row:

- `train_id ok` column → ✅ if all match, 🔴 if mismatch persists, 🟡 if reboot pending
- `Last touched` column → today's date + initials
- If 🔴, add or update the per-train notes section explaining what's still wrong

## What this skill deliberately does NOT do

- ❌ Edit `/etc/obn/backbone-discovery.yaml` (mar5 rule — that file is off-limits)
- ❌ Edit templates directly (chroot is engineer-driven, irreversible — only the engineer runs it)
- ❌ Trigger `nd-systemupdate.sh shell` programmatically
- ❌ Reboot the CCU
- ❌ Auto-extract the Fzg ID from the PDF (engineer-supplied, same convention as `dosto-vlan7-config`)
- ❌ Decide between Form 1 and Form 2 silently — Form 1 is the default; Form 2 is opt-in via `--decoupled`
- ❌ Touch templates of the *other* variant (if both nv6 and nv4 dirs are present, the skill aborts rather than guessing)

## Edge cases / gotchas

- **Fzg 133 / box1-t1 historical Form 2.** auto-memory `feedback_train_id_ip_mismatch.md` documents this train's deliberate decoupling. Don't auto-rewrite to Form 1; surface the mismatch and recommend `--decoupled` if (and only if) the engineer confirms this is one of the documented decoupled trains.
- **nv4 description aliasing** — known nv4 quirk in the cloned `nomad-obn-template-nv4` repo (descriptions reference nv6 coach names). Cosmetic; this skill operates on the `train_id` line only, not descriptions, so unaffected. Documented in auto-memory `reference_obn_template_clones.md`.
- **Template count mismatch** — if `templates_found != templates_expected` (18 for nv6, 12 for nv4), the recipe's `assert` will fail. Skill should refuse to print the recipe in `--check` and route the engineer to investigate first (likely a hand-deletion or a multi-variant CCU that needs separate triage).
- **Mixed nv4 + nv6 dirs** — verdict `templates_missing` (technically "ambiguous"); skill aborts rather than guessing the variant.
- **`backbone-discovery.yaml` informational read** — read for `raw.backbone_discovery_train_id` only. Never written. Never used to compute the recipe. If it's missing or unreadable, that's not an error condition for this skill.
- **First-line assumption** — every nv6/nv4 template in the cloned `nomad-obn-template-{nv4,nv6}` repos opens with the `train_id` directive on line 1. The recipe's `assert` enforces this. If a future OBN version moves the directive elsewhere, the recipe will abort cleanly instead of corrupting the file.

## Pairs with

- [`dosto-vlan7-config`](../dosto-vlan7-config/SKILL.md) — same diagnostic+recipe shape; both are "static-config-from-PDF must persist via `nd-systemupdate`" skills.
- [`dosto-obn-patches`](../dosto-obn-patches/SKILL.md) — cross-check A surfaces template anomalies that route here. `--persist` chroot session can fold OBN patches + Fzg-ID + vlan7 fixes into a single promote (handoff lesson 1).
- [train-login-checklist.md](../../../train-login-checklist.md) — Step 4c invokes this skill.
- [fleet-status.md](../../../fleet-status.md) — `train_id ok` column tracks per-train state.

## Reference

- auto-memory `feedback_train_id_location.md` — Fzg ID lives only in `nv*-*.cfg`, never `backbone-discovery.yaml`
- auto-memory `feedback_train_id_ip_mismatch.md` — DOSTO NEU `train_id ≠ Fzg ID` on documented decoupled trains
- [troubleshooting-runbook.md](../../../troubleshooting-runbook.md) → "Watch out: the broken `128 + train_id` formula"
- [reports/internal/105-update-report-2026-05-04.md](../../../reports/internal/105-update-report-2026-05-04.md) — Fzg 133 cascade post-mortem (the original failure mode this skill prevents)
- handoff lesson 1 — single-promote pattern for fold-in chroot session
