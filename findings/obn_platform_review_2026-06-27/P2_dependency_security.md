# P2 — Dependency & Security Audit (origin/master v2.3.12)

Read-only. Citations are `file:line` under `src/usr/share/obn/`. CVE scan = pip-audit on pinned deps.

## Dependency health
- 25 runtime deps, fully pinned (`pyproject.toml`); `uv.lock` present and CI-protected.
- **pip-audit: "No known vulnerabilities found"** (all pinned runtime + dev deps). See `baseline/pip_audit.txt`.
- Versions are current (FastAPI 0.137, cryptography 48.0.1, paramiko 5.0.0, requests 2.33). Not a stale
  dependency tree.

### Supply-chain flag (LOW–MED) — `httpx2` / `httpcore2` fork
- `cli/update.py:15` and `lib/ospf.py:35`: `import httpx2 as httpx`.
- `uv.lock`: `httpx2==2.3.0` from `registry = https://pypi.org/simple` (a real public package, not a
  lockfile typosquat), pulling `httpcore2`. Introduced by commit `2cddeef` "Fix references for HTTPX to
  HTTPX2 after vulnerability fixes."
- **Risk:** these are low-profile third-party *forks* of `httpx`/`httpcore`, not the upstream packages.
  Smaller maintainer base → slower security response and a larger trust surface than depending on
  mainstream `httpx`. No current CVE, but worth a deliberate "why this fork, and who maintains it?"
  before either path. Cheap to reverse if upstream httpx is now patched.

## Security surface

### FINDING S1 (MED–HIGH) — REST API has no authentication, state-changing ops are GET
- `lib/server/server.py` mounts `/consist` + `/actions` with **no auth** (no API key/JWT/Depends guard;
  zero auth keywords in `lib/server/`).
- `routers/actions.py` exposes **hardware-affecting operations as HTTP GET**:
  `GET /reset_device/{ip}` (actions.py:20), `GET /togglepoe/{ap_ip}/{state}` (actions.py:83),
  `GET /getlog/{ip}` (actions.py:53). `reset_device` reboots a device on a live train.
- GET-for-mutation is itself a flaw (CSRF-able, cacheable, prefetchable, leaks into access logs),
  compounded by no auth.
- **Severity is exposure-dependent:** if `serve_api` binds localhost-only it is low; if reachable from
  the management VLAN it is high. The determining control (bind address / network ACL) is config/Puppet,
  not in-app — so the code provides **no defense-in-depth** regardless. Recommend: add an auth dependency
  + switch mutations to POST regardless of binding. (Cheap, isolated change — an "improve" data point.)

### FINDING S3 (HIGH) — plaintext SNMP/SSH credentials committed in the repo
- OBN reads device credentials as **plaintext** from config: `snmp_user`, `snmp_password` (used for BOTH
  the auth AND priv passphrases — snmpdevice.py:165–167), and `snmp_v2c_community` (snmpdevice.py:158).
  There is **no decryption / keyring / vault layer** anywhere in OBN.
- The live credentials are **committed to the OBN git repo** in `src/etc/obn/vendors.yaml` (present in
  `HEAD` since commit `5429a28`): **12 distinct `snmp_password` values, 2 `ssh_password`, and a v2c
  community string** in clear text — the real production secrets (`NomadStayOut!`, `NomadComeIn`,
  `DelicateSoundofThunder`, `SW_V1A_R0`, …). Anyone with repo read access, a copy of the `nd-obn` .deb, or
  read access to `/etc/obn` on any CCU obtains every device credential fleet-wide.
- A safer mechanism **exists but is not enforced**: `secret.yaml` (snmpdevice.py:132 — "Some projects use
  non-default uname and pw, if so: find them in secret.yaml") overrides per-brand creds. But it is optional,
  `vendors.yaml` still ships live passwords as the default, and `secret` is **not in `.gitignore`**. The
  insecure default is what ships.
- **This is the most serious security finding in the review** — a fleet-wide credential exposure baked into
  version control, above S1 (which is exposure-dependent). Recommendation (no external action taken here):
  rotate the exposed passwords on devices; move all secrets to `secret.yaml`; add `secret.yaml` to
  `.gitignore`; replace the committed values in `vendors.yaml` with placeholders; and scrub the secrets from
  git history. Process gap, not a logic bug — fixable in place.

### FINDING S2 (LOW) — weak SNMPv3 crypto defaults; SNMPv2c still allowed
- Default USM profile is **MD5 auth + DES priv** (snmpdevice.py:143–144); AES is available
  (`usmAesCfb128Protocol`, line 149) but not the default.
- Legacy **SNMPv2c `CommunityData`** path retained (snmpdevice.py:162, `# nosec B508`).
- Reasonable for old rail hardware that may not support better, but worth a config push toward AES where
  devices allow. Not a code defect. Compounds S3: the same plaintext `snmp_password` is reused as both
  passphrases.

### Injection surface — CLEAN
- Only **2 subprocess calls** in the codebase (`lib/lldp.py:23`, `lldparpwalker.py:157`), both list-form,
  `shell=False`; the one interpolated value (`interface`) comes from local NIC enumeration, not user
  input. **No `shell=True`, no `os.system`.**
- `getlog` keyword filtering is pure-Python `key in x` (actions.py:78) — not shelled. No command injection.
- **No hardcoded credentials in Python source** — BUT credentials ARE committed in plaintext in the
  `vendors.yaml` config (see S3). The earlier "no hardcoded credentials" phrasing applied only to `.py`
  source and understated the real exposure; S3 corrects it.
- jinja2 templating uses `StrictUndefined`; template inputs are train_id/coach numbers (operator config),
  not external user input → SSTI risk is theoretical only.

### Error-handling review — DEFENSIBLE
- All **6 broad `except Exception`** are intentional and documented (each logs or carries a rationale:
  acksys "device may be rebooting after successful upload" (497), tipg541 SSH catch-all (204),
  logging.py self-`handleError` (59), actions.py logs + returns `{"success": False}` (48), lldparp
  ignores non-SNMP devices (217)). **0 bare `except:`.** Not a smell.

## P2 verdict
Dependencies are current and CVE-clean; injection surface is clean; error handling is disciplined. The two
real security gaps are **S3 (HIGH — plaintext SNMP/SSH credentials committed in `vendors.yaml`)** and **S1
(MED–HIGH — unauthenticated, GET-mutating REST API)**. Both are well-scoped, in-place fixes (move secrets to
an ignored `secret.yaml` + rotate + history-scrub for S3; add auth + POST for S1). Neither argues for a
rewrite. **Correction to the first-pass note:** "no hardcoded credentials" held only for Python source —
the committed config carries live secrets, which S3 now captures.
