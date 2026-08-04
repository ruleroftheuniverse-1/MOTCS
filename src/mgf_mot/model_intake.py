"""Run 018 preserve-first molecular-model package intake; never promotion."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Mapping

from .molecular_model_package import MolecularModelPackageError, compare_packages, load_package, validate_package
from .release_manifest import RELEASE_LABELS, atomic_write_json, file_hash, semantic_hash


INTAKE_SCHEMA_VERSION = "mgf-mot-author-model-intake-v1"
PROMOTION_RECORD_SCHEMA_VERSION = "mgf-mot-model-promotion-record-v1"


@dataclass(frozen=True)
class IntakeResult:
    schema_version: str
    source_description: str
    source_base: str
    source_file_hashes: Mapping[str, str]
    source_bundle_hash: str
    quarantine_directory: str | None
    preserved_file_hashes: Mapping[str, str]
    validation_gate: str
    validation_errors: tuple[str, ...]
    validation_warnings: tuple[str, ...]
    package_hash: str | None
    compared_with_accepted_hash: str | None
    equivalent_to_accepted: bool | None
    accepted_package_replaced: bool
    automatic_promotion_authorized: bool
    force_cache_rebuilds: int
    trajectory_integrations: int
    capture_calculations: int
    labels: tuple[str, ...] = RELEASE_LABELS


def package_files(base: Path) -> tuple[Path, Path, Path]:
    text = str(base)
    for suffix in (".npz", ".metadata.json", ".manifest.json"):
        if text.endswith(suffix): text = text[:-len(suffix)]
    base = Path(text)
    return Path(f"{base}.npz"), Path(f"{base}.metadata.json"), Path(f"{base}.manifest.json")


def _bundle_hash(hashes: Mapping[str, str]) -> str:
    return semantic_hash(tuple(sorted(hashes.items())))


def intake_molecular_model(source: Path, quarantine_root: Path, source_description: str,
                           *, accepted_base: Path | None = None, validation_only: bool = False) -> IntakeResult:
    if not source_description.strip(): raise ValueError("source description is mandatory")
    files = package_files(source)
    missing = [str(path) for path in files if not path.is_file()]
    if missing: raise MolecularModelPackageError("intake source files are missing: " + ", ".join(missing))
    source_hashes = {path.name: file_hash(path) for path in files}; bundle_hash = _bundle_hash(source_hashes)
    quarantine = None; preserved = {}
    intake_base = source
    if not validation_only:
        quarantine = quarantine_root / bundle_hash
        quarantine.mkdir(parents=True, exist_ok=True)
        canonical_names = ("package.npz", "package.metadata.json", "package.manifest.json")
        for path, canonical_name in zip(files, canonical_names):
            target = quarantine / canonical_name
            if target.exists() and file_hash(target) != source_hashes[path.name]:
                raise MolecularModelPackageError(f"quarantine conflict for {target}")
            if not target.exists():
                temporary = target.with_name(target.name + ".tmp")
                shutil.copyfile(path, temporary); temporary.replace(target)
            preserved[path.name] = file_hash(target)
        intake_base = quarantine / "package"
    errors = (); warnings = (); gate = "IMPORT_INVALID"; package_hash = None; equivalent = None; accepted_hash = None
    try:
        package = load_package(intake_base, validate=False); validation = validate_package(package, include_equilibrium=False)
        errors = validation.errors; warnings = validation.warnings; gate = validation.gate.value; package_hash = validation.package_hash
        if accepted_base is not None:
            accepted = load_package(accepted_base); accepted_hash = accepted.hashes().full_package
            equivalent = compare_packages(package, accepted).equivalent if validation.valid else False
    except (MolecularModelPackageError, ValueError, KeyError, json.JSONDecodeError) as exc:
        errors = (str(exc),)
    result = IntakeResult(INTAKE_SCHEMA_VERSION, source_description, str(source), source_hashes, bundle_hash,
        None if quarantine is None else str(quarantine), preserved, gate, tuple(errors), tuple(warnings), package_hash,
        accepted_hash, equivalent, False, False, 0, 0, 0)
    if quarantine is not None:
        atomic_write_json(quarantine / "intake-record.json", result)
    return result
