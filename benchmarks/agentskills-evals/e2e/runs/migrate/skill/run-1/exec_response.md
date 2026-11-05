TypeScript 마이그레이션 작업을 마쳤습니다. 작업 범위가 비어 있어서 지시대로 1~3단계까지만 했고, 서버 코드가 6개 파일뿐이라 3단계에서 `src/` 전체를 TS로 옮겼습니다. 남은 JS는 테스트 파일 하나와 jest 설정뿐입니다. 아래 검증은 전부 실제로 실행해서 통과했습니다.

- **테스트**: 기준선 7개 통과 / 실패 0 / 스킵 0, 변환 후에도 7개 통과 / 실패 0 / 스킵 0입니다. 원래 실패하던 테스트는 없었고, 테스트 파일은 손대지 않았습니다.
- **타입 체크·빌드**: `npm run typecheck`(strict)와 `npm run build`가 통과합니다.
- **응답 비교**: 변환 전 서버에서 22가지 요청(정상 흐름, 잘못된 JSON, 404, 409, 이상한 입력 등)의 상태 코드, 주요 헤더(content-type, etag 등), 본문을 기록해 두었습니다. 매 커밋마다 빌드 결과물로 서버를 띄워 같은 요청을 보냈고, 22건 모두 동일했습니다.
- **CI 재현**: 깨끗한 클론에서 `npm ci → npm test → typecheck → build → npm start` 순서로 돌려 모두 통과했습니다.
- **미검증**: 실제 GitHub Actions 실행(push를 하지 않았으므로)과 운영 배포 환경. 저장소에 Dockerfile이나 배포 설정이 없어서 배포 쪽은 확인할 수 없었습니다.

작업은 `chore/ts-migration-phase1` 브랜치에 로컬 커밋 6개로 나눠 두었고, push나 PR은 하지 않았습니다.

## 1. 변환한 파일과 남은 JS
| 순서 | 파일 | 비고 |
|---|---|---|
| 1 | `src/store.ts`, `src/types.ts`(새 파일, 타입만 있음) | 이름 있는 export로 바꿔서 JS 쪽 `require().reset`이 그대로 동작 |
| 2 | `src/validate.ts` | 입력을 `unknown`으로 받음 |
| 3 | `src/services/pricing.ts` | |
| 4 | `src/routes/orders.ts` | `export = router`로 기존 `require` 형태 유지 |
| 5 | `src/app.ts`, `src/server.ts` | 에러 미들웨어는 인자 4개 유지(빌드 결과에서 4개 확인), `export = app` |

- **남은 JS**: `tests/orders.test.js`, `jest.config.js`(설정 파일이라 JS로 둬도 됨).
- **다음 권장 순서**: `@types/supertest`를 추가하고 테스트를 `.ts`로 옮기는 것(단언은 그대로). 그다음 2의 `app.ts`, `routes/orders.ts`에 둔 `export =`를 일반 export로 바꾸는 것은 JS 호출부가 모두 사라진 뒤에 하면 됩니다.
- 동적 `require`, `__dirname`, JSON 같은 비코드 파일 로딩, monkey-patching, `req`에 붙이는 커스텀 속성은 하나도 없었습니다. 그래서 `req` 타입 확장 선언은 필요 없었습니다.

## 2. 설정 변경과 선택 이유
- **빌드 방식은 `tsc → dist`**: tsx나 ts-node로 바로 실행하려면 런타임 의존성을 추가해야 해서 금지 조건에 걸립니다. `dist/`는 `src/`와 같은 폴더 구조로 나오므로 상대 경로가 깨지지 않습니다. 빌드 전에 `dist`를 지우는 `clean` 스크립트도 넣었습니다.
- **`tsconfig.json`**(타입 체크용): `allowJs`, `checkJs: false`, `strict: true`, CommonJS. JS는 타입 검사를 하지 않으므로 strict는 변환한 `.ts`에만 적용됩니다. **`tsconfig.build.json`**은 실제 빌드용입니다.
- **jest**: `.ts`는 ts-jest가, `.js`는 기존 기본값과 같은 babel-jest가 처리합니다. 기존 JS 테스트의 처리 방식을 바꾸지 않으려고 이렇게 나눴습니다. `dist/`는 테스트 대상에서 제외했습니다.
- **package.json**: `build`, `typecheck`, `clean`을 추가했고, `start`를 `node dist/server.js`로, `main`을 `dist/server.js`로 바꿨습니다.
- **개발 의존성 추가**: typescript 5.7.3, ts-jest 29.4.15, @types/express 4.17.25, @types/jest 29.5.14, @types/node 22.20.5. 런타임 패키지 69개는 lockfile 기준으로 버전 변화가 없습니다. @types/node는 원래 jest를 통해 26.x가 들어와 있었는데, 실제 Node 버전에 맞춰 22로 고정했습니다.
- **CI**: 기존 단계는 그대로 두고 맨 뒤에 `npm run typecheck`와 `npm run build`만 추가했습니다.

## 3. 결과
맨 위에 적은 대로입니다. 타입을 맞추면서 조건식이 바뀐 곳이 두 군데 있는데(`validate`의 `typeof` 검사 추가, `pricing`의 쿠폰 조회), 둘 다 원래 구현과 직접 대조했습니다. `validate`는 3,385가지 입력(예외 메시지 포함), `pricing`은 60가지 입력에서 결과가 같았습니다.

## 4. `any` 및 `TODO(ts)`
- 직접 쓴 `any`: 0개. `req.body`는 Express 타입상 `any`이지만 받자마자 값이 `unknown`인 필드로 받았습니다.
- `TODO(ts)`: 3개 — `src/types.ts:23`(`Order.coupon`이 `unknown`), `src/validate.ts:8`, `src/services/pricing.ts:16`.
- 그 밖의 타입 단언: 검증이 끝난 지점에서 `items as LineItem[]`(`src/routes/orders.ts:21`), 앞에서 이미 걸러진 경우에 대한 `rate!`(`src/services/pricing.ts:26`). 둘 다 이유를 주석으로 남겼습니다.

## 5. 발견했지만 고치지 않은 버그 의심 지점 (원래 서버에서 재현됨)
1. **`src/services/pricing.js:9`** — 쿠폰으로 `"toString"`, `"constructor"`, `"__proto__"`처럼 객체가 기본으로 가진 이름을 보내면 "없는 쿠폰"으로 걸러지지 않습니다. 그 결과 201 응답에 `discount: null, total: null`(계산 결과가 NaN)인 주문이 저장됩니다.
2. **`src/validate.js:4`** — `items: [null]`을 보내면 TypeError가 나서 500이 되고, `"Cannot read properties of null..."` 같은 내부 에러 메시지가 그대로 응답에 나갑니다.
3. **`src/app.js:9`** — 에러 미들웨어가 모든 에러의 `message`를 클라이언트에 그대로 내보냅니다(2번과 같은 원인).
4. **`src/routes/orders.js:14`** — 쿠폰이 문자열인지 검사하지 않습니다. `["VIP20"]` 같은 배열도 할인이 적용되고 배열 그대로 저장됩니다. `0`이나 `""`는 쿠폰 없음으로 처리됩니다.
5. **`src/routes/orders.js:20-22`** — `?status=a&status=b`처럼 status를 두 번 주면 배열과 비교하게 되어 항상 `[]`가 나옵니다.

## 사람이 결정해야 할 항목
- **배포 절차(가장 중요)**: 이제 `npm start` 전에 `npm run build`가 필요합니다. 빌드에는 typescript(개발 의존성)가 필요하므로, CI에서 빌드한 `dist`를 배포하거나 배포 쪽에서 빌드 단계를 추가해야 합니다. 저장소에 배포 설정이 없어서 확인하지 못했습니다.
- **strict 모드**: `strict`가 켜지면 빌드 결과물 전체에 `"use strict"`가 붙습니다. 지금 코드에는 strict 모드에서 동작이 달라질 패턴이 없고 응답 비교도 같았지만, 앞으로 옮길 코드가 있다면 같은 점을 확인해야 합니다.
- **5번 버그 수정 여부**: 고치면 응답 동작이 바뀌므로 클라이언트 영향을 보고 결정해야 합니다.