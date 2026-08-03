# Run 012 molecular-model interchange

`PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_012_MOLECULAR_MODEL_INTERCHANGE_AND_AUTHOR_HANDOFF_ONLY`

Run 012 defines `mgf-mot-molecular-model-v1`, a portable molecular-matrix
package for comparing the current provisional MgF model with a model supplied
by the Rodriguez authors. It does not promote an imported model, rebuild a
force cache, or authorize trajectories.

## Files and complex-number representation

Each package is a three-file set with one common basename:

- `.npz`: numerical arrays in native NumPy numeric dtypes, including complex
  arrays without dropping their imaginary parts;
- `.metadata.json`: units, axis meanings, basis labels, conventions, source,
  approximations, force context, and authorization state;
- `.manifest.json`: filenames, canonicalization rules, and SHA-256 hashes.

Mandatory arrays are `H0_g`, `mu_q_g`, `H0_e`, `mu_q_e`, `d_q`, branching,
zero-field eigenvalues/eigenvectors, construction-to-working transformations,
and working-to-canonical transformations. Array shapes, units, and axis
meanings are mandatory. Missing values never fall back to spectroscopy.py or a
pylcp default.

The v1 force convention is angular-frequency units normalized by `Gamma`,
`H(B)=H0-|B| mu_q[q=0]`, spherical order `(-1,0,+1)`, and a
ground-to-excited dipole tensor. Other conventions must be converted explicitly
before declaring a v1 package valid.

## Canonical hashes

Array names are sorted. Each array contributes its name, little-endian dtype,
shape, and contiguous bytes. Metadata uses canonical UTF-8 JSON with sorted
keys and compact separators; manifest/hash fields are excluded. Basis labels
are hashed separately. The full hash covers the schema version and all three
component hashes. Downstream artifacts made from an imported package must carry
the full package hash.

## Validation and equivalence

Validation checks schema completeness, shapes, finite values, units, axes,
basis ordering, Hermiticity, q=0 magnetic Hermiticity, transform unitarity,
dipole ordering, branching normalization, dipole-derived branching, transition
strengths, weak-field slopes, deterministic phase invariance, and a small
equilibrium-solver health problem. The result is `IMPORT_VALID`,
`IMPORT_VALID_WITH_WARNINGS`, or `IMPORT_INVALID`. Invalid packages cannot
construct the packaged force backend.

Comparison reports raw and physically aligned differences. Labels provide
permutation alignment; declared canonical transformations handle state phase
and unitary rotations confined to degenerate manifolds; one global energy
offset per manifold is removed. A transform that mixes nondegenerate energies
is warned and is not accepted as harmless. Reports cover energies, magnetic
slopes, eigenvector overlaps, transition strengths, branching, weak/dark-state
strengths, and connectivity.

## Workflow

1. `python scripts/export_accepted_molecular_model.py`
2. `python scripts/validate_molecular_model_package.py PACKAGE_BASE`
3. `python scripts/compare_molecular_model_packages.py ACCEPTED_BASE IMPORTED_BASE`
4. `python scripts/benchmark_imported_molecular_model.py IMPORTED_BASE`

The compact benchmark evaluates Figure 2 [3]/[3+1] plane-wave samples, local
slopes, component-(4) level hierarchy, paper scattering statements, selected
Figure 3 detunings, and Run 011B digitized samples. It is intentionally a
pre-dynamics decision layer.

The accepted reference package explicitly records corrected ground magnetism,
effective excited `g'=0.001`, effective `F'` splitting `0.5 MHz` as the midpoint
of a source-supported interval rather than a measurement, omission of the full
Doppelbauer `d` operator, and `replication_valid=false`.

`molecular_model_interchange_authorized=true`; imported-model force promotion,
cache rebuilds, trajectory reintegration, capture, optimization, and exact
replication remain unauthorized. Track E remains blocked pending the actual
paper model.
