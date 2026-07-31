# Track P outcome-classification scaffold

`mgf_mot.outcomes` separates two operations:

1. trajectory integration produces time, position, velocity, force, policy
   state, and backend provenance;
2. outcome classification applies explicit engineering criteria to those
   arrays.

This separation keeps numerical integration reusable and prevents provisional
classification settings from being mistaken for molecular dynamics.

Every Run 006 artifact is stamped:

- `PROVISIONAL`
- `NOT_RODRIGUEZ_REPLICATION`
- `OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY`

## Explicit outcome labels

The classifier returns one of:

- `BOUNDED_FINAL_STATE`
- `ESCAPED`
- `UNRESOLVED`
- `INVALID`

It does not return a bare captured/not-captured Boolean.
`BOUNDED_FINAL_STATE` means only that the configured position and speed bounds
were satisfied for enough samples in the final dwell window. It is not yet
equivalent to physical MOT capture.

`ESCAPED` requires crossing an explicitly configured hard position or speed
bound. `UNRESOLVED` covers insufficient duration, insufficient dwell samples,
or failure to remain within the final engineering bounds. `INVALID` identifies
malformed or nonfinite numerical arrays.

## Why a final dwell window is required

A single final sample can be misleading. A trajectory can pass briefly through
the origin while moving rapidly, or cross the bounded region and leave again.
The classifier therefore inspects a configurable final time window, requires a
minimum number of samples, and by default requires every dwell sample to
satisfy both the position and speed limits.

The configurable criteria include:

- radius or maximum absolute coordinate;
- final position and speed bounds;
- final dwell duration;
- minimum dwell-sample count;
- required in-bounds sample fraction;
- optional hard escape-position and speed bounds;
- explicit normalized units.

These settings are engineering-defined. They are not derived from Rodriguez et
al. and must not be interpreted as a physical loading or capture definition.

## Ordered provisional ensembles

`run_trajectory_ensemble` accepts an explicit ordered list of initial states.
It preserves that order and attaches the backend mode, project track,
replication status, omitted and collapsed physics, policy name, initial state,
integration status, outcome label, and numerical reason to every member.

The Run 006 script uses a deterministic list of three initial velocities at one
common position. This is not a molecular source distribution and is not a
velocity-threshold search. Infinite plane waves are used; no Gaussian envelope,
stochastic diffusion, optimizer, or exact force path is present.

## Future calibration

The interface allows the engineering criteria to be replaced or calibrated
later against an explicitly reviewed Rodriguez-derived definition. That future
work must establish the relevant spatial, velocity, time, loss, and beam-model
conditions before any physical statement is made.

Track E remains blocked by the independent Doppelbauer `d` operator and
excited-state Zeeman mappings. Once the exact Hamiltonian and force backend are
validated, Track E can reuse the trajectory and outcome interfaces with
separately sourced criteria. Changing labels alone cannot promote a Track P
result into an exact replication.
