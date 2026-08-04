# MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_013_CONTROL_POLICY_ABI_ONLY

**MODEL-INDEPENDENT CONTROL ABI AUDIT ONLY. No molecular force, force-field, trajectory, capture, feedback, or optimization calculation was performed.**

## MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_013_CONTROL_POLICY_ABI_ONLY Result

All four legacy configurations converted to `mgf-mot-control-policy-v2`, validated, serialized, deserialized, and instantiated. Compatibility result: `LEGACY_BEHAVIOR_EXACT`. Canonical parameter, channel, policy, and full-package hashes remained exact across round trip.

## MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_013_CONTROL_POLICY_ABI_ONLY Explicit contracts

Every state contains ordered components `(1,2,3,4)` with separate detuning and saturation channel IDs. The common chirp of components `(1,2,3)` is one SHARED channel; parked component `(4)` remains at `+2 Gamma` with zero optical power. Static values are FIXED channels. AFFINE_DERIVED is declarative, acyclic, and limited to scale/offset; executable expressions fail closed.

Negative-time behavior is explicit HOLD_INITIAL. Linear chirp evaluation includes the exact endpoint and final hold. The handoff event preserves `t<tau` pre-handoff and `t>=tau` post-handoff. The static-[3] legacy null off-reason is represented internally by an explicit provenance sentinel and projected back to null only in the v1 compatibility view, preserving legacy samples exactly without rewriting YAML.

## MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_013_CONTROL_POLICY_ABI_ONLY Boundaries

Accepted Track P physics and historical artifacts remain byte-identical. The ABI gate authorizes subsequent apparatus schedule-compiler work and later policy families against v2, but does not authorize apparatus claims, new simulation, feedback, optimization, or capture calculations.

`apparatus_schedule_compiler_authorized=false`; `open_loop_policy_families_authorized=false`; `feedback_policy_authorized=false`; `optimizer_interface_authorized=false`; `optimization_run_authorized=false`; `capture_authorized=false`; `exact_replication_valid=false`.

CONTROL_POLICY_ABI_GO
