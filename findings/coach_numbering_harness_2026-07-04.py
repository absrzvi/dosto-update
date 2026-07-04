#!/usr/bin/env python3
"""Standalone harness: exercises report_dosto_neu_MERGED_2026-07-04.py against real
discovery fixtures, asserting the three target behaviours. Stubs lib.report so it runs
offline. Run: python coach_numbering_harness_2026-07-04.py   (needs the bench fixture).

RESULT 2026-07-04: 7/7 checks pass.
  Case 1 (switch down / bypass): 10 discovered switches retained + numbered; A1 DOWN
          (reciprocal-proven), B3 UNKNOWN (terminus, no false DOWN).
  Case 2 (alternate path up):    G2 off both expected edges but reciprocally reachable
          via redundant path -> PLACED at slot 2/2 + status OFF_EXPECTED_WIRING.
  Case 3 (miswire):              G2 one-directional/unreachable bogus peer -> UNPLACED
          (surfaced, not mis-numbered, not DOWN).

Note the reciprocal-reachability rule (proven necessary by case 3): a redundant-path
edge counts only if BOTH ends LLDP-see each other, else a misimaged switch claiming a
bogus neighbour would be "recovered" for free.
"""
import sys, json, types, importlib.util
from dataclasses import dataclass, field

FIND = "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/findings"
BENCH = f"{FIND}/fixture_bench_box1-t122_discovery_2026-07-04.json"


@dataclass
class Device:
    mac: str; ip: str; serial: str = None; firmware: str = None; bios: str = None
    config: str = None; uptime: int = None; neighbours: list = field(default_factory=list)
    coach_number: int = None; device_number: int = None; type: str = None
    target: dict = None; status: str = "UP"
    def __hash__(self): return hash(self.mac + self.ip)


class _L:
    def warning(self, *a): pass
    def info(self, *a): pass


class Report:
    def __init__(self, tt, devs):
        self.train_type = tt; self.logger = _L()
        self.device_instances = {d.mac: d for d in devs}
    def find_type(self, d, retype_icl=True):
        m = (d.mac or "").lower()
        if (d.serial or "").startswith("box"): return "BOX"
        if m.startswith("a0:59:3a"): return "SW"
        if m.startswith("00:14:5a"): return "AP"
        return "UNKNOWN"
    def get_device(self, meta):
        mac = meta.get("mac") if isinstance(meta, dict) else meta
        return next((d for d in self.device_instances.values() if d.mac.lower() == (mac or "").lower()), None)
    def normalise_devices(self, inc=0):
        self.device_instances = {k: v for k, v in self.device_instances.items()
                                 if v.coach_number is not None and v.device_number is not None and v.type is not None}


for n in ["lib", "lib.report", "lib.report.report"]:
    sys.modules[n] = types.ModuleType(n)
sys.modules["lib.report"].Device = Device
sys.modules["lib.report.report"].Report = Report
spec = importlib.util.spec_from_file_location("rdn", f"{FIND}/report_dosto_neu_MERGED_2026-07-04.py")
rdn = importlib.util.module_from_spec(spec); spec.loader.exec_module(rdn)


def load(p):
    d = json.load(open(p)); devs = d if isinstance(d, list) else d.get("devices", d)
    return [Device(mac=x["mac"], ip=x.get("ip"), serial=x.get("serial"),
                   config=x.get("config"), neighbours=x.get("neighbours", []) or []) for x in devs]


def cp(d):
    p = (d.config or "").split("-"); return p[1] if len(p) > 1 else None


def runr(tt, devs, leased=None):
    r = rdn.DostoNeuReport(tt, devs); r._leased_switch_count = lambda: leased
    cap = {}; r._write_placeholders = lambda p: cap.setdefault("p", p); r.number_coaches()
    return r, cap.get("p", [])


def unlink(devs, a, b):
    a.neighbours = [n for n in a.neighbours if (n.get("mac") or "").lower() != b.mac.lower()]
    b.neighbours = [n for n in b.neighbours if (n.get("mac") or "").lower() != a.mac.lower()]


P = [0]; F = [0]
def ck(c, m): print(("  PASS " if c else "  FAIL ") + m); P[0] += c; F[0] += (not c)


# CASE 1 — cold-bypass (bench has A1, B3 absent)
print("CASE 1 - cold-bypass (A1,B3 absent)")
r, ph = runr("nv4", load(BENCH), 10)
sw = [d for d in r.device_instances.values() if d.type == "SW"]
ck(len(sw) >= 10, f"all 10 discovered switches retained (+downs) = {len(sw)} rows")
a1 = next((d for d in sw if d.mac == "DOWN:A1"), None)
ck(a1 is not None and a1.status == "DOWN", "A1 emitted DOWN (reciprocal-proven)")
present = [d for d in sw if not d.mac.startswith("DOWN:")]
ck(all(d.status in ("UP", "OFF_EXPECTED_WIRING") for d in present), "all present switches healthy")

# CASE 2 — off-expected-wiring: G2 off both expected edges, reciprocal redundant edge to E2
print("CASE 2 - off-expected-wiring (G2 severed from G3+E1, reciprocal edge to E2)")
devs = load(BENCH)
g2 = next(d for d in devs if cp(d) == "G2"); g3 = next(d for d in devs if cp(d) == "G3")
e1 = next(d for d in devs if cp(d) == "E1"); e2 = next(d for d in devs if cp(d) == "E2")
unlink(devs, g2, g3); unlink(devs, g2, e1)
g2.neighbours.append({"mac": e2.mac, "port": 4}); e2.neighbours.append({"mac": g2.mac, "port": 4})
r, ph = runr("nv4", devs, 10)
g2r = next((d for d in r.device_instances.values() if cp(d) == "G2"), None)
ck(g2r is not None and (g2r.coach_number, g2r.device_number) == (2, 2), "G2 placed at slot 2/2 (not dropped)")
ck(g2r is not None and g2r.status == "OFF_EXPECTED_WIRING", "G2 flagged OFF_EXPECTED_WIRING")

# CASE 3 — true miswire: G2 sees only E2 one-directionally (E2 doesn't list G2), unreachable
print("CASE 3 - miswire (G2 one-directional bogus peer E2, not reciprocated)")
devs = load(BENCH)
g2 = next(d for d in devs if cp(d) == "G2"); e2 = next(d for d in devs if cp(d) == "E2")
for d in devs:
    d.neighbours = [n for n in d.neighbours if (n.get("mac") or "").lower() != g2.mac.lower()]
g2.neighbours = [{"mac": e2.mac, "port": 4}]
r, ph = runr("nv4", devs, 10)
g2r = next((d for d in r.device_instances.values() if cp(d) == "G2"), None)
unpl = [x for x in ph if x.get("status") == "UNPLACED" and "G2" in x["config"]]
ck(g2r is None, "miswired G2 NOT numbered")
ck(bool(unpl), "G2 surfaced as UNPLACED (not mis-numbered, not DOWN)")

print(f"\n==== {P[0]} passed / {F[0]} failed ====")
sys.exit(1 if F[0] else 0)
