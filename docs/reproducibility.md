# Reproducibility

## Environment and installation

The project uses its existing `pyproject.toml`/pip workflow; Run 018 does not introduce another package manager.

Repository text bytes are canonical LF under the root `.gitattributes` policy. Numerical arrays, images, archives, wheels, compressed files, and PDFs are explicitly binary. Raw-byte SHA-256 remains the integrity rule; hashes do not normalize content during verification. CI runs `scripts/audit_canonical_line_endings.py` before dependency installation and the full suite.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test]"
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m compileall -q src scripts
```

The environment record under `outputs/provisional/release/run_018/` lists direct requirements and installed audit versions. It is an environment snapshot, not a universal lockfile.

The `test` extra explicitly declares `pytest>=8.0`, `Pillow>=10.0`,
`pdfplumber>=0.11.0`, and the Python-3.10-only `tomli>=2.0` compatibility
dependency. Pillow and pdfplumber are direct dependencies of the Run 011B
digitization module; clean CI environments must not rely on either being
installed transitively.

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

The Run 018 portability correction renormalized the Windows working tree to the same LF bytes stored by Git, recorded old/new working-tree hashes, proved parsed JSON/YAML and normalized text equivalence, and verified that every declared binary artifact remained byte-identical. The README code-fence repair is recorded separately as documentation-only.

Checkout-byte portability and provenance-path portability are distinct. The
former is enforced by `.gitattributes`; the latter requires repository-relative
POSIX strings inside semantic dependency provenance. The Run 010 cache mismatch
was caused by OS-dependent path serialization, not by CRLF-versus-LF dependency
hashes. See [provenance path portability](provenance-path-portability.md) for the
canonical rule, invalid-input behavior, identity-domain separation, and the
project-wide provenance-field audit.

Run 010 force-cache source identity remains strict raw-byte SHA-256. Source
paths are canonical repository-relative POSIX paths, independent of host path
separators, and the root `.gitattributes` policy makes the hashed checked-out
text bytes canonical LF. The one-time Run 018 migration changes only the two
cache metadata files. Their NPZ files and every contained array remain
byte-for-byte and value-for-value unchanged; no legacy cache-key fallback is
accepted afterward.

Historical Run 013-017 policy/full-package and runtime-checkpoint records retain
some checkout locators. Those records are explicitly platform-local audit
snapshots. Their documented portable policy/family identities exclude
provenance locators; molecular-model content hashes and release catalog paths
remain cross-platform. They are not silently treated as repository dependency
paths and were not rewritten by the focused Run 018 cache migration.

## Warning policy

The sole accepted warning is `ComplexWarning` at `pylcp/rateeq.py:264`, audited by Run 011D. The discarded imaginary magnitude is exactly zero and classification is `WARNING_IS_NUMERICAL_ROUNDOFF`. It is not globally suppressed. A new warning type or source is not covered by this disposition.

## Documentation and integrity

`verify_release_integrity.py` validates release schemas, semantic hashes, protected/cataloged files, gates, authorization boundaries, documentation links, and the warning ledger. `audit_model_independent_boundaries.py` parses the Run 013–018 scripts’ Python syntax trees and rejects forbidden imports/calls without being confused by documentation prose.
