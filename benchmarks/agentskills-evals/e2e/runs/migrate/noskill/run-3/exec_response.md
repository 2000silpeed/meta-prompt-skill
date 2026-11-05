0단계(조사)와 1단계(기반 설정)는 끝냈고, **2단계 파일 변환은 시작하기 전에 멈췄습니다.** 지금 구조에서는 src 파일을 하나라도 `.ts`로 바꾸면 `npm start`(`node src/server.js`)가 깨지기 때문입니다. 실행 방식을 바꾸지 않는다는 조건과 함께 맞출 수 없어서 멈춤 조건에 해당한다고 판단했습니다. 지금 작업 트리는 깨끗하고, 커밋은 두 개 추가됐습니다.

- `f87ccf4` build(ts): TypeScript 기반 설정
- `a973a93` docs(ts): `MIGRATION.md`

## 왜 멈췄는가
src 아래 6개 파일은 모두 `node src/server.js`가 실제로 불러오는 경로에 있습니다. 스크래치패드에서 실험해 보니 이렇습니다.
- `store.js`를 `store.ts`로 바꾸면 JS 쪽 `require('./store')`가 파일을 찾지 못해 **MODULE_NOT_FOUND**로 실패합니다.
- `require('./store.ts')`처럼 확장자를 쓰면 Node 22.23에서는 동작합니다. 하지만 JS의 require 경로를 고쳐야 하고, 운영 Node 버전에 기대야 합니다.

`MIGRATION.md` §7에 네 가지 선택지를 정리했습니다. 권장하는 쪽은 **A안**입니다.
- **A안:** 파일 변환보다 `tsc` 빌드 후 `node dist/server.js`로 실행하는 전환을 먼저 합니다. `allowJs` 설정 덕분에 JS 파일도 `dist/`로 함께 복사되므로, 코드를 하나도 바꾸지 않은 상태에서 실행 방식만 따로 검증하고 바로 되돌릴 수 있습니다.
- 원래 계획(진입점까지 변환한 뒤 전환)과 순서가 반대라서, 결정은 맡기겠습니다.

## 완료 보고
**1. 변환한 파일:** 없습니다. 남은 JS 파일은 7개(src 6개, tests 1개)입니다.
- 1단계에서 설치한 것: typescript 6.0.3, ts-jest 29.4.15, @types/node@22, @types/express@4, @types/jest@29, @types/supertest. 모두 버전을 정확히 고정했습니다.
- 추가한 파일과 설정: `tsconfig.json`(`allowJs`, `checkJs: false`, `strict`, `module: node16`, `outDir: dist`), `jest.config.js`, `src/types/express.d.ts`, `typecheck` 스크립트, CI의 typecheck 단계, `.gitignore`의 `dist/`
- TS 최신은 7.x지만 ts-jest가 TS 7을 지원하지 않아서 6.x를 골랐습니다.
- jest에는 **ts-jest**를 골랐습니다. 이 저장소에서 가장 조심해야 할 부분이 CJS interop(`export =` 등)인데, ts-jest는 실제 빌드와 같은 `tsc`로 처리합니다. 테스트가 7개뿐이라 swc의 속도 이점도 의미가 없습니다.
- 코드에 `req`/`res` 커스텀 속성이 없어서 `express.d.ts`는 예시 주석만 담은 빈 틀로 두었습니다.

**2. 마지막 실행 결과**
- `npm run typecheck`: exit 0, 오류 없음
- `npm test`: Suites 1/1, Tests 7/7 통과. 작업 전에 6번 돌린 기준 결과와 같고, flaky는 없었습니다.
- lint: **저장소에 lint 설정이 없어 실행하지 못했습니다.**
- `npm start` 후 `/health` 응답 `{"ok":true}`를 확인했습니다.
- 설정이 실제로 동작하는지도 임시 파일로 확인했고, 확인 뒤 지웠습니다. tsc가 strict 위반을 잡고, jest가 `.ts` 테스트를 실행합니다.

**3. `any` / `TODO(ts-migration)` / `@ts-expect-error`:** 0건입니다.

**4. 잠재 버그 (고치지 않음, 전부 재현 확인. 자세한 내용은 `MIGRATION.md` §9)**
- `items: [null]`을 보내면 500이 나고 내부 에러 메시지가 응답에 그대로 나갑니다.
- 쿠폰으로 `"toString"`이나 `"__proto__"`를 보내면 201이 나오고 `total: null`이 됩니다.
- 쿠폰이 배열이어도 할인이 적용됩니다.
- 처리되지 않은 예외가 나면 500 응답에 원래 에러 메시지가 그대로 노출됩니다.
- `?status=a&status=b`처럼 status를 두 번 주면 항상 `[]`가 나옵니다.
- 소수 가격을 넣으면 `0.30000000000000004` 같은 값이 나옵니다.
- 이미 취소된 주문을 다시 취소해도 200이 나옵니다.
- store가 내부 객체를 참조로 그대로 돌려줍니다.
- `qty`/`price` 상한을 검사하지 않습니다.
- 설치 전부터 있던 `npm audit` 경고(express 4 계열 body-parser, qs, path-to-regexp)도 손대지 않았습니다.

**5. 다음 묶음과 빌드/배포 전환 계획**
- 실행 방식이 정해지면 다음 순서로 진행합니다. 말단 3개(`store`, `validate`, `services/pricing`) → `routes/orders` → `app`/`server` → 테스트.
- 지켜야 할 점이 두 가지 있습니다.
  - `module.exports = X`로 내보내는 파일은 `export =`로 바꿔야 합니다. `export default`로 바꾸면 JS 쪽 `require`가 깨집니다.
  - 에러 핸들러는 인자 4개를 유지해야 합니다. Express가 인자 개수로 에러 핸들러를 구분합니다.
- 빌드/배포 전환 계획은 §8에 적었고, 실제 변경은 하지 않았습니다.

**6. 결정이 필요한 사항**
1. 실행 방식 전환 시점과 방법(§7의 A~D). 이게 정해져야 2단계를 시작할 수 있습니다.
2. lint를 들일지 여부. 지금은 "lint 통과" 조건을 확인할 수 없습니다.
3. routes를 변환하기 전에, 테스트가 없는 동작에 대한 테스트를 추가할지. 대상은 목록·status 필터, ship 성공, 잘못된 JSON, 500 경로입니다.
4. 검증을 통과한 `items`의 타입을 어떻게 좁힐지. 캐스트를 쓰는 방법과 type-guard 래퍼를 두는 방법이 있습니다(§5).
5. 운영 Node 버전과 배포 방식 확인. 이 저장소에서는 Dockerfile이나 PM2 설정을 찾지 못했습니다.

작업 요청에 남아 있던 빈칸([버전], [배포 방식], [작업 범위])은 저장소에서 확인한 값으로 채웠습니다. 예로 든 `src/utils`, `src/lib`는 이 저장소에 없습니다.