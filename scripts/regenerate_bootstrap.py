#!/usr/bin/env python3
"""
Regenerate the DOSTO bootstrap markdown file from the live project tree.

Usage:
    python scripts/regenerate_bootstrap.py                       # writes BOOTSTRAP_DOSTO_v1.md
    python scripts/regenerate_bootstrap.py --output FILE.md      # custom output path
    python scripts/regenerate_bootstrap.py --check               # dry run, just report sizes
    python scripts/regenerate_bootstrap.py --include-state       # include fleet-status, handoff, etc. (large!)

The bootstrap is a single self-contained markdown file the engineer pastes into
a fresh Claude Code session. Claude reads the STEP blocks in order and creates
every file with the exact content given. No git, no MCP-clone, no remote
dependency — just the file + Claude.

Default mode embeds the "scaffold" content (skills, agents, contracts, CLAUDE.md,
settings, scripts) but NOT the project state docs (fleet-status.md, handoff.md,
runbooks). State docs are large and change frequently; the engineer copies them
separately from a companion archive or another machine. Pass --include-state to
embed them too (produces a larger bootstrap, ~10k lines).

Run this whenever you change a skill, agent definition, or contract — the
bootstrap stays canonical.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Layout — what the bootstrap creates and what it embeds.
# ---------------------------------------------------------------------------

# Paths are relative to the project root (parent of scripts/).
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directories the bootstrap creates with `mkdir -p`. Order doesn't matter; the
# regenerator emits one mkdir line per entry. Empty directories that the
# engineer fills in separately (PDFs, the openssh key) live here too.
DIRECTORIES = [
    ".claude/agents",
    ".claude/commands",
    ".claude/contracts",
    ".claude/skills",
    ".claude/logs",
    "docs",
    "scripts",
    "findings",
    "reports/customer",
    "reports/internal",
    "reports/_archive",
    "trackers",
    "train-ip-allocation-commission/extracted/_shared",
]

# Files embedded in STEP blocks. Each entry is (rel_path, fence_lang).
# fence_lang controls the markdown code-fence label — "markdown", "json",
# "python", "bash". For "markdown" content, the regenerator uses ~~~~ (4 tildes)
# instead of ``` so the embedded content's own fences don't break the outer
# fence.
EMBEDDED_FILES_SCAFFOLD = [
    # Settings + MCP
    (".claude/settings.local.json", "json"),  # if present — engineer-specific
    # Contracts (4)
    (".claude/contracts/subagent-report.md", "markdown"),
    (".claude/contracts/autonomy-boundary.md", "markdown"),
    (".claude/contracts/approval-gates.md", "markdown"),
    (".claude/contracts/confluence-sync.md", "markdown"),
    # Agents (1, reduced from 2 in v2 — dosto-orchestrator retired per audit F5 2026-05-11; orchestration logic lives in dosto-orchestrate skill)
    (".claude/agents/dosto-train-worker.md", "markdown"),
    # Skills (14) — alphabetised for deterministic output
    (".claude/skills/dosto-ap-config-update/SKILL.md", "markdown"),
    (".claude/skills/dosto-ap-firmware-update/SKILL.md", "markdown"),
    (".claude/skills/dosto-commission-train/SKILL.md", "markdown"),
    (".claude/skills/dosto-confluence-sync/SKILL.md", "markdown"),
    (".claude/skills/dosto-device-discovery/SKILL.md", "markdown"),
    (".claude/skills/dosto-extract-train-data/SKILL.md", "markdown"),
    (".claude/skills/dosto-fzg-id-check/SKILL.md", "markdown"),
    (".claude/skills/dosto-l2-health/SKILL.md", "markdown"),
    (".claude/skills/dosto-l2-report/SKILL.md", "markdown"),
    (".claude/skills/dosto-obn-patches/SKILL.md", "markdown"),
    (".claude/skills/dosto-orchestrate/SKILL.md", "markdown"),
    (".claude/skills/dosto-state-inventory/SKILL.md", "markdown"),
    (".claude/skills/dosto-sw-config-update/SKILL.md", "markdown"),
    (".claude/skills/dosto-sw-firmware-update/SKILL.md", "markdown"),
    (".claude/skills/dosto-tftp-helper-check/SKILL.md", "markdown"),
    (".claude/skills/dosto-vlan7-config/SKILL.md", "markdown"),
    # Scripts (the OBN fix scripts + LLDP topology check + workspace validator;
    # engineer needs these canonical to drive the recipes the skills print, and
    # to run validation pre-flight before any orchestration session)
    ("scripts/fix_obn.py", "python"),
    ("scripts/fix_obn_bug8.py", "python"),
    ("scripts/fix_obn_bugs67.py", "python"),
    ("scripts/fix_bug1_regex.py", "python"),
    ("scripts/lldp_topology_check.py", "python"),
    ("scripts/validate_dosto_workspace.py", "python"),
    # Project constitution — must come AFTER skills/agents/contracts so its
    # cross-references are valid by the time it's written. (Order in the
    # bootstrap is order of `Write` operations, but Claude reads the whole file
    # before acting; ordering matters only for the engineer's mental model.)
    ("CLAUDE.md", "markdown"),
    # The regenerator script itself — included so a future engineer can update
    # the bootstrap without finding the original. Self-replicating scaffold.
    ("scripts/regenerate_bootstrap.py", "python"),
]

# Files embedded only when --include-state is passed. These are project-state
# (which changes daily) rather than scaffold (which changes when the design
# evolves). Default off because they bloat the paste and the engineer typically
# already has the latest state from a separate copy.
EMBEDDED_FILES_STATE = [
    ("fleet-status.md", "markdown"),
    ("train-login-checklist.md", "markdown"),
    ("troubleshooting-runbook.md", "markdown"),
    ("cable-issues-register.md", "markdown"),
    ("iperf3-troubleshooting.md", "markdown"),
    ("handoff.md", "markdown"),
]

# Files that exist in the live tree but are deliberately NEVER embedded.
NEVER_EMBED = {
    "openssh",  # SSH private key — engineer brings their own copy
    "pvt_key.ppk",  # Same
    "package.json",  # Regenerated; node_modules excluded entirely
    "package-lock.json",  # Same
    ".gitignore",  # Per-engineer preference; not part of the bootstrap
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read_file(rel_path: str) -> str | None:
    """Read a file relative to the project root. Returns None if absent."""
    p = PROJECT_ROOT / rel_path
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def fenced_block(content: str, lang: str) -> str:
    """
    Wrap content in a fenced code block. Markdown content uses 4-tilde fences
    so embedded ```language blocks inside the content don't terminate ours.
    """
    if lang == "markdown":
        return f"~~~~markdown\n{content.rstrip()}\n~~~~"
    return f"```{lang}\n{content.rstrip()}\n```"


def step_block(step_num: int, title: str, body: str) -> str:
    """Format a single STEP block."""
    return f"## STEP {step_num} — {title}\n\n{body}\n\n---\n"


def emit_directory_step(step_num: int) -> str:
    """STEP for creating directory structure."""
    cmds = "\n".join(f"mkdir -p {d}" for d in DIRECTORIES)
    body = f"Run these commands first:\n\n```bash\n{cmds}\n```"
    return step_block(step_num, "Create directory structure", body)


def emit_settings_step(step_num: int) -> str:
    """STEP for the settings file (if it exists)."""
    settings = read_file(".claude/settings.local.json")
    if settings is None:
        # Provide a sensible default if no settings file exists
        settings = """{
  "permissions": {
    "allow": [
      "Bash(ssh -i C:/Users/*/Documents/dosto-troubleshooting/openssh developer@10.179.*.1 *)",
      "Bash(ssh -i C:/Users/*/Documents/dosto-troubleshooting/openssh -o * developer@10.179.*.1 *)",
      "Bash(sshpass -p Nom@dCome1n *)",
      "Bash(scp -i C:/Users/*/Documents/dosto-troubleshooting/openssh *)",
      "Bash(ls *)",
      "Bash(wc -l *)",
      "Bash(stat *)",
      "Bash(date *)"
    ]
  }
}"""
    body = f"Create `.claude/settings.local.json`:\n\n```json\n{settings.rstrip()}\n```"
    return step_block(step_num, "Create `.claude/settings.local.json`", body)


def emit_file_step(step_num: int, rel_path: str, lang: str) -> str | None:
    """
    STEP for writing a single embedded file. Returns None if the source file is
    missing — the regenerator skips silently rather than failing, so a partial
    tree still produces a usable bootstrap.
    """
    content = read_file(rel_path)
    if content is None:
        return None
    body = (
        f"Create `{rel_path}` with the following exact content:\n\n"
        f"{fenced_block(content, lang)}"
    )
    return step_block(step_num, f"Create `{rel_path}`", body)


def emit_verification_step(step_num: int) -> str:
    """STEP for the post-bootstrap verification checklist."""
    body = """After creating all files, run the following and confirm every item exists:

```bash
echo "=== Checking DOSTO scaffold ==="
echo "Settings:" && ls .claude/settings.local.json
echo "Contracts:" && ls .claude/contracts/ | sort
echo "Agents:" && ls .claude/agents/ | sort
echo "Skills:" && ls .claude/skills/ | sort
echo "Scripts (OBN + LLDP):" && ls scripts/fix_obn*.py scripts/fix_bug1_regex.py scripts/lldp_topology_check.py
echo "Constitution:" && ls CLAUDE.md
echo "Logs dir:" && ls -d .claude/logs
echo "Directories ready for engineer-supplied content:"
echo "  docs/                          (engineer drops schema PDFs here)"
echo "  train-ip-allocation-commission (engineer drops IP-Port-Allocation PDFs here)"
echo "  reports/{customer,internal}    (deliverables — start empty)"
echo "  findings/                      (l2-health output — start empty)"
echo "=== Scaffold complete ==="
```

Expected:
- `.claude/contracts/` — 4 files: subagent-report.md, autonomy-boundary.md, approval-gates.md, confluence-sync.md
- `.claude/agents/` — 1 file: dosto-train-worker.md (Sonnet 4.6). (dosto-orchestrator.md retired 2026-05-11 per audit F5 — orchestration logic moved into dosto-orchestrate skill body, executed inline in the engineer's top-level session.)
- `.claude/skills/` — 14 directories, each with a SKILL.md
- `scripts/` — fix_obn.py, fix_obn_bug8.py, fix_obn_bugs67.py, fix_bug1_regex.py, lldp_topology_check.py (more, including the regenerator itself, are also present)
- `CLAUDE.md` at project root

**Sanity grep checks:**

```bash
# Every skill SKILL.md must have name + description frontmatter
for f in .claude/skills/*/SKILL.md; do
  grep -q "^name:" "$f" || echo "MISSING name in $f"
  grep -q "^description:" "$f" || echo "MISSING description in $f"
done

# Both agent definitions must declare a model
grep -l "^model:" .claude/agents/*.md  # expect 2

# Cross-references in CLAUDE.md must resolve to real files
grep -oE '\\.claude/[a-z/_-]+\\.md' CLAUDE.md | sort -u | while read f; do
  [ -f "$f" ] || echo "BROKEN REFERENCE in CLAUDE.md: $f"
done

# Confluence page ID hard-coded in confluence-sync skill matches the contract
grep -h "5410684933" .claude/contracts/confluence-sync.md .claude/skills/dosto-confluence-sync/SKILL.md | wc -l  # expect ≥ 2
```"""
    return step_block(step_num, "Verification checklist", body)


def emit_first_run_step(step_num: int) -> str:
    """STEP for first-run instructions."""
    body = """The scaffold is complete. Before the first commissioning run, you need to add a few engineer-supplied artefacts that don't belong in the bootstrap:

### 1. SSH key (credential — never embedded)

Drop your OpenSSH-format private key for the CCU at the project root, named exactly `openssh`:

```bash
# If you have it as PuTTY .ppk, convert with PuTTYgen first (export OpenSSH, no passphrase)
ls openssh   # confirm it exists
chmod 600 openssh   # POSIX systems; Windows: ensure ACL restricts to your user
```

The skills reference this absolute path: `C:/Users/<You>/Documents/dosto-troubleshooting/openssh`. If you keep it elsewhere, search-and-replace the path in `.claude/settings.local.json` and any skill SKILL.md that hard-codes it.

### 2. Schema PDFs (engineer-supplied)

Drop the per-train IP-Port-Allocation PDFs under `train-ip-allocation-commission/<series>/<train#>/`. Each train has its own subfolder. The skills don't fail without these — they fall back to formula-derived values — but having them lets `dosto-extract-train-data` populate per-train reference files.

### 3. State docs (regenerated separately or copied from another workspace)

If you ran the bootstrap on a fresh machine, you'll need:

- `fleet-status.md` — copy from your previous workspace, or start fresh and let `dosto-orchestrate` populate as you commission trains
- `train-login-checklist.md` — the canonical 11-step procedure (small; reproducible from CLAUDE.md but worth keeping as a separate file engineers can scan quickly)
- `troubleshooting-runbook.md` — the operational runbook (LLDP cabling check, OBN bug catalogue, AP factory bypass)
- `cable-issues-register.md` — the fleet's open cabling faults
- `iperf3-troubleshooting.md` — the UDP-pacing-artefact diagnostic notes
- `handoff.md` — last-session state (gets stale fast; safe to start empty)

If you generated this bootstrap with `--include-state`, those files are embedded later in the same bootstrap. Otherwise, copy them from another workspace via `scp` / cloud drive / git clone.

### 4. MCP connectors (one-time setup)

The `dosto-confluence-sync` skill calls the Atlassian connector. Verify it's connected in your Claude Code settings — the tool name to look for is `mcp__b29e83b2-87a0-46a4-9f8c-e389232437ac__updateConfluencePage`. If absent, add the Atlassian MCP via Claude Code's connector UI before running an end-to-end commissioning day.

### 5. Smoke test

```
/dosto-orchestrate fzg=132 dry-run
```

This validates the whole stack (skill → orchestrator → subagent → commission-train → per-device skills) against Fzg 132 in `--dry-run` mode — no destructive ops. If the orchestrator spawns, the subagent reports stage 1 verdicts, and you can ack a fake gate, the scaffold is healthy.

### Daily workflow

```
/dosto-orchestrate fzg=130,132,148   # multi-train day
```

Or for single-train debug:

```
/dosto-commission-train --ccu-ip 10.179.10.1 --fzg 132 --train-number 4736-104 --consist 6-car
```

### Updating the bootstrap

When you change a skill, agent definition, or contract, regenerate the bootstrap so it stays canonical:

```bash
python scripts/regenerate_bootstrap.py
```

That writes `BOOTSTRAP_DOSTO_v1.md` reflecting the current tree. Pass `--include-state` to embed the daily-changing state docs too (produces a larger file ~10k lines)."""
    return step_block(step_num, "First-run instructions", body)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_bootstrap(include_state: bool) -> tuple[str, dict[str, int]]:
    """
    Walk the embed lists, build the bootstrap markdown. Returns (text, stats).
    Missing source files are skipped silently (a warning is added to stats).
    """
    stats = {
        "embedded": 0,
        "skipped_missing": 0,
        "total_chars": 0,
        "total_lines": 0,
    }

    parts: list[str] = []

    # Header
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts.append(
        f"""# DOSTO Bootstrap — Single-paste scaffold for the dosto-troubleshooting workspace

**Generated:** {timestamp} (by `scripts/regenerate_bootstrap.py`)
**Scope:** Self-contained bootstrap for the DOSTO commissioning workspace. Paste this entire file into a fresh Claude Code session in an empty directory; Claude reads each STEP and creates every file with the exact content given. No git, no MCP-clone, no remote dependency.

This file is **regenerated** from the live project tree — don't hand-edit. To update it:

```bash
python scripts/regenerate_bootstrap.py            # scaffold only (default)
python scripts/regenerate_bootstrap.py --include-state   # scaffold + fleet-status, handoff, runbooks
```

**What's in the bootstrap:**
- 4 contract docs in `.claude/contracts/`
- 1 agent definition in `.claude/agents/` (dosto-train-worker only; dosto-orchestrator retired per F5)
- 14 skills in `.claude/skills/` (the per-device, orchestration, and reporting skills)
- `CLAUDE.md` (project constitution + orchestration architecture)
- `.claude/settings.local.json` (permissions allowlist for common SSH patterns)
- 5 fix scripts in `scripts/` (the OBN bug-fix scripts and LLDP topology check)
- `scripts/regenerate_bootstrap.py` (this regenerator itself — self-replicating)
- Verification checklist + first-run instructions

**What's NOT in the bootstrap (you bring these separately):**
- The `openssh` SSH private key (credential)
- Schema PDFs in `docs/` and `train-ip-allocation-commission/`
- Project state docs (`fleet-status.md`, `handoff.md`, etc.) unless you passed `--include-state`
- MCP connector setup (configure in Claude Code's UI; the Atlassian connector is required for `dosto-confluence-sync`)
- `node_modules/`, `findings/`, `reports/` content (start empty; populated as you commission trains)

You are setting up a complete DOSTO commissioning workspace for this project. Your job is to scaffold every file described below — exactly as specified. Do not summarise, do not skip files, do not ask questions. Work through each STEP in order, creating every file with the exact content given.

When you are done, run the verification checklist at the bottom and confirm every file exists.

---
"""
    )

    step_num = 1

    # STEP 1 — directory structure
    parts.append(emit_directory_step(step_num))
    step_num += 1

    # STEP 2 — settings
    parts.append(emit_settings_step(step_num))
    step_num += 1

    # STEPs 3..N — embedded files
    files_to_embed = list(EMBEDDED_FILES_SCAFFOLD)
    if include_state:
        files_to_embed.extend(EMBEDDED_FILES_STATE)

    for rel_path, lang in files_to_embed:
        if rel_path == ".claude/settings.local.json":
            # Already handled by emit_settings_step
            continue
        block = emit_file_step(step_num, rel_path, lang)
        if block is None:
            stats["skipped_missing"] += 1
            print(f"  ⚠ skipped (file missing): {rel_path}", file=sys.stderr)
            continue
        parts.append(block)
        stats["embedded"] += 1
        step_num += 1

    # STEP N — verification
    parts.append(emit_verification_step(step_num))
    step_num += 1

    # STEP N+1 — first-run
    parts.append(emit_first_run_step(step_num))

    # Footer
    parts.append(
        f"\n*End of bootstrap — generated {timestamp} from {stats['embedded']} files.*\n"
    )

    text = "\n".join(parts)
    stats["total_chars"] = len(text)
    stats["total_lines"] = text.count("\n") + 1
    return text, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--output",
        default="BOOTSTRAP_DOSTO_v1.md",
        help="Output path (relative to project root). Default: BOOTSTRAP_DOSTO_v1.md",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry run — generate but don't write; report sizes.",
    )
    parser.add_argument(
        "--include-state",
        action="store_true",
        help="Embed state docs (fleet-status.md, handoff.md, runbooks). Larger output.",
    )
    args = parser.parse_args()

    print("Regenerating DOSTO bootstrap...", file=sys.stderr)
    text, stats = build_bootstrap(include_state=args.include_state)

    print(
        f"  files embedded:   {stats['embedded']}\n"
        f"  files skipped:    {stats['skipped_missing']} (source missing)\n"
        f"  total lines:      {stats['total_lines']:,}\n"
        f"  total chars:      {stats['total_chars']:,}\n"
        f"  est. tokens:      ~{stats['total_chars'] // 4:,}",
        file=sys.stderr,
    )

    if args.check:
        print("(--check mode — not writing)", file=sys.stderr)
        return 0

    out_path = PROJECT_ROOT / args.output
    out_path.write_text(text, encoding="utf-8")
    print(f"  written:          {out_path.relative_to(PROJECT_ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
