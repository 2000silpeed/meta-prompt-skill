변경 사항

- `parse_time`이 명시적 timezone offset/Z를 검증하고 UTC로 변환하도록 수정했다.
- 할인 배분과 환불 계산을 정확한 정수 산술로 수정하고, 동률 SKU 정렬 및 bool 입력 거부를 반영했다.
- 재고 예약의 사전 검증을 보강해 실패 시 부분 차감이 없도록 했다.
- 주문 엔진에 UTC 정규화 fingerprint, 깊은 복사 기반 원자적 apply, 경계 포함 만료, 예약 전량 취소, 확인 주문 환불, 깊은 복사 snapshot, UTC 기준 replay 정렬을 구현했다.

검증

- `python -m unittest discover -s tests -v` (6 tests, 모두 통과)
- 별도 Python focused checks (시간대/naive 거부, 할인·환불 산술, TTL 경계 원자성, 만료, alias 방지) 통과

한계

- 제공된 공개 테스트와 표준 라이브러리 기반 focused checks만 실행했으며 평가용 테스트 결과는 확인하지 않았다.
