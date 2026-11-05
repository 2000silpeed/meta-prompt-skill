# TypeScript 점진 전환 결과 보고

인프라 구축과 말단 모듈 3개(`validate`, `store`, `services/pricing`) 전환을 마쳤습니다. 두 브랜치 모두 `npm ci`부터 test, typecheck, build, test:dist까지 7/7로 통과합니다. 라우트, 상태 코드, 응답, 에러 포맷, 미들웨어 순서는 바뀌지 않았습니다. 다만 **배포 진입점을 `dist/`로 옮기는 결정이 아직 남아 있습니다.** 저장소만으로는 배포 방식을 확인할 수 없어서, 진입점을 바꾼 커밋과 모듈 전환 커밋은 별도 브랜치에 두었습니다.

```
master (a0afcbe, 변경 없음)
└─ ts-migration          ← Phase 2 인프라. 실행 진입점은 그대로(node src/server.js)
   └─ ts-migration-phase3 ← 진입점을 dist로 변경 + 말단 모듈 3개 전환 (사람 결정 필요)
```
push와 PR은 하지 않았고 로컬 커밋만 있습니다.

## 1. 조사 요약과 기준선
- **실행·배포:** Express **4.21.2**, jest 29.7.0, supertest 7.0.0, npm(`package-lock.json`). `engines`, `.nvmrc`, Dockerfile, Procfile은 없습니다. 실행은 `main`/`start` = `node src/server.js`이고, 배포 설정은 저장소에 없습니다.
- **모듈 시스템:** CommonJS만 씁니다(`require`/`module.exports`). `"type"` 필드는 없습니다.
- **jest:** 별도 설정이 없어 기본값(babel-jest, babel 설정 없음)으로 돕니다. 테스트는 supertest로 `app`을 메모리 안에서 띄웁니다. 외부 연동이나 DB는 없고 저장소는 메모리 Map입니다.
- **CI:** job `test` 하나, Node 22, `npm ci` 후 `npm test`. lint와 build 단계는 없습니다.
- **의존성 그래프:** `validate`, `store`, `services/pricing`(말단) → `routes/orders` → `app` → `server`. 순환 require는 없습니다.
- **런타임 경로 의존:** `__dirname`, 정적 파일, 동적 require는 없습니다. 환경 변수는 `process.env.PORT` 하나이고 `.env` 파일은 없습니다.
- **기준선:** `npm test` 7/7 통과. 원래 실패하던 테스트는 없습니다.

## 2. 바꾼 설정과 이유
- **devDependencies (정확한 버전 고정, 기존 관례를 따름):** typescript 5.9.3, ts-jest 29.4.15, @types/express **4.17.25**(Express 4에 맞춤), @types/node 22.20.5(CI의 Node 22에 맞춤). jest가 간접으로 끌어오던 dev 전용 `@types/node`는 26.x에서 22.x로 바뀌었습니다. 런타임 의존성은 그대로입니다.
- **tsconfig.json**
  - `module`/`moduleResolution: node16`: `"type"` 필드가 없어서 CJS로 해석됩니다. Node의 실제 해석 방식과 같습니다.
  - `allowJs`, `checkJs: false`로 기존 JS를 그대로 받습니다. `esModuleInterop`도 켰습니다.
  - `strict: true`로 시작했고 **낮춘 옵션은 없습니다.**
  - `isolatedModules: true`: ts-jest가 node16 모듈과 함께 쓸 때 요구합니다(경고 TS151002). 그래서 jest는 파일 단위로 변환만 하고, 타입 검사는 CI의 `tsc --noEmit`가 맡습니다.
  - 출력은 `rootDir: src`에서 `outDir: dist`로 갑니다. 소스맵도 켰습니다.
- **jest transform은 ts-jest를 골랐습니다.** 기존 JS 모듈이 `require`하는 동안에는 `export =`가 필요한데, babel의 TS 프리셋은 `export =`를 지원하지 않습니다. 저장소에 babel 설정도 없었습니다. `transform`을 지정하면 jest의 기본 babel-jest가 꺼지기 때문에, `.js`용 babel-jest를 명시적으로 남겼습니다(`jest.mock` 호이스팅 유지).
- **새 스크립트:**
  - `typecheck`, `build`(dist를 지운 뒤 tsc)
  - `test:dist`: 기존 테스트를 **수정 없이** 빌드 결과에 대해 돌립니다(`jest.dist.config.js`의 moduleNameMapper 사용). src 폴더를 잠시 치운 상태에서도 7/7이 통과해, 매핑이 실제로 적용되는 것을 확인했습니다.
- **CI:** 기존 단계는 그대로 두고 `typecheck` → `build` → `test:dist`를 뒤에 추가했습니다. `.gitignore`에 `dist/`를 추가했습니다.
- **phase3 브랜치에서만:** `start`/`main`을 `dist/server.js`로 바꿨습니다.

## 3. 전환 현황
- **전환 완료 (각각 별도 커밋, `export =`로 CJS export 형태 유지):**
  - `src/validate.ts`
  - `src/store.ts`
  - `src/services/pricing.ts`
  - 새로 만든 공용 타입: `src/types/order.ts`(OrderItem, Quote, Order, OrderStatus, NewOrder), `src/types/http.ts`(HttpError)
  - 빌드 결과물은 원본과 비교해 들여쓰기, `"use strict"`, 소스맵 주석만 다릅니다.
- **남은 파일과 권장 순서:** ① `routes/orders.js` → ② `app.js` → ③ `server.js`(그다음 테스트)
  - `app.js`를 옮길 때 에러 핸들러의 인자 4개(`next` 포함)를 반드시 유지해야 합니다.
  - `app`과 `router`를 TS 쪽에서 소비하게 되면 `export =` 대신 `export default`로 바꾸는 작업도 검토할 수 있습니다.
- **`routes/orders.js`에서 멈춘 이유:** `validateItems`는 타입 가드가 아니라 에러 문자열을 돌려줍니다. 그래서 `req.body.items`(unknown)를 `quote(items: OrderItem[])`에 넘기려면 `as` 단언으로 검증된 척하거나(금지 사항), 검증 함수 시그니처를 바꿔야 합니다(결정 사항 2 참고).

## 4. 마지막 검증
두 브랜치 각각에서 `npm ci`로 378개 패키지를 설치한 뒤 실행했습니다.
- `npm test`: 7/7 통과
- `npm run typecheck`: exit 0, 출력 없음
- `npm run build`: exit 0
- `npm run test:dist`: 7/7 통과
- `node dist/server.js`를 띄워 `/health`를 호출하니 `{"ok":true}`가 왔습니다.
- **lint는 실행하지 않았습니다.** 저장소에 lint 설정이 없습니다.
- 실제 배포 환경에서는 검증하지 못했습니다.

## 5. any/TODO, 고치지 않은 버그, 결정할 사항
**`any`/TODO는 1곳입니다.** `src/validate.ts:3`의 요청 입력 원소 `it`입니다(`Array.isArray`가 unknown을 `any[]`로 좁힘). 이 외에는 `as` 단언도 `any`도 없습니다.

**고치지 않은 버그 (master 원본에서도 같은 동작을 재현해 기존 버그임을 확인했습니다):**
1. **`coupon: "toString"`, `"constructor"` 같은 프로토타입 키를 보내면 201이 나가고 `discount`/`total`이 `null`입니다.** `COUPONS[coupon]`이 함수를 반환해 계산 결과가 NaN이 되기 때문입니다. TS 타입(`Record<string, number>`)도 이 경우를 가리지 못합니다.
2. **`items: [null]`을 보내면 500과 함께 내부 메시지 `"Cannot read properties of null (reading 'sku')"`가 그대로 노출됩니다.**
3. 문자열이 아닌 `coupon`(숫자, 객체)은 런타임 검증 없이 키로 쓰입니다. 결과는 400이 나옵니다.

**사람이 결정할 사항:**
1. **배포 방식.** 실제 배포가 `npm start`를 쓰는지, build를 실행하는지, devDependencies를 설치하는지 확인해야 합니다. 확인되면 phase3 브랜치를 채택할 수 있습니다. 배포에서 `npm ci --omit=dev`를 쓴다면 이미지를 빌드하는 단계에서 `npm run build`를 먼저 실행해야 합니다.
2. **라우터 전환 방식.** `validateItems`에 타입 가드를 추가할지(예: `isValidItems(x): x is OrderItem[]`), 아니면 별도 런타임 스키마(zod 등)를 도입할지 정해야 합니다. 어느 쪽이든 로직 변경이라 이번 범위에서 제외했습니다.
3. **`"use strict"`.** tsc는 모든 출력 파일(기존 JS 포함)에 `"use strict"`를 붙입니다. 현재 코드에는 strict 모드에서 동작이 달라지는 구문이 없음을 확인했지만, 이후 전환할 파일도 같은 점을 확인해야 합니다.
4. **`req.user` 같은 Request 확장.** 현재 코드에 없어서 declaration merging은 만들지 않았습니다.
5. `package.json`에 `engines`가 없습니다. Node 22로 고정할지 정해야 합니다.

임시로 만든 검증 스크립트, 프로브, worktree, `dist/`는 모두 삭제했습니다. 작업 트리는 깨끗하고, 현재 체크아웃된 브랜치는 `ts-migration-phase3`입니다.