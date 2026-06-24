from math import isclose, sqrt

import pytest

from mgf_mot.geometry import MOT_BEAM_DIRECTIONS, X_PRIME, Y_PRIME, quadrupole_field


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b))


def test_rotated_axes_are_orthonormal_and_at_45_degrees() -> None:
    assert isclose(_dot(X_PRIME, X_PRIME), 1.0)
    assert isclose(_dot(Y_PRIME, Y_PRIME), 1.0)
    assert isclose(_dot(X_PRIME, Y_PRIME), 0.0, abs_tol=1e-15)
    assert isclose(_dot(X_PRIME, (1.0, 0.0, 0.0)), 1 / sqrt(2))


def test_six_beams_are_unit_vectors_in_opposite_pairs() -> None:
    assert len(MOT_BEAM_DIRECTIONS) == 6
    for axis in ("x_prime", "y_prime", "z"):
        forward = MOT_BEAM_DIRECTIONS[f"+{axis}"]
        backward = MOT_BEAM_DIRECTIONS[f"-{axis}"]
        assert isclose(_dot(forward, forward), 1.0)
        assert backward == tuple(-component for component in forward)


def test_quadrupole_field_and_gradient_sign() -> None:
    position = (0.01, -0.02, 0.03)
    assert quadrupole_field(position, 0.2) == pytest.approx((-0.001, 0.002, 0.006))
    flipped = quadrupole_field(position, -0.2)
    nominal = quadrupole_field(position, 0.2)
    assert flipped == pytest.approx(tuple(-value for value in nominal))


def test_quadrupole_is_divergence_free() -> None:
    gradient = 0.2
    diagonal_derivatives = (-gradient / 2, -gradient / 2, gradient)
    assert isclose(sum(diagonal_derivatives), 0.0, abs_tol=1e-15)


def test_quadrupole_rejects_non_3d_positions() -> None:
    with pytest.raises(ValueError, match="exactly three"):
        quadrupole_field((1.0, 2.0), 0.2)

