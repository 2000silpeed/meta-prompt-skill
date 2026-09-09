#!/usr/bin/env python3
"""Check saved experiment integrity without invoking models or editing candidates."""
import json
from collections import Counter
from grade import ROOT, frozen_check, digest_tree


def read(path):
    return json.loads(path.read_text())


def main():
    frozen_check()
    manifest = read(ROOT / 'manifest.json')
    agents, cells, intervals, prompts = [], Counter(), [], {}
    for name in manifest['orders']:
        run = ROOT / 'runs' / name
        cfg, score = read(run / 'config.json'), read(run / 'score.json')
        assert cfg['model'] in manifest['models'].values(), name
        assert cfg['reasoning_effort'] == manifest['effort'], name
        prompt = (run / 'prompt.txt').read_text().replace(str(run / 'work'), '<WORK>')
        prompt_key = ('all' if cfg['arm'] == 'raw' else cfg['model'], cfg['arm'])
        assert prompts.setdefault(prompt_key, prompt) == prompt, 'prompt changed across repetitions'
        assert score['total'] == manifest['acceptance_tests'], name
        assert score['source_sha256'] == digest_tree(run / 'work' / 'shop'), name
        assert score['measurement']['source_sha256'] == score['source_sha256'], name
        assert len(score['agents']) == 1, name
        assert score['agents'] == read(run / 'agents.json'), name
        agents.extend(score['agents'])
        cells[(cfg['model'], cfg['arm'])] += 1
        m = score['measurement']
        assert m['completed_epoch'] >= m['started_epoch'], name
        intervals.append((m['started_epoch'], m['completed_epoch'], name))
        for relative in ['CONTRACT.md', 'tests/test_public.py']:
            assert (run / 'work' / relative).read_bytes() == (ROOT / 'fixture' / relative).read_bytes(), name
    assert len(agents) == len(set(agents)) == 12
    assert len(cells) == 6 and all(n == 2 for n in cells.values())
    assert all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])), 'overlap'
    print('PASS: 12 independent saved runs; 6 cells × 2; 41 tests; frozen inputs, candidate hashes, protected files and sequential completion intervals verified.')


if __name__ == '__main__':
    main()
