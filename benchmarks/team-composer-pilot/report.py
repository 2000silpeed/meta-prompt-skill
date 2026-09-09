#!/usr/bin/env python3
"""Generate measured results from saved artifacts; never executes agent tasks."""
import json
import hashlib
import statistics
import time
from pathlib import Path
from evaluate import ROOT, grade, load, verify_frozen


def main():
    verify_frozen()
    fixture = load(ROOT/'input/cases.json')
    results = []
    for run in sorted((ROOT/'runs').iterdir()):
        if not run.is_dir():
            continue
        final = run/'final.json'
        if not final.exists():
            continue
        score = grade(load(final), fixture)
        start = load(run/'start.json')['started_epoch']
        digest = hashlib.sha256(final.read_bytes()).hexdigest()
        measurement_path = run/'measurement.json'
        if measurement_path.exists():
            measurement = load(measurement_path)
            if measurement['final_sha256'] != digest or measurement['started_epoch'] != start:
                raise ValueError(f'Artifact or start record changed: {run.name}; use a new run directory')
        else:
            measurement = dict(started_epoch=start, artifact_ready_epoch=final.stat().st_mtime,
                               observed_epoch=time.time(), final_sha256=digest,
                               method='start marker to final output mtime, frozen at first scoring')
            measurement_path.write_text(json.dumps(measurement, indent=2))
        config = run.name.split('-', 1)[1]
        score.update(run=run.name, config=config,
                     artifact_seconds=round(measurement['artifact_ready_epoch']-start, 3),
                     final_sha256=digest,
                     agent_calls=len(load(run/'agents.json')),
                     actual_cost=None, actual_tokens=None,
                     agents=load(run/'agents.json'))
        if config == 'review':
            score['draft_score'] = grade(load(run/'draft.json'),fixture)['passed']
        if config == 'parallel':
            parts = {'cases':load(run/'part-a.json')['cases']+load(run/'part-b.json')['cases']}
            score['parts_score'] = grade(parts,fixture)['passed']
        (run/'score.json').write_text(json.dumps(score,ensure_ascii=False,indent=2))
        results.append(score)
    (ROOT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    lines = ['# 서비스 조합 설계 파일럿 결과','',
             '고정 합성 과제 6개, 같은 런타임의 세 구성. 자동 점수는 요구사항 준수 검사이며 전반적 결과 품질이나 서비스 성능 순위가 아니다.','',
             '| 실행 | 조건 통과 | 완전 통과 케이스 | 산출물 도달 시간 | 에이전트 호출 |',
             '|---|---:|---:|---:|---:|']
    for r in results:
        lines.append(f"| {r['run']} | {r['passed']}/{r['total']} | {r['cases_passed']}/{r['case_count']} | {r['artifact_seconds']:.1f}초 | {r['agent_calls']} |")
    lines += ['', '## 구성별 관측 요약', '',
              '| 구성 | 실행 수 | 조건 통과 합계 | 도달 시간 평균 (최소–최대) | 호출 합계 |',
              '|---|---:|---:|---:|---:|']
    for config in ['single','parallel','review']:
        rows=[r for r in results if r['config']==config]
        if not rows: continue
        times=[r['artifact_seconds'] for r in rows]
        lines.append(f"| {config} | {len(rows)} | {sum(r['passed'] for r in rows)}/{sum(r['total'] for r in rows)} | {statistics.mean(times):.1f}초 ({min(times):.1f}–{max(times):.1f}) | {sum(r['agent_calls'] for r in rows)} |")
    lines += ['', '## 검토·통합 전후', '']
    for r in results:
        key='draft_score' if 'draft_score' in r else 'parts_score' if 'parts_score' in r else None
        if key: lines.append(f"- {r['run']}: {r[key]}/54 → {r['passed']}/54")
    lines += ['', '## 해석의 한계', '',
              '- 실제 금액·토큰 사용량은 미측정이다. 호출 수만으로 비용 비율을 추정하지 않는다.',
              '- 시간은 시작 마커부터 최종 산출물 수정 시점까지이며 역할 간 대기와 호출 준비를 포함한다.',
              '- 프롬프트 내용의 의미적 품질은 이 자동 점수에 포함하지 않는다.',
              '- 구성당 두 번의 고정 과제 관측이다. 유의성·일반적 우열·다른 서비스의 성능을 주장할 수 없다.',
              '- 상세 실행 조건과 격리 한계는 [PROTOCOL.md](PROTOCOL.md)를 참고한다.', '']
    (ROOT/'RESULTS.md').write_text('\n'.join(lines))
    print(json.dumps([{k:r[k] for k in ['run','passed','total','artifact_seconds']} for r in results],ensure_ascii=False))

if __name__=='__main__': main()
