# meta-prompt

타깃 AI 모델의 공식 프롬프팅 가이드북에 맞춰 자연어 요청을 최적화된 프롬프트로 변환하는 에이전트 스킬.

> **EN** — meta-prompt is an agent skill that transforms natural-language requests into prompts optimized for a target AI model, using per-model guidebooks distilled from official prompting guides (GPT-5.x, Codex, Claude, Gemini, GLM, Nano Banana, Seedance, Higgsfield). Guidebooks carry freshness metadata (`last_verified`, 30-day staleness warnings) and a `refresh` pipeline that re-verifies official sources — think Context7, but for prompting knowledge. Docs are Korean-first for now; the mechanism itself is language-agnostic.

## 사용법

Claude Code, Gemini CLI 또는 Codex에서 자연어로 부르면 자동 발동됩니다:

```
시댄스로 카페 신제품 15초 광고 영상 프롬프트 만들어줘
나노바나나2로 종이 공예 스타일 고양이 이미지 프롬프트 뽑아줘
이 요청을 GPT-5.6 Sol용 프롬프트로 최적화해줘
GLM-5.3으로 이 저장소의 버그를 수정하고 검증할 프롬프트를 만들어줘
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
실행 전에 meta-prompt를 적용해줘. 최종 모델은 Claude Fable 5야.
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

## 지원 모델 (v1)

| ID | 커버리지 | 유형 |
|---|---|---|
| `openai-gpt-5` | GPT-5.x / GPT-5.6 Sol·Terra·Luna | 텍스트 LLM |
| `openai-codex` | Codex CLI/IDE (태스크 프롬프트, AGENTS.md) | 코딩 에이전트 |
| `anthropic-claude` | Opus / Sonnet / Haiku / Fable 5 | 텍스트 LLM |
| `z-ai-glm` | GLM-5.3 (Coding Plan; 일반 API 출시 전) | 텍스트 LLM / 코딩 에이전트 |
| `google-gemini` | Gemini 3.6 Flash / 3.5 Flash / 3.0 Pro | 텍스트 LLM |
| `google-nano-banana` | 나노바나나2 (Gemini 3.1 Flash Image) / Pro / Lite | 이미지 생성 |
| `bytedance-seedance-2` | Jimeng Seedance 2.0 | 영상 생성 |
| `higgsfield` | Higgsfield 플랫폼 (Cinema Studio 등) | 미디어 플랫폼 |

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
