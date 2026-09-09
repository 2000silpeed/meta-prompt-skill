#!/usr/bin/env python3
"""Offline, configuration-blind fixture evaluator; no network or model calls."""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(path):
    return json.loads(Path(path).read_text())


def eligible(task, service):
    offer = service['offers'].get(task['capability'])
    return (service['available'] and offer is not None
            and offer['cost'] is not None
            and (not task['local_only'] or service['local'])
            and (not task['fixed_service'] or task['fixed_service'] == service['id']))


def waves_for(tasks):
    done, waves = set(), []
    while len(done) < len(tasks):
        ready = sorted(t['id'] for t in tasks if t['id'] not in done
                       and set(t['depends_on']) <= done)
        if not ready:
            raise ValueError('Invalid fixture DAG')
        waves.append(ready)
        done.update(ready)
    return waves


def metrics(case, assignment):
    tasks = {t['id']: t for t in case['tasks']}
    cost = sum(assignment[k]['offers'][t['capability']]['cost'] for k, t in tasks.items())
    cost += (len({s['id'] for s in assignment.values()}) - 1) * case['setup_cost']
    cost += sum(case['transfer_cost'] for k, t in tasks.items() for d in t['depends_on']
                if assignment[d]['id'] != assignment[k]['id'])
    ends = {}
    for wave in waves_for(case['tasks']):
        for k in wave:
            t = tasks[k]
            ends[k] = assignment[k]['offers'][t['capability']]['duration'] + max(
                (ends[d] for d in t['depends_on']), default=0)
    return cost, max(ends.values())


def solve(case, services):
    tasks = sorted(case['tasks'], key=lambda t: t['id'])
    candidates = [[s for s in services if eligible(t, s)] for t in tasks]
    blockers = set()
    by_id = {s['id']: s for s in services}
    for t, opts in zip(tasks, candidates):
        if not opts:
            fixed = by_id.get(t['fixed_service'])
            blockers.add('required_service_unavailable' if fixed and not fixed['available']
                         else 'no_eligible_service')
    if blockers:
        return dict(status='blocked', blockers=sorted(blockers), assignments=[],
                    total_cost=None, latency=None, waves=[])
    feasible = []
    for combo in itertools.product(*candidates):
        assignment = dict(zip((t['id'] for t in tasks), combo))
        cost, latency = metrics(case, assignment)
        if cost <= case['budget']:
            vector = tuple(s['id'] for s in combo)
            key = (cost, latency, vector) if case['objective'] == 'cost' else (latency, cost, vector)
            feasible.append((key, assignment, cost, latency))
    if not feasible:
        return dict(status='blocked', blockers=['budget_exceeded'], assignments=[],
                    total_cost=None, latency=None, waves=[])
    _, assignment, cost, latency = min(feasible, key=lambda x: x[0])
    return dict(status='planned', blockers=[], assignments=[
        dict(task_id=t['id'], service_id=assignment[t['id']]['id'],
             depends_on=t['depends_on'], guidebook=assignment[t['id']]['guidebook'] or '_generic')
        for t in tasks], total_cost=cost, latency=latency, waves=waves_for(tasks))


def grade(document, fixture):
    cases = document.get('cases', []) if isinstance(document, dict) else []
    if not isinstance(cases, list):
        cases = []
    ids = [c.get('case_id') for c in cases if isinstance(c, dict)]
    coverage = len(cases) == len(fixture['cases']) and sorted(str(x) for x in ids) == sorted(c['id'] for c in fixture['cases'])
    by_service = {s['id']: s for s in fixture['services']}
    rows = []
    for case in fixture['cases']:
        found = [c for c in cases if isinstance(c, dict) and c.get('case_id') == case['id']]
        got = found[0] if len(found) == 1 else {}
        expected = solve(case, fixture['services'])
        assignments = got.get('assignments')
        shape = isinstance(assignments, list) and all(isinstance(a, dict) for a in assignments)
        assignments = assignments if shape else []
        expected_ids = [a['task_id'] for a in expected['assignments']]
        exact_ids = shape and [a.get('task_id') for a in assignments] == expected_ids
        checks = {'coverage': coverage and len(found) == 1,
                  'status': got.get('status') == expected['status'],
                  'blockers': isinstance(got.get('blockers'), list) and sorted(got['blockers']) == expected['blockers'],
                  'metrics': all(k in got and got[k] == expected[k] and not isinstance(got[k], bool)
                                 for k in ['total_cost', 'latency']),
                  'waves': got.get('waves') == expected['waves']}
        if expected['status'] == 'blocked':
            checks.update(eligible=exact_ids, optimal=exact_ids, handoff=exact_ids, prompt_contract=exact_ids)
        else:
            task_by_id = {t['id']: t for t in case['tasks']}
            checks['eligible'] = exact_ids and all(
                a.get('service_id') in by_service and eligible(task_by_id[a['task_id']], by_service[a['service_id']])
                for a in assignments)
            checks['optimal'] = exact_ids and [a.get('service_id') for a in assignments] == [a['service_id'] for a in expected['assignments']]
            checks['handoff'] = exact_ids and all(a.get('depends_on') == e['depends_on'] and a.get('guidebook') == e['guidebook']
                                                for a, e in zip(assignments, expected['assignments']))
            checks['prompt_contract'] = exact_ids and all(
                isinstance(a.get('prompt_contract'), dict) and all(
                    isinstance(a['prompt_contract'].get(k), str) and a['prompt_contract'][k].strip()
                    for k in ['goal', 'context', 'constraints', 'done_when']) for a in assignments)
        rows.append(dict(case_id=case['id'], checks=checks, passed=sum(checks.values()), total=len(checks),
                         fully_passed=all(checks.values())))
    return dict(passed=sum(r['passed'] for r in rows), total=sum(r['total'] for r in rows),
                cases_passed=sum(r['fully_passed'] for r in rows), case_count=len(rows), details=rows,
                note='prompt_contract checks structure only, not semantic quality')


def verify_frozen():
    manifest = load(ROOT/'manifest.json')
    for name, digest in manifest['input_sha256'].items():
        assert hashlib.sha256((ROOT/'input'/name).read_bytes()).hexdigest() == digest, name
    if 'evaluator_sha256' in manifest:
        assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == manifest['evaluator_sha256']


def self_test():
    fixture = load(ROOT/'input/cases.json')
    reference = {'cases': []}
    for c in fixture['cases']:
        r = solve(c, fixture['services'])
        r['case_id'] = c['id']
        for a in r['assignments']:
            a['prompt_contract'] = {k: 'structural evaluator fixture' for k in ['goal','context','constraints','done_when']}
        reference['cases'].append(r)
    assert grade(reference, fixture)['passed'] == 54
    assert solve(fixture['cases'][0],fixture['services'])['total_cost'] == 0
    assert solve(fixture['cases'][0],fixture['services'])['latency'] == 15
    assert solve(fixture['cases'][1],fixture['services'])['latency'] == 10
    assert solve(fixture['cases'][2],fixture['services'])['total_cost'] == 6
    assert solve(fixture['cases'][4],fixture['services'])['blockers'] == ['no_eligible_service','required_service_unavailable']
    assert solve(fixture['cases'][5],fixture['services'])['blockers'] == ['budget_exceeded']
    # Deliberately corrupt decisions, outputs and uncertainty handling.
    mutations = [lambda p:p['cases'].pop(),
                 lambda p:p['cases'][0].update(total_cost=99),
                 lambda p:p['cases'][0]['assignments'][0].update(service_id='cloud-offline'),
                 lambda p:p['cases'][0].update(waves=[['z'],['r','w']]),
                 lambda p:p['cases'][1]['assignments'][0].update(guidebook='invented'),
                 lambda p:p['cases'][4].update(status='planned'),
                 lambda p:p['cases'][4].update(total_cost=0),
                 lambda p:p['cases'][0]['assignments'][0].update(prompt_contract={}),
                 lambda p:p['cases'][0]['assignments'][0].update(depends_on=['z'])]
    for mutate in mutations:
        candidate=copy.deepcopy(reference); mutate(candidate)
        assert grade(candidate, fixture)['passed'] < 54
    assert grade({}, fixture)['passed'] == 0
    print('PASS: oracle hand-calculations, 9 deliberate errors, empty output')
    return reference


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('output', nargs='?')
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args(); verify_frozen()
    if args.self_test:
        self_test()
    if args.output:
        try: document=load(args.output)
        except (OSError, ValueError): document={}
        print(json.dumps(grade(document,load(ROOT/'input/cases.json')),ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
