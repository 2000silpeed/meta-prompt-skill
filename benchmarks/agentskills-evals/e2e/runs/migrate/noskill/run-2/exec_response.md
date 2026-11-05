마이그레이션 작업은 끝났습니다. 소스 6개와 테스트 1개를 모두 TypeScript로 옮겼고, 남은 `.js` 소스는 없습니다. 브랜치 `chore/ts-migration`에 커밋 14개를 남겼고, 커밋 하나하나를 다시 꺼내서 확인한 결과 모두 타입체크·jest 7/7·빌드·실서버 스모크가 통과합니다. push, PR, 머지는 하지 않았습니다.

**배포 전에 꼭 확인할 것:** `npm start`가 이제 `node dist/server.js`를 실행합니다. 따라서 배포 과정에서 `npm start` 전에 `npm ci`(devDependencies 포함)와 `npm run build`가 실행돼야 합니다. 그렇지 않으면 서버가 뜨지 않습니다. 저장소에 Dockerfile/Procfile/PM2 설정이 없어서 실제 배포 환경은 확인하지 못했습니다. 실행 명령(`npm start`) 자체는 그대로라서 "배포 방식을 크게 바꾸는 경우"로 보지 않고 진행했습니다.

## 1. 바꾼 설정 파일
| 파일 | 내용과 이유 |
|---|---|
| `tsconfig.json` | 타입체크용. `allowJs`, `strict`, CommonJS 유지, `esModuleInterop`, src와 tests 포함, jest 타입 포함 |
| `tsconfig.build.json` | 운영 빌드용. `src` → `dist`, jest 타입 제외 |
| `jest.config.js` | `.ts`는 **ts-jest**로 실행합니다. 빌드와 같은 tsc 컴파일러를 쓰므로 CommonJS 변환 결과가 운영 코드와 같고, 테스트 코드도 타입체크됩니다. 프로젝트가 작아서 swc의 속도 이점은 의미가 없습니다. `.js`는 원래 기본값이던 babel-jest를 그대로 유지했습니다. |
| `package.json` | `build`, `typecheck`, `dev`(`tsx watch src/server.ts`)를 추가했습니다. `start`와 `main`은 `dist/server.js`를 가리키게 했고, 빌드 전에 `dist`를 지우는 `prebuild`를 넣었습니다. devDependencies는 버전을 고정해서 추가했습니다(기존 방식과 동일). `@types/express`는 Express 4에 맞춰 v4를 썼습니다. |
| `.github/workflows/ci.yml` | `npm run typecheck`와 `npm run build` 단계를 추가했고, 테스트 단계는 그대로입니다. |
| `.gitignore` | `dist/` 추가 |

## 2. 변환한 파일과 남은 파일
- **변환한 파일:** `store`, `validate`, `services/pricing`, `routes/orders`, `app`, `server`, `tests/orders.test`. 새로 만든 파일은 `src/types/order.ts`, `src/types/http.ts`입니다.
- **커밋 방식:** 파일마다 이름만 바꾸는 커밋(`git mv`, `@ts-nocheck` 한 줄만 추가)과 타입을 적용하는 커밋을 나눴습니다. 파일이 작아서 한 커밋에 하면 git이 rename으로 인식하지 못했기 때문입니다. 지금은 `git log --follow`로 히스토리가 `initial`까지 이어집니다.
- **CommonJS 유지:** `module.exports = x`는 `export =`로 옮겼습니다. 빌드된 JS가 원본과 같은 구조인 것을 직접 확인했습니다.
- **`types/express.d.ts`는 만들지 않았습니다.** `req.user` 같은 Express 확장 속성을 쓰는 곳이 없기 때문입니다.
- **남은 파일:** 없습니다. `MIGRATION_PLAN.md`도 최신 상태로 갱신했습니다.

## 3. 테스트 결과와 기준선 비교
- 기준선은 7/7 통과였고, 변경 전부터 실패하던 테스트는 없었습니다. 지금도 7/7 통과입니다.
- assertion은 한 줄도 바꾸지 않았습니다(diff로 확인).
- 테스트가 덮지 못하는 부분은 변경 전 서버로 요청 26개(엣지 케이스 포함)의 응답을 녹화해 두고 매 커밋마다 비교했습니다. 모든 커밋에서 바이트 단위로 같았습니다.

## 4. 잠재 버그(TODO)와 단언 사용
**TODO(ts-migration) — 고치지 않고 표시만 했습니다:**
- `coupon:"toString"`을 보내면 201이 나고 `discount`와 `total`이 `null`입니다. 프로토타입 키도 쿠폰으로 조회되기 때문입니다.
- `coupon:["WELCOME10"]`처럼 배열을 보내도 할인이 적용되고, 쿠폰이 배열 그대로 저장됩니다. 그래서 `Order.coupon` 타입과 실제 저장값이 다를 수 있습니다.
- `items:[null]`을 보내면 400이 아니라 500이 나고, 내부 TypeError 메시지가 응답에 그대로 노출됩니다.
- 에러 핸들러는 500 에러의 메시지를 그대로 응답하고, `err.status`가 유효한 코드인지 검사하지 않습니다.
- `GET /orders?status=a&status=b`처럼 status를 배열로 보내면 항상 빈 배열이 나옵니다.

**`as` 단언 4곳 — 모두 이유를 주석으로 남겼고 `any`와 eslint-disable은 쓰지 않았습니다:**
- `validate.ts`: 항목이 객체인지 검사를 추가하면 null 항목의 500 응답이 바뀌므로, 검사 대신 단언했습니다.
- `orders.ts`: 검증을 통과한 `items`와 `coupon`에 각각 단언했습니다. `validateItems`가 메시지를 반환하는 함수라서 타입을 자동으로 좁혀 주지 못하기 때문입니다.
- `app.ts`: 에러 핸들러의 `err`. 원래 코드처럼 형태를 검증하지 않고 읽기 위해 단언했습니다.

**동작은 같지만 코드 모양이 바뀐 곳:**
- `pricing`의 쿠폰 조회를 if 블록으로 다시 썼고, 키를 `String(coupon)`으로 바꿨습니다.
- `validate`에 `typeof qty` 검사를 추가했습니다. 숫자가 아니면 `Number.isInteger`도 false라서 결과는 같습니다.
- tsc가 출력 JS에 `"use strict"`를 붙입니다. 코드를 검토해 보니 sloppy 모드에 의존하는 부분은 없었습니다.

## 5. 다음 실행에서 할 일
1. `allowJs`와 jest의 `.js` 규칙을 제거합니다.
2. ESLint와 `@typescript-eslint`를 도입할지 검토합니다.
3. `.nvmrc` 또는 `engines`를 추가할지 검토합니다(현재 기준은 CI의 Node 22뿐입니다).
4. 위 TODO 버그는 마이그레이션과 분리해서 별도 PR로, 테스트와 함께 고칩니다.

## 6. 직접 확인하지 못한 것
- **실제 운영 배포 환경:** 배포 설정이 저장소에 없어서 확인하지 못했습니다.
- **GitHub Actions 실제 실행:** push하지 않았기 때문에 돌려 보지 못했습니다. 대신 새 클론에서 CI와 같은 순서(`npm ci` → typecheck → test → build)로 실행해 통과를 확인했습니다.
- **`npm audit` 경고:** 설치할 때 나왔지만 내용은 확인하지 않았습니다.