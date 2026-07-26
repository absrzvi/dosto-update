#!/bin/bash
# Vign/Vin ignition + supply logger for ADLINK R5001C CMM (I2C 0x2D, bus 2).
# Read-only against the CMM. Change-only logging + heartbeat.
# Distinguishes ignition-input drop (Vign collapses, Vin holds) from
# supply removal (both collapse) at the moment of a power-down.
# 2026-06-18: HB tightened 300->30; added inlet/outlet temperature (0x03) to
# capture a thermal-cause shutdown (CMM inlet thresh default 70C / outlet 85C).
LOG=/data/ignition-log/vign.csv
BUS=2; ADDR=0x2d
INTERVAL=10           # seconds between samples. HISTORY: 3s(orig) -> 2s(2026-07-24, pre-cut capture)
                      # -> 10s(2026-07-27). The 2s rate wedged the CMM I2C bus on box1-t1/4736-105
                      # (2026-07-25 11:51): escalating partial reads over ~3h then total bus lockup
                      # (i2ctransfer timeout). Control: 110 ran 5.5 weeks at 30s with 3 glitches total;
                      # 105 at 2s hit 24 glitches in 27h then hung. Over-polling the CMM MCU is the
                      # suspected cause. 10s is well within the proven-safe envelope and still gives a
                      # last-sample <=10s before any cut (ample for the power/hard-cut argument, which
                      # rests on the GAP + missing shutdown marker, not sub-10s voltage resolution).
HB=30                # heartbeat: force a line every 30s even without a change (matches the 30s that
                      # ran glitch-free for weeks; a hard cut is proven by the gap, not by HB tightness)
DV_THRESH=2.0        # log if Vin or Vign moves more than this many volts
DT_THRESH=2.0        # log if inlet or outlet temp moves more than this many degC
MAXBYTES=$((50*1024*1024))   # self-cap log at 50MB

mkdir -p "$(dirname "$LOG")"
if [ ! -f "$LOG" ]; then
  echo "iso_utc,vin_v,vign_v,vign_pct_of_vin,v12_v,v5stb_v,curr_a,inlet_c,outlet_c,bp_mode,status1_faults,reason" > "$LOG"
fi

prev_vin=""; prev_vign=""; prev_mode=""; prev_s1=""; prev_inlet=""; prev_outlet=""; last_hb=0

decode() {  # $1=MSB $2=LSB -> volts (raw/100), prints with 2 decimals
  awk "BEGIN{printf \"%.2f\", (($1*256)+$2)/100.0}"
}

dtemp() {  # $1=MSB $2=LSB -> degC, 16-bit signed 2's complement /10
  awk "BEGIN{v=($1*256)+$2; if(v>=32768)v-=65536; printf \"%.1f\", v/10.0}"
}

while true; do
  now=$(date -u +%s)
  iso=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  # 0x04 -> 12V,5VSTB,Vin,Vign (9 bytes incl PEC)
  V=$(i2ctransfer -y $BUS w1@$ADDR 0x04 r9 2>/dev/null)
  S=$(i2ctransfer -y $BUS w1@$ADDR 0x01 r3 2>/dev/null)
  C=$(i2ctransfer -y $BUS w1@$ADDR 0x05 r3 2>/dev/null)
  # 0x03 -> inlet MSB,LSB, outlet MSB,LSB, heatsink MSB,LSB, PEC (7 bytes)
  T=$(i2ctransfer -y $BUS w1@$ADDR 0x03 r7 2>/dev/null)
  if [ -z "$V" ] || [ -z "$S" ]; then sleep $INTERVAL; continue; fi
  read -r b0 b1 b2 b3 b4 b5 b6 b7 b8 <<< "$V"
  read -r s1 s2 s2pec <<< "$S"
  read -r cm cl cpec <<< "$C"
  # Guard against partial/malformed I2C reads: every byte we will do arithmetic on
  # must be present and a valid hex byte (0xNN). One bad/short read otherwise turned
  # an awk program into "if(>0)" -> "awk: line 1: syntax error", which killed the
  # logger until next reboot and wrote a corrupt row (2026-07-25 on box1-t1). If any
  # required byte is missing/non-hex, skip this sample rather than crash or log garbage.
  hexok() { case "$1" in 0x[0-9a-fA-F][0-9a-fA-F]) return 0;; *) return 1;; esac; }
  bad=0
  for byte in "$b0" "$b1" "$b2" "$b3" "$b4" "$b5" "$b6" "$b7" "$s1" "$s2" "$cm" "$cl"; do
    hexok "$byte" || { bad=1; break; }
  done
  if [ "$bad" = 1 ]; then sleep $INTERVAL; continue; fi
  v12=$(decode $((b0)) $((b1)))
  v5=$(decode $((b2)) $((b3)))
  vin=$(decode $((b4)) $((b5)))
  vign=$(decode $((b6)) $((b7)))
  curr=$(awk "BEGIN{printf \"%.2f\", ((($cm)*256)+($cl))/100.0}")
  # temperature (graceful if 0x03 read failed -> NA, no crash)
  if [ -n "$T" ]; then
    read -r t0 t1 t2 t3 t4 t5 t6 <<< "$T"
    inlet=$(dtemp $((t0)) $((t1)))
    outlet=$(dtemp $((t2)) $((t3)))
  else
    inlet="NA"; outlet="NA"
  fi
  # pass vin/vign as awk -v vars (not string-interpolated) so an empty value can never
  # malform the program; awk treats an empty numeric var as 0 and we fall to NA.
  pct=$(awk -v vin="$vin" -v vign="$vign" "BEGIN{ if(vin+0>0) printf \"%.1f\", (vign+0)/(vin+0)*100; else print \"NA\"}")
  modebits=$(( ( $((s2)) >> 6) & 3 ))
  case $modebits in
    0) mode="BP_OFF/ign";; 1) mode="IGN_mode";; 2) mode="MANUAL_on";; 3) mode="reserved";; esac
  s1faults=$(printf "0x%02x" $((s1)))

  reason=""
  if [ -z "$prev_vin" ]; then reason="start"; fi
  if [ -n "$prev_vin" ]; then
    dv=$(awk -v vin="$vin" -v pvin="$prev_vin" -v vign="$vign" -v pvign="$prev_vign" -v th="$DV_THRESH" "BEGIN{d=(vin+0)-(pvin+0); if(d<0)d=-d; g=(vign+0)-(pvign+0); if(g<0)g=-g; print (d>th||g>th)?1:0}")
    [ "$dv" = "1" ] && reason="delta"
    # temperature delta (only when both prev and current are numeric)
    if [ "$inlet" != "NA" ] && [ "$prev_inlet" != "NA" ] && [ -n "$prev_inlet" ]; then
      dt=$(awk "BEGIN{a=$inlet-$prev_inlet; if(a<0)a=-a; b=$outlet-$prev_outlet; if(b<0)b=-b; print (a>$DT_THRESH||b>$DT_THRESH)?1:0}")
      [ "$dt" = "1" ] && reason="${reason:+$reason+}tempchg"
    fi
    [ "$mode" != "$prev_mode" ] && reason="${reason}+modechg"
    [ "$s1faults" != "$prev_s1" ] && reason="${reason}+faultchg"
  fi
  if [ $((now-last_hb)) -ge $HB ] && [ -z "$reason" ]; then reason="hb"; fi

  if [ -n "$reason" ]; then
    # size guard
    sz=$(stat -c%s "$LOG" 2>/dev/null || echo 0)
    if [ "$sz" -lt "$MAXBYTES" ]; then
      echo "$iso,$vin,$vign,$pct,$v12,$v5,$curr,$inlet,$outlet,$mode,$s1faults,$reason" >> "$LOG"
    fi
    last_hb=$now
    prev_vin=$vin; prev_vign=$vign; prev_mode=$mode; prev_s1=$s1faults
    prev_inlet=$inlet; prev_outlet=$outlet
  fi
  sleep $INTERVAL
done
