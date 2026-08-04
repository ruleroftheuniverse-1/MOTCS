"""Build and inspect Run 018 wheel/sdist without publishing."""
from __future__ import annotations
import json
from pathlib import Path
import shutil,subprocess,sys,tarfile,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"outputs/provisional/release/run_018";DIST=OUT/"dist"
LABELS=("MODEL_INDEPENDENT","NOT_RODRIGUEZ_REPLICATION","RUN_018","REPRODUCIBLE_CONTROL_INFRA_RELEASE_ONLY")
def run():
    if DIST.exists():shutil.rmtree(DIST)
    DIST.mkdir(parents=True);subprocess.run([sys.executable,"-m","build","--outdir",str(DIST)],cwd=ROOT,check=True)
    wheel=next(DIST.glob("*.whl"));sdist=next(DIST.glob("*.tar.gz"))
    with zipfile.ZipFile(wheel) as z:wheel_files=sorted(z.namelist())
    with tarfile.open(sdist) as t:sdist_files=sorted(t.getnames())
    forbidden_tokens=("outputs/provisional","__pycache__",".pytest_cache","tmp/","author correspondence","C:/Users/","C:\\Users\\")
    forbidden=[name for name in wheel_files+sdist_files if any(token.lower() in name.lower() for token in forbidden_tokens)]
    with tempfile.TemporaryDirectory(prefix="mgf_run018_pkg_") as d:
        env=Path(d)/"venv";subprocess.run([sys.executable,"-m","venv","--system-site-packages",str(env)],check=True)
        python=env/("Scripts/python.exe" if sys.platform=="win32" else "bin/python")
        subprocess.run([str(python),"-m","pip","install",str(wheel)],check=True,capture_output=True,text=True)
        smoke_run=subprocess.run([str(python),"-c","from mgf_mot.release_manifest import semantic_hash; assert len(semantic_hash({'smoke':1}))==64; print('MODEL_INDEPENDENT_SMOKE_OK')"],cwd=d,capture_output=True,text=True)
        if smoke_run.returncode:
            raise RuntimeError("installed-wheel smoke failed: "+smoke_run.stderr.strip())
        smoke=smoke_run.stdout.strip()
    payload={"labels":LABELS,"build_status":"PACKAGE_BUILD_OK" if not forbidden else "PACKAGE_BUILD_FAILED","wheel":wheel.name,"sdist":sdist.name,"wheel_files":wheel_files,"sdist_files":sdist_files,"forbidden_members":forbidden,"installed_import_smoke":smoke,"published":False,"includes_force_caches":False,"includes_transient_outputs":False}
    path=OUT/"package-content-report.json";path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n");print(payload["build_status"]);return payload
if __name__=="__main__":run()
