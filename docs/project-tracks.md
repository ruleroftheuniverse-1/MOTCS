# Project tracks

This project now has two deliberately separate tracks. The split exists so we
can build and test static force-map plumbing without pretending that approximate
MgF results reproduce Rodriguez et al.

## Track E: `exact`

Track E is the exact Rodriguez/MgF replication track.

It may claim:

- source-tagged spectroscopy inputs;
- validated `X 2Sigma+` ground-state structure;
- validated 12-ground / 4-excited basis counts;
- validated ground hyperfine ordering and spacings;
- exact force-map readiness only after the excited-state Hamiltonian and Zeeman
  model are resolved and tested.

It may not claim yet:

- a complete MgF Hamiltonian;
- exact excited-state energies;
- exact excited-state magnetic moments;
- Rodriguez-valid static force maps;
- capture velocities, trajectories, chirped MOT behavior, Gaussian-beam
  results, or optimization.

Current status:

- blocked honestly;
- `ExactBackendMode.LOCAL_EXTENDED_ASTATE` is only a feasibility report;
- no exact-track force maps are allowed while exact construction is blocked.

The current exact blockers are:

- independent Doppelbauer excited-state `d` operator is not implemented or
  validated;
- excited-state Zeeman inputs are not source-mapped to MgF with `pylcp`
  conventions;
- fluorine nuclear g-factor/convention remains uncertified for exact magnetic
  matrices;
- no source-validated `F'=0/F'=1` splitting or line-position check has been
  added for the local exact extension.

## Track P: `provisional`

Track P is an engineering/plumbing track.

It may claim:

- the code path is useful for API, metadata, plotting, and sign-flip plumbing;
- it uses explicit opt-in approximation mode;
- outputs are normalized diagnostic artifacts;
- every output is marked `PROVISIONAL` and `NOT_RODRIGUEZ_REPLICATION`.

It may not claim:

- exact MgF physics;
- Rodriguez replication validity;
- force readiness by default;
- quantitative comparison to Rodriguez force magnitudes;
- capture behavior, chirp performance, Gaussian-beam physics, physically
  meaningful trajectories, or optimized parameters.

Track P may exercise a visibly labeled trajectory scaffold solely to validate
the policy-to-pointwise-force-to-integrator interface. That scaffold may not
define capture/loss criteria, source distributions, loading, calibrated
force-to-acceleration physics, or physical trajectory conclusions.

Track P may also apply explicitly engineering-defined outcome labels to an
ordered trajectory list. `BOUNDED_FINAL_STATE` records satisfaction of a
configured final dwell window only; it is not a physical capture claim and may
not be used to report a capture velocity or threshold curve.

Track P may validate source-stated finite beam geometry and explicitly apply
its envelopes to the normalized diagnostic force. This permits coordinate and
plumbing checks only; it does not establish Gaussian-beam molecular-force
physics or authorize capture-style conclusions.

Track P may execute a fixed, named list of apparatus trajectories as an
end-to-end integration check. The list must remain explicit and ordered; it may
not be refined, interpolated, or summarized as a maximum successful velocity.

Required status metadata for Track P:

| Field | Required value |
|---|---|
| `track` | `provisional` |
| `backend_mode` | explicit approximation mode, currently `collapsed_pylcp_astate` |
| `force_ready` | `false` unless promoted in a later reviewed step |
| `replication_valid` | `false` |
| `warnings` | must include provisional and not-replication warnings |
| `omitted_terms` | must list unresolved/omitted physics |
| `collapsed_terms` | must list collapsed source-to-backend mappings |

The current provisional force-map harness is a normalized diagnostic model for
plumbing only. It requires:

1. an `ApproximateMgFHamiltonian` built through
   `ApproximationMode.COLLAPSED_PYLCP_ASTATE`; and
2. `ProvisionalForceMapConfig(explicit_provisional_opt_in=True)`.

Without both, the harness raises.

Every provisional plot/table/spec must include both labels:

- `PROVISIONAL`
- `NOT_RODRIGUEZ_REPLICATION`

### Run 009 static rate-equation backend

Run 009 adds a separate, explicit-opt-in `pylcp 1.0.2` rate-equation backend
for static Track P validation. It constructs all active physical
beam/component entries in one optical system and obtains one shared equilibrium
population solution before summing radiative-force contributions. Gaussian
saturation is evaluated separately for every beam/component before that solve.

This backend is physics-bearing only inside its narrow, provisional static
scope. It is not Rodriguez-replication-valid, is not connected to trajectory
integration, and does not remove the exact Track E blockers. Its required label
is
`PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY`.

The earlier spring/damping force law is now explicitly represented by
`ToyHeuristicForceBackend`. It remains available solely to preserve Runs
001--008 as historical interface-plumbing artifacts. It is not the default
provisional physics backend, has `physics_valid = false`, and cannot support
physical interpretation. Run 008B supersedes any physical interpretation of
those earlier outputs; Run 009 does not retroactively recalculate them.

Run 009A applies the static acceptance gate documented in
`docs/run-009a-static-acceptance-audit.md`. Its current decision is `NO-GO`:
the lab-x geometry and equilibrium solves are healthy, but the nominal force is
anti-restoring and component (4) strengthens that wrong sign. The real-backend
reversal matrix confirms a convention/topology mismatch. Consequently the
Run 009 rate-equation backend remains disconnected from every trajectory path.

Run 009B identified a centralized ground Zeeman convention error. Under the
project convention `dE/dB=g_F mu_B m_F`, raw Xstate tensors gave all identified
ground g signs opposite Rodriguez Fig. 1. The named
`PROJECT_ENERGY_SLOPE_CORRECTED` translation negates that ground tensor once at
the pylcp Hamiltonian boundary and passes the compact static `[3]`, `[3+1]`,
component-(4), polarization, dipole-order, and chirp-direction checks.

This does not reopen trajectories. Corrected full static artifacts and Run
009A must be regenerated first. Moreover, the collapsed excited tensor remains
far from the representative Rodriguez `g=0.001` treatment, and exact Track E
remains blocked.

Run 009A-R1 performs that historical-preserving regeneration using the named
corrected ground-Zeeman convention. Its static gate applies only to further
provisional static study. Regardless of the gate, trajectory and capture
authorization remain false because the excited-state magnetic tensor is still
unresolved.

Run 009C adds explicit excited-Zeeman choices. Its validated
`RODRIGUEZ_EFFECTIVE_G_0P001` direct-sum operator is the preferred Track P
static choice after sensitivity comparison, but must always be selected
explicitly. This is a representative paper-aligned approximation, not exact
excited spectroscopy, and it does not lift any trajectory, capture, or Track E
lock.

## Promotion rules

No Track P result may be promoted into Track E by changing labels. Promotion
requires new source-backed physics:

1. implement or source the independent excited-state `d` operator;
2. validate excited level splittings or line positions;
3. resolve the excited Zeeman mapping or explicitly document a reviewed
   effective replacement;
4. rerun backend validation;
5. only then enable exact-track force-map construction.
