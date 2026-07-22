# meta-prompt

타깃 AI 모델의 공식 프롬프팅 가이드북에 맞춰 자연어 요청을 최적화된 프롬프트로 변환하는 에이전트 스킬.

## 사용법

Claude Code(또는 Gemini CLI)에서 자연어로 부르면 자동 발동됩니다:

```
시댄스로 카페 신제품 15초 광고 영상 프롬프트 만들어줘
나노바나나2로 종이 공예 스타일 고양이 이미지 프롬프트 뽑아줘
이 요청을 GPT-5.5용 프롬프트로 최적화해줘
```

명시 호출은 `/meta-prompt <요청>`.

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
```

- **새 모델이 나오면**: 기존 패밀리의 새 버전이면 `refresh`, 완전히 새로운 모델이면 `add`
- 가이드북 검증일이 30일을 넘으면 사용 시 자동으로 갱신 경고가 뜹니다 (차단 없음)

## 지원 모델 (v1)

| ID | 커버리지 | 유형 |
|---|---|---|
| `openai-gpt-5` | GPT-5 / 5.1 / 5.5 Sol / 5.5 Terra | 텍스트 LLM |
| `openai-codex` | Codex CLI/IDE (태스크 프롬프트, AGENTS.md) | 코딩 에이전트 |
| `anthropic-claude` | Opus / Sonnet / Haiku / Fable 5 | 텍스트 LLM |
| `google-gemini` | Gemini 3.6 Flash / 3.5 Flash / 3.0 Pro | 텍스트 LLM |
| `google-nano-banana` | 나노바나나2 (Gemini 3.1 Flash Image) / Pro / Lite | 이미지 생성 |
| `bytedance-seedance-2` | Jimeng Seedance 2.0 | 영상 생성 |
| `higgsfield` | Higgsfield 플랫폼 (Cinema Studio 등) | 미디어 플랫폼 |

한국어 별칭도 인식합니다 (예: "시댄스", "나노바나나2").

## 설치

가이드북 데이터는 이 레포에 있고, 스킬 정의만 각 에이전트에 심링크합니다:

```bash
ln -s "$PWD/skill/meta-prompt" ~/.claude/skills/meta-prompt          # Claude Code
ln -s "$PWD/skill/meta-prompt" ~/.gemini/config/skills/meta-prompt   # Gemini CLI
```

## 구조

```
guidebooks/
  registry.yaml        # 모델 목록·별칭·검증일 (항상 로드되는 유일한 파일)
  <model-id>/
    sources.yaml       # 공식 가이드 URL (refresh의 입력)
    index.yaml         # 카드 목록·로드 조건·슬롯 정의
    cards/*.yaml       # 주제별 문법 카드 (선별 로드)
skill/meta-prompt/SKILL.md   # 스킬 본체 (변환 플로우)
PLAN.md                      # 설계 결정 기록
```

설계 배경과 결정 근거는 [PLAN.md](PLAN.md) 참고.

## 라이선스

MIT License
