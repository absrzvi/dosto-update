# How OBN is set up in GitLab — the standard process (and how nv2 *should* be done)

Captured 2026-06-04 while planning the nv2 bench enablement. The point: stop hand-patching `/usr/share/obn/*.py` on CCUs (it gets wiped on the next package/image update — the whole reason for the R&D-ticket backlog) and instead change the source in GitLab so the fix ships in the package.

## The pipeline (GitLab → CCU)

```
GitLab repo (onboard/ org)  ──build.sh (fpm)──▶  .deb  ──▶  apt repo  ──▶  Puppet / nd-systemupdate  ──▶  CCU filesystem
   master branch                 versioned                                  (vmpuppet01.ovh.21net.com)      /usr/share/obn, /etc/obn
```

Every OBN artifact on a CCU is an **installed Debian package**, not a git checkout. Verified on box1-t123:
- `dpkg -S /usr/share/obn/lib/report/report_dosto_neu.py` → **`nd-obn`** (the engine package).
- `/etc/obn/template/*.cfg` → the **`nd-obn-template-dostoneu-<type>`** packages.
- No `.git` anywhere under `/usr/share/obn`. CCU has only the built artifact.

So a CCU hand-patch edits the *installed file*; the next `nd-systemupdate`/image refresh reinstalls the package and **reverts it**. (This is exactly the v8 regression risk in `project_rd_gitlab_tickets_todo`.)

## The repos

GitLab org: **`git@git-nc.nomadrail.com:onboard/`** (SSH auth, `@abbas.rizvi` registered; host key in known_hosts).

| Repo | Package | Owns on CCU | Cloned locally? |
|---|---|---|---|
| `nd-obn-template-dostoneu-nv4` | `nd-obn-template-dostoneu-nv4` | `/etc/obn/template/*.cfg`, `rules.yaml`, `dhcp_groups/` | ✅ `~/Documents/nomad-obn-template-nv4` |
| `nd-obn-template-dostoneu-nv6` | …`-nv6` | same, nv6 | ✅ `~/Documents/nomad-obn-template-nv6` |
| `nd-obn-template-dostoneu-fv5` / `-fv6` | …`-fv5`/`-fv6` | same, fv5/fv6 | ✅ `~/Documents/nomad-obn-template-fv5`/`-fv6` |
| **`nd-obn`** (engine — name to confirm on GitLab) | `nd-obn` | `/usr/share/obn/**` (Python: `report_dosto_neu.py`, `report_generic.py`, `topology.yaml`, vendor drivers, `obn.py`) | ❌ **not cloned** — clone this to do the nv2 code/topology work |

## Anatomy of a template repo (the standard layout — verified on nv4 @ v0.0.19)

```
nd-obn-template-dostoneu-nv4/
├── version          # plain text, e.g. "0.0.19" — bump per change
├── README.md        # human changelog, one line per version
├── build.sh         # fpm -s dir -t deb, packs src/ → filesystem root (src/=/)
└── src/             # payload laid out as TARGET FILESYSTEM
    └── etc/obn/template/...   # the .cfg.j2 templates, rules.yaml, dhcp_groups/
```

`build.sh` essentials:
```bash
version=$(cat version)
fpm -s dir -t deb -f -n "nd-obn-template-dostoneu-nv4" -v "${version}" -a all \
    --deb-no-default-config-files --provides "${name}" src/=/
```
`src/=/` ⇒ whatever path a file sits at under `src/` is where it installs. So `src/etc/obn/template/nv4-100-A1-v8.cfg` → `/etc/obn/template/...`. Single `master` branch, no feature/release branches — changes land on master, version bumps, CI (or `build.sh`) builds the deb.

## The standard change process (what we SHOULD do for nv2)

1. **Clone the repo** (`git clone git@git-nc.nomadrail.com:onboard/<repo>.git`).
2. **Branch** off master (or work on master per their convention — these repos are single-branch, so likely a short-lived MR branch).
3. **Edit `src/`** — the files exactly as they should land on the CCU.
4. **Bump `version`** + add a **`README.md`** changelog line.
5. **Commit + push, open a Merge Request** for R&D review.
6. CI builds the **versioned .deb**; on merge it publishes to the apt repo.
7. **Puppet / `nd-systemupdate`** rolls it to CCUs on the next update window — no hand-patch, survives reboots/images.

## Applying this to nv2 (the two work items, mapped to repos)

| nv2 work item | Repo / file | MR content |
|---|---|---|
| **A. Coach-numbering engine** (the `report_dosto_neu.py` patch we drafted) | **`nd-obn`** engine repo → `src/usr/share/obn/lib/report/report_dosto_neu.py` (Option A) OR `src/etc/obn/topology.yaml` + `report_generic.py` adoption (Option B) | nv2 dict + e0-1 inter-coach hop rule + bug-10 guard (Option A); or add `dostoneu2` topology map + switch `report_module` (Option B). Bump `nd-obn` version, changelog, MR. |
| **B. nv2 switch templates** | **NEW repo `nd-obn-template-dostoneu-nv2`** (mirror the nv4 repo layout) | 6 switch `.cfg.j2` (A1/A2/A3/B1/B2/B3, `2t-` hostname scheme), trimmed to bench reality (1 AP A1.e0-4, firewall A3.e1-4, A↔B on e0-1), `rules.yaml`, `dhcp_groups/`. `version` 0.0.1 + README. New package `nd-obn-template-dostoneu-nv2`. |

Plus the non-repo items: CCU **re-cable** (lan0→A1, lan1→A3) and set `train_type: nv2` + `report_module` in `backbone-discovery.yaml` (which is itself templated/Puppet-managed — confirm where that file's source lives before editing).

## Engine fork reminder (see nv2-bench-obn-enablement-plan.md)
- Option A = patch `report_dosto_neu.py` (active on ALL trains today). Bench-consistent, but Python hand-code in the engine repo.
- Option B = add `dostoneu2` to `topology.yaml` + switch to `GenericReport` (the declarative engine, deployed on ZERO trains today). Pure-data, the intended long-term home — but adopting it fleet-wide is an R&D decision, not a bench one.
- Recommendation: A for the bench now; file B as the R&D ticket. Either way the change goes through the `nd-obn` repo MR process above, **not** a CCU hand-patch.

## Package ownership — RESOLVED (dpkg -S on box1-t123, 2026-06-04)
- **`nd-obn` v2.3.8** (maintainer Darren Fitzgibbon) owns the ENGINE **and** the config yamls:
  - `/usr/share/obn/**` (report_dosto_neu.py, report_generic.py, vendor drivers, obn.py)
  - `/etc/obn/topology.yaml`, `/etc/obn/backbone-discovery.yaml`, `/etc/obn/vendors.yaml`, `/etc/obn/coach_ap_mappings.yaml`
  - `nd-backbone-discovery.service` + `.timer`
- **`nd-obn-template-dostoneu-nv4`** owns `/etc/obn/rules.yaml` (+ the templates + dhcp_groups).

⇒ **nv2 = exactly two repos:**
1. **`nd-obn`** — one MR covers the engine change (report_dosto_neu.py Option A *or* topology.yaml `dostoneu2` Option B) AND `backbone-discovery.yaml` (`train_type: nv2`, `report_module`). Engine repo name on GitLab ≈ `onboard/nd-obn` (confirm — package name is `nd-obn`, maintainer Darren Fitzgibbon; could be `nd-backbone-discovery`).
2. **NEW `nd-obn-template-dostoneu-nv2`** — 6 switch templates + nv2 `rules.yaml`, mirroring the nv4 repo layout.

⚠️ **`backbone-discovery.yaml` is package-owned but currently has hardcoded `train_type: nv4`** on this bench. Since every train can't ship the same `nd-obn` with one train_type, the per-train `train_type`/`train_id`/`ccu_ip` are almost certainly **overlaid by Puppet** (or a per-CCU config layer) on top of the package default. So flipping the bench to `train_type: nv2` is likely a **Puppet/per-CCU change**, not (only) an `nd-obn` repo edit. Confirm where the per-train override lives (Puppet `vmpuppet01.ovh.21net.com`) before assuming the repo default is the lever.

## GitLab access + repo IDs — RESOLVED (PAT `cm-devl`, 2026-06-04)
Authenticated to `https://git-nc.nomadrail.com/api/v4` as **abbas.rizvi (id 103/116)**. PAT scopes include `api`, `write_repository`.

**DOSTO template repos (all `onboard/`, `master` branch, `internal` visibility):**
| id | repo |
|---|---|
| 1183 | `nd-obn-template-dostoneu` (base — holds `dostoneu-obn-v1.cfg.j2`, shared rules.yaml, firmware) |
| 1239 | `nd-obn-template-dostoneu-nv4` |
| 1240 | `nd-obn-template-dostoneu-nv6` |
| 1358 / 1351 | `nd-obn-template-dostoneu-fv5` / `-fv6` |

`nd-obn-template-dostoneu-**nv2**` does **NOT exist** — to be created.

**Engine repo = `onboard/obn`** — DEFINITIVE. Proven by the CI build path baked into the installed venv: `/usr/share/obn/venv/pyvenv.cfg` → `command = ... /builds/onboard/obn/src/usr/share/obn/venv`. `/builds/<group>/<project>` is GitLab CI's checkout dir, so the repo is `onboard/obn` with `src/usr/share/obn/...` layout (same fpm `src/=/`). Builds `nd-obn` deb (apt: 2.3.8 installed, **2.3.10 available** in pool/unstable at vmrepo01.ovh2.21net.com).
⚠️ **`onboard/obn` is R&D-PRIVATE** — my PAT 404s on it (vs `internal`-visibility template repos which I can read). So I have **no read access to the engine source.** Engine changes (the report_dosto_neu.py / topology.yaml nv2 work) must be done BY R&D, or you need access granted to `onboard/obn`.
(Earlier guess `nd-obn-migration` id 873 was WRONG — that's a stale 2022 CyboxAP2/Normandie migration *tool*, no report modules.)

**ACCESS REALITY (decisive for who does the work):**
- On `onboard/` group (id 20) and the template/engine repos: **project_access = None, group_access = None.** You can READ (internal visibility) but have **NO push/maintainer role** on `onboard/`.
- You DO own namespaces: `abbas.rizvi` (user) + groups `puppet` (id 4), `env` (id 62).
- ⇒ **The nv2 GitLab work is a FORK → MR flow, not direct push:** fork `onboard/nd-obn-migration` and a new `nd-obn-template-dostoneu-nv2` (R&D creates it, or fork the base) into your `abbas.rizvi` namespace, push branches, open **Merge Requests to the `onboard/` repos for R&D review/merge.** R&D (group owners) merge + release. Matches the existing "file R&D tickets" model — you propose via MR, they own the merge/build/Puppet rollout.

**nv4 repo source layout (the blueprint for nv2):**
```
src/etc/obn/
├── firmware/ (IBEX-firmware-*.img, ipart-ng.kad-7-4-2)
├── rules.yaml
└── template/
    ├── dhcp_groups/{afz,energiezaehler,fis,reservierung,service,sprechstelle,video}_group.j2
    ├── dostoneu-obn.cfg
    ├── nv4-100-A1.cfg … nv4-600-B3.cfg   (12 = 4 coach × 3 sw; hostname set inside via Jinja, NOT in filename)
    └── vlans.j2
README.md (changelog) · build.sh · version · .gitignore
```
nv2 mirror = 6 switch cfgs (`nv2-100-A1/A2/A3`, `nv2-200-B1/B2/B3`) + same dhcp_groups/vlans.j2/rules.yaml/firmware, trimmed to bench reality (1 AP A1.e0-4, fw A3.e1-4, A↔B e0-1).

## 🔑 BIG FINDING — OBN config (incl. topology.yaml + train_type + report_module) is PUPPET-managed, and you have WRITE access

The OBN engine *code* is R&D-private (`onboard/obn`), BUT the **config that decides coach-numbering behavior is in Puppet/hiera, where you are a Developer.**

- **`env/environment-dostoneu`** (id **1136**, the DOSTO Puppet control repo) — **you have access_level 30 (Developer → can branch + MR).** Contains:
  - `hieradata/files/obn/topology.yaml` — **the hiera-managed source of `/etc/obn/topology.yaml`** (has `dostoneu6`/`dostoneu4` keys, anchors `wagon_a100`…`wagon_b600`; NO `dostoneu2`).
  - `hieradata/common.yaml` — sets **`obn::report_module: "GenericReport"`** and **`obn::train_type: "dostoneu"`** fleet-wide.
  - `hieradata/nodes/box1-t123.dostoneu.21net.com.yaml` — the bench CCU's per-node file (currently only `tunnel_remote_host` + `external_id: T4736023`; no train_type/obn override).
- **`puppet/obn`** (id 682, the `obn` Puppet class) — read-only for you (level 20). `manifests/init.pp` defaults **`$report_module = 'GenericReport'`**, `$train_type` "used to identify correct config from topology.yaml". `templates/backbone-discovery.yaml.epp` renders `train_type: <%= $obn::train_type %>` + `report_module: <%= $obn::report_module %>`.

**⇒ The fleet's INTENDED state is `GenericReport` + declarative `topology.yaml` (Option B), set via Puppet — NOT the hardcoded `DostoNeuReport`.** The live bench CCU showing `report_module: DostoNeuReport` / `train_type: nv4` in `backbone-discovery.yaml` is **STALE** (Puppet hasn't applied current hiera, consistent with the neglected bench). So Option A (patching report_dosto_neu.py) patches a module the fleet is migrating AWAY from. **Option B is correct, and the `dostoneu2` topology lands in a repo you can MR (environment-dostoneu / 1136).**

### ✅ MISMATCH RESOLVED — the deployed config is on branch `Engage26`, via per-traintype PIPELINE hiera

The `master` branch's `common.yaml` (`GenericReport`/`dostoneu`) is **NOT deployed** — it's aspirational. The live Puppet environment is **`dostoneu_Engage26`** → control-repo branch **`Engage26`** (active, last commit 2026-06-03). Confirmed: bench `puppet config environment = dostoneu_Engage26`, certname `box1-t123.dostoneu-bench.21net.com`, `projectName_21net = dostoneu-bench`.

**Hiera hierarchy (Engage26 `hiera.yaml`):** `nodes/%{projectname_21net}/%{certname}.yaml` → **`pipeline/%{projectname_21net}.yaml`** → hiera_file → actions → `box/box%{unitid}.yaml` → common.yaml.

**The `pipeline/<projectname>.yaml` layer is the lever** — one per train type, each pinning the OBN trio (verified on Engage26):
| pipeline file | train_type | report_module | template pkg |
|---|---|---|---|
| dostoneu-nv6.yaml | nv6 | DostoNeuReport | nd-obn-template-dostoneu-nv6 @0.0.8 |
| dostoneu-nv4.yaml | nv4 | DostoNeuReport | nd-obn-template-dostoneu-nv4 @0.0.6 |
| **dostoneu-bench.yaml** | **nv4** | DostoNeuReport | nd-obn-template-dostoneu-nv4 @0.0.2 |
| dostoneu-fv5 / -fv6 | … | … | … |

⇒ **No mismatch & no staleness — `DostoNeuReport` + `nvN` is the intentional, current fleet config.** The bench runs `train_type: nv4` because `pipeline/dostoneu-bench.yaml` says so — that's literally why a 2-coach rig has nv4 4-coach templates.

**This REVERSES the earlier Option-A-vs-B lean back to OPTION A:** the whole fleet uses the hardcoded `DostoNeuReport` BFS (which keys on `ccu1_coach_map[train_type]` — i.e. `nvN`, exactly the dict our patch extends). `GenericReport`/declarative-topology is unused. So nv2 = patch `report_dosto_neu.py` (Option A) + new nv2 template pkg + flip the pipeline file.

**THE nv2 Puppet change** (in `environment-dostoneu` branch `Engage26`, where you have Developer/30 → MR):
```yaml
# hieradata/pipeline/dostoneu-bench.yaml
obn::template_pkg_name: "nd-obn-template-dostoneu-nv2"
obn::template_pkg_ensure: "0.0.1"
obn::report_module: "DostoNeuReport"   # unchanged
obn::train_type: "nv2"                  # ← the lever (was nv4)
```
⚠️ CHECKED — do NOT flip the shared pipeline. The `dostoneu-bench` CCUs are a MIX: t121=Stadler, **t122=OBB 4C, t123=OBB 2C (target), t124=NCL 4C, t125=NCL 6T, t127=test**. All share `projectName_21net=dostoneu-bench` → all inherit pipeline `train_type: nv4`. **t127 already shows the right pattern: a per-NODE `obn::train_type` override** (node layer > pipeline layer in the hierarchy).

**⇒ THE nv2 lever = the per-NODE file (surgical, t123 only), NOT the pipeline:**
```yaml
# hieradata/nodes/dostoneu-bench/box1-t123.dostoneu-bench.21net.com.yaml  (Engage26 branch)
# OEBB 2-coach Bench
mar3_frontend::tunnel_remote_host: "77.237.62.210"
train_identification_api::external_id: "Dostoneu_Bench_OBB_2C"
obn::train_type: "nv2"                                    # ← add (overrides pipeline nv4)
obn::report_module: "DostoNeuReport"                      # ← add (explicit; matches t127)
obn::template_pkg_name: "nd-obn-template-dostoneu-nv2"    # ← add
obn::template_pkg_ensure: "0.0.1"                         # ← add
```
You have Developer (30) on this repo → branch off `Engage26`, edit this one node file, MR. Leaves all other benches untouched.

## ✅ nv2 template package — BUILT (2026-06-04)
Assembled at **`OEBB-251/nv2-template-src/`** (builder: `OEBB-251/build_nv2_template_pkg.py`), ready to push to a new `onboard/nd-obn-template-dostoneu-nv2` repo or hand to R&D. Mirrors the nv4 repo layout exactly.

- **Base = field-tested `OEBB-251/2t-bench-*-v4.cfg`** (NOT nv4 — nv4's e0-3 is `no enable`, which would isolate the CCU). **Only change per file = the hostname line** → `nv2-<pos>-v8-{{ ("%03d"|format(train_id)) }}` (verified: 1-line content diff, 0 length delta vs source). CCU/OBS port A1.e0-3 stays enabled vlan100 trunk; firewall A3.e1-4; inter-coach A1.e0-1↔B1.e0-1.
- Files: `src/etc/obn/template/nv2-100-A1/A2/A3.cfg` + `nv2-200-B1/B2/B3.cfg`, shared `vlans.j2` + `dostoneu-obn.cfg` + `dhcp_groups/*` (7) + `rules.yaml` (from nv4), `build.sh` (`name=nd-obn-template-dostoneu-nv2`), `version` 0.0.1, README.md, .gitignore.
- **`rules.yaml`** (the template selector, validated YAML): coach 1 d1/d2/d3 → nv2-100-A1/A2/A3; coach 2 d1/d2/d3 → nv2-200-B1/B2/B3; AP rules coach[1,2] d1-4 → dostoneu-obn.cfg; firmware_rules SW 7.4.2 / AP 6.11.2-0.
- ⚠️ **Firmware binaries NOT committed** (large; identical to nv4). Before `build.sh`, copy `ipart-ng.kad-7-4-2` + `IBEX-firmware-6.11.2-0.img` from the nv4 repo into `src/etc/obn/firmware/`. See `README_FIRMWARE.txt`.
- `_nv4-reference/` in that folder is scratch (pulled nv4 sources) — DO NOT commit to the nv2 repo.

### ✅ Local git repo staged, ready to push (2026-06-04)
A clean git repo is committed at **`C:/Users/AbbasRizvi/Documents/nd-obn-template-dostoneu-nv2`** — shipping files only (no `_nv4-reference`), `.gitattributes` forces **LF** endings (committed blobs verified CRLF:0), one commit on `master` (`0.0.1: initial nv2 ...`), remote `origin` set to `git@git-nc.nomadrail.com:onboard/nd-obn-template-dostoneu-nv2.git`.

**Blocked on access:** Abbas has requested `onboard/` group access (currently access_level=None → can't create/push there). Once granted (or R&D creates the empty repo + grants push), publish with:
```
cd ~/Documents/nd-obn-template-dostoneu-nv2 && git push -u origin master
```
Then add the 2 firmware binaries (per README_FIRMWARE.txt) and run build.sh / let CI build the deb. ⚠️ Don't push to a personal namespace — it must live under `onboard/` with the other template packages (engineer decision 2026-06-04).

## Who does what — RESOLVED split
- **Engine change (nv2 coach-numbering: report_dosto_neu.py / topology.yaml + backbone-discovery.yaml train_type)** → repo **`onboard/obn`**, which is **R&D-private (you can't even read it).** ⇒ **R&D does this** — hand them the drafted `scripts/fix_obn_nv2_report_dosto_neu.py` (Option A) or the dostoneu2-topology spec (Option B) as a ticket/MR-request. Confirm whether their HEAD still uses DostoNeuReport or has moved to GenericReport before they pick A vs B.
- **nv2 switch templates** → new repo `onboard/nd-obn-template-dostoneu-nv2` (you can READ the sibling template repos but lack create/push on `onboard/`). ⇒ R&D creates it, OR you fork the base/nv4 repo into `abbas.rizvi/` and MR. The template content I CAN draft (we have read access + the nv4 blueprint).
- **Per-train `train_type: nv2` flip** → likely the **`puppet`** group (id 4, you're a member). Check puppet repos for the bench CCU's role/hiera — this lever may be yours directly.

## Open items to confirm on GitLab (next session)
- Get **read access to `onboard/obn`** (engine) so the nv2 engine patch can be drafted as a real MR instead of handed off blind; OR confirm R&D owns it end-to-end.
- Check **`puppet`** group repos (id 4) for where the bench CCU sets `train_type` — that's the lever to flip to nv2 without an nd-obn change.
- bump note: apt has **nd-obn 2.3.10** (CCU on 2.3.8) — confirm what 2.3.9/2.3.10 changed (may already touch nv2 / GenericReport).
