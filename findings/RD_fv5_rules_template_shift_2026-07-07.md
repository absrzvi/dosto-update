# fv5 `rules.yaml` template-reference shift — repo/Puppet fix plan

**Date:** 2026-07-07
**Found on:** box1-t42 (Fzg 42 subnet / 4705-101, Fzg 229), nd-obn 2.3.6, `nd-obn-template-dostoneu-fv5` 0.0.18
**Repo:** `nomad-obn-template-fv5` (`~/Documents/nomad-obn-template-fv5`, branch `master`)
**Status:** ✅ **REPO FIX SHIPPED & DEPLOYED to master** (2026-07-07). Pipeline complete
through step 7; a CCU picks up 0.0.19 on its next factory-up / `puppet agent -t`.

### What shipped (2026-07-07)
- `nomad-obn-template-fv5` `master` commit `41b552f` — 9 SW template refs corrected + version 0.0.18→0.0.19.
- Built `nd-obn-template-dostoneu-fv5_0.0.19_all.deb` (127M) in WSL, verified corrected rules.yaml inside.
- Published to vmrepo01: registered into unstable, **promoted to main** (confirmed `Version: 0.0.19` in main index).
- `environment-dostoneu` `migration_mar5` commit `80490c8` — `hieradata/pipeline/dostoneu-fv5.yaml` pinned `obn::template_pkg_ensure: 0.0.19`.
- Deployed env to master `vmpuppet01` via `nd-update-puppetenv.sh migration_mar5` — master clone confirmed `0.0.19`.
- CCU landing (`puppet agent -t`) intentionally deferred — box1-t42 was mid-`update c`, and a puppet run there would also revert its per-train train_id=229 hardcode (see Point 2).

This doc covers **one** issue only — the fv5 `rules.yaml` template-reference bug. A
second, unrelated issue (train_id/Fzg > 127 box-id limit) surfaced on the same box
and is recorded as **out of scope** at the bottom — deferred, to be handled separately.

---

## Point 1 — fv5 `rules.yaml` SW `template:` refs are shifted one coach (THE fix)

### Symptom
`obn update c sw all` on an fv5 train crashes on the coach-3 switches:

```
CRITICAL: template fv5-300-D1.cfg not found
ERROR:    configuration exception for 10.179.42.185
```

OBN then retries the switch and loops; the consist is left in a partial mixed-config
state.

### Root cause (confirmed in the repo source, not just live)
`src/etc/obn/rules.yaml` maps the coach-3/4/5 SW positions to the wrong template
files. The `config:` names are correct and the template **files** are correct
(named for the real A-C-E-F-B topology); only the `template:` pointers are shifted
one coach up:

| Rule (`config:`) | `rules.yaml` `template:` (WRONG) | Template that exists / should be used |
|---|---|---|
| coach3 `fv5-E1-v8` | `fv5-300-D1.cfg` — **does not exist** | `fv5-400-E1.cfg` |
| coach3 `fv5-E2-v8` | `fv5-300-D2.cfg` — **does not exist** | `fv5-400-E2.cfg` |
| coach3 `fv5-E3-v8` | `fv5-300-D3.cfg` — **does not exist** | `fv5-400-E3.cfg` |
| coach4 `fv5-F1-v8` | `fv5-400-E1.cfg` — **E's template** | `fv5-500-F1.cfg` |
| coach4 `fv5-F2-v8` | `fv5-400-E2.cfg` — **E's template** | `fv5-500-F2.cfg` |
| coach4 `fv5-F3-v8` | `fv5-400-E3.cfg` — **E's template** | `fv5-500-F3.cfg` |
| coach5 `fv5-B1-v8` | `fv5-500-F1.cfg` — **F's template** | `fv5-600-B1.cfg` |
| coach5 `fv5-B2-v8` | `fv5-500-F2.cfg` — **F's template** | `fv5-600-B2.cfg` |
| coach5 `fv5-B3-v8` | `fv5-500-F3.cfg` — **F's template** | `fv5-600-B3.cfg` |

`fv5-600-B*` templates exist in the repo but are **never referenced** — the whole
SW block shifted up one coach. Coaches 1 (A) and 2 (C) are correct.

**Consequence if the crash hadn't stopped it:** coach 4 (F) would have received
coach E's config and coach 5 (B) would have received F's config — a silent
mis-config. The missing-template crash actually prevented that.

Likely origin: the `300-D*` → `400-E*`/`500-F*`/`600-B*` template rename (commit
`4a739af` / v9 box=Fzg era) renamed the files but did not fully re-point `rules.yaml`.

### The fix (repo)
Correct the 9 SW `template:` refs in `src/etc/obn/rules.yaml`: coach3→`400-E*`,
coach4→`500-F*`, coach5→`600-B*`. Identical to the live patch applied by
`dosto-troubleshooting/scripts/fix_fv5_rules_template_shift.py`.

### Deploy steps (per `project_obn_deb_publish_process` + `project_puppet_deploy_chain_vmpuppet01`)
1. **Edit** `~/Documents/nomad-obn-template-fv5/src/etc/obn/rules.yaml` — 9 refs.
2. **Bump** `version` 0.0.18 → 0.0.19.
3. **Commit** (Davud-terse, no Co-Authored-By): e.g.
   `Fix rules.yaml SW template refs: coach3->E coach4->F coach5->B (300-D* never existed)`.
   Push to `master`.
4. **Build** `.deb`: `./build.sh` (needs `fpm`; see repo `PUBLISHING.md`) →
   `nd-obn-template-dostoneu-fv5_0.0.19_all.deb`.
5. **Publish** (from **Git-Bash**, not WSL):
   `scp <deb> admin21net@vmrepo01.ovh2.21net.com:/tmp/` then
   `ssh admin21net@vmrepo01 'sudo nd-registerpkg-bookworm.sh /tmp/<deb>'`
   (registers into unstable; `-promote` → main).
6. **Pin** the fv5 template pkg version to 0.0.19 in the DOSTO env hieradata on the
   `dostoneu_migration_mar5` branch.
7. **Deploy env to the master** (git push alone does nothing to trains):
   `ssh admin21net@vmpuppet01 'cd /etc/puppetlabs/code/environments/dostoneu_migration_mar5 && sudo nd-update-puppetenv.sh migration_mar5'`
8. **Land on a CCU** — `puppet agent -t` on an fv5 box; canary = box1-t42.

### Success criteria
- Repo: every SW `template:` ref in `rules.yaml` has a matching file in
  `src/etc/obn/template/`.
- Deployed 0.0.19 on a test CCU: all 15 refs resolve; `dpkg -l | grep fv5` = 0.0.19.
- `obn update c sw all` on a clean fv5 box completes with **no `template ... not found`**
  and renders correct E/F/B positions.

### Live status on box1-t42 (workaround, not the repo fix)
- `rules.yaml` corrected live under btrfs `ro=false` via
  `scripts/fix_fv5_rules_template_shift.py` (backup in `/var/tmp/rules.yaml.bak-*`).
- Runtime-only — will be wiped by CCU reboot / nightly auto-update until the repo
  fix lands and is deployed. (This box is also NDSU-EXPOSED — patches need
  `--persist` + `.dont` re-rename to survive locally in the interim.)

---

## Point 2 — train_id / Fzg > 127 box-id limit (OUT OF SCOPE — deferred)

**Not part of the rules.yaml fix. Recorded here only so it isn't lost; to be handled separately, later.**

fv5 templates use a `box-id = Fzg` strategy (line 1 is a comment, no `set train_id`
directive; hostname renders from the runtime box-id). box1-t42 is Fzg **229**
(4705-101), and **229 > 127** — the box-id / backbone `train_id` is the 3rd IP octet,
capped 0–127, so it physically cannot encode 229. The box runs `train_id: 42`
(fits the octet, matches the `.42.x` subnet), which makes the box=Fzg templates
render the wrong Fzg (`-042`).

Temporary per-train workaround on box1-t42: hardcoded `{%- set train_id = 229 -%}`
into all 15 `fv5-*.cfg` line 1 (via `scripts/fix_fv5_train_id_229.py`), leaving
`backbone-discovery.yaml` train_id=42 untouched. Hostnames now render `-229`;
management IPs stay `.42.x`. This is intentional decoupling, **per-train only** — it
must NOT go into the shared template repo.

The durable fix (an `fzg_id`-key path so the shared template can carry Fzg > 127
without per-train edits) is a fleet-wide R&D architecture decision affecting all
4705/4706/4736 fv5/fv6 trains. See memory `project_box_fzg_breaks_127_octet_limit`,
`project_box_equals_fzg_strategy_split`, `project_fzg_id_render_transport_constraint`.
**Deferred — revisit as its own workstream.**
