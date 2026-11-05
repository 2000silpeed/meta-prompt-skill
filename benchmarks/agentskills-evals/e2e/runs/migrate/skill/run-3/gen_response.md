```
레거시 Express API 서버(JavaScript)를 TypeScript로 점진적으로 옮기는 작업을 맡깁니다. 목표는 한 번에 다 바꾸는 것이 아니라, 서비스 동작을 바꾸지 않은 채 JS와 TS가 함께 동작하는 상태를 만들고, 파일을 하나씩 안전하게 전환할 수 있는 기반을 갖추는 것입니다. 이 서버는 운영 중인 API이므로 클라이언트가 보는 동작(라우트, 상태 코드, 응답 형태, 에러 포맷, 미들웨어 순서)은 하나도 바뀌면 안 됩니다. 판단 기준은 "타입이 예쁜가"가 아니라 "기존 jest 테스트와 GitHub Actions CI가 매 단계 초록색인가"입니다.

<context>
- 프레임워크: Express (JavaScript)
- 테스트: jest (기존 테스트 존재)
- CI: GitHub Actions
- 그 밖의 사실(Node 버전, Express 4/5, CommonJS/ESM, 패키지 매니저, 빌드·배포 방식, 테스트 커버리지)은 아직 확인되지 않았습니다. 추측하지 말고 저장소에서 직접 확인하세요.
</context>

<phase_1_investigate>
코드를 고치기 전에 먼저 조사하고, 아래 내용을 짧은 보고서로 정리하세요.
1. package.json(engines, scripts, 의존성 버전), lockfile, .nvmrc, Dockerfile, Procfile 등 실행·배포 진입점
2. 모듈 시스템(require/module.exports인지 import/export인지 섞여 있는지)과 "type" 필드
3. jest 설정(transform, testMatch, moduleFileExtensions, setupFiles)과 테스트가 실제 서버를 띄우는지(supertest 등)
4. .github/workflows/*의 각 job이 실행하는 명령(install, lint, test, build)과 Node 버전 매트릭스
5. 디렉터리 구조와 의존성 그래프: 다른 모듈에 의존하지 않는 말단 모듈(utils, constants, validators 등)부터 라우터·앱 진입점까지
6. 런타임 경로에 의존하는 코드: __dirname, path.join으로 찾는 정적 파일·템플릿·마이그레이션, 동적 require, 환경 변수 로딩
7. 시작 전 기준선: 지금 상태에서 `npm test`(또는 해당 명령)를 실행한 결과. 이미 실패하는 테스트가 있으면 목록을 남기고, 그 테스트는 고치지 마세요.
</phase_1_investigate>

<phase_2_foundation>
JS와 TS가 공존하는 인프라를 하나의 독립된 변경으로 만드세요.
- typescript, @types/node, @types/express(설치된 Express 메이저 버전에 맞춰서), 필요한 다른 @types/* 를 devDependencies에 추가합니다.
- tsconfig.json: `allowJs: true`, `checkJs: false`로 기존 JS를 그대로 수용합니다. 기존 모듈 시스템에 맞는 module/moduleResolution을 고르고 `esModuleInterop`을 설정합니다. 처음부터 strict를 켜되, 엄격도를 낮춰야 한다면 어떤 옵션을 왜 낮췄는지 기록하세요.
- jest가 .ts 파일을 실행할 수 있게 합니다(ts-jest 또는 기존 babel 설정 확장 중 저장소에 더 맞는 쪽을 고르고, 이유를 적으세요). 기존 .js 테스트는 그대로 돌아야 합니다.
- 빌드와 실행: tsc 출력 디렉터리, start 스크립트, 배포 진입점이 새 경로를 가리키도록 맞춥니다. 빌드 결과물에서 __dirname 기준 상대 경로(정적 파일, 템플릿 등)가 깨지지 않는지 확인하세요.
- CI: 기존 job을 지우거나 약화시키지 말고 `tsc --noEmit` 타입 체크 단계를 추가합니다. 빌드가 필요하면 빌드 단계도 추가합니다.
- 이 단계에서는 소스 파일을 .ts로 바꾸지 않습니다. 인프라 변경과 코드 변환을 섞으면 실패했을 때 원인을 가르기 어렵기 때문입니다.
</phase_2_foundation>

<phase_3_incremental_conversion>
의존성 그래프의 말단부터 위로 올라가며 한 번에 하나의 모듈(또는 서로 밀접한 작은 묶음)만 전환합니다.
- 파일 이름 변경(.js→.ts)과 타입 추가는 같은 단위 안에서 하되, 로직 변경이나 리팩터링은 하지 않습니다. 버그를 발견하면 고치지 말고 보고서에 적으세요.
- 단위마다 테스트 전체, `tsc --noEmit`, (있다면) lint와 빌드를 돌리고, 모두 통과한 뒤에만 다음 단위로 넘어갑니다.
- `any`는 경계(외부 입력, 타입 없는 서드파티)에서만 허용하고, 쓸 때마다 `// TODO(ts-migration): 이유` 주석을 붙입니다. 요청 입력(req.body, req.query, req.params)은 `unknown` 또는 명시적 인터페이스로 받고, 런타임 검증 없이 타입 단언(as)으로 "검증된 척"하지 않습니다.
- 공용 타입(도메인 모델, 요청/응답 DTO, Express Request 확장 예: req.user)은 한곳(예: src/types)에 모으고, Request 확장은 declaration merging으로 처리합니다.
</phase_3_incremental_conversion>

<pitfalls>
이런 실수를 특히 주의하세요.
- CommonJS↔ESM 상호운용: `module.exports = fn`을 `export default fn`으로 바꾸면, 아직 JS로 남아 있는 쪽의 `require()`가 `{ default: fn }`을 받아 런타임에 깨집니다. tsc는 이 문제를 잡지 못하고 테스트에서만 드러납니다. 소비자가 JS로 남아 있는 동안에는 `export =`를 쓰거나 기존 export 형태를 유지하세요.
- `module.exports.a = ...; module.exports.b = ...` 형태의 부분 export와 순환 require는 전환 후 초기화 순서가 달라질 수 있습니다.
- 에러 핸들러 미들웨어는 인자가 4개여야 Express가 에러 핸들러로 인식합니다. 타입을 붙이면서 쓰지 않는 `next`를 지우면 동작이 바뀝니다.
- async 라우트 핸들러의 에러 전파 방식(Express 4에서는 next(err)를 직접 호출해야 함)을 타입 작업 중에 바꾸지 마세요.
- `@types/express` 버전이 실제 Express 메이저 버전과 다르면 타입은 통과해도 실제 API와 맞지 않습니다.
- jest 모킹(`jest.mock` 경로, default export 모킹)은 모듈 형태가 바뀌면 조용히 무력화될 수 있습니다. 테스트가 통과해도 모킹이 실제로 적용됐는지 확인하세요.
</pitfalls>

<boundaries>
- 기존 테스트의 기대값이나 단언을 고쳐서 통과시키지 마세요. 테스트가 실패하면 원인을 분석해 보고하고, 테스트 수정이 정말 필요하다고 판단되면 그 이유를 적어 제안만 하세요. 테스트 파일 자체를 .ts로 옮기는 것은 단언 내용이 그대로일 때만 허용합니다.
- 테스트를 skip하거나 삭제하지 말고, CI 단계를 비활성화하거나 `continue-on-error`로 우회하지 마세요.
- git push, PR 생성·머지, 브랜치 보호나 CI 시크릿 변경은 하지 말고 보고만 하세요. 로컬 커밋은 논리적 단위마다 작게 나눠 해도 됩니다(인프라, 그리고 모듈 단위 전환).
- 메이저 버전이 바뀌는 의존성 업그레이드(Express, Node, jest 등), DB 스키마 변경, 공개 API 계약 변경은 하지 말고 필요성만 보고하세요.
- 운영·스테이징 DB나 외부 API(결제, 메일 발송, 서드파티 웹훅 등)에는 접근하거나 호출하지 마세요. 테스트가 실제 외부 연동을 필요로 하면 실행하지 말고 그 사실을 보고하세요. .env의 실제 비밀 값을 읽거나 출력하지 마세요.
- 작업 중 만든 임시 파일과 스크립트는 끝나면 정리하세요.
</boundaries>

<autonomy>
조사, 인프라 구성, 말단 모듈 전환은 스스로 판단해 진행하세요. 서로 독립적인 조사(파일 읽기, 설정 확인)는 도구를 병렬로 호출하세요. 다음 경우에는 멈추고 보고하세요: 기준선 테스트가 대량으로 실패할 때, 빌드·배포 진입점을 바꿔야 하는데 배포 방식을 저장소에서 확인할 수 없을 때, 모듈 시스템 자체(CJS→ESM)를 바꿔야 할 것 같을 때, boundaries에 걸리는 변경이 필요할 때.
이번 작업 범위는 phase 1, phase 2, 그리고 phase 3을 말단 모듈부터 진행할 수 있는 만큼입니다. 모든 파일을 전환하지 못해도 괜찮습니다. 완료된 각 단위가 초록색인 것이 전환한 파일 수보다 중요합니다.
</autonomy>

<deliverable>
작업을 마치면 다음을 보고하세요.
1. 조사 요약(phase 1 항목별)과 기준선 테스트 결과
2. 바꾼 설정 파일과 그렇게 정한 이유(tsconfig 옵션, jest transform 선택, CI 변경 내용)
3. 전환된 파일 목록과 남은 파일 목록, 남은 파일을 전환할 권장 순서(의존성 순)
4. 마지막으로 실행한 test, tsc, lint, build 명령과 실제 출력 요약. 실행하지 못한 검증이 있으면 실행하지 못했다고 명시하세요.
5. 남겨 둔 `any`/TODO 개수와 위치, 발견했지만 고치지 않은 버그, 사람이 결정해야 할 사항
</deliverable>
```