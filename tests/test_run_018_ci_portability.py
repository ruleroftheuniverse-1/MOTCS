from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import subprocess,sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"scripts"))
from audit_canonical_line_endings import BINARY_EXTENSIONS,TEXT_EXTENSIONS,audit  # noqa:E402
from mgf_mot.release_manifest import file_hash,load_release_bundle,verify_bundle

def test_gitattributes_declares_lf_text_and_known_binary_formats():
    text=(ROOT/".gitattributes").read_text(encoding="utf-8")
    assert "* text=auto eol=lf" in text
    for extension in TEXT_EXTENSIONS:assert f"*{extension} text eol=lf" in text
    for extension in BINARY_EXTENSIONS:assert f"*{extension} binary" in text

def test_raw_hashes_expose_crlf_drift_instead_of_hiding_it():
    lf=b'{"value":1}\n';crlf=b'{"value":1}\r\n'
    assert sha256(lf).hexdigest()!=sha256(crlf).hexdigest()
    assert crlf.replace(b"\r\n",b"\n")==lf
    source=(ROOT/"src/mgf_mot/release_manifest.py").read_text(encoding="utf-8")
    assert "sha256(path.read_bytes()).hexdigest()" in source

def test_every_tracked_text_file_is_canonical_lf():
    result=audit(ROOT);assert result["passed"] and result["offending_paths"]==[]

def test_renormalization_audit_proves_text_equivalence_and_binary_stability():
    result=json.loads((ROOT/"outputs/provisional/release/run_018/line-ending-renormalization-audit.json").read_text(encoding="utf-8"))
    assert result["changed_path_count"]>0 and result["all_renormalized_text_content_equal"]
    assert result["all_binary_artifacts_byte_identical"] and result["binary_changed_paths"]==[]
    assert all(row["line_ending_only"] and row["parsed_content_equivalent"] is not False for row in result["changed_paths"])

def test_catalog_hashes_checked_out_canonical_bytes():
    bundle=load_release_bundle(ROOT/"outputs/provisional/release/run_018")
    for item in bundle.artifact_catalog.artifacts:assert file_hash(ROOT/item.path)==item.sha256
    assert verify_bundle(ROOT,bundle).valid

def test_release_generation_is_semantically_stable_across_second_generation():
    command=[sys.executable,str(ROOT/"scripts/generate_release_manifest.py")]
    subprocess.run(command,cwd=ROOT,check=True,capture_output=True,text=True)
    first=json.loads((ROOT/"outputs/provisional/release/run_018/semantic-release-manifest.json").read_text(encoding="utf-8"))["semantic_hash"]
    subprocess.run(command,cwd=ROOT,check=True,capture_output=True,text=True)
    second=json.loads((ROOT/"outputs/provisional/release/run_018/semantic-release-manifest.json").read_text(encoding="utf-8"))["semantic_hash"]
    assert first==second and verify_bundle(ROOT,load_release_bundle(ROOT/"outputs/provisional/release/run_018")).valid

def test_readme_test_count_fence_is_not_nested():
    text=(ROOT/"README.md").read_text(encoding="utf-8");block=text.split("Current test status:",1)[1].split("One known",1)[0]
    assert block.count("```text")==1 and block.count("```")==2 and "````" not in block
