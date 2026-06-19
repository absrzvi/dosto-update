DOSTO NEU NV2 SWITCH/AP CONFIG (2-coach bench, OEBB-251)
- 0.0.1 initial: 6 switches (A1/A2/A3 coach1, B1/B2/B3 coach2) based on field-tested
  2t-bench-v4 cfgs; hostname -> nv2-<pos>-v8-{{train_id}}; CCU on A1.e0-3 (OBS trunk);
  firewall on A3.e1-4; inter-coach A1.e0-1<->B1.e0-1. Pairs with report_dosto_neu.py
  nv2 patch (ccu1_coach=1,max_coach=2) + per-node hiera train_type: nv2.
