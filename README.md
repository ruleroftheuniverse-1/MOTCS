# Static MgF MOT force-map replication

This repository contains the pre-Hamiltonian foundation for reproducing the
static MgF MOT force maps of Rodriguez *et al.*: paper parameters, SI unit
conversions, the MOT quadrupole field, and the rotated six-beam geometry.

The MgF Hamiltonian, transition couplings, force calculation, and trajectories
are intentionally not implemented. The source paper does not contain all
spectroscopy constants required to construct them faithfully.

Install and test with:

```powershell
python -m pip install -e ".[test]"
python -m pytest
```

Configuration files use angular-frequency detunings normalized to `Gamma`.
Geometry functions use SI units (metres, tesla, and tesla/metre).

