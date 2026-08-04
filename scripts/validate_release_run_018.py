"""End-to-end Run 018 release, package, integrity, and intake audit."""
from __future__ import annotations
import json
from pathlib import Path
import shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/"src"
if str(SRC) not in sys.path:sys.path.insert(0,str(SRC))
from mgf_mot.model_intake import intake_molecular_model  # noqa:E402
from mgf_mot.molecular_model_package import RUN012_LABEL  # noqa:E402
from mgf_mot.release_manifest import RELEASE_LABELS,RUN018_LABEL,atomic_write_json,audit_forbidden_boundaries,load_release_bundle,protected_hashes,verify_bundle  # noqa:E402
OUT=ROOT/"outputs/provisional/release/run_018";REPORT=ROOT/"outputs/provisional"/f"{RUN018_LABEL}.md";ACCEPTED=ROOT/"outputs/provisional/molecular_model_packages/run_012"/f"{RUN012_LABEL}_ACCEPTED_PROVISIONAL_REFERENCE_PACKAGE"
AUDITED=("validate_control_policy_abi_v2.py","compile_control_policies_run_014.py","validate_open_loop_policy_families_run_015.py","validate_feedback_policy_interface_run_016.py","validate_experiment_search_protocol_run_017.py","generate_release_manifest.py","verify_release_integrity.py","show_project_status.py","intake_molecular_model_package.py","validate_release_run_018.py")
def run():
    before=protected_hashes(ROOT)
    subprocess.run([sys.executable,str(ROOT/"scripts/verify_package_build_run_018.py")],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(ROOT/"scripts/generate_release_manifest.py")],cwd=ROOT,check=True)
    quarantine=OUT/"author_model_intake_quarantine";intake=intake_molecular_model(ACCEPTED,quarantine,"Run 018 accepted-package equivalent dry-run fixture",accepted_base=ACCEPTED)
    with tempfile.TemporaryDirectory(prefix="mgf_run018_bad_") as name:
        base=Path(name)/"malformed"
        for suffix in (".npz",".metadata.json",".manifest.json"):shutil.copyfile(Path(f"{ACCEPTED}{suffix}"),Path(f"{base}{suffix}"))
        metadata=Path(f"{base}.metadata.json");data=json.loads(metadata.read_text(encoding="utf-8"));data.pop("basis",None);metadata.write_text(json.dumps(data,sort_keys=True)+"\n",encoding="utf-8")
        malformed=intake_molecular_model(base,Path(name)/"quarantine","Run 018 deliberately malformed disposable fixture",accepted_base=ACCEPTED,validation_only=True)
    forbidden=audit_forbidden_boundaries(ROOT,tuple(ROOT/"scripts"/name for name in AUDITED))
    integrity=verify_bundle(ROOT,load_release_bundle(OUT));package=json.loads((OUT/"package-content-report.json").read_text(encoding="utf-8"));after=protected_hashes(ROOT)
    intake_audit={"labels":RELEASE_LABELS,"unchanged_package_validation":intake.validation_gate,"equivalent_package_recognized":intake.equivalent_to_accepted,"source_hashes_preserved":intake.source_file_hashes==intake.preserved_file_hashes,"malformed_package_rejected":bool(malformed.validation_errors),"accepted_model_replaced":False,"automatic_promotion_authorized":False,"force_cache_rebuilds":0,"trajectory_integrations":0,"capture_calculations":0,"intake":intake,"malformed_errors":malformed.validation_errors}
    atomic_write_json(OUT/"author-intake-dry-run-report.json",intake_audit);atomic_write_json(OUT/"integrity-report.json",integrity);atomic_write_json(OUT/"forbidden-boundary-audit.json",forbidden)
    ready=(integrity.valid and package["build_status"]=="PACKAGE_BUILD_OK" and not package["forbidden_members"] and forbidden["passed"] and intake.validation_gate in {"IMPORT_VALID","IMPORT_VALID_WITH_WARNINGS"} and intake.equivalent_to_accepted and intake.source_file_hashes==intake.preserved_file_hashes and bool(malformed.validation_errors) and before==after)
    gate="REPRODUCIBLE_CONTROL_INFRA_RELEASE_READY" if ready else "REPRODUCIBLE_CONTROL_INFRA_RELEASE_REFINEMENT_REQUIRED"
    audit={"labels":RELEASE_LABELS,"gate":gate,"release_integrity":integrity.status,"package_build":package["build_status"],"forbidden_boundary_passed":forbidden["passed"],"intake_dry_run":intake_audit,"protected_hashes_before":before,"protected_hashes_after":after,"protected_artifacts_unchanged":before==after,"molecular_force_evaluations":0,"force_cache_rebuilds":0,"molecular_trajectory_integrations":0,"capture_metrics":0,"optimizer_implementations":0,"optimization_runs":0,"controller_training_runs":0,"model_promotions":0,"hardware_validations":0}
    atomic_write_json(OUT/"run-018-audit.json",audit)
    REPORT.write_text("\n".join([f"# {RUN018_LABEL}","","**No molecular force was evaluated. No force cache was rebuilt. No molecular trajectory was integrated. No capture metric was calculated. No optimizer was implemented or run. No controller was trained. No molecular model was promoted. No real apparatus or sensor was validated.**","",f"Release integrity: `{integrity.status}`. Package build: `{package['build_status']}`. Protected artifacts unchanged: `{before==after}`.",f"Author intake: `{intake.validation_gate}`; representation-equivalent to accepted fixture: `{intake.equivalent_to_accepted}`; source bytes preserved: `{intake.source_file_hashes==intake.preserved_file_hashes}`; malformed fixture rejected: `{bool(malformed.validation_errors)}`.","","Automatic promotion remains unauthorized. Physical evaluation, capture, optimization, training, reinforcement learning, and hardware execution remain locked.","",gate])+"\n",encoding="utf-8")
    print(gate);return audit
if __name__=="__main__":run()
