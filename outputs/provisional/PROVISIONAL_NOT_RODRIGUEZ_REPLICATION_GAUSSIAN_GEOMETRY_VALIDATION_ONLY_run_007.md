# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY Run 007

The Gaussian geometry follows the paper's stated radii and beam axes.
The exact MgF Hamiltonian remains blocked.
Reported peak saturation vectors are used directly.
The reported total laser power is retained as metadata rather than converted through an assumed allocation.
No capture velocity or threshold search was performed.
No physical conclusions should be drawn from provisional force differences.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY Geometry

- `wxy = 17.5 mm`
- `wz = 10 mm`
- radius convention: `1/e^2_intensity_radius`
- longitudinal model: `none`
- total power metadata: `1 W`
- power allocation status: `unresolved_no_conversion`
- operative peak saturation vector: `(1.45, 1.45, 2.17, 0.72)`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY Analytic checks

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY Beam +x_prime

- center envelope: `1.0`
- one `wxy` radius: `0.1353352832366128`
- one `wz` radius: `0.1353352832366127`
- longitudinal displacement: `1.0`
- right-handed frame: `True`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY Beam -x_prime

- center envelope: `1.0`
- one `wxy` radius: `0.1353352832366128`
- one `wz` radius: `0.1353352832366127`
- longitudinal displacement: `1.0`
- right-handed frame: `True`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY Beam +y_prime

- center envelope: `1.0`
- one `wxy` radius: `0.1353352832366128`
- one `wz` radius: `0.1353352832366127`
- longitudinal displacement: `1.0`
- right-handed frame: `True`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY Beam -y_prime

- center envelope: `1.0`
- one `wxy` radius: `0.1353352832366128`
- one `wz` radius: `0.1353352832366127`
- longitudinal displacement: `1.0`
- right-handed frame: `True`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY Beam +z

- center envelope: `1.0`
- one `wxy` radius: `0.1353352832366127`
- one `wz` radius: `0.1353352832366127`
- longitudinal displacement: `1.0`
- right-handed frame: `True`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY Beam -z

- center envelope: `1.0`
- one `wxy` radius: `0.1353352832366127`
- one `wz` radius: `0.1353352832366127`
- longitudinal displacement: `1.0`
- right-handed frame: `True`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY Lab x-axis projection

| point | +x' | -x' | +y' | -y' | +z | -z |
|---|---:|---:|---:|---:|---:|---:|
| origin | 1 | 1 | 1 | 1 | 1 | 1 |
| x_minus_50_mm | 0.000284930489 | 0.000284930489 | 0.000284930489 | 0.000284930489 | 8.11853835e-08 | 8.11853835e-08 |
| x_minus_25_mm | 0.129922608 | 0.129922608 | 0.129922608 | 0.129922608 | 0.0168798841 | 0.0168798841 |
| x_plus_25_mm | 0.129922608 | 0.129922608 | 0.129922608 | 0.129922608 | 0.0168798841 | 0.0168798841 |
| x_plus_50_mm | 0.000284930489 | 0.000284930489 | 0.000284930489 | 0.000284930489 | 8.11853835e-08 | 8.11853835e-08 |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY Static force plumbing

The same frozen static `[3+1]` policy state and grid were used for both modes.

- plane-wave force values: `[0.28950000000000004, 0.14475000000000002, -0.0, -0.14475000000000002, -0.28950000000000004]`
- elliptical-Gaussian force values: `[5.499941874268481e-05, 0.013351986111617361, -0.0, -0.013351986111617361, -5.499941874268481e-05]`
- arrays: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY_run_007_arrays.npz`
- metadata: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY_run_007_metadata.json`
- plot: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_GAUSSIAN_GEOMETRY_VALIDATION_ONLY_run_007_force_comparison.png`