"""Compare two validated Run 012 molecular-model packages."""

from dataclasses import asdict
import argparse
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]; SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))
from mgf_mot.molecular_model_package import RUN012_LABEL, compare_packages, load_package  # noqa: E402

DEFAULT = ROOT / "outputs/provisional/molecular_model_packages/run_012" / f"{RUN012_LABEL}_ACCEPTED_PROVISIONAL_REFERENCE_PACKAGE"

def run(left: Path = DEFAULT, right: Path = DEFAULT) -> dict:
    a, b = load_package(left), load_package(right); result = compare_packages(a, b)
    spectra = {}
    for manifold, hname, muname in (("ground", "H0_g", "mu_q_g"), ("excited", "H0_e", "mu_q_e")):
        ea, eb = np.linalg.eigvalsh(a.arrays[hname]), np.linalg.eigvalsh(b.arrays[hname]); ea -= ea[0]; eb -= eb[0]
        eps = 1e-6
        sa = (np.linalg.eigvalsh(a.arrays[hname] - eps*a.arrays[muname][1]) - np.linalg.eigvalsh(a.arrays[hname] + eps*a.arrays[muname][1]))/(2*eps)
        sb = (np.linalg.eigvalsh(b.arrays[hname] - eps*b.arrays[muname][1]) - np.linalg.eigvalsh(b.arrays[hname] + eps*b.arrays[muname][1]))/(2*eps)
        spectra[manifold] = {"level_energy_max_difference_Gamma": float(np.max(abs(ea-eb))), "magnetic_slope_spectrum_max_difference_Gamma_per_G": float(np.max(abs(np.sort(sa)-np.sort(sb))))}
    strength_a, strength_b = abs(a.arrays["d_q"])**2, abs(b.arrays["d_q"])**2
    connectivity_a, connectivity_b = strength_a > 1e-12, strength_b > 1e-12
    weakest_a, weakest_b = np.sum(strength_a, axis=(0,2)), np.sum(strength_b, axis=(0,2))
    derived = {
        "spectra_and_magnetic_slopes": spectra,
        "transition_strength_max_difference": float(np.max(abs(strength_a-strength_b))),
        "branching_max_difference": float(np.max(abs(a.arrays["branching"]-b.arrays["branching"]))),
        "state_connectivity_changed_entries": int(np.count_nonzero(connectivity_a != connectivity_b)),
        "dark_structure_weakest_ground_total_strengths": {"left": sorted(float(x) for x in weakest_a)[:4], "right": sorted(float(x) for x in weakest_b)[:4]},
        "eigenvector_overlap_singular_values": {
            "ground": np.linalg.svd(a.arrays["ground_eigenvectors"].conj().T @ b.arrays["ground_eigenvectors"], compute_uv=False).tolist(),
            "excited": np.linalg.svd(a.arrays["excited_eigenvectors"].conj().T @ b.arrays["excited_eigenvectors"], compute_uv=False).tolist(),
        },
        "eigenvector_absolute_overlap_matrices": {
            "ground": abs(a.arrays["ground_eigenvectors"].conj().T @ b.arrays["ground_eigenvectors"]).tolist(),
            "excited": abs(a.arrays["excited_eigenvectors"].conj().T @ b.arrays["excited_eigenvectors"]).tolist(),
            "note": "Interpret within degenerate subspaces; individual degenerate eigenvectors are not unique.",
        },
    }
    payload = {"label": RUN012_LABEL, **asdict(result), "derived_physical_differences": derived, "primary_difference_class": result.difference_classes[0] if len(result.difference_classes) == 1 else "multiple_classes" if result.difference_classes else "none", "replication_valid": False}
    output = DEFAULT.parent / f"{RUN012_LABEL}_model_difference_report.json"; output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{RUN012_LABEL}: equivalent={result.equivalent}; differences={result.difference_classes}"); return payload

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("left", nargs="?", type=Path, default=DEFAULT); parser.add_argument("right", nargs="?", type=Path, default=DEFAULT); args = parser.parse_args(); run(args.left, args.right)
