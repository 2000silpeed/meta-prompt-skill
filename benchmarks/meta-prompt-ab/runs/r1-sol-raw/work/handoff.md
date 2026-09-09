# 변경 사항

- `shop.clock.parse_time`이 명시적 offset 또는 `Z`가 있는 ISO 날짜·시각만 받고, 실제 instant를 보존해 UTC로 변환하도록 수정했다.
- 할인 배분과 환불 증분을 부동소수점 없이 정확한 정수 연산으로 구현했다. 할인 잔여 단위의 동률은 SKU 오름차순으로 처리하며 모든 수치 인자에서 bool을 거부한다.
- 재고 입력을 엄격히 검증하고, `reserve`가 모든 재고 충분 여부를 확인한 뒤에만 차감하도록 원자성을 보장했다.
- `OrderBook`이 초기 입력 및 snapshot과 내부 상태를 공유하지 않게 했다. 이벤트는 복제한 상태에 만료와 동작을 모두 적용한 뒤 성공할 때만 커밋한다.
- TTL 경계(`expires_at <= at`), 확인 후 TTL 제외, 예약 상태의 전량 취소 제한, 확인 주문의 SKU별 누적 환불, 주문 ID 재사용 금지를 구현했다.
- 이벤트 fingerprint는 전체 JSON payload를 키 순서와 무관하게 직렬화하고 `at` 및 reserve의 `expires_at`을 UTC로 정규화한다. 성공 이벤트의 정확한 재전송은 시간 역행 검사보다 먼저 no-op 처리한다.
- `replay`가 입력을 복제한 뒤 UTC 시각 순서와 동일 시각의 원래 입력 순서로 안정 정렬하도록 수정했다.
- `tests/test_contract_additional.py`에 계약의 경계값, 원자성, 중복, alias 방지, 환불 및 replay 정렬 검증 9개를 추가했다.

# 실제 검증

- `python3 -m unittest discover -s tests -v`: 공개 테스트 6개와 추가 테스트 9개, 총 15개 모두 통과.
- `python3 -m py_compile shop/__init__.py shop/clock.py shop/engine.py shop/inventory.py shop/money.py tests/test_contract_additional.py tests/test_public.py`: 성공(출력 없음).

# 한계

- 다중 스레드 안전성, DB, 네트워크는 계약 범위 밖이므로 구현하지 않았다.
