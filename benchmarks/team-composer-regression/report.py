#!/usr/bin/env python3
import json
import statistics
from grade import ROOT, frozen_check, digest_tree


def main():
    frozen_check(); rows=[]
    for path in sorted((ROOT/'runs').glob('*/score.json')):
        r=json.loads(path.read_text()); run=path.parent
        if r['source_sha256']!=digest_tree(run/'work/shop'): raise ValueError('Candidate changed: '+run.name)
        config=run.name.split('-',1)[1]
        stage='draft' if config=='review' else 'pre-integration' if config=='parallel' else None
        before=json.loads((run/(stage+'-score.json')).read_text())['passed'] if stage else None
        rows.append({'run':run.name,'config':config,'passed':r['passed'],'total':r['total'],
                     'seconds':r['measurement']['artifact_seconds'],'agents':len(r['agents']),
                     'public_passed':r['public_tests_passed'],'before':before,
                     'failed_tests':[d['id'] for d in r['details'] if d['status']!='passed']})
    (ROOT/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    lines=['# 코드 회귀 수정 비교 결과','',
           '같은 시작 코드·공개 계약·고정 평가 테스트 40개. 수정 전 기준은 20/40이다.','',
           '| 실행 | 평가 테스트 | 공개·자체 테스트 | 중간→최종 | 시간 | 호출 수 |',
           '|---|---:|---|---|---:|---:|']
    for r in rows:
        stage=f"{r['before']} → {r['passed']}" if r['before'] is not None else '—'
        lines.append(f"| {r['run']} | {r['passed']}/{r['total']} | {'통과' if r['public_passed'] else '실패'} | {stage} | {r['seconds']:.1f}초 | {r['agents']} |")
    lines+=['','## 구성별 관측','','| 구성 | 실행 수 | 평가 통과 합계 | 시간 평균 (최소–최대) | 호출 합계 |','|---|---:|---:|---:|---:|']
    for config in ['single','parallel','review']:
        group=[r for r in rows if r['config']==config]
        if not group: continue
        times=[r['seconds'] for r in group]
        lines.append(f"| {config} | {len(group)} | {sum(r['passed'] for r in group)}/{sum(r['total'] for r in group)} | {statistics.mean(times):.1f}초 ({min(times):.1f}–{max(times):.1f}) | {sum(r['agents'] for r in group)} |")
    lines+=['','## 한계','','같은 합성 코드 과제의 구성당 2회 반복이다. 서비스별 성능·실제 금액·토큰 비용이나 통계적 우열을 평가하지 않았다. 시간에는 인계와 호출 준비가 포함된다. 평가 테스트가 모든 회귀를 포괄하는 것은 아니다.','', '[실험 조건](PROTOCOL.md)','']
    (ROOT/'RESULTS.md').write_text('\n'.join(lines))
    print(json.dumps(rows,ensure_ascii=False))

if __name__=='__main__': main()
