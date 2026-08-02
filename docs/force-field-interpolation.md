# PROVISIONAL NOT_RODRIGUEZ_REPLICATION FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY

Run 010 turns the Run 009D-accepted equilibrium rate-equation backend into reusable force tables. It does not integrate a trajectory, calculate capture velocity, classify loading, use a source distribution, add diffusion, optimize parameters, or make an exact Rodriguez/MgF claim.

## Immutable accepted backend

`build_accepted_provisional_rateeq_backend(explicit_provisional_opt_in=True)` is the only factory used by this path. It requires:

- Track P and explicit provisional opt-in;
- `GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED`;
- `ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001`;
- `ExcitedHyperfineModel.SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING`;
- `SourceAlignedSplittingCase.MID_RANGE_0P5_MHZ`.

The `0.5 MHz` splitting is a deterministic midpoint of the source-supported `0 <= splitting < 1 MHz` interval, not a measured central value. The independent Doppelbauer `d` operator, its `J'=3/2` mixing, and exact positive-parity spectroscopy remain unresolved. `replication_valid` is false and Track E remains blocked. The accepted factory does not expose the collapsed excited Zeeman tensor or collapsed `55.33 MHz` splitting as choices.

## Separate fields

The pre-handoff field is

```text
F_pre(x, v_x, Delta) / (hbar k Gamma)
```

for the elliptical-Gaussian `[3]` system. Components `(1,2,3)` have saturations `(1.45,1.45,2.89)`, share detuning `-8 <= Delta/Gamma <= -1`, and component 4 is explicitly parked with zero saturation.

The post-handoff field is

```text
F_post(x, v_x) / (hbar k Gamma)
```

for the distinct elliptical-Gaussian `[3+1]` system with detunings `(-1,-1,-1,+2) Gamma` and saturations `(1.45,1.45,2.17,0.72)`. The fields are never blended. The handoff selector uses pre for `t < tau` and post for `t >= tau`.

Normalized force is canonical in both caches. The `hbar*k*Gamma/m` acceleration conversion remains available separately through `force_units.py` and is not baked into either table.

## Domain and grids

The config-backed domain is:

- `-60 mm <= x <= +60 mm`, covering the named `x0=-50 mm` with margins;
- `-100 m/s <= v_x <= +100 m/s`, covering inbound and outbound motion beyond the named `2-9 Gamma/k` range;
- exactly `-8 <= Delta/Gamma <= -1` for the pre-handoff field.

The final tables use `(25,33,15)` pre-handoff nodes and `(25,33)` post-handoff nodes: 13,200 equilibrium solves total. Position and velocity spacings balance build cost against direct holdout and refined-slice accuracy. Metadata also stores `x/(hbar Gamma/(mu_B B'))`, `v/(Gamma/k)`, and `Delta/Gamma` coordinates.

The initial `(25,33,8)` baseline used 1-Gamma detuning spacing. Although its global holdout RMS was only `0.28%` of the total force range, it underestimated the dynamically important `-4.5 Gamma` slowing extremum by about `16%` of the range. This exceeded the predeclared `8%` important-region limit. The detuning grid was refined to `0.5 Gamma` spacing without changing thresholds.

## Interpolation and boundaries

`InterpolatedForceField` uses trilinear interpolation for pre-handoff and bilinear interpolation for post-handoff. Exactly-on-boundary and just-inside queries are supported. Any position, velocity, or detuning outside the stored domain raises `ForceFieldDomainError`; it is never silently clamped or extrapolated.

`SeparatedHandoffForceFields` keeps the optical systems distinct and applies the exact `t < tau` / `t >= tau` boundary. It does not smooth across the policy discontinuity.

## Validation

Acceptance limits were declared in `configs/provisional_force_field_run_010.yaml` before the final refined build:

- normalized RMS error / total force range `<= 0.03`;
- maximum important-region error / range `<= 0.08`;
- local-slope relative error `<= 0.15`;
- extremum displacement `<= 1.5` grid cells.

Validation includes structured off-node midpoints, deterministic pseudorandom holdouts, near-boundary points, origin and Gaussian-edge points, between-plane detunings, and slowing-extremum probes. Refined direct slices contain 121 position and 161 velocity points. The audit compares restoring/damping slopes, extrema and positions, representative zero crossings and branch counts, chirp-feature ordering, Gaussian attenuation, and the component-4 confinement increment. Relative errors are reported only above a documented force floor.

Run 010 final refined results:

- holdout RMS/range: approximately `0.48%`;
- holdout maximum/range: approximately `2.04%`;
- slowing-extremum errors/range: approximately `2.2%` to `6.2%`;
- post-handoff restoring and damping signs preserved;
- chirp-feature ordering and zero-crossing branch counts preserved;
- Gaussian attenuation and stronger `[3+1]` confinement verified;
- all population solves healthy;
- all outside-domain diagnostics rejected.

Final gate: **`PROVISIONAL_FORCE_FIELD_INTERPOLATION_GO`**. This authorizes connecting these accepted tables to the existing named, non-capture trajectory scaffold. Capture thresholds, source distributions, stochastic diffusion, optimization, and exact-replication claims remain unauthorized.

## Cache safety

Caches live under `outputs/provisional/force_fields/` as compressed NPZ plus JSON. Each metadata file contains the warning label, creation timestamp, normalized-force declaration, shapes, coordinate scales, source hashes, complete backend/optical provenance, interpolation method, cache key, NPZ hash, and validation results.

Loading requires an exact provenance cache-key match and an exact NPZ content hash. A mismatch raises `ForceFieldCacheMismatchError`; the Run 010 script refuses reuse and performs an explicit rebuild.
