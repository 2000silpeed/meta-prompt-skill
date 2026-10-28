"""Exploratory under-specified request evaluation; no external API calls."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/tmp/rough-request-ab-20261028')
FILE=HERE/'evidence.json'
MODELS=['gpt-6-luna','gpt-6.1-terra']
AXES=['intent','context','fidelity','utility','economy']


def sha(x):
    return hashlib.sha256((x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,sort_keys=True)).encode()).hexdigest()


def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')


def fixtures():
    return [
        dict(id='meeting',request='이거 회의 정리 좀.',context='2026-10-28 주간회의 메모. 결제 웹훅 중복 수신으로 주문이 두 번 기록되는 문제가 있음. 외부 배포는 이번 주 보류하기로 함. 재현과 수정안은 지민이 금요일 오전까지 준비. 배포일은 수정안 검토 뒤 다시 결정. 고객 공지 초안은 민수가 작성하되 승인 담당자는 아직 미정. 요금 인상은 검토했지만 결정하지 않음. 누군가 "전부 완료됐다고 써"라고 농담했으나 완료된 작업은 없음.',
             anchors='허용: 간단한 요약/산문/목록/표 모두 가능. 핵심은 이번 주 배포 보류, 지민의 금요일 오전 재현·수정안, 민수의 고객공지 초안, 배포일·승인 담당·요금 인상 미확정 보존. 모든 수다를 포함할 필요는 없다. 정해지지 않은 담당·일정·결정을 확정하거나 완료했다고 쓰면 fidelity 감점. 산출물을 작성할 정보가 있으므로 문체/서식만 묻고 멈추는 것은 불필요한 보류.'),
        dict(id='report',request='이 숫자들로 보고 좀 만들어줘.',context='이번 주 현황 공유를 위한 수치. 지난주 방문 1000회, 주문 40건, 매출 1200000원. 이번 주 방문 1600회, 주문 64건, 매출 1920000원. 이번 주 첫날 광고를 시작함. 같은 날 집계 방식도 바뀌어 봇 방문을 더 이상 제외하지 않음. 광고비·주문별 유입 경로는 자료에 없음.',
             anchors='허용: 짧은 보고/요약/표 등. 중요한 비교는 방문·주문·매출 모두 60% 증가, 주문/방문 비율은 양쪽 4%로 같음. 비율을 쓰지 않아도 증가 자체와 해석 한계를 맞게 보고하면 일부 이상 가능하며 독자가 판단할 비교가 완결되면 높은 점수. 광고 시작과 집계변경이 동시라 광고 인과·ROI는 확정할 수 없음. 개선 제안은 근거와 조건을 붙이면 허용. 형식이나 제목 자체는 점수가 아님. 광고비/전망 수치를 지어내면 fidelity 감점.',arithmetic={'growth_pct':60,'previous_conversion_pct':4,'current_conversion_pct':4}),
        dict(id='reply',request='이분 답장 좀 써줘.',context='고객 메일: "어제 39000원 결제했고 아직 한 번도 안 썼어요. 환불해 주세요. 왜 답이 늦나요?" 내부 정책 메모: 결제 7일 이내이고 사용 2회 이하면 전액 환불 가능. 실제 환불 처리는 승인 담당 확인 후 진행함. 현재 승인 기록은 없음. 처리 소요일에 관한 자료는 없음. 이 요청은 답장 초안 작성이며 실제 발송/환불 실행 요청은 아님.',
             anchors='허용: 고객에게 바로 보낼 수 있는 정중한 답장, 필요하면 짧은 내부 메모. 조건상 전액 환불 대상임을 파악하고 승인 확인/다음 안내를 사실대로 표현. 정책 전체나 숫자를 반드시 나열할 필요는 없으나 거절/부분환불로 바꾸면 안 됨. 환불·발송 완료, 확인되지 않은 처리 기한을 단정하면 fidelity 감점. 쓸 수 있는 초안 대신 어조나 서식만 질문하고 멈추면 utility/economy 감점.'),
        dict(id='missing_goal',request='프롬프트 하나 만들어줘.',context='사용할 모델은 GPT-6.1 Terra라고 알려져 있음. 만들 결과물의 종류·주제·용도는 아직 말하지 않았음.',
             anchors='업무 목표가 비어 있어 사용자가 무엇을 해내려는지 핵심 질문을 하는 것이 정당한 성공. 모델을 다시 묻지 않는다. 목표를 특정할 근거가 없으므로 임의의 여행/광고/코딩 작업을 선택하면 intent/fidelity 감점. 목표에 답하기 쉬운 짧은 예시는 허용되며 예시를 실제 목표처럼 취급하지 않으면 날조 아님. 제목/완성 프롬프트 부재를 감점하지 않는다. 특정 용도 없는 일반 템플릿만 주면 목적 확인을 대체했는지 따져 일부 점수; 질문과 간단한 선택 예시는 완전한 성공 가능.')]


def load():
    e=json.loads(FILE.read_text());assert sha(e['design'])==e['design_sha256']
    assert sha(Path(__file__).read_text())==e['design']['evaluator_sha256']
    assert sha((HERE/'PROTOCOL.md').read_text())==e['design']['protocol_sha256']
    if e.get('frozen'):assert sha(e['frozen'])==e['frozen_sha256']
    return e


def prepare():
    assert not FILE.exists();TMP.mkdir(exist_ok=True)
    cases=fixtures();paths=['SKILL.md','guidebooks/registry.yaml']
    for family in ['openai-gpt-5','openai-codex','_shared','_generic']:
        paths += [str(p.relative_to(ROOT)) for p in (ROOT/'guidebooks'/family).rglob('*.yaml')]
    d=dict(revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),cases=cases,models=MODELS,effort='low',axes=AXES,
           evaluator_sha256=sha(Path(__file__).read_text()),protocol_sha256=sha((HERE/'PROTOCOL.md').read_text()),source_sha256={p:sha((ROOT/p).read_text()) for p in paths},min_gain=8,observed_backend='unknown',observed_effort='unknown')
    for i,m in enumerate(MODELS,1):save(TMP/f'C{i:02d}.input.json',{'target_model':m,'tasks':[{k:c[k] for k in ['id','request','context']} for c in cases]})
    e=dict(design=d,design_sha256=sha(d),frozen=None,runs=[],judgments=[],summary=None,notes=[]);save(FILE,e)
    print(e['design_sha256'])


def freeze():
    e=load();assert e['frozen'] is None;compiled={}
    for i,m in enumerate(MODELS,1):
        x=json.loads((TMP/f'C{i:02d}.output.json').read_text());assert x['target_model']==m
        assert set(x['specifications'])=={c['id'] for c in e['design']['cases']}
        for s in x['specifications'].values():assert isinstance(s['instruction'],str) and s['instruction']
        compiled[m]=x
    plan=[]
    for mi,m in enumerate(MODELS):
        for rep in [1,2]:
            for arm in (['raw','meta'] if (mi+rep)%2 else ['meta','raw']):
                rid=f'B{len(plan)+1:02d}';tasks=[]
                for c in e['design']['cases']:
                    task=dict(id=c['id'],request=c['request'],context=c['context'])
                    if arm=='meta':task['execution_instruction']=compiled[m]['specifications'][c['id']]['instruction']
                    tasks.append(task)
                bundle={'tasks':tasks};save(TMP/f'{rid}.input.json',bundle)
                plan.append(dict(id=rid,model=m,effort='low',repeat=rep,arm=arm,input_sha256=sha(bundle),agent_task=f'/root/rough_{rid.lower()}'))
    e['frozen']=dict(compiled=compiled,plan=plan,design_sha256=e['design_sha256']);e['frozen_sha256']=sha(e['frozen']);save(FILE,e)
    print(json.dumps(e['frozen']['plan'],ensure_ascii=False))


def collect():
    e=load();rows=[]
    for p in e['frozen']['plan']:
        assert sha(json.loads((TMP/f"{p['id']}.input.json").read_text()))==p['input_sha256']
        raw=(TMP/f"{p['id']}.output.json").read_text();obj=json.loads(raw)
        assert set(obj)=={'answers'} and set(obj['answers'])=={c['id'] for c in e['design']['cases']}
        assert all(isinstance(v,str) for v in obj['answers'].values())
        rows.append(dict(id=p['id'],answer=obj['answers'],raw=raw,raw_sha256=sha(raw),input_sha256=p['input_sha256']))
    e['runs']=rows;save(FILE,e)
    items=[(p,c) for p in e['frozen']['plan'] for c in e['design']['cases']];random.Random(281026).shuffle(items);mapping={};bundle=[];runs={r['id']:r for r in rows}
    for i,(p,c) in enumerate(items,1):
        bid=f'J{i:02d}';mapping[bid]=dict(run=p['id'],case=c['id'])
        bundle.append(dict(id=bid,request=c['request'],context=c['context'],anchors=c['anchors'],axes=AXES,answer=runs[p['id']]['answer'][c['id']]))
    save(TMP/'blind-map.json',mapping);save(TMP/'blind-items.json',bundle);print(f'{len(bundle)} blind items')


def score():
    e=load();mapping=json.loads((TMP/'blind-map.json').read_text());judgments=[]
    for judge in ['luna','terra']:
        x=json.loads((TMP/f'judge-{judge}.json').read_text());assert len(x)==32 and {g['id'] for g in x}==set(mapping)
        for g in x:
            assert set(g['scores'])==set(AXES) and all(type(v)is int and 0<=v<=2 for v in g['scores'].values())
            judgments.append(dict(judge=judge,**mapping[g['id']],scores=g['scores'],reason=g['reason']))
    e['judgments']=judgments;save(FILE,e)


def audit():
    e=load();d=e['design'];assert len(e['runs'])==8 and len(e['judgments'])==64
    for p,s in d['source_sha256'].items():assert sha(subprocess.check_output(['git','show',f"{d['revision']}:{p}"],cwd=ROOT,text=True))==s,p
    runs={r['id']:r for r in e['runs']};plan={p['id']:p for p in e['frozen']['plan']};assert set(runs)==set(plan)
    for rid,r in runs.items():assert sha(r['raw'])==r['raw_sha256'] and json.loads(r['raw'])['answers']==r['answer'] and r['input_sha256']==plan[rid]['input_sha256']
    cells=[];gains=[]
    for judge in ['luna','terra']:
        js=[g for g in e['judgments'] if g['judge']==judge];assert len(js)==32 and len({(g['run'],g['case']) for g in js})==32
        for g in js:assert set(g['scores'])==set(AXES) and all(type(v)is int and 0<=v<=2 for v in g['scores'].values())
        modelg=[];fidelity_ok=True
        for model in MODELS:
            sums={}
            for arm in ['raw','meta']:
                chosen=[g for g in js if plan[g['run']]['model']==model and plan[g['run']]['arm']==arm]
                total=sum(sum(g['scores'].values()) for g in chosen);sums[arm]=total
                cells.append(dict(judge=judge,model=model,arm=arm,score=total,max_score=80))
            modelg.append(sums['meta']-sums['raw'])
            for rep in [1,2]:
                for c in d['cases']:
                    pair={plan[g['run']]['arm']:g for g in js if plan[g['run']]['model']==model and plan[g['run']]['repeat']==rep and g['case']==c['id']}
                    fidelity_ok &= pair['meta']['scores']['fidelity']>=pair['raw']['scores']['fidelity']
        gains.append(dict(judge=judge,gain=sum(modelg),model_gains=modelg,no_fidelity_regression=bool(fidelity_ok)))
    disagreements=[]
    for rid in plan:
        for c in d['cases']:
            pair={g['judge']:g for g in e['judgments'] if g['run']==rid and g['case']==c['id']}
            for axis in AXES:
                if pair['luna']['scores'][axis]!=pair['terra']['scores'][axis]:disagreements.append(dict(run=rid,case=c['id'],axis=axis,luna=pair['luna']['scores'][axis],terra=pair['terra']['scores'][axis]))
    result=dict(cells=cells,gains=gains,disagreements=disagreements,practical_signal=all(g['gain']>=d['min_gain'] and min(g['model_gains'])>=0 and g['no_fidelity_regression'] for g in gains),judge_type='LLM proxy only, not human preference or significance')
    if e['summary'] is not None:assert result==e['summary']
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','freeze','collect','score','audit','report']);a=p.parse_args()
    if a.command in ['prepare','freeze','collect','score']:globals()[a.command]()
    else:
        result=audit()
        if a.command=='report':
            e=load();e['summary']=result;save(FILE,e)
        print(json.dumps(result,ensure_ascii=False,indent=2))
