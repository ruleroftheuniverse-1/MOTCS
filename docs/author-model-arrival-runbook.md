# Author-model arrival runbook

## Intake

1. Preserve every received file unchanged and retain source/receipt metadata outside the package.
2. Calculate SHA-256 hashes before conversion.
3. Run `scripts/intake_molecular_model_package.py` to copy the package into a hash-named quarantine.
4. Never overwrite the accepted Track P package.
5. If files are incomplete, ambiguous, or damaged, stop and record the exact problem; do not repair silently.

## Conversion

6. Identify the source format, units, tensor axes, basis order, and spherical-component convention.
7. Convert to `mgf-mot-molecular-model-v1` only through a reviewed conversion script.
8. Record every mapping, permutation, phase convention, unit conversion, and derived field.
9. Preserve original arrays and labels adjacent to, but distinct from, the converted package.
10. Missing units, axes, basis order, or mandatory arrays are hard failures. Ask the authors rather than infer them.

## Validation

11. Run schema and mandatory-field validation.
12. Check dimensions, finiteness, Hermiticity, and eigensystem consistency.
13. Check dipole/branching sum rules.
14. Check weak-field magnetic slopes and Hamiltonian sign conventions.
15. Compare basis permutations, phase rephasings, and allowed degenerate rotations using Run 012 equivalence rules.
16. Compare with the accepted provisional package and classify identical, representation-equivalent, or physically different content.

Ambiguous phase/basis metadata blocks benchmarking. A valid but physically different package proceeds as a candidate import; it does not become accepted. A malformed package remains quarantined with a failed intake record.

## Static benchmark

17. After explicit benchmark authorization, run compact Figure 2 plane-wave comparisons.
18. Run compact Figure 3 finite-beam comparisons.
19. Test the component `(4)` `F=2` trapping / upper-`F=1` anti-trapping hierarchy.
20. Compare digitized paper topology and spatial/velocity widths with uncertainty.
21. Classify agreement without tuning undocumented constants.

The default intake command does not run this benchmark. If the package cannot reproduce source-level structure, retain it as an intake candidate and request clarification.

## Authorization and promotion

22. Never replace the accepted model automatically.
23. Issue a separate, manually reviewed scientific benchmark gate.
24. Rebuild force fields only after explicit authorization and a cache invalidation plan.
25. Rerun trajectories only after new force-field validation.
26. Leave capture, physical policy comparison, optimization, and hardware claims locked until their own later gates.

A future `mgf-mot-model-promotion-record-v1` record must cite the valid package, successful paper benchmark, explicit review, new accepted hash, and downstream invalidation plan. Run 018 sets `automatic_model_promotion_authorized=false` and provides no promotion command.
