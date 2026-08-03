# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_012_MOLECULAR_MODEL_INTERCHANGE_AND_AUTHOR_HANDOFF_ONLY

Run 012 provides a versioned molecular-model interchange and author handoff layer. It does not change accepted Track P physics or authorize imported models for production force calculations.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_012_MOLECULAR_MODEL_INTERCHANGE_AND_AUTHOR_HANDOFF_ONLY Reference export

Schema: `mgf-mot-molecular-model-v1`. Full package hash: `1b9394706613011ab54cbd3c143b60e655487fee38fe9207af11750ddd03ae8c`. Complex NPZ arrays, unit/axis metadata, and a canonical hash manifest are stored under `outputs/provisional/molecular_model_packages/run_012/`.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_012_MOLECULAR_MODEL_INTERCHANGE_AND_AUTHOR_HANDOFF_ONLY Round trip

Complex arrays preserved exactly: `True`. Matrix equivalence: `True`. Maximum force difference: `0.000e+00`; population difference: `0.000e+00`; pumping-total difference: `0.000e+00`.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_012_MOLECULAR_MODEL_INTERCHANGE_AND_AUTHOR_HANDOFF_ONLY Boundaries

The exported reference is provisional and explicitly records corrected ground magnetism, effective g'=0.001, the 0.5 MHz interval midpoint (not a measurement), and omission of the full independent Doppelbauer d operator. Imported models remain unauthorized until a later validation and force-benchmark decision. No cache was rebuilt and no trajectory was integrated.


## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_012_MOLECULAR_MODEL_INTERCHANGE_AND_AUTHOR_HANDOFF_ONLY Import validation and paper benchmark

The serialized package passes `IMPORT_VALID` and carries full hash `1b9394706613011ab54cbd3c143b60e655487fee38fe9207af11750ddd03ae8c` into the packaged backend. The compact sampled Figure 2 RMSE values are `{'mgf_3': 0.004717106085416586, 'mgf_3_plus_1': 0.009061953169852493}`. Reproduces the paper force structure: `False`. The accepted provisional reference is expected to remain discrepant; this establishes the baseline an author package must improve.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_012_MOLECULAR_MODEL_INTERCHANGE_AND_AUTHOR_HANDOFF_ONLY Author handoff

The low-burden request is documented in `docs/author-request-molecular-model-package.md`; a matrix-free synthetic schema template is under `examples/molecular_model_package_template/`. A construction script is acceptable in place of serialized matrices, and no trajectory code is requested.

`molecular_model_interchange_authorized=true`; `imported_model_force_authorized=false`; `cache_rebuild_authorized=false`; `trajectory_reintegration_authorized=false`; `capture_authorized=false`; `optimizer_authorized=false`; `exact_replication_valid=false`. Track E remains blocked pending the actual paper model.

MOLECULAR_MODEL_INTERCHANGE_READY
