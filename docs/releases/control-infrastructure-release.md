# Control infrastructure release

This is a **reproducible provisional molecular-model interchange and model-independent control infrastructure release**. It is not an exact-replication release.

Runs 012–017 provide the molecular-model interchange, control-policy ABI, apparatus schedule compiler, deterministic open-loop families, observation/feedback/replay layer, and experiment/trial/checkpoint/replay protocol. Run 018 freezes their hashes into a versioned release manifest, authorization ledger, artifact catalog, environment record, package-build audit, CI workflow, and safe author-model intake path.

Semantic identities are deterministic; volatile environment metadata is separate. Trial and release artifacts are content-hashed and conflict-detecting. Physical metrics stay locked, synthetic objectives remain visibly synthetic, and no optimizer has been implemented or run.

The Run 018 CI portability correction adds a repository-wide LF checkout policy and explicit binary declarations. It retains raw-byte hashing while making checked-out canonical text bytes identical on Windows and Linux. The correction changes no scientific value, conclusion, gate, or authorization.

The focused Run 018 cache-provenance and CI dependency addendum declares the
Run 011B Pillow and pdfplumber dependencies explicitly and migrates the two
Run 010 cache metadata records to canonical repository-relative POSIX source
paths. The audit found that their recorded dependency hashes already matched
canonical-LF bytes; host-specific path serialization caused the remaining CI
mismatch. The Run 010 NPZ files were not rewritten, no force field was rebuilt,
and the accepted loader continues to reject every noncanonical or genuinely
changed provenance key.

The final provenance certification keeps checkout-byte and provenance-path
portability separate. `.gitattributes` controls canonical LF artifact bytes;
repository dependency identities use root-relative POSIX paths. It also audits
molecular-model, policy, apparatus, feedback, experiment, intake, release, and
catalog path fields. Older policy full-package and experiment checkpoint hashes
that include audit locators are explicitly platform-local; their portable
content identities are separately named and no protected Runs 013-017 schema
was rewritten. See [provenance path portability](../provenance-path-portability.md).

Scientifically, the numerical and rate-equation machinery has been reproduced, but the Rodriguez force structure has not. The discrepancy is localized to molecular-model objects. Track E awaits the original arrays or construction code. When they arrive, preserve and quarantine them, validate/compare them through Run 012, and seek a separate benchmark gate before any promotion, cache rebuild, trajectory, or capture work.
