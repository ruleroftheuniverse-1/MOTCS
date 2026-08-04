"""Compare HEAD blobs with the renormalized index and prove content preservation."""
from __future__ import annotations
from hashlib import sha256
import json,subprocess,sys
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"outputs/provisional/release/run_018/line-ending-renormalization-audit.json"
LABELS=("MODEL_INDEPENDENT","NOT_RODRIGUEZ_REPLICATION","RUN_018","CI_PORTABILITY_CORRECTION_ONLY")
BINARY={".npz",".npy",".png",".jpg",".jpeg",".gif",".pdf",".zip",".whl",".gz",".pkl",".pickle",".h5",".hdf5"}
def _git(*args,check=True):return subprocess.run(["git",*args],cwd=ROOT,capture_output=True,check=check).stdout
def _normalize(data):return data.replace(b"\r\n",b"\n").replace(b"\r",b"\n")
def _parse(path,data):
    text=data.decode("utf-8")
    if path.suffix.lower() in {".json",".ipynb"}:return json.loads(text)
    if path.suffix.lower() in {".yaml",".yml"}:return yaml.safe_load(text)
    return None
def run():
    changed=[Path(x.decode()) for x in _git("diff","--cached","--name-only","-z").split(b"\0") if x]
    rows=[];valid=True;binary_changed=[]
    for path in changed:
        new=_git("show",f":{path.as_posix()}");old_result=subprocess.run(["git","show",f"HEAD:{path.as_posix()}"],cwd=ROOT,capture_output=True);old=None if old_result.returncode else old_result.stdout
        classification="binary" if path.suffix.lower() in BINARY else "text"
        line_only=old is None or (classification=="text" and _normalize(old)==_normalize(new)) or (classification=="binary" and old==new)
        parsed=None
        if old is not None and classification=="text" and path.suffix.lower() in {".json",".ipynb",".yaml",".yml"}:
            try:parsed=_parse(path,old)==_parse(path,new)
            except Exception:parsed=False
        if classification=="binary" and old!=new:binary_changed.append(path.as_posix())
        if not line_only or parsed is False:valid=False
        rows.append({"path":path.as_posix(),"old_sha256":None if old is None else sha256(old).hexdigest(),"new_sha256":sha256(new).hexdigest(),"classification":classification,"line_ending_only":line_only,"parsed_content_equivalent":parsed,"old_crlf_count":0 if old is None else old.count(b"\r\n"),"new_crlf_count":new.count(b"\r\n"),"documentation_only_exception":path.as_posix()=="README.md" and not line_only})
    payload={"labels":LABELS,"changed_path_count":len(rows),"changed_paths":rows,"binary_changed_paths":binary_changed,"all_binary_artifacts_byte_identical":not binary_changed,"all_renormalized_text_content_equal":valid,"audit_status":"LINE_ENDING_RENORMALIZATION_OK" if valid and not binary_changed else "LINE_ENDING_RENORMALIZATION_FAILED"}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n");print(payload["audit_status"],len(rows));return payload
if __name__=="__main__":raise SystemExit(0 if run()["audit_status"]=="LINE_ENDING_RENORMALIZATION_OK" else 1)
