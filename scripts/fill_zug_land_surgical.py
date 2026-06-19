#!/usr/bin/env python3
"""
fill_zug_land_surgical.py — Fill the ZUG-LAND sheet by surgically replacing ONLY
worksheets/sheet4.xml inside a copy of the workbook zip. Every other part — the
6 drawings, 2 images, charts, themes, shared strings, all other sheets — is copied
byte-for-byte from the original, so nothing is lost (unlike an openpyxl round-trip,
which drops DrawingML).

Strategy:
  - keep rows 1-2 (title bar + column headers) exactly as they are in the original
  - replace rows 3+ of <sheetData> with our train<->ground flow rows
  - use inline strings (t="inlineStr") so the shared-strings table is untouched
  - reuse existing cell style indices: 33 = header fill (bold/white), 34/35 = bordered data cells
  - update <dimension> to the new extent
"""
import re
import shutil
import zipfile
from xml.sax.saxutils import escape

SRC = "design freeze/network-planning-v7.xlsx"
OUT = "design freeze/network-planning-v8-WORKING.xlsx"
SHEET = "xl/worksheets/sheet4.xml"

# style indices observed in the original sheet4.xml
S_HEADER = "33"   # bold white-on-fill (used for col headers in row 2) -> reuse for section bands
S_DATA_L = "34"   # bordered data cell (left group)
S_DATA_R = "35"   # bordered data cell (right group)
COLS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]
NCOL = len(COLS)

# ---- the content (same data as reviewed, section markers + rows) ----
def S(label):
    return ("__SECTION__", label)

rows = [
    S("Nomad IoB — CCU <-> MAR5 Backend (NextLayer DC, Wien)  ·  source: SDD Table 8 + 'NC-ID und Fzg-ID'"),
    ("MAR5 VPN tunnel (CCU -> assigned HA)", "Train -> Land", "CCU (bond0)", "10.179.x.1 / 10.178.x.1", "ephemeral",
     "Assigned MAR5 Home Agent", "mar3be06-09 (see ref below)", "UDP/MAR5", "WAN (cellular)", "IPv4", "UDP (MAR5 tunnel, AES-256)"),
    ("  HA mar3be06  (Dosto Neu 1-10)", "reference", "", "", "",
     "mar3be06.nextlayer", "int 172.16.195.136 / pub 213.208.157.7", "", "", "IPv4", ""),
    ("  HA mar3be07  (Dosto Neu 11-21)", "reference", "", "", "",
     "mar3be07.nextlayer", "int 172.16.195.137 / pub 213.208.157.9", "", "", "IPv4", ""),
    ("  HA mar3be08  (Dosto Neu 22-32)", "reference", "", "", "",
     "mar3be08.nextlayer", "int 172.16.195.138 / pub 213.208.157.77", "", "", "IPv4", ""),
    ("  HA mar3be09  (Dosto Neu 33-42 + benches)", "reference", "", "", "",
     "mar3be09.nextlayer", "int 172.16.195.139 / pub 213.208.157.79", "", "", "IPv4", ""),
    ("Telemetry / MQTT (via tunnel)", "Train -> Land", "CCU (telemetry)", "10.179.x.1", "ephemeral",
     "HiveMQ MQTT broker (backend)", "via MAR5 HA", "1883 / 8883", "100 -> WAN", "IPv4 (in tunnel)", "TCP (MQTT/MQTTS)"),
    ("NMS / Telemetry stats, logs", "Train -> Land", "CCU", "10.179.x.1", "ephemeral",
     "NMS app / Zabbix / RTL log collector", "CDC 10.178.0.0/16", "various", "100 -> WAN", "IPv4 (in tunnel)", "TCP"),
    ("Portal / OBN image pull, updates", "Land -> Train", "Rollout Mgr / CDC", "CDC 10.178.0.0/16", "443",
     "CCU (Docker portal)", "10.179.x.1", "443", "WAN -> 100", "IPv4 (in tunnel)", "TCP (HTTPS)"),
    ("Engineering Pages access (staff)", "On-board", "iobstaff client", "10.205.{train}.x", "ephemeral",
     "CCU Engineering Pages", "engineering.page", "8005", "30", "IPv4", "TCP (HTTPS)"),

    S("Stadler wayside — routed via VLAN 7 -> CCU (NAT) -> Land  ·  source: SDD 6.18.1 'Erlaubte Verbindungen'"),
    ("Stadler RDS VPN tunnel", "Train -> Land", "Stadler Router (via vlan7)", "172.19.x.x (vlan7)", "ephemeral",
     "Stadler RDS", "62.2.130.53", "83", "7 -> WAN", "IPv4", "UDP"),
    ("Stadler RDS VPN tunnel (2nd port)", "Train -> Land", "Stadler Router (via vlan7)", "172.19.x.x (vlan7)", "ephemeral",
     "Stadler RDS", "62.2.130.53", "84", "7 -> WAN", "IPv4", "UDP"),
    ("Data transfer to OEBB landside", "Train -> Land", "Stadler Router (via vlan7)", "172.19.x.x (vlan7)", "ephemeral",
     "OEBB landside (SFTP)", "195.69.192.153", "22", "7 -> WAN", "IPv4", "TCP (SSH/SFTP)"),
    ("IPSec tunnel to video server", "Train -> Land", "Stadler Router (via vlan7)", "172.19.x.x (vlan7)", "500",
     "Video server (Stadler)", "tbd (Stadler)", "500", "7 -> WAN", "IPv4", "UDP (IKE/IPSec)"),
    ("AFZ -> landside AFZ server", "Train -> Land", "AFZ (via vlan7/SecGW)", "VLAN 8 (Stadler)", "ephemeral",
     "ftp-afz.landside.oebb-flotte", "195.69.194.146", "tbd (Stadler)", "8 -> 7 -> WAN", "IPv4", "tbd (FTP/SFTP)"),
    ("CCTV -> landside CCTV server", "Train -> Land", "Recorder (via vlan7/SecGW)", "VLAN 5 (Stadler)", "ephemeral",
     "cctv.landside.oebb-flotte", "10.10.x.y (Stadler landing-zone)", "tbd (Stadler)", "5 -> 7 -> WAN", "IPv4", "tbd (Stadler)"),

    S("Time & name services  ·  source: SDD 'Zeit synchronisation' + 'Backend Netzwerke'"),
    ("NTP - OBS reference (primary)", "Train -> Land", "OBS (NTP master)", "VLAN 7 (Stadler)", "123",
     "Landside Internet NTP", "via vlan7 -> CCU -> WAN", "123", "7 -> WAN", "IPv4", "UDP (NTP)"),
    ("NTP - backend source (IoB)", "Train -> Land", "CCU / switches / APs", "10.179.x.x", "123",
     "Backend NTP server", "10.178.13.1", "123", "100 -> WAN", "IPv4 (in tunnel)", "UDP (NTP)"),
    ("NTP - RCU via SNAT (3rd-party)", "On-board", "Stadler RCU NTP", "192.168.101.10 / .15", "123",
     "OBS (via Stadler FW SNAT)", "VLAN 7", "123", "7", "IPv4", "UDP (NTP, SNAT by FW)"),
    ("DNS - zug-domain resolution", "On-board / Land", "Train clients / CCU", "per VLAN", "ephemeral",
     "DNS (CCU + backend blacklisting)", "CCU + CDC DNS", "53", "various -> WAN", "IPv4", "TCP/UDP (DNS)"),
    ("GPS / NMEA feed (staff/CCU)", "On-board", "CCU GPS source", "10.179.x.1", "ephemeral",
     "iobstaff / OBS (vlan7)", "10.205.x.x / vlan7", "2947", "30 / 7", "IPv4", "TCP (gpsd)"),

    S("Train-to-Ground (T2G) reference addresses  ·  source: 'IP-Adresse ZUG' / 'IP-Adresse LAND' (Stadler/RDC model)"),
    ("CCU T2G VIP (router addr)", "reference", "ccu-t2g", "10.70.0.13", "n/a",
     "(T2G VIP for train<->land)", "", "n/a", "T2G", "IPv4", ""),
    ("CCTV recorder external access", "reference", "rec1b / rec2b", "10.52.0.10 / .11", "n/a",
     "(external CCTV access VIP)", "", "n/a", "T2G", "IPv4", ""),
    ("AFZ passenger counting", "reference", "AFZ", "10.38.0.10", "n/a",
     "ftp-afz.landside.oebb-flotte", "195.69.194.146", "n/a", "T2G", "IPv4", ""),
    ("CCU backend servers (T2G DNS)", "reference", "mar3be1-4.nextlayer.oebb.com", "see MAR5 alloc", "n/a",
     "(backend home agents)", "213.208.157.7/.9/.77/.79", "n/a", "T2G", "IPv4", ""),

    S("Open items — owner: Stadler (INFO 'Offene Themen', 2025-11-03)"),
    ("Zug-Land Endpunkte (full list)", "tbd", "tbd (Stadler)", "tbd (Stadler)", "tbd",
     "tbd (Stadler)", "tbd (Stadler)", "tbd", "tbd", "tbd", "tbd"),
    ("Multitraktion Stadler-VLAN routing", "tbd", "tbd (Stadler/Nomad VO)", "tbd", "tbd",
     "tbd", "tbd", "tbd", "5,15 (+VO)", "tbd", "tbd"),
    ("Reservierung / PIS wayside endpoints", "tbd", "tbd (Stadler)", "tbd (Stadler)", "tbd",
     "tbd (Stadler)", "tbd (Stadler)", "tbd", "6 / 3", "tbd", "tbd"),
]

def cell_xml(col, rownum, style, text):
    ref = f"{col}{rownum}"
    if text == "" or text is None:
        return f'<c r="{ref}" s="{style}"/>'
    return (f'<c r="{ref}" s="{style}" t="inlineStr">'
            f'<is><t xml:space="preserve">{escape(text)}</t></is></c>')

def build_rows(start_row):
    out = []
    rnum = start_row
    for r in rows:
        if r[0] == "__SECTION__":
            label = r[1]
            cells = [cell_xml("A", rnum, S_HEADER, label)]
            # fill the rest of the columns with the header style (empty) so the band spans
            for col in COLS[1:]:
                cells.append(f'<c r="{col}{rnum}" s="{S_HEADER}"/>')
            out.append(f'<row r="{rnum}" spans="1:17" ht="18" customHeight="1">{"".join(cells)}</row>')
        else:
            cells = []
            for j, val in enumerate(r):
                col = COLS[j]
                style = S_DATA_L if col in ("A", "C", "D", "F", "G") else S_DATA_R
                cells.append(cell_xml(col, rnum, style, val))
            out.append(f'<row r="{rnum}" spans="1:17" ht="28" customHeight="1">{"".join(cells)}</row>')
        rnum += 1
    return "".join(out), rnum - 1

# read original sheet xml
zin = zipfile.ZipFile(SRC)
xml = zin.read(SHEET).decode("utf-8")

# split out <sheetData> ... </sheetData>
m = re.search(r"(<sheetData>)(.*?)(</sheetData>)", xml, re.S)
assert m, "sheetData not found"
sd_open, sd_body, sd_close = m.group(1), m.group(2), m.group(3)

# keep rows 1 and 2 only from the original body
keep = re.findall(r'<row r="([12])"[^>]*>.*?</row>', sd_body, re.S)
# extract the literal row1/row2 elements
row12 = "".join(re.findall(r'(<row r="[12]"[^>]*>.*?</row>)', sd_body, re.S))
assert row12.count("<row") == 2, f"expected 2 header rows, got {row12.count('<row')}"

new_rows_xml, last_row = build_rows(3)
new_sheetdata = sd_open + row12 + new_rows_xml + sd_close
xml2 = xml[:m.start()] + new_sheetdata + xml[m.end():]

# update <dimension ref="A1:Q30"/> to new extent
xml2 = re.sub(r'<dimension ref="[^"]*"/>', f'<dimension ref="A1:Q{last_row}"/>', xml2)

# also widen columns J/K (10,11) and tweak col widths via <cols>: original sets 9-11 width 21.4;
# we leave widths as-is (acceptable) to avoid touching <cols> structure.

# write a new zip: copy every entry verbatim except SHEET
shutil.copyfile(SRC, OUT)  # start from an exact copy (preserves order/metadata baseline)
# rewrite just the one entry by rebuilding the zip (zipfile can't replace in place)
tmp = OUT + ".tmp"
with zipfile.ZipFile(SRC) as zsrc, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zdst:
    for item in zsrc.infolist():
        data = zsrc.read(item.filename)
        if item.filename == SHEET:
            data = xml2.encode("utf-8")
        # preserve compression type per-entry
        zi = zipfile.ZipInfo(item.filename, date_time=item.date_time)
        zi.compress_type = item.compress_type
        zi.external_attr = item.external_attr
        zi.internal_attr = item.internal_attr
        zi.create_system = item.create_system
        zdst.writestr(zi, data)
shutil.move(tmp, OUT)

print("WROTE", OUT)
print("ZUG-LAND rows: 2 headers + content, last row =", last_row)
