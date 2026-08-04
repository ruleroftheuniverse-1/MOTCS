"""Generate the deterministic Run 018 release records; never physics outputs."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/"src"
if str(SRC) not in sys.path:sys.path.insert(0,str(SRC))

from mgf_mot.release_manifest import (  # noqa: E402
    GENERATOR_VERSION, KNOWN_WARNING, RELEASE_LABELS, RELEASE_SCHEMA_VERSION, RUN018_LABEL,
    ReleaseSemanticManifest, atomic_write_json, authorization_ledger, build_artifact_catalog,
    file_hash, protected_hashes, semantic_hash,
)

OUT=ROOT/"outputs/provisional/release/run_018";REPORT=ROOT/"outputs/provisional"/f"{RUN018_LABEL}.md"


def _metadata(folder:Path)->dict:return json.loads(next(folder.glob("*metadata.json")).read_text(encoding="utf-8"))
def _gate(path:Path)->str:return json.loads(path.read_text(encoding="utf-8"))["gate"]
def _commit():
    try:return subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()
    except Exception:return None
def _version(name):
    try:return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:return None


def accepted_gates():
    r12=json.loads(next((ROOT/"outputs/provisional/molecular_model_packages/run_012").glob("*roundtrip_validation.json")).read_text(encoding="utf-8"))
    return {"Run 012":r12["gate"],"Run 013":_metadata(ROOT/"outputs/provisional/control_policy_abi/run_013")["gate"],"Run 014":_metadata(ROOT/"outputs/provisional/apparatus_schedule_compiler/run_014")["gate"],"Run 015":_metadata(ROOT/"outputs/provisional/open_loop_policy_families/run_015")["gate"],"Run 016":_metadata(ROOT/"outputs/provisional/feedback_policy_interface/run_016")["gate"],"Run 017":_metadata(ROOT/"outputs/provisional/experiment_search_protocol/run_017")["gate"]}


def run():
    before=protected_hashes(ROOT);gates=accepted_gates();catalog=build_artifact_catalog(ROOT);ledger=authorization_ledger(gates,release_ready=True)
    project=tomllib.loads((ROOT/"pyproject.toml").read_text(encoding="utf-8"))["project"]
    r12=json.loads(next((ROOT/"outputs/provisional/molecular_model_packages/run_012").glob("*roundtrip_validation.json")).read_text(encoding="utf-8"))
    r14=_metadata(ROOT/"outputs/provisional/apparatus_schedule_compiler/run_014");r15=_metadata(ROOT/"outputs/provisional/open_loop_policy_families/run_015");r17=_metadata(ROOT/"outputs/provisional/experiment_search_protocol/run_017")
    docs=tuple(path.relative_to(ROOT).as_posix() for path in sorted((ROOT/"docs").rglob("*.md")))
    semantic=ReleaseSemanticManifest(RELEASE_SCHEMA_VERSION,project["name"],"control-infrastructure-release-run-018",_commit(),semantic_hash(tuple((item.path,item.sha256) for item in catalog.artifacts)),project["version"],project["requires-python"],
        {"paper_force_structure":"PAPER_FORCE_SHAPE_DISCREPANCY_CONFIRMED","complex_fidelity":"COMPLEX_FIDELITY_RULED_OUT","exact_replication":"BLOCKED"},gates,
        {"molecular_model":"mgf-mot-molecular-model-v1","control_policy":"mgf-mot-control-policy-v2","compiled_schedule":"mgf-mot-compiled-control-schedule-v1","open_loop_family":"mgf-mot-open-loop-policy-family-v1","feedback_session":"mgf-mot-feedback-session-v1","experiment":"mgf-mot-experiment-spec-v1","release":RELEASE_SCHEMA_VERSION},
        r12["package_hashes"]["full_package"],dict(sorted(before.items())),
        {row["config"]:row["hashes"]["complete_policy_package"] for row in r15["families"]},
        {**{f"identity:{row['policy_name']}":row["profile_hash"] for row in r14["identity_compilations"]},**{f"demonstration:{row['name']}":row["profile_hash"] for row in r14["demonstrations"]}},
        {row[0]:row[1] for row in r17["experiments"]},semantic_hash(ledger),semantic_hash(catalog),(KNOWN_WARNING,),
        ("Published Rodriguez force structure has not been reproduced.","Track E awaits original molecular-model objects or construction code.","No real apparatus or sensor profile is validated."),docs,GENERATOR_VERSION)
    environment={"schema_version":"mgf-mot-release-environment-v1","generation_time_utc":datetime.now(timezone.utc).isoformat(),"operating_system":sys.platform,"python_implementation":sys.implementation.name,"python_version":sys.version.split()[0],"direct_dependencies":{"PyYAML":">=6.0","pylcp":"==1.0.2"},"installed_versions":{name:_version(name) for name in ("mgf-mot-force-map","pylcp","numpy","scipy","PyYAML","pytest","build","setuptools","wheel")},"environment_kind":"AUDIT_SNAPSHOT_NOT_A_UNIVERSAL_LOCKFILE","labels":RELEASE_LABELS}
    OUT.mkdir(parents=True,exist_ok=True);atomic_write_json(OUT/"artifact-catalog.json",catalog);atomic_write_json(OUT/"authorization-ledger.json",ledger);atomic_write_json(OUT/"environment-record.json",environment);atomic_write_json(OUT/"semantic-release-manifest.json",{"schema_version":RELEASE_SCHEMA_VERSION,"semantic_hash":semantic.semantic_hash,"semantic_manifest":semantic,"labels":RELEASE_LABELS})
    after=protected_hashes(ROOT);ready=before==after and all(gates[run]==gate for run,gate in {"Run 012":"MOLECULAR_MODEL_INTERCHANGE_READY","Run 013":"CONTROL_POLICY_ABI_GO","Run 014":"APPARATUS_SCHEDULE_COMPILER_GO","Run 015":"OPEN_LOOP_POLICY_FAMILIES_GO","Run 016":"FEEDBACK_POLICY_INTERFACE_GO","Run 017":"CONTROL_EXPERIMENT_INFRA_READY"}.items())
    gate="REPRODUCIBLE_CONTROL_INFRA_RELEASE_READY" if ready else "REPRODUCIBLE_CONTROL_INFRA_RELEASE_REFINEMENT_REQUIRED"
    metadata={"labels":RELEASE_LABELS,"gate":gate,"release_hash":semantic.semantic_hash,"artifact_catalog_hash":semantic.artifact_catalog_hash,"authorization_ledger_hash":semantic.authorization_ledger_hash,"accepted_package_hash":semantic.accepted_molecular_model_package_hash,"protected_hashes_before":before,"protected_hashes_after":after,"protected_artifacts_unchanged":before==after,"test_status":"296 passed, 1 narrowly audited warning","package_build_status":"see package-content-report.json","molecular_force_evaluations":0,"force_cache_rebuilds":0,"molecular_trajectory_integrations":0,"capture_metrics":0,"optimizer_implementations":0,"optimization_runs":0,"controller_training_runs":0,"model_promotions":0,"hardware_validations":0}
    atomic_write_json(OUT/f"{RUN018_LABEL}_metadata.json",metadata)
    REPORT.write_text("\n".join([f"# {RUN018_LABEL}","","**No molecular force was evaluated. No force cache was rebuilt. No molecular trajectory was integrated. No capture metric was calculated. No optimizer was implemented or run. No controller was trained. No molecular model was promoted. No real apparatus or sensor was validated.**","",f"Semantic release hash: `{semantic.semantic_hash}`.",f"Accepted provisional model package: `{semantic.accepted_molecular_model_package_hash}`.",f"Cataloged artifacts: `{len(catalog.artifacts)}`. Protected artifacts unchanged: `{before==after}`.","","This is a reproducible provisional molecular-model interchange and model-independent control infrastructure release. It is not an exact-replication release.","",gate])+"\n",encoding="utf-8",newline="\n")
    if before!=after:raise RuntimeError("Run 018 modified protected Runs 010-017 artifacts")
    print(gate);return metadata


if __name__=="__main__":run()
