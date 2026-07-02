# Static MgF MOT force-map replication

This repository contains the pre-Hamiltonian foundation for reproducing the
static MgF MOT force maps of Rodriguez *et al.*: paper parameters, SI unit
conversions, the MOT quadrupole field, and the rotated six-beam geometry.

The faithful full MgF Hamiltonian, force calculation, and trajectories are
intentionally not implemented. The current code validates the source-supported
ground Hamiltonian and angular coupling tensor, while the exact excited-state
factory remains blocked until the missing mappings are resolved.

Install and test with:

```powershell
python -m pip install -e ".[test]"
python -m pytest
```

Run the pre-MgF `pylcp` convention check with:

```powershell
python -m pip install -e ".[notebook]"
python -m jupyter lab notebooks/pylcp_conventions_sanity_check.ipynb
```

The checked-in notebook is already executed and contains its five force plots
and quantitative sign assertions.

Validate the source-tagged MgF level structure with:

```powershell
python scripts/validate_mgf_hamiltonian.py
```

This validation constructs the sourced 12-state ground Hamiltonian and the
12-by-4 angular coupling structure. Complete excited-state Hamiltonian
construction remains deliberately blocked pending a reviewed implementation of
the independent Doppelbauer hyperfine `d` term and unresolved parameter
mappings. An explicit provisional `ApproximationMode.COLLAPSED_PYLCP_ASTATE`
exists for audit work only; it is not enabled by default and is not force-ready.
`ExactBackendMode.LOCAL_EXTENDED_ASTATE` currently reports feasibility blockers
rather than constructing a local exact backend.

The project is split into Track E (`exact`) and Track P (`provisional`); see
`docs/project-tracks.md`. Provisional force-map plumbing exists only behind
explicit opt-in and every provisional artifact is labeled
`PROVISIONAL_NOT_RODRIGUEZ_REPLICATION`.

Track P laser schedule policies are documented in `docs/policy-interface.md`;
inspect them with `python scripts/inspect_policies.py`.

Configuration files use angular-frequency detunings normalized to `Gamma`.
Geometry functions use SI units (metres, tesla, and tesla/metre).
