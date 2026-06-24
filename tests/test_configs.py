from pathlib import Path

import pytest
import yaml


CONFIG_DIR = Path(__file__).parents[1] / "configs"


@pytest.mark.parametrize(
    ("filename", "saturations", "relative", "enabled_count"),
    [
        ("rodriguez_static_3.yaml", [1.45, 1.45, 2.89, 0.0], [0.25, 0.25, 0.50, 0.0], 3),
        ("rodriguez_static_3_plus_1.yaml", [1.45, 1.45, 2.17, 0.72], [0.25, 0.25, 0.375, 0.125], 4),
    ],
)
def test_rodriguez_static_configs(
    filename: str,
    saturations: list[float],
    relative: list[float],
    enabled_count: int,
) -> None:
    config = yaml.safe_load((CONFIG_DIR / filename).read_text(encoding="utf-8"))
    components = config["frequency_components"]
    assert config["beam_model"] == "infinite_plane_wave"
    assert config["magnetic_gradient"] == {"value": 20.0, "unit": "G/cm"}
    assert [item["id"] for item in components] == [1, 2, 3, 4]
    assert [item["saturation"] for item in components] == saturations
    assert [item["relative_saturation"] for item in components] == relative
    assert sum(item.get("enabled", True) for item in components) == enabled_count
    assert sum(relative) == pytest.approx(1.0)
    assert [item["detuning_gamma"] for item in components[:3]] == [-1.0] * 3
    assert components[3]["detuning_gamma"] == 2.0

