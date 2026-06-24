from math import isclose, pi

from mgf_mot.constants import (
    EXCITED_HYPERFINE_SPLITTING_MHZ,
    GROUND_HYPERFINE_LEVELS,
    MGF,
    RODRIGUEZ_STATIC,
)


def test_published_mgf_scales() -> None:
    assert isclose(MGF.natural_linewidth_rad_s, 2 * pi * 20.9e6)
    assert isclose(MGF.wavelength_m, 359.33e-9, rel_tol=2e-4)
    assert isclose(MGF.natural_linewidth_rad_s / MGF.wave_number_rad_m, 7.515, rel_tol=3e-3)
    assert MGF.saturation_intensity_w_m2 == 600.0


def test_state_counts_and_static_scales() -> None:
    assert MGF.ground_state_count + MGF.excited_state_count == 16
    assert isclose(RODRIGUEZ_STATIC.gradient_t_m, 0.2)
    assert isclose(RODRIGUEZ_STATIC.position_unit_m, 7.48e-3)


def test_only_paper_reported_spectroscopy_values_are_encoded() -> None:
    assert [level.spacing_from_previous_mhz for level in GROUND_HYPERFINE_LEVELS] == [
        None,
        109.0,
        120.0,
        9.0,
    ]
    assert [level.g_factor for level in GROUND_HYPERFINE_LEVELS] == [-0.2, None, 0.7, 0.5]
    assert EXCITED_HYPERFINE_SPLITTING_MHZ is None
