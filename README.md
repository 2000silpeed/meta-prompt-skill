# 🚀 Meta-Prompt Skill & NEXUS Analytics Dashboard

AI 모델별 최적화 프롬프트 변환기 스킬(`meta-prompt-skill`)과 인터랙티브 데이터 시각화 대시보드 웹 애플리케이션 프로젝트입니다.

---

## 📌 주요 구성 요소

### 1. `/meta-prompt` — 타깃 AI 모델별 프롬프트 변환기 (Agent Skill)

사용자의 자연어 요청을 타깃 AI 모델(GPT-5.5, Claude Fable 5, Gemini 3.6 Flash, Nano Banana 2 등)의 공식 프롬프팅 가이드북에 맞춰 **최적화된 프롬프트**로 즉시 변환합니다.

#### 💡 핵심 설계 원칙
- **토큰 절약 3단 점진 로딩**: `registry.yaml` → 타깃 모델 `index.yaml` → 조건(`when`)에 맞는 카드만 선별 로드
- **엄격한 공식 가이드 대조**: 지식 덤프를 지양하고 verified / knowledge-based 검증 가이드에 기반하여 작성
- **다양한 타깃 지원**:
  - **OpenAI**: GPT-5, GPT-5.1, GPT-5.5 (Sol / Terra), Codex
  - **Anthropic**: Claude 3.5/3.7 (Opus / Sonnet / Haiku / Fable 5)
  - **Google**: Gemini 3.6 Flash, Gemini 3.5 Flash, Gemini 3.0 Pro
  - **Media & Image**: Google Nano Banana 2 (Gemini Image), Jimeng Seedance 2.0, Higgsfield

#### 🛠 서브 커맨드
```bash
# 특정 모델 가이드북 최신화 (공식 문서 재수집 및 카드 대조)
/meta-prompt refresh <model-id>

# 신규 AI 모델 가이드북 추가
/meta-prompt add <model-id>
```

---

### 2. NEXUS Analytics Dashboard — 데이터 시각화 대시보드 웹앱

프롬프팅을 통해 구축된 프리미엄 다크모드 기반의 인터랙티브 데이터 시각화 대시보드입니다.

#### ✨ 주요 기능
- **KPI 지표 카운터**: ARR 매출액, MAU 활성 사용자, 결제 CVR, 평균 체류 시간 (동적 뱃지 및 증감율)
- **인터랙티브 차트 (Chart.js)**:
  - 매출 추이 & 유저 성장 라인 차트 (지표 전환 토글)
  - 제품 라인업 점유율 도넛 차트
  - 글로벌 권역별 목표 달성도 바 차트
- **실시간 필터링 & 인터랙션**:
  - `7D` / `30D` / `90D` / `YTD` 기간 필터
  - 카테고리별 드롭다운 필터 및 데이터 실시간 무작위 재생성 (Toast 알림)
  - 고객사 거래 내역 검색 및 실시간 결과 필터링
- **테마 지원**: 다크 모드 / 라이트 모드 실시간 스위처

---

## 📂 프로젝트 구조

```text
meta-prompt-skill/
├── index.html                   # NEXUS Analytics 대시보드 웹앱
├── PLAN.md                      # 프로젝트 설계 및 구조 문서
├── README.md                    # 프로젝트 안내 문서
└── guidebooks/                  # 모델별 가이드북 데이터베이스
    ├── registry.yaml            # 중앙 모델 레지스트리
    ├── anthropic-claude/        # Claude 3.5 / Fable 5 가이드북 & 카드
    ├── google-gemini/           # Gemini 3.6 Flash / Pro 가이드북 & 카드
    ├── google-nano-banana/      # Nano Banana 2 이미지 가이드북 & 카드
    ├── openai-gpt-5/            # GPT-5.5 Sol/Terra/Codex 가이드북 & 카드
    ├── bytedance-seedance-2/    # Seedance 2.0 비디오 가이드북
    └── higgsfield/              # Higgsfield 미디어 가이드북
```

---

## 💻 실행 방법

### 로컬 웹 서버 실행 (대시보드 확인)

```bash
# Python 내장 HTTP 서버로 실행
python3 -m http.server 8080
```
브라우저에서 `http://localhost:8080` 접속을 통해 대시보드 웹앱을 열 수 있습니다.

---

## 📄 라이선스

MIT License
