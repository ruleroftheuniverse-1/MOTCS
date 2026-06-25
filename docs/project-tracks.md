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
- capture behavior, chirp performance, Gaussian-beam physics, trajectories, or
  optimized parameters.

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

## Promotion rules

No Track P result may be promoted into Track E by changing labels. Promotion
requires new source-backed physics:

1. implement or source the independent excited-state `d` operator;
2. validate excited level splittings or line positions;
3. resolve the excited Zeeman mapping or explicitly document a reviewed
   effective replacement;
4. rerun backend validation;
5. only then enable exact-track force-map construction.

