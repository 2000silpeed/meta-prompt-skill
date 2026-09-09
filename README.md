# meta-prompt

타깃 AI 모델의 공식 프롬프팅 가이드북에 맞춰 자연어 요청을 최적화된 프롬프트로 변환하는 에이전트 스킬.

> **EN** — meta-prompt is an agent skill that transforms natural-language requests into prompts optimized for a target AI model, using per-model guidebooks distilled from official prompting guides (GPT-5.x, Codex, Claude, Gemini, GLM, Qwen, Grok, DeepSeek, Kimi, Nano Banana, Seedance, Higgsfield). Guidebooks carry freshness metadata (`last_verified`, 30-day staleness warnings) and a `refresh` pipeline that re-verifies official sources — think Context7, but for prompting knowledge. Docs are Korean-first for now; the mechanism itself is language-agnostic.

## 사용법

### 에이전트 팀 자동 구성

`agent-team-composer`는 이 스킬의 가이드북을 기반으로 서비스·모델·역할을 선택하고,
역할별 프롬프트와 작업 순서를 구성하는 확장 스킬입니다.
실행까지 요청하면 현재 연결된 도구로 배정·통합·검증합니다.
서비스의 성능 순위를 고정하지 않고 작업 적합성, 실제 연결, 비용 제약, 인계 비용으로 판단합니다.

```text
$agent-team-composer 연결된 서비스로 이 프로젝트에 맞는 팀을 구성하고 구현해줘.
$agent-team-composer Claude 조사 + Gemini 초안 조합으로 팀과 프롬프트만 만들어줘.
$agent-team-composer 외부 비용 없이 이 작업을 처리할 팀을 구성해줘.
```

기존 meta-prompt를 설치한 상태에서 저장소 루트에서 추가 등록할 수 있습니다.

```bash
ln -s "$PWD/skills/agent-team-composer" ~/.codex/skills/agent-team-composer
```

연결되지 않은 서비스에는 수동 전달용 프롬프트를 제공합니다. 프롬프트 생성과 실제 서비스
실행은 구분하며, 서브에이전트 기능이 없는 환경에서는 순차 실행합니다.
[설계](docs/agent-team-design.md) · [스킬 본체](skills/agent-team-composer/SKILL.md)

팀 구성 비교 파일럿: [테스트 조건](benchmarks/team-composer-pilot/PROTOCOL.md) ·
[실행 결과](benchmarks/team-composer-pilot/RESULTS.md) ·
[관측과 해석](benchmarks/team-composer-pilot/FINDINGS.md).
동일한 합성 과제에서 단일 에이전트, 병렬 분담·통합, 제작·검토 구성을 비교합니다.
실제 서비스별 모델 성능이나 요금 비교와는 구분합니다.

확장 실험은 [다중 모듈 코드 회귀 수정](benchmarks/team-composer-regression/FINDINGS.md)입니다.
공개 계약과 평가용 테스트 40개를 고정해 같은 세 구성을 각각 두 번 실행했습니다.
고정 평가 결과와 실행 중 새로 발견한 결함의 사후 검사를 분리해 기록합니다.

모델별 프롬프트 A/B: [실험 조건](benchmarks/meta-prompt-ab/PROTOCOL.md) ·
[실행 결과](benchmarks/meta-prompt-ab/RESULTS.md) ·
[관측과 해석](benchmarks/meta-prompt-ab/FINDINGS.md).
Astra·Sol·Luna 각각에서 일반 지시와 가이드북으로 구성한 메타 프롬프트를 비교합니다.
상세 명세와 코드, 단독 실행 구조, 추론 설정, 41개 평가 테스트를 동일하게 유지합니다.

### 단일 모델 프롬프트

Claude Code, Gemini CLI 또는 Codex에서 자연어로 부르면 자동 발동됩니다:

```
시댄스로 카페 신제품 광고 영상 프롬프트 만들어줘
나노바나나2로 종이 공예 스타일 고양이 이미지 프롬프트 뽑아줘
이 요청을 GPT-5.6 Sol용 프롬프트로 최적화해줘
Claude Fable 5.1로 장시간 리팩터링을 맡길 프롬프트 만들어줘
Qwen3.8-Max로 이 저장소의 버그를 수정하고 검증할 프롬프트를 만들어줘
```

명시 호출은 `/meta-prompt <요청>`.

### Codex에서 변환 후 바로 실행

Codex에서 아래처럼 요청하면, 스킬이 현재 Codex 작업에 맞춘 최종 프롬프트를 먼저 만들고 그 명세를 즉시 적용해 작업을 계속합니다.

```text
$meta-prompt를 적용해서 이 요청을 Codex용으로 최적화한 뒤 구현해줘:
대시보드의 접근성 문제를 찾아 수정하고 테스트해줘.
```

모델을 명시하면 해당 모델 가이드북을 우선합니다.

```text
실행 전에 meta-prompt를 적용해줘. 최종 모델은 Claude Fable 5.1이야.
아래 고객 문의를 분석하고 답변 초안을 만들어줘.
```

### 동작 흐름

1. **모델 감지** — 명시된 모델명 → 별칭 매칭. 없으면 세션 환경·맥락으로 추론하고, 모호하면 목록에서 고르게 질문
2. **가이드북 로드** — 레지스트리 → 모델 index → 요청에 해당하는 문법 카드만 선별 로드 (토큰 절약 3단 로딩)
3. **컨텍스트 보강** — 카드가 정의한 필수 슬롯이 비었을 때만 한 번에 묶어 질문, 나머지는 기본값 + 가정 명시
4. **변환** — 카드의 규칙·템플릿·함정 체크리스트로 프롬프트 재작성 (미디어 모델은 영어 프롬프트 + 한국어 해설)
5. **전달 / 실행** — 프롬프트 전달이 기본. 세션에 실행 경로(Higgsfield MCP, codex 등)가 있으면 비용 고지 후 확인받고 실행

## 서브커맨드

```
/meta-prompt refresh <model>   # 공식 가이드 재수집 → 변경된 카드만 갱신
/meta-prompt add <model>       # 새 모델 가이드북 생성 (소스 수집 → 카드 증류 → 등록)
/meta-prompt eval <요청>       # 원본 vs 변환본을 실제 실행해 A/B 비교 (실행 경로 필요)
```

- **새 모델이 나오면**: 기존 패밀리의 새 버전이면 `refresh`, 완전히 새로운 모델이면 `add`
- 가이드북 검증일이 30일을 넘으면 사용 시 자동으로 갱신 경고가 뜹니다 (차단 없음)
- **미등록 모델**을 지정하면 범용 폴백(`_generic`, CO-STAR 기반)으로 즉시 변환하고 `add`를 권합니다
- 변환 전 원 요청을 명확성·구체성·맥락 3차원으로 진단하고, 낮은 차원을 보강해 변환합니다

## 지원 모델

| ID | 커버리지 | 유형 |
|---|---|---|
| `openai-gpt-5` | GPT-5.6 Sol · Terra · Luna | 텍스트 LLM |
| `openai-codex` | Codex CLI/IDE (태스크 프롬프트, AGENTS.md) | 코딩 에이전트 |
| `anthropic-claude` | Claude Fable 5.1 / Fable 5 / Opus 5 / Sonnet / Haiku | 텍스트 LLM |
| `z-ai-glm` | GLM-5.3 / GLM-5.3-Flash (MIT 오픈웨이트) | 텍스트 LLM / 코딩 에이전트 |
| `google-gemini` | Gemini 3.8 Flash / 3.1 Pro / 3.1 Flash-Lite | 텍스트 LLM |
| `alibaba-qwen` | Qwen3.8-Max / Flash / 오픈웨이트 | 텍스트 LLM |
| `xai-grok` | Grok 4.6 (+ 4.20 계열) | 텍스트 LLM |
| `deepseek` | DeepSeek V4-Pro / V4-Flash | 텍스트 LLM |
| `moonshot-kimi` | Kimi K3 (오픈웨이트) / K2.7 · K2.6 | 텍스트 LLM |
| `google-nano-banana` | 나노바나나2 (Gemini 3.1 Flash Image) / Pro / Lite | 이미지 생성 |
| `bytedance-seedance-2` | Seedance 2.5 (30초 원테이크 + 네이티브 오디오) / 2.0 | 영상 생성 |
| `higgsfield` | Higgsfield 플랫폼 (멀티모델 라우팅, 워크플로우) | 미디어 플랫폼 |

한국어 별칭과 흔한 오타도 인식합니다 (예: "시댄스", "나노바나나2", `GML-5.3` → `GLM-5.3`).

## 설치

레포 자체가 스킬 디렉토리입니다 — 클론 후 심링크 하나면 끝:

```bash
git clone https://github.com/2000silpeed/meta-prompt-skill.git
ln -s "$PWD/meta-prompt-skill" ~/.codex/skills/meta-prompt           # Codex
ln -s "$PWD/meta-prompt-skill" ~/.claude/skills/meta-prompt          # Claude Code
ln -s "$PWD/meta-prompt-skill" ~/.gemini/config/skills/meta-prompt   # Gemini CLI
```

## 구조

```
guidebooks/
  registry.yaml        # 모델 목록·별칭·검증일 (항상 로드되는 유일한 파일)
  <model-id>/
    sources.yaml       # 공식 가이드 URL (refresh의 입력)
    index.yaml         # 카드 목록·로드 조건·슬롯 정의
    cards/*.yaml       # 주제별 문법 카드 (선별 로드)
SKILL.md               # 스킬 본체 (변환 플로우, 레포 루트 = 스킬 디렉토리)
PLAN.md                # 설계 결정 기록
```

설계 배경과 결정 근거는 [PLAN.md](PLAN.md) 참고.

## 라이선스

MIT License
