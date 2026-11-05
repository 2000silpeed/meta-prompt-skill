Express API 서버의 소스 6개와 테스트 1개를 모두 TypeScript(`strict`)로 바꿨습니다. CI와 같은 순서(`npm ci` → typecheck → test → build)로 돌려보니 기존 jest 테스트 7개가 모두 통과했습니다. 빌드한 결과물로 서버를 띄워 실제 요청도 몇 개 보내봤는데 응답이 예전과 같았습니다. 변경 사항은 커밋하지 않고 작업 트리에만 두었습니다.

## 진행 방식
의존성이 없는 파일부터 하나씩 옮겼고, 한 파일을 바꿀 때마다 typecheck와 테스트를 돌렸습니다.

1. **TS 도구만 먼저 추가**: 이 단계에서는 JS 코드를 건드리지 않았습니다. `allowJs`를 켜서 JS와 TS 파일이 섞여 있어도 빌드와 테스트가 되는 상태로 시작했습니다.
2. **변환 순서**: `store` → `validate` → `pricing` → `routes/orders` → `app` → `server` → 테스트. 중간에 JS와 TS가 섞여 있던 단계에서도 매번 테스트가 통과했습니다.
3. **마무리**: 변환이 끝난 뒤 `allowJs`를 꺼서 앞으로 JS 파일이 다시 들어오지 않게 했습니다.

## 주요 변경
- **추가한 개발 의존성**: `typescript@5.9.3`, `ts-jest`, `@types/*`. 버전은 기존처럼 정확히 고정했습니다. TypeScript 최신은 7.x지만 ts-jest 29가 `<7`만 지원해서 5.9를 썼습니다.
- **설정 파일**:
  - `tsconfig.json`: 타입 검사용입니다. `src`와 `tests`를 함께 검사합니다.
  - `tsconfig.build.json`: `src`를 `dist/`로 CommonJS로 빌드합니다.
  - `jest.config.js`: ts-jest를 쓰기 때문에 타입 에러가 있으면 테스트도 실패합니다.
- **스크립트**: `build`, `typecheck`를 추가했습니다. `start`는 이제 `node dist/server.js`를 실행합니다.
- **CI** (`.github/workflows/ci.yml`): typecheck와 build 단계, npm 캐시를 추가했습니다. 타입 에러를 일부러 넣어보니 typecheck와 jest 둘 다 실패로 잡아냈습니다.
- **새 파일**:
  - `src/types/order.ts`: 주문 관련 타입입니다.
  - `src/errors.ts`: 기존의 `err.status = 400` 처리를 `HttpError` 클래스로 바꿨습니다. 응답은 예전과 같습니다.
- **동작 보존**: 동작은 바꾸지 않았습니다. 예를 들어 `items`에 `null`이 들어오면 예전처럼 500을 반환합니다.

## 확인이 필요한 점
1. **배포 절차가 바뀝니다.** 이제 `npm start` 전에 `npm run build`가 꼭 필요합니다. 서버에서 devDependencies를 빼고 설치한다면 `tsc`가 없으니 빌드를 CI나 Docker 빌드 단계에서 미리 해야 합니다. 배포 설정은 저장소에 없어서 손대지 않았습니다.
2. **원래 있던 버그를 하나 발견했고 그대로 두었습니다.** 쿠폰 값으로 `"constructor"`나 `"toString"`처럼 객체의 기본 속성 이름을 보내면 400 "unknown coupon"이 나와야 하는데, 실제로는 할인 금액과 총액이 `NaN`인 주문이 만들어집니다 (`src/services/pricing.ts`의 `COUPONS[coupon]` 조회). 마이그레이션에서는 동작을 그대로 유지하는 게 원칙이라 고치지 않았습니다. `Object.hasOwn(COUPONS, coupon)`로 확인하도록 바꾸면 한 줄로 고칠 수 있으니, 별도 PR로 따로 고치길 권합니다.

리뷰하기 쉽게 커밋을 나눈다면 "TS 도구와 CI 추가"와 "모듈 변환" 두 개로 나누는 것이 좋겠습니다.