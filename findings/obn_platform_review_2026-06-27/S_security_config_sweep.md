# S — Targeted Security/Config Sweep (origin/master v2.3.12)

Closes the non-code audit gap that finding S3 exposed. Method: 4-hunter sweep over the under-audited
surface (config secrets, git history, packaging, CI/CD, perms, guardrails). **Verification note:** the
workflow's adversarial-verify phase failed (every verifier hit a session limit), so the structured
confirmed/refuted arrays came back empty. **All findings below were therefore re-verified directly by the
engineer via read-only git/grep/sed** (commands + outputs in session) rather than trusted from unverified
agent output — they stand on first-hand evidence.

## The S3 cluster — credential exposure (all HIGH, one root, several amplifiers)

| ID | Finding | Evidence (self-verified) |
|---|---|---|
| **S3** | Plaintext SNMP/SSH creds committed in `vendors.yaml` | 12 `snmp_password` + 2 `ssh_password` + 1 `enable_password "admin"` + 1 `snmp_v2c_community "SW_V1A_R0"`, all cleartext (grep w/ line numbers). |
| **S4** | **Password reuse across the fleet** | `NomadStayOut!` repeated across **8** vendor blocks (moxa/lantech/lantech_6000/vdsrail/eltec_cybox/westermo/acksys…), `NomadComeIn` across **3**. One leaked string ⇒ SNMP **write** on most devices, incl. the `vdsrail` consist switches this project commissions. These are not read-only — same creds drive config/firmware/reboot OIDs. |
| **S5** | **Secrets baked into the published `.deb`** | `.gitlab-ci.yml:77` `fpm … src/=/` ships `/etc/obn/*.yaml` verbatim into the `nd-obn` package pushed to the registry → wider audience than repo read access. |
| **S6** | **World-readable on every CCU** | `packaging/postinst.sh` chmods only scripts/obn.py — **never** `/etc/obn/*.yaml`; fpm preserves source mode **644**. So device passwords are readable by **any local unprivileged user** on each CCU. Compounded: `serve-api` + `telemetry` systemd units run **`User=root`**. |
| **S7** | **Secrets persist in git history, never rotated** | Introduced years ago (`RD-8288` westermo, `RD-8067` folder rename); across **64** commits touching the file, `git log -S` shows **no removal/rotation** — every secret still recoverable from history. |
| (context) | The `secret.yaml` override is **dead** | `vendors.yaml` header (L5–7) says "DO NOT CHANGE THIS FILE … only valid version is the one in the OBN .deb" → the intended `secret.yaml` override path (snmpdevice.py:131) is effectively decorative; cleartext defaults ARE the production creds. |

## Guardrail gap (why this class can recur silently)
- **No secret scanner anywhere** — `.pre-commit-config.yaml` runs bandit (code SAST) only; `.gitlab-ci.yml`
  runs pip-audit (dependency CVEs) only. A committed credential passes every gate.
- **`.gitignore` has zero credential patterns** (no `secret`, `*.env`, `credentials`, `*.key`, `*.pem`) —
  nothing stops a future `secret.yaml` from being committed too.
- **Recommended guardrail (no external action taken):** add `gitleaks` (or trufflehog/detect-secrets) to
  pre-commit **and** CI; add `secret.yaml` + `*.env` + key patterns to `.gitignore`; ship a
  `secret.yaml.example` template; relax the "do not change" header so the override path is usable.

## Surfaces checked and found CLEAN (scoping honesty)
- `vendors_extra.yaml`, `backbone-discovery.yaml`, `coach_ap_mappings.yaml`, `topology.yaml` — no secrets
  (MAC prefixes, OIDs, project/train ids, port maps, MQTT-on-localhost only).
- `docs/`, systemd units (no `Environment=` secrets), `tmpfiles.d`, `tools/update_version.py`, `metrics.sh`
  — no creds, no dangerous shell.
- `prerm.sh` `rm -rf` targets a hardcoded build-time path — **not** a vuln.
- No `*secret*.yaml` was ever committed — the exposure is entirely via `vendors.yaml`.

## Lower-severity / informational
- `lib/logging.py` MQTTHandler publishes formatted log records to an MQTT broker — a conditional exfil
  *path* (risk depends on log content/level), not a standalone secret leak. Worth a look when hardening.
- Internal infra hostnames exposed in CI/Makefile/README (`docker-registry-01.nomadrail.com`,
  `vmrepo01.ovh2.21net.com`, `git-nc.nomadrail.com`) — minor info-leak.

## Bearing on replace-vs-improve
Unchanged verdict: **IMPROVE.** This entire cluster is **process/config/packaging**, not program logic — a
rewrite would not prevent any of it (you can commit plaintext secrets into a brand-new codebase just as
easily). The fixes are in-place and largely one-time (rotate, move to ignored secret file, chmod 600 in
postinst, add a scanner). It does, however, raise the **urgency** of a security-hardening workstream and
drops the dependency/security score to 3/5.

## Methodology lesson (why S3 was missed first time)
P2 grepped for hardcoded creds in **`.py` source only** and treated "value comes from config" as safe,
without auditing the committed config file itself. The logic sweeps (P3/C3) were scoped to code defects, so
a secrets-in-repo issue fell **between** phases. Fix for future reviews: treat committed config + git
history + packaging + CI artifacts as first-class security surfaces, and run an automated secret scanner —
don't rely on manual source grep.
