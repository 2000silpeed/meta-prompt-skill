작업을 마쳤습니다. 커밋 5개를 `chore/ts-migration-phase1` 브랜치에 올렸고, 테스트·타입 체크·빌드·실제 서버 기동이 모두 통과합니다. 저장소에 git remote가 없어서 push와 PR은 하지 않았습니다(요청서의 PR 항목도 비어 있었습니다). 말단 모듈이 3개뿐이라 10~20개 묶음은 나오지 않았습니다. 저장소 전체 JS가 7개입니다.

## 1. 바꾼 것

| 커밋 | 내용 |
|---|---|
| `e923474` 기반 세팅 | 패키지 추가, `tsconfig.json`, `jest.config.js`, npm 스크립트, `.gitignore`에 `dist/` 추가 |
| `d8d8491` CI | 기존 `test` job은 그대로 두고 `typecheck` job을 새로 추가(`npm run typecheck`, `npm run build`) |
| `234b4bd` 이름 변경 | `git mv`만 함: `store`, `validate`, `services/pricing`의 `.js`를 `.ts`로 |
| `b60da87` 타입 추가 | 위 3개 파일에 타입을 붙임 |
| `e251a53` 문서 | `MIGRATION.md` |

`234b4bd`는 리뷰용으로 이름 변경만 분리한 커밋이라 이것만으로는 타입 체크를 통과하지 않습니다. 커밋 메시지에도 적어 두었습니다.

**고른 도구와 이유**
- **TypeScript 5.9.3:** 최신은 7.0.2지만 ts-jest 29가 `typescript <7`까지만 지원해서 5.9.3으로 정했습니다.
- **ts-jest 29.4.15:** 빌드와 같은 `tsc`, 같은 tsconfig로 변환하므로 테스트와 운영 결과물의 의미가 같습니다. babel은 설정 파일을 추가하면 기존 `.js` 변환에도 영향을 주고, swc는 네이티브 바이너리가 새로 들어옵니다. jest 설정은 `.ts`만 ts-jest로 보내고 `.js`는 기존 babel-jest를 그대로 씁니다.
- **추가한 패키지:** `@types/express@4.17.25`, `@types/node@22.20.5`, `@types/jest@29.5.14`. 기존 패키지 버전은 바꾸지 않았습니다(express 4.21.2, jest 29.7.0, supertest 7.0.0 그대로). 다만 jest가 간접으로 쓰던 `@types/node`가 26.6.6에서 22.20.5로 합쳐졌습니다. 타입 전용 패키지라 런타임 영향은 없습니다.
- **`alwaysStrict: false`:** strict를 켜면 tsc가 레거시 `.js` 출력에 `"use strict"`를 붙인다는 것을 실제로 확인했습니다. 그러면 JS 파일의 실행 의미가 바뀔 수 있어서 이 옵션만 껐습니다. `.ts` 모듈은 이 설정과 관계없이 strict로 출력됩니다. 레거시 JS의 빌드 출력을 원본과 비교했더니 들여쓰기와 줄바꿈만 달랐습니다.
- **모듈 시스템:** CommonJS 그대로입니다. 바꾼 3개 파일은 named export로 옮겼고, 빌드 결과물의 export 이름과 타입은 이전과 같습니다. `pricing`은 키 순서만 달라졌는데, 이 모듈 객체를 순회하는 코드는 없습니다. 원래 default export가 없던 모듈이라 default export 문제는 생기지 않습니다.

## 2. 검증 결과

| 항목 | 작업 전 | 작업 후 |
|---|---|---|
| `npm test` | 7/7 통과 (이미 실패하던 테스트 없음) | 7/7 통과 (`npm ci` 후 `dist`를 지우고 다시 실행) |
| `tsc --noEmit` | 해당 없음 | 통과 |
| `npm run build` | 해당 없음 | 통과 |
| 서버 기동 | `node src/server.js` | `npm start`(`node dist/server.js`)로 `listening` 로그와 `/health` 응답 `{"ok":true}` 확인 |
| 응답 비교 | 원본 JS로 18개 요청을 보내 기준값 기록 | 빌드 결과물에 같은 요청을 보낸 결과가 상태 코드와 본문까지 완전히 같음 |
| actionlint v1.7.7 | 원본 workflow 통과 | 수정한 workflow 통과 |

- 비교한 18개 요청에는 health, 생성, 쿠폰, 검증 오류, 잘못된 JSON, 목록과 필터, 조회와 404, cancel/ship 409가 들어 있습니다.
- actionlint는 Go 모듈 프록시로 설치했습니다. GitHub 릴리스 다운로드가 403으로 막혀 있었습니다.
- **확인 못 함:** 실제 GitHub Actions에서의 실행. 원격 저장소가 없어서 돌려 보지 못했습니다.

## 3. 발견한 의심 동작 (고치지 않음)

코드에는 `NOTE(ts-migration)` 주석으로 표시했습니다.

1. **`src/services/pricing.ts:11`, `:22`:** 쿠폰을 일반 객체에서 찾기 때문에 `coupon: "toString"` 같은 값이 그대로 조회됩니다. 그러면 201 응답에 `discount: null`, `total: null`이 담깁니다. 실제로 재현했습니다.
2. **`src/services/pricing.ts:22`:** coupon이 문자열이 아니어도 문자열로 바뀌어 조회됩니다. 예를 들어 `["VIP20"]`을 보내면 할인이 적용되고, 주문에는 coupon이 배열 그대로 저장됩니다.
3. **`src/validate.ts:9-10`:** `items: [null]`을 보내면 TypeError가 나서 500이 반환되고, 내부 메시지 `Cannot read properties of null…`가 응답에 그대로 나갑니다. 실제로 재현했습니다.
4. **`src/validate.ts:14`:** price에 NaN이나 Infinity가 들어오면 검증을 통과합니다. JSON 요청으로는 보낼 수 없고 내부 호출에서만 가능합니다.
5. **`src/store.ts:18`:** `create`에 넘긴 데이터에 `id`나 `status`가 있으면 그 값으로 덮어씁니다. 현재 호출하는 곳에서는 이 키가 들어오지 않습니다.
6. **`src/store.ts:20`:** `update`에 `id`를 넘기면 저장소의 키와 주문의 `id`가 서로 달라집니다. 또 `get`과 `list`가 내부 객체를 그대로 돌려줘서 호출한 쪽에서 값을 바꿀 수 있습니다.
7. **`src/app.js:9`:** 에러 핸들러가 `err.message`를 그대로 응답에 넣습니다. 500 에러의 내부 메시지와 JSON 파싱 오류 메시지가 외부로 노출됩니다.
8. **`src/routes/orders.js:22`:** `?status=a&status=b`처럼 status가 여러 개 오면 항상 빈 배열을 반환합니다.

## 4. `any`와 `@ts-expect-error`

- `any`, `@ts-ignore`, `@ts-expect-error`는 0개입니다. grep으로 확인했습니다.
- 대신 타입 단언 4곳이 있고, 모두 이유를 주석으로 달았습니다.
  - `validate.ts:9`: `items as UncheckedItem[]`. 3번 버그를 그대로 두기 위해서입니다.
  - `validate.ts:12`: `it.qty as number`. `Number.isInteger`가 타입을 좁혀 주지 않습니다.
  - `pricing.ts:22`: `coupon as string`. 2번의 문자열 변환 동작을 유지하기 위해서입니다.
  - `pricing.ts:29`: `rate!`. 바로 위 분기에서 undefined가 아님이 보장되지만 TS가 이를 추론하지 못합니다.
- 요청 body에서 들어오는 값(`validateItems`의 `items`, `quote`의 `coupon`)은 `unknown`으로 받습니다.
- `req.user` 같은 커스텀 속성은 지금 없어서 declaration merging 파일은 만들지 않았습니다. 필요해지면 둘 위치를 `MIGRATION.md`에 적어 두었습니다.

## 5. 배포에 영향이 있는 변경

| 항목 | 이전 | 이후 |
|---|---|---|
| `scripts.start` | `node src/server.js` | `node dist/server.js` |
| `main` | `src/server.js` | `dist/server.js` |
| 새 스크립트 | 없음 | `build`(`tsc`), `typecheck` |

- 운영에서 런타임 트랜스파일을 쓰지 않기로 했기 때문에 실행 대상을 빌드 결과물로 바꿨습니다. 그래서 **배포 과정에서 `npm start` 전에 `npm run build`를 꼭 실행해야 합니다.**
- 빌드에는 dev 의존성인 `typescript`가 필요합니다. 빌드 단계에서 `npm ci --omit=dev`를 쓰면 실패합니다.
- 저장소에 Dockerfile이나 PM2 설정이 없어서 실제 배포 파이프라인은 확인하지 못했습니다. 배포 쪽 수정은 팀에서 판단해야 합니다.
- `tsc`는 `dist`를 비우지 않으므로, 배포 때는 깨끗한 상태에서 빌드하는 것을 권장합니다.

## 6. 다음 묶음 (`MIGRATION.md` 요약)

1. **`routes/orders.js`:** `app.js`가 이 모듈을 바로 라우터로 쓰므로 반드시 `export = router`로 내보내야 합니다. `export default`를 쓰면 서버가 깨집니다. `req.body`는 `unknown`으로 받습니다.
2. **`app.js`와 `server.js`:** 테스트와 `server.js`가 `require('./app')`의 결과를 앱으로 바로 쓰므로 `export = app`으로 내보냅니다. 에러 핸들러는 인자 4개를 유지해야 Express가 에러 핸들러로 인식합니다.
3. **테스트를 TS로 (선택):** `@types/supertest`가 추가로 필요합니다.
4. **마무리:** `allowJs`와 `alwaysStrict: false`를 제거하고, `noUncheckedIndexedAccess` 도입을 검토합니다.