#!/usr/bin/env python3
import json
import statistics
from grade import ROOT, frozen_check, digest_tree


def main():
    frozen_check(); rows=[]
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for name in manifest['orders']:
        run=ROOT/'runs'/name
        if not (run/'score.json').exists(): continue
        score=json.loads((run/'score.json').read_text()); cfg=json.loads((run/'config.json').read_text())
        if score['source_sha256']!=digest_tree(run/'work/shop'): raise ValueError('Completed source changed: '+name)
        rows.append(dict(run=name,**cfg,passed=score['passed'],total=score['total'],
                         seconds=score['measurement']['artifact_seconds'],public_passed=score['public_tests_passed'],
                         failed_tests=[r['id'] for r in score['details'] if r['status']!='passed']))
    (ROOT/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    lines=['# 모델별 일반 지시 vs 메타 프롬프트 결과','',
           '같은 상세 명세와 시작 코드, 모델별 medium 추론 설정, 사전에 고정한 41개 평가 테스트를 사용했다.','',
           '| 모델 | 조건 | 실행 수 | 테스트 통과 합계 | 평균 시간 (최소–최대) |','|---|---|---:|---:|---:|']
    comparisons=[]
    for label,model in manifest['models'].items():
        groups={arm:[r for r in rows if r['model']==model and r['arm']==arm] for arm in ['raw','meta']}
        for arm,group in groups.items():
            if not group: continue
            t=[r['seconds'] for r in group]
            lines.append(f"| {label} | {arm} | {len(group)} | {sum(r['passed'] for r in group)}/{sum(r['total'] for r in group)} | {statistics.mean(t):.1f}초 ({min(t):.1f}–{max(t):.1f}) |")
        if all(len(g)==2 for g in groups.values()):
            delta=sum(r['passed'] for r in groups['meta'])-sum(r['passed'] for r in groups['raw'])
            time_delta=statistics.mean(r['seconds'] for r in groups['meta'])-statistics.mean(r['seconds'] for r in groups['raw'])
            comparisons.append(dict(model=model,passed_delta=delta,mean_seconds_delta=round(time_delta,3)))
    lines+=['','## 모델 내 차이','','메타 − 일반. 양수 시간은 메타 조건이 더 오래 걸렸다는 뜻이다.','',
            '| 모델 | 통과 항목 차이 (2회 합계) | 평균 시간 차이 |','|---|---:|---:|']
    for r in comparisons: lines.append(f"| {r['model']} | {r['passed_delta']:+d} | {r['mean_seconds_delta']:+.1f}초 |")
    lines+=['','## 원본 실행','','| 실행 | 평가 | 공개·저장된 자체 테스트 | 시간 |','|---|---:|---|---:|']
    for r in rows: lines.append(f"| {r['run']} | {r['passed']}/{r['total']} | {'통과' if r['public_passed'] else '실패'} | {r['seconds']:.1f}초 |")
    lines+=['','## 실패 항목','']
    for r in rows:
        if r['failed_tests']: lines.append(f"- {r['run']}: "+', '.join(r['failed_tests']))
    lines+=['','한 상세 명세 과제의 조건당 두 번 관측이다. 모델별 전용 가이드 수준이 다르며 Astra는 범용 폴백이다. 금액·토큰 비용은 미측정이다. 테스트 점수와 시간의 차이를 일반적인 모델·프롬프트 우열로 확대하지 않는다.','', '[실험 조건](PROTOCOL.md)','']
    (ROOT/'RESULTS.md').write_text('\n'.join(lines));(ROOT/'comparisons.json').write_text(json.dumps(comparisons,indent=2))
    print(json.dumps(rows,ensure_ascii=False))

if __name__=='__main__': main()
