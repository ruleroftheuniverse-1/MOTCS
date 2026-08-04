# MODEL_INDEPENDENT NOT_RODRIGUEZ_REPLICATION RUN_018 CROSS_PLATFORM_PROVENANCE_CERTIFICATION_ONLY

This is a provenance-portability certification for model-independent infrastructure. It is not a Rodriguez replication result and contains no new physical calculation.

## Corrected diagnosis

The original assumption was that CRLF-versus-LF source hashes caused the Run 010 cache provenance mismatch. The recorded evidence disproved that assumption: dependency hashes already matched canonical LF source/configuration bytes. Windows and POSIX checkouts instead serialized the same repository-relative dependency paths with different separators, changing canonical provenance JSON and its cache key.

Checkout-byte portability remains a separate, valid requirement. `.gitattributes` establishes canonical LF text bytes for raw release-artifact SHA-256. That prior normalization was necessary for artifact byte integrity, but it did not cause the Run 010 cache mismatch.

The historical `RUN_018_CI_CACHE_PROVENANCE_REFINEMENT_REQUIRED` gate was therefore honest: its requested line-ending-only condition was unsupported. It records a corrected diagnosis, not an implementation failure.

## Canonical rule and project audit

Repository dependencies are identified by root-relative POSIX strings: `/` separators, no drive or leading slash, no `.` or `..`, no checkout prefix, no symlink realpath expansion, preserved case, and the existing JSON Unicode rules. Absolute Windows or POSIX inputs are accepted only with an explicit matching repository root and are never emitted. The representative Windows-backslash, Windows-forward-slash, POSIX-runner, and relative forms all canonicalize to `src/mgf_mot/example.py`; outside, UNC, empty, drive-relative, and ambiguous paths fail closed.

The machine audit classifies 12 provenance-bearing uses across Run 010, molecular-model packages, policy provenance, apparatus profiles, feedback specs, experiment checkpoints, model intake, release manifests, and artifact catalogs. All classifications are complete, all 22 current Run 010 dependency paths are canonical, and no new migration is required. Historical policy full-package and experiment checkpoint locators are explicitly platform-local audit snapshots; separately named policy/family content identities remain the portable comparison domain.

Identity domains remain distinct:

- artifact integrity: raw SHA-256 bytes;
- structured semantics: canonical JSON;
- repository dependencies: repository-relative POSIX strings inside provenance;
- external references: opaque citations, identifiers, or URIs.

## Run 010 invariants and strictness

For both accepted caches, old metadata is recognized exactly, new metadata uses canonical repository paths, non-source provenance fields are unchanged, and all dependency content hashes are unchanged except the separately audited one-line `accepted_backend.py` path-serialization implementation change. Old and new cache keys differ. The NPZ hashes are identical before and after migration, and every contained array is exactly equal. A second migration run performs no metadata write.

The migrated caches load through the accepted trajectory adapter. Legacy keys, modified source files, modified configuration files, unrecognized dependencies, and unexplained hashes remain rejected. There is no indefinite legacy-key fallback and no weakened provenance check.

## Validation

| Environment | Result |
|---|---|
| Windows Python 3.12 | `326 passed`, one narrowly audited pylcp `ComplexWarning` |
| Clean canonical-LF Python 3.10 | `326 passed`, one narrowly audited pylcp `ComplexWarning` |
| Clean canonical-LF Python 3.12 | `326 passed`, one narrowly audited pylcp `ComplexWarning` |

Additional gates: `CANONICAL_LF_OK`, `PROVENANCE_PATH_AUDIT_OK`, `RELEASE_INTEGRITY_OK`, `PACKAGE_BUILD_OK`, documentation links valid, and the forbidden-boundary audit passed.

Final semantic release hash: `7bd2e4d24ecf041ca121405ec7449e4aa5365c0697beadbd0876d461af9e951d`.

Execution counters: zero force evaluations, zero force-cache rebuilds, zero equilibrium solves, zero trajectory integrations, zero capture calculations, zero optimizer runs, zero controller training runs, and zero hardware validations.

RUN_018_CROSS_PLATFORM_PROVENANCE_GO
