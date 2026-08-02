# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY

This is a read-only paper-figure benchmark. It is provisional, is not a Rodriguez replication, and does not authorize capture calculations.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY Source and reproducibility

Source: *Simulations of a frequency-chirped magneto-optical trap of MgF*, Physical Review A 108, 033105 (2023), DOI `10.1103/PhysRevA.108.033105`. Local source SHA-256: `994e2e8c269aa280ebc6234f99ed20854bc0db2efb372665977ba86f1b31d4a7`. Pages 4-6 were rendered at `300` dpi with `pdfplumber 0.11.10; Pillow 12.2.0`. Every crop, axis anchor, colorbar anchor, and extraction bound is in `configs/rodriguez_figure_digitization_run_011b.yaml`.

Protected Run 010/011/011A and configuration artifacts unchanged: `True` (31 files). No accepted cache was rebuilt and no trajectory was reintegrated.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY Digitization uncertainty

Separate contributions are recorded for half-pixel source resolution, +/-1 and +/-2 pixel anchor placement, one-pixel crop boundaries, +/-1 and +/-2 pixel colorbar boundaries, antialiasing palette residuals, thick-line width, overlapping curves, and publication rasterization. Figure 3 one-pixel scales are approximately 0.289 mm, 0.718 m/s, and 0.000287 hbar*k*Gamma; the +/-2-pixel bounds are approximately 0.58 mm, 1.45 m/s, and 0.00057 hbar*k*Gamma.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY Figure 3 Gaussian force surfaces

| detuning | paper Fmin | model Fmin | paper Fmax | model Fmax | paper 1/e2 x half-width mm | model 1/e2 x half-width mm | paper 1/e2 v half-width m/s | model 1/e2 v half-width m/s | NRMS | corr | scale |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| -8 | -0.0477 | -0.0697 | 0.0459 | 0.0697 | 24.49 | 18.77 | 22.40 | 17.97 | 0.028 | 0.956 | 0.874 |
| -6 | -0.0482 | -0.0612 | 0.0465 | 0.0612 | 26.25 | 18.40 | 18.69 | 22.18 | 0.025 | 0.956 | 0.948 |
| -4 | -0.0477 | -0.0721 | 0.0459 | 0.0721 | 28.82 | 20.78 | 16.16 | 15.43 | 0.026 | 0.957 | 0.912 |
| -2 | -0.0477 | -0.0648 | 0.0462 | 0.0648 | 29.47 | 21.18 | 13.60 | 13.57 | 0.028 | 0.945 | 0.913 |

Widths are reported under four explicit constructions in metadata: spatial through the actual extremum, spatial at the paper-motivated sqrt(2)|Delta|/k slice, velocity at x=0, and velocity through the actual extremum. Each has half-maximum, 1/e, 1/e^2, and supported fixed-force contours. The earlier Run 011A 15-20 mm estimate used a coarse cached-grid threshold; the digitized paper and interpolated model comparison uses calibrated high-resolution slices, so the two estimates were not operationally identical.

Every surface metric is retained both with no fitted correction and after a diagnostic global force-scale factor only. Small axis offsets are reported independently and are not applied to the accepted model. Signed-area, contour-overlap, extremum-displacement, force-support, suppressed-force, and zero-crossing diagnostics are recorded in the JSON metadata.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY Figure 2 plane-wave surfaces

| configuration | paper dF/dx | model dF/dx | paper dF/dv | model dF/dv | paper Fmin | model Fmin | paper Fmax | model Fmax | NRMS | corr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mgf_3 | -0.001226 | -0.001102 | -0.03514 | -0.05193 | -0.0509 | -0.0653 | 0.0495 | 0.0653 | 0.066 | 0.695 |
| mgf_3_plus_1 | 0.003002 | -0.003794 | -0.0278 | -0.04514 | -0.0413 | -0.0561 | 0.0408 | 0.0561 | 0.088 | 0.487 |

Plane-wave and Gaussian comparisons remain separate. Component (4)'s published effect is compared through the independent [3] and [3+1] panels; no Gaussian waist, gradient, detuning, Hamiltonian term, or optical strength was fitted. White trajectory overlays obscure some Figure 2 pixels, so width-like measurements in those covered regions are not promoted as quantitative findings; calibrated support, zero-contour, slope, extrema, and surface metrics remain in metadata.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY Figure 4(a) trajectory

The digitized thick curve starts near x=-49.52 mm with a rendered plateau near 59.04 m/s, and reaches v=0.26 m/s near the origin. The saved Run 011 path remains much faster and enters the positive-force region. The first raw material separation under the documented normalized distance rule is `{'run011_sample_index': 1, 'x_mm': -44.35255127025764, 'velocity_m_s': 56.473510861648, 'normalized_phase_space_distance': 0.2810447431029891}`. After removing only the initial rendered velocity offset, the first path-shape separation is `{'run011_sample_index': 5, 'x_mm': -21.855088265824907, 'raw_velocity_m_s': 55.269504556628455, 'offset_normalized_velocity_m_s': 57.83296609508997, 'normalized_phase_space_distance': 0.16056164115840896, 'nearest_paper_x_mm': -24.917324931718014, 'nearest_paper_velocity_m_s': 57.05128205128203}`; this diagnostic offset is not a backend fit. Relative to Run 011A's first useful-force event, that separation is `COINCIDENT_AT_SAVED_SAMPLE_RESOLUTION`—the saved sampling does not support a claim that shape divergence begins earlier. The paper curve then bends more strongly and samples a wider slowing region, but Figure 4(a) has no time coordinate, so negative impulse or handoff timing cannot be numerically recovered from the figure; only the phase-space path can be compared.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY Paper-text consistency

Spatial text estimate: `CONSISTENT_WITH_DIGITIZED_FIGURE`. Velocity text estimate: `ROUGH_UNDERSTATEMENT`. The paper's values are treated as rough descriptions, not exact ground truth.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY Difference localization

Confirmed discrepancies:

- `PLANE_WAVE_HAMILTONIAN_SHAPE_DISCREPANCY`
- `FORCE_MAGNITUDE_DISCREPANCY`
- `SPATIAL_WIDTH_DISCREPANCY`
- `POSITIVE_FORCE_REGION_DISCREPANCY`
- `MULTIPLE_DIFFERENCES`

Likely discrepancies:

- `VELOCITY_WIDTH_DISCREPANCY`

Within uncertainty:

- `small axis offsets of at most two rendered pixels`

Unmeasurable:

- `trajectory time and impulse from Figure 4(a)`
- `force values hidden by white Figure 2 trajectory overlays`
- `sub-colorbar-step force detail in saturated Figure 3 extrema`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY Final gate: PAPER_FORCE_SHAPE_DISCREPANCY_CONFIRMED

**PAPER_FORCE_SHAPE_DISCREPANCY_CONFIRMED**

The mismatch is localized to multiple locations: plane-wave Hamiltonian/transition topology already differs in visible force structure and magnitude, and the Gaussian surfaces retain material force-width and positive/negative-topology differences beyond digitization uncertainty. These differences are sufficient to alter the Run 011 trajectory interpretation. The diagnostic force-scale fit is reported but was not applied to the accepted backend.

`capture_authorized = false`; `capture_velocity_authorized = false`; `optimizer_authorized = false`; `exact_replication_valid = false`; Track E remains blocked.

# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY FINAL_PAPER_FORCE_SHAPE_DISCREPANCY_CONFIRMED
