# SysOps ticket — provision admin21net SSH key across DOSTO release/deploy hosts

**Requested by:** Abbas Rizvi (abbas.rizvi@nomadrail.com)
**Date:** 2026-07-03
**Priority:** Medium — blocks DOSTO Puppet env deploys (migration_mar5 stuck stale on master)

---

## Summary (the ask, in 2 lines)

Please add my `admin21net` SSH public key to **vmpuppet01** so I can run DOSTO Puppet
environment deploys, and **verify/persist** the same key already in use on **git-nc** and
**vmrepo01** so it survives any future rotation. One key, three hosts.

## The key

| Field | Value |
|---|---|
| Identity / user | `admin21net` |
| Key type | ed25519 |
| Fingerprint | `SHA256:6maEvELmjhoWnLR0AnRFbgjqON0hfq/dPXE+aC1Kc4I` |
| Comment | `abbas.rizvi@nomadrail.com` |

Public key (append to the relevant `~admin21net/.ssh/authorized_keys` / GitLab key config):

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMJlg7RQFTlq/pvm9sne7e9kPxIpoVenC9147MAzgwuY abbas.rizvi@nomadrail.com
```

## Hosts

| # | Host | User | Action needed | Current state |
|---|---|---|---|---|
| 1 | `vmpuppet01.ovh2.21net.com` (Deb12 master, `192.168.66.14`) | `admin21net` | **ADD key** | Blocked — `Permission denied (publickey)` |
| 2 | `git-nc.nomadrail.com` (GitLab) | `admin21net` / abbas.rizvi | **Verify/persist** | Working today (push/pull OK) |
| 3 | `vmrepo01.ovh2.21net.com` (apt repo) | `admin21net` | **Verify/persist** | Working today (deb publish OK) |

Note: host #1 is the **Deb12** master `vmpuppet01.ovh2.21net.com` (with the "2"), NOT the
legacy Deb10 `vmpuppet01.ovh.21net.com`. DOSTO runs Deb12 / Nomad Connect 2023.3+.

## Why this is needed

The DOSTO commissioning pipeline ends in a Puppet env deploy to the master. The
`rake ci:deploy:remote` task (from `env/environment-dostoneu`) runs
`ssh admin21net@vmpuppet01.ovh2.21net.com` to refresh the master's clone of the
`migration_mar5` branch. That SSH currently returns `Permission denied`, so merged DOSTO
changes never reach the trains.

Evidence: current GitLab HEAD of `migration_mar5` = `8cc76f14`; the master is serving the
older `d79f96d8` — confirmed across three CCUs (box1-t19, box1-t29, box1-t42) on 2026-07-03.
Until the master's clone is refreshed, no DOSTO train can pull the latest config.

The Nomad Connect deployment guide and the CCU install guide both state the master key is
added by "R&D or sysadmin" — hence this ticket.

## One extra check (host #1)

Please confirm the existing env clones under
`/etc/puppetlabs/code/environments/dostoneu_migration_mar5` (and its `_staging` / `_devel`
siblings, if present) are owned `admin21net:admin21net`, so the deploy task can write to them.

## Acceptance / how I'll verify

Once done I'll confirm with:
```
ssh admin21net@vmpuppet01.ovh2.21net.com 'hostname'
```
returning the master hostname (no password prompt).
