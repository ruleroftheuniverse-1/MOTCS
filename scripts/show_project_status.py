"""Print current status solely from the Run 018 release records."""
from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/"src"
if str(SRC) not in sys.path:sys.path.insert(0,str(SRC))
from mgf_mot.release_manifest import load_release_bundle  # noqa:E402
def run(directory=ROOT/"outputs/provisional/release/run_018"):
    b=load_release_bundle(Path(directory));a={x.name:x for x in b.authorization_ledger.entries};s=b.semantic_manifest
    lines=["Scientific status: rate-equation machinery reproduced; published force structure not reproduced.","Current blocker: original Rodriguez molecular-model objects or construction code.",f"Accepted package hash: {s.accepted_molecular_model_package_hash}","Latest gates:",*[f"  {k}: {v}" for k,v in sorted(s.infrastructure_gates.items())],"Locked: physical evaluation, capture, optimization, hardware execution.","Author-model next step: quarantine, preserve, validate, compare, then separately benchmark; never auto-promote.","Docs: docs/current-project-status.md; docs/author-model-arrival-runbook.md; docs/reproducibility.md",f"Track E blocked: {a['track_e_blocked'].value}"]
    print("\n".join(lines));return lines
if __name__=="__main__":run()
