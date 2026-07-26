# 4705-103 (Fzg 231) — IPA PDF vs rendered fv5 templates v0.0.19

Rendered locally with `train_id=231` from `nomad-obn-template-fv5` @ `41b552f` (v0.0.19).
Source of truth: `4705-103_IP-Port-Allocation.pdf`. Live-switch verification pending (train offline 2026-07-09).

Legend: ✅ match · 🟡 benign/cosmetic · 🟠 check design intent · ❌ fault
## Summary

- ✅ match: **377**
- 🟡 benign/cosmetic: **39**
- 🟠 check design intent: **4**
- ❌ faults: **0**

### Faults / design questions

| Switch | Port | Verdict |
|---|---|---|
| A1 | e0-2 | 🟠 v9 coupler containment (native-999, allow 5,15) — intentional deviation from IPA list |
| A3 | e0-2 | 🟠 v9 coupler containment (native-999, allow 5,15) — intentional deviation from IPA list |
| B1 | e0-2 | 🟠 v9 coupler containment (native-999, allow 5,15) — intentional deviation from IPA list |
| B3 | e0-2 | 🟠 v9 coupler containment (native-999, allow 5,15) — intentional deviation from IPA list |


## Switch A1

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch A3 | All (except OBS Interc… | Trunk | - | Switch A3 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch C1 | All (except OBS Interc… | Trunk | - | Switch C1 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | Frontkupplung A1 | 100, 2, 3, 5, 6, 7, 8,… | Trunk | - | Frontkupplung A1 | 5,15 | - | y | 🟠 v9 coupler containment (native-999, allow 5,15) — intentional deviation from IPA list |
| e0-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-4 | Access point A1 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP A1 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | Service FIS / CCTV | 2 | Access | 172.17.115.248 | Service FIS/ CCTV | 2 | 172.17.115.248 | y | ✅ |
| e1-0 | Überw. Kamera A7 | 5 | Access | 172.18.243.138 | Interior Camera A7 | 5 | 172.18.243.138 | y | ✅ |
| e1-1 | Überw. Kamera A2 | 5 | Access | 172.18.243.139 | Interior Camera A2 | 5 | 172.18.243.139 | y | ✅ |
| e1-2 | Überw. Kamera A1 | 5 | Access | 172.18.243.140 | Interior Camera A1 | 5 | 172.18.243.140 | y | ✅ |
| e1-3 | Überw. Kamera A5 | 5 | Access | 172.18.243.141 | Interior Camera A5 | 5 | 172.18.243.141 | y | ✅ |
| e1-4 | Überw. Kamera A9 | 5 | Access | 172.18.243.142 | Interior Camera A9 | 5 | 172.18.243.142 | y | ✅ |
| e1-5 | AFZ A1 | 8 | Access | 172.20.115.133 | AFZ A1 | 8 | 172.20.115.133 | y | ✅ |
| e1-6 | AFZ A2 | 8 | Access | 172.20.115.134 | AFZ A2 | 8 | 172.20.115.134 | y | ✅ |
| e1-7 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-8 | Sprechstelle A1 | 9 | Access | 172.20.243.133 | Sprechstelle A1 | 9 | 172.20.243.133 | y | ✅ |
| e1-9 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-10 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-11 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-12 | Future use box A5 | 90 | Access | - | Funksensor A5 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box A6 | 90 | Access | - | Funksensor A6 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | Seitenanzeige A1 | 3 | Access | 172.17.243.153 | Seitenanzeige A1 | 3 | 172.17.243.153 | y | ✅ |
| e1-15 | Seitenanzeige A3 | 3 | Access | 172.17.243.154 | Seitenanzeige A3 | 3 | 172.17.243.154 | y | ✅ |
| e2-0 | Bildschirm A3 | 3 | Access | 172.17.243.178 | Bildschirm A3 | 3 | 172.17.243.178 | y | ✅ |
| e2-1 | Bildschirm Werbung A1 | 3 | Access | 172.17.243.179 | Bildschirm Werbung A1 | 3 | 172.17.243.179 | y | ✅ |
| e2-2 | Bildschirm Werbung A5 | 3 | Access | 172.17.243.180 | Bildschirm Werbung A5 | 3 | 172.17.243.180 | y | ✅ |
| e2-3 | Bildschirm A1 | 3 | Access | 172.17.243.181 | Bildschirm A1 | 3 | 172.17.243.181 | y | ✅ |
| e2-4 | ADU A | 9 | Access | 172.20.243.131 | ADU A | 9 | 172.20.243.131 | y | ✅ |
| e2-5 | Audio Amp. A1 | 9 | Access | 172.20.243.149 | Audio Amp. A1 | 9 | 172.20.243.149 | y | ✅ |

## Switch A2

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch A3 | All (except OBS Interc… | Trunk | - | Switch A3 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch C3 | All (except OBS Interc… | Trunk | - | Switch C3 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-4 | Access point A2 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP A2 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | reserved | - | - | - | Reserved | - | - | n | ✅ unused/disabled |
| e1-0 | Überw. Kamera A8 | 5 | Access | 172.18.243.143 | Interior Camera A8 | 5 | 172.18.243.143 | y | ✅ |
| e1-1 | Überw. Kamera A4 | 5 | Access | 172.18.243.144 | Interior Camera A4 | 5 | 172.18.243.144 | y | ✅ |
| e1-2 | Überw. Kamera A3 | 5 | Access | 172.18.243.145 | Interior Camera A3 | 5 | 172.18.243.145 | y | ✅ |
| e1-3 | Überw. Kamera A6 | 5 | Access | 172.18.243.146 | Interior Camera A6 | 5 | 172.18.243.146 | y | ✅ |
| e1-4 | Überw. Kamera A10 | 5 | Access | 172.18.243.147 | Interior Camera A10 | 5 | 172.18.243.147 | y | ✅ |
| e1-5 | AFZ A3 | 8 | Access | 172.20.115.135 | AFZ A3 | 8 | 172.20.115.135 | y | ✅ |
| e1-6 | AFZ A4 | 8 | Access | 172.20.115.136 | AFZ A4 | 8 | 172.20.115.136 | y | ✅ |
| e1-7 | NVR A | 5 | Access | 172.18.243.133 | NVR A | 5 | 172.18.243.133 | y | ✅ |
| e1-8 | Sprechstelle A2 | 9 | Access | 172.20.243.134 | Sprechstelle A2 | 9 | 172.20.243.134 | y | ✅ |
| e1-9 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-10 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-11 | Bildschirm Werbung A4 | 3 | Access | 172.17.243.228 | Bildschirm Werbung A4 | 3 | 172.17.243.228 | y | ✅ |
| e1-12 | Future use box A2 | 90 | Access | - | Funksensor A2 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box A4 | 90 | Access | - | Funksensor A4 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | Seitenanzeige A2 | 3 | Access | 172.17.243.155 | Seitenanzeige A2 | 3 | 172.17.243.155 | y | ✅ |
| e1-15 | Seitenanzeige A4 | 3 | Access | 172.17.243.156 | Seitenanzeige A4 | 3 | 172.17.243.156 | y | ✅ |
| e2-0 | Bildschirm A4 | 3 | Access | 172.17.243.182 | Bildschirm A4 | 3 | 172.17.243.182 | y | ✅ |
| e2-1 | Bildschirm Werbung A8 | 3 | Access | 172.17.243.183 | Bildschirm Werbung A8 | 3 | 172.17.243.183 | y | ✅ |
| e2-2 | Bildschirm Werbung A6 | 3 | Access | 172.17.243.184 | Bildschirm Werbung A6 | 3 | 172.17.243.184 | y | ✅ |
| e2-3 | Bildschirm A2 | 3 | Access | 172.17.243.185 | Bildschirm A2 | 3 | 172.17.243.185 | y | ✅ |
| e2-4 | Bildschirm Werbung A2 | 3 | Access | 172.17.243.247 | Bildschirm Werbung A2 | 3 | 172.17.243.247 | y | ✅ |
| e2-5 | Audio Amp. A2 | 9 | Access | 172.20.243.150 | Audio Amp. A2 | 9 | 172.20.243.150 | y | ✅ |

## Switch A3

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch A1 | All (except OBS Interc… | Trunk | - | Switch A1 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch A2 | All (except OBS Interc… | Trunk | - | Switch A2 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | Frontkupplung A2 | 100, 2, 3, 5, 6, 7, 8,… | Trunk | - | Frontkupplung A2 | 5,15 | - | y | 🟠 v9 coupler containment (native-999, allow 5,15) — intentional deviation from IPA list |
| e0-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-4 | Access point A3 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP A3 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | reserved | - | - | - | reserved | - | - | n | ✅ unused/disabled |
| e1-0 | Rücksehkamera A1 | 5 | Access | 172.18.243.208 | Exterior Camera A1 | 5 | 172.18.243.208 | y | ✅ |
| e1-1 | Rücksehkamera A2 | 5 | Access | 172.18.243.209 | Exterior Camera A2 | 5 | 172.18.243.209 | y | ✅ |
| e1-2 | Access point A4 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP A4 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e1-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-4 | Firewall | 2 | Trunk | 172.17.115.129 | Firewall | 2,3,5,6,7,8,9,12,15 | - | y | 🟡 trunk extra VLANs ['3', '5', '6', '7', '8', '9', '12', '15'] |
| e1-5 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-6 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-7 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-8 | Sprechstelle A1R | 9 | Access | 172.20.243.133 | Sprechstelle A1R | 9 | 172.20.243.133 | y | ✅ |
| e1-9 | Sprechstelle A2R | 9 | Access | 172.20.243.134 | Sprechstelle A2R | 9 | 172.20.243.134 | y | ✅ |
| e1-10 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-11 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-12 | Future use box A1 | 90 | Access | - | Funksensor A1 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box A3 | 90 | Access | - | Funksensor A3 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | Frontanzeige A | 3 | Access | 172.17.243.151 | Frontanzeige A | 3 | 172.17.243.151 | y | ✅ |
| e1-15 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-0 | Bildschirm Werbung A3 | 3 | Access | 172.17.243.235 | Bildschirm Werbung A3 | 3 | 172.17.243.235 | y | ✅ |
| e2-1 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-3 | Sitzplatzreservierung A | 6 | Access | 172.19.115.138 | Sitzplatzreservierung A | 6 | 172.19.115.138 | y | ✅ |
| e2-4 | ADU AR | 9 | Access | 172.20.243.131 | ADU AR | 9 | 172.20.243.131 | y | ✅ |
| e2-5 | Service VLAN PWLAN | 100, 10, 20, 30, 31, 1… | Trunk | - | Service VLAN PWLAN | 100,10,20,30,31,131,150 | - | n | 🟡 service socket disabled by fleet convention (matches nv6) |

## Switch C1

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch A1 | All (except OBS Interc… | Trunk | - | Switch A1 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch E1 | All (except OBS Interc… | Trunk | - | Switch E1 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | OBS D1 | 100, 10, 20, 21, 22, 2… | Trunk | - | OBS D1 | 100,10,20,21,22,23,24,… | - | y | 🟡 trunk extra VLANs ['7'] |
| e0-3 | RDC D1 | 200, 202 | Trunk | - | RDC D1 | 200,202 | - | y | ✅ trunk |
| e0-4 | Access point C1 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP C1 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | Service FIS / CCTV | 2 | Access | 172.17.115.249 | Service FIS/ CCTV | 2 | 172.17.115.249 | y | ✅ |
| e1-0 | Überw. Kamera C7 | 5 | Access | 172.18.243.148 | Interior Camera C7 | 5 | 172.18.243.148 | y | ✅ |
| e1-1 | Überw. Kamera C2 | 5 | Access | 172.18.243.149 | Interior Camera C2 | 5 | 172.18.243.149 | y | ✅ |
| e1-2 | Überw. Kamera C1 | 5 | Access | 172.18.243.150 | Interior Camera C1 | 5 | 172.18.243.150 | y | ✅ |
| e1-3 | Überw. Kamera C5 | 5 | Access | 172.18.243.151 | Interior Camera C5 | 5 | 172.18.243.151 | y | ✅ |
| e1-4 | Überw. Kamera C9 | 5 | Access | 172.18.243.152 | Interior Camera C9 | 5 | 172.18.243.152 | y | ✅ |
| e1-5 | AFZ C1 | 8 | Access | 172.20.115.137 | AFZ C1 | 8 | 172.20.115.137 | y | ✅ |
| e1-6 | AFZ C2 | 8 | Access | 172.20.115.138 | AFZ C2 | 8 | 172.20.115.138 | y | ✅ |
| e1-7 | AFZ C5 | 8 | Access | 172.20.115.139 | AFZ C5 | 8 | 172.20.115.139 | y | ✅ |
| e1-8 | Sprechstelle C1 | 9 | Access | 172.20.243.135 | Sprechstelle C1 | 9 | 172.20.243.135 | y | ✅ |
| e1-9 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-10 | Bildschirm Werbung C1 | 3 | Access | 172.17.243.236 | Bildschirm Werbung C1 | 3 | 172.17.243.236 | y | ✅ |
| e1-11 | Bildschirm C5 | 3 | Access | 172.17.243.190 | Bildschirm C7 | 3 | 172.17.243.190 | y | 🟡 OK, label drift ('Bildschirm C7' vs 'Bildschirm C5') |
| e1-12 | Future use box C5 | 90 | Access | - | Funksensor C5 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box C6 | 90 | Access | - | Funksensor C6 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | Seitenanzeige C1 | 3 | Access | 172.17.243.157 | Seitenanzeige C1 | 3 | 172.17.243.157 | y | ✅ |
| e1-15 | Seitenanzeige C3 | 3 | Access | 172.17.243.158 | Seitenanzeige C3 | 3 | 172.17.243.158 | y | ✅ |
| e2-0 | Bildschirm C3 | 3 | Access | 172.17.243.186 | Bildschirm C3 | 3 | 172.17.243.186 | y | ✅ |
| e2-1 | Bildschirm Werbung C7 | 3 | Access | 172.17.243.187 | Bildschirm Werbung C7 | 3 | 172.17.243.187 | y | ✅ |
| e2-2 | Bildschirm Werbung C5 | 3 | Access | 172.17.243.188 | Bildschirm Werbung C5 | 3 | 172.17.243.188 | y | ✅ |
| e2-3 | Bildschirm C1 | 3 | Access | 172.17.243.189 | Bildschirm C1 | 3 | 172.17.243.189 | y | ✅ |
| e2-4 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-5 | Audio Amp. C1 | 9 | Access | 172.20.243.151 | Audio Amp. C1 | 9 | 172.20.243.151 | y | ✅ |

## Switch C2

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch C3 | All (except OBS Interc… | Trunk | - | Switch C3 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch E3 | All (except OBS Interc… | Trunk | - | Switch E3 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-4 | Access point C2 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP C2 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | reserved | - | - | - | Reserved | - | - | n | ✅ unused/disabled |
| e1-0 | Überw. Kamera C8 | 5 | Access | 172.18.243.153 | Interior Camera C8 | 5 | 172.18.243.153 | y | ✅ |
| e1-1 | Überw. Kamera C4 | 5 | Access | 172.18.243.154 | Interior Camera C4 | 5 | 172.18.243.154 | y | ✅ |
| e1-2 | Überw. Kamera C3 | 5 | Access | 172.18.243.155 | Interior Camera C3 | 5 | 172.18.243.155 | y | ✅ |
| e1-3 | Überw. Kamera C6 | 5 | Access | 172.18.243.156 | Interior Camera C6 | 5 | 172.18.243.156 | y | ✅ |
| e1-4 | Überw. Kamera C10 | 5 | Access | 172.18.243.157 | Interior Camera C10 | 5 | 172.18.243.157 | y | ✅ |
| e1-5 | AFZ C3 | 8 | Access | 172.20.115.140 | AFZ C3 | 8 | 172.20.115.140 | y | ✅ |
| e1-6 | AFZ C4 | 8 | Access | 172.20.115.141 | AFZ C4 | 8 | 172.20.115.141 | y | ✅ |
| e1-7 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-8 | Sprechstelle C2 | 9 | Access | 172.20.243.136 | Sprechstelle C2 | 9 | 172.20.243.136 | y | ✅ |
| e1-9 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-10 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-11 | Bildschirm Werbung C2 | 3 | Access | 172.17.243.237 | Bildschirm Werbung C2 | 3 | 172.17.243.237 | y | ✅ |
| e1-12 | Future use box C2 | 90 | Access | - | Funksensor C2 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box C4 | 90 | Access | - | Funksensor C4 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | Seitenanzeige C2 | 3 | Access | 172.17.243.159 | Seitenanzeige C2 | 3 | 172.17.243.159 | y | ✅ |
| e1-15 | Seitenanzeige C4 | 3 | Access | 172.17.243.160 | Seitenanzeige C4 | 3 | 172.17.243.160 | y | ✅ |
| e2-0 | Bildschirm C4 | 3 | Access | 172.17.243.191 | Bildschirm C4 | 3 | 172.17.243.191 | y | ✅ |
| e2-1 | Bildschirm Werbung C8 | 3 | Access | 172.17.243.192 | Bildschirm Werbung C8 | 3 | 172.17.243.192 | y | ✅ |
| e2-2 | Bildschirm Werbung C6 | 3 | Access | 172.17.243.193 | Bildschirm Werbung C6 | 3 | 172.17.243.193 | y | ✅ |
| e2-3 | Bildschirm C2 | 3 | Access | 172.17.243.194 | Bildschirm C2 | 3 | 172.17.243.194 | y | ✅ |
| e2-4 | Bildschirm C6 | 3 | Access | 172.17.243.195 | Bildschirm C6 | 3 | 172.17.243.195 | y | ✅ |
| e2-5 | Audio Amp. C2 | 9 | Access | 172.20.243.152 | Audio Amp. C2 | 9 | 172.20.243.152 | y | ✅ |

## Switch C3

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch A2 | All (except OBS Interc… | Trunk | - | Switch A2 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch C2 | All (except OBS Interc… | Trunk | - | Switch C2 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | OBS D1 | 100, 10, 20, 21, 22, 2… | Trunk | - | OBS D1 | 100,10,20,21,22,23,24,… | - | y | 🟡 trunk extra VLANs ['7'] |
| e0-3 | RDC D1 | 200, 202 | Trunk | - | RDC D1 | 200,202 | - | y | ✅ trunk |
| e0-4 | Access point C3 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP C3 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | reserved | - | - | - | Reserved | - | - | n | ✅ unused/disabled |
| e1-0 | Rücksehkamera C1 | 5 | Access | 172.18.243.210 | Exterior Camera C1 | 5 | 172.18.243.210 | y | ✅ |
| e1-1 | Rücksehkamera C2 | 5 | Access | 172.18.243.211 | Exterior Camera C2 | 5 | 172.18.243.211 | y | ✅ |
| e1-2 | Access point C4 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP C4 | 100,10,20,30,31,131,150 | - | y | ✅ trunk |
| e1-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-4 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-5 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-6 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-7 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-8 | Sprechstelle C1R | 9 | Access | 172.20.243.135 | Sprechstelle C1R | 9 | 172.20.243.135 | y | ✅ |
| e1-9 | Sprechstelle C2R | 9 | Access | 172.20.243.136 | Sprechstelle C2R | 9 | 172.20.243.136 | y | ✅ |
| e1-10 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-11 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-12 | Future use box C1 | 90 | Access | - | Funksensor C1 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box C3 | 90 | Access | - | Funksensor C3 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-15 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-0 | Bildschirm Werbung C3 | 3 | Access | 172.17.243.238 | Bildschirm Werbung C3 | 3 | 172.17.243.238 | y | ✅ |
| e2-1 | Bildschirm Werbung C4 | 3 | Access | 172.17.243.239 | Bildschirm Werbung C4 | 3 | 172.17.243.239 | y | ✅ |
| e2-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-3 | Sitzplatzreservierung C | 6 | Access | 172.19.115.139 | Sitzplatzreservierung C | 6 | 172.19.115.139 | y | ✅ |
| e2-4 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-5 | - | - | - | - | - | - | - | n | ✅ unused/disabled |

## Switch E1

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch F1 | All (except OBS Interc… | Trunk | - | Switch F1 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch C2 | All (except OBS Interc… | Trunk | - | Switch C2 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-4 | Access point E1 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP E1 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | Service FIS / CCTV | 2 | Access | 172.17.115.251 | Service FIS / CCTV | 2 | 172.17.115.251 | y | ✅ |
| e1-0 | Überw. Kamera E7 | 5 | Access | 172.18.243.168 | Interior Camera E7 | 5 | 172.18.243.168 | y | ✅ |
| e1-1 | Überw. Kamera E2 | 5 | Access | 172.18.243.169 | Interior Camera E2 | 5 | 172.18.243.169 | y | ✅ |
| e1-2 | Überw. Kamera E1 | 5 | Access | 172.18.243.170 | Interior Camera E1 | 5 | 172.18.243.170 | y | ✅ |
| e1-3 | Überw. Kamera E5 | 5 | Access | 172.18.243.171 | Interior Camera E5 | 5 | 172.18.243.171 | y | ✅ |
| e1-4 | Überw. Kamera E9 | 5 | Access | 172.18.243.172 | Interior Camera E9 | 5 | 172.18.243.172 | y | ✅ |
| e1-5 | AFZ E1 | 8 | Access | 172.20.115.147 | AFZ E1 | 8 | 172.20.115.147 | y | ✅ |
| e1-6 | AFZ E2 | 8 | Access | 172.20.115.148 | AFZ E2 | 8 | 172.20.115.148 | y | ✅ |
| e1-7 | AFZ E5 | 8 | Access | 172.20.115.149 | AFZ E5 | 8 | 172.20.115.149 | y | ✅ |
| e1-8 | Sprechstelle E1 | 9 | Access | 172.20.243.140 | Sprechstelle E1 | 9 | 172.20.243.140 | y | ✅ |
| e1-9 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-10 | Sprechstelle PRM E1 | 9 | Access | 172.20.243.141 | Sprechstelle PRM E1 | 9 | 172.20.243.141 | y | ✅ |
| e1-11 | Sprechstelle PRM WCR | 9 | Access | 172.20.243.144 | Sprechstelle PRM WCR | 9 | 172.20.243.144 | y | ✅ |
| e1-12 | Future use box E5 | 90 | Access | - | Funksensor E5 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box E7 | 90 | Access | - | Funksensor E7 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | Seitenanzeige E1 | 3 | Access | 172.17.243.165 | Seitenanzeige E1 | 3 | 172.17.243.165 | y | ✅ |
| e1-15 | Seitenanzeige E3 | 3 | Access | 172.17.243.166 | Seitenanzeige E3 | 3 | 172.17.243.166 | y | ✅ |
| e2-0 | Bildschirm E3 | 3 | Access | 172.17.243.206 | Bildschirm E3 | 3 | 172.17.243.206 | y | ✅ |
| e2-1 | Bildschirm Werbung E7 | 3 | Access | 172.17.243.207 | Bildschirm Werbung E7 | 3 | 172.17.243.207 | y | ✅ |
| e2-2 | Bildschirm Werbung E5 | 3 | Access | 172.17.243.208 | Bildschirm Werbung E5 | 3 | 172.17.243.208 | y | ✅ |
| e2-3 | Bildschirm E1 | 3 | Access | 172.17.243.209 | Bildschirm E1 | 3 | 172.17.243.209 | y | ✅ |
| e2-4 | ADU E | 9 | Access | 172.20.243.130 | ADU E | 9 | 172.20.243.130 | y | ✅ |
| e2-5 | Audio Amp. E1 | 9 | Access | 172.20.243.155 | Audio Amp. E1 | 9 | 172.20.243.155 | y | ✅ |

## Switch E2

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch E3 | All (except OBS Interc… | Trunk | - | Switch E3 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch C1 | All (except OBS Interc… | Trunk | - | Switch C1 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-4 | Access point E2 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP E2 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | reserved | - | - | - | Reserved | - | - | n | ✅ unused/disabled |
| e1-0 | Überw. Kamera E8 | 5 | Access | 172.18.243.173 | Interior Camera E8 | 5 | 172.18.243.173 | y | ✅ |
| e1-1 | Überw. Kamera E4 | 5 | Access | 172.18.243.174 | Interior Camera E4 | 5 | 172.18.243.174 | y | ✅ |
| e1-2 | Überw. Kamera E3 | 5 | Access | 172.18.243.175 | Interior Camera E3 | 5 | 172.18.243.175 | y | ✅ |
| e1-3 | Überw. Kamera E6 | 5 | Access | 172.18.243.176 | Interior Camera E6 | 5 | 172.18.243.176 | y | ✅ |
| e1-4 | Überw. Kamera E10 | 5 | Access | 172.18.243.198 | Interior Camera E10 | 5 | 172.18.243.198 | y | ✅ |
| e1-5 | AFZ E3 | 8 | Access | 172.20.115.150 | AFZ E3 | 8 | 172.20.115.150 | y | ✅ |
| e1-6 | AFZ E4 | 8 | Access | 172.20.115.151 | AFZ E4 | 8 | 172.20.115.151 | y | ✅ |
| e1-7 | AFZ E6 | 8 | Access | 172.20.115.152 | AFZ E6 | 8 | 172.20.115.152 | y | ✅ |
| e1-8 | Sprechstelle E2 | 9 | Access | 172.20.243.142 | Sprechstelle E2 | 9 | 172.20.243.142 | y | ✅ |
| e1-9 | Sprechstelle E1R | 9 | Access | 172.20.243.140 | Sprechstelle E1R | 9 | 172.20.243.140 | y | ✅ |
| e1-10 | Sprechstelle PRM E2 | 9 | Access | 172.20.243.143 | Sprechstelle PRM E2 | 9 | 172.20.243.143 | y | ✅ |
| e1-11 | Sprechstelle PRM E1R | 9 | Access | 172.20.243.141 | Sprechstelle PRM E1R | 9 | 172.20.243.141 | y | ✅ |
| e1-12 | Future use box E2 | 90 | Access | - | Funksensor E2 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box E4 | 90 | Access | - | Funksensor E4 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | Seitenanzeige E2 | 3 | Access | 172.17.243.167 | Seitenanzeige E2 | 3 | 172.17.243.167 | y | ✅ |
| e1-15 | Seitenanzeige E4 | 3 | Access | 172.17.243.168 | Seitenanzeige E4 | 3 | 172.17.243.168 | y | ✅ |
| e2-0 | Bildschirm E4 | 3 | Access | 172.17.243.211 | Bildschirm E4 | 3 | 172.17.243.211 | y | ✅ |
| e2-1 | Bildschirm Werbung E8 | 3 | Access | 172.17.243.212 | Bildschirm Werbung E8 | 3 | 172.17.243.212 | y | ✅ |
| e2-2 | Bildschirm Werbung E6 | 3 | Access | 172.17.243.213 | Bildschirm Werbung E6 | 3 | 172.17.243.213 | y | ✅ |
| e2-3 | Bildschirm E2 | 3 | Access | 172.17.243.214 | Bildschirm E2 | 3 | 172.17.243.214 | y | ✅ |
| e2-4 | Bildschirm E6 | 3 | Access | 172.17.243.215 | Bildschirm E6 | 3 | 172.17.243.215 | y | ✅ |
| e2-5 | Audio Amp. E2 | 9 | Access | 172.20.243.156 | Audio Amp. E2 | 9 | 172.20.243.156 | y | ✅ |

## Switch E3

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch F2 | All (except OBS Interc… | Trunk | - | Switch F2 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch E2 | All (except OBS Interc… | Trunk | - | Switch E2 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-4 | Access point E3 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP E3 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | reserved | - | - | - | Reserved | - | - | n | ✅ unused/disabled |
| e1-0 | Rücksehkamera E1 | 5 | Access | 172.18.243.214 | Exterior Camera E1 | 5 | 172.18.243.214 | y | ✅ |
| e1-1 | Rücksehkamera E2 | 5 | Access | 172.18.243.215 | Exterior Camera E2 | 5 | 172.18.243.215 | y | ✅ |
| e1-2 | Access point E4 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP E4 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e1-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-4 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-5 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-6 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-7 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-8 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-9 | Sprechstelle E2R | 9 | Access | 172.20.243.142 | Sprechstelle E2R | 9 | 172.20.243.142 | y | ✅ |
| e1-10 | Sprechstelle PRM WC | 9 | Access | 172.20.243.144 | Sprechstelle PRM WC | 9 | 172.20.243.144 | y | ✅ |
| e1-11 | Sprechstelle PRM E2R | 9 | Access | 172.20.243.143 | Sprechstelle PRM E2R | 9 | 172.20.243.143 | y | ✅ |
| e1-12 | Future use box E1 | 90 | Access | - | Funksensor E1 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box E3 | 90 | Access | - | Funksensor E3 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-15 | Bildschirm Werbung E1 | 3 | Access | 172.17.243.210 | Bildschirm Werbung E1 | 3 | 172.17.243.210 | y | ✅ |
| e2-0 | Bildschirm Werbung E3 | 3 | Access | 172.17.243.240 | Bildschirm Werbung E3 | 3 | 172.17.243.240 | y | ✅ |
| e2-1 | Bildschirm Werbung E4 | 3 | Access | 172.17.243.241 | Bildschirm Werbung E4 | 3 | 172.17.243.241 | y | ✅ |
| e2-2 | Fahrausweiseinrichtung | - | Access | - | Fahrausweiseinrichtung | - | - | n | 🟡 IPA has no VLAN/IP assigned; template disabled |
| e2-3 | Sitzplatzreservierung E | 6 | Access | 172.19.115.141 | Sitzplatzreservierung E | 6 | 172.19.115.141 | y | ✅ |
| e2-4 | ADU ER | 9 | Access | 172.20.243.130 | ADU ER | 9 | 172.20.243.130 | y | ✅ |
| e2-5 | Energiezahler E | 12 | Access | 172.22.115.131 | Energiezaehler E | 12 | 172.22.115.131 | y | ✅ |

## Switch F1

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch B1 | All (except OBS Interc… | Trunk | - | Switch B1 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch E1 | All (except OBS Interc… | Trunk | - | Switch E1 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-4 | Access point F1 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP F1 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | Service FIS / CCTV | 2 | Access | 172.17.115.252 | Service FIS/ CCTV | 2 | 172.17.115.252 | y | ✅ |
| e1-0 | Überw. Kamera F7 | 5 | Access | 172.18.243.177 | Interior Camera F7 | 5 | 172.18.243.177 | y | ✅ |
| e1-1 | Überw. Kamera F2 | 5 | Access | 172.18.243.178 | Interior Camera F2 | 5 | 172.18.243.178 | y | ✅ |
| e1-2 | Überw. Kamera F1 | 5 | Access | 172.18.243.179 | Interior Camera F1 | 5 | 172.18.243.179 | y | ✅ |
| e1-3 | Überw. Kamera F5 | 5 | Access | 172.18.243.180 | Interior Camera F5 | 5 | 172.18.243.180 | y | ✅ |
| e1-4 | Überw. Kamera F9 | 5 | Access | 172.18.243.181 | Interior Camera F9 | 5 | 172.18.243.181 | y | ✅ |
| e1-5 | AFZ F1 | 8 | Access | 172.20.115.153 | AFZ F1 | 8 | 172.20.115.153 | y | ✅ |
| e1-6 | AFZ F2 | 8 | Access | 172.20.115.154 | AFZ F2 | 8 | 172.20.115.154 | y | ✅ |
| e1-7 | AFZ F5 | 8 | Access | 172.20.115.155 | AFZ F5 | 8 | 172.20.115.155 | y | ✅ |
| e1-8 | Sprechstelle F1 | 9 | Access | 172.20.243.145 | Sprechstelle F1 | 9 | 172.20.243.145 | y | ✅ |
| e1-9 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-10 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-11 | Bildschirm F5 | 3 | Access | 172.17.243.242 | Bildschirm F7 | 3 | 172.17.243.242 | y | 🟡 OK, label drift ('Bildschirm F7' vs 'Bildschirm F5') |
| e1-12 | Future use box F5 | 90 | Access | - | Funksensor F5 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box F6 | 90 | Access | - | Funksensor F6 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | Seitenanzeige F1 | 3 | Access | 172.17.243.169 | Seitenanzeige F1 | 3 | 172.17.243.169 | y | ✅ |
| e1-15 | Seitenanzeige F3 | 3 | Access | 172.17.243.170 | Seitenanzeige F3 | 3 | 172.17.243.170 | y | ✅ |
| e2-0 | Bildschirm F3 | 3 | Access | 172.17.243.216 | Bildschirm F3 | 3 | 172.17.243.216 | y | ✅ |
| e2-1 | Bildschirm Werbung F7 | 3 | Access | 172.17.243.217 | Bildschirm Werbung F7 | 3 | 172.17.243.217 | y | ✅ |
| e2-2 | Bildschirm Werbung F5 | 3 | Access | 172.17.243.218 | Bildschirm Werbung F5 | 3 | 172.17.243.218 | y | ✅ |
| e2-3 | Bildschirm F1 | 3 | Access | 172.17.243.219 | Bildschirm F1 | 3 | 172.17.243.219 | y | ✅ |
| e2-4 | Bildschirm Werbung F1 | 3 | Access | 172.17.243.220 | Bildschirm Werbung F1 | 3 | 172.17.243.220 | y | ✅ |
| e2-5 | Audio Amp. F1 | 9 | Access | 172.20.243.157 | Audio Amp. F1 | 9 | 172.20.243.157 | y | ✅ |

## Switch F2

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch F3 | All (except OBS Interc… | Trunk | - | Switch F3 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch E3 | All (except OBS Interc… | Trunk | - | Switch E3 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-4 | Access point F2 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP F2 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | reserved | - | - | - | Reserved | - | - | y | 🟡 reserved port enabled on default vlan |
| e1-0 | Überw. Kamera F8 | 5 | Access | 172.18.243.182 | Interior Camera F8 | 5 | 172.18.243.182 | y | ✅ |
| e1-1 | Überw. Kamera F4 | 5 | Access | 172.18.243.183 | Interior Camera F4 | 5 | 172.18.243.183 | y | ✅ |
| e1-2 | Überw. Kamera F3 | 5 | Access | 172.18.243.184 | Interior Camera F3 | 5 | 172.18.243.184 | y | ✅ |
| e1-3 | Überw. Kamera F6 | 5 | Access | 172.18.243.185 | Interior Camera F6 | 5 | 172.18.243.185 | y | ✅ |
| e1-4 | Überw. Kamera F10 | 5 | Access | 172.18.243.186 | Interior Camera F10 | 5 | 172.18.243.186 | y | ✅ |
| e1-5 | AFZ F3 | 8 | Access | 172.20.115.156 | AFZ F3 | 8 | 172.20.115.156 | y | ✅ |
| e1-6 | AFZ F4 | 8 | Access | 172.20.115.157 | AFZ F4 | 8 | 172.20.115.157 | y | ✅ |
| e1-7 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-8 | Sprechstelle F2 | 9 | Access | 172.20.243.146 | Sprechstelle F2 | 9 | 172.20.243.146 | y | ✅ |
| e1-9 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-10 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-11 | Bildschirm Werbung F2 | 3 | Access | 172.17.243.243 | Bildschirm Werbung F2 | 3 | 172.17.243.243 | y | ✅ |
| e1-12 | Future use box F2 | 90 | Access | - | Funksensor F2 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box F4 | 90 | Access | - | Funksensor F4 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | Seitenanzeige F2 | 3 | Access | 172.17.243.171 | Seitenanzeige F2 | 3 | 172.17.243.171 | y | ✅ |
| e1-15 | Seitenanzeige F4 | 3 | Access | 172.17.243.172 | Seitenanzeige F4 | 3 | 172.17.243.172 | y | ✅ |
| e2-0 | Bildschirm F4 | 3 | Access | 172.17.243.221 | Bildschirm F4 | 3 | 172.17.243.221 | y | ✅ |
| e2-1 | Bildschirm Werbung F8 | 3 | Access | 172.17.243.222 | Bildschirm Werbung F8 | 3 | 172.17.243.222 | y | ✅ |
| e2-2 | Bildschirm Werbung F6 | 3 | Access | 172.17.243.223 | Bildschirm Werbung F6 | 3 | 172.17.243.223 | y | ✅ |
| e2-3 | Bildschirm F2 | 3 | Access | 172.17.243.224 | Bildschirm F2 | 3 | 172.17.243.224 | y | ✅ |
| e2-4 | Bildschirm F6 | 3 | Access | 172.17.243.225 | Bildschirm F6 | 3 | 172.17.243.225 | y | ✅ |
| e2-5 | Audio Amp. F2 | 9 | Access | 172.20.243.158 | Audio Amp. F2 | 9 | 172.20.243.158 | y | ✅ |

## Switch F3

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch B2 | All (except OBS Interc… | Trunk | - | Switch B2 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch F2 | All (except OBS Interc… | Trunk | - | Switch F2 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-4 | Access point F3 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP F3 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | reserved | - | - | - | Reserved | - | - | n | ✅ unused/disabled |
| e1-0 | Rücksehkamera F1 | 5 | Access | 172.18.243.216 | Exterior Camera F1 | 5 | 172.18.243.216 | y | ✅ |
| e1-1 | Rücksehkamera F2 | 5 | Access | 172.18.243.217 | Exterior Camera F2 | 5 | 172.18.243.217 | y | ✅ |
| e1-2 | Access point F4 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP F4 | 100,10,20,30,31,131,150 | - | y | ✅ trunk |
| e1-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-4 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-5 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-6 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-7 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-8 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-9 | Sprechstelle F2R | 9 | Access | 172.20.243.146 | Sprechstelle F2R | 9 | 172.20.243.146 | y | ✅ |
| e1-10 | Sprechstelle F1R | 9 | Access | 172.20.243.145 | Sprechstelle F1R | 9 | 172.20.243.145 | y | ✅ |
| e1-11 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-12 | Future use box F1 | 90 | Access | - | Funksensor F1 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box F3 | 90 | Access | - | Funksensor F3 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-15 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-0 | Bildschirm Werbung F3 | 3 | Access | 172.17.243.244 | Bildschirm Werbung F3 | 3 | 172.17.243.244 | y | ✅ |
| e2-1 | Bildschirm Werbung F4 | 3 | Access | 172.17.243.245 | Bildschirm Werbung F4 | 3 | 172.17.243.245 | y | ✅ |
| e2-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-3 | Sitzplatzreservierung F | 6 | Access | 172.19.115.142 | Sitzplatzreservierung F | 6 | 172.19.115.142 | y | ✅ |
| e2-4 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-5 | - | - | - | - | - | - | - | n | ✅ unused/disabled |

## Switch B1

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch B3 | All (except OBS Interc… | Trunk | - | Switch B3 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch F1 | All (except OBS Interc… | Trunk | - | Switch F1 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | Frontkupplung B1 | 100, 2, 3, 5, 6, 7, 8,… | Trunk | - | Frontkupplung B1 | 5,15 | - | y | 🟠 v9 coupler containment (native-999, allow 5,15) — intentional deviation from IPA list |
| e0-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-4 | Access point B1 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP B1 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | Service FIS / CCTV | 2 | Access | 172.17.115.253 | Service FIS/CCTV | 2 | 172.17.115.253 | y | ✅ |
| e1-0 | Überw. Kamera B5 | 5 | Access | 172.18.243.190 | Interior Camera B5 | 5 | 172.18.243.190 | y | ✅ |
| e1-1 | Überw. Kamera B2 | 5 | Access | 172.18.243.188 | Interior Camera B2 | 5 | 172.18.243.188 | y | ✅ |
| e1-2 | Überw. Kamera B1 | 5 | Access | 172.18.243.189 | Interior Camera B1 | 5 | 172.18.243.189 | y | ✅ |
| e1-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-4 | Überw. Kamera B9 | 5 | Access | 172.18.243.191 | Interior Camera B9 | 5 | 172.18.243.191 | y | ✅ |
| e1-5 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-6 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-7 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-8 | Sprechstelle B1 | 9 | Access | 172.20.243.147 | Sprechstelle B1 | 9 | 172.20.243.147 | y | ✅ |
| e1-9 | Sprechstelle B3R | 9 | Access | 172.20.243.168 | Sprechstelle B3R | 9 | 172.20.243.168 | y | ✅ |
| e1-10 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-11 | ZFR R | 2 | Access | 172.17.115.130 | ZFR R | 2 | 172.17.115.130 | y | ✅ |
| e1-12 | Future use box B5 | 90 | Access | - | Funksensor E5 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box B6 | 90 | Access | - | Funksensor E6 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | Seitenanzeige B1 | 3 | Access | 172.17.243.173 | Seitenanzeige B1 | 3 | 172.17.243.173 | y | ✅ |
| e1-15 | Seitenanzeige B3 | 3 | Access | 172.17.243.174 | Seitenanzeige B3 | 3 | 172.17.243.174 | y | ✅ |
| e2-0 | Bildschirm B3 | 3 | Access | 172.17.243.226 | Bildschirm B3 | 3 | 172.17.243.226 | y | ✅ |
| e2-1 | Bildschirm Werbung B3 | 3 | Access | 172.17.243.227 | Bildschirm Werbung B3 | 3 | 172.17.243.227 | y | ✅ |
| e2-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-4 | ADU B | 9 | Access | 172.20.243.132 | ADU B | 9 | 172.20.243.132 | y | ✅ |
| e2-5 | Audio Amp. B1 | 9 | Access | 172.20.243.159 | Audio Amp. B1 | 9 | 172.20.243.159 | y | ✅ |

## Switch B2

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch B3 | All (except OBS Interc… | Trunk | - | Switch B3 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch F3 | All (except OBS Interc… | Trunk | - | Switch F3 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-4 | Access point B2 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP B2 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | reserved | - | - | - | Reserved | - | - | n | ✅ unused/disabled |
| e1-0 | Überw. Kamera B8 | 5 | Access | 172.18.243.192 | Interior Camera B8 | 5 | 172.18.243.192 | y | ✅ |
| e1-1 | Überw. Kamera B4 | 5 | Access | 172.18.243.193 | Interior Camera B4 | 5 | 172.18.243.193 | y | ✅ |
| e1-2 | Überw. Kamera B3 | 5 | Access | 172.18.243.194 | Interior Camera B3 | 5 | 172.18.243.194 | y | ✅ |
| e1-3 | Überw. Kamera B6 | 5 | Access | 172.18.243.195 | Interior Camera B6 | 5 | 172.18.243.195 | y | ✅ |
| e1-4 | Überw. Kamera B10 | 5 | Access | 172.18.243.196 | Interior Camera B10 | 5 | 172.18.243.196 | y | ✅ |
| e1-5 | AFZ B3 | 8 | Access | 172.20.115.160 | AFZ B3 | 8 | 172.20.115.160 | y | ✅ |
| e1-6 | AFZ B4 | 8 | Access | 172.20.115.161 | AFZ B4 | 8 | 172.20.115.161 | y | ✅ |
| e1-7 | NVR B | 5 | Access | 172.18.243.134 | NVR B | 5 | 172.18.243.134 | y | ✅ |
| e1-8 | Sprechstelle B2 | 9 | Access | 172.20.243.148 | Sprechstelle B2 | 9 | 172.20.243.148 | y | ✅ |
| e1-9 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-10 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-11 | Bildschirm B1 | 3 | Access | 172.17.243.246 | Bildschirm B1 | 3 | 172.17.243.246 | y | ✅ |
| e1-12 | Future use box B2 | 90 | Access | - | Funksensor B2 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box B4 | 90 | Access | - | Funksensor B4 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | Seitenanzeige B2 | 3 | Access | 172.17.243.175 | Seitenanzeige B2 | 3 | 172.17.243.175 | y | ✅ |
| e1-15 | Seitenanzeige B4 | 3 | Access | 172.17.243.176 | Seitenanzeige B4 | 3 | 172.17.243.176 | y | ✅ |
| e2-0 | Bildschirm B4 | 3 | Access | 172.17.243.230 | Bildschirm B4 | 3 | 172.17.243.230 | y | ✅ |
| e2-1 | Bildschirm Werbung B8 | 3 | Access | 172.17.243.231 | Bildschirm Werbung B8 | 3 | 172.17.243.231 | y | ✅ |
| e2-2 | Bildschirm Werbung B6 | 3 | Access | 172.17.243.232 | Bildschirm Werbung B6 | 3 | 172.17.243.232 | y | ✅ |
| e2-3 | Bildschirm Werbung B2 | 3 | Access | 172.17.243.233 | Bildschirm Werbung B2 | 3 | 172.17.243.233 | y | ✅ |
| e2-4 | Bildschirm Werbung B4 | 3 | Access | 172.17.243.234 | Bildschirm Werbung B4 | 3 | 172.17.243.234 | y | ✅ |
| e2-5 | Audio Amp. B2 | 9 | Access | 172.20.243.160 | Audio Amp. B2 | 9 | 172.20.243.160 | y | ✅ |

## Switch B3

| Port | IPA usage | IPA VLAN | Type | IPA IP | Template desc | Tpl VLAN(s) | Tpl IP | En | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| e0-0 | FIS Switch B1 | All (except OBS Interc… | Trunk | - | Switch B1 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-1 | FIS Switch B2 | All (except OBS Interc… | Trunk | - | Switch B2 | 1-1000 | - | y | ✅ trunk (all VLANs) |
| e0-2 | Frontkupplung B2 | 100, 2, 3, 5, 6, 7, 8,… | Trunk | - | Frontkupplung B3 | 5,15 | - | y | 🟠 v9 coupler containment (native-999, allow 5,15) — intentional deviation from IPA list |
| e0-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e0-4 | Access point B3 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP B3 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e0-5 | reserved | - | - | - | Reserved | - | - | n | ✅ unused/disabled |
| e1-0 | Rücksehkamera B1 | 5 | Access | 172.18.243.218 | Exterior Camera B1 | 5 | 172.18.243.218 | y | ✅ |
| e1-1 | Rücksehkamera B2 | 5 | Access | 172.18.243.219 | Exterior Camera B2 | 5 | 172.18.243.219 | y | ✅ |
| e1-2 | Access point B4 | 100, 10, 20, 30, 31, 1… | Trunk | - | AP B4 | 100,10,20,30,31,131,15… | - | y | ✅ trunk |
| e1-3 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-4 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-5 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-6 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-7 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e1-8 | Sprechstelle B3 | 9 | Access | 172.20.243.168 | Sprechstelle B3 | 9 | 172.20.243.168 | y | ✅ |
| e1-9 | Sprechstelle B2R | 9 | Access | 172.20.243.148 | Sprechstelle B2R | 9 | 172.20.243.148 | y | ✅ |
| e1-10 | Sprechstelle B1R | 9 | Access | 172.20.243.147 | Sprechstelle B1R | 9 | 172.20.243.147 | y | ✅ |
| e1-11 | ZFR | 2 | Access | 172.17.115.130 | ZFR | 2 | 172.17.115.130 | y | ✅ |
| e1-12 | Future use box B1 | 90 | Access | - | Funksensor B1 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-13 | Future use box B3 | 90 | Access | - | Funksensor B3 | 90 | - | n | 🟡 future-use: cfg present, disabled (intentional) |
| e1-14 | Frontanzeige B | 3 | Access | 172.17.243.152 | Frontanzeige B | 3 | 172.17.243.152 | y | ✅ |
| e1-15 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-0 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-1 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-2 | - | - | - | - | - | - | - | n | ✅ unused/disabled |
| e2-3 | Sitzplatzreservierung B | 6 | Access | 172.19.115.143 | Sitzplatzreservierung B | 6 | 172.19.115.143 | y | ✅ |
| e2-4 | ADU BR | 9 | Access | 172.20.243.132 | ADU BR | 9 | 172.20.243.132 | y | ✅ |
| e2-5 | Service VLAN PWLAN | 100, 10, 20, 30, 31, 1… | Trunk | - | Service VLAN PWLAN | 100,10,20,30,31,131,150 | - | n | 🟡 service socket disabled by fleet convention (matches nv6) |
