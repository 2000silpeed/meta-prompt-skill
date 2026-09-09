#!/usr/bin/env python3
"""Exploratory check chosen after one reviewer's finding; separate from scoring."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from grade import ROOT, frozen_check


def main():
    frozen_check()
    provenance=json.loads((ROOT/'private/probe-provenance.json').read_text())
    probe=ROOT/'private/probe_large_integer.py'
    if hashlib.sha256(probe.read_bytes()).hexdigest()!=provenance['probe_sha256']:
        raise ValueError('Exploratory probe changed')
    rows=[]
    for run in sorted((ROOT/'runs').iterdir()):
        if not (run/'score.json').exists(): continue
        for stage in ['work','draft','pre-integration']:
            candidate=run/stage
            if not candidate.exists(): continue
            env=os.environ.copy(); env['PYTHONDONTWRITEBYTECODE']='1'
            with tempfile.TemporaryDirectory(prefix='posthoc-probe-') as tmp:
                call=subprocess.run([sys.executable,str(probe),str(candidate)],cwd=tmp,
                                    env=env,text=True,capture_output=True,timeout=10)
            result=json.loads(call.stdout) if call.returncode==0 else {'passed':False,'error':call.stderr}
            rows.append(dict(run=run.name,stage=stage,**result))
    (ROOT/'posthoc-results.json').write_text(json.dumps({'provenance':provenance,'results':rows},ensure_ascii=False,indent=2))
    print(json.dumps([{'run':r['run'],'stage':r['stage'],'passed':r['passed']} for r in rows],ensure_ascii=False))

if __name__=='__main__': main()
