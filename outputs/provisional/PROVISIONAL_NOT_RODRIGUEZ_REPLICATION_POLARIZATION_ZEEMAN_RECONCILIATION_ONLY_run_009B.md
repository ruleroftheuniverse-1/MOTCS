# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLARIZATION_ZEEMAN_RECONCILIATION_ONLY Run 009B

This is a static convention reconciliation only. It preserves the paper magnetic field, positive gradient, beam directions, component labels, Gaussian implementation, and spectroscopy inputs. No trajectory or capture calculation was run.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLARIZATION_ZEEMAN_RECONCILIATION_ONLY Frozen source semantics

YAML remains `(1) sigma+`, `(2) sigma-`, `(3) sigma-`, `(4) sigma+`. Paper labels, pylcp beam-relative scalar helicity, Cartesian electric fields, and fixed-axis spherical components are stored as separate concepts.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLARIZATION_ZEEMAN_RECONCILIATION_ONLY Polarization and dipole evidence

- normalized vectors: `True`; transverse: `True`
- equal scalar `pol` on opposite k reverses fixed-axis q: `True`
- rotated-frame handedness consistent: `True`
- dipole tensor order: `[-1, 0, 1]`; forbidden nonzero transitions: `0`
- pylcp contracts opposite spherical indices, so light q=+1 drives Delta m=+1 even though it multiplies tensor plane q=-1.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLARIZATION_ZEEMAN_RECONCILIATION_ONLY Independent Zeeman evidence

Under `H=H0-mu.B` and `dE/dB=g_F mu_B m_F`, the raw ground tensor gives every identified nonzero manifold the opposite source-tagged sign. Negating that ground tensor once at the Hamiltonian boundary restores the expected signs.
Raw signs globally reversed: `True`; corrected signs match: `True`.
The provisional excited tensor remains unresolved: its partial Astate terms imply effective `g about +0.334`, not the Rodriguez representative `+0.001`. This reconciliation does not invent a replacement.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLARIZATION_ZEEMAN_RECONCILIATION_ONLY Controlled candidate force matrix

| mapping | [3] dF/dx | [3] dF/dv | [3+1] dF/dx | c4 ablated dF/dx | c4 alone dF/dx | justified |
|---|---:|---:|---:|---:|---:|---|
| mapping_a_current | 0.159482 | -0.00397668 | 0.299954 | 0.138078 | -0.000738214 | no |
| mapping_b_global_helicity_inversion_diagnostic | -0.159482 | -0.00397668 | -0.299954 | -0.138078 | 0.000738214 | no |
| mapping_d_corrected_ground_zeeman | -0.00894088 | -0.00397668 | -0.152767 | -0.0176337 | -0.00130792 | yes |

Mapping B produces attractive signs but is rejected as an empirical global helicity inversion: the actual polarization and dipole audits do not justify it. Mappings C and E were not constructed because the audited q order and rotated frames are correct.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLARIZATION_ZEEMAN_RECONCILIATION_ONLY Causal resonance direction

Controlled one-component solves compare equal-intensity positive- and negative-kx beam groups at small positive and negative x. The larger summed pumping group is an operational closer-to-resonance proxy. Detailed selected state indices, resonance errors, pumping rates, and population-weighted group forces are in metadata.
Corrected mapping makes the operational closer-to-resonance beam group match the expected restoring group for all representative components: `True`. Population-weighted group forces are reported separately because optical pumping can reverse a one-component net force in a type-II system.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLARIZATION_ZEEMAN_RECONCILIATION_ONLY Mapping-change gate

- `documented_convention_justification`: `True`
- `ground_zeeman_slopes_expected`: `True`
- `dipole_q_order_verified`: `True`
- `three_restoring_and_damping`: `True`
- `three_plus_one_strengthens_confinement`: `True`
- `component_4_intended_direction`: `True`
- `chirp_direction_coherent`: `True`
- `polarization_vectors_and_counterpropagation_verified`: `True`
- `transition_resonance_direction_causal`: `True`
- `centralized_translation`: `True`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLARIZATION_ZEEMAN_RECONCILIATION_ONLY Final result: CONVENTION_ERROR_IDENTIFIED

**CONVENTION_ERROR_IDENTIFIED**

Exact error: the raw `XFmolecules.Xstate` tensor was passed directly as pylcp's magnetic moment even though, under the project energy convention, that produces ground `dE/dB` signs opposite the source-tagged MgF g factors.
Corrected translation: `translate_xstate_ground_muq_for_pylcp(..., PROJECT_ENERGY_SLOPE_CORRECTED)` negates the ground tensor exactly once at Hamiltonian construction. It does not change YAML, the apparatus field, the dipole tensor, or the excited tensor.
Run 009A should be rerun against newly generated corrected static artifacts. Historical Run 009 and Run 009A artifacts were not rewritten here.
Trajectories remain unauthorized. Exact Track E remains blocked.

# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLARIZATION_ZEEMAN_RECONCILIATION_ONLY FINAL_CONVENTION_ERROR_IDENTIFIED
