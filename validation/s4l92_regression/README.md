# Stock GOLIAT on licensed Sim4Life 9.2 (Windows, RTX A6000), 2026-11-04

GOLIAT ran from the working tree without changes or shims. Sim4Life 9.2 raised no unknown-attribute errors. The configs are the
shipped defaults with shorter loops (`val92_nf.json`, `val92_ff.json`). The studies ran headless through
`NearFieldStudy`/`FarFieldStudy.run()`. The `goliat study` command was not used, because it waits for an interactive first-run prompt when
started from a Windows service session.

| study | case | result | reference |
|---|---|---|---|
| far field | Duke, 700 MHz, x_pos, theta | WB-SAR 5.452e-6 W/kg, psSAR10g 1.609e-4 W/kg | published campaign record (Dataverse, `revision/padding_audit/ff_zip`): 5.470e-6 (−0.3 %), 1.581e-4 (+1.7 %) |
| near field | Thelonious, 3.5 GHz IFA, front_of_eyes centre vertical | psSAR10g 2.43e-4, psSAR1g 6.18e-4 W/kg at P_in 2.47 mW, power balance 99.6 % | no reference value, so this run only shows that the study completes |

- The kernel was Acceleware (the default), at about 3.8 GCells/s. The near-field run took 23 min (iSolve 944 s, SAR extraction 349 s).
  The far-field run took 4 min.
- The far-field power balance is 167 % (168 % in the campaign record). The far-field "input power" is
  S_inc × the bounding-box cross-section, which is not a conserved quantity. Therefore, the far-field power balance is not a quality check.
