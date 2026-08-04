# Reproducibility

## Environment and installation

The project uses its existing `pyproject.toml`/pip workflow; Run 018 does not introduce another package manager.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test]"
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m compileall -q src scripts
```

The environment record under `outputs/provisional/release/run_018/` lists direct requirements and installed audit versions. It is an environment snapshot, not a universal lockfile.

## Focused validation and packages

```powershell
.venv\Scripts\python scripts/validate_molecular_model_package.py <package-base>
.venv\Scripts\python scripts/validate_experiment_search_protocol_run_017.py
.venv\Scripts\python scripts/verify_package_build_run_018.py
.venv\Scripts\python scripts/generate_release_manifest.py
.venv\Scripts\python scripts/verify_release_integrity.py
.venv\Scripts\python scripts/show_project_status.py
```

The package-build audit creates an sdist and wheel, inspects their members, installs the wheel into a temporary environment, and runs a model-independent import/hash smoke test. It never publishes.

## Hashes and protected artifacts

Canonical JSON sorts mapping keys, rejects nonfinite/executable content where applicable, and excludes explicitly volatile environment fields from semantic identity. The release manifest hashes a deterministic, ordered artifact catalog. Runs 010–017 scientific/generated artifacts and current policy YAML files are protected byte-for-byte. Verification is read-only and fails on a missing or changed cataloged file.

Canonical outputs are accepted run reports, package objects, metadata, manifests, and protected trial/checkpoint artifacts. Disposable files live in temporary test directories or explicitly named quarantine/dry-run directories. `__pycache__`, `.pytest_cache`, editor files, `.git`, and temporary files are excluded.

## Warning policy

The sole accepted warning is `ComplexWarning` at `pylcp/rateeq.py:264`, audited by Run 011D. The discarded imaginary magnitude is exactly zero and classification is `WARNING_IS_NUMERICAL_ROUNDOFF`. It is not globally suppressed. A new warning type or source is not covered by this disposition.

## Documentation and integrity

`verify_release_integrity.py` validates release schemas, semantic hashes, protected/cataloged files, gates, authorization boundaries, documentation links, and the warning ledger. `audit_model_independent_boundaries.py` parses the Run 013–018 scripts’ Python syntax trees and rejects forbidden imports/calls without being confused by documentation prose.
