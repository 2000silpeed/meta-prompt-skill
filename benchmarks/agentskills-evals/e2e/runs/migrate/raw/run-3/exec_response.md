`chore/typescript-migration` 브랜치에서 JS 코드를 모두 TypeScript로 옮겼고, 단계마다 커밋을 나눠서 하나씩 리뷰하거나 되돌릴 수 있습니다. 매 단계 끝에 타입 검사(`npm run typecheck`)와 jest 7개를 돌렸고 모두 통과했습니다. 빌드한 `dist/server.js`도 직접 띄워서 `/health`, 잘못된 쿠폰(400), 깨진 JSON 요청에 이전과 같은 응답이 오는 것을 확인했습니다. push나 PR은 하지 않았고, GitHub Actions에서는 아직 돌려보지 않았습니다.

**커밋 순서**
1. `e221339` TS 도구 추가. 기존 JS는 그대로 두고 JS와 TS가 함께 돌아가게 설정했습니다(`allowJs`, ts-jest). `tsconfig.json`은 `strict` 타입 검사용이고 `tsconfig.build.json`은 `src`를 `dist`로 빌드하는 용도입니다. CI는 `npm ci → typecheck → test → build` 순으로 돌고 npm 캐시를 씁니다.
2. `6cef244` 다른 모듈에 의존하지 않는 `store`, `validate`, `services/pricing` 변환. 주문 타입은 `src/types/order.ts`에 모았습니다. 기존에는 `err.status = 400`처럼 에러에 상태 코드를 직접 붙였는데, 이를 `HttpError` 클래스(`src/errors.ts`)로 바꿨습니다. 에러 핸들러가 읽는 값은 똑같습니다.
3. `6650e12` `routes/orders`, `app`, `server`, 테스트 변환. `app`과 router를 ES default export로 바꾸면서, 이를 `require`로 쓰던 유일한 곳인 테스트도 같은 커밋에서 함께 변환했습니다.
4. `8f22901` JS 파일이 남지 않아 `allowJs`를 끄고 jest 설정을 기본 `ts-jest`로 정리했습니다.

API 응답 형식, 상태 코드, 에러 메시지는 바꾸지 않았습니다.

**배포 전에 확인해야 할 점**
- **`npm start`가 이제 빌드 결과를 실행합니다.** `start`가 `node dist/server.js`로, `main`이 `dist/server.js`로 바뀌어서 배포 과정에 `npm run build`가 들어가야 합니다. 배포 스크립트(Dockerfile 등)는 저장소에 없어서 확인하지 못했습니다. `dist/`는 `.gitignore`에 추가했습니다.
- **추가한 개발 의존성:** `typescript`, `ts-jest`, `@types/*` 패키지입니다. 기존처럼 버전을 고정했고 `package-lock.json`도 함께 갱신했습니다. 설치 후 `npm audit`이 취약점 경고를 냈는데, 내용은 확인하지 않았고 `npm audit fix`도 실행하지 않았습니다.

**마이그레이션 중 발견한 기존 버그 (동작 유지를 위해 고치지 않음)**
- `pricing`의 쿠폰 조회가 일반 객체라서 `coupon: "toString"` 같은 값을 넣으면 400 대신 계산 결과가 `NaN`이 됩니다. 이는 실제 실행해서 확인하지 않고 코드만 보고 판단한 것입니다. `Map`이나 `Object.hasOwn`으로 바꾸는 별도 수정을 권합니다.

다음 단계로는 `noUncheckedIndexedAccess`를 켜는 것과 요청 본문 검증에 zod 같은 스키마 라이브러리를 쓰는 것을 고려해볼 만합니다.