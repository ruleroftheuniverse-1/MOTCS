"""Validate one Run 012 molecular-model package before force use."""

from dataclasses import asdict
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]; SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))
from mgf_mot.molecular_model_package import RUN012_LABEL, load_package, validate_package  # noqa: E402

DEFAULT = ROOT / "outputs/provisional/molecular_model_packages/run_012" / f"{RUN012_LABEL}_ACCEPTED_PROVISIONAL_REFERENCE_PACKAGE"

def run(path: Path = DEFAULT) -> dict:
    package = load_package(path, validate=False); result = validate_package(package)
    output = path.parent / f"{RUN012_LABEL}_import_validation.json"
    payload = {"label": RUN012_LABEL, "package": str(path), "package_hash": result.package_hash, "gate": result.gate.value, "errors": list(result.errors), "warnings": list(result.warnings), "checks": result.checks, "invalid_package_force_authorized": False, "replication_valid": False}
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{RUN012_LABEL}: {result.gate.value}"); return payload

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("package", nargs="?", type=Path, default=DEFAULT); args = parser.parse_args(); run(args.package)
