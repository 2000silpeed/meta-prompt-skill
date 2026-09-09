# 서비스 조합 벤치마크 — 고정 과제 v1

Goal: cases.json의 각 워크플로에 대해 아래 규칙을 모두 지키는 최적 서비스 배정 계획을 JSON으로 생성한다. 실제 서비스 실행은 하지 않는다.
Context: 모든 서비스·가격은 이 테스트를 위해 만든 합성 데이터다. 현재 계정이나 인터넷의 서비스 정보를 사용하지 않는다. 동일 케이스 안의 모든 작업을 수행해야 하며, 작업과 서비스 ID를 그대로 쓴다.
Constraints:
1. service.available=true이고 작업 capability가 service.offers에 있어야 한다. 작업 local_only=true이면 service.local=true여야 한다. fixed_service가 있으면 반드시 그 서비스만 사용한다.
2. offers[capability].cost=null은 비용 미확인이다. 모든 케이스는 엄격한 수치 budget을 가지므로 미확인 비용의 서비스는 배정할 수 없다. service가 unavailable이면 가격이 싸더라도 사용할 수 없다.
3. total_cost = 모든 작업의 offer.cost 합 + (사용한 서로 다른 서비스 개수 - 1)*case.setup_cost + 서비스가 다른 모든 직접 의존 간선마다 case.transfer_cost. 비용 단위는 가상의 unit이다. 총비용이 budget 이하여야 한다.
4. 작업 목록은 DAG다. duration은 선택된 offer.duration이다. latency는 각 작업의 end=duration+max(선행 end들, 없으면 0)로 계산한 모든 end의 최댓값이다. 이 가상 계산에는 자원 경합/동시실행 한도가 없다. latency는 실제 에이전트 소요 시간이 아니다.
5. objective=cost이면 (total_cost, latency, task ID 오름차순 서비스 ID 목록) 순으로 사전식 최소화한다. objective=speed이면 (latency,total_cost,같은 서비스 목록) 순으로 최소화한다. 최적 배정은 전역적으로 구한다. 개별 작업의 최저가만 고르는 것과 다를 수 있다.
6. 유효한 전체 배정이 없으면 status=blocked, assignments=[], total_cost=null, latency=null, waves=[], blockers에 아래 해당 코드를 각각 한 번 넣는다.
   - required_service_unavailable: fixed_service가 available=false인 작업 존재.
   - no_eligible_service: 고정 서비스 unavailable 이외의 이유로 후보가 0인 작업 존재.
   - budget_exceeded: 모든 작업에 후보가 있고 전체 배정은 가능하지만 예산 이내 배정 없음.
   앞 두 코드 중 하나라도 있으면 budget_exceeded는 넣지 않는다. blocks 순서는 무관하다.
7. 유효한 배정이면 status=planned, blockers=[]. assignments는 task ID 오름차순. 각 항목은 task_id, service_id, depends_on(원본 그대로), guidebook, prompt_contract를 가진다. guidebook은 서비스 데이터의 guidebook 값, null이면 "_generic". prompt_contract는 아래 네 키를 가진 객체다.
   goal: 작업 capability와 해당 작업을 완료할 목적을 명시한 짧은 한국어 문장
   context: 해당 작업 ID와 선행 작업 ID들을 포함한 문자열
   constraints: local_only, fixed_service, budget 제약을 설명한 문자열 (해당 없음을 명시 가능)
   done_when: 확인 가능한 결과 조건을 명시한 문자열
8. waves는 선행 관계의 층이다. 모든 선행 작업이 이전 wave에 있어야 하며, 매 wave마다 가능한 모든 작업을 task ID 오름차순으로 포함한다. 서비스가 같은 작업도 이 테스트에서는 같은 wave에 들어갈 수 있다. 이는 실제 네이티브 에이전트 배정 계획이 아니다.
Done when: 지정한 모든 케이스에 대해 해석 가능한 JSON 파일을 작성하고 자신의 결과를 위 규칙으로 확인했다. 최종 파일에는 설명이나 Markdown fence를 넣지 않는다.

출력:
{"cases":[{"case_id":"...","status":"planned|blocked","assignments":[],"total_cost":0,"latency":0,"waves":[],"blockers":[]}]}

공통 실행 범위: 현재 받은 input 파일과 자신에게 지정된 산출물만 읽고 쓴다. 다른 실행의 결과, evaluator, 정답 파일을 읽지 않는다. 외부 네트워크·추가 에이전트 호출은 하지 않는다. 필요하면 Python 표준 라이브러리로 계산/자기 검증할 수 있다. 1회 작성·자기 검증 후 완료하며 채점 피드백은 받지 않는다.
