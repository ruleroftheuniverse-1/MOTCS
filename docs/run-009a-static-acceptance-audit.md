# Track P Run 009A static-force acceptance audit

`PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY`

Run 009A audits the saved Run 009 rate-equation grids and performs additional
static diagnostic calls. It adds no Hamiltonian term, beam physics, trajectory,
capture criterion, source distribution, recoil model, or optimizer. Exact
Track E remains blocked.

## Coordinate convention

Every audited map is `F_x(x,v_x)` in the lab frame. Positions are passed as
`[x,0,0]`, velocities as `[v_x,0,0]`, and component zero of the returned force
is recorded. The `x'` and `y'` beams have lab-x wave-vector projections of
magnitude `1/sqrt(2)`; the z beams have zero lab-x projection. Thus the Doppler
shift contains the required 45-degree projection and the maps are not z-axis
maps inherited from the early convention notebook.

## Population-solver audit

The full saved 17 by 17 grid for all seven Run 009 cases was re-evaluated with
solver diagnostics, for 2023 points total. At every point the audit checks
finite populations and forces, nonnegative populations to numerical tolerance,
unit population sum, the infinity norm of `R N`, SVD nullspace dimension, and
whether a fallback was used. The installed `pylcp 1.0.2` implementation uses an
SVD-nullspace solve and has no separate singular-solver fallback in this path.

The audit also repeats representative points with `svd_eps` values `1e-9`,
`1e-10`, and `1e-11`. These tolerance changes do not change the reported force
or populations at the audit tolerance.

## Acceptance checks

The audit compares `[3]` and `[3+1]`, evaluates the real-backend polarization
and gradient reversal matrix, scans the Gaussian chirp force over positive lab-x
velocity, checks manual plane-wave/Gaussian phase-space points, converts useful
force scales to acceleration without integrating them, and refines selected
lab-x position and velocity slices by a factor of two.

The chirp scan uses the rough geometric guide

```text
v_feature = sqrt(2) * |Delta| / k
```

only as a qualitative acceptance diagnostic. It is not a fit or a Rodriguez
replication claim.

## Gate result: NO-GO

The numerical solver, lab-x geometry, chirp-feature motion, Gaussian
application, force scale, and slice convergence pass their provisional audit
conditions. The trajectory gate nevertheless remains closed because:

- the nominal local force is damping but anti-restoring;
- flipping either polarization or gradient produces restoring behavior, while
  flipping both returns the nominal anti-restoring sign;
- component (4) increases the magnitude of the anti-restoring slope rather
  than strengthening restoring confinement.

These observations point to a polarization/component or magnetic-gradient
convention mismatch in the provisional wiring, or to topology distortion from
the collapsed backend. Run 009A does not choose or apply a correction.
Trajectories remain disconnected until a later static audit returns `GO`.
