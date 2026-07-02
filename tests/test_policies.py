from pathlib import Path

import pytest

from mgf_mot.policies import (
    COMPONENT_ORDER,
    LinearChirpPolicy,
    PolicyValidationError,
    StaticPolicy,
    load_policy,
    policy_from_config,
)
from scripts.inspect_policies import POLICY_INTERFACE_LABEL, run as inspect_policies_run

CONFIG_DIR = Path(__file__).parents[1] / "configs"


def _sample_by_id(policy, t: float):
    sample = policy.sample(t)
    return {component.component_id: component for component in sample.components}


@pytest.mark.parametrize(
    ("filename", "detunings", "saturations", "enabled"),
    [
        (
            "rodriguez_static_3.yaml",
            [-1.0, -1.0, -1.0, 2.0],
            [1.45, 1.45, 2.89, 0.0],
            [True, True, True, False],
        ),
        (
            "rodriguez_static_3_plus_1.yaml",
            [-1.0, -1.0, -1.0, 2.0],
            [1.45, 1.45, 2.17, 0.72],
            [True, True, True, True],
        ),
    ],
)
def test_static_policies_reproduce_existing_static_configs(
    filename: str,
    detunings: list[float],
    saturations: list[float],
    enabled: list[bool],
) -> None:
    policy = load_policy(CONFIG_DIR / filename)
    assert isinstance(policy, StaticPolicy)
    sample = policy.sample(123.0)
    assert sample.component_order == COMPONENT_ORDER
    assert [component.component_id for component in sample.components] == [1, 2, 3, 4]
    assert [component.detuning_gamma for component in sample.components] == detunings
    assert [component.saturation for component in sample.components] == saturations
    assert [component.enabled for component in sample.components] == enabled


def test_linear_chirp_policy_endpoints_and_hold() -> None:
    policy = load_policy(CONFIG_DIR / "rodriguez_baseline_linear_chirp.yaml")
    assert isinstance(policy, LinearChirpPolicy)
    assert policy.chirped_components == (1, 2, 3)
    assert policy.duration_s == pytest.approx(0.001)

    at_start = _sample_by_id(policy, 0.0)
    at_mid = _sample_by_id(policy, 0.0005)
    at_end = _sample_by_id(policy, policy.duration_s)
    after_end = _sample_by_id(policy, 2 * policy.duration_s)

    for component_id in (1, 2, 3):
        assert at_start[component_id].detuning_gamma == -8.0
        assert at_mid[component_id].detuning_gamma == pytest.approx(-4.5)
        assert at_end[component_id].detuning_gamma == -1.0
        assert after_end[component_id].detuning_gamma == -1.0

    assert at_start[4].enabled is False
    assert at_start[4].saturation == 0.0
    assert at_start[4].detuning_gamma == 2.0
    assert policy.component_4_behavior == "explicit_off_during_chirp"


def test_linear_chirp_rejects_invalid_duration() -> None:
    config = {
        "name": "bad_duration",
        "policy_type": "linear_chirp",
        "component_order": [1, 2, 3, 4],
        "detuning_unit": "Gamma",
        "saturation_unit": "saturation_parameter",
        "time_unit": "s",
        "chirp": {
            "components": [1, 2, 3],
            "initial_detuning_gamma": -8.0,
            "final_detuning_gamma": -1.0,
            "duration_s": 0.0,
            "component_4_behavior": "explicit_off_during_chirp",
        },
        "frequency_components": [
            {"id": 1, "detuning_gamma": -8.0, "saturation": 1.0},
            {"id": 2, "detuning_gamma": -8.0, "saturation": 1.0},
            {"id": 3, "detuning_gamma": -8.0, "saturation": 1.0},
            {"id": 4, "enabled": False, "detuning_gamma": 2.0, "saturation": 0.0},
        ],
    }
    with pytest.raises(PolicyValidationError, match="duration"):
        policy_from_config(config)


def test_policy_validation_rejects_bad_units_missing_components_and_negative_saturation() -> None:
    base = {
        "name": "bad_static",
        "policy_type": "static",
        "component_order": [1, 2, 3, 4],
        "detuning_unit": "MHz",
        "saturation_unit": "saturation_parameter",
        "time_unit": "s",
        "frequency_components": [
            {"id": 1, "detuning_gamma": -1.0, "saturation": 1.0},
            {"id": 2, "detuning_gamma": -1.0, "saturation": 1.0},
            {"id": 3, "detuning_gamma": -1.0, "saturation": 1.0},
            {"id": 4, "detuning_gamma": 2.0, "saturation": 0.0},
        ],
    }
    with pytest.raises(PolicyValidationError, match="detuning_unit"):
        policy_from_config(base)

    missing = {**base, "detuning_unit": "Gamma", "frequency_components": base["frequency_components"][:3]}
    with pytest.raises(PolicyValidationError, match="ordered"):
        policy_from_config(missing)

    negative = {
        **base,
        "detuning_unit": "Gamma",
        "frequency_components": [
            *base["frequency_components"][:2],
            {"id": 3, "detuning_gamma": -1.0, "saturation": -0.1},
            base["frequency_components"][3],
        ],
    }
    with pytest.raises(PolicyValidationError, match="negative saturation"):
        policy_from_config(negative)


def test_linear_chirp_rejects_wrong_chirped_components() -> None:
    config = {
        "name": "bad_components",
        "policy_type": "linear_chirp",
        "component_order": [1, 2, 3, 4],
        "detuning_unit": "Gamma",
        "saturation_unit": "saturation_parameter",
        "time_unit": "s",
        "chirp": {
            "components": [1, 2],
            "initial_detuning_gamma": -8.0,
            "final_detuning_gamma": -1.0,
            "duration_s": 0.001,
            "component_4_behavior": "explicit_off_during_chirp",
        },
        "frequency_components": [
            {"id": 1, "detuning_gamma": -8.0, "saturation": 1.0},
            {"id": 2, "detuning_gamma": -8.0, "saturation": 1.0},
            {"id": 3, "detuning_gamma": -8.0, "saturation": 1.0},
            {"id": 4, "enabled": False, "detuning_gamma": 2.0, "saturation": 0.0},
        ],
    }
    with pytest.raises(PolicyValidationError, match="exactly"):
        policy_from_config(config)


def test_inspect_policies_writes_provisional_policy_report(tmp_path, capsys) -> None:
    result = inspect_policies_run(tmp_path)
    output = capsys.readouterr().out
    assert POLICY_INTERFACE_LABEL in output
    assert result["metadata_path"].exists()
    assert result["report_path"].exists()
    assert POLICY_INTERFACE_LABEL in result["metadata_path"].name
    assert POLICY_INTERFACE_LABEL in result["report_path"].name
    report = result["report_path"].read_text(encoding="utf-8")
    assert report.startswith(f"# {POLICY_INTERFACE_LABEL}")
    assert "pure control-schedule plumbing" in report
    assert "not an MgF/Rodriguez reproduction" in report
    assert "Track E exact MgF force readiness remains blocked" in report
    assert len(result["records"]) == 6


def test_no_forbidden_policy_runtime_names() -> None:
    import mgf_mot.policies as policies

    forbidden = ("trajectory", "capture_velocity", "gaussian", "optimizer")
    public_names = [name.lower() for name in dir(policies) if not name.startswith("_")]
    for word in forbidden:
        assert not any(word in name for name in public_names)
