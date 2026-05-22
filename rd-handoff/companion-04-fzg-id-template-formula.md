# Companion 4 — `/etc/obn/template/nv*-*.cfg` shipping with broken `{%- set train_id = 128 + train_id -%}` formula

**Repo:** OBN template repo (`nd-obn-template-dostoneu-nv6`, and the sibling `-nv4`)
**Not in:** `nd-obn` proper

## Summary

The switch config templates in `/etc/obn/template/nv6-*.cfg` (and the `-nv4` variants) ship with a top-line Jinja directive that computes the rendered `train_id` (used in switch hostnames, downstream-IP encodings, etc.) from another `train_id` variable plus an offset:

```jinja
{%- set train_id = 128 + train_id -%}
```

This is wrong for **every train**. The correct value is the hardcoded Fzg ID for that specific consist. The formula's "128 +" offset was apparently a legacy convention for some early 4736 trains but it's been bitten on every other series we've touched — most famously the 4736-105 (Fzg 133) cascade where the formula produced Fzg `261` and we cabled an entire health check to the wrong firewall IP before catching it.

Our skill `dosto-fzg-id-check` detects this and replaces line 1 of every nv6/nv4 template with the literal hardcoded Fzg from the engineer's input. That's the workaround. The actual fix is in the template repo.

## Reproducer

1. Fresh CCU on current image. `grep -h "^{%- set train_id" /etc/obn/template/nv6-*.cfg | sort -u`
2. Observe one of:
   - `{%- set train_id = 128 + train_id -%}` (the broken formula) — most CCUs
   - Multiple different `{%- set train_id = N -%}` lines (partial fix from a previous session) — some CCUs
   - A single correct hardcoded `{%- set train_id = <Fzg> -%}` — CCUs we've touched

## The actual fix

The template repo should not ship a formula. Each template should have a placeholder that the **Puppet env** renders to the Fzg ID for the specific train it's deploying to. That removes the per-CCU manual fix entirely.

Concrete shape:
- Template files contain `{%- set train_id = {{ fzg_id }} -%}` (Puppet template variable).
- Puppet env's per-train hiera (or whatever the per-train data source is) supplies `fzg_id` from the train number → Fzg mapping documented in [CLAUDE.md § Series → Fzg mapping shorthand](../CLAUDE.md).
- On deploy, the rendered templates have the hardcoded right Fzg, and OBN sees them as immutable (no formula to evaluate at OBN runtime).

The `nd-obn` runtime side does not need any change — it currently just reads the rendered `train_id` and uses it. The fix is entirely in the template + Puppet rendering layer.

## Test evidence

- Fzg 132 / 4736-104 (2026-05-09) — broken formula rendered `260`, fixed via chroot.
- Fzg 133 / 4736-105 (2026-05-04) — broken formula rendered `261`, caused the original cascade.
- Fzg 130 / 4736-102 (2026-05-12) — broken formula plus duplicate-position misimaged switches.
- Many more in `fleet-status.md` — search for `train_id template`.

See memory [`feedback_train_id_location.md`](../?) for the Fzg-ID-template-only rule and [`project_obn_update_target_catch22.md`](../?) for the cascade evidence.

## Marker

After fix, on a fresh CCU deploy, `grep -h "^{%- set train_id" /etc/obn/template/nv6-*.cfg | sort -u` should return exactly one line of the form `{%- set train_id = <Fzg> -%}` where `<Fzg>` is the correct hardcoded value for the train. Our skill checks this.

## Notes for R&D

This is the template-repo issue most likely to be "owned by R&D but assigned to nobody" because it sits between OBN and Puppet. Naming a single owner here would unblock the fix.

The nv4 templates (`nv4-*.cfg`) have their own variant of this — see memory [`feedback_nv4_form1_directive_required.md`](../?) — where nv4 ships as **Form-2** (no directive at all) and commissioning currently requires adding the directive as line 1 of each template. A coherent fix would unify Form-1 (nv6-style: rendered directive present) and Form-2 (nv4 current style: directive absent) so the Puppet rendering layer always emits the same shape.
