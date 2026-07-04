# Puppet pin changes — DOSTO NEU CAT/FV pilot (fv5/fv6)

Repo: `environment-dostoneu`, branch **`dostoneu_migration_mar5`**
Applies AFTER packages are published to vmrepo01/unstable:
- nd-obn **2.3.14** (from OBN MR #63, once merged + tagged)
- nd-obn-template-dostoneu-fv5 **0.0.18**
- nd-obn-template-dostoneu-fv6 **0.0.18**

## Key facts (verified from live CCU catalog 2026-07-02)
- OBN package pin: hiera key **`obn::pkg_ensure`** → renders `Package['nd-obn'] ensure=>` in `nomad_connect/obn/manifests/package.pp:28`. Currently **"2.2.23"**.
- Template package pin: key **`template_pkg_name`** / **`template_pkg_ensure`** (per-fleet). On nv4 it's `nd-obn-template-dostoneu-nv4` @ `0.0.19`. For fv5/fv6 the fleet suffix + version differ.

## Change 1 — OBN version (fleet-wide DOSTO, or scope to CAT/FV only if piloting)
```yaml
obn::pkg_ensure: "2.3.14"      # was "2.2.23"
```
⚠️ This is likely a COMMON/dostoneu-level value → bumping it moves ALL DOSTO trains to 2.3.14 on their next factory-up/puppet run. If you want CAT/FV ONLY for the pilot, set it at the fv5/fv6 NODE level (per box1-tNN.yaml) instead of common, and leave common at 2.2.23 until the pilot proves out.

## Change 2 — Template package pins (per-fleet)
fv5 nodes:
```yaml
template_pkg_ensure: "0.0.18"   # nd-obn-template-dostoneu-fv5, was 0.0.16
```
fv6 nodes:
```yaml
template_pkg_ensure: "0.0.18"   # nd-obn-template-dostoneu-fv6, was 0.0.16
```
(template_pkg_name is already the right fleet package per node's train_type — only the version/ensure changes.)

## WHERE to set them (hiera hierarchy — confirm actual layout in repo)
Typical: `data/common.yaml` (fleet-wide) vs `data/nodes/box1-t<N>.yaml` (per-train).
- OBN 2.3.14: node-level for pilot (t41/t42/t43 = CAT) OR common for whole fleet — DECIDE based on pilot vs full rollout.
- Template 0.0.18: fv5/fv6 scope. If hiera keys off train_type/project, set at that scope; else per CAT/FV node.

## Cautions
- exact-version pins (not `latest`) — apt installs the specific version even from `unstable` channel (2.3.14/0.0.18 land in unstable first, promote to main after pilot).
- Only change the OBN + fv5/fv6 template keys. Do NOT touch other pkg_ensure (wifi-control, 21net-security, etc.).
- Puppet auto-run is DISABLED on CCUs → change takes effect on next manual `puppet agent -t` (inside nd-systemupdate shell) or factory-up. So pilot trains get it exactly when you re-image them.

## Verify after applying (on a pilot CCU, inside nd-systemupdate shell where puppet runs)
```
apt-cache policy nd-obn                              # candidate/installed = 2.3.14
apt-cache policy nd-obn-template-dostoneu-fv5        # = 0.0.18
grep -E 'train_type|report_module' /etc/obn/backbone-discovery.yaml   # fv5 + DostoNeuReport
```
