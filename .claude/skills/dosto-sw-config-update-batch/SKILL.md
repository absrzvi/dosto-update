---
name: dosto-sw-config-update-batch
description: Push DOSTO switch configs in OBN-driven parallel batches. Auto mode wraps `obn update c sw` for full-fleet leaf-first parallel push; manual mode takes --switches A,B,C and runs OBN's leaf-first batches scoped to those IPs. Default replacement for the single-switch config skill inside dosto-commission-train (escape hatch: --legacy-serial-sw-config). Estimated wall-clock: ~30-45 min for a 6-car DOSTO vs ~3 hours single-switch serial. Validated empirically on Fzg <TBD>. Pairs with dosto-tftp-helper-check, dosto-obn-patches, dosto-fzg-id-check, dosto-l2-health.
---

# DOSTO Switch Config Update — Batched

Stub. Full body lands in Task 11.
