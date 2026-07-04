# DOSTO NEU release takeover + CAT/FV pilot — status (updated end of 2026-07-03 session)

Goal: own the DOSTO NEU build/publish/deploy end-to-end, unblock CAT/FV (fv5/fv6) with box=Fzg + v9 + switch fw 7.4.8, and fix the FV5 NMS template.

## THE FULL PIPELINE — Abbas now owns ALL of it (access to git-nc + vmrepo01 + vmpuppet01)
```
1 edit → 2 version → 3 git push → 4 build .deb → 5 publish vmrepo01 →
6 pin Puppet env (migration_mar5) → 7 DEPLOY to master (nd-update-puppetenv.sh) →
8 factory up CCU → 9 hand-roll bug-10 → 10 obn update c → 11 NMS recreate
```
Steps 1–7 DONE for fv5/fv6. nd-obn pinned to **2.3.6** (not 2.3.14 — that's unpublished, MR onboard/obn!63 pending R&D). Templates **0.0.18** published to unstable. Puppet pin deployed to master (8cc76f1), CCU box1-t19 confirmed Remote=8cc76f1.

## ⛔ THE BIG BLOCKER DISCOVERED 2026-07-03: box=Fzg impossible for CAT/6-car/FV
`factory up` train-ID field caps 0–127 (= 3rd IP octet). Fzg: 4736=129-148, 4706=189-191, 4705=229-231 — ALL exceed 127. **box=Fzg ONLY works for 4734 (Fzg 1-90).** Entered 231 → rejected. Recovered by entering box-id 41 on t41 (stays 10.179.41.1, no re-IP). See memory [[project_box_fzg_breaks_127_octet_limit]].
- Consequence: the v9 templates (0.0.18, remap dropped) render WRONG hostnames on a box-id CAT train (train_id=41 → `fv5-A1-v8-41` not `-231`). **Do NOT `obn update c` a CAT train yet.**
- Needs R&D DECISION: fzg_id-key path for 6-car/CAT/FV (keep box-id≠Fzg), OR only 4734 does box=Fzg.

## Where the 3 CAT trains stand
- box1-t41 (4705-103, Fzg231): factory-up'd with train-id 41 (box-id), on nd-obn 2.2.23 still (pin/2.3.6 not applied to it yet — it re-pulled but shows 2.2.23; verify). Cert was cleared via dbc12/9494 during factory-up.
- t42 (4705-101), t43 (4705-102): dropping off cellular, not done.

## FV5 NMS TEMPLATE (in progress — NOT finished)
- Draft: `findings/coupling_test_4736-110_119_2026-06-12/NMS_fv5_template_2026-07-03.json`
- CORRECT now: 5 coaches A/C/E/F/B (coach 1-5), CCU in coach C cabled to C1+C3, 3 SW + 4 AP each, zabbix/proxy/puppet → fv5, url .ovh2.
- STILL WRONG per engineer: the `trainConsistView` inter-switch WIRING (connection lines). Needs careful redo from the authoritative topology.
- How NMS matches devices: by coach+device# (Zabbix host `%d_%d_R<coach>_<type><dev>`), NOT trainLayout IP. See [[project_nms_traintype_template_config]] + [[project_fv5_topology_reference]].
- FV5 _id in NMS: 68f7a91435907e00012370d0. NV4 reference _id: 6a27165fb29b630001793fb2.
- Topology sources: 4705-103 IPA PDF (pdfplumber TEXT — no poppler for render) + fv5_topology_t41.yaml (saved). Raw cfg e0-0/e0-1 descriptions are ASYMMETRIC — don't trust them.

## Deploy mechanics (proven this session)
- Publish deb: scp admin21net@vmrepo01:/tmp/ (from Git-Bash NOT WSL — VPN) + `sudo nd-registerpkg-bookworm.sh <deb>` → unstable.
- Deploy env: `ssh admin21net@vmpuppet01 → cd .../dostoneu_migration_mar5 && sudo nd-update-puppetenv.sh migration_mar5`. Master does NOT auto-sync.
- Cert clear on re-IP: `curl -X DELETE http://192.168.66.14:9494/cert?fqdn=<fqdn>` (or dbc12 -c).

## MRs / artifacts
- fv5/fv6 template master @ 0.0.18 (v9+box=Fzg+fw7.4.8) + PUBLISHING.md
- OBN engine MR onboard/obn!63 (2.3.14) — R&D merge pending (not blocking, pinned 2.3.6)
- Puppet pin ON migration_mar5 (8cc76f1), deployed to master
- built debs: WSL ~/dosto-debs/ (also in vmrepo pool)

## RESUME (new session)
1. FINISH the FV5 NMS template wiring (the connection lines) — from IPA PDF/topology, engineer to verify render.
2. Resolve box=Fzg-vs-127 for CAT: R&D decision on fzg_id-key. Until then, CAT trains commissioned with box-id (no obn update c with the remap-dropped templates).
3. Get t42/t43 online, complete their factory-up (box-id, not Fzg).
4. When onboard/obn!63 merges → 2.3.14 publishes → decide fzg strategy before bumping pin.

Key memories: [[project_box_fzg_breaks_127_octet_limit]] [[project_nms_traintype_template_config]] [[project_fv5_topology_reference]] [[project_puppet_deploy_chain_vmpuppet01]] [[project_obn_deb_publish_process]] [[project_fv5_report_working_recipe_validated]]
