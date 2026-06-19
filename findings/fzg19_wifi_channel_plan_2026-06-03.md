# Fzg 19 (4734-119) Wi-Fi 5 GHz channel plan — IBS Phase 4 WE1/WE2 fix

Date: 2026-06-03. Source: live `iw dev` on all 16 APs (10.179.45.218–233) + nv4 `rules.yaml` + nv4-topology.md.
Coach order front→back: **A → G → E → B**. G & E are the middle (`m`) coaches.

## AP archetypes (by rules.yaml)
- **WIDE-5G** (Modulation 28/28, Bandwidth 5 = 80 MHz): both radios bonded on ONE 5 GHz channel.
- **DUAL** (Modulation 3/10, Bandwidth 0 = 20 MHz): radio0 = 5 GHz ch36 (20 MHz, no HT), radio1 = a 2.4 GHz channel.

## CURRENT state (live)

| Coach | AP1 | AP2 | AP3 (WE1) | AP4 |
|---|---|---|---|---|
| A (non-m) | DUAL 5G36 + 2.4G ch1 | WIDE-5G **36** | WIDE-5G **44** | DUAL 5G36 + 2.4G ch11 |
| G (m)     | WIDE-5G **36** | DUAL 5G36 + 2.4G ch1 | DUAL 5G36 + 2.4G ch11 | WIDE-5G **44** |
| E (m)     | WIDE-5G **36** | DUAL 5G36 + 2.4G ch1 | DUAL 5G36 + 2.4G ch11 | WIDE-5G **44** |
| B (non-m) | DUAL 5G36 + 2.4G ch1 | WIDE-5G **36** | WIDE-5G **44** | DUAL 5G36 + 2.4G ch11 |

**Customer complaint:** on G/E, WE1 (=AP3) scans as ch11 (its 2.4 GHz radio) instead of ch44.
Root cause: on m-coaches the WIDE-5G role is on AP1/AP4; on non-m it's on AP2/AP3. So AP3m/AP2m
are DUAL APs whose user-facing service SSIDs ride the 2.4 GHz radio → ch11/ch1.

## 5 GHz channel occupancy per coach (CURRENT)
Every coach: **ch36 ×3 radios, ch44 ×1 radio.** (3 APs touch 36, 1 touches 44.) Skewed onto ch36 in all coaches, both variants. This is the existing fleet reality, not introduced by us.

## Channel adjacency note
ch36 (5180, 80 MHz) occupies 5170–5250 → overlaps ch44 (5220, 80 MHz, 5190–5270). With 80 MHz width,
ch36 and ch44 are NOT non-overlapping. True non-overlap at 80 MHz needs ch36 vs ch149 (UNII-1 vs UNII-3),
or drop to 40/20 MHz. Current design already has this overlap on EVERY coach.

## PROPOSED target — Option A: make m-coaches mirror non-m (WE1=ch44, WE2=ch36 everywhere)

Goal stated by customer: WE1 should be ch44. Make G/E identical to A/B.

| Coach | AP1 | AP2 (WE2) | AP3 (WE1) | AP4 |
|---|---|---|---|---|
| A | DUAL 5G36+2.4G1 | WIDE-5G 36 | WIDE-5G 44 | DUAL 5G36+2.4G11 |
| G | DUAL 5G36+2.4G1 | WIDE-5G 36 | WIDE-5G 44 | DUAL 5G36+2.4G11 |
| E | DUAL 5G36+2.4G1 | WIDE-5G 36 | WIDE-5G 44 | DUAL 5G36+2.4G11 |
| B | DUAL 5G36+2.4G1 | WIDE-5G 36 | WIDE-5G 44 | DUAL 5G36+2.4G11 |

rules.yaml changes (4 AP roles):
- AP1m-v1: Mod 28/28→**3/10**, BW 5→**0**, Freq 5180→**2412** (becomes DUAL like AP1)
- AP2m-v1: Mod 3/10→**28/28**, BW 0→**5**, Freq 2412→**5180** (becomes WIDE ch36 like AP2)
- AP3m-v1: Mod 3/10→**28/28**, BW 0→**5**, Freq 2462→**5220** (becomes WIDE ch44 like AP3)
- AP4m-v1: Mod 28/28→**3/10**, BW 5→**0**, Freq 5220→**2462** (becomes DUAL like AP4)

Per-coach 5G occupancy after: ch36 ×3, ch44 ×1 — unchanged skew, but identical to non-m. Closes ticket exactly.

## PROPOSED target — Option B: minimal (only the 2 complained APs)
- AP2m-v1: → WIDE ch36 (Mod 28/28, BW 5, Freq 5180)
- AP3m-v1: → WIDE ch44 (Mod 28/28, BW 5, Freq 5220)
- AP1m/AP4m unchanged (stay WIDE 36/44)
Result per m-coach 5G: ch36 ×2 (AP1m,AP2m wide) + ch44 ×2 (AP3m,AP4m wide) + DUAL radios gone from m. WE1/WE2 read correctly, but loses 2.4 GHz coverage on m-coaches entirely (no AP left on 2.4G) and doubles up wide APs co-channel. NOT recommended — kills 2.4 GHz clients.

## WHY the m-variant exists (git archaeology — read before any fix)
Commit `868f189` (Davud Zejnelovic, 2026-04-07) "Mirrored x1-x3, x2-x4 AP configuration after coach 2".
Before it, ALL coaches shared one AP rule (`coach_number: [1,2,3,4,5,6]`). The commit split coaches 3,4 into
an `m` variant that **mirrors the 5 GHz channels** vs non-m:
- non-m WIDE APs: AP2=ch36, AP4=ch44
- m     WIDE APs: AP2m=ch44, AP4m=ch36   ← deliberate stagger so adjacent coaches don't repeat a 5G channel
This is a CORRECT co-channel-avoidance idea. **Do NOT delete the m-variant (Option A is therefore WRONG —
it would undo Davud's intended staggering).**

The actual DEFECT: the mirror also swapped wirelessFreq on the *dual-band* APs (AP1m=2462, AP3m=2412).
On a DUAL AP, wirelessFreq sets the 2.4 GHz radio while radio0 hard-defaults to 5 GHz ch36. Net effect:
on m-coaches the AP positions the customer calls WE1/WE2 are DUAL APs whose service SSIDs ride 2.4 GHz
(ch11/ch1) → the complaint. The fix must KEEP the stagger and instead ensure WE1/WE2 land on the WIDE-5G
role on every coach.

## Nomad-side sources checked (none carry WE↔AP map or channel plan) — 2026-06-03
- nv4 rules.yaml / templates: use AP1–4, no WE labels; only the current (buggy) freqs.
- 4734-119_IP-Port-Allocation.pdf: labels APs "Access point A1…B4" against switch ports; NO WE labels, NO channels.
- SDD v2.3 (design freeze): "WE1/WE2" here = Wagenende CCU-cabinet mount locations (cars 300/500), NOT the AP labels. "channel"=GPS spec; MHz/2.4-5GHz/80MHz = Westermo RT610-LV datasheet capabilities only. No per-AP channel plan, no WE↔AP map.
→ The WE↔AP-position mapping and intended channel plan exist only on the Stadler side. Must ask Anton.

## BLOCKED — need WE↔AP-position mapping from Stadler
WE1/WE2 are Stadler physical labels, NOT in the Nomad repo. The correct fix depends on which AP position
(AP1/2/3/4, = which switch e0-4 / e1-2) is "WE1 Unter" / "WE2". Anchor from Anton: WE1 should be ch44
(a 5 GHz wide AP). Awaiting exact WE↔AP↔switch-port map from Anton / Stadler installation drawing before
designing the corrected (stagger-preserving) channel plan and pushing. Options A and B above are SUPERSEDED.

## Recommendation (revised)
Do NOT push yet. Once Stadler confirms WE↔AP mapping: make WE1/WE2 the WIDE-5G APs on m-coaches with the
mirrored channels (preserve Davud's stagger), move the 2.4 GHz/dual role to the other two positions. The
ch36/ch44 80 MHz overlap is pre-existing fleet-wide and out of scope for this ticket — flag to R&D/WLAN design.

## Test push scope on Fzg 19 (Option A)
4 APs reconfigured per m-coach × 2 m-coaches = 8 APs:
- G: AP1m .231, AP2m .228, AP3m .224, AP4m .219  (need to confirm .228/.224 vs .223/.222 are G vs E)
- E: AP1m .232, AP2m .223, AP3m .222, AP4m .218
Mechanism: edit live /etc/obn/rules.yaml on CCU → `obn discover && obn report` → `obn update c <ip>` each AP (reboots) → verify `iw dev`.
