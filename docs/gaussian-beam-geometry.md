# Track P elliptical-Gaussian beam geometry

Run 007 adds the finite transverse intensity envelopes stated by Rodriguez et
al. This remains provisional geometry and force-plumbing validation, not an
exact force calculation or capture protocol.

Every Run 007 artifact is stamped:

- `PROVISIONAL`
- `NOT_RODRIGUEZ_REPLICATION`
- `GAUSSIAN_GEOMETRY_VALIDATION_ONLY`

## Coordinate frames

The six propagation directions are `+/-x'`, `+/-y'`, and `+/-z`. The rotated
axes are

`x' = (x + y)/sqrt(2)` and `y' = (-x + y)/sqrt(2)`.

Lab `x` is the later molecular propagation axis. Each beam stores a normalized
propagation vector `k` and normalized transverse axes `u` and `v`. Frames use
the consistent right-handed convention

`u cross v = k`.

For beams in the MOT `x-y` plane, `u` is the in-plane direction perpendicular
to `k` and `v` is lab `z`. For `+z`, `u` is lab `x` and `v` is lab `y`; the
`-z` partner reverses `u` to preserve handedness. Axis-sign changes do not
change the squared-coordinate envelope, so counterpropagating partners have
identical spatial profiles.

## Radius and intensity convention

The source radii are:

- `wxy = 17.5 mm`;
- `wz = 10 mm`.

They are interpreted as `1/e^2` intensity radii. For displacement from the
beam center, with transverse coordinates `u_coord` and `v_coord`,

`I(r)/I0 = exp[-2 (u_coord^2/wu^2 + v_coord^2/wv^2)]`.

The envelope is one at the center and `exp(-2)` at one corresponding radius.
It is independent of displacement along the propagation direction. No
Rayleigh-range, longitudinal diffraction, waist evolution, or wavefront model
is included because this step has no paper-supported input for one.

For in-plane beams, `wu = wxy` and `wv = wz`, with `v` along lab `z`. For the
`z` pair, the `wxy` axis is lab `+/-x` and the `wz` axis is lab `y`.

## Peak saturation and total power

The reported peak saturation vectors are stored explicitly:

- `[3]`: `(1.45, 1.45, 2.89, 0.00)`;
- `[3+1]`: `(1.45, 1.45, 2.17, 0.72)`.

The operative frozen policy vector is attached to every beam and used directly.
Component activity, detuning, and polarization logic are unchanged.

The reported total laser power of `1 W` is retained as source metadata.
No per-beam or per-component allocation is inferred, and no conversion from
that power to the peak saturation vectors is performed.

## Provisional force integration

Plane-wave mode remains the default. Elliptical-Gaussian mode requires both an
explicit mode selection and an explicit `GaussianBeamSet`; positions must be
declared in metres. For Track P plumbing, the equal-peak mean of the six
envelopes scales the existing normalized diagnostic force. This averaging is
an engineering adapter, not a molecular scattering-force derivation.

Run 007 compares plane-wave and Gaussian results using the same frozen static
`[3+1]` policy state and one common grid. These differences are not compared to
Rodriguez figures and support no physical conclusion.

The geometry can later enter a paper-grounded trajectory protocol after the
exact Hamiltonian, exact force calculation, power convention, and protocol
criteria are independently resolved. Run 007 performs no capture velocity or
threshold search, source-distribution modeling, stochastic diffusion,
optimization, or exact-force calculation.
