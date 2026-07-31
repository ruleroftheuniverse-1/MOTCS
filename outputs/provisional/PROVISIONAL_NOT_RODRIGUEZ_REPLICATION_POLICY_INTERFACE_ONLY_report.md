# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLICY_INTERFACE_ONLY report

This is pure control-schedule plumbing for Track P.

This is not an MgF/Rodriguez reproduction.
Track E exact MgF force readiness remains blocked.
No trajectory integration, capture velocity calculation, Gaussian beam model, optimizer, or exact force-map path is used.
No physical conclusions should be drawn from these policy samples.

## Component order

`(1, 2, 3, 4)`

## Samples

```text
rodriguez_static_3                 | t=        0s | c1: detuning=    -1 Gamma s= 1.45 active | c2: detuning=    -1 Gamma s= 1.45 active | c3: detuning=    -1 Gamma s= 2.89 active | c4: detuning=     2 Gamma s=    0 off reason=zero_or_disabled
rodriguez_static_3_plus_1          | t=        0s | c1: detuning=    -1 Gamma s= 1.45 active | c2: detuning=    -1 Gamma s= 1.45 active | c3: detuning=    -1 Gamma s= 2.17 active | c4: detuning=     2 Gamma s= 0.72 active
rodriguez_baseline_linear_chirp    | t=        0s | c1: detuning=    -8 Gamma s= 1.45 active | c2: detuning=    -8 Gamma s= 1.45 active | c3: detuning=    -8 Gamma s= 2.89 active | c4: detuning=     2 Gamma s=    0 off reason=parked_off_until_3_plus_1_handoff
rodriguez_baseline_linear_chirp    | t=   0.0005s | c1: detuning=  -4.5 Gamma s= 1.45 active | c2: detuning=  -4.5 Gamma s= 1.45 active | c3: detuning=  -4.5 Gamma s= 2.89 active | c4: detuning=     2 Gamma s=    0 off reason=parked_off_until_3_plus_1_handoff
rodriguez_baseline_linear_chirp    | t=    0.001s | c1: detuning=    -1 Gamma s= 1.45 active | c2: detuning=    -1 Gamma s= 1.45 active | c3: detuning=    -1 Gamma s= 2.89 active | c4: detuning=     2 Gamma s=    0 off reason=parked_off_until_3_plus_1_handoff
rodriguez_baseline_linear_chirp    | t=   0.0015s | c1: detuning=    -1 Gamma s= 1.45 active | c2: detuning=    -1 Gamma s= 1.45 active | c3: detuning=    -1 Gamma s= 2.89 active | c4: detuning=     2 Gamma s=    0 off reason=parked_off_until_3_plus_1_handoff
```

Metadata: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLICY_INTERFACE_ONLY_metadata.json`