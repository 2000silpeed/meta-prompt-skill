# 작업 인계

## 변경 사항

- `parse_time`이 명시적 offset/Z를 요구하고 실제 UTC instant로 변환하도록 수정했다.
- 할인 배분과 취소 환불을 부동소수점 없이 계산하고, 동일 remainder는 SKU 오름차순으로 처리하며 bool 수치를 거부한다.
- 재고 예약의 선검증을 추가해 부족 재고 실패 시 원본 stock을 보존한다.
- `OrderBook` 입력과 snapshot을 깊은 복사하고, 이벤트 처리를 복제 상태에서 수행해 실패 시 만료를 포함한 모든 변경을 롤백한다.
- TTL 경계(`expires_at <= at`), 예약 전체 취소 규칙, 확인 주문의 부분 취소·누적 환불, 주문 ID 재사용 금지를 계약대로 구현했다.
- 이벤트 fingerprint가 dict 키 순서를 무시하고 시간을 UTC로 정규화하도록 했으며, 중복 검사를 시간 역행과 만료보다 먼저 수행한다.
- `replay`가 실제 UTC timestamp 기준으로 stable sort하도록 수정했다.

## 실제 검증

- `python -m unittest -v tests.test_public`: 공개 테스트 6개 모두 통과.
- `python -m compileall -q shop`: 성공.
- `python -m json.tool completion.json >/dev/null && python -m unittest -q tests.test_public`: completion JSON 유효, 공개 테스트 6개 재통과.
- `python - <<'PY' ... PY` 자체 계약 검증 2회: 시간 파싱, 정확한 할인/환불, 재고 원자성, alias 격리, fingerprint 정규화, TTL 경계 롤백/후속 만료, 예약 부분 취소 거부, 실패 ID 재사용, 누적 환불 보존, 역순 replay를 검증했고 모두 통과.

## 한계

- 알려진 남은 실패나 한계 없음.
