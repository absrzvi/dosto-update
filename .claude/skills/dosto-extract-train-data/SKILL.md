---
name: dosto-extract-train-data
description: Extract per-train allocation data (Fzg ID, switches, APs with switch+port mapping, inter-coach trunks, Stadler-facing trunks, vlan7 IPs) from an IP-Port-Allocation PDF into a structured markdown file under train-ip-allocation-commission/extracted/. Run this once per train PDF — output is then the source of truth for downstream skills (dosto-device-discovery, dosto-cabling-check, etc.) which read the .md and never the PDF. Use when commissioning a new train, when a Stadler PDF is updated, or when batch-populating extracted files for the fleet. Engineer-in-the-loop — the LLM extracts, the engineer eyeballs the output against the PDF before committing.
---

# DOSTO Train PDF Extraction

Extract structured allocation data from an IP-Port-Allocation PDF into a markdown file readable by other skills. **Run once per train**, eyeball the output, commit. Downstream skills read the `.extracted.md` file, never the PDF.

## When to use

- **Bootstrapping the fleet** — first-time extraction for all trains we'll commission
- **New train added** — PDF arrives from Stadler, run this skill once to make it agent-readable
- **Stadler updates a PDF** — extracted file's `pdf_sha256` no longer matches; re-extract

## Why this skill exists

PDF parsing at runtime is fragile (format varies, columns drift, `pdftotext -layout` output is non-deterministic). Doing it once with engineer review, then having agents read the resulting markdown, gives:

- Deterministic agent behaviour (markdown is stable)
- Easy spot-check during extraction (engineer reviews against the visual PDF)
- Versionable, diff-able state when corrections are made
- A single change-detection point (`pdf_sha256`) instead of every skill having to handle PDF format errors

## Inputs

- `<train#>` — e.g. `4736-105` or `4734-120`
- (implied) The PDF at `train-ip-allocation-commission/<series>-xxx/<train#>/<train#>_IP[_-]Port[_-]Allocation.pdf` (note: filename has both `_` and `-` variants across the fleet — check both)

## Output

A markdown file at `train-ip-allocation-commission/extracted/<train#>.md` (flat directory, per-train spec). One file per train. Format defined below.

## Output format (CONTRACT — downstream skills depend on this shape)

```markdown
---
train_number: 4736-105
fzg_id: 133
consist: 6-car
schema: nv6
extracted_from: 4736-105_IP_Port_Allocation.pdf
extracted_at: 2026-05-09
extracted_by: dosto-extract-train-data v1
pdf_sha256: <hex>
---

# 4736-105 / Fzg 133 — Extracted Allocation

## Switches expected (18 total)

| Coach | Pos | Hostname | Notes |
|---|---|---|---|
| 1 | A1 | nv6-A1-v8-133 | |
| 1 | A2 | nv6-A2-v8-133 | |
| 1 | A3 | nv6-A3-v8-133 | |
| 2 | C1 | nv6-C1-v8-133 | |
... (18 rows for 6-car, 12 for 4-car)

## APs expected (24 total — 4 per coach)

| Coach | Slot | Connects to switch | Switch port | Config | Notes |
|---|---|---|---|---|---|
| 1 | AP1 | A2 | e0-3 | AP1-v1 | |
| 1 | AP2 | A2 | e0-0 | AP2-v1 | |
| 1 | AP3 | A3 | e2-5 | AP3-v1 | |
| 1 | AP4 | A3 | e0-3 | AP4-v1 | |
| 4 | AP1 | E2 | e0-3 | AP1m-v1 | "m-" middle-coach config |
... (24 rows for 6-car, 16 for 4-car)

## Inter-coach trunks (LLDP topology)

| Switch | Port | Should connect to | Notes |
|---|---|---|---|
| A1 | e0-0 | C1 | Inter-coach trunk |
| A1 | e0-1 | (front coupler) | DOWN when train solo, expected |
| A2 | e2-3 | A3 | Intra-coach |
| A2 | e2-4 | C3 | Inter-coach trunk |
... 

## Critical Stadler-facing trunks

| Switch | Port | Carries | VLANs |
|---|---|---|---|
| A3 | e1-4 | Stadler firewall | 1, 2, 3, 5, 6, 7, 8, 9, 12 |
| D1 | e0-2 | OBS D1 | 7, 200, 202, ... |
| D1 | e0-3 | RDC D1 | 200, 202 |
| D3 | e0-2 | OBS D3 | 7, 200, 202, ... |
| D3 | e0-3 | RDC D3 | 200, 202 |
| B1 | e1-11 | ZFR primary | 2 |
| B3 | e1-11 | ZFR standby | 2 |

## VLAN 7 (FIS) addressing

| Endpoint | IP |
|---|---|
| CCU vlan7 | 172.19.194.130/17 |
| Stadler firewall | 172.19.194.1 |
| Subnet | 172.19.128.0/17 |
```

### Required sections

A valid extracted file has, **exactly**, these top-level headings (in order):

1. (frontmatter)
2. `# <train#> / Fzg <fzg> — Extracted Allocation`
3. `## Switches expected (<N> total)`
4. `## APs expected (<N> total — 4 per coach)`
5. `## Inter-coach trunks (LLDP topology)`
6. `## Critical Stadler-facing trunks`
7. `## VLAN 7 (FIS) addressing`

If any are missing or in a different order, downstream skills will reject the file. The contract is strict to keep parsing trivial.

### Required frontmatter fields

| Key | Value | Required |
|---|---|---|
| `train_number` | e.g. `4736-105` | yes |
| `fzg_id` | integer | yes |
| `consist` | `4-car` or `6-car` | yes |
| `schema` | `nv4` or `nv6` | yes |
| `extracted_from` | source PDF filename | yes |
| `extracted_at` | YYYY-MM-DD | yes |
| `extracted_by` | tool name + version | yes |
| `pdf_sha256` | SHA256 of source PDF | yes |

### Naming conventions

- **Switch position** (`A1`, `A2`, `A3`, `B1`, ...): from the schema, top-of-coach naming. Use the canonical letters per consist:
  - 6-car: `A`, `C`, `D`, `E`, `F`, `B` — coaches numbered 1, 2, 3, 4, 5, 6 in this order
  - 4-car: `A`, `G`, `E`, `B` — coaches numbered 1, 2, 3, 4
  - **Coach 1 is always the leading coach** (A position) regardless of consist size
- **AP slot** (`AP1`, `AP2`, `AP3`, `AP4`): **always 4 per coach**. Slot ordering matches the schema's "Access point A1/A2/A3/A4" labels in the relevant coach.
- **AP config name** (`AP1-v1`, `AP1m-v1`): include the `m-` prefix when present in the schema. The `m-` indicates middle-coach configuration and is meaningful — different config than non-`m-` APs. Capture it.

## Procedure (how to extract)

### Step 1: Read the PDF

Use `pdftotext -layout` via Bash to get the raw text, or use the Read tool directly on the PDF (the harness can read PDFs natively).

```bash
pdftotext -layout "train-ip-allocation-commission/<series>-xxx/<train#>/<train#>_IP[_-]Port[_-]Allocation.pdf" /tmp/<train#>.txt
```

For 6-car PDFs the format is roughly: 6 pages, one per coach, in order A → C → D → E → F → B. Each page has 3 switches' port allocations. AP rows typically appear under `e0-3` and `e0-0` access ports of each switch with VLAN list `100, 10, 20, 30, 31, 131, 150` and label `Access point AN`.

For 4-car PDFs: 4 pages, one per coach, A → G → E → B.

### Step 2: Identify the header

First page contains:

```
DOSTO NEU                                          IPv4-Schema
                                                Fgz. Nr: 4736 - 105
Nahverkehr- 6 Teiler

Fahrzeugnummer:        4736-105        Fzg. ID: 133        Wagen:        A - 100
```

Extract:
- `train_number`: `4736-105` (from "Fahrzeugnummer:" or "Fgz. Nr:" — they should match)
- `fzg_id`: `133` (from "Fzg. ID:")
- `consist`: `6-car` if "6 Teiler" / "Nahverkehr- 6 Teiler", `4-car` if "4 Teiler"
- `schema`: `nv6` for 6-car, `nv4` for 4-car

If header values disagree (Fahrzeugnummer ≠ Fgz. Nr suffix), **stop and flag** — the PDF is internally inconsistent and likely a transcription error. Do not silently pick one.

### Step 3: Build the switches table

Switches are deterministic from the consist size:

- **6-car (nv6):** 18 switches — coaches 1–6, 3 switches per coach, positions A1/A2/A3 in coach 1, C1/C2/C3 in coach 2, D in 3, E in 4, F in 5, B in 6.
- **4-car (nv4):** 12 switches — coaches 1–4, 3 switches per coach, positions A1/A2/A3 in coach 1, G in 2, E in 3, B in 4.

Hostname format: `<schema>-<pos>-v8-<fzg_id_padded_to_3>`. E.g. Fzg 133 6-car coach 5 position 2 → `nv6-F2-v8-133`.

Generate all rows from the consist + Fzg ID. **No PDF parsing needed for this section** — it's pure formula.

### Step 4: Extract APs (the one tricky parse)

This is where engineer review matters most. APs appear in the per-switch port tables. For each switch in each coach, look for rows with:

- Label like `Access point A1`, `Access point A2`, etc. (matches the AP slot number)
- VLAN field containing `100, 10, 20, 30, 31, 131, 150` (or similar — vlan100 + passenger VLANs)
- Port type `Trunk`

The switch hosting that AP port and the port number is what we need.

**Common pattern (6-car):**

| Coach | AP slot | Hosting switch + port |
|---|---|---|
| 1 (A) | AP1 | A1 e0-3 |
| 1 (A) | AP2 | A2 e0-0 |
| 1 (A) | AP3 | A3 e2-5 |
| 1 (A) | AP4 | A3 e0-3 |
| 2 (C) | AP1 | C1 e0-3 |
| 2 (C) | AP2 | C2 e0-0 |
| 2 (C) | AP3 | C3 e2-5 |
| 2 (C) | AP4 | C3 e0-3 |
... and so on for D, E, F, B coaches.

The pattern *should* be coach-symmetric (every coach has the same 4 AP slots in the same switch+port positions), but **this is the assumption to verify per train**. If the PDF shows a different layout for a given coach, capture what's actually there.

For the AP **config name**:
- Coaches 1–3 (A, C, D) typically use `AP1-v1`, `AP2-v1`, `AP3-v1`, `AP4-v1`
- Coaches 4–6 (E, F, B) typically use `AP1m-v1`, `AP2m-v1`, `AP3m-v1`, `AP4m-v1` (the `m-` middle-coach variant)
- For 4-car: coaches 1, 4 (A, B) → no `m-`; coaches 2, 3 (G, E) → `m-`

**This is also a per-train verification point.** The `m-` boundary may differ.

### Step 5: Extract inter-coach trunks

For each switch, look at its `e0-0` and `e0-1` ports. The "Usage" column lists the neighbour switch (e.g. `FIS Switch C1` for an A1.e0-0 entry).

Pattern:
- Most switches: `e0-0` and `e0-1` connect to other VDS switches
- End-of-train switches (A1, A3 of coach 1; B1, B3 of last coach): one of `e0-0`/`e0-1` is the front coupler (will be DOWN when train is solo) — Usage `Frontkupplung` in German.

Extract the `(switch, port, neighbour, "Inter-coach" or "Intra-coach" or "front coupler")` tuple for every e0-0/e0-1 of every switch.

### Step 6: Extract Stadler-facing trunks

Six fixed positions (per the playbook):

| Switch | Port | Usage |
|---|---|---|
| A3 | e1-4 | Stadler firewall trunk (multi-VLAN) |
| D1 | e0-2 | OBS D1 |
| D1 | e0-3 | RDC D1 |
| D3 | e0-2 | OBS D3 |
| D3 | e0-3 | RDC D3 |
| B1 | e1-11 | ZFR primary |
| B3 | e1-11 | ZFR standby |

Find each in the PDF, capture the VLAN list ("VLAN ID" column).

### Step 7: Compute vlan7 IPs

These are deterministic from Fzg ID using the formula in [CLAUDE.md](../../../CLAUDE.md):

```
octet 3 = 128 + (Fzg // 2)
octet 4 = (128 if Fzg odd else 0) + 2     # CCU is device 2
firewall_octet4 = (128 if Fzg odd else 0) + 1  # FW is device 1
```

For Fzg 133: CCU = `172.19.194.130`, FW = `172.19.194.129`.

Wait — the firewall is `.129` for odd Fzg or `.1` for even? Let me re-check:
- Even Fzg → octet 4 host base = 0, so device 1 = `.1`, device 2 = `.2`
- Odd Fzg → octet 4 host base = 128, so device 1 = `.129`, device 2 = `.130`

So Fzg 133 (odd): CCU = `.130`, FW = `.129`. Both sit on the `/17` covering `172.19.128.0` – `172.19.255.255`.

**Validate** by comparing the FW IP from the PDF (look for `172 19 ... 129 1` rows in the Firewall section) against the formula. If they disagree, flag — the formula or the PDF is wrong, and silently picking one is dangerous.

### Step 8: Compute pdf_sha256

```bash
sha256sum "train-ip-allocation-commission/<series>-xxx/<train#>/<train#>_IP[_-]Port[_-]Allocation.pdf" | cut -d' ' -f1
```

### Step 9: Write the output

Path: `train-ip-allocation-commission/extracted/<train#>.md`. Overwrite if exists (re-extraction is the use case for that — but warn the engineer first if `pdf_sha256` matches the existing file's, since the re-extraction is then a no-op).

### Step 10: Print a summary for engineer review

```
─── Extraction summary: 4736-105 ───
Fzg ID: 133 (from PDF header)
Consist: 6-car (nv6)
Switches: 18 generated from formula (no PDF parse needed)
APs: 24 extracted (eyeball check vs. PDF needed)
Inter-coach trunks: 36 e0-0/e0-1 entries
Stadler trunks: 7 confirmed (A3 e1-4, D1 e0-2/e0-3, D3 e0-2/e0-3, B1/B3 e1-11)
vlan7: 172.19.194.130/17 (CCU), 172.19.194.129 (FW) — formula matches PDF? <yes/no>
pdf_sha256: <hex prefix>
Output: train-ip-allocation-commission/extracted/4736-105.md

⚠ Engineer: please open the output file and verify the AP table against the PDF
  before committing. Pay attention to: m- prefix on coaches 4-6, AP slot positions
  per coach, and any per-coach asymmetry.
```

## Edge cases and quirks

- **Filename inconsistency.** Some folders have `<train#>_IP_Port_Allocation.pdf` (underscore variant), others `<train#>_IP-Port-Allocation.pdf` (hyphen variant). Try both in glob.
- **Empty / unreadable PDF.** If `pdftotext` fails or returns < 100 lines, the PDF is corrupt or password-protected. Stop and surface to engineer.
- **Fzg ID mismatch with hostname.** On DOSTO NEU, `train_id` in OBN templates may NOT match the IP-encoded Fzg (mar5 workaround). The extracted file uses **PDF Fzg ID** as truth, not OBN `train_id`. The vlan7 IP follows from PDF Fzg ID.
- **AP "Reserve" or "FU" slots.** Some schemas show "AP Reserve D2" or "AP FU" — these are *not* in the 24-AP count. Skip them; the 4-per-coach rule is for the canonical AP1/AP2/AP3/AP4 only.
- **Front coupler trunks.** A1.e0-2, A3.e0-2 (and B1/B3.e0-2 on 6-car) are coupler-side trunks. On a solo consist they're admin-enabled but link DOWN — expected, not a fault. Capture in inter-coach table with note "front coupler".

## What this skill does NOT do

- ❌ Parse end-device IPs (cameras, displays, audio amps, etc.) — they're not needed by any commissioning skill, only the L2 health check, which has its own per-VLAN data already
- ❌ Extract physical wiring lengths or PoE budgets from the PDF — present in the PDF, not used by any skill
- ❌ Re-extract on every run — `pdf_sha256` check should skip extraction if file is current
- ❌ Auto-commit the file — engineer reviews and commits manually

## Failure handling

If extraction can't complete (PDF parse fails, header mismatch, AP count != 24/16, mandatory section missing):

1. Do not write a partial output file
2. Print a clear error stating which step failed
3. Surface to the engineer with the raw `pdftotext` output for the affected page so they can manually verify

## Reusing the extracted file

Downstream skills do this:

```python
import yaml, hashlib

def load_train_data(train_number, project_root):
    md_path = f"{project_root}/train-ip-allocation-commission/extracted/{train_number}.md"
    with open(md_path) as f:
        content = f.read()
    # split frontmatter
    frontmatter = yaml.safe_load(content.split("---")[1])
    # verify pdf hash matches the source
    pdf_path = locate_source_pdf(train_number, project_root)
    actual_hash = hashlib.sha256(open(pdf_path, "rb").read()).hexdigest()
    if frontmatter["pdf_sha256"] != actual_hash:
        raise ValueError(f"Stale extraction: {md_path} based on different PDF. Re-run dosto-extract-train-data {train_number}.")
    return content
```

The hash check is the safety net — it's how we catch the "PDF was updated, extracted file is stale" failure mode.

## Reference

- Source PDFs: `train-ip-allocation-commission/<series>-xxx/<train#>/`
- Extracted output: `train-ip-allocation-commission/extracted/<train#>.md` (flat, all trains together)
- Related skills that consume the extracted file:
  - `dosto-device-discovery` (count + missing-device localisation)
  - `dosto-cabling-check` (LLDP topology vs. expected — when built)
  - `dosto-l2-health` (Stadler-facing trunks list — could be retrofit to read this)
- Related contracts:
  - [.claude/contracts/subagent-report.md](../../contracts/subagent-report.md) — JSON shapes that consume extracted data
