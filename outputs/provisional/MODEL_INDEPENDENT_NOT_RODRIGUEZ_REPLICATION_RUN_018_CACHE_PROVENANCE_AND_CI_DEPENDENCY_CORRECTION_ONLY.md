# MODEL_INDEPENDENT NOT_RODRIGUEZ_REPLICATION RUN_018 CACHE_PROVENANCE_AND_CI_DEPENDENCY_CORRECTION_ONLY

This is a focused CI/provenance portability correction. It does not rerun Run 010 and changes no force value or physics.

`RUN_010_NUMERICAL_CACHE_UNCHANGED`: both NPZ files are byte-identical and every contained array is exactly equal.

`RUN_018_PROVENANCE_METADATA_MIGRATED`: metadata now uses canonical repository-relative POSIX paths and current canonical-LF raw-byte source hashes.

The audit found that recorded dependency hashes already matched LF bytes; Windows-versus-POSIX path serialization, not numerical or textual physics content, caused the CI cache-key mismatch. The one-line `as_posix()` plumbing correction is explicitly recorded.

Checkout-byte portability is separate: `.gitattributes` establishes canonical LF text bytes for release-artifact byte hashes. That normalization was necessary, but it did not cause the Run 010 cache-key mismatch.

The prior `RUN_018_CI_CACHE_PROVENANCE_REFINEMENT_REQUIRED` gate was honest because its requested line-ending-only condition was contradicted by the recorded hashes; it was not an implementation-failure verdict.

Pillow and pdfplumber are explicit `.[test]` digitization dependencies. Cache loading remains fail-closed for any genuine source or configuration change; no legacy-key fallback exists.

Validation: `326 passed with 1 narrowly audited pylcp ComplexWarning: Windows Python 3.12, clean canonical-LF Python 3.10, and clean canonical-LF Python 3.12`.

Migration counters: zero force evaluations, zero cache rebuilds, zero equilibrium solves, and zero trajectory integrations.

RUN_018_CI_CACHE_PROVENANCE_REFINEMENT_REQUIRED
