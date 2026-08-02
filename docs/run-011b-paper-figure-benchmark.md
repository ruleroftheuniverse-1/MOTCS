# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY

Run 011B is a read-only comparison between the accepted Track P force model and the rendered figures in K. J. Rodriguez *et al.*, “Simulations of a frequency-chirped magneto-optical trap of MgF,” *Physical Review A* **108**, 033105 (2023), DOI `10.1103/PhysRevA.108.033105`. It neither changes nor promotes the provisional model. Track E remains blocked.

The extraction configuration is [rodriguez_figure_digitization_run_011b.yaml](../configs/rodriguez_figure_digitization_run_011b.yaml). It records the local source hash, rendering resolution, panel crops, axes bounds, all pixel-to-data anchors, colorbar samples, trajectory extraction bounds, uncertainty perturbations, and protected-artifact set. [digitize_rodriguez_force_figures.py](../scripts/digitize_rodriguez_force_figures.py) renders pages 4–6 at 300 dpi and exports calibrated NPZ arrays, validity masks, palette residuals, panel images, and metadata. It does not copy or commit the source PDF.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY uncertainty model

The metadata keeps source half-pixel resolution, ±1 and ±2 pixel axis-anchor perturbations, one-pixel crop movement, ±1 and ±2 pixel colorbar-boundary perturbations, nearest-palette antialiasing residual, thick-trajectory line width, overlapping-curve limitations, and publication rasterization as separate contributions. Figure 3’s ±2 pixel calibration bounds are about 0.58 mm, 1.45 m/s, and 0.00057 in `hbar*k*Gamma`. Reported comparisons therefore do not imply precision below the source rendering.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY comparison method

[compare_accepted_force_to_rodriguez_figures.py](../scripts/compare_accepted_force_to_rodriguez_figures.py) reads the accepted Run 010 cache planes at exactly `-8`, `-6`, `-4`, and `-2 Gamma`; it does not rebuild them. Figure 2 is sampled from the already accepted backend solely for the normalized plane-wave diagnostic and remains separate from the Gaussian comparison. The script reads the saved Run 011 `7.5 Gamma/k` path and never reintegrates it.

For every Figure 3 negative-force region, widths are measured independently at half maximum, `1/e`, `1/e^2`, and supported fixed-force contours. Spatial slices pass through the actual extremum and through the paper-motivated `sqrt(2)|Delta|/k` velocity. Velocity slices are taken at `x=0` and through the actual extremum. The comparison also records zero crossings, support extents, extrema and displacement, signed area, normalized RMS difference, maximum difference, correlation, contour overlap, and force-sign agreement. Results are retained with no correction and after a diagnostic global force scale only. The scale and small-axis-offset diagnostics do not alter model data; waist, gradient, detuning, Hamiltonian quantities, and optical strengths are never fitted.

The earlier Run 011A `15–20 mm` value was a coarse cached-grid threshold estimate. The calibrated Figure 3 `1/e^2` spatial half-widths are about `24.5–29.5 mm`, while the accepted surfaces are about `18.4–21.2 mm`. These are different operational definitions, so the old number is revised rather than directly compared as the same measurement. The paper’s rough `sqrt(2) w_xy ≈ 25 mm` spatial statement is consistent with the digitized panels. Its rough `Gamma/k ≈ 7.5 m/s` velocity statement understates the digitized `1/e^2` slice widths, which are about `13.6–22.4 m/s`; the statement remains descriptive rather than exact ground truth.

Figure 2 already shows material plane-wave differences. In particular, the accepted `[3+1]` local spatial slope has the opposite sign from the digitized panel near the origin, and its surface correlation is lower than for `[3]`. White published trajectory overlays obscure some pixels, so covered plane-wave widths are not promoted as quantitative findings.

The thick Figure 4(a) curve was extracted as a black connected component with line-thickness uncertainty. Its raw starting ordinate differs from the saved Run 011 initial velocity. Metadata therefore reports both raw phase-space separation and a diagnostic comparison after removing only that initial ordinate offset. The latter is not a backend parameter fit. At the saved Run 011 sampling resolution, the first material path-shape separation coincides with Run 011A's first useful-force encounter, so the figure does not support a claim that divergence begins before that encounter. Thereafter the published curve bends more strongly and slows through a wider spatial region, whereas the saved path stays fast and later enters the positive-force region. Because the figure has no time coordinate, impulse and handoff timing are unmeasurable from it.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY gate

`PAPER_FORCE_SHAPE_DISCREPANCY_CONFIRMED`

Differences exceed the documented digitization bounds and occur at multiple locations: plane-wave Hamiltonian/transition force structure, force magnitude, Gaussian spatial width, and positive-force topology. They are sufficient to change the interpretation of the saved Run 011 trajectory. No corrective physics change is made.

`capture_authorized = false`; `capture_velocity_authorized = false`; `optimizer_authorized = false`; `exact_replication_valid = false`; Track E remains blocked.
