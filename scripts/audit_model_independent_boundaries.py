"""AST-based forbidden execution/import audit for Runs 013-018 scripts."""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/"src"
if str(SRC) not in sys.path:sys.path.insert(0,str(SRC))
from mgf_mot.release_manifest import audit_forbidden_boundaries  # noqa:E402
NAMES=("validate_control_policy_abi_v2.py","compile_control_policies_run_014.py","validate_open_loop_policy_families_run_015.py","validate_feedback_policy_interface_run_016.py","validate_experiment_search_protocol_run_017.py","generate_release_manifest.py","verify_release_integrity.py","show_project_status.py","intake_molecular_model_package.py","validate_release_run_018.py","verify_package_build_run_018.py","audit_canonical_line_endings.py","audit_line_ending_renormalization.py","normalize_tracked_line_endings.py","write_ci_portability_report.py","migrate_run_010_cache_provenance_to_canonical_lf.py","audit_provenance_path_portability.py")
def run():
    result=audit_forbidden_boundaries(ROOT,tuple(ROOT/"scripts"/name for name in NAMES));print(json.dumps(result,indent=2,sort_keys=True));return result
if __name__=="__main__":raise SystemExit(0 if run()["passed"] else 1)
