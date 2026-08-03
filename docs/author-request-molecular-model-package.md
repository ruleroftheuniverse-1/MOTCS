# Request for the MgF molecular-model matrices

We are reproducing the MgF MOT calculations in K. J. Rodriguez et al., *Phys.
Rev. A* **108**, 033105 (2023). We have reproduced the published rate equations
and the official pylcp 1.0.2 calculation path. Independent and pylcp rate-
equation implementations agree numerically, and we have checked level counts,
matrix dimensions, sum rules, basis transformations, branching normalization,
sign conventions, and complex phase handling. The remaining force-map mismatch
is confined to the molecular matrices supplied to the rate equations.

The smallest useful payload would be:

- ground zero-field Hamiltonian `H0_g` and magnetic tensor `mu_q_g`;
- excited zero-field Hamiltonian `H0_e` and magnetic tensor `mu_q_e`;
- ground-to-excited spherical dipole tensor `d_q`;
- ground and excited basis labels in exact array order;
- units, spherical-component order, Hamiltonian/magnetic sign conventions, and
  the exact pylcp commit or checkout identifier.

This would let us resolve whether the missing independent Doppelbauer `d` term,
excited-state mixing, magnetic tensors, dipoles, or derived branching causes the
difference. A spontaneous branching matrix, exact Figure 2/3 force arrays, and
the excited-state line positions used would also be helpful but are not
required.

NumPy arrays (`.npy`/`.npz`), HDF5, MATLAB, or plain text accompanied by basis
ordering are all suitable. A Python pickle is usable only if unavoidable and
accompanied by Python, NumPy, pylcp, and source-version information. Instead of
arrays, the script/configuration that constructs the matrices—or a complete
documented serialized `pylcp.hamiltonian` object—would be entirely sufficient.

No trajectory, optimization, loading, or capture code is requested. The goal
is simply to compare the molecular-model instance and reproduce the static
force structure before attempting dynamics.
