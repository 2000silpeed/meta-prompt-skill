Claude 관련 지침을 확인했고, 이제 프롬프트를 작성하고 있습니다.

```markdown
<context>
이 저장소는 운영 중인 레거시 Express API 서버이고 JavaScript로 작성되어 있다. 테스트는 jest 약 120개, CI는 GitHub Actions다.
목표는 이 서버를 TypeScript로 **점진적으로** 옮기는 것이다. 한 번에 모두 바꾸지 않고, 매 단계가 끝날 때마다 서버가 그대로 동작하고 테스트와 CI가 통과해야 한다.
이 작업은 대화 없이 실행된다. 중간에 물어볼 사람이 없으므로, 스스로 판단할 수 있는 일은 판단해서 진행한다. 사람이 결정해야 할 일은 진행 기록에 남기고 다른 작업으로 넘어간다.
</context>

<goal>
런타임 동작을 하나도 바꾸지 않고 `.js` 소스를 `.ts`로 전환한다. 리뷰어가 각 단계를 따로 검토하고 필요하면 되돌릴 수 있도록, 작은 단위로 나눠 진행한다.
"동작이 같다"는 기존 jest 테스트가 모두 그대로 통과하고, HTTP 응답(상태 코드, 본문 형태, 헤더)과 미들웨어 실행 순서가 바뀌지 않았다는 뜻이다.
</goal>

<phase_0_baseline>
코드를 고치기 전에 현재 상태를 조사해 `MIGRATION_PROGRESS.md`에 기록한다.
- Node 버전, 모듈 방식(CommonJS/ESM), 진입점, `package.json` 스크립트, jest 설정(babel 사용 여부, transform, moduleNameMapper)
- `.github/workflows/`의 각 job이 하는 일, 특히 test 단계와 build/deploy 단계
- **기준선**: `npm test`(또는 이 저장소의 테스트 명령)를 실행해 통과/실패/스킵 개수를 정확히 적는다. 이미 실패하는 테스트가 있으면 이름을 적고 고치지 않는다. 이후 검증은 모두 이 기준선과 비교한다.
- 모듈 의존 그래프를 대략 파악해 전환 순서를 정한다. 의존성이 없는 쪽(utils, constants, 순수 함수)에서 시작해 services, middleware, routes, app/server 진입점 순서로 올라간다.
</phase_0_baseline>

<phase_1_setup>
JS와 TS가 함께 돌아가도록 기반을 만든다.
- 개발 의존성으로 `typescript`, `@types/node`, `@types/express`, `@types/jest`와 사용 중인 라이브러리의 `@types/*`를 추가한다.
- `tsconfig.json`: `allowJs: true`, `checkJs: false`로 시작한다. `strict`는 처음에는 끄고, 진행 기록에 단계별로 켤 계획을 적는다. 모듈 설정은 현재 런타임의 모듈 방식과 맞춘다.
- jest가 `.ts` 테스트와 소스를 처리하도록 설정한다(ts-jest 또는 기존 babel 설정 확장 중 저장소에 맞는 쪽). 설정을 바꾼 직후 기준선과 같은 결과가 나오는지 확인한다.
- `typecheck` 스크립트(`tsc --noEmit`)를 추가한다.
- 빌드 산출물 방식(tsc emit, ts-node, tsx 등)이 정해지기 전에는 운영 실행 경로(`start` 스크립트, Dockerfile, 배포 job)를 건드리지 않는다. 필요한 변경안만 기록한다.
</phase_1_setup>

<phase_2_incremental_conversion>
파일을 하나씩, 또는 서로 강하게 묶인 작은 묶음 단위로 전환한다. 한 단위마다 다음 순서를 반복한다.
1. 파일 이름을 `.ts`로 바꾸고 타입을 붙인다. 외부 입력(req.body, req.query, 환경변수, DB 결과)은 실제 사용처를 보고 타입을 정한다. 확신이 없으면 `unknown`과 좁히기를 쓰고, `any`를 쓰면 `// TODO(ts):` 주석으로 이유를 남긴다.
2. 타입을 맞추려고 로직을 바꾸지 않는다. 타입 오류가 실제 버그를 드러내면 고치지 말고 진행 기록의 "발견한 버그" 항목에 위치와 재현 조건을 적는다. 버그를 고치면 동작이 바뀌기 때문이다.
3. 검증: `tsc --noEmit` 통과, 전체 jest를 기준선과 같은 개수로 통과, lint가 있으면 lint 통과.
4. 진행 기록을 갱신한다(전환한 파일, 남은 파일, 남긴 TODO).

독립적인 조사 작업(여러 파일 읽기, 사용처 검색)은 도구를 병렬로 호출해도 된다. 파일 수정과 검증은 한 단위씩 순서대로 한다.
</phase_2_incremental_conversion>

<phase_3_tightening>
모든 소스가 `.ts`로 바뀐 뒤에 `noImplicitAny`, `strictNullChecks` 순서로 strict 옵션을 하나씩 켠다. 옵션 하나를 켤 때마다 오류를 정리하고 위 검증을 반복한다. 이 단계의 범위는 테스트 파일 전환 여부를 포함해 진행 기록에 먼저 계획으로 적고 시작한다.
</phase_3_tightening>

<pitfalls>
이 마이그레이션에서 놓치기 쉬운 지점이다. 해당 코드를 만나면 특히 주의한다.
- **에러 핸들러의 인자 4개**: Express는 `(err, req, res, next)`처럼 인자가 4개인 함수만 에러 미들웨어로 인식한다. 쓰지 않는 `next`를 지우거나 lint 수정으로 인자 개수가 줄면 에러 처리가 조용히 망가진다. `_next`로 이름만 바꾼다.
- **CommonJS/ESM 상호운용**: `module.exports = fn`을 `export default fn`으로 바꾸면, 아직 JS로 남은 파일의 `require()` 결과가 `{ default: fn }`이 된다. 아직 JS인 사용처가 남아 있으면 `export =`를 쓰거나 사용처를 함께 고친다. `esModuleInterop` 설정이 기존 `require` 동작에 미치는 영향도 확인한다.
- **jest.mock 경로와 호이스팅**: 파일 확장자가 바뀌면 `jest.mock('./x')`이 가리키는 모듈과 mock 팩토리의 export 형태(default인지 named인지)가 실제 모듈과 어긋날 수 있다. 테스트가 통과하더라도 mock이 실제로 적용되는지 확인한다.
- **req 확장 속성**: `req.user` 같은 커스텀 속성은 캐스팅으로 처리하지 않는다. `declare global { namespace Express { interface Request { ... } } }`으로 선언을 병합한다.
- **emit으로 바뀌는 런타임 의미**: `target`과 `useDefineForClassFields`에 따라 클래스 필드 초기화 순서가 달라질 수 있다. 동적 `require(변수)`, JSON import, `__dirname`처럼 빌드 산출물 위치에 따라 달라지는 경로도 확인한다.
</pitfalls>

<boundaries>
다음은 사람이 결정할 일이다. 하지 말고 진행 기록의 "결정 필요" 항목에 이유와 제안을 적은 뒤 다른 작업을 계속한다.
- 기존 테스트의 기대값이나 assertion 수정, 테스트 삭제, skip 처리. 테스트는 동작이 같다는 유일한 증거다. 확장자 변경과 import 경로 수정만 허용한다.
- API 응답 형태, 라우트, DB 스키마, 외부 연동, 환경변수 이름 변경
- `start` 스크립트, Dockerfile, CI의 deploy 단계, Node 버전, secrets 변경. CI에는 기존 test job에 `typecheck` 단계를 **추가**하는 것만 허용한다.
- 메이저 버전 의존성 업그레이드
- {커밋 정책: 기본값은 "작업 브랜치에서 전환 단위마다 로컬 커밋 허용. push, PR 생성, main 브랜치 직접 수정은 금지"}
</boundaries>

<progress_and_continuation>
`MIGRATION_PROGRESS.md`는 작업이 중단되거나 컨텍스트가 초기화되어도 이어서 할 수 있게 해 주는 기준 문서다. 항상 최신 상태로 유지한다. 포함할 항목은 기준선, 전환 순서와 체크리스트(완료/남음), 현재 tsconfig strict 단계, TODO(ts) 개수, 발견한 버그, 결정 필요 항목이다.
새로 시작하거나 이어서 작업할 때는 먼저 이 파일과 `git log`/`git status`를 읽고, 남은 첫 항목부터 진행한다.
진행 상황을 보고할 때는 실제로 실행한 명령의 결과만 근거로 쓴다. 테스트 개수와 tsc 결과는 실행 출력에서 확인한 숫자로 적는다.
</progress_and_continuation>

<completion>
다음 조건을 모두 만족하면 완료로 보고한다. 일부만 끝났으면 어디까지 했는지와 남은 항목을 보고한다.
- 대상 소스 디렉토리에 `.js` 파일이 남아 있지 않다. 의도적으로 남긴 파일은 이유를 기록한다.
- `tsc --noEmit` 통과, 전체 jest 결과가 기준선과 같다(통과 개수 동일, 새 실패 0).
- CI 워크플로에 typecheck 단계가 추가되었다.
- 진행 기록이 최신이다.

마지막 보고에는 다음만 담는다: 전환한 파일 수와 남은 파일 수, 검증 명령과 실제 결과, 현재 strict 단계, TODO(ts) 개수, 발견한 버그, 결정 필요 항목 목록.
</completion>
```

**프롬프트에 넣은 것**:
- **기준선 기록**: 테스트 개수를 정확히 적어 두게 했습니다. 120개가 계속 통과하는지 나중에 비교할 기준이 없으면 "통과했다"는 보고를 확인할 수 없기 때문입니다.
- **바꾸지 말아야 할 것**: 테스트 기대값, 배포 경로, 버그 수정을 금지 목록에 넣었습니다. 장기 무인 작업에서 가장 위험한 실패는 "테스트를 고쳐서 통과시키는 것"입니다.
- **작업 기록 파일**: 컨텍스트가 끊겨도 이어갈 수 있도록 `MIGRATION_PROGRESS.md`를 두었습니다.
- **Express·TS 함정**: 에러 핸들러 인자 개수, CJS/ESM `default` 상호운용, jest.mock을 넣었습니다.

**정해야 할 것**:
- `{커밋 정책}` 자리표시자를 채워 주세요. 기본값은 "로컬 커밋 허용, push/PR 금지"로 두었습니다.
- 테스트 파일까지 `.ts`로 바꿀지는 phase 3에서 에이전트가 계획을 적게만 해 두었습니다. 이미 정해 두셨다면 프롬프트에 직접 적어 주세요.

**실행 설정** (Anthropic 공식 문서 기준, 2026-10 확인):
- 모델은 `claude-opus-5-5`입니다. effort 기본값은 medium입니다. 결과 품질이 부족할 때만 high로 올리고, xhigh/max를 쓰면 `max_tokens`를 넉넉히 잡으세요.
- `tool_choice`는 auto만 쓰세요(any/tool은 거부됩니다). thinking을 disabled로 보내거나 `budget_tokens`를 지정해도 거부됩니다.
- 에이전트가 텍스트로만 턴을 끝냈다고 해서 작업이 끝난 것으로 보지 마세요. 진행 기록에 남은 항목이 있으면 짧게 "계속하라"를 보내되, 같은 작업에서는 2~3회까지만 하고 사람이 확인하는 것을 권장합니다.