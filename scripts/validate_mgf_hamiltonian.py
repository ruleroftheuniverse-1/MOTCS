"""Print the current source-supported MgF Hamiltonian validation status."""

from mgf_mot.mgf_backend import (
    ApproximationMode,
    MgFBackendCapabilityError,
    analyze_mgf_exact_backend_feasibility,
    build_mgf_hamiltonian_from_sources,
    build_mgf_validation_model_from_sources,
)
from mgf_mot.spectroscopy import (
    EXCITED_G_FACTOR_RODRIGUEZ,
    GROUND_EFFECTIVE_G_FACTORS,
)


def main() -> None:
    model = build_mgf_validation_model_from_sources()

    print("MgF pylcp Hamiltonian validation layer")
    print(f"ground states: {model.ground_state_count}")
    print(f"excited states: {model.excited_state_count}")
    print(f"transition dipole tensor shape: {model.transition_dipole_q.shape}")

    print("\nGround eigenstate basis labels (dominant bare component):")
    for state in model.ground_eigenstates:
        print(
            f"  {state.index:2d}: J~{state.dominant_J:g}, F={state.F:g}, "
            f"mF={state.mF:+g}, E-E(lower F=1)={state.relative_energy_mhz:10.6f} MHz, "
            f"dominant weight={state.dominant_weight:.6f}"
        )

    print("\nGround hyperfine levels relative to lower F=1:")
    for level in model.ground_levels:
        g_factor = GROUND_EFFECTIVE_G_FACTORS[level.label]
        g_text = "UNKNOWN" if g_factor.value is None else f"{g_factor.value:g}"
        print(
            f"  {level.label:9s}: F={level.F}, degeneracy={level.degeneracy}, "
            f"E={level.relative_energy_mhz:10.6f} MHz, g={g_text} [{g_factor.status}]"
        )

    print("\nExcited basis and energies:")
    for index, (state, energy) in enumerate(zip(model.excited_basis, model.excited_energies_mhz)):
        energy_text = "UNKNOWN" if energy is None else f"{energy:.6f} MHz"
        print(
            f"  {index:2d}: J={float(state['J']):g}, F={float(state['F']):g}, "
            f"mF={float(state['mF']):+g}, P={int(state['P']):+d}, E={energy_text}"
        )
    print(
        f"  Rodriguez excited g assumption: {EXCITED_G_FACTOR_RODRIGUEZ.value:g} "
        f"[{EXCITED_G_FACTOR_RODRIGUEZ.status}; not a measured constant]"
    )

    print("\nMissing constants:")
    for constant in model.missing_constants:
        print(f"  {constant.name}: UNKNOWN — {constant.note}")

    print("\nApproximations/model assumptions:")
    for constant in model.approximate_constants:
        print(f"  {constant.name}: {constant.value} {constant.units} [{constant.status}]")

    print("\nBackend limitations:")
    for limitation in model.backend_limitations:
        print(f"  - {limitation}")

    try:
        build_mgf_hamiltonian_from_sources()
    except MgFBackendCapabilityError as exc:
        print("\nComplete pylcp.hamiltonian status: BLOCKED (expected)")
        print(exc)
    else:  # pragma: no cover - becomes relevant only after the backend is completed
        print("\nComplete pylcp.hamiltonian status: READY")

    feasibility = analyze_mgf_exact_backend_feasibility()
    print("\nExact backend feasibility:")
    print(f"  mode: {feasibility.mode.value}")
    print(f"  can construct exact Hamiltonian: {feasibility.can_construct}")
    print(f"  force-ready: {feasibility.force_ready}")
    print(f"  undocumented pylcp defaults used: {feasibility.undocumented_defaults_used}")
    if feasibility.missing_source_constants:
        print("  missing required source constants:")
        for constant in feasibility.missing_source_constants:
            print(f"  - {constant.name}: {constant.note}")
    print("  blockers:")
    for blocker in feasibility.blockers:
        print(f"  - {blocker}")

    approximate = build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )
    print("\nExplicit approximation mode:")
    print(f"  track: {approximate.provenance.track.value}")
    print(f"  mode: {approximate.report.mode.value}")
    print(f"  replication-valid: {approximate.provenance.replication_valid}")
    print(f"  pylcp-compatible block sizes: {approximate.hamiltonian.ns}")
    print(f"  force-ready by default: {approximate.report.force_ready_by_default}")
    print("  provenance warnings:")
    for warning in approximate.provenance.warnings:
        print(f"  - {warning}")
    print("  collapsed/omitted terms:")
    for term in approximate.report.missing_or_collapsed_terms:
        print(f"  - {term}")
    print(f"  undocumented pylcp defaults used: {approximate.report.undocumented_defaults_used}")

    expected_order = ["lower_F1", "F0", "upper_F1", "F2"]
    actual_order = [level.label for level in model.ground_levels]
    structure_ok = (
        model.ground_state_count == 12
        and model.excited_state_count == 4
        and model.transition_dipole_q.shape == (3, 12, 4)
        and actual_order == expected_order
    )
    print(f"\nRodriguez 12+4 structural validation: {'PASS' if structure_ok else 'FAIL'}")


if __name__ == "__main__":
    main()
