# v0.1 검증 기록

## 후속 실행 3: 모델별 일반 지시와 메타 프롬프트

Astra·Sol·Luna × 일반/메타 × 두 반복, 총 12회를 단독 에이전트로 실행했다.
같은 상세 명세·시작 코드와 medium 추론 설정, 사전에 고정한 평가 41개를 사용했다.
Astra·Sol은 양 조건 모두 40/41을 두 번 기록했고, Luna는 일반 37·39/41에서
메타 40·40/41로 달라졌다. 12회 모두 큰 정수 주문 사례는 실패했다.
모델별 시간·가이드북 적용 범위·한계는 [관측 보고서](../benchmarks/meta-prompt-ab/FINDINGS.md),
개별 결과는 [결과표](../benchmarks/meta-prompt-ab/RESULTS.md)에 있다.
입력·산출물 해시, 조건별 반복 수, 실행 구간, 보호 파일과 지시문 일관성 검사도 통과했다.

## 후속 실행 2: 다중 모듈 코드 회귀 수정

5개 Python 모듈의 실제 수정 과제에서 세 구성을 각각 두 번 실행했다. 수정 전 20/40이던
고정 평가 테스트는 여섯 최종본 모두 40/40을 통과했다. 별도 검토자·통합자가 찾아낸 큰 정수
직렬화 결함은 고정 평가에 소급 추가하지 않고 별도 재현 검사로 확인했다.
[측정과 추가 발견](../benchmarks/team-composer-regression/FINDINGS.md),
[고정 평가 결과](../benchmarks/team-composer-regression/RESULTS.md)를 참고한다.

## 후속 실행: 팀 구조 비교 파일럿

초기 구조 검증 이후, 네이티브 에이전트로 실제 단일·병렬 분담·제작 후 검토를 수행했다.
6개 합성 케이스 × 세 구성 × 두 반복에서 36개 케이스 판정과 324개 자동 검사가 통과했다.
별도 서비스 호출이나 전체 자동 선택 동작의 검증은 포함하지 않는다.
[측정 결과](../benchmarks/team-composer-pilot/RESULTS.md)와
[해석·한계](../benchmarks/team-composer-pilot/FINDINGS.md)를 참고한다.

아래 기록은 이 실행 이전에 수행한 초기 구조·계획 점검이다.

검증일: 2026-09-05. 범위는 스킬 구조와 계획 산출물의 로컬 점검이다.

## 수행 결과

- skill-creator의 `quick_validate.py`: 새 agent-team-composer와 기존 meta-prompt 모두 통과.
- 새 스킬의 YAML과 예제 YAML 파싱 통과.
- 스킬·README의 로컬 링크 존재 확인, 예제에 적용한 가이드북 카드 경로 확인.
- 예제의 작업 ID 유일성, 선행 작업 존재, 의존성 순환 없음 확인.
- 예제의 외부 실행 횟수 0, 실행 ID 없음, 사용자 지정 서비스 유지 확인.
- `git diff --check` 통과.

## 계획 예제 검토

[manual-handoff.yaml](../examples/agent-team/manual-handoff.yaml)은 다음 **가상 환경**에 대해 작성한 계획 산출물이다.

요청: “근무 방식 설문을 Claude가 정리하고 Gemini가 사내 공지 초안을 작성하는 팀과 프롬프트만 만들어줘.”
환경: 두 서비스 모두 연결되지 않았다고 가정. 입력 설문 수치는 예제에 포함.

관측한 결과:

- 지정한 두 서비스를 유지하고 수동 전달 경로를 기록했다.
- Claude 역할은 기존 explicit-instructions 카드, Gemini 역할은 PCTF와 런타임 카드를 읽고 컴파일했다.
- 확인하지 않은 실제 모델 버전·가격·API 설정은 지정하지 않았다.
- 첫 작업은 `manual-handoff`, 선행 결과가 없는 후속 작업은 `blocked`다.
- Gemini 프롬프트는 선행 분석 본문을 받아야 실행할 수 있으며, 없는 분석을 만들어 진행하지 않게 했다.
- 역할의 출력 소유권과 최종 통합 확인 조건을 명시했다.

이는 작성자가 수행한 계획 수준의 점검이다. 독립 평가 에이전트의 행동 테스트나 실제 Claude·Gemini 호출 결과가 아니다.

## 검증하지 않은 범위

여러 외부 서비스의 실제 인증·호출·비용, 실제 서브에이전트의 병렬 실행과 실패 복구,
팀 구성의 품질·비용 우위는 검증하지 않았다. 전체 행동 시나리오는
[evaluation.md](../skills/agent-team-composer/references/evaluation.md)에 정의했으며 모두 실행한 것으로 간주하지 않는다.
