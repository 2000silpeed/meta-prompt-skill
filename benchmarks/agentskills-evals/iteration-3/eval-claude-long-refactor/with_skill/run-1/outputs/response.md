Claude Opus 5.5에 그대로 넣을 수 있는 프롬프트입니다. 사람이 지켜보지 않고 오래 돌아가는 작업이라, 작업 상태를 파일로 남기는 규칙, 멈추고 보고할 조건, 끝났다고 판단하는 기준을 넣었습니다.

```xml
<context>
우리 팀의 레거시 Express API 서버(JavaScript)를 TypeScript로 점진적으로 옮기려 한다.
- 테스트: jest, 약 120개. 정확한 수는 직접 세서 기준으로 삼아라.
- CI: GitHub Actions(.github/workflows/)
- 저장소: {저장소 경로 또는 URL}
- 작업 브랜치: {브랜치 이름, 기본값: ts-migration}
- 이 작업은 여러 세션에 걸쳐 진행되며, 중간에 사람의 응답을 받을 수 없다. 진행 중에 컨텍스트가 초기화될 수 있다.

이 마이그레이션의 목적은 서버 동작을 바꾸지 않고 타입 안정성을 확보하는 것이다. 운영 중인 API이므로 응답 형식, 상태 코드, 에러 메시지가 하나라도 바뀌면 클라이언트가 깨진다. 그래서 "타입을 붙이는 것"과 "코드를 고치는 것"을 엄격히 분리한다.
</context>

<task>
JS와 TS가 함께 돌아가는 상태를 유지하면서 서버 코드를 모듈 단위로 TypeScript로 전환하라. 단계마다 jest 전체와 CI가 계속 통과해야 한다.
</task>

<phase name="0. 조사와 기준선 (코드 변경 없음)">
아래 사항을 실제 파일에서 확인하라. 추측으로 채우지 마라.
- Node 버전(.nvmrc, engines, CI matrix), 패키지 매니저와 lockfile
- 모듈 시스템(CommonJS인지 ESM인지, package.json의 "type")
- jest 설정(transform, testMatch, moduleFileExtensions, setupFiles), 테스트 실행 명령
- CI workflow의 단계, 앱 시작 경로(start 스크립트, Dockerfile, Procfile 등 실제 운영 진입점)
- 모듈 의존 그래프: 어떤 파일이 어떤 파일을 require 하는지

그다음 jest 전체를 실행해 기준선을 기록하라. 통과·실패·skip 수와, 원래부터 실패하던 테스트 목록이 기준선이다.
조사 결과와 전환 순서는 저장소 루트의 MIGRATION_PROGRESS.md에 적어라.
</phase>

<phase name="1. 공존 인프라">
- tsconfig.json: allowJs: true, checkJs: false, noEmit 또는 별도 outDir로 시작한다. strict는 처음부터 켜되, 아직 전환하지 않은 JS 파일은 검사 대상에서 빠지는 구성으로 한다.
- jest가 .ts를 실행할 수 있게 transform을 추가한다. 기존 설정 방식(babel-jest인지 ts-jest인지)을 확인하고, 그 방식과 맞는 쪽을 고른 근거를 기록하라.
- CI에 tsc --noEmit 단계를 추가한다. 기존 단계는 그대로 둔다.
- 운영 빌드·시작 경로가 TS를 실제로 실행할 수 있는지 확인한다. dist 빌드를 쓰든 런타임 로더를 쓰든, 로컬에서 서버를 띄워 헬스체크 엔드포인트 하나 이상으로 검증하라.
- @types/express, @types/node 등 타입 패키지는 devDependencies에만 추가한다. 버전은 현재 쓰는 런타임 버전에 맞춘다.
</phase>

<phase name="2. 모듈 단위 전환 (반복)">
전환은 의존성이 없는 말단 모듈부터 시작한다. 순서는 utils/config → models/services → middleware → routes → app 진입점이다.
모듈 하나(또는 밀접한 작은 묶음)마다 다음을 수행한다.
1. git mv로 .js를 .ts로 바꿔 파일 이력을 보존한다.
2. 타입을 붙인다. 로직, 제어 흐름, 리터럴 값은 바꾸지 않는다.
3. tsc --noEmit, 관련 테스트, jest 전체를 차례로 실행한다. 결과가 기준선 이하로 떨어지면 다음 모듈로 넘어가지 마라.
4. 커밋 1개를 만든다. 메시지 형식은 "ts: convert <경로>"이다.
5. MIGRATION_PROGRESS.md를 갱신한다. 완료 항목, 남은 any와 @ts-expect-error의 위치와 이유, 다음 대상을 적는다.
테스트 파일 자체는 서버 코드 전환이 모두 끝날 때까지 JS로 둔다.
</phase>

<pitfalls>
이 영역에서 흔히 놓치는 것들이다. 모듈마다 확인하라.
- Express는 에러 핸들러를 함수의 인자 개수(fn.length === 4)로 판별한다. (err, req, res, next)에서 쓰지 않는 next를 지우거나, 기본값 또는 rest 파라미터로 바꾸면 에러 핸들러가 일반 미들웨어가 되어 조용히 무시된다. next는 `_next`로 이름만 바꿔 남겨라.
- CJS와 ES 모듈의 상호운용: TS 파일을 `export default`로 바꾸면 아직 JS인 호출부의 `require('./x')`가 `{ default: ... }`를 받는다. 호출부가 남아 있는 동안에는 `export =`를 쓰거나 기존 export 형태를 그대로 유지하라. esModuleInterop 설정이 이 문제를 가려 줄 거라고 가정하지 마라.
- 타입 오류를 없애려고 동작을 바꾸지 마라. ==를 ===로, ||를 ??로 바꾸거나 null 체크를 추가하는 것은 런타임 동작 변경이다. 꼭 필요하면 TODO 주석과 MIGRATION_PROGRESS.md의 "동작 변경 후보"에 적고, 코드는 그대로 둬라.
- req.user 같은 커스텀 속성은 any 캐스팅이 아니라 선언 병합(declare global의 Express.Request 확장)으로 처리한다.
- enum, path alias, JSON import(resolveJsonModule)는 런타임 산출물이나 해석 경로를 바꿀 수 있다. 쓰기 전에 운영 실행 경로에서도 동작하는지 확인하라.
</pitfalls>

<boundaries>
아래 행동은 하지 말고, MIGRATION_PROGRESS.md의 "사람 결정 필요" 항목에 기록한 뒤 다른 모듈로 넘어가라.
- 원격 push, PR 생성, main 브랜치 변경. 로컬 작업 브랜치에 커밋하는 것은 허용한다.
- 기존 테스트의 기대값 수정, 테스트 삭제, skip/only 추가
- API 응답 형태, 상태 코드, 라우트 경로 변경
- Express 등 런타임 의존성의 메이저 업그레이드, 새 런타임 의존성 추가
- CI의 기존 검사 단계를 제거·완화하거나 continue-on-error 추가
- DB 스키마, 환경 변수 이름, 외부 연동 설정 변경
테스트가 실패하는 원인이 기존 코드의 버그로 보여도 고치지 말고 기록하라.
</boundaries>

<working_rules>
- 세션을 시작할 때마다 MIGRATION_PROGRESS.md와 git log를 먼저 읽고 이어서 진행하라. 이 파일이 유일한 작업 상태 기록이다.
- 서로 독립적인 조회·실행(파일 읽기, 검색 등)은 도구를 병렬로 호출하라.
- 진행 상황을 주장할 때는 실제 명령 출력에 근거하라. 실행하지 않은 테스트를 통과했다고 쓰지 마라.
- 한 모듈에서 같은 오류로 세 번 막히면 되돌리고(git restore), 막힌 이유를 기록한 다음 다른 모듈로 넘어가라.
- 작업 중 만든 임시 파일과 스크립트는 끝나기 전에 지워라.
</working_rules>

<done_when>
아래 조건이 모두 실제 실행 결과로 확인되면 완료로 본다.
- src(또는 서버 코드 루트) 아래 .js 서버 파일 0개. 남겨야 하는 파일이 있다면 이유를 기록한다.
- tsc --noEmit 오류 0
- jest 결과가 기준선과 같거나 더 좋다. 통과 수는 같거나 많고, 새로 실패한 테스트는 0이다.
- 로컬 CI 동등 명령이 통과하고, 서버 기동 후 헬스체크가 성공한다.
조건이 하나라도 남아 있으면 완료 보고 대신 다음 작업을 계속하라.
</done_when>

<final_report>
작업을 마치거나 더 진행할 수 없을 때 다음을 보고하라.
1. 전환된 모듈 수 / 전체 모듈 수와 커밋 목록
2. 기준선 대비 jest 결과, tsc 결과(실행한 명령과 출력 요약 포함)
3. 남은 any, @ts-expect-error 개수와 주요 위치
4. 사람 결정 필요 항목과 동작 변경 후보
5. 다음 세션에서 이어 할 첫 작업
</final_report>
```

**보강한 점**
- **CJS/TS 상호운용과 Express 에러 핸들러 문제**: 둘 다 테스트가 넉넉하지 않으면 그대로 통과해 버리는 함정이라 따로 적었습니다.
- **"타입만 붙이고 동작은 바꾸지 않는다"는 원칙**: jest를 통과하는 것만으로는 회귀가 없다는 보장이 안 되기 때문에 원칙으로 못박았습니다.
- **MIGRATION_PROGRESS.md**: 오래 걸리는 작업이라 중간에 컨텍스트가 끊겨도 이어서 할 수 있도록 상태를 이 파일에 남기게 했습니다.

**채워야 할 것과 가정**
- `{저장소 경로}`, `{브랜치 이름}`은 직접 채워 주세요.
- 로컬 커밋은 허용하고 push와 PR은 금지했습니다. PR까지 맡기려면 boundaries 항목을 고치면 됩니다.
- Node 버전, CJS/ESM, ts-jest/babel 중 무엇을 쓸지는 정하지 않고 모델이 직접 조사해서 고르게 했습니다.

**실행 설정** (Anthropic 공식 문서, 2026-10 기준)
- 모델: `claude-opus-5-5`
- effort: 기본값은 `medium`입니다. 처음 몇 개 모듈을 돌려 보고, 타입을 설계하는 품질이 아쉬우면 `high`로 올려 비교해 보세요. `xhigh`/`max`는 품질이 좋아진다는 걸 확인한 뒤에만 쓰는 것이 권장이고, 이 경우 `max_tokens`도 넉넉히 잡아야 합니다.
- thinking: 끄거나 토큰 예산(`budget_tokens`)을 지정하면 400 오류가 납니다. thinking 설정은 생략하세요.
- 이어서 실행시키기: 텍스트만 오고 응답이 끝났다고 해서 작업이 끝난 것으로 보면 안 됩니다. 체크리스트에 남은 항목이 있으면 "MIGRATION_PROGRESS.md를 읽고 이어서 진행하라"를 보내 다시 돌리세요. 같은 작업에서 이렇게 자동으로 이어 붙이는 건 2~3회까지만 하고, 그다음에는 사람이 한 번 검토하는 것이 권장됩니다.