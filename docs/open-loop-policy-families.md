# Model-independent open-loop policy families

`MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_015_OPEN_LOOP_POLICY_FAMILIES_ONLY`

Run 015 adds three closed, versioned control families on top of the accepted
`mgf-mot-control-policy-v2` ABI and routes them through the Run 014 schedule
compiler. This is control-schedule infrastructure only. It evaluates no
molecular force, trajectory, capture metric, reward, or physical performance.
It contains no search or optimizer behavior.

## Versions and closed registry

The family schema is `mgf-mot-open-loop-policy-family-v1`; parameterization
version `1` registers:

- `piecewise-linear-open-loop-v1` with
  `DETERMINISTIC_LINEAR_INTERPOLATION_V1`;
- `monotone-cubic-open-loop-v1` with
  `FRITSCH_CARLSON_PCHIP_V1`;
- `fourier-correction-open-loop-v1` with
  `ENDPOINT_PRESERVING_SIN_N_PI_U_V1`.

The registry maps a family/version pair to its algorithm, derivative support,
serializer, validator, evaluator, and parameter layout. Unknown identifiers or
versions fail closed. Arbitrary module paths, callables, and executable
expressions are not accepted.

Every family embeds a validated ABI-v2 specification. Consequently it retains
the exact four-component order `(1, 2, 3, 4)`, explicit enabled/active/off
states, parked detunings, channel targets, shared ownership, fixed channels,
affine dependencies, domains, provenance, and semantic events.

## Normalized time and endpoint behavior

Within a finite family interval,

`u = (t - t_start) / (t_end - t_start)`, with `0 <= u <= 1`.

Both endpoints are mandatory, finite, and distinct. The normalization itself
never clamps. Outside that interval, an endpoint is held only when the embedded
ABI channel explicitly has `LINEAR_HOLD` semantics. Otherwise evaluation fails.
Derivatives with respect to physical seconds include the factors
`1 / duration` and `1 / duration^2`.

For a composed handoff, the family owns only `t < tau`; ABI-v2's existing
handoff segment owns `t >= tau`. The adapter requires an explicit channel-ID
mapping and an ABI event exactly at the family endpoint. No interpolation
crosses the event, and structural knots are not promoted to semantic events.

## Piecewise-linear schedules

The canonical representation is paired arrays `(u_i, y_i)`. It requires at
least two finite knots, exactly `u_0 = 0` and `u_last = 1`, strictly increasing
positions, and an optional positive minimum separation. Values may be
`UNRESTRICTED`, `NONDECREASING`, or `NONINCREASING`; violations fail rather than
being reordered or repaired.

Values are continuous and exact at knots. The first derivative is constant on
each open interval and has an explicit discontinuity at an interior knot. A
classical second derivative is not claimed at knots. Endpoint derivatives are
one-sided. Saturation values must remain nonnegative; there is no clipping.

## Shape-preserving monotone cubic schedules

The cubic implementation is the deterministic Fritsch-Carlson/PCHIP Hermite
construction. Interior tangents use the weighted harmonic mean when adjacent
secant slopes have the same nonzero sign and zero otherwise. Endpoint tangents
use the one-sided shape-preserving limiter. This preserves monotonicity, stays
within neighboring knot bounds, and creates no artificial extrema.

Value and first derivative are continuous within the family interval. Second
derivatives are piecewise defined and generally discontinuous at knots. The
two-knot case is evaluated with the exact linear algebraic form, so it matches
the distinguished Rodriguez control baseline rather than producing a curved
approximation or a last-bit Hermite discrepancy. Unrestricted cubic splines
are intentionally unsupported.

## Finite Fourier corrections

The Fourier family uses

`y(u) = y_start + (y_end - y_start) u + sum(a_n sin(n pi u))`.

The finite, versioned sine basis makes every correction zero at both endpoints.
Harmonic and coefficient counts must agree, and every coefficient must be
finite. First and second derivatives are analytic. Coefficients are merely an
inspectable parameter representation: the module performs no initialization,
fitting, regularization, objective evaluation, or search.

Fourier monotonicity is classified, not silently enforced. Nonmonotone policies
remain structurally valid and may subsequently fail declared rate or bandwidth
constraints. For saturation, validation uses a conservative correction bound;
any case that cannot guarantee nonnegative saturation fails. Saturation is not
interpreted as optical power.

## Parameter vectors and deterministic identity

`ParameterVectorLayout` sorts entries by explicit channel ID and declared
element index. Each entry records its name, units, element, and bound metadata.
Unknown bounds remain `null` with `UNKNOWN` basis. Fixed endpoints and other
fixed parameters are excluded. Flattening and reconstruction require the exact
layout hash and vector length, preserve fixed values, and revalidate the
resulting family specification. No `[0, 1]` rescaling is implicit.

Canonical JSON preserves algorithms, arrays, ordering, ABI ownership, events,
baseline parameters, provenance, and versions. SHA-256 identities separately
cover the family specification, parameter values, layout, and complete package.
Mapping-key order and timestamps do not change identity; meaningful waveform
or ownership changes do.

## Smoothness ledger and structural metrics

Each instance provides a machine-readable ledger for value, first-derivative,
and second-derivative continuity; structural knots; semantic events; known
discontinuities; and endpoint derivative behavior. It deliberately does not
overstate smoothness across a handoff.

Per-channel structural metrics report total variation, derivative maxima,
endpoint displacement, extrema, monotonicity, knot/harmonic count, and
derivative-discontinuity count. Whole-policy metadata reports parameter and
event counts, structural boundaries, hashes, and compiler readiness. Detuning
and saturation remain separate; these metrics are not physical quality scores.
Derivative extrema are evaluated on a documented deterministic 4097-point
diagnostic grid, while pointwise derivatives use the analytic family formulas.

## Compiler integration and examples

The Run 014 compiler accepts a registered evaluator and its deterministic
family hash while retaining its existing validation, clock, quantization,
latency, event, reconstruction, and constraint pipeline. Default ABI-v2 calls
are unchanged. The formal continuous identity profile is still synthetic and
not a device. Finite-clock examples use zero-order hold.

The `configs/run_015/` examples include exact baseline representations,
multi-knot synthetic fixtures, a zero-correction Fourier baseline, a nonzero
synthetic Fourier fixture, and a deliberately infeasible high-bandwidth stress
fixture. Nonbaseline values are explicitly `SYNTHETIC_TEST_FIXTURE` or
`ENGINEERING_STRESS_TEST`; none is described as improved or optimal.

Run the deterministic audit with:

```powershell
python scripts/validate_open_loop_policy_families_run_015.py
```

The gate authorizes later interface and protocol infrastructure only. It does
not authorize real apparatus execution, force or capture studies, feedback,
optimization, or claims that a policy improves MgF MOT performance.
