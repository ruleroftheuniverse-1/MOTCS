"""Fail fast when tracked repository text is not canonical LF bytes."""
from __future__ import annotations
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS={".py",".md",".json",".yaml",".yml",".toml",".txt",".csv",".ipynb",".html",".css",".js",".ts",".tsx",".ps1",".sh"}
BINARY_EXTENSIONS={".npz",".npy",".png",".jpg",".jpeg",".gif",".pdf",".zip",".whl",".gz",".pkl",".pickle",".h5",".hdf5"}
TEXT_NAMES={".gitignore",".gitattributes"}
def tracked_paths(root:Path=ROOT):
    raw=subprocess.run(["git","ls-files","-z"],cwd=root,check=True,capture_output=True).stdout
    return tuple(root/part.decode("utf-8") for part in raw.split(b"\0") if part)
def classify(path:Path):
    if path.suffix.lower() in BINARY_EXTENSIONS:return "binary"
    if path.suffix.lower() in TEXT_EXTENSIONS or path.name in TEXT_NAMES:return "text"
    data=path.read_bytes();return "binary" if b"\0" in data else "text"
def audit(root:Path=ROOT):
    offending=[];unknown=[];text_count=binary_count=0
    for path in tracked_paths(root):
        if not path.is_file():continue
        kind=classify(path)
        if kind=="binary":binary_count+=1;continue
        text_count+=1;data=path.read_bytes()
        if b"\r" in data:offending.append(path.relative_to(root).as_posix())
        if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in TEXT_NAMES:unknown.append(path.relative_to(root).as_posix())
    return {"policy":"TRACKED_TEXT_MUST_USE_LF_BYTES","text_file_count":text_count,"binary_file_count":binary_count,"offending_paths":offending,"heuristically_classified_text":unknown,"passed":not offending}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--json",action="store_true");a=p.parse_args();result=audit();print(json.dumps(result,indent=2,sort_keys=True) if a.json else ("CANONICAL_LF_OK" if result["passed"] else "NONCANONICAL_LINE_ENDINGS: "+", ".join(result["offending_paths"])));raise SystemExit(0 if result["passed"] else 1)
