"""Safe, preserve-first model package intake. No promotion or physics execution."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/"src"
if str(SRC) not in sys.path:sys.path.insert(0,str(SRC))
from mgf_mot.model_intake import intake_molecular_model  # noqa:E402
from mgf_mot.molecular_model_package import RUN012_LABEL  # noqa:E402
ACCEPTED=ROOT/"outputs/provisional/molecular_model_packages/run_012"/f"{RUN012_LABEL}_ACCEPTED_PROVISIONAL_REFERENCE_PACKAGE"
def run(source:Path,destination:Path,description:str,validation_only=False):return intake_molecular_model(source,destination,description,accepted_base=ACCEPTED,validation_only=validation_only)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("source",type=Path);p.add_argument("--destination",type=Path,default=ROOT/"outputs/provisional/release/run_018/author_model_intake_quarantine");p.add_argument("--source-description",required=True);p.add_argument("--validation-only",action="store_true");a=p.parse_args();r=run(a.source,a.destination,a.source_description,a.validation_only);print(json.dumps(r.__dict__,indent=2,sort_keys=True,default=list));raise SystemExit(0 if not r.validation_errors else 1)
