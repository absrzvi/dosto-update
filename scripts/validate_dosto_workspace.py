#!/usr/bin/env python3
"""
Validate cross-references across the DOSTO workspace's contracts, skills,
and agent definitions. Catches drift between canonical names that are
referenced by string match across files.

Usage:
    python scripts/validate_dosto_workspace.py        # human-readable report
    python scripts/validate_dosto_workspace.py --json # machine-readable

Exits 0 if all checks pass, 1 if any check fails.

What it checks:
  C1  Stage IDs in subagent-report.md ↔ dosto-commission-train SKILL.md
  C2  Gate names in autonomy-boundary.md ↔ approval-gates.md ↔ agents
  C3  fields: allowlist in subagent-report.md ↔ orchestrator G2 table
  C4  Every /dosto-<name> reference resolves to a real skill directory
  C5  Every .claude/agents/<name>.md reference resolves to a real file
  C6  Confluence page ID 5410684933 hard-coded identically in 2 places
  C7  schema_version: "1" appears in every skill SKILL.md that has --json output
  C8  Agent definitions declare model: and tools: in frontmatter
  C9  Skill SKILL.md frontmatter has name: and description:

These are pure grep/parse checks — no semantic validation, no CCU connectivity,
no file content correctness. Run pre-flight from `dosto-orchestrate` skill +
manually after any contract / agent / skill edit.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CANONICAL_STAGE_IDS = [
    # Stage list v2 (2026-05-09): config-first device-push ordering, two new
    # stages (push_switch_firmware split from push_ap_firmware; push_ap_config
    # added as final refresh), one renamed (obn_discover_post_config →
    # obn_discover_post_sw_config), ap_factory_bypass moved from after
    # obn_discover_initial to after push_switch_firmware. See subagent-report.md
    # § "Commissioning stage list" → "Stage list version: v2" for migration.
    "initial_diagnostics",
    "await_device_count_mismatch",
    "apply_obn_patches",
    "apply_train_id_fix",
    "apply_vlan7_fix",
    "await_promote_snapshot",
    "promote_snapshot",
    "await_safe_reboot",
    "reboot_and_wait",
    "post_reboot_verify",
    "obn_discover_initial",
    "await_obn_update_c",
    "push_switch_config",
    "obn_discover_post_sw_config",
    "await_obn_update_f",
    "push_switch_firmware",
    "ap_factory_bypass",
    "push_ap_firmware",
    "push_ap_config",
    "final_l2_health_check",
    "generate_report",
    "done",
]

CANONICAL_GATE_NAMES = [
    "promote_snapshot",
    "safe_reboot",
    "obn_update_c",
    "obn_update_f",
    "device_count_mismatch",
]

CANONICAL_FIELDS = [
    "obn_patches",
    "switches_v8",
    "aps",
    "vlan7_ok",
    "stadler_cabling",
    "fw_reach",
    "health_check_done",
    "customer_report",
]

CONFLUENCE_PAGE_ID = "5410684933"


class CheckResult(NamedTuple):
    check_id: str
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return self._asdict()


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def find_files(pattern: str) -> list[Path]:
    return sorted(PROJECT_ROOT.glob(pattern))


def check_stage_ids() -> CheckResult:
    """C1: every canonical stage ID must appear in commission-train SKILL.md."""
    commission = read(".claude/skills/dosto-commission-train/SKILL.md")
    missing_in_skill = [
        stage for stage in CANONICAL_STAGE_IDS
        if stage != "done" and stage not in commission
    ]
    if missing_in_skill:
        return CheckResult(
            "C1",
            "Stage IDs (commission-train vs contract)",
            False,
            f"commission-train SKILL.md does not mention these canonical stage IDs: {sorted(missing_in_skill)}",
        )
    return CheckResult(
        "C1",
        "Stage IDs (commission-train vs contract)",
        True,
        f"All {len(CANONICAL_STAGE_IDS) - 1} canonical stage IDs (excluding implicit 'done') referenced.",
    )


def check_gate_names() -> CheckResult:
    """C2: gate names appear in autonomy-boundary, approval-gates, both agents."""
    files = [
        ".claude/contracts/autonomy-boundary.md",
        ".claude/contracts/approval-gates.md",
        ".claude/agents/dosto-train-worker.md",
        ".claude/skills/dosto-orchestrate/SKILL.md",  # was: agents/dosto-orchestrator.md — retired 2026-05-11 per audit F5
    ]
    missing = []
    for f in files:
        content = read(f)
        for gate in CANONICAL_GATE_NAMES:
            if gate not in content:
                missing.append(f"{f}: missing gate '{gate}'")
    if missing:
        return CheckResult(
            "C2",
            "Gate names (cross-file consistency)",
            False,
            "; ".join(missing),
        )
    return CheckResult(
        "C2",
        "Gate names (cross-file consistency)",
        True,
        f"All {len(CANONICAL_GATE_NAMES)} gate names present in 4 canonical files.",
    )


def check_fields_allowlist() -> CheckResult:
    """C3: orchestrator's fields allowlist must match the contract's fields list.
    Post-F5 (2026-05-11): orchestration lives in the dosto-orchestrate skill, not an agent file.
    The "Surgical-Changes allowlist" section that was in dosto-orchestrator.md is now in
    dosto-orchestrate/SKILL.md under "Fleet-status writer" → "Surgical-Changes allowlist".
    """
    contract = read(".claude/contracts/subagent-report.md")
    orch = read(".claude/skills/dosto-orchestrate/SKILL.md")
    # Contract uses `| `field` | type | example | column |` shape — match `| `field` |` substring.
    missing_in_contract = [f for f in CANONICAL_FIELDS if f"| `{f}` |" not in contract]
    missing_in_orch = [f for f in CANONICAL_FIELDS if f"| `{f}` |" not in orch]
    issues = []
    if missing_in_contract:
        issues.append(
            f"contract subagent-report.md missing fields: {sorted(missing_in_contract)}"
        )
    if missing_in_orch:
        issues.append(f"orchestrator.md fields allowlist missing: {missing_in_orch}")
    if issues:
        return CheckResult("C3", "Fields allowlist consistency", False, "; ".join(issues))
    return CheckResult(
        "C3",
        "Fields allowlist consistency",
        True,
        f"All {len(CANONICAL_FIELDS)} fields present in contract + orchestrator allowlist.",
    )


def check_skill_references() -> CheckResult:
    """C4: every /dosto-<name> referenced anywhere must resolve to a skill dir.

    Allows aspirational references (skills documented as 'when built' or 'not yet
    implemented') via the EXPECTED_PENDING_SKILLS allowlist below. These are
    placeholders for future work; flag them when removed from the allowlist but
    don't fail validation.
    """
    EXPECTED_PENDING_SKILLS = {
        # Referenced in topology files + handoff as "when built". Future scope.
        "dosto-cabling-check",
    }
    EXCLUDE_NAMES = {
        "dosto-troubleshooting",  # workspace directory name, not a skill
        "dosto-train-worker",  # agent definition, not a skill
        # dosto-orchestrator retired 2026-05-11 per F5 — was an agent, now is the dosto-orchestrate skill
    }
    skill_dirs = {
        p.name for p in (PROJECT_ROOT / ".claude/skills").iterdir() if p.is_dir()
    }
    files_to_scan = (
        list(find_files(".claude/contracts/*.md"))
        + list(find_files(".claude/agents/*.md"))
        + list(find_files(".claude/skills/*/SKILL.md"))
        + [PROJECT_ROOT / "CLAUDE.md"]
    )
    referenced: set[str] = set()
    for f in files_to_scan:
        if not f.exists():
            continue
        content = f.read_text(encoding="utf-8")
        # Skill references: /dosto-foo or `dosto-foo` or [dosto-foo]. The name
        # must consist of dosto- followed by at least one segment, and end with
        # a letter/digit (not a dash) — so we don't match truncated brace
        # expansions like `dosto-sw-{config,firmware}-update`.
        for match in re.finditer(r"\bdosto(?:-[a-z][a-z0-9]*)+\b", content):
            name = match.group(0)
            if name in EXCLUDE_NAMES:
                continue
            referenced.add(name)
    missing = referenced - skill_dirs - EXPECTED_PENDING_SKILLS
    if missing:
        return CheckResult(
            "C4",
            "Skill references resolve",
            False,
            f"References to non-existent skills: {sorted(missing)}",
        )
    pending = referenced & EXPECTED_PENDING_SKILLS
    pending_note = f" (plus {len(pending)} pending: {sorted(pending)})" if pending else ""
    return CheckResult(
        "C4",
        "Skill references resolve",
        True,
        f"All {len(referenced - EXPECTED_PENDING_SKILLS)} referenced skills exist as directories{pending_note}.",
    )


def check_agent_references() -> CheckResult:
    """C5: every .claude/agents/X.md mention must point to a real file."""
    agent_dir = PROJECT_ROOT / ".claude/agents"
    existing = {p.name for p in agent_dir.glob("*.md")}
    files_to_scan = (
        list(find_files(".claude/contracts/*.md"))
        + list(find_files(".claude/agents/*.md"))
        + list(find_files(".claude/skills/*/SKILL.md"))
        + [PROJECT_ROOT / "CLAUDE.md"]
    )
    referenced: set[str] = set()
    for f in files_to_scan:
        if not f.exists():
            continue
        content = f.read_text(encoding="utf-8")
        for match in re.finditer(r"\.claude/agents/([a-z-]+\.md)", content):
            referenced.add(match.group(1))
    missing = referenced - existing
    if missing:
        return CheckResult(
            "C5",
            "Agent references resolve",
            False,
            f"References to non-existent agent files: {sorted(missing)}",
        )
    return CheckResult(
        "C5",
        "Agent references resolve",
        True,
        f"All {len(referenced)} referenced agent files exist.",
    )


def check_confluence_page_id() -> CheckResult:
    """C6: page ID 5410684933 in contract + sync skill."""
    contract = read(".claude/contracts/confluence-sync.md")
    skill = read(".claude/skills/dosto-confluence-sync/SKILL.md")
    if CONFLUENCE_PAGE_ID not in contract:
        return CheckResult(
            "C6",
            "Confluence page ID consistency",
            False,
            f"Page ID {CONFLUENCE_PAGE_ID} missing from confluence-sync contract.",
        )
    if CONFLUENCE_PAGE_ID not in skill:
        return CheckResult(
            "C6",
            "Confluence page ID consistency",
            False,
            f"Page ID {CONFLUENCE_PAGE_ID} missing from dosto-confluence-sync skill.",
        )
    return CheckResult(
        "C6",
        "Confluence page ID consistency",
        True,
        f"Page ID {CONFLUENCE_PAGE_ID} present in both files.",
    )


def check_schema_version() -> CheckResult:
    """C7: every skill_outputs JSON example must declare schema_version: "1".

    A "skill_outputs example" is a JSON block that contains the canonical
    `"skill":` and `"verdict":` keys — these are the markers from the
    subagent-report.md `skill_outputs[].raw` shape. Other JSON blocks (input
    shapes, partial fragments, configuration examples) are skipped — they don't
    need to declare a schema_version because they're not OUR output schema.
    """
    skill_files = list(find_files(".claude/skills/*/SKILL.md"))
    issues = []
    examples_checked = 0
    for f in skill_files:
        content = f.read_text(encoding="utf-8")
        json_blocks = re.findall(r"```json\s*\n(.*?)\n```", content, re.DOTALL)
        # Only check blocks that look like skill-output specs
        output_blocks = [
            b for b in json_blocks
            if '"skill":' in b and '"verdict":' in b
        ]
        if not output_blocks:
            continue
        examples_checked += len(output_blocks)
        # Each output block must declare schema_version: "1"
        for i, b in enumerate(output_blocks):
            if '"schema_version": "1"' not in b and '"schema_version":"1"' not in b:
                issues.append(
                    f"{f.parent.name}: skill-output example #{i+1} missing schema_version: \"1\""
                )
    if issues:
        return CheckResult(
            "C7", 'schema_version: "1" in skill-output examples', False, "; ".join(issues)
        )
    return CheckResult(
        "C7",
        'schema_version: "1" in skill-output examples',
        True,
        f"All {examples_checked} skill-output JSON examples declare schema_version \"1\".",
    )


def check_agent_frontmatter() -> CheckResult:
    """C8: every agent definition has frontmatter with name, description, model, tools."""
    agent_files = list(find_files(".claude/agents/*.md"))
    required = ["name:", "description:", "model:", "tools:"]
    issues = []
    for f in agent_files:
        content = f.read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            issues.append(f"{f.name}: no frontmatter")
            continue
        # Extract frontmatter (between first two --- lines)
        end = content.find("\n---\n", 4)
        if end == -1:
            issues.append(f"{f.name}: unterminated frontmatter")
            continue
        frontmatter = content[4:end]
        for req in required:
            if req not in frontmatter:
                issues.append(f"{f.name}: missing '{req}' in frontmatter")
    if issues:
        return CheckResult("C8", "Agent frontmatter completeness", False, "; ".join(issues))
    return CheckResult(
        "C8",
        "Agent frontmatter completeness",
        True,
        f"All {len(agent_files)} agents have name/description/model/tools.",
    )


def check_skill_frontmatter() -> CheckResult:
    """C9: every SKILL.md has frontmatter with name and description."""
    skill_files = list(find_files(".claude/skills/*/SKILL.md"))
    issues = []
    for f in skill_files:
        content = f.read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            issues.append(f"{f.parent.name}: no frontmatter")
            continue
        end = content.find("\n---\n", 4)
        if end == -1:
            issues.append(f"{f.parent.name}: unterminated frontmatter")
            continue
        frontmatter = content[4:end]
        if "name:" not in frontmatter:
            issues.append(f"{f.parent.name}: missing 'name:' in frontmatter")
        if "description:" not in frontmatter:
            issues.append(f"{f.parent.name}: missing 'description:' in frontmatter")
        # name should match the directory name
        m = re.search(r"^name:\s*(\S+)", frontmatter, re.MULTILINE)
        if m and m.group(1) != f.parent.name:
            issues.append(
                f"{f.parent.name}: name in frontmatter is '{m.group(1)}' — does not match dir"
            )
    if issues:
        return CheckResult("C9", "Skill frontmatter completeness", False, "; ".join(issues))
    return CheckResult(
        "C9",
        "Skill frontmatter completeness",
        True,
        f"All {len(skill_files)} skills have name/description; names match directories.",
    )


CHECKS = [
    check_stage_ids,
    check_gate_names,
    check_fields_allowlist,
    check_skill_references,
    check_agent_references,
    check_confluence_page_id,
    check_schema_version,
    check_agent_frontmatter,
    check_skill_frontmatter,
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()

    results = [check() for check in CHECKS]

    if args.json:
        out = {
            "schema_version": "1",
            "skill": "validate-dosto-workspace",
            "passed": all(r.passed for r in results),
            "checks": [r.to_dict() for r in results],
        }
        print(json.dumps(out, indent=2))
    else:
        # Plain ASCII for Windows console compatibility
        for r in results:
            mark = "PASS" if r.passed else "FAIL"
            print(f"[{mark}] {r.check_id}: {r.name}")
            print(f"      {r.detail}")
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        summary = "PASS" if passed == total else "FAIL"
        print(f"\n[{summary}] {passed}/{total} checks passed")

    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
