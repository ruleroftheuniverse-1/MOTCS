# Track P policy-force snapshots

This page documents the Track P bridge from laser schedule policies to frozen
static force-grid evaluation.

This is not trajectory simulation. It does not integrate molecule motion,
compute capture velocity, model Gaussian beams, optimize parameters, open exact
force maps, or claim Rodriguez/MgF replication.

## What the bridge does

`src/mgf_mot/policy_force.py` evaluates a policy at one fixed time and passes
the sampled component state into the provisional static force-grid harness.

The main function is:

```python
force_grid_for_policy_snapshot(policy, t, backend, force_config, grid_config)
```

It requires:

- a Track P provisional backend;
- explicit approximation mode upstream;
- `ProvisionalForceMapConfig(explicit_provisional_opt_in=True)`;
- metadata with `replication_valid = False`;
- warning labels preserved in titles, filenames, JSON metadata, and reports.

Snapshot metadata includes a per-component table with:

- detuning;
- saturation;
- `enabled`;
- `active`;
- `off_reason`.

This distinction is intentional. During the baseline linear policy, component
`(4)` has a parked detuning of `+2 Gamma`, but it is explicitly off:
`saturation = 0`, `enabled = false`, and `active = false`. A detuning value
alone must never be interpreted as active optical power.

## What the bridge does not do

It does not advance time. It does not call a differential-equation solver. It
does not compute capture, loading, or trajectory behavior. Each output is just a
static grid evaluated at one frozen policy time.

## Run 003

Run:

```powershell
python scripts/run_provisional_policy_force_snapshots.py
```

The script loads:

- `configs/rodriguez_baseline_linear_chirp.yaml`

and samples:

- `t = 0`;
- `t = tau/2`;
- `t = tau`;
- `t = 2 tau`.

Outputs are written under:

`outputs/provisional/`

All output names include:

- `PROVISIONAL`;
- `NOT_RODRIGUEZ_REPLICATION`;
- `POLICY_FORCE_SNAPSHOT_ONLY`.

The run report is:

`outputs/provisional/PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLICY_FORCE_SNAPSHOT_ONLY_run_003.md`

## Track status

Track E exact MgF force readiness remains blocked by unresolved excited-state
Hamiltonian and Zeeman mappings. Track P outputs are engineering/plumbing
artifacts only. No physical conclusions should be drawn from provisional force
magnitudes or topology.
