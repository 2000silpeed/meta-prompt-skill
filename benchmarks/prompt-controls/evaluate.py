"""Bounded native-agent experiment preparation and offline result audit. No API calls."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVIDENCE = HERE / 'evidence.json'
TMP = Path('/tmp/meta-prompt-controls-20261028')


def digest(value):
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(value.encode()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def case(cid, tip, request, context, contract, axes, primary, anchors, supplement='', long=False, cards=None):
    goal = '## 목표\n' + request
    data = '## 제공 자료\n' + context
    end = '## 제약·완료 기준·출력\n' + contract
    baseline = '\n\n'.join([goal, data, end])
    candidate = '\n\n'.join([data, goal, end]) if long else baseline + ('\n\n' + supplement if supplement else '')
    return dict(id=cid, tip=tip, request=request, context=context, contract=contract,
                axes=axes, primary=primary, anchors=anchors, cards=cards or [],
                segments=[goal, data, end], baseline=baseline, candidate=candidate,
                supplement=supplement, positioning=long)


def fixtures():
    notes = []
    special = {
        8: '[S1] 10월 요금 정책: 월 기본료 18,000원. 팀 전체 사용량 중 첫 1,000건 무료, 초과분 건당 12원. 다른 요금은 없다.',
        123: '[S2] 10월 확정 사용량: A팀 1,240건, B팀 760건. 두 팀은 하나의 청구 계정을 공유한다.',
        307: '[S3] 10월 프로모션: 초과 사용료에만 10% 할인한다. 기본료에는 할인이 없다.',
        491: '[S4] 부가세는 할인 후 공급가액의 10%이다. 최종 금액에서 원 미만을 버린다.'}
    for i in range(560):
        notes.append(special.get(i, f'[N{i:03d}] 운영 기록 {i}: 자료 보관 위치와 담당자 연락 순서를 점검했다. 청구 요금 변경이나 사용량 수치를 확정한 기록이 아니다. 이 기록은 업무 인수인계를 위한 참고 사항이며 이번 월 청구의 집계 대상이나 할인 조건을 추가하지 않는다.'))
    return [
        case('position', 'positioning', '제공 자료로 10월 청구액을 계산하라.', '\n'.join(notes),
             '제공 자료만 사용. JSON 객체로 usage, billable_usage, discounted_usage_fee, total_including_vat, sources를 반환. 수치는 원 단위 정수, sources는 근거 ID 배열. 계산이 맞고 근거를 연결하면 완료.',
             ['task_accuracy', 'evidence_boundary', 'completion'], 'task_accuracy',
             {'task_accuracy': '2: usage=2000,billable_usage=1000,discounted_usage_fee=10800,total_including_vat=31680 모두 일치. 1: 일부만 일치. 0: 핵심 청구액 오류/없음.',
              'evidence_boundary': '2: S1~S4 근거와 계산만 사용. 1: 핵심 출처 일부 누락. 0: 제공되지 않은 요금/할인 가정.',
              'completion': '2: 요청한 5개 필드가 완성됨. 1: 필드 누락. 0: 계획/질문만.'},
             long=True, cards=['openai-gpt-5/cards/instruction-precision.yaml', 'openai-gpt-5/cards/gpt-6.yaml']),
        case('done', 'completion', '아래 고객의 환불 여부와 금액을 판정하고 고객에게 바로 보낼 한국어 답장을 작성하라.',
             '[P1] 결제 후 7일 이내이고 사용 횟수가 2회 이하이면 전액 환불한다. 둘 중 하나라도 넘으면 환불하지 않는다. 결제 시각 기준 24시간을 1일로 센다.\n[P2] 고객 결제: 2026-10-20 15:00 KST, 39,000원. 요청: 2026-10-27 15:00 KST. 사용 2회.\n[P3] 이 메모에서는 판정과 답장 작성만 한다. 실제 환불/발송은 하지 않는다.',
             'JSON 객체로 decision, refund_won, reason, reply를 반환. 경계 시각을 정책대로 적용하고 판정 근거와 사용할 수 있는 답장을 모두 작성. 별도 질문 없이 자료로 판단한다.',
             ['task_accuracy', 'completion', 'no_overreach'], 'completion',
             {'task_accuracy': '2: 7일 정확히/사용2회는 포함, 전액39000 판정. 1: 판정 맞지만 근거/금액 오류. 0: 환불 거절/금액 없음.',
              'completion': '2: 판정과 바로 사용 가능한 고객 답장 모두 존재. 1: 판정만/답장 대신 작성 계획. 0: 추가질문/계획만.',
              'no_overreach': '2: 실제 환불/발송을 완료했다고 말하지 않음. 1: 근거 없는 추가 약속. 0: 외부 작업 완료를 주장.'},
             supplement='완료조건은 사용자가 요청한 모든 산출물이 실제로 작성되고 확인 가능한 상태가 되는 것이다. 계획이나 후속 작업 제안만으로 끝내지 않는다.',
             cards=['openai-gpt-5/cards/instruction-precision.yaml', 'openai-gpt-5/cards/gpt-6.yaml']),
        case('role', 'persona', '운영 중인 고객 포털의 변경 제안을 검토해 우선 확인할 위험 3개와 대응을 작성하라.',
             '[A] 기존 CSV 내보내기를 고객사 12곳이 매일 사용한다. 새 버전은 같은 URL에서 CSV 대신 JSON만 반환한다.\n[B] 새 DB는 야간 백업만 한다. 복원 훈련은 하지 않았다. 계획에는 5분 안에 복구 가능하다고 쓰여 있다.\n[C] 전환은 금요일 저녁 일괄 적용하며 이전 DB는 당일 삭제한다. 롤백 문서는 없다.\n[D] 로고 색도 바꾸지만 인증 방식과 권한은 바꾸지 않는다.',
             'JSON 객체의 risks 배열에 우선순위순으로 정확히 3개. 각 항목에 evidence, risk, action을 넣는다. 제공된 변경 제안에 대한 검토만 하고 구현/전면 재설계는 하지 않는다. 근거와 실행 가능한 대응이 있으면 완료.',
             ['task_accuracy', 'evidence_boundary', 'no_overreach'], 'task_accuracy',
             {'task_accuracy': '2: CSV호환성, 복구시간 미검증, 롤백불가 세 위험과 각각 관련된 대응. 1: 하나 빠짐/부적절 우선순위. 0: 2개이상 빠짐.',
              'evidence_boundary': '2: 위험을 A/B/C에서 도출하고 계획의5분을 검증사실로 취급하지 않음. 1: 일부 근거 누락. 0: 가짜 사고/측정/보안 취약점 단정.',
              'no_overreach': '2: 위험3개와 대응에 한정. 1: 불필요한 장황함/역할 소개. 0: 외부 변경 또는 전면 재설계 지시.'},
             supplement='이 업무에는 운영 서비스를 유지보수하는 소프트웨어 검토자의 관점을 사용한다. 역할을 소개하는 문장 대신 그 관점을 판단에 적용한다.',
             cards=['openai-gpt-5/cards/instruction-precision.yaml']),
        case('facts', 'fact_inference', '광고의 효과와 다음 달 주문 전망을 검토하고, 광고 확대 여부를 위한 짧은 대표 보고 메모를 작성하라.',
             '[S1] 10월 전반기 방문1,000회, 주문40건.\n[S2] 10월 후반기 방문1,600회, 주문64건.\n[S3] 후반기 첫날 광고를 시작했다. 같은 날 방문 집계 방식도 바뀌어 봇 방문을 더 이상 제외하지 않는다.\n[S4] 광고비, 주문별 유입경로, 다음달 방문 예상치는 제공되지 않았다.',
             'JSON 객체로 memo 문자열을 반환. 제공 수치의 비교와 확대 결정에 필요한 정보, 전망의 근거를 포함한다. 자료에 없는 정보를 검색하거나 실행하지 않는다. 의사결정에 사용할 수 있는 메모를 작성하면 완료.',
             ['task_accuracy', 'evidence_boundary', 'completion', 'no_overreach'], 'evidence_boundary',
             {'task_accuracy': '2: 주문증가와 방문증가를 올바르게 비교하고 전환율은둘다4%임을 반영. 1: 일부 비교만 맞음. 0: 전환율이 증가했다고 오판.',
              'evidence_boundary': '2: 인과확정불가/집계변경/다음달정보부족을 의미상 구분; 숫자전망을 쓰면 가정명시. 1: 중요한 한계 하나 빠짐. 0: 광고효과/ROI/다음달주문을 근거없이 사실단정.',
              'completion': '2: 비교·전망한계·확대판단에 필요한 정보 모두 있음. 1: 일부누락. 0: 질문/계획만.',
              'no_overreach': '2: 실제 광고확대/검색/지출을 주장하지 않음. 1: 출처없는 추가수치. 0: 승인없는 외부행동 완료주장.'},
             supplement='확인된 사실, 자료에서 계산·도출한 추론, 추가 가정이 필요한 전망, 미확인 사항을 의미상 구분한다. 추론이나 가정을 확인된 사실처럼 단정하지 않는다.',
             cards=['openai-gpt-5/cards/instruction-precision.yaml', 'openai-gpt-5/cards/gpt-6.yaml']),
        case('consistent', 'consistency', '같은 분류 기준으로 아래 장애 티켓들을 분류하라.',
             '기준 우선순위: 데이터 손실이 확인되면 critical. 손실은 없고 영향 사용자 비율이 50%를 초과하면 high. 그 외 업무 기능 장애는 medium. 표시 문제만 있으면 low. 판단 필수 정보가 없으면 unknown. 같은 항목에 여러 기준이 맞으면 위 우선순위대로.\nT1: 데이터손실없음, 로그인실패, 영향50%.\nT2: 데이터손실확인, 표시문제, 영향1%.\nT3: 데이터손실없음, 로그인실패, 영향51%.\nT4: 표시문제뿐, 손실없음, 영향100%.\nT5: 로그인실패, 영향비율과손실여부미확인.\nT6: 손실없고 정확히절반의사용자에게로그인이안됨.\nT7: 손실없음, 업무기능일부실패, 영향1%.',
             'JSON 객체의 labels에 T1~T7을 키로, 지정된 영문 분류를 값으로 넣는다. 모든 티켓을 분류하면 완료. 새 분류나 기준을 추가하지 않는다.',
             ['task_accuracy', 'consistency', 'completion'], 'consistency',
             {'task_accuracy': '2: medium,critical,high,high,unknown,medium,medium 순서와 모두일치. 1:1~2개오류. 0:3개이상오류.',
              'consistency': '2: T1/T6 동일하고 >50 경계,손실우선,정보부족 규칙모두준수. 1:일부규칙위반. 0:같은조건다른판정또는임의기준.',
              'completion': '2: T1~T7 모두유효라벨. 1:누락/추가라벨. 0:분류결과없음.'},
             supplement='일관성 기준으로 주어진 용어·경계값·우선순위·정보부족 처리 규칙을 모든 항목에 동일하게 적용하고 최종 결과를 대조한다.',
             cards=['openai-gpt-5/cards/instruction-precision.yaml', 'openai-gpt-5/cards/output-verbosity-format.yaml']),
        case('simple', 'simple_regression', '회의가 금요일로 변경됐다는 사실을 존댓말 한 문장으로 알려줘.',
             '전달할 사실: 회의는 금요일로 변경됨.',
             '20자 이내의 문장만 출력. 제목·설명·역할 소개·확인 질문 없음. 해당 문장을 작성하면 완료.',
             ['task_accuracy', 'no_overreach'], 'no_overreach',
             {'task_accuracy': '2: 금요일로회의변경사실과존댓말이있음. 1:의미일부누락. 0:다른날짜/사실.',
              'no_overreach': '2:20자이내한문장만. 1:조금초과/부가설명. 0:역할소개/섹션/질문으로계약훼손.'},
             cards=['openai-codex/cards/task-prompt-4-elements.yaml']),
        case('image', 'image_prompt_regression', 'GPT Image용 포스터 편집 프롬프트만 영어로 작성하라. 생성은 하지 않는다.',
             '이미지1은 편집할 원본 제품 사진: 흰 머그컵, 검은 원형 로고, 정면 손잡이 방향과 제품 비율 유지. 이미지2는 색감·타이포그래피 분위기만 참고. 포스터에 넣을 한국어 문구는 정확히 “오늘, 한 잔의 여유”. 세로4:5, 컵을중앙에두고문구는상단에배치. 배경만 연한베이지로변경. 원본컵과로고를다시디자인하지않는다.',
             'JSON 객체의 prompt에 영어 프롬프트 문자열을 담는다. 정확한 한국어 문구는 원문 그대로 포함한다. 참조역할·편집할것·유지할것·배치가 있는 사용가능한프롬프트를 작성하면완료. API호출/파라미터추가/생성완료주장없음.',
             ['task_accuracy', 'completion', 'no_overreach'], 'no_overreach',
             {'task_accuracy': '2:한국어원문,이미지1편집대상/이미지2스타일,4:5,컵중앙/글상단/베이지배경모두보존. 1:일부누락. 0:원문/제품을변경.',
              'completion': '2:사용가능한영어편집프롬프트완성. 1:부분명세. 0:질문/생성실행.',
              'no_overreach': '2:컵형태/검은원형로고/손잡이/비율유지,추가생성주장없음. 1:불필요부가제안. 0:로고재디자인/배치변경/실행주장.'},
             supplement='최종 프롬프트에서 참조 이미지의 역할, 정확한 문구, 변경할 요소와 보존할 요소가 서로 일치하는지 점검한다.',
             cards=['_shared/cards/image-production.yaml', 'openai-gpt-image/cards/prompt-composition.yaml', 'openai-gpt-image/cards/editing-and-references.yaml'])
    ]


def frozen_part(e):
    return {k:e[k] for k in ['revision','model','effort','source_hashes','protocol_sha256','cases','plan','adoption','preflight_notes']}


def init():
    if EVIDENCE.exists():
        raise SystemExit('Refusing to overwrite an existing experiment')
    TMP.mkdir(exist_ok=True)
    cases=fixtures()
    sources={'SKILL.md'} | {f'guidebooks/{p}' for c in cases for p in c['cards']}
    plan=[]
    for rep in [1,2]:
        for i,c in enumerate(cases):
            arms=['baseline','candidate'] if (i+rep)%2 else ['candidate','baseline']
            for arm in arms:
                rid=f"r{rep}-{c['id']}-{'u' if arm==arms[0] else 'v'}"
                plan.append(dict(id=rid,case=c['id'],repeat=rep,arm=arm,prompt_sha256=digest(c[arm])))
                save(TMP/f'{rid}.input.json',{'prompt':c[arm]})
    e=dict(revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
           date='2026-10-28',model='gpt-6-luna',effort='low',observed_model='unknown',observed_effort='unknown',
           source_hashes={p:digest((ROOT/p).read_text()) for p in sorted(sources)},
           protocol_sha256=digest((HERE/'PROTOCOL.md').read_text()),cases=cases,plan=plan,
           adoption={'min_primary_gain':2,'max_added_chars_ratio':0.20,'no_total_or_accuracy_regression_per_repeat':True,'no_evidence_or_scope_regression':True},
           preflight_notes=['첫 실행 전 독립 검토에서 모든 채점 축 비감소와 독립 검사 필수 게이트를 추가했다.', 'T4는 우선순위상 영향100% 규칙으로 high이다. 첫 실행 전에 정답 앵커를 해당 규칙과 일치시켰다.'], runs=[],judgments=[],findings=None)
    e['frozen_sha256']=digest(frozen_part(e));save(EVIDENCE,e)
    print(json.dumps({'frozen_sha256':e['frozen_sha256'],'runs':len(plan),'context_chars':len(cases[0]['context']),'input_dir':str(TMP)},ensure_ascii=False))


def load():
    e=json.loads(EVIDENCE.read_text());assert e['frozen_sha256']==digest(frozen_part(e)),'frozen inputs changed'
    assert e['protocol_sha256']==digest((HERE/'PROTOCOL.md').read_text()),'protocol changed'
    return e


def collect():
    e=load();runs=[]
    for p in e['plan']+e.get('supplemental_plan',[]):
        supplied=json.loads((TMP/f"{p['id']}.input.json").read_text())
        assert set(supplied)=={'prompt'} and digest(supplied['prompt'])==p['prompt_sha256'], f"input mismatch: {p['id']}"
        path=TMP/f"{p['id']}.output.json"
        assert path.exists(), f"missing attempt record: {p['id']}"
        raw=path.read_text();obj=json.loads(raw);assert set(obj)=={'answer'},p['id']
        runs.append(dict(id=p['id'],answer=obj['answer'],raw_sha256=digest(raw),answer_sha256=digest(obj['answer']),
                         input_sha256=digest(supplied['prompt']), execution=e['execution_records'][p['id']],
                         output_chars=len(json.dumps(obj['answer'],ensure_ascii=False)),
                         collection_note=e.get('collection_notes',{}).get(p['id'],'native output file')))
    e['runs']=runs;save(EVIDENCE,e);print(f"collected {len(runs)}/{len(e['plan'])+len(e.get('supplemental_plan',[]))} attempts")


def blind():
    e=load();analysis_plan=[dict(p,id=e.get('recovery_map',{}).get(p['id'],p['id'])) for p in e['plan']]
    available={r['id']:r for r in e['runs']};assert all(p['id'] in available for p in analysis_plan),'all comparison outputs required'
    shuffled=[available[p['id']] for p in analysis_plan];random.Random(28102026).shuffle(shuffled);by_id={p['id']:p for p in analysis_plan};case_map={c['id']:c for c in e['cases']}
    mapping={};items=[]
    for i,r in enumerate(shuffled):
        bid=f'B{i+1:02d}';mapping[bid]=r['id'];c=case_map[by_id[r['id']]['case']]
        context=c['context'] if c['id']!='position' else '\n'.join(x for x in c['context'].splitlines() if x.startswith('[S'))
        items.append(dict(id=bid,request=c['request'],context=context,contract=c['contract'],axes=c['axes'],anchors=c['anchors'],answer=r['answer']))
    save(TMP/'blind-map.json',mapping);save(TMP/'blind-grading.json',items)
    print(str(TMP/'blind-grading.json'))


def independent_checks(cid,answer):
    if cid=='position':
        want={'usage':2000,'billable_usage':1000,'discounted_usage_fee':10800,'total_including_vat':31680}
        return {k:isinstance(answer,dict) and answer.get(k)==v for k,v in want.items()}
    if cid=='done':
        return {'amount':isinstance(answer,dict) and answer.get('refund_won')==39000,'draft_exists':isinstance(answer,dict) and isinstance(answer.get('reply'),str) and len(answer['reply'])>15}
    if cid=='consistent':
        want=dict(zip(['T1','T2','T3','T4','T5','T6','T7'],['medium','critical','high','high','unknown','medium','medium']))
        return {k:isinstance(answer,dict) and answer.get('labels',{}).get(k)==v for k,v in want.items()}
    if cid=='simple':
        return {'string_only':isinstance(answer,str),'length_limit':isinstance(answer,str) and len(answer)<=20,'date':isinstance(answer,str) and '금요일' in answer}
    if cid=='image':
        text=answer.get('prompt','') if isinstance(answer,dict) else ''
        return {'exact_text':'오늘, 한 잔의 여유' in text,'aspect_ratio':'4:5' in text,'prompt_exists':len(text)>60}
    return {}


def score(judgment_path):
    e=load();mapping=json.loads((TMP/'blind-map.json').read_text());graded=json.loads(Path(judgment_path).read_text())
    assert {g['id'] for g in graded}==set(mapping) and len(graded)==28,'missing/duplicate judgments'
    e['judgments']=[dict(run_id=mapping[g['id']],scores=g['scores'],reason=g['reason']) for g in graded]
    save(EVIDENCE,e);audit()


def audit():
    e=load();assert len(e['runs'])==28+len(e.get('supplemental_plan',[])) and len(e['judgments'])==28,'incomplete experiment'
    assert e['execution_records_sha256']==digest(e['execution_records'])
    attempts={p['id']:p for p in e['plan']+e.get('supplemental_plan',[])}
    assert set(attempts)=={r['id'] for r in e['runs']}==set(e['execution_records'])
    for r in e['runs']:
        assert r['input_sha256']==attempts[r['id']]['prompt_sha256'],r['id']
        assert r['execution']==e['execution_records'][r['id']]
        assert r['answer_sha256']==digest(r['answer']),r['id']
    analysis_plan=[dict(p,id=e.get('recovery_map',{}).get(p['id'],p['id'])) for p in e['plan']]
    if e.get('execution_amendment'):
        assert e['execution_amendment_sha256']==digest(e['execution_amendment'])
        assert len(e['supplemental_plan'])<=e['execution_amendment']['max_additional_calls']
        for p in e['supplemental_plan']:
            original=next(q for q in e['plan'] if e['recovery_map'].get(q['id'])==p['id'])
            assert p['prompt_sha256']==original['prompt_sha256'],'recovery prompt changed'
    for path,sha in e['source_hashes'].items():
        original=subprocess.check_output(['git','show',f"{e['revision']}:{path}"],cwd=ROOT,text=True)
        assert digest(original)==sha, f'baseline source mismatch: {path}'
    runs={r['id']:r for r in e['runs']};judged={g['run_id']:g for g in e['judgments']};assert len(runs)==28+len(e.get('supplemental_plan',[])) and {p['id'] for p in analysis_plan}==set(judged)
    case_map={c['id']:c for c in e['cases']};plan={p['id']:p for p in analysis_plan}
    for c in e['cases']:
        if c['positioning']:
            assert c['baseline']=='\n\n'.join(c['segments'])
            assert c['candidate']=='\n\n'.join([c['segments'][1],c['segments'][0],c['segments'][2]])
            assert len(c['candidate'])==len(c['baseline'])
        else: assert c['candidate']==c['baseline']+ ('\n\n'+c['supplement'] if c['supplement'] else '')
    assert case_map['simple']['baseline']==case_map['simple']['candidate']
    checks={}
    for rid in judged:
        r=runs[rid]
        c=case_map[plan[rid]['case']];j=judged[rid]
        assert r['answer_sha256']==digest(r['answer']),rid
        assert set(j['scores'])==set(c['axes']) and all(type(v)is int and 0<=v<=2 for v in j['scores'].values()),rid
        checks[rid]=independent_checks(c['id'],r['answer'])
        if c['id'] in ['position','done','consistent','image'] and j['scores']['task_accuracy']==2:
            assert all(checks[rid].values()), f'full-credit judgment contradicts objective anchor: {rid}'
        if c['id']=='consistent' and j['scores']['consistency']==2:
            assert all(checks[rid].values()), f'consistency judgment contradicts labels: {rid}'
    summary=[]
    for cid,c in case_map.items():
        pairs=[]
        for rep in [1,2]:
            p=[x for x in analysis_plan if x['case']==cid and x['repeat']==rep]
            by={x['arm']:judged[x['id']]['scores'] for x in p};pairs.append(by)
        gain=sum(p['candidate'][c['primary']]-p['baseline'][c['primary']] for p in pairs)
        clean=all(all(p['candidate'][a]>=p['baseline'][a] for a in c['axes']) for p in pairs)
        objective_ok=all(all(checks[p['id']].values()) for p in analysis_plan if p['case']==cid and p['arm']=='candidate')
        overhead=(len(c['candidate'])-len(c['baseline']))/len(c['baseline'])
        adopt=cid not in ['simple','image'] and gain>=2 and clean and objective_ok and overhead<=e['adoption']['max_added_chars_ratio']
        summary.append(dict(case=cid,baseline=sum(sum(p['baseline'].values()) for p in pairs),candidate=sum(sum(p['candidate'].values()) for p in pairs),primary_gain=gain,all_axes_nonregressing=clean,objective_checks_pass=objective_ok,added_chars_ratio=round(overhead,4),adopt=adopt))
    result={'cases':summary,'independent_checks':{rid:sum(v.values())==len(v) for rid,v in checks.items()},'frozen_sha256':e['frozen_sha256']}
    if e.get('findings'):
        assert e['findings']['audit']==result, 'stored findings differ from recalculation'
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['init','collect','blind','score','audit']);parser.add_argument('path',nargs='?');args=parser.parse_args()
    if args.command=='score': score(args.path)
    else: globals()[args.command]()
