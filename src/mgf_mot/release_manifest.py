"""Run 018 deterministic project-release, integrity, and status primitives."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import sys
from typing import Any, Mapping, Sequence


RELEASE_SCHEMA_VERSION = "mgf-mot-project-release-v1"
AUTHORIZATION_SCHEMA_VERSION = "mgf-mot-authorization-ledger-v1"
ARTIFACT_CATALOG_SCHEMA_VERSION = "mgf-mot-artifact-catalog-v1"
ENVIRONMENT_SCHEMA_VERSION = "mgf-mot-release-environment-v1"
INTEGRITY_SCHEMA_VERSION = "mgf-mot-release-integrity-v1"
PROMOTION_SCHEMA_VERSION = "mgf-mot-model-promotion-record-v1"
GENERATOR_VERSION = "run018-release-generator-v1"
RUN018_LABEL = "MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_018_REPRODUCIBLE_CONTROL_INFRA_RELEASE_ONLY"
RELEASE_LABELS = ("MODEL_INDEPENDENT", "NOT_RODRIGUEZ_REPLICATION", "RUN_018", "REPRODUCIBLE_CONTROL_INFRA_RELEASE_ONLY")
KNOWN_WARNING = {
    "warning_type": "ComplexWarning", "source": "pylcp/rateeq.py:264", "audited_in": "Run 011D",
    "discarded_imaginary_magnitude": 0.0, "classification": "WARNING_IS_NUMERICAL_ROUNDOFF",
    "globally_suppressed": False,
}


class ReleaseError(ValueError):
    pass


@dataclass(frozen=True)
class AuthorizationEntry:
    name: str
    value: bool
    source_run: str
    source_gate: str
    rationale: str


@dataclass(frozen=True)
class AuthorizationLedger:
    schema_version: str
    entries: tuple[AuthorizationEntry, ...]
    labels: tuple[str, ...] = RELEASE_LABELS

    def value(self, name: str) -> bool:
        matches = [item.value for item in self.entries if item.name == name]
        if len(matches) != 1:
            raise ReleaseError(f"authorization {name!r} is missing or duplicated")
        return matches[0]


@dataclass(frozen=True)
class ArtifactRecord:
    path: str
    category: str
    producing_run: str
    semantic_role: str
    sha256: str
    size_bytes: int
    labels: tuple[str, ...]
    protected: bool
    regeneration_command: str | None
    canonical: bool


@dataclass(frozen=True)
class ArtifactCatalog:
    schema_version: str
    artifacts: tuple[ArtifactRecord, ...]
    excluded_patterns: tuple[str, ...]
    labels: tuple[str, ...] = RELEASE_LABELS

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self)


@dataclass(frozen=True)
class ReleaseSemanticManifest:
    schema_version: str
    project_name: str
    release_identifier: str
    source_commit_hash: str | None
    source_tree_hash: str
    python_package_version: str
    supported_python: str
    scientific_gates: Mapping[str, str]
    infrastructure_gates: Mapping[str, str]
    schema_versions: Mapping[str, str]
    accepted_molecular_model_package_hash: str
    protected_artifact_hashes: Mapping[str, str]
    policy_hashes: Mapping[str, str]
    apparatus_profile_hashes: Mapping[str, str]
    example_experiment_hashes: Mapping[str, str]
    authorization_ledger_hash: str
    artifact_catalog_hash: str
    known_warnings: tuple[Mapping[str, Any], ...]
    known_blockers: tuple[str, ...]
    documentation_index: tuple[str, ...]
    generation_tool_version: str
    labels: tuple[str, ...] = RELEASE_LABELS

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self)


@dataclass(frozen=True)
class EnvironmentRecord:
    schema_version: str
    generation_time_utc: str
    operating_system: str
    python_implementation: str
    python_version: str
    direct_dependencies: Mapping[str, str]
    installed_versions: Mapping[str, str | None]
    environment_kind: str
    labels: tuple[str, ...] = RELEASE_LABELS


@dataclass(frozen=True)
class ReleaseBundle:
    semantic_manifest: ReleaseSemanticManifest
    environment: EnvironmentRecord
    artifact_catalog: ArtifactCatalog
    authorization_ledger: AuthorizationLedger


@dataclass(frozen=True)
class IntegrityReport:
    schema_version: str
    release_hash_valid: bool
    schema_valid: bool
    gates_valid: bool
    authorizations_valid: bool
    documentation_links_valid: bool
    warning_ledger_valid: bool
    modified_files: tuple[str, ...]
    missing_files: tuple[str, ...]
    unexpected_files: tuple[str, ...]
    conflicting_files: tuple[str, ...]
    status: str
    labels: tuple[str, ...] = RELEASE_LABELS

    @property
    def valid(self) -> bool:
        return self.status == "RELEASE_INTEGRITY_OK"


def _plain(value: Any) -> Any:
    if isinstance(value, Enum): return value.value
    if is_dataclass(value): return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping): return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)): return [_plain(item) for item in value]
    if callable(value): raise ReleaseError("arbitrary executable content is forbidden")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def semantic_hash(value: Any) -> str:
    return sha256(canonical_json(value).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_plain(value), indent=2, sort_keys=True, allow_nan=False) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def authorization_ledger(gates: Mapping[str, str], *, release_ready: bool) -> AuthorizationLedger:
    def entry(name: str, value: bool, run: str, gate: str, reason: str) -> AuthorizationEntry:
        return AuthorizationEntry(name, value, run, gate, reason)
    enabled = (
        ("molecular_model_interchange_authorized", "Run 012", "MOLECULAR_MODEL_INTERCHANGE_READY"),
        ("control_policy_abi_authorized", "Run 013", "CONTROL_POLICY_ABI_GO"),
        ("apparatus_schedule_compiler_authorized", "Run 014", "APPARATUS_SCHEDULE_COMPILER_GO"),
        ("open_loop_policy_families_authorized", "Run 015", "OPEN_LOOP_POLICY_FAMILIES_GO"),
        ("feedback_policy_interface_authorized", "Run 016", "FEEDBACK_POLICY_INTERFACE_GO"),
        ("experiment_protocol_authorized", "Run 017", "CONTROL_EXPERIMENT_INFRA_READY"),
        ("synthetic_trial_execution_authorized", "Run 017", "CONTROL_EXPERIMENT_INFRA_READY"),
        ("optimizer_adapter_interface_authorized", "Run 017", "CONTROL_EXPERIMENT_INFRA_READY"),
    )
    rows = [entry(name, gates.get(run) == gate, run, gate, "accepted infrastructure gate") for name, run, gate in enabled]
    rows.extend(entry(name, False, "Run 018", "REPRODUCIBLE_CONTROL_INFRA_RELEASE_READY" if release_ready else "PENDING",
                      reason) for name, reason in (
        ("optimizer_implementation_authorized", "no optimizer implementation is authorized"),
        ("optimization_run_authorized", "no optimization run is authorized"),
        ("physical_evaluator_authorized", "published force structure is not reproduced"),
        ("physical_objective_authorized", "physical metrics remain locked"),
        ("capture_metric_authorized", "capture remains locked"),
        ("capture_authorized", "capture remains locked"),
        ("real_sensor_model_validated", "only synthetic observation fixtures are validated"),
        ("real_apparatus_profile_validated", "only synthetic or source-incomplete profiles exist"),
        ("hardware_executable_claim_valid", "no real apparatus has been validated"),
        ("reinforcement_learning_authorized", "reinforcement learning is outside authorized scope"),
        ("exact_replication_valid", "published force structure has not been reproduced"),
        ("track_e_blocked", "inverted semantic flag; replaced below"),
        ("automatic_model_promotion_authorized", "promotion requires a later reviewed gate"),
    ))
    rows[-2] = replace(rows[-2], value=True, rationale="awaiting original Rodriguez molecular-model objects")
    rows.extend((
        entry("release_manifest_authorized", release_ready, "Run 018", "REPRODUCIBLE_CONTROL_INFRA_RELEASE_READY", "release audit gate"),
        entry("author_model_intake_pipeline_authorized", release_ready, "Run 018", "REPRODUCIBLE_CONTROL_INFRA_RELEASE_READY", "quarantined preserve-validate-compare workflow only"),
    ))
    return AuthorizationLedger(AUTHORIZATION_SCHEMA_VERSION, tuple(sorted(rows, key=lambda item: item.name)))


def protected_paths(root: Path) -> tuple[Path, ...]:
    patterns = (
        "outputs/provisional/*RUN_010*", "outputs/provisional/*RUN_011*", "outputs/provisional/*RUN_012*",
        "outputs/provisional/*RUN_013*", "outputs/provisional/*RUN_014*", "outputs/provisional/*RUN_015*",
        "outputs/provisional/*RUN_016*", "outputs/provisional/*RUN_017*",
        "outputs/provisional/force_fields/**/*", "outputs/provisional/molecular_model_packages/run_012/**/*",
        "outputs/provisional/control_policy_abi/run_013/**/*", "outputs/provisional/apparatus_schedule_compiler/run_014/**/*",
        "outputs/provisional/open_loop_policy_families/run_015/**/*", "outputs/provisional/feedback_policy_interface/run_016/**/*",
        "outputs/provisional/experiment_search_protocol/run_017/**/*", "outputs/provisional/experiments/run_017/**/*",
        "outputs/provisional/molecular_model_audit/**/*", "outputs/provisional/paper_digitization/**/*",
        "configs/*.yaml", "configs/run_015/*.yaml", "configs/run_016/*.yaml", "configs/run_017/*.yaml",
    )
    paths: set[Path] = set()
    for pattern in patterns: paths.update(item for item in root.glob(pattern) if item.is_file())
    return tuple(sorted(paths))


def protected_hashes(root: Path) -> Mapping[str, str]:
    return {path.relative_to(root).as_posix(): file_hash(path) for path in protected_paths(root)}


def _category(path: Path) -> str:
    if path.parts[0] == "src": return "source"
    if path.parts[0] == "tests": return "test"
    if path.parts[0] == "scripts": return "script"
    if path.parts[0] == "configs": return "configuration"
    if path.parts[0] == "docs": return "documentation"
    if path.parts[0] == ".github": return "continuous_integration"
    if path.parts[0] == "outputs": return "protected_output"
    return "project_metadata"


def _producing_run(path: Path) -> str:
    match = re.search(r"RUN[_ -]?(\d{3}[A-Z]?(?:-R1)?)", path.as_posix(), re.IGNORECASE)
    return f"Run {match.group(1).upper().replace('-R1', '-R1')}" if match else "PROJECT"


def catalog_paths(root: Path) -> tuple[Path, ...]:
    paths: set[Path] = {root / "pyproject.toml", root / "README.md", root / ".gitattributes", root / ".gitignore"}
    for pattern in ("src/**/*.py", "scripts/*.py", "tests/*.py", "configs/**/*.yaml", "docs/**/*.md", ".github/workflows/*.yml", ".github/workflows/*.yaml"):
        paths.update(item for item in root.glob(pattern) if item.is_file())
    paths.update(protected_paths(root))
    return tuple(sorted(path for path in paths if not any(part in {"__pycache__", ".pytest_cache", ".git", "tmp"} for part in path.parts)))


def build_artifact_catalog(root: Path) -> ArtifactCatalog:
    protected = set(protected_paths(root)); rows = []
    commands = {"Run 012": "python scripts/export_accepted_molecular_model.py", "Run 013": "python scripts/validate_control_policy_abi_v2.py",
                "Run 014": "python scripts/compile_control_policies_run_014.py", "Run 015": "python scripts/validate_open_loop_policy_families_run_015.py",
                "Run 016": "python scripts/validate_feedback_policy_interface_run_016.py", "Run 017": "python scripts/validate_experiment_search_protocol_run_017.py"}
    for absolute in catalog_paths(root):
        relative = absolute.relative_to(root); run = _producing_run(relative); text = relative.as_posix().upper()
        labels = tuple(label for label in ("MODEL_INDEPENDENT", "PROVISIONAL", "NOT_RODRIGUEZ_REPLICATION", "EXACT") if label in text)
        rows.append(ArtifactRecord(relative.as_posix(), _category(relative), run, f"canonical {_category(relative).replace('_', ' ')}",
            file_hash(absolute), absolute.stat().st_size, labels, absolute in protected, commands.get(run), True))
    return ArtifactCatalog(ARTIFACT_CATALOG_SCHEMA_VERSION, tuple(sorted(rows, key=lambda item: item.path)), ("**/__pycache__/**", ".pytest_cache/**", "tmp/**", "*.tmp", ".git/**"))


def check_documentation_links(root: Path) -> tuple[str, ...]:
    broken = []
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for document in sorted((root / "docs").rglob("*.md")):
        for target in pattern.findall(document.read_text(encoding="utf-8")):
            target = target.strip().strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if not (document.parent / target).resolve().exists():
                broken.append(f"{document.relative_to(root).as_posix()} -> {target}")
    return tuple(broken)


def audit_forbidden_boundaries(root: Path, scripts: Sequence[Path]) -> Mapping[str, Any]:
    forbidden_modules = {"mgf_mot.rateeq_backend", "mgf_mot.force_field", "mgf_mot.trajectory", "mgf_mot.outcomes", "scipy.optimize", "torch", "gym"}
    forbidden_calls = {"build_accepted_provisional_rateeq_backend", "load_force_field_cache", "integrate_policy_trajectory", "classify_outcome", "minimize", "train"}
    violations = []
    for path in scripts:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name == item or alias.name.startswith(item + ".") for item in forbidden_modules): violations.append(f"{path.name}:import:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if any(module == item or module.startswith(item + ".") for item in forbidden_modules): violations.append(f"{path.name}:from:{module}")
            elif isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
                if name in forbidden_calls: violations.append(f"{path.name}:call:{name}")
    return {"audited_modules": [path.relative_to(root).as_posix() for path in scripts], "forbidden_boundary": sorted(forbidden_modules | forbidden_calls), "violations": violations, "passed": not violations, "allowed_references": "data-only provenance and documentation strings"}


def environment_record(generation_time_utc: str, installed_versions: Mapping[str, str | None]) -> EnvironmentRecord:
    return EnvironmentRecord(ENVIRONMENT_SCHEMA_VERSION, generation_time_utc, platform.system(), platform.python_implementation(), platform.python_version(),
                             {"PyYAML": ">=6.0", "pylcp": "==1.0.2"}, dict(sorted(installed_versions.items())),
                             "AUDIT_SNAPSHOT_NOT_A_UNIVERSAL_LOCKFILE")


def load_release_bundle(directory: Path) -> ReleaseBundle:
    def read(name: str) -> Any: return json.loads((directory / name).read_text(encoding="utf-8"))
    s = read("semantic-release-manifest.json"); e = read("environment-record.json"); c = read("artifact-catalog.json"); a = read("authorization-ledger.json")
    catalog = ArtifactCatalog(c["schema_version"], tuple(ArtifactRecord(**row) for row in c["artifacts"]), tuple(c["excluded_patterns"]), tuple(c["labels"]))
    ledger = AuthorizationLedger(a["schema_version"], tuple(AuthorizationEntry(**row) for row in a["entries"]), tuple(a["labels"]))
    semantic = ReleaseSemanticManifest(**{**s["semantic_manifest"], "known_warnings": tuple(s["semantic_manifest"]["known_warnings"]), "known_blockers": tuple(s["semantic_manifest"]["known_blockers"]), "documentation_index": tuple(s["semantic_manifest"]["documentation_index"]), "labels": tuple(s["semantic_manifest"]["labels"])})
    environment = EnvironmentRecord(**{**e, "labels": tuple(e["labels"])})
    return ReleaseBundle(semantic, environment, catalog, ledger)


def verify_bundle(root: Path, bundle: ReleaseBundle) -> IntegrityReport:
    modified = []; missing = []; conflicting = []
    for item in bundle.artifact_catalog.artifacts:
        path = root / item.path
        if not path.is_file(): missing.append(item.path)
        elif file_hash(path) != item.sha256: modified.append(item.path)
    recorded_paths = {item.path for item in bundle.artifact_catalog.artifacts}
    current_paths = {item.relative_to(root).as_posix() for item in catalog_paths(root)}
    unexpected = sorted(current_paths - recorded_paths)
    catalog_valid = semantic_hash(bundle.artifact_catalog) == bundle.semantic_manifest.artifact_catalog_hash
    ledger_valid = semantic_hash(bundle.authorization_ledger) == bundle.semantic_manifest.authorization_ledger_hash
    schemas = (bundle.semantic_manifest.schema_version == RELEASE_SCHEMA_VERSION and bundle.artifact_catalog.schema_version == ARTIFACT_CATALOG_SCHEMA_VERSION and bundle.authorization_ledger.schema_version == AUTHORIZATION_SCHEMA_VERSION)
    required_false = ("optimizer_implementation_authorized", "optimization_run_authorized", "physical_evaluator_authorized", "capture_authorized", "automatic_model_promotion_authorized", "exact_replication_valid")
    authorizations = ledger_valid and all(not bundle.authorization_ledger.value(name) for name in required_false) and bundle.authorization_ledger.value("track_e_blocked")
    links = check_documentation_links(root)
    warning_valid = tuple(bundle.semantic_manifest.known_warnings) == (KNOWN_WARNING,)
    release_hash_valid = catalog_valid and bundle.semantic_manifest.source_tree_hash == semantic_hash(tuple((item.path, item.sha256) for item in bundle.artifact_catalog.artifacts))
    gates_valid = bundle.semantic_manifest.infrastructure_gates.get("Run 017") == "CONTROL_EXPERIMENT_INFRA_READY"
    valid = release_hash_valid and schemas and gates_valid and authorizations and not links and warning_valid and not modified and not missing and not unexpected and not conflicting
    return IntegrityReport(INTEGRITY_SCHEMA_VERSION, release_hash_valid, schemas, gates_valid, authorizations, not links, warning_valid,
                           tuple(modified), tuple(missing), tuple(unexpected), tuple(conflicting), "RELEASE_INTEGRITY_OK" if valid else "RELEASE_INTEGRITY_FAILED")
