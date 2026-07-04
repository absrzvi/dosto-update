---
type: guide
title: Frontmatter cheatsheet
description: Copy-paste frontmatter blocks for each doc type.
tags: [meta, reference]
timestamp: <YYYY-MM-DDT00:00:00Z>
---

# Frontmatter cheatsheet

Only `type:` is required. Copy the block for the kind of doc you're writing.

## component-knowledge
```yaml
---
type: component-knowledge
title: <Device/Subsystem — aspect>
description: <one sentence>
component: <component-slug>
vendor: <vendor if relevant>
tags: [<component>, ...]
maturity: field-validated
timestamp: <ISO-8601>
---
```
Body sections: Overview · behaviour · `# Proven dead ends — do NOT repeat these` · `# EXAMPLE` · `# Related` · `# Citations`.

## topic
```yaml
---
type: topic
title: <cross-cutting subject>
description: <one sentence>
tags: [...]
maturity: field-validated
timestamp: <ISO-8601>
---
```

## evidence
```yaml
---
type: evidence
title: <what this proves>
description: <one sentence>
tags: [...]
maturity: field-validated
timestamp: <ISO-8601>
resource: /<path to raw artifact>
---
```
Body: `## What it proves` · `## How it was captured` · `## Evidence` (link raw) · `## So what` · `# Related`.

## tool
```yaml
---
type: tool
title: <tool — what it does>
description: <one sentence>
tags: [...]
maturity: field-validated
timestamp: <ISO-8601>
resource: /<path to script>
---
```
Body: `## What it does` · `## When to reach for it` · `## Usage` · `## Output` · `## Notes` · `# Related`.

## index (directory listing)
```yaml
---
type: index
title: <Category> — index
description: <one sentence>
timestamp: <ISO-8601>
---
```
Body: grouped bullets — `* [Title](file.md) - <description>`.
