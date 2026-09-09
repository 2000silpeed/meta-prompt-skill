#!/usr/bin/env python3
"""Record stages and evaluate saved code; does not start model calls."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from grade import ROOT, digest_tree, frozen_check


def load(path): return json.loads(path.read_text())


def score(candidate, output):
    subprocess.run([sys.executable,str(ROOT/'grade.py'),'--candidate',str(candidate),'--output',str(output)],check=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['start','snapshot','finish'])
    parser.add_argument('run')
    parser.add_argument('--stage')
    args=parser.parse_args(); frozen_check()
    run=ROOT/'runs'/args.run
    if args.action=='start':
        path=run/'start.json'
        with path.open('x') as f: json.dump({'started_epoch':time.time()},f)
        return
    if args.action=='snapshot':
        if args.stage not in ['draft','pre-integration']: raise ValueError('stage required')
        target=run/args.stage
        shutil.copytree(run/'work',target,ignore=shutil.ignore_patterns('__pycache__'))
        score(target,run/(args.stage+'-score.json'))
        return
    completion=run/'work/completion.json'
    if not completion.exists(): raise ValueError('completion artifact missing')
    source=digest_tree(run/'work/shop')
    expected=load(ROOT/'manifest.json')['frozen']
    for name in ['CONTRACT.md','tests/test_public.py']:
        if hashlib.sha256((run/'work'/name).read_bytes()).hexdigest()!=expected['fixture/'+name]:
            raise ValueError('Protected contract/public tests changed: '+name)
    measurement_path=run/'measurement.json'
    start=load(run/'start.json')['started_epoch']
    if measurement_path.exists():
        measurement=load(measurement_path)
        if measurement['source_sha256']!=source: raise ValueError('Completed source changed')
    else:
        measurement={'started_epoch':start,'completed_epoch':completion.stat().st_mtime,
                     'observed_epoch':time.time(),'source_sha256':source,
                     'artifact_seconds':round(completion.stat().st_mtime-start,3)}
        measurement_path.write_text(json.dumps(measurement,indent=2))
    public=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],
                          cwd=run/'work',text=True,capture_output=True,timeout=30)
    (run/'public-test.log').write_text(public.stdout+public.stderr)
    score(run/'work',run/'score.json')
    recorded=load(run/'score.json')
    recorded.update(measurement=measurement,agents=load(run/'agents.json'),
                    public_tests_passed=public.returncode==0,
                    reported_completion=load(completion),actual_tokens=None,actual_cost=None)
    (run/'score.json').write_text(json.dumps(recorded,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
