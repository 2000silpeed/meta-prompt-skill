#!/usr/bin/env python3
"""Evaluate one candidate against the pre-frozen regression suite."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import unittest

ROOT = Path(__file__).resolve().parent


def digest_tree(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*.py')) if '__pycache__' not in p.parts}


def frozen_check():
    path = ROOT / 'manifest.json'
    if not path.exists():
        return
    manifest = json.loads(path.read_text())
    for name, digest in manifest['frozen'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Frozen input/evaluator changed: {name}')


class Results(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({'id': test.id(), 'status': 'passed'})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record_error(test, err, 'failed')

    def addError(self, test, err):
        super().addError(test, err)
        self.record_error(test, err, 'error')

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.records.append({'id': test.id(), 'status': 'skipped', 'detail': reason})

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.record_error(test, err, 'failed')

    def record_error(self, test, err, status):
        detail = ''.join(traceback.format_exception(*err))
        existing = next((r for r in self.records if r['id'] == test.id()), None)
        if existing:
            existing['detail'] = existing.get('detail', '') + detail
            existing['status'] = status
        else:
            self.records.append({'id': test.id(), 'status': status, 'detail': detail})


def worker(candidate):
    sys.path.insert(0, str(candidate))
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'private'), pattern='test_acceptance.py')
    tree = ast.parse((ROOT / 'private/test_acceptance.py').read_text())
    expected = sum(isinstance(n, ast.FunctionDef) and n.name.startswith('test_') for n in ast.walk(tree))
    result = Results()
    suite.run(result)
    return {'passed': sum(r['status'] == 'passed' for r in result.records), 'total': expected,
            'tests_run': result.testsRun, 'details': result.records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    if args.worker:
        print(json.dumps(worker(candidate), ensure_ascii=False))
        return
    frozen_check()
    with tempfile.TemporaryDirectory(prefix='regression-evaluation-') as tmp:
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        try:
            call = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--candidate', str(candidate), '--worker'],
                                  capture_output=True, text=True, cwd=tmp, timeout=30, env=env)
            if call.returncode:
                raise RuntimeError(call.stderr)
            result = json.loads(call.stdout)
        except (subprocess.TimeoutExpired, ValueError, RuntimeError) as exc:
            result = {'passed': 0, 'total': None, 'tests_run': 0, 'details': [], 'evaluation_error': str(exc)}
    result['source_sha256'] = digest_tree(candidate / 'shop')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in ['details', 'source_sha256']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
