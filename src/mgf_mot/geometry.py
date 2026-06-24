"""Rodriguez quadrupole field and six-beam MOT geometry."""

from math import sqrt
from typing import Iterable

Vector3 = tuple[float, float, float]

_INV_SQRT_2 = 1.0 / sqrt(2.0)

X_PRIME: Vector3 = (_INV_SQRT_2, _INV_SQRT_2, 0.0)
Y_PRIME: Vector3 = (-_INV_SQRT_2, _INV_SQRT_2, 0.0)
Z_AXIS: Vector3 = (0.0, 0.0, 1.0)


def _negative(vector: Vector3) -> Vector3:
    return tuple(-component for component in vector)  # type: ignore[return-value]


MOT_BEAM_DIRECTIONS: dict[str, Vector3] = {
    "+x_prime": X_PRIME,
    "-x_prime": _negative(X_PRIME),
    "+y_prime": Y_PRIME,
    "-y_prime": _negative(Y_PRIME),
    "+z": Z_AXIS,
    "-z": _negative(Z_AXIS),
}


def quadrupole_field(
    position_m: Iterable[float], gradient_t_m: float
) -> Vector3:
    """Return B = B'(-x/2, -y/2, z) in tesla.

    ``position_m`` is a three-component lab-frame position in metres and
    ``gradient_t_m`` is the signed strong-axis gradient in tesla/metre.
    """
    coordinates = tuple(float(value) for value in position_m)
    if len(coordinates) != 3:
        raise ValueError("position_m must contain exactly three components")
    x, y, z = coordinates
    return (
        -0.5 * gradient_t_m * x,
        -0.5 * gradient_t_m * y,
        gradient_t_m * z,
    )

