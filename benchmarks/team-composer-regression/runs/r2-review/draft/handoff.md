# 제작 초안 완료

공개 API와 CONTRACT.md를 확인하고 shop 모듈을 수정했다. 함수명과 시그니처, 공개 계약 및 기존 테스트는 유지했다.

## 변경
- clock: 명시적 시간대가 없는 입력을 거부하고 astimezone으로 실제 instant를 UTC로 변환한다.
- money: bool 수치를 거부하고, 큰 정수에도 정확한 할인 비례 배분 및 SKU 오름차순 동률 처리를 적용했다. 환불은 누적 floor 차이로 계산한다.
- inventory: reserve는 전 SKU의 재고 충분 여부를 검사한 다음 차감한다. release의 사전 검증 동작을 검토했다.
- engine: 초기 입력과 snapshot의 깊은 복사를 보장한다. 정규화한 UTC 시간과 정렬한 dict 키로 전체 이벤트 fingerprint를 만들며 중복 검사를 시간 역행보다 먼저 수행한다. 별도 복사본에서 만료 및 이벤트를 적용하고 성공 시에만 상태를 교체한다. reserved만 TTL 이하 경계에서 만료하며 reserved 부분 취소를 거부한다. replay는 UTC instant를 기준으로 안정 정렬한다.
- __init__: 기존 OrderBook, replay export를 확인했으며 변경할 필요가 없었다.
- tests/test_regression.py: 추가 회귀 테스트 12개를 작성했다.

## 실제 검증
- `python3 -m unittest discover -s tests -v`: 공개 6개 + 추가 12개, 총 18개 통과.
- `python3 -m unittest discover -s tests -p test_regression.py -v`: 추가 12개 통과.

큰 정수 할인, 동률 SKU 정렬, 환불 총합 보존, 잘못된 입력의 ValueError, 재고 원자성, caller 및 snapshot 별칭 격리, TTL 경계 실패 롤백, 실패 id 재사용, confirmed TTL 면제, 누적 부분 환불, 예약 전체 취소, UTC 중복 정규화, 오래된 재전송, replay 동시각 순서와 입력 불변성을 검사했다.

## 한계
알려진 계약 미충족 사항은 없다. 비공개 평가 자료에는 접근하지 않았으며 공개 계약과 자체 테스트에 기반한 검증이다. 다중 스레드, DB, 네트워크는 계약 범위 밖이다.
