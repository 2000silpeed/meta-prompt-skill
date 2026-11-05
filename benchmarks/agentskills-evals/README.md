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

### 다음 iteration 제안

아래 1~4는 iteration-2에서 SKILL.md에 적용했다(4절 참고). 5는 `evals.json` assertion에 반영했다.

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

## 4. Iteration 2 — 개선 적용 후 재평가

**SKILL.md 변경** (커밋 `Apply iteration-1 eval findings`):

- `## Gotchas` 섹션을 추가했다. 내용은 네 가지다.
  - 내부 용어를 노출하지 않는다.
  - "프롬프트만"이면 코드블록만 낸다.
  - 실행 설정에는 출처와 기준일을 붙인다.
  - 해설보다 바로 쓸 부속물을 넣는다.
- 신선도 경고와 폴백 고지를 사용자 언어로 바꿨다. 30일 이내 가이드는 날짜를 알리지 않는다.
- 산출 템플릿을 줄였다. 진단 차원 이름을 나열하지 않고, "보강한 점 / 채워야 할 것 / 실행 설정"만 쓴다.
- progressive disclosure를 강화했다. 서브커맨드 절차는 `references/subcommands.md`로, 이미지 분기 세부는 `references/image-prompts.md`로 옮겼다.
  그 결과 SKILL.md가 약 6,700토큰에서 약 5,800토큰으로, 150줄에서 131줄로 줄었다.

**평가 방법:** 가이드대로 이전 버전 스냅샷(`53d22e8`)을 `old_skill` baseline으로 썼다.
assertion은 iteration-1 채점자의 피드백으로 보강했기 때문에 iteration-1 수치와 직접 비교할 수 없다.
추가로 새 버전과 iteration-1의 스킬 미사용 출력을 블라인드로 비교했다.
이 출력은 `without_skill_iter1`로 연결했고, 이 쌍은 서로 다른 실행이다.

| eval | assertion new | assertion old | 블라인드 new : old | 블라인드 new : 스킬 미사용 |
|---|---|---|---|---|
| claude-long-refactor | 7/8 | 6/8 | **8** : 7 | 7 : **8** |
| glm-stale-guidebook | 7/7 | 5/7 | **8** : 7 | 6 : **8** |
| nanobanana-background-edit | 5/5 | 4/5 | **8** : 5 | 7 : **8** |
| unregistered-model-fallback | 6/6 | 5/6 | **8** : 6 | 7 : **8** |
| vague-no-target | 4/4 | 4/4 | **8** : 7 | **8** : 7 |

`benchmark.json` 평균(new vs old)은 다음과 같다.

| | new | old | Δ |
|---|---|---|---|
| pass rate | 0.975 | 0.819 | +0.16 |
| 시간 | 43.5초 | 52.4초 | −9.0초 |
| 토큰 | 20.0만 | 24.5만 | −4.5만 |

이번에는 vague-no-target에서도 양쪽 모두 스킬이 발동했다(발동은 비결정적이다).

### 해석

- **이전 버전 대비로는 블라인드 비교 5/5 개선이고, 더 싸고 빠르다.** iteration-1에서 지적된 문제가 사라졌다.
  내부 용어 노출, "프롬프트만" 위반, 장황한 진단 섹션이 그것이다. 해당 assertion도 old만 실패한다.
- **스킬 미사용 대비로는 여전히 1승 4패다(점수 차는 대부분 1점).** 남은 감점 이유는 다음과 같다.
  1. 판정자는 모델·API 사실 주장을 검증할 수 없어서, 출처를 붙여도 "근거 없는 단정"으로 본다.
     예: "Opus 5.5 effort 기본값", "Coding Plan 엔드포인트 제한".
     이 주장은 가이드북 카드에서 왔으므로 판정 설계의 한계와 겹친다.
     다음 평가에서는 판정자에게 해당 카드나 공식 문서 발췌를 근거 자료로 함께 주는 방식을 검토한다.
  2. 원본에 없는 세부를 고정한 경우다. 편집 프롬프트에 "upper left 광원, 85mm f/2.8"을 넣은 것과,
     사용자가 말하지 않은 "기능 개발이 계속 merge된다" 전제를 넣은 것이 그렇다. 실제 개선 대상이다.
     편집 요청에서는 원본 조건과 충돌할 수 있는 촬영 세부를 고정하지 않도록 이미지 카드 pitfalls에 넣을 후보다.
  3. baseline이 실전 안전장치를 더 많이 넣었다.
     예: BigDecimal 문자열 생성, 기존 테스트 기대값 변경 금지, commit 금지.
- 표본이 작고 각 쌍을 1회씩만 판정했다. 점수 차가 대부분 1점이라 반복 실행 없이는 우열을 단정하지 않는다.

description은 바꾸지 않았다. 트리거는 frontmatter만 보고 결정되므로 3절 결과가 그대로 유효하다.

### 4-1. 같은 출력을 참고 자료와 함께 다시 판정

판정자가 모델 사실을 확인할 수 없어서 생기는 감점이 얼마나 되는지 따로 쟀다.
iteration-2의 new 대 스킬 미사용 쌍을 **출력은 그대로 두고** 다시 판정했다. 이번에는 판정자에게 해당 모델 가이드북 카드를 참고 자료로 줬다.
자료는 `evals.json`의 `judge_references`에 지정했고, 양쪽 응답에 같은 자료를 준다.
처음 판정 결과는 `comparison-without_skill_iter1-norefs.json`에 남겼다.

| eval | 자료 없음 (new : 미사용) | 자료 있음 |
|---|---|---|
| claude-long-refactor | 7 : **8** | **9** : 7 |
| glm-stale-guidebook | 6 : **8** | **9** : 7 |
| nanobanana-background-edit | 7 : **8** | 7 : **8** |
| unregistered-model-fallback | 7 : **8** | 7 : **8** (참고 자료 없음) |
| vague-no-target | **8** : 7 | 7 : **8** (참고 자료 없음, 입력 동일) |

모델 지식이 많이 필요한 두 eval은 자료를 주자 판정이 뒤집혔다.
참고 자료가 없는 vague-no-target은 판정 입력이 완전히 같은데도 결과가 바뀌었다. 판정 1회의 노이즈가 이 정도라는 뜻이다.

## 5. Iteration 3 — 남은 감점 수정 + 반복 3회 + 근거 기반 판정

**SKILL.md 변경** (커밋 `Add gotchas for unstated premises...`):

- Gotcha를 두 개 추가했다.
  - 사용자가 말하지 않은 사실을 전제로 박지 않는다. 기존 이미지 편집에서는 원본이 정하는 조명·렌즈·구도를 새로 고정하지 않는다.
  - 에이전트 작업에서 되돌리기 어려운 행동의 경계와 영역별 함정을 명시한다.
- 같은 내용을 `references/image-prompts.md`에도 넣었다.
- 새 gotcha를 확인하는 assertion을 추가했다.

**평가 방법:**

- 실행: with_skill과 without_skill을 eval마다 3회씩, 총 30회 돌렸다. 결과는 `run-N/`에 있다.
- 판정: 같은 번호의 run끼리 짝지어 블라인드로 비교했다. 참고 자료가 있을 때(`-refs`)와 없을 때(`-norefs`)를 각각 판정했다.

| eval | assertion with (3회) | assertion without (3회) | 블라인드 승 (자료 있음) | 블라인드 승 (자료 없음) |
|---|---|---|---|---|
| claude-long-refactor | 7, 7, 8 / 9 | 7, 7, 5 / 9 | **3/3** | 0/3 |
| glm-stale-guidebook | 8, 7, 8 / 9 | 5, 4, 5 / 9 | **2/3** | 0/3 |
| nanobanana-background-edit | 6, 6, 6 / 6 | 5, 6, 6 / 6 | **2/3** | **2/3** |
| unregistered-model-fallback | 6, 6, 6 / 6 | 4, 4, 5 / 6 | 0/3 | 1/3 |
| vague-no-target | 4, 4, 4 / 4 | 4, 4, 4 / 4 | 3/3 | 1/3 |
| **합계** | 0.93 | 0.78 | **10/15** | 4/15 |

블라인드 승은 with_skill이 이긴 횟수다.
unregistered-model-fallback과 vague-no-target에는 참고 자료가 없다. 그래서 두 판정 조건의 입력이 같고, 두 열의 차이는 판정 노이즈다.

평균 비용은 스킬 사용 $0.26, 미사용 $0.13으로 2.1배다. 시간은 35.6초와 29.8초다.
vague-no-target은 3회 중 2회 스킬이 발동했다.

### 해석

- **판정자가 모델 사실을 확인할 수 있으면 스킬이 3분의 2를 이긴다.** 지시문 구조 차이보다, 이 스킬이 주는 모델별 지식이 판정자에게 검증 가능한지가 결과를 갈랐다.
  자료 없이 판정한 4/15에는 판정자 지식의 한계가 섞여 있다.
- **assertion 기준으로는 반복 3회 모두에서 스킬이 앞섰다.**
  - 우위가 일관된 항목: 검증일 고지, 실행 설정, 정책이 불명확할 때 보고, commit/테스트 기대값 경계, 폴백 고지.
  - nanobanana는 차이가 거의 없다. 기본 모델도 이미 잘한다.
- **unregistered-model-fallback은 일관되게 진다(1/6).** 판정자가 든 이유는 세 가지다.
  - 한계 고지가 첫 문장에 있다.
  - 정의와 예시가 어긋나는 실수가 있다.
  - baseline이 JSON 스키마, 파싱 실패 대비, 검증 방법을 더 넣었다.
  등록된 가이드가 없는 모델에서는 스킬이 범용 원칙 이상을 주지 못하고 비용만 더 든다.
- **glm 응답은 3회 모두 "실결제 API 호출·운영 데이터 접근 금지"가 빠졌다.** 결제 연동 *변경* 금지만 적고 *호출* 금지는 적지 않았다.

### 이 결과로 추가 반영한 것 (재측정 전)

- 되돌리기 어려운 행동 gotcha에 "부작용 있는 외부 호출과 운영 데이터 접근은 별도로 금지"를 넣었다.
- 폴백 고지를 첫 문장이 아니라 산출물 끝 한 줄로 옮겼다.

### 남은 과제

- 등록되지 않은 모델 요청에서는 스킬이 기본 모델보다 낫지 않았다.
  폴백 경로를 가볍게 만들지(범용 카드만 읽고 바로 작성), 아니면 부속물을 더 챙기게 할지는 다음 iteration에서 비교한다.
- 판정자를 여러 명 두거나 같은 쌍을 반복 판정해, 1회 판정의 노이즈를 줄인다.
