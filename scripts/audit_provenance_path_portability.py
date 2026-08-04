"""Audit repository-path provenance domains without executing project physics."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mgf_mot.provenance_paths import (  # noqa: E402
    RepositoryProvenancePathError,
    canonical_repository_path,
    is_canonical_repository_path,
)


LABELS = (
    "MODEL_INDEPENDENT",
    "NOT_RODRIGUEZ_REPLICATION",
    "RUN_018",
    "CROSS_PLATFORM_PROVENANCE_CERTIFICATION_ONLY",
)
SCHEMA_VERSION = "mgf-mot-provenance-path-audit-v1"
OUTPUT = (
    ROOT
    / "outputs/provisional/provenance_portability/run_018/"
    "MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_018_"
    "CROSS_PLATFORM_PROVENANCE_CERTIFICATION_ONLY_audit.json"
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".audit.", suffix=".tmp", dir=path.parent)
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


def _require_source(path: str, *tokens: str) -> str:
    source = (ROOT / path).read_text(encoding="utf-8")
    missing = [token for token in tokens if token not in source]
    if missing:
        raise RuntimeError(f"provenance audit evidence drifted in {path}: {missing}")
    return _sha256(ROOT / path)


def _record(
    subsystem: str,
    schema_or_object: str,
    field: str,
    classification: str,
    identity_scope: str,
    source_location: str,
    rationale: str,
    *,
    portable_identity: str | None = None,
    platform_local_identity: str | None = None,
) -> dict[str, Any]:
    return {
        "subsystem": subsystem,
        "schema_or_object": schema_or_object,
        "field": field,
        "classification": classification,
        "identity_scope": identity_scope,
        "source_location": source_location,
        "rationale": rationale,
        "portable_identity": portable_identity,
        "platform_local_identity": platform_local_identity,
    }


def audit() -> dict[str, Any]:
    evidence = {
        "run_010": _require_source(
            "src/mgf_mot/accepted_backend.py",
            "path.relative_to(repo_root).as_posix()",
            "sha256(path.read_bytes()).hexdigest()",
        ),
        "molecular_model": _require_source(
            "src/mgf_mot/molecular_model_package.py",
            "arrays_hash",
            "metadata_hash",
            "full_package",
        ),
        "policy": _require_source(
            "src/mgf_mot/control_policy_serialization.py",
            'if key != "provenance"',
            "_digest(mapping)",
        ),
        "policy_adapter": _require_source(
            "src/mgf_mot/legacy_policy_adapter.py",
            "path.as_posix()",
            "source_configuration_paths",
        ),
        "open_loop": _require_source(
            "src/mgf_mot/open_loop_policy_families.py",
            'if key!="provenance"',
            "canonical_family_json(mapping)",
        ),
        "apparatus": _require_source(
            "src/mgf_mot/apparatus_constraints.py",
            "source_path_or_citation",
            "apparatus_profile_hash",
        ),
        "feedback": _require_source(
            "src/mgf_mot/feedback_policy.py",
            "source_path_or_citation",
            "feedback_hash",
        ),
        "experiment": _require_source(
            "src/mgf_mot/experiment_protocol.py",
            "hashes[str(path.relative_to(root))]",
            "artifact_hashes",
        ),
        "intake": _require_source(
            "src/mgf_mot/model_intake.py",
            "source_base",
            "quarantine_directory",
            "source_file_hashes",
        ),
        "release": _require_source(
            "src/mgf_mot/release_manifest.py",
            "path.relative_to(root).as_posix()",
            "relative.as_posix()",
        ),
    }

    representative = (
        (r"C:\MOTCS\src\mgf_mot\example.py", r"C:\MOTCS"),
        ("C:/MOTCS/src/mgf_mot/example.py", "C:/MOTCS"),
        (
            "/home/runner/work/MOTCS/MOTCS/src/mgf_mot/example.py",
            "/home/runner/work/MOTCS/MOTCS",
        ),
        ("src/mgf_mot/example.py", None),
    )
    equivalence = [
        {
            "input": path,
            "repository_root": root,
            "canonical": canonical_repository_path(path, repository_root=root),
        }
        for path, root in representative
    ]
    invalid = (
        ("../outside.py", None),
        (r"C:\other_repo\file.py", r"C:\MOTCS"),
        (r"\\server\share\file.py", r"\\server\share"),
        ("/home/user/unrelated/file.py", "/home/runner/work/MOTCS/MOTCS"),
        ("", None),
        ("src//mgf_mot/example.py", None),
        ("src/./mgf_mot/example.py", None),
    )
    rejections = []
    for path, root in invalid:
        try:
            canonical_repository_path(path, repository_root=root)
        except RepositoryProvenancePathError as exc:
            rejections.append(
                {"input": path, "repository_root": root, "rejected": True, "reason": str(exc)}
            )
        else:
            rejections.append(
                {"input": path, "repository_root": root, "rejected": False, "reason": None}
            )

    records = [
        _record(
            "Run 010 force-field provenance",
            "ForceFieldProvenance",
            "source_hashes[*][0]",
            "already_repository_relative_posix",
            "portable_semantic_identity",
            "src/mgf_mot/accepted_backend.py:accepted_force_field_source_hashes",
            "Dependency paths use relative_to(repo_root).as_posix(); hashes remain raw SHA-256 bytes.",
            portable_identity="ForceFieldProvenance.cache_key",
        ),
        _record(
            "molecular-model packages",
            "mgf-mot-molecular-model-v1",
            "manifest member names and source references",
            "intentionally_opaque_external_reference",
            "portable_semantic_identity",
            "src/mgf_mot/molecular_model_package.py",
            "Package identity hashes arrays and canonical JSON metadata; paper citations and supplied identifiers are opaque data, not repository paths.",
            portable_identity="MolecularModelHashes.full_package",
        ),
        _record(
            "molecular-model validation output",
            "Run 012 import validation",
            "package",
            "nonsemantic_display_path",
            "platform_local_audit_snapshot",
            "scripts/validate_molecular_model_roundtrip.py",
            "The stored package locator reports where validation ran and is not the molecular-model package identity.",
            platform_local_identity="historical validation report bytes",
        ),
        _record(
            "policy provenance",
            "mgf-mot-control-policy-v2",
            "provenance.source_configuration_paths",
            "nonsemantic_display_path",
            "platform_local_audit_snapshot",
            "src/mgf_mot/legacy_policy_adapter.py:_source",
            "Historical Run 013 packages retain checkout locators. policy_specification excludes provenance and is the portable content identity; full_policy_package intentionally snapshots the locator and is platform-local.",
            portable_identity="ControlPolicyHashes.policy_specification",
            platform_local_identity="ControlPolicyHashes.full_policy_package",
        ),
        _record(
            "open-loop policy families",
            "mgf-mot-open-loop-policy-family-v1",
            "provenance.source_path",
            "nonsemantic_display_path",
            "platform_local_audit_snapshot",
            "src/mgf_mot/open_loop_policy_families.py:family_hashes",
            "family_specification excludes provenance and is portable. complete_policy_package includes the historical checkout locator and is explicitly platform-local.",
            portable_identity="FamilyHashes.family_specification",
            platform_local_identity="FamilyHashes.complete_policy_package",
        ),
        _record(
            "apparatus profiles",
            "mgf-mot-apparatus-constraints-v1",
            "ConstraintProvenance.source_path_or_citation",
            "intentionally_opaque_external_reference",
            "declared_external_or_fixture_reference",
            "src/mgf_mot/apparatus_constraints.py",
            "The union field is an opaque citation/identifier supplied by the profile; null is explicit and no repository-path coercion is performed.",
            portable_identity="apparatus_profile_hash for path-free accepted fixtures",
        ),
        _record(
            "feedback specifications",
            "mgf-mot-feedback-session-v1",
            "FeedbackProvenance.source_path_or_citation",
            "intentionally_opaque_external_reference",
            "declared_external_or_fixture_reference",
            "src/mgf_mot/feedback_policy.py",
            "The field is an opaque citation/identifier. Accepted synthetic fixtures use null; inherited legacy policy full-package identities remain platform-local as classified above.",
            portable_identity="feedback_hash for path-free accepted fixtures",
        ),
        _record(
            "experiment manifests",
            "mgf-mot-experiment-checkpoint-v1",
            "artifact_hashes keys",
            "nonsemantic_display_path",
            "platform_local_runtime_checkpoint",
            "src/mgf_mot/experiment_protocol.py:_write_trial_artifacts",
            "Keys are relative to the experiment output root and are used only to reopen artifacts under that same root. The checkpoint snapshot is explicitly platform-local; portable experiment specification hashes contain opaque content hashes, not repository locators.",
            portable_identity="ExperimentSpec.semantic_hash where inputs use portable content hashes",
            platform_local_identity="ExperimentCheckpoint.semantic_hash",
        ),
        _record(
            "author-model intake",
            "mgf-mot-author-model-intake-v1",
            "source_base and quarantine_directory",
            "nonsemantic_display_path",
            "platform_local_audit_snapshot",
            "src/mgf_mot/model_intake.py:IntakeResult",
            "Locations document preserve-first intake execution. Source file hashes and source_bundle_hash provide content identity.",
            portable_identity="source_bundle_hash and source_file_hashes",
            platform_local_identity="IntakeResult serialized report bytes",
        ),
        _record(
            "release manifest",
            "mgf-mot-project-release-v1",
            "protected_artifact_hashes keys and documentation_index",
            "already_repository_relative_posix",
            "portable_semantic_identity",
            "src/mgf_mot/release_manifest.py",
            "Catalog, protected hash, audited-module, and documentation paths use relative_to(root).as_posix().",
            portable_identity="ReleaseSemanticManifest.semantic_hash",
        ),
        _record(
            "artifact catalog",
            "mgf-mot-artifact-catalog-v1",
            "artifacts[*].path",
            "already_repository_relative_posix",
            "portable_semantic_identity",
            "src/mgf_mot/release_manifest.py:build_artifact_catalog",
            "Every catalog path is repository-relative POSIX and participates in the source-tree semantic hash.",
            portable_identity="ArtifactCatalog.semantic_hash",
        ),
        _record(
            "invalid repository dependency paths",
            "canonical_repository_path",
            "rejected inputs",
            "invalid",
            "fail_closed_validation",
            "src/mgf_mot/provenance_paths.py",
            "Absolute paths without matching roots, outside paths, UNC paths, empty paths, and ambiguous segments fail closed.",
        ),
    ]

    allowed = {
        "already_repository_relative_posix",
        "intentionally_opaque_external_reference",
        "nonsemantic_display_path",
        "migration_required",
        "invalid",
    }
    classifications_complete = all(row["classification"] in allowed for row in records)
    equivalence_valid = all(
        row["canonical"] == "src/mgf_mot/example.py" for row in equivalence
    )
    rejections_valid = all(row["rejected"] for row in rejections)
    run010_metadata = sorted(
        (ROOT / "outputs/provisional/force_fields").glob("*run_010_metadata.json")
    )
    run010_paths = []
    for metadata_path in run010_metadata:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        run010_paths.extend(path for path, _ in payload["provenance"]["source_hashes"])
    run010_paths_valid = bool(run010_paths) and all(
        is_canonical_repository_path(path) for path in run010_paths
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "labels": list(LABELS),
        "audit_status": (
            "PROVENANCE_PATH_AUDIT_OK"
            if classifications_complete
            and equivalence_valid
            and rejections_valid
            and run010_paths_valid
            else "PROVENANCE_PATH_AUDIT_FAILED"
        ),
        "canonical_rule": {
            "repository_root_relative": True,
            "separator": "/",
            "drive_letter_forbidden_in_serialized_form": True,
            "leading_slash_forbidden": True,
            "dot_segments_forbidden": True,
            "checkout_prefix_forbidden": True,
            "symlink_realpath_expansion": False,
            "case_preserved": True,
            "unicode_serialization": "existing ensure_ascii=False canonical JSON rules",
            "absolute_input_requires_explicit_repository_root": True,
        },
        "representative_equivalence": equivalence,
        "invalid_path_rejections": rejections,
        "records": records,
        "summary": {
            "record_count": len(records),
            "classifications_complete": classifications_complete,
            "migration_required_count": sum(
                row["classification"] == "migration_required" for row in records
            ),
            "platform_local_records_explicit": sum(
                row["identity_scope"].startswith("platform_local") for row in records
            ),
            "run_010_dependency_path_count": len(run010_paths),
            "run_010_paths_canonical": run010_paths_valid,
            "representative_equivalence_valid": equivalence_valid,
            "invalid_paths_fail_closed": rejections_valid,
        },
        "identity_domains": {
            "artifact_byte_integrity": "raw SHA-256 of canonical checked-out or generated bytes",
            "structured_semantic_identity": "canonical JSON serialization",
            "repository_dependency_paths": "repository-relative POSIX strings inside semantic provenance",
            "external_source_references": "opaque identifiers or URIs; never force-converted into repository paths",
        },
        "source_evidence_sha256": evidence,
        "physical_execution_counts": {
            "force_evaluations": 0,
            "force_cache_rebuilds": 0,
            "equilibrium_solves": 0,
            "trajectory_integrations": 0,
        },
    }


def run() -> dict[str, Any]:
    record = audit()
    _atomic_json(OUTPUT, record)
    print(record["audit_status"])
    return record


if __name__ == "__main__":
    raise SystemExit(0 if run()["audit_status"] == "PROVENANCE_PATH_AUDIT_OK" else 1)
