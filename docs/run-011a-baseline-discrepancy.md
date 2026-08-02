# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY

Run 011A is a read-only audit of why the accepted provisional Track P model does not reproduce the Rodriguez baseline 7.5 Gamma/k trajectory. It does not authorize capture calculations or change any physics input.

The executable audit is [analyze_run_011_baseline_discrepancy.py](../scripts/analyze_run_011_baseline_discrepancy.py). It reads the Run 010 tables and Run 011 arrays, records SHA-256 hashes before and after analysis, and fails if a protected artifact changes. It does not call a trajectory integrator, force-field builder, domain extension, outcome reclassifier, or threshold search. Fresh pylcp solves are restricted to the selected-transition convention check and deterministic saved states on the 7.5 Gamma/k path.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Findings

The source-to-code ledger matches the initial state, direction, chirp endpoints and duration, handoff, saturation vectors, component-4 behavior, field gradient, beam axes, and Gaussian radii. The paper does not state the numerical duration or terminal criterion used for Fig. 4(a), so those remain ambiguous. The 1 W statement stays metadata-only; the reported peak saturation vector is the operative optical strength.

The installed pylcp pumping-rate expression matches Rodriguez Eqs. (3)-(4):

```text
Omega/Gamma = (d.epsilon) sqrt(2s) / 2
R/Gamma = (s/2) |d.epsilon|^2 / (1 + 4 delta^2)
```

Saturation is applied once per physical beam and component. Six beams are represented explicitly. Dipole strength is applied once. Gamma is an angular decay rate and detunings are normalized by that same Gamma. The optical carrier is a rotating-frame coordinate; the common 834.3 THz offset is not numerically constructed. Components 3 and 4 use the mean upper-F=1/F=2 ground energy. Addressed F'=1 transitions receive the requested detuning; the retained F'=0 state differs by the accepted 0.5 MHz interval-midpoint splitting, about 0.023923 Gamma.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Diagnosis

At about 0.4 ms the saved 7.5 Gamma/k molecule is well matched to the cached slowing extremum in velocity, but is still near x=-27 mm. The accepted cache's major negative-force region has an exp(-2)-level spatial half-extent of roughly 15-20 mm, materially below the paper's rough sqrt(2)wxy value of about 25 mm. The molecule therefore receives too little early negative impulse, falls behind the descending velocity feature, crosses the center near the handoff, and samples an accelerating lobe. Its positive reconstructed impulse exceeds its negative reconstructed impulse and it exits slightly faster than it entered.

The 9 Gamma/k path receives more net slowing because it reaches and crosses the center before the handoff while the moving pre-handoff negative feature remains available. The 6 and 7.5 Gamma/k paths cross at or after the handoff and receive strong cancellation. The 2 and 4 Gamma/k paths receive enough negative impulse on x<0 to lose nearly all incoming momentum before reaching the origin; the saved 20 ms interval ends with small positive velocities and no center crossing.

The narrower force region and post-handoff cancellation are demonstrated. Their most likely common origin is a provisional Hamiltonian force-shape difference: the accepted cache also reaches about 0.06-0.07 hbar*k*Gamma, roughly twice the paper's approximate 0.03 scale. Because Fig. 3 has not been digitized and the exact excited-state model remains blocked, no corrective physics change is justified by this audit alone.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Gate

`BASELINE_DISCREPANCY_NARROWED`

`capture_authorized = false`; `capture_velocity_authorized = false`; `optimizer_authorized = false`; `exact_replication_valid = false`; Track E remains blocked.

