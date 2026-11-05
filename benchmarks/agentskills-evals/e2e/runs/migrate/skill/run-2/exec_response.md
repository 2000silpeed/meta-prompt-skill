요청하신 마이그레이션을 끝까지 진행했습니다. `ts-migration` 브랜치에 로컬 커밋 8개를 남겼고(push·PR 없음), 런타임 코드는 전부 TS로 바뀌었으며 `strict: true`까지 오류 0개입니다. 테스트는 기준과 같이 7개 모두 통과합니다.

**먼저 결정해 주셔야 할 점이 하나 있습니다.** 이제 `npm start`가 컴파일된 `dist/`를 읽기 때문에 **start 전에 반드시 `npm run build`를 실행해야** 합니다. 빌드 없이 start 하면 `../dist/app`을 찾지 못해 바로 종료됩니다. start 스크립트·`main`·엔트리 경로(`src/server.js`)는 그대로입니다. 배포 쪽에서 start 전에 build를 돌리도록 맞춰 주셔야 합니다.

## 1. 저장소에서 확인한 사실과 설정 결정
- **Node:** CI가 22 하나뿐이고 매트릭스는 없습니다(로컬 v22.23.4). **패키지 매니저:** npm, `package-lock.json`, CI는 `npm ci`.
- **모듈 시스템:** CommonJS입니다(`"type"` 없음). 그래서 `module: commonjs`, `moduleResolution: node10`으로 정했습니다.
- **기존 설정:** jest 설정 파일이 없어 기본값(babel-jest, babel 설정 없음)으로 돌고 있었습니다. lint 설정, JSDoc 타입, 직접 넣은 `@types/*`는 없었습니다.
- **배포:** Dockerfile, Procfile, 배포 job이 모두 없어서 배포 방식은 알 수 없습니다.
- **start 스크립트를 바꾸지 않은 방식:** `src/server.js`는 JS로 남기고 `require('../dist/app')`만 바꿨습니다. 위에서 말한 build 선행 조건이 여기서 생깁니다.
- **`esModuleInterop: false`:** TS 파일은 `import x = require()`로 가져옵니다. 그러면 원본과 똑같은 `require` 코드가 나오고 interop 헬퍼가 끼지 않습니다.
- **내보내기 방식:**
  - 객체를 내보내던 모듈(store, validate, pricing)은 named export로 바꿨습니다. `require()` 결과 모양이 같아서 남은 JS 소비자에 영향이 없습니다.
  - 값 하나를 내보내던 모듈(app, router)은 `export =`를 써서 `{ default }`로 감싸지는 문제를 피했습니다.
- **jest:** `jest.config.js`를 새로 만들었습니다. `.ts`는 ts-jest로 돌리고, `.js`용 기본 babel-jest도 명시해 그대로 유지했습니다.
- **devDependency 추가:** typescript 5.9.3, ts-jest 29.4.15, `@types/node`·`express`(4.x)·`jest`·`supertest`. 런타임 의존성은 lockfile 기준으로 69개 그대로입니다.
- **CI:** 기존 test job 끝에 `npm run typecheck`와 `npm run build` 단계만 덧붙였습니다.
- **strict:** 변환하는 동안에는 `false`로 두고, 변환을 마친 뒤 `noImplicitAny` → `strictNullChecks` → `strict` 순서로 켰습니다. 매번 오류 0개였고, 빌드 결과물은 바이트 단위로 같았습니다.

## 2. 변환한 파일과 남은 JS
- **변환한 파일:**
  - `validate`, `store`, `services/pricing` (+ 새 파일 `types.ts`)
  - `routes/orders`, `app`, `tests/orders.test`
- **남은 JS:** 엔트리 `src/server.js` 하나뿐입니다.
- **다음 단계 제안:** 배포를 확인한 뒤 `src/server.ts`로 바꾸고 start를 `node dist/server.js`로 변경하는 것을 권합니다.
- **전역 타입 선언:** `req.user` 같은 커스텀 Request 필드가 없어서 `declare global`은 추가하지 않았습니다.

## 3. 테스트·타입체크 결과
마지막에 `rm -rf node_modules dist && npm ci`로 깨끗하게 다시 설치한 뒤 아래 순서로 돌렸습니다.

| 확인 항목 | 기준 | 최종 |
|---|---|---|
| `npm test` | 1 suite, 통과 7 / 실패 0 / 스킵 0 | 같음, 새로 실패한 테스트 0 |
| `npm run typecheck` | — | exit 0 |
| `npm run build` | — | exit 0 |
| `npm start` 후 실제 요청 5종 | 응답 기록 | 같음 |

- 실제 요청 5종은 health, 쿠폰 주문, 모르는 쿠폰 400, 깨진 JSON 400, status 필터입니다. 기준 응답과 바이트 단위로 같았습니다.
- 원래부터 실패하던 테스트는 없었습니다.
- 묶음(커밋)마다 같은 검증을 반복했습니다.
- 에러 핸들러는 컴파일 후에도 인자 4개(`next` 포함)를 유지합니다.
- ES 모듈 문법으로 바꾼 파일은 컴파일 결과에 `"use strict"`가 붙습니다. 해당 파일들에 strict 모드에서 동작이 달라지는 코드가 없는지 확인했습니다.
- 실행하지 못한 것: GitHub Actions에서 실제로 돌려 보지는 못했습니다. 같은 명령을 로컬에서 `npm ci`부터 그대로 재현한 결과만 있습니다.

## 4. TODO(ts-migration): 4곳
- `pricing.ts`, `routes/orders.ts`: 검증되지 않은 `coupon`에 `as string` 단언 (2곳)
- `routes/orders.ts`: `validateItems`가 타입 가드가 아니라서 `items as OrderItem[]` 단언
- `app.ts`: 에러 핸들러의 `err: HttpError`. 실제로는 Error라는 보장이 없습니다.
- TODO를 달지 않은 곳: `validate.ts`의 반복 변수 `it`은 `Array.isArray`가 만든 `any[]`에서 추론된 `any`입니다. 직접 쓴 `any`가 아니어서 TODO는 달지 않았습니다.

## 5. 보류한 결정과 발견한 잠재 버그 (코드는 고치지 않음)
**보류한 결정**
- 배포에 build 단계를 넣을지, start 스크립트를 바꿀지
- `npm ci`가 표시한 audit 경고 처리
- 작업 브랜치 이름: 지정된 이름이 `<브랜치명>` 그대로 비어 있어서 `ts-migration`으로 정했습니다.

**잠재 버그**
1. `items: [null]`을 보내면 `.sku`를 읽다가 TypeError가 나고, 내부 오류 메시지가 그대로 담긴 500이 응답됩니다.
2. 쿠폰이 `"constructor"`나 `"toString"`처럼 객체 기본 속성 이름이면 400이 아니라 `discount`·`total`이 `null`(NaN)인 주문이 201로 만들어집니다.
3. `coupon: ["VIP20"]`처럼 배열을 보내도 할인이 적용되고, 쿠폰이 배열 그대로 저장됩니다.
4. 에러 핸들러가 모든 `err.message`를 클라이언트에 그대로 보냅니다(500 오류와 JSON 파싱 오류 포함).
5. `store.create`가 `id`/`status`를 정한 뒤에 `data`를 펼쳐서, `data`가 이 값들을 덮어쓸 수 있습니다. 지금 라우트 코드로는 일어나지 않습니다.
6. `?status=a&status=b`처럼 status를 여러 번 보내면 배열이 되어 항상 빈 목록이 반환됩니다.

설정 결정 내용은 저장소의 `TS_MIGRATION.md`와 `tsconfig.json` 주석에도 적어 두었습니다.