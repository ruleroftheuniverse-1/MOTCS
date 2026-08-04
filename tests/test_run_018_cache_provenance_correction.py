from __future__ import annotations

from dataclasses import replace
import importlib.util
from importlib.metadata import metadata
import json
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pytest

from mgf_mot.accepted_backend import accepted_force_field_source_hashes
from mgf_mot.accepted_trajectory import InterpolatedRateEquationTrajectoryForce
from mgf_mot.force_field import (
    ForceFieldCacheMismatchError,
    ForceFieldProvenance,
    load_force_field_cache,
)
from mgf_mot.release_manifest import load_release_bundle, verify_bundle


ROOT = Path(__file__).resolve().parents[1]
FORCE_DIR = ROOT / "outputs/provisional/force_fields"
SCRIPT = ROOT / "scripts/migrate_run_010_cache_provenance_to_canonical_lf.py"
RECORD = FORCE_DIR / "run_018_cache_provenance_migration.json"


def _migration_module():
    spec = importlib.util.spec_from_file_location("run018_cache_migration", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _migration_module()


def _legacy_root(tmp_path: Path) -> Path:
    for relative in MIGRATION.SOURCE_DEPENDENCIES:
        source = ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        if relative == "src/mgf_mot/accepted_backend.py":
            assert data.count(MIGRATION._PATH_FIX_NEW) == 1
            data = data.replace(MIGRATION._PATH_FIX_NEW, MIGRATION._PATH_FIX_OLD, 1)
        destination.write_bytes(data)
    destination_dir = tmp_path / "outputs/provisional/force_fields"
    destination_dir.mkdir(parents=True, exist_ok=True)
    for _, (npz_name, metadata_name) in MIGRATION.CACHE_FILENAMES.items():
        shutil.copyfile(FORCE_DIR / npz_name, destination_dir / npz_name)
        backup_name = metadata_name.replace(
            "_run_010_metadata.json", "_run_010_PRE_MIGRATION.json"
        )
        shutil.copyfile(
            FORCE_DIR / "run_018_migration_inputs" / backup_name,
            destination_dir / metadata_name,
        )
    return tmp_path


@pytest.fixture(scope="module")
def adapter() -> InterpolatedRateEquationTrajectoryForce:
    return InterpolatedRateEquationTrajectoryForce(
        repo_root=ROOT,
        explicit_provisional_opt_in=True,
        acknowledge_midpoint_not_measured=True,
    )


@pytest.fixture
def short_tmp_root():
    with tempfile.TemporaryDirectory(prefix="r18_") as directory:
        yield Path(directory)


def test_test_extra_declares_direct_digitization_dependencies_and_module_imports() -> None:
    requirements = metadata("mgf-mot-force-map").get_all("Requires-Dist") or []
    assert any(item.startswith("Pillow>=10.0") and "extra == \"test\"" in item for item in requirements)
    assert any(item.startswith("pdfplumber>=0.11.0") and "extra == \"test\"" in item for item in requirements)
    spec = importlib.util.spec_from_file_location(
        "run011b_digitizer_dependency_smoke",
        ROOT / "scripts/digitize_rodriguez_force_figures.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.Image.__version__
    assert module.pdfplumber.__version__


def test_migration_is_deterministic_idempotent_and_array_preserving(short_tmp_root: Path, monkeypatch) -> None:
    root = _legacy_root(short_tmp_root)
    npz_hashes = {
        name: MIGRATION._hash_file(root / "outputs/provisional/force_fields" / name)
        for name, _ in MIGRATION.CACHE_FILENAMES.values()
    }
    monkeypatch.setattr(np, "savez", lambda *args, **kwargs: pytest.fail("NPZ write attempted"))
    monkeypatch.setattr(np, "savez_compressed", lambda *args, **kwargs: pytest.fail("NPZ write attempted"))
    first = MIGRATION.migrate(root, test_result="TEST_PASS")
    metadata_hashes = {
        name: MIGRATION._hash_file(root / "outputs/provisional/force_fields" / name)
        for _, name in MIGRATION.CACHE_FILENAMES.values()
    }
    second = MIGRATION.migrate(root, test_result="TEST_PASS")
    assert all(row["initial_state"] == "LEGACY_RECOGNIZED" for row in first["caches"])
    assert all(row["initial_state"] == "ALREADY_MIGRATED" for row in second["caches"])
    assert all(not row["metadata_write_performed"] for row in second["caches"])
    assert all(row["npz_byte_identical"] and row["arrays_exactly_equal"] for row in second["caches"])
    assert metadata_hashes == {
        name: MIGRATION._hash_file(root / "outputs/provisional/force_fields" / name)
        for _, name in MIGRATION.CACHE_FILENAMES.values()
    }
    assert npz_hashes == {
        name: MIGRATION._hash_file(root / "outputs/provisional/force_fields" / name)
        for name, _ in MIGRATION.CACHE_FILENAMES.values()
    }


def test_migration_rejects_semantic_source_and_unexplained_hash_changes(short_tmp_root: Path) -> None:
    semantic_root = _legacy_root(short_tmp_root / "semantic")
    spectroscopy = semantic_root / "src/mgf_mot/spectroscopy.py"
    spectroscopy.write_text(spectroscopy.read_text(encoding="utf-8") + "\nSEMANTIC_CHANGE = True\n", encoding="utf-8")
    with pytest.raises(MIGRATION.CacheProvenanceMigrationError, match="neither line-ending-only"):
        MIGRATION.migrate(semantic_root)

    unexplained_root = _legacy_root(short_tmp_root / "unexplained")
    _, metadata_name = MIGRATION.CACHE_FILENAMES["pre_handoff_chirp_3"]
    metadata_path = unexplained_root / "outputs/provisional/force_fields" / metadata_name
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["provenance"]["source_hashes"][0][1] = "0" * 64
    metadata["cache_key"] = MIGRATION._canonical_cache_key(metadata["provenance"])
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(MIGRATION.CacheProvenanceMigrationError, match="neither line-ending-only"):
        MIGRATION.migrate(unexplained_root)


def test_migration_record_proves_path_hash_and_numerical_identity() -> None:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    assert record["all_npz_byte_identical"]
    assert record["all_arrays_exactly_equal"]
    assert record["all_dependency_changes_explained"]
    assert record["requested_line_ending_only_cache_key_gate_satisfied"] is False
    assert record["operational_cross_platform_ci_correction_validated"] is True
    assert record["final_gate"] == "RUN_018_CI_CACHE_PROVENANCE_REFINEMENT_REQUIRED"
    assert record["canonical_lf_provenance_is_sole_accepted_state"]
    assert record["strict_mismatch_detection_retained"]
    assert record["run_010_numerical_cache_status"] == "RUN_010_NUMERICAL_CACHE_UNCHANGED"
    assert record["run_018_provenance_status"] == "RUN_018_PROVENANCE_METADATA_MIGRATED"
    assert len(record["caches"]) == 2
    for cache in record["caches"]:
        assert cache["old_cache_key"] != cache["new_cache_key"]
        assert cache["old_metadata_sha256"] != cache["new_metadata_sha256"]
        assert cache["npz_sha256_before"] == cache["npz_sha256_after"]
        assert cache["arrays_before"] == cache["arrays_after"]
        assert len(cache["dependency_hash_changes"]) == 11
        assert all(row["path_canonical"] == row["path_canonical"].replace("\\", "/") for row in cache["dependency_hash_changes"])
        assert sum(row["hash_changed"] for row in cache["dependency_hash_changes"]) == 1


def test_migrated_cache_loads_and_legacy_key_has_no_fallback(adapter) -> None:
    assert adapter.pre_cache_key == adapter.pre.grid.provenance.cache_key
    assert adapter.post_cache_key == adapter.post.grid.provenance.cache_key
    for cache_kind, (npz_name, metadata_name) in MIGRATION.CACHE_FILENAMES.items():
        backup_name = metadata_name.replace(
            "_run_010_metadata.json", "_run_010_PRE_MIGRATION.json"
        )
        legacy = json.loads((FORCE_DIR / "run_018_migration_inputs" / backup_name).read_text(encoding="utf-8"))
        legacy_provenance = ForceFieldProvenance(**legacy["provenance"])
        with pytest.raises(ForceFieldCacheMismatchError, match="provenance hash differs"):
            load_force_field_cache(FORCE_DIR / npz_name, FORCE_DIR / metadata_name, legacy_provenance)


@pytest.mark.parametrize(
    ("relative_path", "replacement"),
    [
        ("src/mgf_mot/spectroscopy.py", b"\nSEMANTIC_SOURCE_CHANGE = True\n"),
        ("configs/rodriguez_gaussian_baseline.yaml", b"\nsemantic_config_change: true\n"),
    ],
)
def test_genuine_source_or_configuration_change_still_fails_closed(
    adapter, tmp_path: Path, relative_path: str, replacement: bytes
) -> None:
    for source_relative in MIGRATION.SOURCE_DEPENDENCIES:
        source = ROOT / source_relative
        destination = tmp_path / source_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    changed = tmp_path / relative_path
    changed.write_bytes(changed.read_bytes() + replacement)
    changed_hashes = accepted_force_field_source_hashes(tmp_path)
    expected = replace(adapter.pre.grid.provenance, source_hashes=changed_hashes)
    npz_name, metadata_name = MIGRATION.CACHE_FILENAMES["pre_handoff_chirp_3"]
    with pytest.raises(ForceFieldCacheMismatchError, match="provenance hash differs"):
        load_force_field_cache(FORCE_DIR / npz_name, FORCE_DIR / metadata_name, expected)


def test_migration_source_has_no_builder_solver_or_trajectory_calls() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in (
        "save_force_field_cache(",
        "build_and_validate_provisional_force_fields",
        "build_accepted_provisional_rateeq_backend(",
        "solve_equilibrium_force(",
        "integrate_accepted_force_field_trajectory(",
        "integrate_policy_trajectory(",
    ):
        assert forbidden not in source


def test_release_integrity_covers_migrated_metadata() -> None:
    release = ROOT / "outputs/provisional/release/run_018"
    result = verify_bundle(ROOT, load_release_bundle(release))
    assert result.valid, result
