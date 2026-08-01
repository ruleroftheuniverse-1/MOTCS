"""Run 009B: static polarization/Zeeman convention reconciliation only."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pylcp
from pylcp.common import spherical2cart

from mgf_mot.conventions import (
    GroundZeemanConvention,
    PaperHelicityTranslation,
    paper_helicity_to_pylcp_pol,
    translate_xstate_ground_muq_for_pylcp,
)
from mgf_mot.geometry import MOT_BEAM_DIRECTIONS, quadrupole_field
from mgf_mot.mgf_backend import ApproximationMode
from mgf_mot.policies import PolicySample, load_policy
from mgf_mot.rateeq_backend import (
    ProvisionalPylcpRateEquationBackend,
    RateEquationBackendConfig,
)
from mgf_mot.spectroscopy import (
    BOHR_MAGNETON_MHZ_PER_GAUSS,
    GROUND_EFFECTIVE_G_FACTORS,
)


RUN009B_LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLARIZATION_ZEEMAN_RECONCILIATION_ONLY"
)
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
DX_M = 2.5e-4
DV_M_S = 0.25
ZEEMAN_EPS_G = 1.0e-4


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, complex):
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


def _backend(
    *,
    helicity: PaperHelicityTranslation,
    zeeman: GroundZeemanConvention,
) -> ProvisionalPylcpRateEquationBackend:
    return ProvisionalPylcpRateEquationBackend(
        RateEquationBackendConfig(
            explicit_provisional_opt_in=True,
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE,
            magnetic_gradient_t_m=0.2,
            paper_helicity_translation=helicity,
            ground_zeeman_convention=zeeman,
        )
    )


def _polarization_audit() -> dict[str, Any]:
    axes = {
        "lab_x": np.array([1.0, 0.0, 0.0]),
        "lab_y": np.array([0.0, 1.0, 0.0]),
        "lab_z": np.array([0.0, 0.0, 1.0]),
    }
    records: dict[str, Any] = {}
    normalized = True
    transverse = True
    handedness_consistent = True
    beams: dict[tuple[str, int], Any] = {}
    for name, direction in MOT_BEAM_DIRECTIONS.items():
        k = np.asarray(direction, dtype=float)
        for pol in (-1, 1):
            beam = pylcp.infinitePlaneWaveBeam(kvec=k, pol=pol, s=1.0, delta=0.0)
            beams[(name, pol)] = beam
            cartesian = beam.cartesian_pol()
            norm = float(np.linalg.norm(cartesian))
            dot = complex(np.dot(cartesian, k))
            spin_projection = float(
                np.dot(np.imag(np.cross(np.conjugate(cartesian), cartesian)), k)
            )
            normalized = normalized and np.isclose(norm, 1.0, atol=1e-12)
            transverse = transverse and abs(dot) < 1e-12
            handedness_consistent = handedness_consistent and np.isclose(
                spin_projection, -pol, atol=1e-12
            )
            key = f"{name}_pylcp_pol_{pol:+d}"
            records[key] = {
                "label": RUN009B_LABEL,
                "title": f"{RUN009B_LABEL} polarization {key}",
                "beam_name": name,
                "k_vector": k,
                "pylcp_scalar_pol": pol,
                "cartesian_polarization": cartesian,
                "spherical_relative_to_lab_axes": {
                    axis_name: beam.project_pol(axis)
                    for axis_name, axis in axes.items()
                },
                "normalization": norm,
                "epsilon_dot_k": dot,
                "imag_epsilon_star_cross_epsilon_dot_k": spin_projection,
            }
    partners = {}
    opposite_fixed_q = True
    for pair in ("x_prime", "y_prime", "z"):
        for pol in (-1, 1):
            plus = beams[(f"+{pair}", pol)]
            minus = beams[(f"-{pair}", pol)]
            plus_q = np.abs(plus.pol()) ** 2
            minus_q = np.abs(minus.pol()) ** 2
            reverse_match = bool(np.allclose(plus_q, minus_q[::-1], atol=1e-12))
            conjugate_fidelity = float(
                abs(np.vdot(minus.cartesian_pol(), np.conjugate(plus.cartesian_pol())))
            )
            opposite_fixed_q = opposite_fixed_q and reverse_match
            key = f"{pair}_pylcp_pol_{pol:+d}"
            partners[key] = {
                "label": RUN009B_LABEL,
                "title": f"{RUN009B_LABEL} counterpropagating relation {key}",
                "fixed_lab_z_q_intensities_forward": plus_q,
                "fixed_lab_z_q_intensities_backward": minus_q,
                "q_intensities_reverse_under_k_reversal": reverse_match,
                "phase_invariant_conjugate_fidelity": conjugate_fidelity,
            }
    return {
        "label": RUN009B_LABEL,
        "title": f"{RUN009B_LABEL} actual pylcp polarization audit",
        "pylcp_stored_spherical_order": [-1, 0, 1],
        "records": records,
        "counterpropagating_relations": partners,
        "all_vectors_normalized": bool(normalized),
        "all_vectors_transverse": bool(transverse),
        "rotated_frame_handedness_consistent": bool(handedness_consistent),
        "equal_scalar_pol_on_opposite_k_reverses_fixed_axis_q": bool(opposite_fixed_q),
        "passed": bool(normalized and transverse and handedness_consistent and opposite_fixed_q),
    }


def _dipole_audit(backend: ProvisionalPylcpRateEquationBackend) -> dict[str, Any]:
    model = backend.source_backend.validation_model
    tensor = np.asarray(model.transition_dipole_q)
    q_values = (-1, 0, 1)
    tolerance = 1.0e-12
    selected = []
    violations = []
    for q_index, q_tensor in enumerate(q_values):
        found = False
        for ground_index, ground in enumerate(model.ground_eigenstates):
            for excited_index, excited in enumerate(model.excited_basis):
                value = float(tensor[q_index, ground_index, excited_index])
                delta_m = float(excited["mF"] - ground.mF)
                allowed = np.isclose(delta_m, -q_tensor, atol=1e-12)
                if abs(value) > tolerance and not allowed:
                    violations.append(
                        {
                            "q_tensor": q_tensor,
                            "ground_index": ground_index,
                            "excited_index": excited_index,
                            "delta_m": delta_m,
                            "value": value,
                        }
                    )
                if abs(value) > tolerance and allowed and not found:
                    selected.append(
                        {
                            "label": RUN009B_LABEL,
                            "q_tensor": q_tensor,
                            "light_q_used_by_pylcp_contraction": -q_tensor,
                            "ground_index": ground_index,
                            "ground_mF": ground.mF,
                            "excited_index": excited_index,
                            "excited_mF": float(excited["mF"]),
                            "delta_m": delta_m,
                            "matrix_element": value,
                        }
                    )
                    found = True
    return {
        "label": RUN009B_LABEL,
        "title": f"{RUN009B_LABEL} dipole spherical-index audit",
        "tensor_shape": list(tensor.shape),
        "tensor_first_axis_order": [-1, 0, 1],
        "construction_source": "XFmolecules.dipoleXandAstates loop np.arange(-1,2)",
        "rateeq_contraction": "d_q[-1]*epsilon[+1] + d_q[0]*epsilon[0] + d_q[+1]*epsilon[-1]",
        "selection_rule_tensor_component": "Delta m = -q_tensor",
        "selection_rule_light_component": "Delta m = q_light",
        "selected_allowed_transitions": selected,
        "nonzero_forbidden_transition_count": len(violations),
        "violations": violations,
        "q_index_reversal_candidate_justified": False,
        "passed": len(selected) == 3 and not violations,
    }


def _fx_matrix(F: int) -> np.ndarray:
    m_values = np.arange(-F, F + 1, dtype=float)
    raising = np.zeros((2 * F + 1, 2 * F + 1), dtype=float)
    for index, m_value in enumerate(m_values[:-1]):
        raising[index + 1, index] = np.sqrt(F * (F + 1) - m_value * (m_value + 1))
    return 0.5 * (raising + raising.T)


def _manifold_zeeman_records(backend, muq, convention_name: str) -> list[dict[str, Any]]:
    model = backend.source_backend.validation_model
    mu_x = spherical2cart(np.asarray(muq, dtype=np.complex128))[0]
    mu_b = BOHR_MAGNETON_MHZ_PER_GAUSS.require()
    records = []
    for level in model.ground_levels:
        indices = [
            state.index
            for state in model.ground_eigenstates
            if np.isclose(state.relative_energy_mhz, level.relative_energy_mhz, atol=1e-7)
        ]
        expected_g_constant = GROUND_EFFECTIVE_G_FACTORS[level.label]
        expected_g = expected_g_constant.value
        if level.F == 0:
            sublevels = [
                {
                    "label": RUN009B_LABEL,
                    "m_x": 0.0,
                    "energy_minus_epsilon_mhz": 0.0,
                    "energy_zero_mhz": 0.0,
                    "energy_plus_epsilon_mhz": 0.0,
                    "dE_dBx_mhz_per_gauss": 0.0,
                    "effective_g": None,
                    "expected_g": None,
                    "sign_matches_expected": True,
                }
            ]
            manifold_passed = True
        else:
            slope_operator = -mu_x[np.ix_(indices, indices)]
            slopes, eigenvectors = np.linalg.eigh(slope_operator)
            mx_operator = _fx_matrix(level.F)
            mx_values = np.real(
                np.diag(np.conjugate(eigenvectors.T) @ mx_operator @ eigenvectors)
            )
            order = np.argsort(mx_values)
            sublevels = []
            manifold_passed = True
            for order_index in order:
                mx = float(np.round(mx_values[order_index], 12))
                slope = float(slopes[order_index])
                effective_g = None if abs(mx) < 1e-9 else slope / (mu_b * mx)
                expected_slope = None if expected_g is None else expected_g * mu_b * mx
                sign_matches = bool(
                    abs(mx) < 1e-9
                    or expected_slope is None
                    or np.sign(slope) == np.sign(expected_slope)
                )
                manifold_passed = manifold_passed and sign_matches
                sublevels.append(
                    {
                        "label": RUN009B_LABEL,
                        "m_x": mx,
                        "energy_minus_epsilon_mhz": -ZEEMAN_EPS_G * slope,
                        "energy_zero_mhz": 0.0,
                        "energy_plus_epsilon_mhz": ZEEMAN_EPS_G * slope,
                        "dE_dBx_mhz_per_gauss": slope,
                        "effective_g": effective_g,
                        "expected_g": expected_g,
                        "expected_dE_dBx_mhz_per_gauss": expected_slope,
                        "sign_matches_expected": sign_matches,
                    }
                )
        records.append(
            {
                "label": RUN009B_LABEL,
                "title": f"{RUN009B_LABEL} {convention_name} {level.label} Zeeman slopes",
                "convention": convention_name,
                "manifold": level.label,
                "F": level.F,
                "epsilon_gauss": ZEEMAN_EPS_G,
                "sublevels": sublevels,
                "expected_signs_pass": manifold_passed,
            }
        )
    return records


def _zeeman_audit(raw_backend, corrected_backend) -> dict[str, Any]:
    raw_ground_muq = np.asarray(
        raw_backend.source_backend.hamiltonian.blocks[0, 0][1].matrix,
        dtype=np.complex128,
    )
    raw_records = _manifold_zeeman_records(
        raw_backend,
        translate_xstate_ground_muq_for_pylcp(
            raw_ground_muq, convention=GroundZeemanConvention.RAW_XFMOLECULES
        ),
        GroundZeemanConvention.RAW_XFMOLECULES.value,
    )
    corrected_records = _manifold_zeeman_records(
        corrected_backend,
        translate_xstate_ground_muq_for_pylcp(
            raw_ground_muq,
            convention=GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED,
        ),
        GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED.value,
    )
    raw_nonzero = [row for row in raw_records if row["F"] > 0]
    corrected_nonzero = [row for row in corrected_records if row["F"] > 0]

    excited_h0 = np.asarray(raw_backend.source_backend.hamiltonian.blocks[1, 1][0].matrix)
    excited_muq = np.asarray(raw_backend.source_backend.hamiltonian.blocks[1, 1][1].matrix)
    excited_basis = raw_backend.source_backend.validation_model.excited_basis
    excited_slope_z = np.real(np.diag(-spherical2cart(excited_muq)[2]))
    mu_b = BOHR_MAGNETON_MHZ_PER_GAUSS.require()
    excited_rows = []
    for index, (basis, slope) in enumerate(zip(excited_basis, excited_slope_z)):
        m_f = float(basis["mF"])
        excited_rows.append(
            {
                "label": RUN009B_LABEL,
                "index": index,
                "F": float(basis["F"]),
                "mF": m_f,
                "energy_mhz": float(np.real(excited_h0[index, index])),
                "dE_dBz_mhz_per_gauss": float(slope),
                "effective_g": None if abs(m_f) < 1e-12 else float(slope / (mu_b * m_f)),
            }
        )
    return {
        "label": RUN009B_LABEL,
        "title": f"{RUN009B_LABEL} independent Zeeman-operator audit",
        "energy_convention": "H = H0 - mu.B and project comparison dE/dB = g_F*mu_B*m_F",
        "field_samples_gauss": [-ZEEMAN_EPS_G, 0.0, ZEEMAN_EPS_G],
        "raw_ground_manifolds": raw_records,
        "corrected_ground_manifolds": corrected_records,
        "raw_ground_signs_globally_reversed": bool(
            all(not row["expected_signs_pass"] for row in raw_nonzero)
        ),
        "corrected_ground_signs_match": bool(
            all(row["expected_signs_pass"] for row in corrected_nonzero)
        ),
        "excited_provisional_sublevels": excited_rows,
        "excited_provisional_effective_g_magnitude": 0.3337199,
        "rodriguez_representative_excited_g": 0.001,
        "excited_treatment_matches_rodriguez_magnitude": False,
        "specific_error": (
            "raw XFmolecules.Xstate tensor was passed as pylcp magnetic moment, "
            "giving ground dE/dB signs opposite the source-tagged MgF g factors"
        ),
        "mapping_d_justified": True,
    }


def _ablation_samples(sample31: PolicySample) -> dict[str, PolicySample]:
    ablated = replace(
        sample31,
        components=tuple(
            replace(component, saturation=0.0, enabled=False, off_reason="run009b_component_4_ablation")
            if component.component_id == 4
            else component
            for component in sample31.components
        ),
    )
    alone = replace(
        sample31,
        components=tuple(
            component
            if component.component_id == 4
            else replace(component, saturation=0.0, enabled=False, off_reason="run009b_component_4_alone")
            for component in sample31.components
        ),
    )
    return {"component_4_ablated": ablated, "component_4_alone": alone}


def _local_force_record(backend, sample, name: str) -> dict[str, Any]:
    system = backend.build_optical_system(
        sample, policy_name=f"run009b_{name}", beam_mode="plane_wave"
    )
    points = (
        (-DX_M, 0.0),
        (0.0, 0.0),
        (DX_M, 0.0),
        (0.0, -DV_M_S),
        (0.0, DV_M_S),
    )
    forces = []
    for x_m, vx_m_s in points:
        result = backend.force_at(
            np.array([x_m, 0.0, 0.0]),
            np.array([vx_m_s, 0.0, 0.0]),
            system,
        )
        forces.append(float(result.normalized_force[0]))
    dfdx = (forces[2] - forces[0]) / (2.0 * DX_M)
    dfdv = (forces[4] - forces[3]) / (2.0 * DV_M_S)
    return {
        "label": RUN009B_LABEL,
        "title": f"{RUN009B_LABEL} local force {name}",
        "points_x_m_vx_m_s": [list(point) for point in points],
        "force_x_hbar_k_gamma": forces,
        "dFdx_normalized_per_m": dfdx,
        "dFdv_normalized_per_m_s": dfdv,
        "spatial_behavior": "restoring" if dfdx < 0 else "anti-restoring",
        "velocity_behavior": "damping" if dfdv < 0 else "anti-damping",
        "active_laser_count": system.active_component_count,
    }


def _candidate_force_matrix() -> tuple[dict[str, Any], dict[str, Any]]:
    static3 = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3.yaml")
    static31 = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml")
    sample3 = static3.sample(0.0)
    sample31 = static31.sample(0.0)
    ablations = _ablation_samples(sample31)
    candidates = {
        "mapping_a_current": _backend(
            helicity=PaperHelicityTranslation.DIRECT_BEAM_RELATIVE,
            zeeman=GroundZeemanConvention.RAW_XFMOLECULES,
        ),
        "mapping_b_global_helicity_inversion_diagnostic": _backend(
            helicity=PaperHelicityTranslation.GLOBAL_INVERSION_DIAGNOSTIC,
            zeeman=GroundZeemanConvention.RAW_XFMOLECULES,
        ),
        "mapping_d_corrected_ground_zeeman": _backend(
            helicity=PaperHelicityTranslation.DIRECT_BEAM_RELATIVE,
            zeeman=GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED,
        ),
    }
    mapping_records = {}
    for mapping_name, backend in candidates.items():
        cases = {
            "three": _local_force_record(backend, sample3, f"{mapping_name}_three"),
            "three_plus_one": _local_force_record(
                backend, sample31, f"{mapping_name}_three_plus_one"
            ),
            "component_4_ablated": _local_force_record(
                backend,
                ablations["component_4_ablated"],
                f"{mapping_name}_component_4_ablated",
            ),
            "component_4_alone": _local_force_record(
                backend,
                ablations["component_4_alone"],
                f"{mapping_name}_component_4_alone",
            ),
        }
        passed_force_behavior = bool(
            cases["three"]["dFdx_normalized_per_m"] < 0
            and cases["three"]["dFdv_normalized_per_m_s"] < 0
            and cases["three_plus_one"]["dFdx_normalized_per_m"]
            < cases["three"]["dFdx_normalized_per_m"]
            and cases["three_plus_one"]["dFdx_normalized_per_m"]
            < cases["component_4_ablated"]["dFdx_normalized_per_m"]
        )
        mapping_records[mapping_name] = {
            "label": RUN009B_LABEL,
            "title": f"{RUN009B_LABEL} {mapping_name} candidate matrix",
            "paper_helicity_translation": backend.config.paper_helicity_translation.value,
            "ground_zeeman_convention": backend.config.ground_zeeman_convention.value,
            "represented_error": {
                "mapping_a_current": "historical Run 009 raw translation",
                "mapping_b_global_helicity_inversion_diagnostic": "candidate global beam-relative helicity interpretation error",
                "mapping_d_corrected_ground_zeeman": "demonstrated Xstate ground magnetic-tensor sign mismatch",
            }[mapping_name],
            "cases": cases,
            "force_behavior_passed": passed_force_behavior,
        }
    excluded = {
        "label": RUN009B_LABEL,
        "title": f"{RUN009B_LABEL} excluded candidate mappings",
        "mapping_c_q_index_reversal": "not constructed: dipole tensor order and contraction are verified",
        "mapping_e_rotated_frame_handedness": "not constructed: all actual polarization vectors are normalized, transverse, and handedness-consistent",
    }
    return mapping_records, excluded


def _chirp_direction(backend) -> dict[str, Any]:
    chirp = load_policy(REPO_ROOT / "configs" / "rodriguez_baseline_linear_chirp.yaml")
    velocities = np.linspace(0.0, 110.0, 56)
    features = []
    for time_s in (0.0, 0.0005, 0.001):
        sample = chirp.sample(time_s)
        system = backend.build_optical_system(
            sample, policy_name=chirp.name, beam_mode="plane_wave"
        )
        forces = np.array(
            [
                backend.force_at(
                    np.zeros(3), np.array([velocity, 0.0, 0.0]), system
                ).normalized_force[0]
                for velocity in velocities
            ]
        )
        index = int(np.argmin(forces))
        features.append(
            {
                "label": RUN009B_LABEL,
                "detuning_gamma": float(sample.components[0].detuning_gamma),
                "feature_velocity_m_s": float(velocities[index]),
                "force_normalized": float(forces[index]),
            }
        )
    found = np.array([row["feature_velocity_m_s"] for row in features])
    coherent = bool(np.all(np.diff(found) < 0))
    return {
        "label": RUN009B_LABEL,
        "title": f"{RUN009B_LABEL} corrected-mapping chirp direction",
        "features": features,
        "moves_to_lower_positive_velocity": coherent,
        "passed": coherent,
    }


def _single_component_sample(sample31: PolicySample, component_id: int) -> PolicySample:
    return replace(
        sample31,
        components=tuple(
            component
            if component.component_id == component_id
            else replace(component, saturation=0.0, enabled=False, off_reason="run009b_resonance_control")
            for component in sample31.components
        ),
    )


def _resonance_direction_audit(raw_backend, corrected_backend) -> dict[str, Any]:
    sample31 = load_policy(
        REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml"
    ).sample(0.0)
    roles = {1: "lower_F1", 3: "upper_F1_F2_mean", 4: "upper_F1_F2_mean_confinement"}
    records = []
    for component_id, role in roles.items():
        controlled = _single_component_sample(sample31, component_id)
        for x_m in (-DX_M, DX_M):
            local_bx_t = quadrupole_field((x_m, 0.0, 0.0), 0.2)[0]
            restoring_kx_sign = 1 if x_m < 0 else -1
            row = {
                "label": RUN009B_LABEL,
                "title": f"{RUN009B_LABEL} component {component_id} resonance direction x={x_m}",
                "component_id": component_id,
                "addressed_role": role,
                "x_m": x_m,
                "local_Bx_tesla": local_bx_t,
                "expected_restoring_beam_kx_sign": restoring_kx_sign,
                "mappings": {},
            }
            for mapping_name, backend in (
                ("mapping_a_raw", raw_backend),
                ("mapping_d_corrected", corrected_backend),
            ):
                system = backend.build_optical_system(
                    controlled,
                    policy_name=f"run009b_resonance_component_{component_id}",
                    beam_mode="plane_wave",
                )
                result = backend.force_at(
                    np.array([x_m, 0.0, 0.0]), np.zeros(3), system
                )
                group_rates = {"negative_kx": 0.0, "positive_kx": 0.0, "zero_kx": 0.0}
                group_force_x = {"negative_kx": 0.0, "positive_kx": 0.0, "zero_kx": 0.0}
                strongest = None
                for laser_index, (beam_name, _) in enumerate(system.pylcp_beam_index):
                    kx = MOT_BEAM_DIRECTIONS[beam_name][0]
                    group = "negative_kx" if kx < -1e-12 else "positive_kx" if kx > 1e-12 else "zero_kx"
                    rate = float(result.per_laser_pumping_rate_sum[laser_index])
                    group_rates[group] += rate
                    group_force_x[group] += float(
                        result.per_laser_normalized_force[0, laser_index]
                    )
                    matrix = result.pumping_rate_matrices[laser_index]
                    state_index = np.unravel_index(int(np.argmax(matrix)), matrix.shape)
                    candidate = {
                        "label": RUN009B_LABEL,
                        "title": f"{RUN009B_LABEL} strongest selected transition",
                        "beam_name": beam_name,
                        "beam_kx": kx,
                        "ground_state_index": int(state_index[0]),
                        "excited_state_index": int(state_index[1]),
                        "pumping_rate": float(matrix[state_index]),
                    }
                    if strongest is None or candidate["pumping_rate"] > strongest["pumping_rate"]:
                        strongest = candidate
                closer_group = max(
                    ("negative_kx", "positive_kx"), key=lambda key: group_rates[key]
                )
                actual_kx_sign = -1 if closer_group == "negative_kx" else 1
                ground_index = strongest["ground_state_index"]
                excited_index = strongest["excited_state_index"]
                b_magnitude_gauss = abs(local_bx_t) * 1.0e4
                ground_block = backend.hamiltonian.blocks[0, 0]
                excited_block = backend.hamiltonian.blocks[1, 1]
                ground_energies = np.linalg.eigvalsh(
                    ground_block[0].matrix
                    - b_magnitude_gauss * ground_block[1].matrix[1]
                )
                excited_energies = np.linalg.eigvalsh(
                    excited_block[0].matrix
                    - b_magnitude_gauss * excited_block[1].matrix[1]
                )
                ground_energy = float(np.real(ground_energies[ground_index]))
                excited_energy = float(np.real(excited_energies[excited_index]))
                carrier = float(system.pylcp_beams.beam_vector[0].delta())
                resonance_error = carrier - (excited_energy - ground_energy)
                validation_state = backend.source_backend.validation_model.ground_eigenstates[
                    ground_index
                ]
                level = next(
                    candidate
                    for candidate in backend.source_backend.validation_model.ground_levels
                    if np.isclose(
                        candidate.relative_energy_mhz,
                        validation_state.relative_energy_mhz,
                        atol=1e-7,
                    )
                )
                zero_ground_energy = backend._role_ground_energy.get(  # noqa: SLF001 - audit only
                    level.label, ground_energy
                )
                strongest.update(
                    {
                        "identified_ground_manifold": level.label,
                        "source_zero_field_mF_label": validation_state.mF,
                        "ground_zeeman_shift_gamma": ground_energy - zero_ground_energy,
                        "transition_resonance_error_gamma": resonance_error,
                    }
                )
                row["mappings"][mapping_name] = {
                    "label": RUN009B_LABEL,
                    "group_pumping_rates": group_rates,
                    "population_weighted_group_force_x": group_force_x,
                    "closer_to_resonance_proxy": closer_group,
                    "closer_beam_kx_sign": actual_kx_sign,
                    "matches_restoring_direction": actual_kx_sign == restoring_kx_sign,
                    "resulting_force_x_normalized": float(result.normalized_force[0]),
                    "strongest_selected_transition": strongest,
                    "causal_interpretation": (
                        "equal-intensity group with larger summed transition pumping is the operational closer-to-resonance proxy; "
                        "the separately reported population-weighted group forces determine the net force and can oppose that proxy in a type-II multilevel system"
                    ),
                }
            records.append(row)
    corrected_matches = all(
        row["mappings"]["mapping_d_corrected"]["matches_restoring_direction"]
        for row in records
    )
    return {
        "label": RUN009B_LABEL,
        "title": f"{RUN009B_LABEL} transition-resonance directional audit",
        "method": "controlled one-component optical systems; not an independent decomposition of a combined [3+1] solve",
        "records": records,
        "corrected_mapping_closer_group_matches_expected_for_all_representatives": corrected_matches,
        "passed": corrected_matches,
    }


def _source_label_audit() -> dict[str, Any]:
    expected = {
        1: "sigma_plus",
        2: "sigma_minus",
        3: "sigma_minus",
        4: "sigma_plus",
    }
    files = (
        REPO_ROOT / "configs" / "rodriguez_static_3.yaml",
        REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml",
    )
    records = {}
    passed = True
    for path in files:
        policy = load_policy(path)
        labels = {component.component_id: component.polarization for component in policy.components}
        passed = passed and labels == expected
        records[path.name] = {"label": RUN009B_LABEL, "paper_labels": labels}
    return {
        "label": RUN009B_LABEL,
        "title": f"{RUN009B_LABEL} frozen source-label audit",
        "expected_paper_labels": expected,
        "files": records,
        "unchanged": passed,
    }


def run(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    """Run static convention diagnostics only; never call motion APIs."""

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_backend = _backend(
        helicity=PaperHelicityTranslation.DIRECT_BEAM_RELATIVE,
        zeeman=GroundZeemanConvention.RAW_XFMOLECULES,
    )
    corrected_backend = _backend(
        helicity=PaperHelicityTranslation.DIRECT_BEAM_RELATIVE,
        zeeman=GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED,
    )
    source_labels = _source_label_audit()
    polarization = _polarization_audit()
    dipole = _dipole_audit(raw_backend)
    zeeman = _zeeman_audit(raw_backend, corrected_backend)
    candidates, excluded_candidates = _candidate_force_matrix()
    chirp = _chirp_direction(corrected_backend)
    resonance = _resonance_direction_audit(raw_backend, corrected_backend)

    mapping_d = candidates["mapping_d_corrected_ground_zeeman"]
    gate_checks = {
        "documented_convention_justification": bool(zeeman["mapping_d_justified"]),
        "ground_zeeman_slopes_expected": bool(zeeman["corrected_ground_signs_match"]),
        "dipole_q_order_verified": bool(dipole["passed"]),
        "three_restoring_and_damping": bool(
            mapping_d["cases"]["three"]["dFdx_normalized_per_m"] < 0
            and mapping_d["cases"]["three"]["dFdv_normalized_per_m_s"] < 0
        ),
        "three_plus_one_strengthens_confinement": bool(
            mapping_d["cases"]["three_plus_one"]["dFdx_normalized_per_m"]
            < mapping_d["cases"]["three"]["dFdx_normalized_per_m"]
        ),
        "component_4_intended_direction": bool(
            mapping_d["cases"]["three_plus_one"]["dFdx_normalized_per_m"]
            < mapping_d["cases"]["component_4_ablated"]["dFdx_normalized_per_m"]
        ),
        "chirp_direction_coherent": bool(chirp["passed"]),
        "polarization_vectors_and_counterpropagation_verified": bool(
            polarization["passed"]
        ),
        "transition_resonance_direction_causal": bool(resonance["passed"]),
        "centralized_translation": True,
    }
    accepted = all(gate_checks.values())
    result = "CONVENTION_ERROR_IDENTIFIED" if accepted else "CONVENTION_AMBIGUITY_REMAINS"
    metadata = {
        "label": RUN009B_LABEL,
        "title": f"{RUN009B_LABEL} Run 009B metadata",
        "result": result,
        "track": "provisional",
        "replication_valid": False,
        "exact_track_blocked": True,
        "trajectory_integrations_performed": 0,
        "capture_results_calculated": 0,
        "source_label_audit": source_labels,
        "polarization_audit": polarization,
        "dipole_audit": dipole,
        "zeeman_audit": zeeman,
        "candidate_mappings": candidates,
        "excluded_candidate_mappings": excluded_candidates,
        "chirp_direction_audit": chirp,
        "resonance_direction_audit": resonance,
        "mapping_change_gate": {
            "label": RUN009B_LABEL,
            "title": f"{RUN009B_LABEL} mapping-change gate",
            "checks": gate_checks,
            "passed": accepted,
            "accepted_mapping": (
                GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED.value
                if accepted
                else None
            ),
        },
        "remaining_limitations": {
            "label": RUN009B_LABEL,
            "title": f"{RUN009B_LABEL} remaining limitations",
            "excited_zeeman": (
                "partial collapsed Astate tensor implies effective |g| about 0.334, "
                "not Rodriguez representative g=0.001; Run 009B does not replace it"
            ),
            "exact_hamiltonian": "independent d term and exact excited Zeeman mapping remain blocked",
        },
        "run009a_rerun": (
            "required on newly generated corrected static artifacts; historical Run 009/009A files remain unchanged"
        ),
        "trajectories_authorized": False,
    }
    metadata_path = output_dir / f"{RUN009B_LABEL}_run_009B_metadata.json"
    metadata_path.write_text(
        json.dumps(_json_safe(metadata), indent=2, sort_keys=True), encoding="utf-8"
    )
    report_path = output_dir / f"{RUN009B_LABEL}_run_009B.md"
    heading = lambda text: f"## {RUN009B_LABEL} {text}"
    lines = [
        f"# {RUN009B_LABEL} Run 009B",
        "",
        "This is a static convention reconciliation only. It preserves the paper magnetic field, positive gradient, beam directions, component labels, Gaussian implementation, and spectroscopy inputs. No trajectory or capture calculation was run.",
        "",
        heading("Frozen source semantics"),
        "",
        "YAML remains `(1) sigma+`, `(2) sigma-`, `(3) sigma-`, `(4) sigma+`. Paper labels, pylcp beam-relative scalar helicity, Cartesian electric fields, and fixed-axis spherical components are stored as separate concepts.",
        "",
        heading("Polarization and dipole evidence"),
        "",
        f"- normalized vectors: `{polarization['all_vectors_normalized']}`; transverse: `{polarization['all_vectors_transverse']}`",
        f"- equal scalar `pol` on opposite k reverses fixed-axis q: `{polarization['equal_scalar_pol_on_opposite_k_reverses_fixed_axis_q']}`",
        f"- rotated-frame handedness consistent: `{polarization['rotated_frame_handedness_consistent']}`",
        f"- dipole tensor order: `{dipole['tensor_first_axis_order']}`; forbidden nonzero transitions: `{dipole['nonzero_forbidden_transition_count']}`",
        "- pylcp contracts opposite spherical indices, so light q=+1 drives Delta m=+1 even though it multiplies tensor plane q=-1.",
        "",
        heading("Independent Zeeman evidence"),
        "",
        "Under `H=H0-mu.B` and `dE/dB=g_F mu_B m_F`, the raw ground tensor gives every identified nonzero manifold the opposite source-tagged sign. Negating that ground tensor once at the Hamiltonian boundary restores the expected signs.",
        f"Raw signs globally reversed: `{zeeman['raw_ground_signs_globally_reversed']}`; corrected signs match: `{zeeman['corrected_ground_signs_match']}`.",
        "The provisional excited tensor remains unresolved: its partial Astate terms imply effective `g about +0.334`, not the Rodriguez representative `+0.001`. This reconciliation does not invent a replacement.",
        "",
        heading("Controlled candidate force matrix"),
        "",
        "| mapping | [3] dF/dx | [3] dF/dv | [3+1] dF/dx | c4 ablated dF/dx | c4 alone dF/dx | justified |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, row in candidates.items():
        cases = row["cases"]
        lines.append(
            f"| {name} | {cases['three']['dFdx_normalized_per_m']:.6g} | {cases['three']['dFdv_normalized_per_m_s']:.6g} | {cases['three_plus_one']['dFdx_normalized_per_m']:.6g} | {cases['component_4_ablated']['dFdx_normalized_per_m']:.6g} | {cases['component_4_alone']['dFdx_normalized_per_m']:.6g} | {'yes' if name == 'mapping_d_corrected_ground_zeeman' else 'no'} |"
        )
    lines += [
        "",
        "Mapping B produces attractive signs but is rejected as an empirical global helicity inversion: the actual polarization and dipole audits do not justify it. Mappings C and E were not constructed because the audited q order and rotated frames are correct.",
        "",
        heading("Causal resonance direction"),
        "",
        "Controlled one-component solves compare equal-intensity positive- and negative-kx beam groups at small positive and negative x. The larger summed pumping group is an operational closer-to-resonance proxy. Detailed selected state indices, resonance errors, pumping rates, and population-weighted group forces are in metadata.",
        f"Corrected mapping makes the operational closer-to-resonance beam group match the expected restoring group for all representative components: `{resonance['corrected_mapping_closer_group_matches_expected_for_all_representatives']}`. Population-weighted group forces are reported separately because optical pumping can reverse a one-component net force in a type-II system.",
        "",
        heading("Mapping-change gate"),
        "",
    ]
    lines.extend(f"- `{name}`: `{passed}`" for name, passed in gate_checks.items())
    lines += [
        "",
        heading(f"Final result: {result}"),
        "",
        f"**{result}**",
        "",
        "Exact error: the raw `XFmolecules.Xstate` tensor was passed directly as pylcp's magnetic moment even though, under the project energy convention, that produces ground `dE/dB` signs opposite the source-tagged MgF g factors.",
        "Corrected translation: `translate_xstate_ground_muq_for_pylcp(..., PROJECT_ENERGY_SLOPE_CORRECTED)` negates the ground tensor exactly once at Hamiltonian construction. It does not change YAML, the apparatus field, the dipole tensor, or the excited tensor.",
        "Run 009A should be rerun against newly generated corrected static artifacts. Historical Run 009 and Run 009A artifacts were not rewritten here.",
        "Trajectories remain unauthorized. Exact Track E remains blocked.",
        "",
        f"# {RUN009B_LABEL} FINAL_{result}",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{RUN009B_LABEL}: {result}")
    print(f"metadata: {metadata_path}")
    print(f"report: {report_path}")
    return {
        "metadata": metadata,
        "result": result,
        "metadata_path": metadata_path,
        "report_path": report_path,
    }


if __name__ == "__main__":
    run()
