"""Versioned, unit-explicit interchange for MgF molecular-model matrices.

The format is deliberately independent of the source-tagged construction
factory.  A loaded package either contains every object needed by pylcp or is
rejected; there is no fallback to project spectroscopy defaults.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from math import pi
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray
import pylcp

from .accepted_backend import AcceptedProvisionalBackendSelection
from .force_units import MgFForceUnitAudit, SourceTaggedMass
from .geometry import quadrupole_field
from .rateeq_backend import (
    ProvisionalPylcpRateEquationBackend,
    RateEquationBackendConfig,
    RateEquationBackendStatus,
)
from .tracks import ProjectTrack


SCHEMA_VERSION = "mgf-mot-molecular-model-v1"
RUN012_LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_012_"
    "MOLECULAR_MODEL_INTERCHANGE_AND_AUTHOR_HANDOFF_ONLY"
)
REQUIRED_ARRAYS = (
    "H0_g", "mu_q_g", "H0_e", "mu_q_e", "d_q", "branching",
    "ground_eigenvalues", "ground_eigenvectors", "excited_eigenvalues",
    "excited_eigenvectors", "construction_to_working_g",
    "construction_to_working_e", "working_to_canonical_g",
    "working_to_canonical_e",
)
REQUIRED_METADATA = (
    "schema_version", "molecule", "isotopologue", "transition",
    "status", "replication_valid", "basis", "array_specs", "conventions",
    "source", "date_created", "generator", "approximations", "force_context",
)


class MolecularModelPackageError(ValueError):
    """A package is absent, malformed, invalid, or incomplete."""


class ImportGate(str, Enum):
    IMPORT_VALID = "IMPORT_VALID"
    IMPORT_VALID_WITH_WARNINGS = "IMPORT_VALID_WITH_WARNINGS"
    IMPORT_INVALID = "IMPORT_INVALID"


@dataclass(frozen=True)
class PackageHashes:
    numerical_arrays: str
    metadata: str
    basis_labels: str
    full_package: str


@dataclass(frozen=True)
class ImportValidation:
    gate: ImportGate
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    checks: Mapping[str, Any]
    package_hash: str

    @property
    def valid(self) -> bool:
        return self.gate is not ImportGate.IMPORT_INVALID


@dataclass(frozen=True)
class PackageComparison:
    equivalent: bool
    raw_differences: Mapping[str, float]
    aligned_differences: Mapping[str, float]
    difference_classes: tuple[str, ...]
    alignment: Mapping[str, Any]
    left_hash: str
    right_hash: str


@dataclass(frozen=True)
class MolecularModelPackage:
    arrays: Mapping[str, NDArray[Any]]
    metadata: Mapping[str, Any]

    def hashes(self) -> PackageHashes:
        return package_hashes(self.arrays, self.metadata)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _canonical_array_bytes(name: str, array: NDArray[Any]) -> bytes:
    values = np.asarray(array)
    if values.dtype.kind not in "biufc":
        raise MolecularModelPackageError(f"array {name!r} has nonportable dtype {values.dtype}")
    little = values.astype(values.dtype.newbyteorder("<"), copy=False)
    header = _canonical_json({"name": name, "dtype": little.dtype.str, "shape": list(little.shape)})
    return len(header).to_bytes(8, "little") + header + np.ascontiguousarray(little).tobytes()


def package_hashes(arrays: Mapping[str, NDArray[Any]], metadata: Mapping[str, Any]) -> PackageHashes:
    array_digest = sha256()
    for name in sorted(arrays):
        array_digest.update(_canonical_array_bytes(name, np.asarray(arrays[name])))
    clean_metadata = {key: value for key, value in metadata.items() if key not in {"hashes", "manifest"}}
    metadata_hash = sha256(_canonical_json(clean_metadata)).hexdigest()
    basis_hash = sha256(_canonical_json(clean_metadata.get("basis", {}))).hexdigest()
    arrays_hash = array_digest.hexdigest()
    full = sha256(_canonical_json({
        "schema_version": clean_metadata.get("schema_version"),
        "numerical_arrays": arrays_hash,
        "metadata": metadata_hash,
        "basis_labels": basis_hash,
    })).hexdigest()
    return PackageHashes(arrays_hash, metadata_hash, basis_hash, full)


def _base_path(path: Path) -> Path:
    text = str(path)
    for suffix in (".metadata.json", ".manifest.json", ".npz"):
        if text.endswith(suffix):
            return Path(text[: -len(suffix)])
    return path


def write_package(package: MolecularModelPackage, path: Path) -> Mapping[str, Path]:
    """Write NPZ arrays plus canonical JSON metadata and hash manifest."""

    validation = validate_package(package)
    if not validation.valid:
        raise MolecularModelPackageError("cannot write invalid package: " + "; ".join(validation.errors))
    base = _base_path(path)
    base.parent.mkdir(parents=True, exist_ok=True)
    array_path = Path(f"{base}.npz")
    metadata_path = Path(f"{base}.metadata.json")
    manifest_path = Path(f"{base}.manifest.json")
    np.savez_compressed(array_path, **{name: np.asarray(value) for name, value in package.arrays.items()})
    metadata_path.write_text(json.dumps(package.metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = package.hashes()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "hashes": asdict(hashes),
        "files": {"arrays": array_path.name, "metadata": metadata_path.name},
        "canonicalization": {
            "arrays": "array names sorted; little-endian dtype+shape header; contiguous raw bytes",
            "metadata": "UTF-8 JSON, recursively sorted keys, compact separators; hashes/manifest keys excluded",
            "basis_labels": "canonical JSON of metadata.basis",
            "full_package": "SHA-256 of schema version and the three component hashes",
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"arrays": array_path, "metadata": metadata_path, "manifest": manifest_path}


def load_package(path: Path, *, validate: bool = True) -> MolecularModelPackage:
    """Load a package without substituting any absent array or metadata field."""

    base = _base_path(path)
    array_path = Path(f"{base}.npz")
    metadata_path = Path(f"{base}.metadata.json")
    manifest_path = Path(f"{base}.manifest.json")
    missing = [str(item) for item in (array_path, metadata_path, manifest_path) if not item.exists()]
    if missing:
        raise MolecularModelPackageError("package files are missing: " + ", ".join(missing))
    with np.load(array_path, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    package = MolecularModelPackage(arrays=arrays, metadata=metadata)
    hashes = package.hashes()
    if manifest.get("hashes") != asdict(hashes):
        raise MolecularModelPackageError("package manifest hash mismatch")
    if validate:
        report = validate_package(package)
        if not report.valid:
            raise MolecularModelPackageError("package validation failed: " + "; ".join(report.errors))
    return package


def _max_hermiticity(array: NDArray[Any]) -> float:
    values = np.asarray(array)
    return float(np.max(abs(values - values.conj().T)))


def _unitarity_error(array: NDArray[Any]) -> float:
    values = np.asarray(array)
    return float(np.max(abs(values.conj().T @ values - np.eye(values.shape[1]))))


def _energy_groups(h0: NDArray[Any], tolerance: float = 1e-10) -> list[list[int]]:
    values = np.linalg.eigvalsh(np.asarray(h0, dtype=complex))
    groups: list[list[int]] = []
    for index, energy in enumerate(values):
        if not groups or abs(energy - values[groups[-1][0]]) > tolerance:
            groups.append([index])
        else:
            groups[-1].append(index)
    return groups


def validate_package(package: MolecularModelPackage, *, include_equilibrium: bool = True) -> ImportValidation:
    errors: list[str] = []
    warnings: list[str] = []
    arrays = package.arrays
    metadata = package.metadata
    for field in REQUIRED_METADATA:
        if field not in metadata:
            errors.append(f"missing mandatory metadata field {field!r}")
    for name in REQUIRED_ARRAYS:
        if name not in arrays:
            errors.append(f"missing mandatory numerical array {name!r}; defaults are forbidden")
    if metadata.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}")
    if errors:
        return ImportValidation(ImportGate.IMPORT_INVALID, tuple(errors), tuple(warnings), {}, package.hashes().full_package)

    expected = {
        "H0_g": (12, 12), "mu_q_g": (3, 12, 12), "H0_e": (4, 4),
        "mu_q_e": (3, 4, 4), "d_q": (3, 12, 4), "branching": (12, 4),
        "ground_eigenvalues": (12,), "ground_eigenvectors": (12, 12),
        "excited_eigenvalues": (4,), "excited_eigenvectors": (4, 4),
        "construction_to_working_g": (12, 12), "construction_to_working_e": (4, 4),
        "working_to_canonical_g": (12, 12), "working_to_canonical_e": (4, 4),
    }
    specs = metadata["array_specs"]
    checks: dict[str, Any] = {"dimensions": {}, "hermiticity": {}, "unitarity": {}}
    for name, shape in expected.items():
        values = np.asarray(arrays[name])
        checks["dimensions"][name] = list(values.shape)
        if values.shape != shape:
            errors.append(f"array {name!r} has shape {values.shape}, expected {shape}")
        if not np.isfinite(values).all():
            errors.append(f"array {name!r} contains nonfinite values")
        spec = specs.get(name)
        if not isinstance(spec, dict) or not spec.get("units") or not spec.get("axes"):
            errors.append(f"array {name!r} requires nonempty units and axis meanings")
        elif list(spec.get("shape", [])) != list(shape):
            errors.append(f"array_specs shape for {name!r} does not match schema")
    basis = metadata["basis"]
    for manifold, count in (("ground", 12), ("excited", 4)):
        labels = basis.get(manifold)
        if not isinstance(labels, list) or len(labels) != count:
            errors.append(f"basis.{manifold} must contain {count} complete labels")
        elif any(not isinstance(row, dict) or "index" not in row or "label" not in row for row in labels):
            errors.append(f"basis.{manifold} labels require index and label")
        elif sorted(int(row["index"]) for row in labels) != list(range(count)):
            errors.append(f"basis.{manifold} indices must be a complete ordering")
    conventions = metadata["conventions"]
    if conventions.get("spherical_component_order") != [-1, 0, 1]:
        errors.append("dipole spherical-component ordering must be [-1, 0, 1]")
    if conventions.get("dipole_orientation") != "ground_to_excited":
        errors.append("v1 dipole orientation must be ground_to_excited")
    if conventions.get("hamiltonian_sign") != "H(B)=H0-|B|*mu_q[q=0_index_1]":
        errors.append("unrecognized Hamiltonian sign convention")
    if conventions.get("angular_frequency") is not True or conventions.get("linewidth_unit") != "Gamma":
        errors.append("v1 requires angular-frequency Hamiltonians normalized by Gamma")
    for name in ("H0_g", "H0_e"):
        error = _max_hermiticity(np.asarray(arrays[name]))
        checks["hermiticity"][name] = error
        if error > 1e-11:
            errors.append(f"{name} is not Hermitian: {error}")
    for name in ("mu_q_g", "mu_q_e"):
        q0_error = _max_hermiticity(np.asarray(arrays[name])[1])
        checks["hermiticity"][f"{name}[q=0]"] = q0_error
        if q0_error > 1e-11:
            errors.append(f"{name} q=0 component is not Hermitian: {q0_error}")
    for name in ("ground_eigenvectors", "excited_eigenvectors", "construction_to_working_g", "construction_to_working_e", "working_to_canonical_g", "working_to_canonical_e"):
        error = _unitarity_error(np.asarray(arrays[name]))
        checks["unitarity"][name] = error
        if error > 1e-10:
            errors.append(f"{name} is not unitary: {error}")
    for manifold, hname, ename, vname in (
        ("ground", "H0_g", "ground_eigenvalues", "ground_eigenvectors"),
        ("excited", "H0_e", "excited_eigenvalues", "excited_eigenvectors"),
    ):
        h0 = np.asarray(arrays[hname], dtype=complex)
        supplied_energy = np.asarray(arrays[ename], dtype=float)
        vectors = np.asarray(arrays[vname], dtype=complex)
        spectrum_error = float(np.max(abs(np.sort(supplied_energy) - np.linalg.eigvalsh(h0))))
        residual = float(np.max(abs(h0 @ vectors - vectors @ np.diag(supplied_energy))))
        checks[f"{manifold}_eigenvalue_spectrum_error"] = spectrum_error
        checks[f"{manifold}_eigenvector_residual"] = residual
        if spectrum_error > 1e-10 or residual > 1e-9:
            errors.append(f"supplied {manifold} eigensystem is inconsistent with {hname}")
    branching = np.asarray(arrays["branching"], dtype=float)
    branching_error = float(np.max(abs(np.sum(branching, axis=0) - 1.0)))
    checks["branching_column_normalization_error"] = branching_error
    if np.min(branching) < -1e-13 or branching_error > 1e-10:
        errors.append("branching must be nonnegative and normalized by excited-state column")
    derived = np.sum(abs(np.asarray(arrays["d_q"])) ** 2, axis=0)
    derived /= np.sum(derived, axis=0, keepdims=True)
    branching_dipole_error = float(np.max(abs(derived - branching)))
    checks["branching_vs_dipole_error"] = branching_dipole_error
    if branching_dipole_error > 1e-10:
        warnings.append("supplied branching differs from branching derived from d_q")
    dipole_sum = np.sum(abs(np.asarray(arrays["d_q"])) ** 2, axis=(0, 1))
    checks["transition_strength_sum_by_excited_state"] = dipole_sum.tolist()
    if np.any(dipole_sum <= 0):
        errors.append("every excited state must have positive total dipole strength")
    weak_field: dict[str, Any] = {}
    for manifold, hname, muname in (("ground", "H0_g", "mu_q_g"), ("excited", "H0_e", "mu_q_e")):
        h0 = np.asarray(arrays[hname], dtype=complex)
        mu0 = np.asarray(arrays[muname], dtype=complex)[1]
        eps = 1e-6
        plus = np.linalg.eigvalsh(h0 - eps * mu0)
        minus = np.linalg.eigvalsh(h0 + eps * mu0)
        slopes = (plus - minus) / (2 * eps)
        weak_field[manifold] = {"finite": bool(np.isfinite(slopes).all()), "maximum_absolute_slope_Gamma_per_G": float(np.max(abs(slopes)))}
        if not np.isfinite(slopes).all():
            errors.append(f"{manifold} weak-field magnetic slopes are nonfinite")
    checks["magnetic_weak_field_slopes"] = weak_field
    rng = np.random.default_rng(12012)
    pg = np.exp(1j * rng.uniform(-pi, pi, 12)); pe = np.exp(1j * rng.uniform(-pi, pi, 4))
    rephased_d = np.asarray([np.diag(pg).conj().T @ q @ np.diag(pe) for q in np.asarray(arrays["d_q"])])
    rephasing_error = float(np.max(abs(np.sum(abs(rephased_d) ** 2, axis=0) - np.sum(abs(np.asarray(arrays["d_q"])) ** 2, axis=0))))
    checks["phase_rephasing_transition_strength_error"] = rephasing_error
    if rephasing_error > 1e-12:
        errors.append("transition strengths are not invariant under deterministic basis rephasing")
    for manifold, hname in (("ground", "H0_g"), ("excited", "H0_e")):
        h0 = np.asarray(arrays[hname])
        off_diagonal = h0 - np.diag(np.diag(h0))
        value = float(np.max(abs(off_diagonal)))
        checks[f"{manifold}_working_basis_offdiagonal_H0"] = value
        if value > 1e-8:
            warnings.append(f"{manifold} working basis contains nondegenerate mixing; not treated as harmless equivalence")
    status = str(metadata.get("status"))
    if status not in {"exact", "provisional"}:
        errors.append("status must be exact or provisional")
    checks["full_independent_d_operator_included"] = bool(metadata["approximations"].get("full_independent_d_operator_included"))
    if include_equilibrium and not errors:
        try:
            import warnings as _warnings
            hamiltonian = pylcp.hamiltonian(
                np.asarray(arrays["H0_g"]), np.asarray(arrays["H0_e"]),
                np.asarray(arrays["mu_q_g"]), np.asarray(arrays["mu_q_e"]),
                np.asarray(arrays["d_q"]), mass=1.0, muB=1.0, gamma=1.0, k=1.0,
            )
            beams = pylcp.laserBeams()
            carrier = float(np.max(np.real(np.diag(arrays["H0_e"]))) - np.min(np.real(np.diag(arrays["H0_g"]))) - 1.0)
            for direction in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                beams.add_laser(pylcp.infinitePlaneWaveBeam(kvec=np.asarray(direction), pol=1, s=0.1, delta=carrier))
            field = pylcp.magField(lambda R: np.zeros(3), eps=1e-6)
            equation = pylcp.rateeq(beams, field, hamiltonian, include_mag_forces=False, svd_eps=1e-10, r0=np.zeros(3), v0=np.zeros(3))
            with _warnings.catch_warnings(record=True) as caught:
                _warnings.simplefilter("always", np.exceptions.ComplexWarning)
                population, evolution, _ = equation.equilibrium_populations(np.zeros(3), np.zeros(3), t=0.0, return_details=True)
            residual = float(np.linalg.norm(np.asarray(evolution) @ np.asarray(population), ord=np.inf))
            checks["equilibrium_solver_health"] = {
                "finite": bool(np.isfinite(population).all()), "population_sum": float(np.sum(population)),
                "population_minimum": float(np.min(population)), "residual_linf": residual,
                "complex_warning_count": sum(issubclass(item.category, np.exceptions.ComplexWarning) for item in caught),
            }
            if not np.isfinite(population).all() or abs(float(np.sum(population)) - 1) > 1e-10 or residual > 1e-9:
                errors.append("equilibrium-solver health check failed")
        except Exception as exc:
            errors.append(f"equilibrium-solver health check failed: {type(exc).__name__}: {exc}")
    gate = ImportGate.IMPORT_INVALID if errors else (ImportGate.IMPORT_VALID_WITH_WARNINGS if warnings else ImportGate.IMPORT_VALID)
    return ImportValidation(gate, tuple(errors), tuple(warnings), checks, package.hashes().full_package)


def _label_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (row.get("label"), row.get("F"), row.get("mF"), row.get("manifold"))


def _permutation(left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]]) -> list[int]:
    lookup: dict[tuple[Any, ...], list[int]] = {}
    for index, row in enumerate(right):
        lookup.setdefault(_label_key(row), []).append(index)
    result = []
    for row in left:
        candidates = lookup.get(_label_key(row), [])
        if len(candidates) != 1:
            raise MolecularModelPackageError(f"basis labels are not uniquely alignable: {_label_key(row)}")
        result.append(candidates[0])
    return result


def _reorder(array: NDArray[Any], pg: Sequence[int], pe: Sequence[int], kind: str) -> NDArray[Any]:
    values = np.asarray(array)
    if kind == "g2": return values[np.ix_(pg, pg)]
    if kind == "e2": return values[np.ix_(pe, pe)]
    if kind == "gq": return values[:, pg][:, :, pg]
    if kind == "eq": return values[:, pe][:, :, pe]
    if kind == "d": return values[:, pg][:, :, pe]
    if kind == "branch": return values[np.ix_(pg, pe)]
    raise AssertionError(kind)


def compare_packages(left: MolecularModelPackage, right: MolecularModelPackage, *, tolerance: float = 1e-10) -> PackageComparison:
    for package in (left, right):
        validation = validate_package(package, include_equilibrium=False)
        if not validation.valid:
            raise MolecularModelPackageError("comparison requires validated packages")
    pg = _permutation(left.metadata["basis"]["ground"], right.metadata["basis"]["ground"])
    pe = _permutation(left.metadata["basis"]["excited"], right.metadata["basis"]["excited"])
    kinds = {"H0_g": "g2", "mu_q_g": "gq", "H0_e": "e2", "mu_q_e": "eq", "d_q": "d", "branching": "branch"}
    raw: dict[str, float] = {}
    aligned: dict[str, float] = {}
    cg = np.asarray(right.arrays["working_to_canonical_g"])[:, pg]
    ce = np.asarray(right.arrays["working_to_canonical_e"])[:, pe]
    lg = np.asarray(left.arrays["working_to_canonical_g"])
    le = np.asarray(left.arrays["working_to_canonical_e"])
    for name, kind in kinds.items():
        a = np.asarray(left.arrays[name])
        b_original = np.asarray(right.arrays[name])
        raw[name] = float(np.max(abs(a - b_original))) if a.shape == b_original.shape else float("inf")
        b = _reorder(b_original, pg, pe, kind)
        if kind == "g2": a2, b2 = lg @ a @ lg.conj().T, cg @ b @ cg.conj().T
        elif kind == "e2": a2, b2 = le @ a @ le.conj().T, ce @ b @ ce.conj().T
        elif kind == "gq": a2, b2 = np.asarray([lg @ q @ lg.conj().T for q in a]), np.asarray([cg @ q @ cg.conj().T for q in b])
        elif kind == "eq": a2, b2 = np.asarray([le @ q @ le.conj().T for q in a]), np.asarray([ce @ q @ ce.conj().T for q in b])
        elif kind == "d": a2, b2 = np.asarray([lg @ q @ le.conj().T for q in a]), np.asarray([cg @ q @ ce.conj().T for q in b])
        else: a2, b2 = a, b
        if name.startswith("H0_"):
            offset = np.trace(b2 - a2) / a2.shape[0]
            b2 = b2 - offset * np.eye(a2.shape[0])
        aligned[name] = float(np.max(abs(a2 - b2)))
    # Branching probabilities are not amplitude-level tensors and therefore
    # cannot themselves be unitarily rotated.  Compare branching recomputed
    # from the canonically aligned dipole amplitudes.
    da = np.asarray([lg @ q @ le.conj().T for q in np.asarray(left.arrays["d_q"])])
    db_work = _reorder(np.asarray(right.arrays["d_q"]), pg, pe, "d")
    db = np.asarray([cg @ q @ ce.conj().T for q in db_work])
    ba = np.sum(abs(da) ** 2, axis=0); ba /= np.sum(ba, axis=0, keepdims=True)
    bb = np.sum(abs(db) ** 2, axis=0); bb /= np.sum(bb, axis=0, keepdims=True)
    aligned["branching"] = float(np.max(abs(ba - bb)))
    classes = []
    if aligned["H0_g"] > tolerance or aligned["H0_e"] > tolerance: classes.append("eigenvalues_or_hamiltonians")
    if aligned["mu_q_g"] > tolerance or aligned["mu_q_e"] > tolerance: classes.append("magnetic_tensors")
    if aligned["d_q"] > tolerance: classes.append("dipole_amplitudes_or_eigenvectors")
    if aligned["branching"] > tolerance: classes.append("branching")
    if pg != list(range(12)) or pe != list(range(4)): classes.append("basis_permutation")
    harmless = not any("not treated as harmless" in item for package in (left, right) for item in validate_package(package).warnings)
    equivalent = harmless and all(value <= tolerance for value in aligned.values())
    return PackageComparison(equivalent, raw, aligned, tuple(classes), {
        "right_ground_indices_in_left_order": pg,
        "right_excited_indices_in_left_order": pe,
        "global_energy_offsets_removed": True,
        "phase_and_degenerate_unitary_alignment_from_package": True,
        "nondegenerate_mixing_treated_as_harmless": False,
    }, left.hashes().full_package, right.hashes().full_package)


def _state_labels(backend: ProvisionalPylcpRateEquationBackend) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ground = [{
        "index": state.index, "label": next(level.label for level in backend.source_backend.validation_model.ground_levels if np.isclose(level.relative_energy_mhz, state.relative_energy_mhz, atol=1e-7)),
        "manifold": "ground", "F": state.F, "mF": state.mF, "dominant_J": state.dominant_J,
        "angular_momentum_assignment": "dominant_zero_field_assignment",
    } for state in backend.source_backend.validation_model.ground_eigenstates]
    excited = [{
        "index": index, "label": "Fprime0" if float(row["F"]) == 0 else "Fprime1",
        "manifold": "excited", "F": float(row["F"]), "mF": float(row["mF"]),
        "angular_momentum_assignment": "pylcp_Astate_basis_assignment",
    } for index, row in enumerate(backend.source_backend.validation_model.excited_basis)]
    return ground, excited


def package_from_accepted_backend(backend: ProvisionalPylcpRateEquationBackend, *, date_created: str, generator: str) -> MolecularModelPackage:
    """Export the immutable accepted Track P matrices and all reconstruction data."""

    ground_block = backend.hamiltonian.blocks[0, 0]
    excited_block = backend.hamiltonian.blocks[1, 1]
    h0g, mug = np.asarray(ground_block[0].matrix), np.asarray(ground_block[1].matrix)
    h0e, mue = np.asarray(excited_block[0].matrix), np.asarray(excited_block[1].matrix)
    dipole = np.asarray(backend.hamiltonian.blocks[0, 1].matrix)
    strength = np.sum(abs(dipole) ** 2, axis=0)
    branching = strength / np.sum(strength, axis=0, keepdims=True)
    eg, ug = np.linalg.eigh(h0g)
    ee, ue = np.linalg.eigh(h0e)
    ground_labels, excited_labels = _state_labels(backend)
    arrays = {
        "H0_g": h0g.astype(complex), "mu_q_g": mug.astype(complex),
        "H0_e": h0e.astype(complex), "mu_q_e": mue.astype(complex),
        "d_q": dipole.astype(complex), "branching": branching.astype(float),
        "ground_eigenvalues": eg.astype(float), "ground_eigenvectors": ug.astype(complex),
        "excited_eigenvalues": ee.astype(float), "excited_eigenvectors": ue.astype(complex),
        "construction_to_working_g": np.asarray(backend.source_backend.validation_model.ground_eigenvectors, dtype=complex),
        "construction_to_working_e": np.eye(4, dtype=complex),
        "working_to_canonical_g": np.eye(12, dtype=complex),
        "working_to_canonical_e": np.eye(4, dtype=complex),
    }
    axes = {
        "H0_g": ["ground_bra", "ground_ket"], "mu_q_g": ["q=-1,0,+1", "ground_bra", "ground_ket"],
        "H0_e": ["excited_bra", "excited_ket"], "mu_q_e": ["q=-1,0,+1", "excited_bra", "excited_ket"],
        "d_q": ["q=-1,0,+1", "ground_bra", "excited_ket"], "branching": ["ground_destination", "excited_source"],
        "ground_eigenvalues": ["ground_eigenstate"], "ground_eigenvectors": ["ground_working_basis", "ground_eigenstate"],
        "excited_eigenvalues": ["excited_eigenstate"], "excited_eigenvectors": ["excited_working_basis", "excited_eigenstate"],
        "construction_to_working_g": ["ground_construction_basis", "ground_working_basis"],
        "construction_to_working_e": ["excited_construction_basis", "excited_working_basis"],
        "working_to_canonical_g": ["ground_canonical_basis", "ground_working_basis"],
        "working_to_canonical_e": ["excited_canonical_basis", "excited_working_basis"],
    }
    units = {name: ("Gamma" if name in {"H0_g", "H0_e", "ground_eigenvalues", "excited_eigenvalues"} else "Gamma/G" if name in {"mu_q_g", "mu_q_e"} else "dimensionless") for name in arrays}
    audit = backend.force_units
    metadata = {
        "schema_version": SCHEMA_VERSION, "molecule": "MgF", "isotopologue": "24Mg19F",
        "transition": "X 2Sigma+(v=0,N=1) to A 2Pi1/2(v'=0,J'=1/2,+)",
        "status": "provisional", "replication_valid": False,
        "basis": {"ground": ground_labels, "excited": excited_labels, "ordering_is_explicit": True},
        "array_specs": {name: {"shape": list(np.asarray(value).shape), "dtype": str(np.asarray(value).dtype), "units": units[name], "axes": axes[name]} for name, value in arrays.items()},
        "conventions": {
            "energy_zero": "serialized working-basis values; comparisons allow one global offset per manifold",
            "angular_frequency": True, "linewidth_unit": "Gamma", "linewidth_definition": "Gamma=2*pi*20.9 MHz",
            "hamiltonian_sign": "H(B)=H0-|B|*mu_q[q=0_index_1]",
            "magnetic_hamiltonian": "pylcp diag_static_field magnitude convention; corrected ground magnetic sign applied exactly once",
            "spherical_component_order": [-1, 0, 1], "dipole_orientation": "ground_to_excited",
            "dipole_normalization": "sum over q and ground states equals one for each excited state",
            "reduced_matrix_element": "pylcp XFmolecules.dipoleXandAstates normalized tensor convention",
            "complex_storage": "native NumPy complex arrays in NPZ; no imaginary part discarded",
        },
        "source": {
            "citation": "K. J. Rodriguez et al., Phys. Rev. A 108, 033105 (2023), doi:10.1103/PhysRevA.108.033105; provisional source mapping documented in spectroscopy.py",
            "source_code": "local MOTCS accepted Track P backend",
            "source_code_version": "Run 009D selection audited through Run 011D; pylcp 1.0.2",
        },
        "date_created": date_created, "generator": generator,
        "approximations": {
            "corrected_ground_magnetic_convention": backend.status.ground_zeeman_convention,
            "effective_excited_g_prime": 0.001,
            "effective_Fprime_splitting_MHz": 0.5,
            "effective_Fprime_splitting_status": "midpoint of source-supported 0 to 1 MHz interval, not a measurement",
            "full_independent_d_operator_included": False,
            "omitted_terms": list(backend.status.omitted_terms), "collapsed_terms": list(backend.status.collapsed_terms),
            "unresolved": list(AcceptedProvisionalBackendSelection().unresolved_terms),
        },
        "force_context": {
            "magnetic_gradient_T_per_m": backend.config.magnetic_gradient_t_m,
            "svd_eps": backend.config.svd_eps,
            "figure_position_unit_m": 7.48e-3,
            "velocity_unit_m_s": audit.linewidth_rad_s / audit.wave_number_rad_m,
            "backend_config": {
                "ground_zeeman_convention": backend.config.ground_zeeman_convention.value,
                "excited_zeeman_model": backend.config.excited_zeeman_model.value,
                "excited_hyperfine_model": backend.config.excited_hyperfine_model.value,
                "excited_hyperfine_splitting_case": backend.config.excited_hyperfine_splitting_case.value if backend.config.excited_hyperfine_splitting_case else None,
                "paper_helicity_translation": backend.config.paper_helicity_translation.value,
            },
            "status": {**asdict(backend.status), "track": backend.status.track.value},
            "role_ground_energy_gamma": dict(backend._role_ground_energy),
            "excited_reference_energy_gamma": backend._excited_reference_energy,
            "force_units": {
                "wavelength_m": audit.wavelength_m, "wave_number_rad_m": audit.wave_number_rad_m,
                "linewidth_rad_s": audit.linewidth_rad_s, "hbar_k_gamma_N": audit.hbar_k_gamma_n,
                "mass_kg": audit.mass.value_kg, "mass_isotopologue": audit.mass.isotopologue,
                "acceleration_per_normalized_force_m_s2": audit.acceleration_per_normalized_force_m_s2,
                "wavelength_source": audit.wavelength_source, "linewidth_source": audit.linewidth_source,
            },
        },
        "authorization": {
            "molecular_model_interchange_authorized": True, "imported_model_force_authorized": False,
            "cache_rebuild_authorized": False, "trajectory_reintegration_authorized": False,
            "capture_authorized": False, "optimizer_authorized": False, "exact_replication_valid": False,
        },
        "notes": ["Accepted Track P reference package; not a Rodriguez-replication-valid molecular model."],
    }
    return MolecularModelPackage(arrays=arrays, metadata=metadata)


class PackagedRateEquationBackend(ProvisionalPylcpRateEquationBackend):
    """pylcp force backend constructed only from a validated serialized package."""

    def __init__(self, package: MolecularModelPackage):
        validation = validate_package(package, include_equilibrium=False)
        if not validation.valid:
            raise MolecularModelPackageError("invalid package cannot enter force calculation: " + "; ".join(validation.errors))
        self.package_hash = validation.package_hash
        context = package.metadata["force_context"]
        config_data = context["backend_config"]
        # These imports map explicit serialized names; they do not supply values.
        from .conventions import GroundZeemanConvention, PaperHelicityTranslation
        from .excited_hyperfine import ExcitedHyperfineModel, SourceAlignedSplittingCase
        from .excited_zeeman import ExcitedZeemanModel
        from .mgf_backend import ApproximationMode
        config = RateEquationBackendConfig(
            explicit_provisional_opt_in=True, track=ProjectTrack.PROVISIONAL,
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE,
            magnetic_gradient_t_m=float(context["magnetic_gradient_T_per_m"]), svd_eps=float(context["svd_eps"]),
            paper_helicity_translation=PaperHelicityTranslation(config_data["paper_helicity_translation"]),
            ground_zeeman_convention=GroundZeemanConvention(config_data["ground_zeeman_convention"]),
            excited_zeeman_model=ExcitedZeemanModel(config_data["excited_zeeman_model"]),
            excited_hyperfine_model=ExcitedHyperfineModel(config_data["excited_hyperfine_model"]),
            excited_hyperfine_splitting_case=SourceAlignedSplittingCase(config_data["excited_hyperfine_splitting_case"]) if config_data["excited_hyperfine_splitting_case"] else None,
        )
        self.config = config
        a = package.arrays
        self.hamiltonian = pylcp.hamiltonian(
            np.asarray(a["H0_g"]), np.asarray(a["H0_e"]), np.asarray(a["mu_q_g"]),
            np.asarray(a["mu_q_e"]), np.asarray(a["d_q"]), mass=1.0, muB=1.0, gamma=1.0, k=1.0,
        )
        status_data = dict(context["status"]); status_data["track"] = ProjectTrack(status_data["track"])
        self.status = RateEquationBackendStatus(**status_data)
        units = context["force_units"]
        mass = SourceTaggedMass(float(units["mass_kg"]), str(units["mass_isotopologue"]), ("serialized molecular-model package",), "serialized", "Loaded without project defaults")
        self.force_units = MgFForceUnitAudit(
            wavelength_m=float(units["wavelength_m"]), wave_number_rad_m=float(units["wave_number_rad_m"]),
            linewidth_rad_s=float(units["linewidth_rad_s"]), hbar_k_gamma_n=float(units["hbar_k_gamma_N"]),
            mass=mass, acceleration_per_normalized_force_m_s2=float(units["acceleration_per_normalized_force_m_s2"]),
            wavelength_source=str(units["wavelength_source"]), linewidth_source=str(units["linewidth_source"]),
        )
        gradient = float(context["magnetic_gradient_T_per_m"])
        self.mag_field = pylcp.magField(lambda R: np.asarray(quadrupole_field(R, gradient), dtype=float) * 1e4, eps=1e-6)
        self.gradient_gauss_per_m = gradient * 1e4
        self._role_ground_energy = {str(k): float(v) for k, v in context["role_ground_energy_gamma"].items()}
        self._excited_reference_energy = float(context["excited_reference_energy_gamma"])
        self.source_backend = None


def build_backend_from_package(package: MolecularModelPackage) -> PackagedRateEquationBackend:
    return PackagedRateEquationBackend(package)
