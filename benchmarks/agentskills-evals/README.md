# agentskills.io 기준 스킬 평가

2026-11-05. [agentskills.io](https://agentskills.io/skill-creation/evaluating-skills)의
세 가이드(출력 품질 평가, best practices, description 최적화)를 그대로 적용한 1차 결과다.
평가 대상은 커밋 `5d6936b`의 `meta-prompt` 스킬이다.
실행과 판정에는 모두 Claude Code 비대화형 모드(`claude -p`)를 썼고, run마다 새 컨텍스트에서 1회씩 돌렸다.

| 파일 | 역할 |
|---|---|
| `evals/evals.json` | 테스트 케이스 5개와 assertion (가이드 형식) |
| `evals/trigger/{train,validation,holdout}_queries.json` | 트리거 eval 쿼리 12/8/10개. 분할은 고정 시드로 한 번만 정했다 |
| `run_quality.py` | with_skill / without_skill 실행. 산출물·transcript·timing 저장 |
| `grade.py` | `grade`(assertion 채점) · `compare`(블라인드 A/B) · `aggregate`(benchmark.json) |
| `run_trigger.py` | 쿼리당 3회 실행해 trigger rate를 계산한다(임계값 0.5) |
| `iteration-1/` | 가이드의 workspace 구조. eval별 `with_skill/`, `without_skill/`, `benchmark.json` |
| `description/` | description 트리거 결과 |

재현 방법:

```bash
python3 benchmarks/agentskills-evals/run_quality.py benchmarks/agentskills-evals/iteration-1
python3 benchmarks/agentskills-evals/grade.py grade benchmarks/agentskills-evals/iteration-1
python3 benchmarks/agentskills-evals/grade.py compare benchmarks/agentskills-evals/iteration-1
python3 benchmarks/agentskills-evals/grade.py aggregate benchmarks/agentskills-evals/iteration-1
python3 benchmarks/agentskills-evals/run_trigger.py evals/trigger/train_queries.json out.json
```

## 1. 출력 품질 (with_skill vs without_skill)

| eval | assertion with | assertion without | 블라인드 판정 (with : without) | 스킬 발동 |
|---|---|---|---|---|
| claude-long-refactor | 7/7 | 4/7 | 7 : **8** | O |
| glm-stale-guidebook | 5/5 | 3/5 | 6 : **8** | O |
| nanobanana-background-edit | 5/5 | 4/5 | 7 : **8** | O |
| unregistered-model-fallback | 5/5 | 3/5 | 7 : **9** | O |
| vague-no-target | 4/4 | 4/4 | 7 : **8** | **X** |

`benchmark.json`의 평균은 다음과 같다. pass rate는 with 1.00, without 0.71(Δ +0.29)이다.
시간은 36.3초와 28.7초다(Δ +7.7초).
토큰은 22.5만과 4.8만이다(캐시 읽기 포함, Δ +17.7만).
스킬이 실제로 발동한 4건만 보면 비용은 평균 $0.31과 $0.14로 약 2.2배다.

### 해석

- **assertion 우세는 대부분 스킬 고유 기능을 반영한다.** baseline이 실패한 assertion은 거의 다 다음 세 종류였다.
  실행 설정 권고(effort·reasoning·endpoint), 가이드 검증일·신선도 고지, 원 요청 진단 해설이다.
  baseline도 통과한 핵심 품질 항목에서는 차이가 없었다. 예를 들면 테스트 기준선, 멈춤 조건, 라벨 원문 보존, JSON 스키마가 그렇다.
  Mistral 폴백 고지는 baseline이 놓쳤고 스킬이 정확히 처리했다. 이것은 실질적인 가치다.
- **블라인드 판정은 5건 모두 baseline을 선호했다.** 판정자가 든 공통 이유는 다음과 같다.
  1. 사용자가 모르는 내부 용어가 응답에 그대로 노출된다.
     예: "가이드북", "`/meta-prompt refresh glm`", "63일 전 검증", "`/meta-prompt add mistral`".
  2. "프롬프트만 줘"라고 했는데 해설을 덧붙였다(nanobanana).
  3. 실행 설정 주장에 출처 표시가 없어서 근거 없는 단정처럼 읽힌다.
     예: "Opus 5.5 기본 effort는 medium", "Coding Plan 구독 이력 시 엔드포인트 제한".
     이 내용은 실제로는 가이드북 카드에서 왔지만 응답만 봐서는 알 수 없다.
  4. 진단·적용 규칙 섹션이 장황하다. 반면 baseline은 user 템플릿, 호출 코드, 경계값 목록처럼 바로 쓸 수 있는 산출물을 더 넣었다.
- 판정자 1명이 표본 5개를 보고 1회 판단한 결과다. 통계적 결론은 아니며, 개선 방향을 찾기 위한 신호로 본다.
- **vague-no-target에서는 스킬이 발동하지 않았다.** "프롬프트 잘 좀 써줘"는 description에 문구 그대로 들어 있는데도 그랬다.
  변환할 내용이 없으니 에이전트가 바로 되물었고, 결과는 baseline과 같다. 해롭지는 않다.
- 채점자가 assertion 자체에 남긴 피드백은 각 `grading.json`의 `assertion_feedback`에 있다.
  요약하면 1~3번 유형은 너무 쉽고, "또는" 조건은 변별력이 약하며, 사실 정확성은 응답만으로 검증할 수 없다는 지적이다.

### 다음 iteration 제안 (아직 SKILL.md에 적용하지 않음)

가이드의 "사람 리뷰 → 개선" 단계를 위해 제안만 기록한다. `iteration-1/feedback.json`에는 사람 리뷰를 적는다.

1. **사용자에게 보이는 출력에서 스킬 내부 용어를 뺀다.** 신선도·폴백 고지는 끝에 한 줄로 쓰고, "가이드북"이나 서브커맨드 이름 대신 의미를 쓴다.
   예: "이 모델의 공식 프롬프트 지침은 9월 3일 기준이라 최신 변경이 빠졌을 수 있습니다."
   서브커맨드는 사용자가 스킬 사용자일 때만 안내한다.
2. **"프롬프트만"이면 코드블록만 낸다.** 진단·적용 규칙·가정은 사용자가 원할 때만 덧붙인다. 정말 필요한 주의는 1줄까지만 쓴다.
3. **실행 설정 권고에는 출처와 기준일을 붙인다.** 예: "(공식 문서, 2026-10 확인)". 카드가 `knowledge-based`이면 권고가 아니라 확인 필요 항목으로 쓴다.
4. 위 1~3을 `## Gotchas` 섹션으로 SKILL.md에 둔다. best-practices 가이드가 권하는 방식이다.
5. assertion을 보강한다. 프롬프트 외 해설 분량, 실제 사용에 필요한 부속물(템플릿·호출 예시), 사실 주장의 출처 표기를 측정한다.
   baseline도 늘 통과하는 항목은 정리한다.

## 2. Best practices 점검

| 항목 | 상태 | 근거 |
|---|---|---|
| SKILL.md 500줄 이하 | ✅ | 150줄 |
| SKILL.md 5,000토큰 이하 | ⚠️ | 약 6,700토큰. 실측 방법: 같은 질문에 SKILL.md를 붙였을 때와 뺐을 때의 input 토큰 차이(9,510 − 2,811). 한국어 본문이라 토큰이 많이 든다 |
| progressive disclosure | ✅ | registry → index → `when` 조건에 맞는 카드만 로드. 로드 시점이 명시되어 있다 |
| 매 실행에 필요한 것만 본문에 | ⚠️ | `refresh`/`add`/`eval` 서브커맨드 절차(약 30줄)는 드물게 쓰이는데 매번 로드된다. `references/subcommands.md`로 옮기고 "서브커맨드 호출 시 읽기"로 연결하면 토큰을 아낄 수 있다 |
| defaults, not menus | ✅ | 모델 감지 사다리와 optional 슬롯 default가 있다 |
| 출력 템플릿 | ✅ | 5. 산출 템플릿. 다만 위 품질 결과를 보면 "프롬프트만" 요청에 대한 예외가 필요하다 |
| validation loop | ✅ | 카드 pitfalls 체크리스트로 최종 점검한다 |
| Gotchas 섹션 | ❌ | 없다. 위 iteration 제안 1~3이 첫 항목 후보다 |
| 이유 설명 | ◑ | 대부분 규칙형("~한다/~하지 않는다")이다. 가이드는 이유를 함께 쓰라고 권한다 |
| 실제 실행으로 다듬기 | ✅ | 기존 `benchmarks/`의 A/B·stress 실험과 이번 eval |
| name·디렉터리 일치 | ✅ | README 설치 안내가 `skills/meta-prompt`로 symlink한다 |

## 3. Description 트리거 최적화

현재 description은 558자다(한도 1,024자). 쿼리 30개를 각각 3회, 총 90회 실행했다.

| 세트 | 결과 |
|---|---|
| train (긍정 6 / 부정 6) | 12/12 |
| validation (긍정 4 / 부정 4) | 8/8 |
| holdout (최적화에 쓰지 않은 새 쿼리, 긍정 5 / 부정 5) | 10/10 |

모든 쿼리의 trigger rate는 0 또는 1이었다(3회 모두 같은 결과).
부정 쿼리는 키워드는 겹치지만 실제로는 다른 일을 요구하는 경우로 골랐다.
예: 한국어 윤문, Claude API 코드, 모델 비교, 프롬프트 인젝션 점검, PS1, 토큰 수 세기, Seedance 영상 자르기, 나노바나나 429 재시도.
긍정 쿼리 중에는 "프롬프트"라는 말이 없는 것도 넣었다.
예: "지시를 단단하게", "뭐라고 입력해야 돼?", "템플릿 만들어줘".
최적화 루프의 1단계에서 이미 train이 전부 통과했으므로, 가이드에 따라 description은 **변경하지 않는다**.

한계: 쿼리가 실제 사용자 로그가 아니라 직접 만든 것이다. 그리고 이 환경에 설치된 다른 스킬과만 경쟁시켰다.
예를 들어 description에 언급된 `humanize-korean`은 설치되어 있지 않았다.
다른 스킬이 많은 환경에서는 결과가 달라질 수 있다.
