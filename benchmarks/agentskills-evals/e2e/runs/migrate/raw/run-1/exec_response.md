`src/` 전체와 테스트를 TypeScript로 옮겼습니다. 단계마다 커밋을 나눠서 하나씩 리뷰하거나 되돌릴 수 있습니다. 작업은 `chore/typescript-migration` 브랜치에 커밋 4개로 들어 있고, 원격에 push하지는 않았습니다.

## 커밋 순서

1. **`chore: add TypeScript toolchain alongside existing JS`** (소스 변경 없음)
   - `tsconfig.json`: `allowJs`를 켜서 `.js`와 `.ts`를 함께 쓸 수 있게 했습니다. 남은 `.js`는 타입체크하지 않고, 새로 만드는 `.ts`는 처음부터 `strict`로 검사합니다.
   - `tsconfig.test.json`: 테스트까지 포함해 타입체크하는 설정입니다.
   - `jest.config.js`: ts-jest가 `.ts`와 `.js`를 둘 다 변환해서, 두 형식이 섞여 있어도 jest가 돕니다.
   - 스크립트를 `build`(tsc → `dist/`), `typecheck`, `start`(빌드 후 `node dist/server.js`)로 정리했고, `main`은 `dist/server.js`로 바꿨습니다.
   - **CI**: `npm ci` 다음에 `typecheck`, `test`, `build` 순서로 돌고, npm 캐시를 추가했습니다.
2. **의존성이 없는 모듈 변환**: `store`, `validate`, `services/pricing`, 그리고 새 파일 `src/types.ts`(Order, OrderItem, Quote, HttpError 타입)
   - named export라서 아직 JS로 남아 있던 `routes/orders.js`의 `require`도 그대로 동작했습니다.
3. **`routes/orders`, `app`, `server` 변환**
   - 에러 핸들러는 Express가 인자 4개로 에러 핸들러를 구분하므로 4개를 그대로 뒀습니다.
   - `app`은 `export =`로 내보내서, JS에서 `require('./app')`을 하는 코드가 있어도 깨지지 않습니다.
4. **테스트를 `.ts`로 변환**: import 3줄만 바꿨고 검증 내용은 그대로입니다.

## 확인한 것

- 원래 테스트 7개가 **매 단계마다 모두 통과**했습니다.
- `node_modules`를 지우고 CI와 같은 순서(`npm ci` → typecheck → test → build)로 다시 돌려 모두 통과했습니다.
- 빌드한 `dist/server.js`를 `npm start`로 띄우고 health 확인, 주문 생성(쿠폰 적용), 배송 처리, 잘못된 JSON 요청을 직접 보내봤습니다. 응답은 기대한 대로였습니다.
- 타입 에러를 일부러 넣었을 때 `typecheck`가 실패하는 것도 확인했습니다.
- 동작은 바꾸지 않았습니다. 바뀐 건 타입과 import/export 방식뿐입니다.

## 확인이 필요한 부분

- **배포 방식이 바뀝니다**: 이제 실행 대상이 `src/server.js`가 아니라 `dist/server.js`입니다. 배포 스크립트, Dockerfile, PM2 설정처럼 이 저장소 밖에서 `src/server.js`를 직접 실행하는 곳이 있으면 같이 고쳐야 합니다. `npm start`는 시작 전에 자동으로 빌드합니다.
- **기존 버그를 하나 발견했고, 고치지는 않았습니다**: 쿠폰 코드로 `"toString"`처럼 객체에 원래 있는 이름을 보내면, 알 수 없는 쿠폰인데도 400으로 거절되지 않습니다. 그대로 **201로 주문이 생성되고 `discount`와 `total`이 `null`로 저장됩니다**. 직접 요청을 보내 재현했습니다. 이번 작업은 동작을 바꾸지 않는 범위라 그대로 뒀고, `src/services/pricing.ts`의 쿠폰 조회를 `Object.hasOwn(COUPONS, coupon)`으로 확인하게 바꾸면 고쳐집니다.
- 앞으로 JS 파일이 새로 생겨도 `allowJs` 덕분에 그대로 돌아갑니다. 그런 파일은 위에 `// @ts-check`를 붙이면 그 파일만 타입체크할 수 있습니다. 전부 TS가 됐다고 판단되면 `allowJs`를 끄면 됩니다.