from __future__ import annotations
from dataclasses import replace
import json
from pathlib import Path
import shutil

from mgf_mot.model_intake import INTAKE_SCHEMA_VERSION, intake_molecular_model
from mgf_mot.molecular_model_package import RUN012_LABEL
from mgf_mot.release_manifest import (
    ARTIFACT_CATALOG_SCHEMA_VERSION, AUTHORIZATION_SCHEMA_VERSION, KNOWN_WARNING,
    RELEASE_SCHEMA_VERSION, ArtifactCatalog, ArtifactRecord, build_artifact_catalog,
    check_documentation_links, file_hash, load_release_bundle, protected_hashes,
    semantic_hash, verify_bundle,
)

ROOT=Path(__file__).resolve().parents[1];RELEASE=ROOT/"outputs/provisional/release/run_018"
ACCEPTED=ROOT/"outputs/provisional/molecular_model_packages/run_012"/f"{RUN012_LABEL}_ACCEPTED_PROVISIONAL_REFERENCE_PACKAGE"


def test_release_schemas_and_semantic_environment_separation():
    bundle=load_release_bundle(RELEASE)
    assert bundle.semantic_manifest.schema_version==RELEASE_SCHEMA_VERSION
    assert bundle.artifact_catalog.schema_version==ARTIFACT_CATALOG_SCHEMA_VERSION
    assert bundle.authorization_ledger.schema_version==AUTHORIZATION_SCHEMA_VERSION
    before=bundle.semantic_manifest.semantic_hash
    changed_environment=replace(bundle.environment,generation_time_utc="2099-01-01T00:00:00Z",operating_system="other")
    assert bundle.semantic_manifest.semantic_hash==before and changed_environment!=bundle.environment


def test_catalog_order_is_deterministic_complete_and_excludes_volatile_files():
    a=build_artifact_catalog(ROOT);b=build_artifact_catalog(ROOT)
    assert a==b and [item.path for item in a.artifacts]==sorted(item.path for item in a.artifacts)
    assert any(item.category=="test" for item in a.artifacts) and any(item.category=="protected_output" for item in a.artifacts)
    assert all("__pycache__" not in item.path and ".pytest_cache" not in item.path and not item.path.startswith("tmp/") for item in a.artifacts)


def _rebundle_with_catalog(bundle,catalog):
    manifest=replace(bundle.semantic_manifest,artifact_catalog_hash=semantic_hash(catalog),source_tree_hash=semantic_hash(tuple((item.path,item.sha256) for item in catalog.artifacts)))
    return replace(bundle,semantic_manifest=manifest,artifact_catalog=catalog)


def test_integrity_detects_missing_and_changed_cataloged_files():
    bundle=load_release_bundle(RELEASE);items=list(bundle.artifact_catalog.artifacts)
    fake=ArtifactRecord("definitely/missing", "test", "Run 018", "fixture", "0"*64, 0, (), True, None, True)
    missing_catalog=replace(bundle.artifact_catalog,artifacts=tuple(sorted(items+[fake],key=lambda x:x.path)))
    missing=verify_bundle(ROOT,_rebundle_with_catalog(bundle,missing_catalog));assert "definitely/missing" in missing.missing_files and not missing.valid
    first=items[0];items[0]=replace(first,sha256="f"*64)
    changed_catalog=replace(bundle.artifact_catalog,artifacts=tuple(items));changed=verify_bundle(ROOT,_rebundle_with_catalog(bundle,changed_catalog))
    assert first.path in changed.modified_files and not changed.valid


def test_authorization_ledger_is_sourced_and_fail_closed():
    ledger=load_release_bundle(RELEASE).authorization_ledger
    assert all(item.source_run and item.source_gate and item.rationale for item in ledger.entries)
    for name in ("molecular_model_interchange_authorized","control_policy_abi_authorized","apparatus_schedule_compiler_authorized","open_loop_policy_families_authorized","feedback_policy_interface_authorized","experiment_protocol_authorized","synthetic_trial_execution_authorized","optimizer_adapter_interface_authorized","release_manifest_authorized","author_model_intake_pipeline_authorized"):
        assert ledger.value(name)
    for name in ("optimizer_implementation_authorized","optimization_run_authorized","physical_evaluator_authorized","capture_authorized","automatic_model_promotion_authorized","exact_replication_valid"):
        assert not ledger.value(name)
    assert ledger.value("track_e_blocked")


def test_readme_status_and_run_index_cover_authoritative_state():
    readme=(ROOT/"README.md").read_text(encoding="utf-8");status=(ROOT/"docs/current-project-status.md").read_text(encoding="utf-8");index=(ROOT/"docs/run-index.md").read_text(encoding="utf-8")
    assert "published force structure has not" in readme.lower()
    assert "The rate-equation and numerical machinery has been reproduced, but the published force structure has not." in status
    for run in [f"{x:03d}" for x in range(1,19)]:assert run in index
    for variant in ("011A","011B","011C","011D"):assert variant in index


def test_documentation_index_has_no_broken_relative_links():
    assert check_documentation_links(ROOT)==()
    index=(ROOT/"docs/README.md").read_text(encoding="utf-8")
    for name in ("current-project-status.md","molecular-model-interchange.md","control-policy-abi-v2.md","experiment-and-search-protocol.md","author-model-arrival-runbook.md","reproducibility.md","run-index.md"):assert name in index


def test_known_warning_is_narrow_and_not_globally_suppressed():
    warnings=load_release_bundle(RELEASE).semantic_manifest.known_warnings
    assert warnings==(KNOWN_WARNING,) and warnings[0]["source"]=="pylcp/rateeq.py:264"
    assert warnings[0]["discarded_imaginary_magnitude"]==0 and not warnings[0]["globally_suppressed"]


def test_package_build_report_excludes_transient_and_large_outputs():
    report=json.loads((RELEASE/"package-content-report.json").read_text(encoding="utf-8"))
    assert report["build_status"]=="PACKAGE_BUILD_OK" and report["forbidden_members"]==[]
    assert report["installed_import_smoke"]=="MODEL_INDEPENDENT_SMOKE_OK" and not report["published"]
    assert not report["includes_force_caches"] and not report["includes_transient_outputs"]


def test_integrity_verification_is_read_only_and_current_release_passes():
    before={p.name:file_hash(p) for p in RELEASE.glob("*.json")};report=verify_bundle(ROOT,load_release_bundle(RELEASE));after={p.name:file_hash(p) for p in RELEASE.glob("*.json")}
    assert report.valid and report.status=="RELEASE_INTEGRITY_OK" and before==after


def test_project_status_script_reads_release_bundle_not_duplicate_constants():
    source=(ROOT/"scripts/show_project_status.py").read_text(encoding="utf-8")
    assert "load_release_bundle" in source and "CONTROL_EXPERIMENT_INFRA_READY" not in source


def test_intake_preserves_hashes_validates_compares_and_never_promotes(tmp_path):
    accepted_before={suffix:file_hash(Path(f"{ACCEPTED}{suffix}")) for suffix in (".npz",".metadata.json",".manifest.json")}
    result=intake_molecular_model(ACCEPTED,tmp_path/"quarantine","test equivalent package",accepted_base=ACCEPTED)
    assert result.schema_version==INTAKE_SCHEMA_VERSION and not result.validation_errors and result.equivalent_to_accepted
    assert result.source_file_hashes==result.preserved_file_hashes and not result.accepted_package_replaced and not result.automatic_promotion_authorized
    assert result.force_cache_rebuilds==result.trajectory_integrations==result.capture_calculations==0
    assert accepted_before=={suffix:file_hash(Path(f"{ACCEPTED}{suffix}")) for suffix in accepted_before}


def test_malformed_intake_fails_closed_without_writing_or_promoting(tmp_path):
    base=tmp_path/"bad"
    for suffix in (".npz",".metadata.json",".manifest.json"):shutil.copyfile(Path(f"{ACCEPTED}{suffix}"),Path(f"{base}{suffix}"))
    path=Path(f"{base}.metadata.json");data=json.loads(path.read_text(encoding="utf-8"));data.pop("basis");path.write_text(json.dumps(data),encoding="utf-8")
    result=intake_molecular_model(base,tmp_path/"unused","malformed test",accepted_base=ACCEPTED,validation_only=True)
    assert result.validation_errors and result.quarantine_directory is None and not result.accepted_package_replaced


def test_ci_and_forbidden_boundary_audit_do_not_execute_locked_paths():
    ci=(ROOT/".github/workflows/ci.yml").read_text(encoding="utf-8");audit=json.loads((RELEASE/"forbidden-boundary-audit.json").read_text(encoding="utf-8"))
    for command in ("compileall","pytest","verify_release_integrity.py","audit_model_independent_boundaries.py","verify_package_build_run_018.py"):assert command in ci
    assert audit["passed"] and audit["violations"]==[]
    for forbidden in ("run_provisional_trajectory","build_and_validate_provisional_force_fields","scipy.optimize","import torch","import gym"):assert forbidden not in ci


def test_protected_runs_010_through_017_match_release_manifest():
    bundle=load_release_bundle(RELEASE);assert dict(protected_hashes(ROOT))==dict(bundle.semantic_manifest.protected_artifact_hashes)
    audit=json.loads((RELEASE/"run-018-audit.json").read_text(encoding="utf-8"))
    assert audit["protected_artifacts_unchanged"] and audit["gate"]=="REPRODUCIBLE_CONTROL_INFRA_RELEASE_READY"
    for key in ("molecular_force_evaluations","force_cache_rebuilds","molecular_trajectory_integrations","capture_metrics","optimizer_implementations","optimization_runs","controller_training_runs","model_promotions","hardware_validations"):assert audit[key]==0
