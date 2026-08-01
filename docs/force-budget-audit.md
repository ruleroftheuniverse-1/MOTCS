# Track P Run 008B force-budget audit

Run 008B is an offline engineering audit. It reads the saved Run 008 arrays,
performs pointwise static-force calls, and does not integrate or modify any
trajectory. Its output is always labeled
`PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY`.

## Source-tagged SI conversion

The audit uses the already source-tagged cooling wavelength `359.3 nm` and
linewidth `Gamma = 2 pi x 20.9 MHz`. The dominant-isotopologue mass is derived
from the NIST relative atomic masses for
[24Mg](https://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl?ele=Mg)
and [19F](https://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl?ele=F),
with the [2022 CODATA atomic mass
constant](https://physics.nist.gov/cuu/pdf/wallet_2022.pdf). The atom-mass sum
neglects molecular binding mass and is explicitly tagged `derived_approximate`;
it is unit-conversion data, not a molecular spectroscopy constant.

The conversion chain is

```text
normalized force -> force_N = normalized force * hbar*k*Gamma
                 -> acceleration = force_N / mass
```

`normalized_force_to_newtons` is the only multiplication by `hbar*k*Gamma`.
The acceleration helper calls it once and then divides by the source-tagged
mass. Run 008 did not use this chain: its explicit engineering adapter was
`normalized_force_to_acceleration = 1.0`.

## What the implementation audit found

The current provisional force law is

```text
F = -spring*x - damping*v
```

where `spring` is the sum of active component saturations. Detuning, component
identity, transition matrices, and the collapsed backend Hamiltonian do not
enter the numerical force. Consequently:

- `[3]` and `[3+1]` both have aggregate saturation `5.79` and are identical;
- frozen chirp forces at `-8`, `-4.5`, and `-1 Gamma` are identical;
- component `(4)` cannot improve confinement in this toy law; and
- a truthful beam-pair or frequency-component decomposition is unavailable.

The six Gaussian beam objects each evaluate their own envelope and
counterpropagating partners agree. However, `force_at` first constructs the
aggregate force and then multiplies it by `GaussianBeamSet.mean_envelope`.
Therefore per-beam envelopes are not applied to corresponding beam/component
intensities before force summation. Saturation is not squared, the weakest
envelope is not selected, and positions remain in metres, but the mean-after-
sum architecture is explicitly diagnosed as `GAUSSIAN_APPLICATION_SUSPECT`.

## Interpretation boundary

The local plane-wave and Gaussian laws are restoring and damping near the
origin, but that sign check does not validate global force topology. The saved
force integrals combined with a physical single conversion would imply an
enormous impulse, whereas Run 008's unit adapter produced only a tiny velocity
change. The resulting diagnoses are:

- `UNIT_CONVERSION_SUSPECT`;
- `GAUSSIAN_APPLICATION_SUSPECT`; and
- `PROVISIONAL_BACKEND_TOPOLOGY_SUSPECT`.

These are nonphysical engineering diagnoses. They are not capture efficiencies,
MgF force predictions, or comparisons claiming agreement or disagreement with
Rodriguez. Exact Track E remains blocked.
