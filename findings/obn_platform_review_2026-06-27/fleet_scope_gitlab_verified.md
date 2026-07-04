# Fleet/customer scope — verified live against GitLab (VPN, 2026-06-27)

Source: GitLab API (`git-nc.nomadrail.com`, v19.0.2), group `onboard` (id 20), authenticated.
Full inventory saved at `onboard_group_inventory.json`.

## Headline numbers (authoritative)
- **290 projects** in the `onboard/` group.
- **65 OBN template repos** (`nd-obn-template-*` / `obn-template-*` / `eurostar-backbone-template-generator`).
- **~49 distinct customer fleets** represented among the templates.
- The OBN **app** ships **14 report classes** (specialized topology handlers) — these are *dispatch
  handlers*, NOT the fleet count.

## How the 14 classes map to ~49 fleets
Customers with bespoke topology get a dedicated report class (DOSTO, TGV/TGV2020, VIA, DANI, DSB, Luna,
Queensland, ACE, CCJPA-WD1/WD2, Daisy, DHCP). Every **other** customer reuses **`GenericReport`** plus its
own template repo that defines the actual train layout. Confirmed live:
- `nd-obn-template-nightjet` → `obn::report_module: "GenericReport"` (explicit).
- `renfe`, `cfl`, `talgo`, `tgvm`, `ns-icng-8c` → no `report_module` key → default/Generic path.

So a single shared class backs many fleets; the **real layout diversity lives in the 65 template repos**,
not the 14 classes.

## Customers/fleets with the most layout variants
| Customer | Template repos |
|---|---|
| TGVM | 10 (tgvm, -730/-734/-830/-834/-930/-934/-943/-954/-945) |
| DOSTO NEU | 6 (base, nv2, nv4, nv6, fv5, fv6) |
| NS-ICNG | 2 (5c, 8c) |
| OSTA | 2 (3c, 5c) |
| ~45 others | 1 each |

## The ~49 fleets (international footprint)
ace, alpin, caledonian, casablanca, cfl, dani, dml, dostoneu, dsb, dtt, enno, eurostar, firstrail,
Fremtidenstog, kinzigtal, luna, lyria, mainweser, msw01, nightjet, normandie, norsketog (72/77),
ns-icng, ntv, ntv5g, oce, ono, osta, osud, otu, ouigofrance, ouigospain, pta, ptaaus, qtmp, queensland,
raaberbahn, rbi, reference, regiolis, renfe, seq, talgo, tgv, tgva, tgvm, 3ufc, 3ux.
(Operators across AT/DE/FR/ES/NL/DK/NO/LU/MA/AU/UK.)

## Bearing on the review
- The earlier "14 report variants / 14 train layouts" wording **materially understated** scope. Correct
  framing: **14 report classes in the app, backing ~49 customer fleets via 65 template repos (well over a
  hundred individual train configurations once per-variant `.cfg` files are counted).**
- This **strengthens "improve, not replace"**: a rewrite's blast radius and re-certification surface are far
  larger than 14 — it would have to preserve behaviour for ~49 fleets / 65 template layouts in service.
- Baseline currency also re-confirmed live: `origin/master` is still `8042c8d` / **v2.3.12** (latest tag
  2.3.12); the review is current, not stale.

## Access note
Enumerated via a GitLab PAT the engineer supplied for this purpose. Read-only API queries
(`/groups/20/projects`, per-project blob search); no writes. (Token is a credential — should be rotated by
the engineer after this session as good practice.)
