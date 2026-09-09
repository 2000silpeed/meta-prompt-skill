# Handoff

## 변경 사항

- `parse_time`이 명시적 offset/Z를 검증하고 실제 instant를 UTC로 변환하도록 수정했다.
- 할인 배분과 취소 환불을 정확한 정수 산술로 구현하고, 할인 나머지 동률을 SKU 오름차순으로 처리하며 bool 수치를 거부한다.
- 재고 예약은 충분한 재고를 전부 확인한 뒤 차감하여 실패 시 원자성을 보장한다.
- `OrderBook`이 caller 입력과 snapshot을 깊은 복사하고, 이벤트를 복제 상태에 적용한 뒤 성공할 때만 commit하도록 수정했다.
- TTL 경계(`expires_at <= at`), reserved 주문만의 만료, reserved 전체 취소 제한, confirmed 부분 환불 누적을 계약에 맞췄다.
- 이벤트 fingerprint의 키 순서를 무시하고 `at`/reserve `expires_at`을 UTC로 정규화했다. 중복 판정을 시간 역행 및 만료보다 먼저 수행한다.
- `replay`가 문자열 표기가 아닌 UTC instant로 안정 정렬하도록 수정했다.
- 계약의 주요 경계 조건을 검증하는 `tests/test_contract_edges.py`를 추가했다.

## 실제 검증

- `python -m unittest -v tests.test_public tests.test_contract_edges` — 12개 테스트 모두 통과.
- `python -m compileall -q shop tests` — 성공(종료 코드 0).

## 남은 한계

알려진 한계나 남은 실패 없음.
