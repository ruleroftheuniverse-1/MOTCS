from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from mgf_mot.provenance_paths import (
    RepositoryProvenancePathError,
    canonical_repository_path,
    is_canonical_repository_path,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "scripts/audit_provenance_path_portability.py"
AUDIT_RECORD = (
    ROOT
    / "outputs/provisional/provenance_portability/run_018/"
    "MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_018_"
    "CROSS_PLATFORM_PROVENANCE_CERTIFICATION_ONLY_audit.json"
)
MIGRATION_RECORD = ROOT / "outputs/provisional/force_fields/run_018_cache_provenance_migration.json"
REPORT = (
    ROOT
    / "outputs/provisional/"
    "MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_018_"
    "CROSS_PLATFORM_PROVENANCE_CERTIFICATION_ONLY.md"
)


@pytest.mark.parametrize(
    ("value", "repository_root"),
    [
        (r"C:\MOTCS\src\mgf_mot\example.py", r"C:\MOTCS"),
        ("C:/MOTCS/src/mgf_mot/example.py", "C:/MOTCS"),
        (
            "/home/runner/work/MOTCS/MOTCS/src/mgf_mot/example.py",
            "/home/runner/work/MOTCS/MOTCS",
        ),
        ("src/mgf_mot/example.py", None),
    ],
)
def test_cross_host_path_forms_have_one_identity(value: str, repository_root: str | None) -> None:
    assert (
        canonical_repository_path(value, repository_root=repository_root)
        == "src/mgf_mot/example.py"
    )


@pytest.mark.parametrize(
    ("value", "repository_root"),
    [
        ("../outside.py", None),
        (r"C:\other_repo\file.py", r"C:\MOTCS"),
        (r"\\server\share\file.py", r"\\server\share"),
        ("/home/user/unrelated/file.py", "/home/runner/work/MOTCS/MOTCS"),
        (r"C:\MOTCS\src\mgf_mot\example.py", None),
        ("", None),
        ("C:src/example.py", None),
        ("src//mgf_mot/example.py", None),
        ("src/./mgf_mot/example.py", None),
        ("src/mgf_mot/../example.py", None),
    ],
)
def test_invalid_or_ambiguous_paths_fail_closed(value: str, repository_root: str | None) -> None:
    with pytest.raises(RepositoryProvenancePathError):
        canonical_repository_path(value, repository_root=repository_root)


def test_canonicalization_preserves_case_and_unicode_without_realpath() -> None:
    value = "Src/MgF_MOT/ΔExample.py"
    assert canonical_repository_path(value) == value
    assert is_canonical_repository_path(value)
    assert not is_canonical_repository_path(r"Src\MgF_MOT\ΔExample.py")


def test_provenance_audit_is_complete_and_has_no_new_migration() -> None:
    record = json.loads(AUDIT_RECORD.read_text(encoding="utf-8"))
    assert record["audit_status"] == "PROVENANCE_PATH_AUDIT_OK"
    assert record["summary"]["classifications_complete"] is True
    assert record["summary"]["migration_required_count"] == 0
    assert record["summary"]["run_010_paths_canonical"] is True
    assert record["summary"]["representative_equivalence_valid"] is True
    assert record["summary"]["invalid_paths_fail_closed"] is True
    assert {row["subsystem"] for row in record["records"]} >= {
        "Run 010 force-field provenance",
        "molecular-model packages",
        "policy provenance",
        "apparatus profiles",
        "feedback specifications",
        "experiment manifests",
        "release manifest",
        "artifact catalog",
    }
    assert all(value == 0 for value in record["physical_execution_counts"].values())


def test_audit_script_uses_only_static_source_and_metadata_evidence() -> None:
    source = AUDIT_SCRIPT.read_text(encoding="utf-8")
    for forbidden in (
        "build_accepted_provisional_rateeq_backend(",
        "load_force_field_cache(",
        "solve_equilibrium_force(",
        "integrate_policy_trajectory(",
        "save_force_field_cache(",
    ):
        assert forbidden not in source


def test_run_010_migration_keeps_corrected_root_cause_and_historical_gate() -> None:
    record = json.loads(MIGRATION_RECORD.read_text(encoding="utf-8"))
    assert record["corrected_root_cause"] == "OS_DEPENDENT_REPOSITORY_PATH_SERIALIZATION"
    assert record["previous_refinement_gate_honest"] is True
    assert record["previous_refinement_gate"] == "RUN_018_CI_CACHE_PROVENANCE_REFINEMENT_REQUIRED"
    assert record["all_npz_byte_identical"] is True
    assert record["all_arrays_exactly_equal"] is True
    for cache in record["caches"]:
        assert cache["non_source_provenance_fields_unchanged"] is True
        assert cache["old_cache_key"] != cache["new_cache_key"]
        changes = cache["dependency_hash_changes"]
        assert sum(row["hash_changed"] for row in changes) == 1
        changed = next(row for row in changes if row["hash_changed"])
        assert changed["path_canonical"] == "src/mgf_mot/accepted_backend.py"
        assert changed["authorized_plumbing_change"] is True


def test_identity_domains_and_platform_local_boundaries_are_documented() -> None:
    documentation = (ROOT / "docs/provenance-path-portability.md").read_text(encoding="utf-8")
    for phrase in (
        "Artifact byte integrity",
        "Structured semantic identity",
        "Repository dependency path",
        "External source reference",
        "platform-local",
        "policy_specification",
        "family_specification",
    ):
        assert phrase in documentation


def test_ci_retains_all_portability_and_release_gates() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert 'python-version: ["3.10", "3.12"]' in workflow
    for command in (
        "python scripts/audit_canonical_line_endings.py",
        'python -m pip install -e ".[test]"',
        "python -m compileall -q src scripts",
        "python -m pytest -q",
        "python scripts/verify_release_integrity.py",
        "python scripts/audit_model_independent_boundaries.py",
        "python scripts/verify_package_build_run_018.py",
        "python scripts/audit_provenance_path_portability.py",
        "check_documentation_links",
    ):
        assert command in workflow


def test_final_certification_report_has_one_gate_and_required_labels() -> None:
    report = REPORT.read_text(encoding="utf-8")
    for label in (
        "MODEL_INDEPENDENT",
        "NOT_RODRIGUEZ_REPLICATION",
        "RUN_018",
        "CROSS_PLATFORM_PROVENANCE_CERTIFICATION_ONLY",
    ):
        assert label in report
    gates = (
        "RUN_018_CROSS_PLATFORM_PROVENANCE_GO",
        "RUN_018_CROSS_PLATFORM_PROVENANCE_REFINEMENT_REQUIRED",
        "RUN_018_CROSS_PLATFORM_PROVENANCE_NO_GO",
    )
    assert sum(report.count(gate) for gate in gates) == 1
    assert report.rstrip().endswith("RUN_018_CROSS_PLATFORM_PROVENANCE_GO")
