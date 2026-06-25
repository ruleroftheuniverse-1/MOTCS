from dataclasses import replace

import pytest

from mgf_mot.spectroscopy import (
    ALL_SPECTROSCOPY_CONSTANTS,
    EXCITED_BACKEND_B_MHZ,
    EXCITED_BACKEND_C_MHZ,
    EXCITED_BACKEND_P_MHZ,
    EXCITED_BACKEND_Q_MHZ,
    EXCITED_HYPERFINE_D_MHZ,
    GROUND_BACKEND_B_MHZ,
    GROUND_DIPOLAR_C_MHZ,
    GROUND_FERMI_CONTACT_BF_MHZ,
    MissingSpectroscopyConstantError,
)


def test_every_spectroscopy_constant_has_provenance() -> None:
    for constant in ALL_SPECTROSCOPY_CONSTANTS.values():
        assert constant.units
        assert constant.source
        assert constant.locator
        assert constant.status in {
            "exact",
            "derived",
            "approximate",
            "unknown",
            "model_assumption",
        }
        if constant.status == "unknown":
            assert constant.value is None


def test_ground_backend_b_is_a_documented_conversion() -> None:
    expected = GROUND_FERMI_CONTACT_BF_MHZ.require() - GROUND_DIPOLAR_C_MHZ.require() / 3
    assert GROUND_BACKEND_B_MHZ.value == pytest.approx(expected)
    assert GROUND_BACKEND_B_MHZ.status == "derived"


def test_correlated_excited_constants_stay_unknown() -> None:
    for constant in (
        EXCITED_BACKEND_B_MHZ,
        EXCITED_BACKEND_C_MHZ,
        EXCITED_BACKEND_P_MHZ,
        EXCITED_BACKEND_Q_MHZ,
    ):
        assert constant.value is None
        with pytest.raises(MissingSpectroscopyConstantError, match="unknown"):
            constant.require()
    assert EXCITED_HYPERFINE_D_MHZ.value == 135.0


def test_unknown_value_cannot_be_disguised_by_replacement() -> None:
    missing = replace(
        GROUND_BACKEND_B_MHZ,
        value=None,
        status="unknown",
        note="test missing value",
    )
    with pytest.raises(MissingSpectroscopyConstantError, match="ground_backend_b"):
        missing.require()

