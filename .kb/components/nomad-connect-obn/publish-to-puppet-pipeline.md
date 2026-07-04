---
type: component-knowledge
title: Nomad Connect / OBN — publish → Puppet deploy pipeline
description: The 7-step path a template/engine change walks to reach a train — build, publish to the apt repo, pin in Puppet, deploy the env to the master — and why merging git alone changes nothing.
component: nomad-connect-obn
project: dosto-neu
tags: [obn, puppet, deploy, apt, vmrepo, vmpuppet, release, ci, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

An OBN config/firmware/engine change is **not live on trains** until it walks the whole release
pipeline. **Merging git is step 3 of 7.** The single most common mistake is assuming a merged (or even
built-and-published) change has reached the fleet — it has not, until the Puppet **master's env clone**
is refreshed and the CCU pulls the new catalog. This doc is the map of that path.

```
1 edit templates/engine  →  2 bump version  →  3 git push/merge  →  4 build .deb  →
5 publish to the apt repo  →  6 pin the version in the Puppet env (hieradata)  →
7 deploy the env to the Puppet MASTER  →  8 factory up / puppet agent -t on the CCU (pulls from master)
```

> **Portability note.** The host names (`vmrepo01`, `vmpuppet01`), env/branch names, package names,
> user `admin21net`, and dates below are DOSTO-NEU specifics. The build → publish → pin → deploy-to-master
> → agent-pull *shape* is generic to a Puppet-managed apt-delivered fleet.

# Two package families, two publish paths

The step-4/5 publish differs by what you changed:

| Family | Packages | CI? | How to publish |
|---|---|---|---|
| **Templates** | `nd-obn-template-dostoneu-{nv4,nv6,fv5,fv6}` | **No CI** | Build with `./build.sh` (needs `fpm`), then **publish MANUALLY**: `scp` the `.deb` to the repo host and run the register script (registers into *unstable*; a `-promote` flag moves unstable → main). Bump `version` first — the register script refuses duplicate versions. |
| **OBN engine** | `onboard/obn` → package `nd-obn` | **Has CI** | Release = merge MR + `make tag` (git tag) → CI builds and publishes. **Do NOT hand-build/publish the engine** — it's shared across all fleets and CI-gated (large test suite). |

The template repos have only `build.sh` and no `.gitlab-ci.yml`, which is why they're manual. The engine
repo is CI on tag.

# Steps 6–8: the deploy is master/agent, NOT "CCU pulls git"

This is the part that trips people. CCUs are **Puppet agents** that fetch their catalog from the
**master**. The master holds a **git clone per branch** of the env; **all DOSTO trains deploy from one
branch**. Merging to GitLab does **nothing** to trains until the master's clone is refreshed:

```
GitLab env repo (branch)  --- has your merged change ---
   │   deploy step: ssh <master> 'cd <envdir> && nd-update-puppetenv.sh <branch>'
   ▼
Puppet MASTER : /etc/puppetlabs/code/environments/<env>_<branch>   ← master serves THIS clone
   │   factory up  /  puppet agent -t  →  CCU fetches catalog from master
   ▼
CCU applies it
```

**The master does NOT auto-sync from GitLab.** Proven: a pin was pushed to the branch, and three CCUs
still reported the *old* commit ~a day later. You **must** run the deploy after any push:

```bash
ssh <release-user>@<master>
cd /etc/puppetlabs/code/environments/<env>_<branch>
sudo nd-update-puppetenv.sh <branch>
```

`nd-update-puppetenv.sh` does `git reset --hard` → `git clean -fd` → `git pull --tags --rebase` →
`git submodule update --init`, and it temporarily blocks/unblocks the train subnets during the pull so
CCUs don't fetch a half-updated env. (This is what `rake ci:deploy:remote` wraps.)

**How a CCU learns its target:** `nd-systemupdate.sh` queries a train-internal host literally named
`puppet` (`http://puppet/puppetmaster`) for the target git hash — the CCU **cannot** resolve the
master's public FQDN. Its reported **"Remote version"** = the *master's* copy (which lags GitLab until
you deploy). Verify a CCU picked up a change with `nd-systemupdate.sh.dont version` — its "Remote
version" should equal GitLab HEAD after the deploy.

# What `dbc` / the env-selection API is NOT

`dbc12 <fqdn> <branch>` (via the master's `:9494` HTTP env API) only **selects which branch** a CCU
uses and clears certs (`dbc12 -c <fqdn>` — needed after a re-IP factory-up hits "certificate does not
match its private key"). **It does NOT deploy or refresh env code.** DOSTO CCUs are already set to the
right branch, so `dbc` is not the missing step — the stale master clone is. Don't set a CCU to literal
"master" (the script refuses).

# Proven dead ends — do NOT repeat these

> Approaches tried and disproven end-to-end.

1. **Do NOT assume merging to GitLab reaches trains.** Merge is step 3 of 7. Proven: a pushed pin left
   three CCUs on the old commit ~a day later. The master's env clone stays stale until you run the deploy.
2. **Do NOT assume the master auto-syncs.** It does not (verified across three CCUs). You must run
   `nd-update-puppetenv.sh <branch>` on the master after every push.
3. **Do NOT treat `dbc12` / the `:9494` env API as a deploy shortcut.** It selects a branch and clears
   certs; it does not refresh env code. The trains are already on the right branch.
4. **Do NOT hand-build/publish the `nd-obn` engine.** It's CI-gated and fleet-shared. Release it via
   MR + `make tag`; let CI build and publish. Only the *templates* are hand-published.
5. **Do NOT publish a `.deb` without bumping `version`.** The register script refuses duplicate versions
   ("Registration of same version is NOT allowed"). Bump first.
6. **Do NOT scp/ssh to the release hosts from WSL2.** WSL2 does not route the Windows VPN — you get
   "Connection closed by port 22" even though ping/port appear to work. scp/ssh from **Git-Bash
   (Windows)**; WSL-built debs are reachable from Git-Bash at `//wsl$/Ubuntu/home/<user>/...`.
7. **Do NOT verify a publish from a read-only/transactional CCU's apt cache.** A hand-hacked RO CCU
   can't refresh its apt index (`apt-cache madison` shows stale). Verify **server-side** by grepping the
   repo's `Packages` index, or use a writable CCU.
8. **Do NOT `factory up` a 6-car / CAT / FV train with box-id = Fzg.** `factory up`'s train-ID field is
   capped 0–127 (it is the 3rd IP octet). Fzg ≥ 128 (4736/4706/4705) is rejected. The v9 templates that
   drop the `128+train_id` remap assume train_id = Fzg and render **wrong hostnames** on a box-id-commissioned
   6-car/CAT/FV train — do not `obn update c` such a train. box=Fzg is viable only for 4734 (Fzg 1–90).

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- **Apt repo host:** `vmrepo01.ovh2.21net.com` (192.168.67.19), repo root `/data/repositories/bookworm/`
  (bookworm = Debian 12 = the CCUs). Register with `sudo nd-registerpkg-bookworm.sh /tmp/<deb>`
  (→ unstable; `-promote` → main). Verify: `grep <name>_<ver> /data/repositories/bookworm/dists/bookworm/unstable/binary-amd64/Packages`.
- **Puppet master:** `vmpuppet01.ovh2.21net.com`. Env clone dir
  `/etc/puppetlabs/code/environments/dostoneu_migration_mar5`. **All DOSTO trains deploy from branch
  `migration_mar5`.** Deploy: `sudo nd-update-puppetenv.sh migration_mar5`. `rake` wrappers:
  `ci:deploy:init` (first-time clone), `ci:deploy:remote` (update — use this).
- **Release identity:** user `admin21net`, key = Abbas's `~/.ssh/id_ed25519` (same key as git-nc). As of
  2026-07-03 it is on git-nc + vmrepo01 + vmpuppet01 (all three) — full pipeline runnable end-to-end.
- **CCU target query:** `PUPPETMASTER_QUERY_URL="http://puppet/puppetmaster"`; verify pickup with
  `nd-systemupdate.sh.dont version` (its "Remote version" = master's served hash).
- **Evidence:** no-auto-sync proven 2026-07-03 (pin `8cc76f1` pushed; box1-t19/t29/t42 all still
  `d79f96d8` ~a day later; deploy on vmpuppet01 fast-forwarded them). fv5/fv6 templates `0.0.18`
  published to unstable 2026-07-02. box=Fzg 127-octet ceiling hit on box1-t41 (4705-103, target Fzg 231)
  2026-07-03. SysOps access ticket: `SYSOPS_TICKET_admin21net_key_hosts_2026-07-03.md`.

# Related

- [Nomad Connect / OBN — the 11-bug suite](/.kb/components/nomad-connect-obn/bug-suite.md)
- [Nomad Connect / OBN — NDSU chroot persistence](/.kb/components/nomad-connect-obn/ndsu-chroot-persistence.md)
- [Nomad Connect / OBN — TFTP conntrack helper gap](/.kb/components/nomad-connect-obn/tftp-conntrack-helper.md)

# Citations

[1] Memory `project_puppet_deploy_chain_vmpuppet01.md` — no-auto-sync proof, deploy command, CCU target query, dbc-is-not-deploy.
[2] Memory `project_obn_deb_publish_process.md` — vmrepo01 register script, unstable/main, no-CI templates vs CI engine, WSL-VPN trap.
[3] Memory `project_box_fzg_breaks_127_octet_limit.md` — factory-up 0–127 cap; wrong hostnames for 6-car/CAT/FV.
[4] `CLAUDE.md` § "OBN / template release + deploy pipeline" — the canonical 7-step diagram.
