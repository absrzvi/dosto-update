# C3 — OBN → Upstream-Consumer Boundary Sweep (origin/master v2.3.12)

General audit of the remote code **as-is** for edge cases/bugs whose blast radius is the upstream
consuming apps (NMS, Zabbix, telemetry). 3 hunters over OBN's output surface + adversarial verification.
21 agents. Full register: `C3_consumer_findings_register.json`.

**Method note:** this is NOT centred on the redundant-link symptom you gave as an example — that symptom
turns out to be just *one trigger* of the most serious finding (C-1, dropped devices). The sweep audited
every field and event OBN emits.

## Outcome
**18 raw → 8 confirmed, 7 needs-runtime, 3 refuted, 0 duplicate.**

## The consumer model (why these bugs exist)
OBN feeds two consumers by two different mechanisms — a split that itself produces boundary bugs:
- **NMS** consumes OBN's MQTT `obn/consist` (full topology+inventory) and `obn/event/device_*` into
  MongoDB → renders the train diagram, inventory (fw/config/coach), and add/remove. **NMS trusts OBN for
  "what devices exist."**
- **Zabbix** consumes OBN's Zabbix-LLD (`lib/zabbix.py` → coach/device macros) for host discovery, but does
  its **own** SNMP/ICMP polling for up/down. So a device's *existence* comes from OBN; its *liveness* comes
  from Zabbix's own polls. Divergence between the two is the root of "shows down / shows missing" confusion.
- **Telemetry** consumes `obn/device/stats|ports|user_count`.

## Three defect classes (all on origin/master as-is)

### Class 1 — Dropped devices (most serious)
`normalise_devices()` (report.py:254) rebuilds `device_instances` keeping ONLY devices with non-None
coach_number AND device_number AND type. **Any discovered, online device the topology walk could not fully
number is silently deleted** → absent from the NMS consist payload (C-1) AND from the Zabbix LLD coach
count (C-6). For DOSTO the drop is fully silent (the DOSTO walk doesn't even call
`report_unexpected_connection()` that other variants use).
- **Triggers (general):** any device on an unexpected port — mis-cabled coupler, AP not on E0-4/E1-2, a
  switch the BFS couldn't number, OR a device reachable only via a redundant path the primary walk didn't
  traverse. **The redundant-link/switch-down case you cited is one instance of this class, not a separate
  bug.**
- **Consumer symptom:** NMS renders the device as missing/down though it's online and forwarding; Zabbix
  never creates the host, so a real end-coach outage is invisible (absent ≠ DOWN).

### Class 2 — Flap / spurious events (no debounce)
The MQTT add/remove diff (`generate_device_mqtt_events`, report.py:436/445) compares ONE fresh discovery
snapshot against the last published one, keyed purely by MAC, with **no confirmation/hysteresis**. A single
SNMP timeout in one cycle → `device_removed` (NMS shows it gone) → `device_added` next cycle → inventory
flap (C-2, C-5, plus needs-runtime variants). This is the consumer-facing face of the same silent-None /
transient-discovery-miss pattern Part B found *inside* OBN.

### Class 3 — Stale-suppression & wrong fields
- **Stale suppression (C, needs-runtime):** `compare_json()` decides "changed" from Device dataclass
  `compare=True` fields, which deliberately EXCLUDE `coach_number`/`device_number`/`type`/
  `physical_coach_number`. So a *corrected* topology (e.g. numbering fixed) with other fields unchanged →
  `compare_json` returns False → **the correction is never republished → NMS stays permanently stale.**
- **Wrong/stale fields pushed:** paintedCoachId = literal "unknown" fleet-wide (C-3; OBN
  `physical_coach_map_file` unset) → NMS & Zabbix `{#PAINTED_COACH_NUMBER}` = "UNKNOWN" (C-7);
  firmware/config/serial "unknown" sent as a real value, indistinguishable from a genuine reading
  (needs-runtime); `macAddr` UPPERCASE on `obn/consist` vs lowercase `mac` on `obn/event/*` →
  case-sensitive correlation mismatch risk (C-4).
- **Template-driven LLD (C-8):** Zabbix LLD advertises the `consist.yaml` template grid, not what was
  discovered — extra real devices never monitored; template entries for absent devices become check-fails.

## Confirmed findings (8)
| Sev | Consumer | Location | Class | Finding |
|---|---|---|---|---|
| HIGH | NMS | report.py:254 | dropped_device | Unnumbered discovered devices deleted from consist payload → NMS shows missing |
| HIGH | Zabbix | zabbix.py:44 | zabbix_lld | `number_of_coaches = max(coach_number)` drops trailing coaches whose devices weren't numbered → end-coach outage invisible |
| MED | NMS | report.py:445 | spurious_event | Dropped device also emits `device_removed` → add/remove churn |
| MED | NMS | report.py:436 | spurious_event | No hysteresis on add/remove diff — any one-cycle absence published immediately |
| MED | Zabbix | zabbix.py:57 | contract_mismatch | LLD is template-driven not discovery-driven — real extra devices unmonitored |
| LOW | NMS | report.py:339 | stale_or_wrong_field | paintedCoachId → "unknown" for a whole coach when its switch is unmapped/dropped |
| LOW | NMS | report.py:205 | contract_mismatch | macAddr uppercased on consist, lowercase on events → MAC-correlation mismatch |
| LOW | Zabbix | zabbix.py:76 | zabbix_lld | `{#PAINTED_COACH_NUMBER}` always "UNKNOWN" fleet-wide |

## Needs-runtime (7)
device_removed/added flap on a single SNMP miss (report.py:433); fw/config/serial "unknown" sent as real
(206); compare_json suppresses real change via excluded fields (115/130); AP with coach but no device_number
dropped (report_dosto_neu.py:80); generate_nodes accesses `node['coach_number']` without the key guard
`check()` uses (zabbix.py:46).

## Refuted (3)
device_* payload field-drop via skip_empty (intended); ACE/ccjpa coach-0 exclusion (by design);
get_painted_coach_number stored-None claim (guarded). — verification filtered, not rubber-stamped.

## Classification (decisive for the decision)
| Where the fix belongs | Findings |
|---|---|
| **OBN-side** (this review) | C-1 dropped devices, C-2/C-4/C-5 events & MAC casing, C-3/C-7 painted-coach plumbing, compare_json staleness, zabbix LLD coach/grid (C-6/C-8) |
| **Consumer-side** (Zabbix template / NMS) | phantom port-down (no debounce), wrong template OIDs (fixed 06-08), PoE-fault not alarmed, painted-coach NMS toggle off — *field-observed, NOT in OBN code* |
| **Firmware-side** (VDS/Stadler) | SNMP AgentX subagent reinit, KMdev boot crash — root of several "switch down" reports |

**This split is the headline for the decision:** several "OBN problems" reported from the field are
actually **consumer-side or firmware-side** — replacing OBN would fix none of them. And the genuine OBN-side
consumer bugs are the **same two root patterns** as Part B (silent-None on discovery miss → drop/flap;
representation gaps), with the **same common fixes** (debounce + multi-sample confirm before emitting
remove; include-with-flag instead of drop; put numbering identity in the change-compare). → reinforces
**IMPROVE**.
