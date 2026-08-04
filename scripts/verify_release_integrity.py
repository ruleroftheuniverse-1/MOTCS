"""Read-only Run 018 release integrity verifier."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/"src"
if str(SRC) not in sys.path:sys.path.insert(0,str(SRC))
from mgf_mot.release_manifest import load_release_bundle,verify_bundle  # noqa:E402
DEFAULT=ROOT/"outputs/provisional/release/run_018"
def run(directory:Path=DEFAULT):
    report=verify_bundle(ROOT,load_release_bundle(directory));return report
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--release-dir",type=Path,default=DEFAULT);p.add_argument("--json",action="store_true");a=p.parse_args();r=run(a.release_dir)
    print(json.dumps(r.__dict__,indent=2,sort_keys=True,default=list) if a.json else f"{r.status}: modified={len(r.modified_files)} missing={len(r.missing_files)} broken_docs={not r.documentation_links_valid}")
    raise SystemExit(0 if r.valid else 1)
