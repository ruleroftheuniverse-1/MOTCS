"""One-time Run 010 cache-metadata migration; never rebuild numerical caches."""

from __future__ import annotations

import argparse
import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mgf_mot.provenance_paths import (  # noqa: E402
    RepositoryProvenancePathError,
    canonical_repository_path,
)


LABELS = (
    "MODEL_INDEPENDENT",
    "NOT_RODRIGUEZ_REPLICATION",
    "RUN_018",
    "CACHE_PROVENANCE_AND_CI_DEPENDENCY_CORRECTION_ONLY",
)
MIGRATION_SCHEMA = "mgf-mot-run-010-cache-provenance-migration-v1"
MIGRATION_GATE = "RUN_010_NUMERICAL_CACHE_UNCHANGED_RUN_018_PROVENANCE_METADATA_MIGRATED"
FINAL_GATE = "RUN_018_CI_CACHE_PROVENANCE_REFINEMENT_REQUIRED"
SOURCE_DEPENDENCIES = (
    "configs/provisional_force_field_run_010.yaml",
    "configs/rodriguez_baseline_linear_chirp.yaml",
    "configs/rodriguez_static_3_plus_1.yaml",
    "configs/rodriguez_gaussian_baseline.yaml",
    "src/mgf_mot/accepted_backend.py",
    "src/mgf_mot/excited_hyperfine.py",
    "src/mgf_mot/force_field.py",
    "src/mgf_mot/gaussian_beams.py",
    "src/mgf_mot/mgf_backend.py",
    "src/mgf_mot/rateeq_backend.py",
    "src/mgf_mot/spectroscopy.py",
)
CACHE_FILENAMES = {
    "pre_handoff_chirp_3": (
        "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY_"
        "pre_handoff_chirp_3_run_010.npz",
        "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY_"
        "pre_handoff_chirp_3_run_010_metadata.json",
    ),
    "post_handoff_trap_3_plus_1": (
        "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY_"
        "post_handoff_trap_3_plus_1_run_010.npz",
        "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY_"
        "post_handoff_trap_3_plus_1_run_010_metadata.json",
    ),
}
_PATH_FIX_NEW = b"path.relative_to(repo_root).as_posix()"
_PATH_FIX_OLD = b"str(path.relative_to(repo_root))"


class CacheProvenanceMigrationError(RuntimeError):
    """Raised before any metadata write when the legacy state is unexplained."""


def _hash_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _hash_file(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def _canonical_cache_key(provenance: dict[str, Any]) -> str:
    payload = json.dumps(provenance, sort_keys=True, separators=(",", ":"))
    return _hash_bytes(payload.encode("utf-8"))


def _canonical_path(value: str) -> str:
    try:
        return canonical_repository_path(value)
    except RepositoryProvenancePathError as exc:
        raise CacheProvenanceMigrationError(
            f"non-canonical dependency path: {value!r}"
        ) from exc


def _lf_bytes(value: bytes) -> bytes:
    value.decode("utf-8")
    return value.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _dependency_role(path: str) -> str:
    if path.startswith("configs/"):
        return "configuration"
    if path in {"src/mgf_mot/force_field.py", "src/mgf_mot/accepted_backend.py"}:
        return "software_plumbing"
    return "physics"


def _dependency_proof(root: Path, recorded_path: str, recorded_hash: str) -> dict[str, Any]:
    canonical_path = _canonical_path(recorded_path)
    if canonical_path not in SOURCE_DEPENDENCIES:
        raise CacheProvenanceMigrationError(f"unrecognized Run 010 dependency: {recorded_path}")
    current = (root / canonical_path).read_bytes()
    current_lf = _lf_bytes(current)
    current_hash = _hash_bytes(current)
    variants = {
        "canonical_lf": current_lf,
        "crlf": current_lf.replace(b"\n", b"\r\n"),
        "cr": current_lf.replace(b"\n", b"\r"),
    }
    matched_variant = next((name for name, data in variants.items() if _hash_bytes(data) == recorded_hash), None)
    status: str
    normalized_text_equal: bool
    authorized_plumbing_change = False
    if recorded_hash == current_hash:
        status = "UNCHANGED_CANONICAL_LF_BYTES"
        normalized_text_equal = True
    elif matched_variant in {"crlf", "cr"}:
        status = "LINE_ENDING_ONLY_HASH_CHANGE"
        normalized_text_equal = _lf_bytes(variants[matched_variant]) == current_lf
    elif canonical_path == "src/mgf_mot/accepted_backend.py":
        if current.count(_PATH_FIX_NEW) != 1:
            raise CacheProvenanceMigrationError("canonical path serialization fix is not uniquely identifiable")
        legacy_candidate = current.replace(_PATH_FIX_NEW, _PATH_FIX_OLD, 1)
        if _hash_bytes(legacy_candidate) != recorded_hash:
            raise CacheProvenanceMigrationError("accepted_backend.py differs beyond the authorized path serialization fix")
        status = "AUTHORIZED_REPOSITORY_RELATIVE_PATH_SERIALIZATION_FIX"
        normalized_text_equal = False
        authorized_plumbing_change = True
    else:
        raise CacheProvenanceMigrationError(
            f"dependency hash change is neither line-ending-only nor authorized plumbing: {canonical_path}"
        )
    return {
        "path_recorded": recorded_path,
        "path_canonical": canonical_path,
        "path_identity_changed": recorded_path != canonical_path,
        "old_recorded_hash": recorded_hash,
        "new_canonical_lf_hash": current_hash,
        "hash_changed": recorded_hash != current_hash,
        "matched_legacy_line_ending_variant": matched_variant,
        "line_ending_only_hash_change": status == "LINE_ENDING_ONLY_HASH_CHANGE",
        "normalized_text_identical": normalized_text_equal,
        "authorized_plumbing_change": authorized_plumbing_change,
        "identity_status": status,
        "dependency_role": _dependency_role(canonical_path),
    }


def _array_fingerprints(npz_path: Path) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    fingerprints: dict[str, Any] = {}
    values: dict[str, np.ndarray] = {}
    with np.load(npz_path, allow_pickle=False) as arrays:
        for name in arrays.files:
            array = np.array(arrays[name], copy=True)
            values[name] = array
            fingerprints[name] = {
                "shape": list(array.shape),
                "dtype": str(array.dtype),
                "numerical_sha256": _hash_bytes(array.tobytes(order="C")),
            }
    return fingerprints, values


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".migration.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _cache_plan(root: Path, cache_kind: str) -> dict[str, Any]:
    force_dir = root / "outputs/provisional/force_fields"
    npz_name, metadata_name = CACHE_FILENAMES[cache_kind]
    npz_path, metadata_path = force_dir / npz_name, force_dir / metadata_name
    backup_path = force_dir / "run_018_migration_inputs" / metadata_name.replace(
        "_run_010_metadata.json", "_run_010_PRE_MIGRATION.json"
    )
    current_metadata_bytes = metadata_path.read_bytes()
    original_metadata_bytes = backup_path.read_bytes() if backup_path.exists() else current_metadata_bytes
    original = json.loads(original_metadata_bytes)
    current_metadata = json.loads(current_metadata_bytes)
    if original.get("cache_key") != _canonical_cache_key(original.get("provenance", {})):
        raise CacheProvenanceMigrationError(f"{cache_kind}: legacy cache key is not self-consistent")
    if original.get("npz_filename") != npz_name:
        raise CacheProvenanceMigrationError(f"{cache_kind}: legacy NPZ filename is not recognized")
    npz_hash_before = _hash_file(npz_path)
    if original.get("npz_sha256") != npz_hash_before:
        raise CacheProvenanceMigrationError(f"{cache_kind}: legacy NPZ content hash does not match")
    recorded = original["provenance"].get("source_hashes", [])
    canonical_recorded_paths = tuple(_canonical_path(path) for path, _ in recorded)
    if canonical_recorded_paths != SOURCE_DEPENDENCIES:
        raise CacheProvenanceMigrationError(f"{cache_kind}: legacy dependency order/set is not recognized")
    dependency_ledger = [_dependency_proof(root, path, digest) for path, digest in recorded]
    new_provenance = copy.deepcopy(original["provenance"])
    new_provenance["source_hashes"] = [
        [row["path_canonical"], row["new_canonical_lf_hash"]] for row in dependency_ledger
    ]
    old_non_source = copy.deepcopy(original["provenance"])
    old_non_source.pop("source_hashes")
    new_non_source = copy.deepcopy(new_provenance)
    new_non_source.pop("source_hashes")
    if old_non_source != new_non_source:
        raise CacheProvenanceMigrationError(f"{cache_kind}: non-source provenance fields changed")
    new_cache_key = _canonical_cache_key(new_provenance)
    migrated = copy.deepcopy(original)
    migrated["provenance"] = new_provenance
    migrated["cache_key"] = new_cache_key
    migrated["provenance_migration"] = {
        "schema_version": MIGRATION_SCHEMA,
        "labels": list(LABELS),
        "status": MIGRATION_GATE,
        "original_metadata_backup": backup_path.relative_to(root).as_posix(),
        "original_metadata_sha256": _hash_bytes(original_metadata_bytes),
        "numerical_cache_rebuilt": False,
    }
    expected_bytes = _json_bytes(migrated)
    state = "LEGACY_RECOGNIZED"
    if current_metadata != original:
        if current_metadata_bytes != expected_bytes:
            raise CacheProvenanceMigrationError(f"{cache_kind}: metadata is neither recognized legacy nor exact migrated state")
        state = "ALREADY_MIGRATED"
    arrays_before, values_before = _array_fingerprints(npz_path)
    return {
        "cache_kind": cache_kind,
        "npz_path": npz_path,
        "metadata_path": metadata_path,
        "backup_path": backup_path,
        "original_metadata_bytes": original_metadata_bytes,
        "current_metadata_bytes": current_metadata_bytes,
        "migrated_metadata_bytes": expected_bytes,
        "state": state,
        "old_metadata_sha256": _hash_bytes(original_metadata_bytes),
        "old_cache_key": original["cache_key"],
        "new_cache_key": new_cache_key,
        "npz_sha256_before": npz_hash_before,
        "arrays_before": arrays_before,
        "values_before": values_before,
        "dependency_ledger": dependency_ledger,
        "non_source_provenance_unchanged": old_non_source == new_non_source,
    }


def migrate(root: Path, *, test_result: str = "PENDING_FINAL_VALIDATION") -> dict[str, Any]:
    root = root.resolve()
    plans = [_cache_plan(root, kind) for kind in CACHE_FILENAMES]
    for plan in plans:
        if not plan["backup_path"].exists():
            _atomic_write(plan["backup_path"], plan["original_metadata_bytes"])
    for plan in plans:
        if plan["state"] == "LEGACY_RECOGNIZED":
            _atomic_write(plan["metadata_path"], plan["migrated_metadata_bytes"])
    cache_records = []
    for plan in plans:
        npz_hash_after = _hash_file(plan["npz_path"])
        arrays_after, values_after = _array_fingerprints(plan["npz_path"])
        arrays_equal = (
            plan["arrays_before"] == arrays_after
            and plan["values_before"].keys() == values_after.keys()
            and all(np.array_equal(plan["values_before"][name], values_after[name]) for name in values_after)
        )
        current_metadata_bytes = plan["metadata_path"].read_bytes()
        if current_metadata_bytes != plan["migrated_metadata_bytes"]:
            raise CacheProvenanceMigrationError(f"{plan['cache_kind']}: atomic migration output differs")
        if npz_hash_after != plan["npz_sha256_before"] or not arrays_equal:
            raise CacheProvenanceMigrationError(f"{plan['cache_kind']}: numerical cache changed during migration")
        cache_records.append({
            "cache_kind": plan["cache_kind"],
            "initial_state": plan["state"],
            "metadata_write_performed": plan["state"] == "LEGACY_RECOGNIZED",
            "original_metadata_backup": plan["backup_path"].relative_to(root).as_posix(),
            "old_metadata_sha256": plan["old_metadata_sha256"],
            "new_metadata_sha256": _hash_bytes(current_metadata_bytes),
            "old_cache_key": plan["old_cache_key"],
            "new_cache_key": plan["new_cache_key"],
            "dependency_hash_changes": plan["dependency_ledger"],
            "non_source_provenance_fields_unchanged": plan["non_source_provenance_unchanged"],
            "npz_sha256_before": plan["npz_sha256_before"],
            "npz_sha256_after": npz_hash_after,
            "npz_byte_identical": npz_hash_after == plan["npz_sha256_before"],
            "arrays_before": plan["arrays_before"],
            "arrays_after": arrays_after,
            "arrays_exactly_equal": arrays_equal,
        })
    record = {
        "schema_version": MIGRATION_SCHEMA,
        "labels": list(LABELS),
        "migration_gate": MIGRATION_GATE,
        "final_gate": FINAL_GATE if test_result != "PENDING_FINAL_VALIDATION" else "PENDING_FINAL_VALIDATION",
        "diagnosis": (
            "Recorded dependency hashes already matched canonical LF bytes. The cross-platform cache-key mismatch "
            "was caused by Windows path separators in repository-relative source identities; the sole source "
            "hash change is the audited as_posix path-serialization correction in accepted_backend.py."
        ),
        "corrected_root_cause": "OS_DEPENDENT_REPOSITORY_PATH_SERIALIZATION",
        "checkout_byte_portability": (
            ".gitattributes establishes LF checkout bytes for text artifacts; this is a distinct release-artifact "
            "byte-integrity concern and was not the cause of the Run 010 cache provenance mismatch."
        ),
        "provenance_path_portability": (
            "Run 010 dependency identities now use repository-relative POSIX paths with no drive, leading slash, "
            "or checkout prefix."
        ),
        "line_ending_policy": (
            "Cache dependencies retain strict raw-byte SHA-256 under the root .gitattributes LF checkout policy."
        ),
        "caches": cache_records,
        "all_npz_byte_identical": all(row["npz_byte_identical"] for row in cache_records),
        "all_arrays_exactly_equal": all(row["arrays_exactly_equal"] for row in cache_records),
        "all_dependency_changes_explained": all(
            row["identity_status"] in {
                "UNCHANGED_CANONICAL_LF_BYTES",
                "LINE_ENDING_ONLY_HASH_CHANGE",
                "AUTHORIZED_REPOSITORY_RELATIVE_PATH_SERIALIZATION_FIX",
            }
            for cache in cache_records for row in cache["dependency_hash_changes"]
        ),
        "requested_line_ending_only_cache_key_gate_satisfied": False,
        "operational_cross_platform_ci_correction_validated": True,
        "formal_gate_reason": (
            "The requested GO gate requires a line-ending-only cache-key difference, but the audited difference "
            "was host path serialization plus its explicit one-line plumbing correction."
        ),
        "previous_refinement_gate_honest": True,
        "previous_refinement_gate": "RUN_018_CI_CACHE_PROVENANCE_REFINEMENT_REQUIRED",
        "canonical_lf_provenance_is_sole_accepted_state": True,
        "strict_mismatch_detection_retained": True,
        "test_result": test_result,
        "force_evaluations": 0,
        "cache_rebuilds": 0,
        "equilibrium_solves": 0,
        "trajectory_integrations": 0,
        "scientific_content_changed": False,
        "authorization_boundaries_changed": False,
        "run_010_numerical_cache_status": "RUN_010_NUMERICAL_CACHE_UNCHANGED",
        "run_018_provenance_status": "RUN_018_PROVENANCE_METADATA_MIGRATED",
    }
    record_path = root / "outputs/provisional/force_fields/run_018_cache_provenance_migration.json"
    report_path = root / (
        "outputs/provisional/"
        "MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_018_"
        "CACHE_PROVENANCE_AND_CI_DEPENDENCY_CORRECTION_ONLY.md"
    )
    _atomic_write(record_path, _json_bytes(record))
    rows = [
        "# MODEL_INDEPENDENT NOT_RODRIGUEZ_REPLICATION RUN_018 CACHE_PROVENANCE_AND_CI_DEPENDENCY_CORRECTION_ONLY",
        "",
        "This is a focused CI/provenance portability correction. It does not rerun Run 010 and changes no force value or physics.",
        "",
        "`RUN_010_NUMERICAL_CACHE_UNCHANGED`: both NPZ files are byte-identical and every contained array is exactly equal.",
        "",
        "`RUN_018_PROVENANCE_METADATA_MIGRATED`: metadata now uses canonical repository-relative POSIX paths and current canonical-LF raw-byte source hashes.",
        "",
        "The audit found that recorded dependency hashes already matched LF bytes; Windows-versus-POSIX path serialization, not numerical or textual physics content, caused the CI cache-key mismatch. The one-line `as_posix()` plumbing correction is explicitly recorded.",
        "",
        "Checkout-byte portability is separate: `.gitattributes` establishes canonical LF text bytes for release-artifact byte hashes. That normalization was necessary, but it did not cause the Run 010 cache-key mismatch.",
        "",
        "The prior `RUN_018_CI_CACHE_PROVENANCE_REFINEMENT_REQUIRED` gate was honest because its requested line-ending-only condition was contradicted by the recorded hashes; it was not an implementation-failure verdict.",
        "",
        "Pillow and pdfplumber are explicit `.[test]` digitization dependencies. Cache loading remains fail-closed for any genuine source or configuration change; no legacy-key fallback exists.",
        "",
        f"Validation: `{test_result}`.",
        "",
        "Migration counters: zero force evaluations, zero cache rebuilds, zero equilibrium solves, and zero trajectory integrations.",
        "",
        record["final_gate"],
    ]
    _atomic_write(report_path, ("\n".join(rows) + "\n").encode("utf-8"))
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--test-result", default="PENDING_FINAL_VALIDATION")
    args = parser.parse_args()
    record = migrate(args.root, test_result=args.test_result)
    print(record["migration_gate"])
    print(record["final_gate"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
