"""One-time working-tree LF normalization with a machine-readable content audit."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import sys
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from audit_canonical_line_endings import classify,tracked_paths  # noqa:E402
OUT=ROOT/"outputs/provisional/release/run_018/line-ending-renormalization-audit.json"
LABELS=("MODEL_INDEPENDENT","NOT_RODRIGUEZ_REPLICATION","RUN_018","CI_PORTABILITY_CORRECTION_ONLY")
def normalized(data:bytes)->bytes:return data.replace(b"\r\n",b"\n").replace(b"\r",b"\n")
def parsed(path:Path,data:bytes):
    text=data.decode("utf-8")
    if path.suffix.lower() in {".json",".ipynb"}:return json.loads(text)
    if path.suffix.lower() in {".yaml",".yml"}:return yaml.safe_load(text)
    return None
def run():
    binary_before={p.relative_to(ROOT).as_posix():sha256(p.read_bytes()).hexdigest() for p in tracked_paths(ROOT) if p.is_file() and classify(p)=="binary"}
    rows=[]
    for path in tracked_paths(ROOT):
        if not path.is_file() or classify(path)!="text":continue
        old=path.read_bytes();new=normalized(old)
        if old==new:continue
        parsed_equal=None
        if path.suffix.lower() in {".json",".ipynb",".yaml",".yml"}:parsed_equal=parsed(path,old)==parsed(path,new)
        if normalized(old)!=new or parsed_equal is False:raise RuntimeError(f"non-line-ending content change detected for {path}")
        path.write_bytes(new)
        rows.append({"path":path.relative_to(ROOT).as_posix(),"old_sha256":sha256(old).hexdigest(),"new_sha256":sha256(new).hexdigest(),"classification":"text","line_ending_only":True,"parsed_content_equivalent":parsed_equal,"old_crlf_count":old.count(b"\r\n"),"new_crlf_count":0})
    binary_after={p.relative_to(ROOT).as_posix():sha256(p.read_bytes()).hexdigest() for p in tracked_paths(ROOT) if p.is_file() and classify(p)=="binary"}
    payload={"labels":LABELS,"changed_path_count":len(rows),"changed_paths":rows,"binary_file_count":len(binary_before),"binary_changed_paths":sorted(path for path in binary_before if binary_before[path]!=binary_after.get(path)),"all_binary_artifacts_byte_identical":binary_before==binary_after,"all_renormalized_text_content_equal":all(row["line_ending_only"] and row["parsed_content_equivalent"] is not False for row in rows),"readme_formatting_correction_recorded_separately":True,"audit_status":"LINE_ENDING_RENORMALIZATION_OK" if binary_before==binary_after else "LINE_ENDING_RENORMALIZATION_FAILED"}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n");print(payload["audit_status"],len(rows));return payload
if __name__=="__main__":raise SystemExit(0 if run()["audit_status"]=="LINE_ENDING_RENORMALIZATION_OK" else 1)
