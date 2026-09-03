# meta-prompt-skill 설계 합의안

2026-07-22 grill 세션에서 합의된 설계. 구현의 기준 문서.

## 목적

타깃 모델을 파악하고, 모델별 프롬프트 가이드북(문법 카드)에 맞춰 사용자의 요청을
최적화된 프롬프트로 변환하는 스킬. 텍스트 LLM과 미디어 생성 모델을 처음부터 모두
커버하는 범용 체계.

동작 흐름: ①모델 감지 → ②가이드북 조회 → ③요청 변환 → ④필요시 컨텍스트 보강 → ⑤전달/실행

핵심 제약: 가이드북의 **최신성 유지**와 **토큰 사용 최소화**의 양립.

## 결정 사항

| 분기 | 결정 |
|---|---|
| 폼 팩터 | Claude Code 스킬 먼저. 가이드북 데이터는 스킬 본체와 분리해 나중에 MCP(Context7식)가 그대로 서빙 가능한 구조로 |
| 가이드북 형식 | 모델별 디렉토리 + 주제별 YAML 문법 카드 (semantic-os 형식 차용, 데이터는 무관) |
| 카드 소유권 | 이 레포에 완전 독립 저장. semantic-os와 연결 없음 |
| 갱신 | 카드·레지스트리에 source_url·last_verified 메타데이터. 사용 시 30일 초과면 경고만, 갱신은 `/meta-prompt refresh <model>`로 명시 실행 (WebFetch → 변경 카드만 수정) |
| 모델 감지 | ⓪ 환경 자체 감지(현재 세션 모델, 연결된 MCP 도구) → ① 사용자 명시 → ② 맥락 추론(추론 시 반드시 명시) → ③ 레지스트리 목록에서 질문 |
| 컨텍스트 보강 | 모델 index.yaml이 required/optional 슬롯 정의. 필수 슬롯 누락분만 묶어 1라운드 질문, optional은 기본값 + 가정 명시 |
| 실행 | 변환된 프롬프트 전달이 기본. 세션에 실행 경로(Higgsfield MCP, codex 등)가 있으면 비용 명시 후 확인받고 실행 |
| v1 커버리지 | GPT-5.x, Claude, Gemini, GLM + Seedance 2.0, Higgsfield (기존 seedance-prompt 스킬은 카드 작성 참고자료로만) |
| 호출 | `/meta-prompt`, 자연어 자동 트리거 병행. 서브커맨드: `refresh <model>`, `add <model>` |

## 세부 설계

- **토큰 절약(3단 점진 로딩)**: `registry.yaml`(전 모델 목록+갱신일, 극소, 항상 로드)
  → 모델별 `index.yaml`(카드 목록+용도 설명+슬롯 정의) → 해당 요청에 필요한 카드만 선별 로드.
- **산출 언어**: index.yaml이 모델별로 정의. 미디어 모델은 영어 프롬프트 + 한국어 해설,
  LLM 프롬프트는 타깃 용도의 언어를 따름.
- **카드 제작 절차**: 모델별 `sources.yaml`에 공식 가이드 URL 목록 → WebFetch로 수집 →
  카드 증류 → 사용자 검토 후 확정. `add <model>`도 같은 절차.

## 디렉토리 구조

```
meta-prompt-skill/                 # 레포 루트 = 스킬 디렉토리 (통째로 심링크)
  SKILL.md                         # ~/.claude/skills/ 및 ~/.gemini/config/skills/ 로 심링크
  PLAN.md
  guidebooks/
    registry.yaml                  # 모델 목록+별칭+갱신일 (항상 로드, 극소)
    <model-id>/
      sources.yaml                 # 공식 가이드 URL 목록 (refresh의 입력)
      index.yaml                   # 카드 목록+when+슬롯 정의 (변환 시 로드)
      cards/*.yaml                 # 주제별 문법 카드 (선별 로드)
```

## 실행 순서

1. ✅ 스킬 골격 + 레지스트리/카드 스키마 확정
2. ✅ GPT-5.x 카드 1세트로 파이프라인 끝까지 검증
3. ✅ 나머지 4개 모델 확장 (Claude, Gemini, Seedance 2.0, Higgsfield)

주의: v1 카드는 모델 지식 기반 초안(`verification: knowledge-based`)으로 작성됨.
첫 `/meta-prompt refresh <model>` 실행이 공식 가이드 대조 검증을 수행한다.

## v1.1 개선 (2026-07-22, 생태계 비교분석 반영)

유사 스킬(prompt-optimizer, prompt-architect, getsentry prompt-optimizer 등) 조사 결과
모델별 가이드북·신선도 파이프라인·미디어 커버는 유일했고, 아래 3가지를 역수입:

1. **범용 폴백** — `guidebooks/_generic/` (CO-STAR/RTF/RISEN). 레지스트리 미등록 모델
   요청 시 즉시 변환 후 `add` 권고. registry에 `fallback: _generic` 필드 추가.
2. **변환 전 진단** — 원 요청을 명확성·구체성·맥락 3차원으로 진단하고 낮은 차원을
   변환에서 보강, 산출물에 진단 표기. (prompt-architect의 5차원 채점에서 착안, 3으로 압축)
3. **`/meta-prompt eval`** — 원본 vs 변환본을 동일 조건 실행해 A/B 비교. 변환본이
   우세하지 않으면 정직 보고 + 해당 카드 개선점 기록(가이드북 피드백 루프).
   (getsentry의 eval-first 접근에서 착안)

보류: 훅 기반 auto 모드(철학 상이 — 모델별 변환이 아닌 전 프롬프트 정제),
마켓플레이스 등재(외부 공개는 별도 결정).

## 2026-08-17 모델 갱신

- OpenAI 패밀리를 GPT-5.6 Sol/Terra/Luna 기준으로 갱신하고, 간결한 결과 중심 프롬프트·승인 경계·reasoning effort/pro mode 규칙을 공식 문서로 재검증.
- Claude Fable 5 전용 카드를 추가하고, always-on adaptive thinking·effort·장시간 실행·refusal 처리·숨은 추론 비노출 규칙을 반영.
- Z.ai GLM-5.3 가이드북을 추가. Coding Plan 제공과 일반 API 미출시 상태를 분리하고, agentic engineering·검증·thinking/도구 규칙을 등록.

## 2026-09-03 모델 갱신 (v1.2)

8월 중순 이후 릴리스를 반영하고, 커버리지를 8종 → 12종으로 넓혔다.

**기존 가이드북 갱신**

- **Claude**: Fable 5.1(2026-09-01) 반영. `fable-5-runtime`을 5.1 기준으로 다시 쓰고(effort에 `max` 추가,
  forced tool use 미지원, thinking 블록의 대화 바인딩, turn-scoped system message·per-message effort·
  `display: updates` 베타, cache read 0.025배), 5.1에서 달라진 기본 동작의 증상→처방 대응표를
  `fable-5-1-behaviors` 카드로 신설했다.
- **Gemini**: `gemini-3-runtime` 카드 신설. 3.8 Flash(2026-09-02)를 기본으로 두고 `thinking_level` 체계와
  temperature 1.0 고정·top_p/top_k/candidate_count 폐기를 명시했다. 기존 `iteration-parameters` 카드가
  권고하던 "결정적 작업은 temperature 0" 지침은 2.x 시대 규칙이라 3.x 기준으로 교체했다.
- **GLM**: GLM-5.3 일반 API가 출시돼 "coming soon" 상태 표기를 걷어내고, GLM-5.3-Flash(2026-08-26, MIT
  오픈웨이트, 320B/활성 18B)를 라인업에 추가했다. `reasoning_effort` low/high/max(기본 max)와
  temperature 1.0을 공식 문서로 확정했다.
- **Codex**: GPT-5.4/5.4-mini 은퇴(2026-08-31)와 Terra/Luna 대체, 신뢰되지 않은 프로젝트의 AGENTS.md
  미주입(v0.150.0), 태스크 @ 멘션을 반영.
- **Seedance**: 2.5(2026-07-31)로 갱신. 30초 원테이크·다회 연장, 영상과 동시 생성되는 오디오,
  참조 50개(이미지 30/영상 10/오디오 10), 클레이 렌더·모션·조명 참조, 타임스탬프 편집.
- **나노바나나**: video-to-image, 이미지 검색 그라운딩, 3.1 Flash의 thinking level, 모델별 참조 상한.
- **Higgsfield**: 현재 탑재 모델 라인업과 Genjutsu 편집 경로(legacy motion_control 대체)로 라우팅 갱신.
- **GPT-5.x**: 2026-09-03 재확인 결과 GPT-5.6(Sol/Terra/Luna)이 여전히 최신 — 검증일만 갱신.

**신규 가이드북 4종** (사용자 선택으로 범위 확정)

| ID | 근거 |
|---|---|
| `alibaba-qwen` | Qwen3.8-Max(2.4T MoE, 1M) / Flash. Model Studio·QwenCloud 공식 문서 대조 |
| `xai-grok` | Grok 4.6(500K). docs.x.ai 기준 — xAI는 별도 프롬프팅 가이드 미발행 |
| `deepseek` | V4-Pro / V4-Flash. thinking·non-thinking 이중 모드, 레거시 ID 은퇴 |
| `moonshot-kimi` | Kimi K3(2.8T 오픈웨이트, 1M). 상시 thinking, reasoning_effort 기본 max |

**메타데이터 규약 추가**: `verification: partial` — 스펙·라인업은 공식 대조했지만 프롬프트 문법 카드는
지식 기반 초안인 상태(현재 Seedance, Higgsfield). SKILL.md의 신선도 표기 규칙에 반영했다.
