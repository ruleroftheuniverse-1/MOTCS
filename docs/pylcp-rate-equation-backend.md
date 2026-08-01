# Provisional pylcp rate-equation static backend

Run 009 introduces a physics-bearing static Track P force calculation while
keeping exact Track E blocked. It requires both explicit provisional opt-in and
`ApproximationMode.COLLAPSED_PYLCP_ASTATE`. Its artifacts are stamped
`PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY`.

The implementation was checked against the installed `pylcp 1.0.2` source and
the official [CaF MOT example](https://python-laser-cooling-physics.readthedocs.io/en/latest/examples/MOTs/20_CaF_MOT.html).

## pylcp 1.0.2 interface findings

### Hamiltonian

`pylcp.rateeq(laserBeams, magField, hamiltonian, ...)` accepts a block
`pylcp.hamiltonian`. The official CaF molecular example divides MHz
Hamiltonian and magnetic-moment inputs by `Gamma` before constructing the
Hamiltonian. Run 009 follows that convention using the source-tagged
`Gamma/(2 pi) = 20.9 MHz`. The retained model has 12 ground states, 4 excited
states, and a `(3, 12, 4)` dipole tensor.

The Hamiltonian remains approximate: the independent Doppelbauer `d` operator,
the full excited Zeeman mapping, and the sourced separation of collapsed terms
remain unresolved.

### Laser beams and saturation

`pylcp.laserBeams` is one collection of `laserBeam` objects. Every active
physical-beam/frequency-component combination is inserted into that collection:

- 18 lasers for `[3]`: six beams times three active components;
- 24 lasers for `[3+1]`: six beams times four active components.

The `s` argument is intensity normalized to saturation intensity. Run 009
passes the config saturation once and does not square it. Component detuning is
specified in units of `Gamma`; a carrier offset aligns each addressed ground
role with the upper level of the collapsed excited block, following the same
pattern used in the official CaF example.

Policy strings `sigma_plus` and `sigma_minus` map to pylcp `pol=+1` and
`pol=-1`. These integers define helicity relative to each beam propagation
vector. This explicit convention is not an exact Rodriguez polarization
validation.

Run 009B subsequently verified the actual Cartesian and fixed-axis spherical
vectors and retained this direct paper-label translation. It also found that
raw `XFmolecules.Xstate` magnetic tensors produce ground energy-slope signs
opposite the source-tagged MgF g factors when passed directly into pylcp's
`H=H0-mu.B` convention. New provisional backend constructions therefore use
the centralized `PROJECT_ENERGY_SLOPE_CORRECTED` ground translation. Historical
Run 009 and Run 009A scripts remain pinned to `RAW_XFMOLECULES` so their saved
artifacts remain reproducible.

The excited provisional tensor is not corrected by that translation. Its
partial collapsed Astate response corresponds to an effective g magnitude of
about `0.334`, rather than Rodriguez's representative `0.001`; this remains an
explicit provisional limitation.

### Magnetic field and units

The project quadrupole geometry is `B = B' (-x/2, -y/2, z)`. Public positions
remain metres. The field callable converts the source gradient `0.2 T/m` and
resulting field to gauss because the normalized molecular magnetic moments are
in `Gamma/G`. Velocity is converted from `m/s` to `Gamma/k` before a solve.

With normalized frequencies, `gamma=1`, and unit wave-vector magnitude, pylcp
force is returned in `hbar k Gamma`. SI acceleration is produced only through
the separately tested `hbar k Gamma / m` conversion. No SI conversion occurs
when normalized force is requested.

### Equilibrium populations and forces

`rateeq.construct_evolution_matrix` computes every laser pumping matrix, sums
all laser pumping rates, and combines them with decay. The method
`equilibrium_populations` obtains the common steady state from the nullspace of
that one evolution matrix using singular-value decomposition.

`find_equilibrium_force(return_details=True)` returns total force, force for
each laser, the common equilibrium population, per-laser/state pumping rates,
and magnetic force. Run 009 disables magnetic-gradient mechanical force and
records radiative force. Per-beam and per-component contributions are grouped
from per-laser force only after the shared population solve. No isolated-beam
or isolated-component solutions are summed.

## Elliptical Gaussian application

The built-in pylcp Gaussian beam is circular. The project therefore uses the
base `pylcp.laserBeam` with a callable saturation. For every active component
of each physical beam, it evaluates the existing elliptical envelope:

`s_local = s_peak * envelope_for_this_physical_beam(position)`.

Local values enter pylcp before pumping rates and populations are calculated.
No averaged envelope, weakest envelope, independent-beam solve, or post-force
multiplier is used.

## Static findings and boundary

Run 009 demonstrates detuning dependence, saturation/component dependence,
distinct `[3]` and `[3+1]` surfaces, distinct frozen chirp surfaces, and center
agreement between peak Gaussian and plane-wave cases. The current explicit
helicity/gradient mapping gives damping but anti-restoring static `[3]` and
`[3+1]` slopes. It is reported rather than tuned away.

These results do not validate MgF capture or reproduce Rodriguez. No trajectory
or capture calculation is connected to this backend. Force-dependent Runs
001-008 remain historical plumbing artifacts whose physical interpretation was
superseded by Run 008B.

Run 009B subsequently traced the anti-restoring sign to the ground magnetic
tensor convention, and Run 009A-R1 validated the corrected static topology.
Those newer artifacts supersede the old anti-restoring surfaces for
provisional engineering while preserving them as historical diagnostics.

Run 009C separates the excited-state magnetic choice through
`ExcitedZeemanModel`. The default remains the historical collapsed pylcp
tensor. Static paper-aligned work may explicitly request
`RODRIGUEZ_EFFECTIVE_G_0P001`, whose direct-sum `F'=0` plus `F'=1` operator is
validated against `H=H0-mu.B` and the source-tagged representative
`g'=+0.001`. The model is applied exactly once at Hamiltonian construction and
does not modify the ground tensor. It remains provisional and opens no motion
or exact-track path.
