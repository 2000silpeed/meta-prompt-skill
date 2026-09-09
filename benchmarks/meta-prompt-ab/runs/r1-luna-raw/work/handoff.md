# Handoff

## 변경 사항

- ISO 8601 timestamp를 명시적 timezone과 함께 UTC aware datetime으로 파싱하도록 수정했다.
- 할인 배분의 동률을 SKU 오름차순으로 처리하고, 환불 증분을 각 취소 구간의 floor 차이로 계산하도록 수정했다.
- 재고 예약의 사전 검증을 추가해 실패 시 부분 차감이 발생하지 않도록 했다.
- OrderBook이 caller 입력과 snapshot에 내부 객체를 공유하지 않도록 깊은 복사를 적용했다.
- 이벤트 적용을 staged 복사본에서 수행해 검증·만료·dispatch 실패 시 상태가 원자적으로 보존되도록 했다.
- 중복 fingerprint에서 키 순서를 무시하고 at/expires_at을 UTC ISO 형식으로 정규화했다.
- reserved 주문의 TTL 경계를 `expires_at <= at`으로 적용하고, confirmed 주문은 TTL 만료 대상에서 제외했다.
- reserved 주문 취소는 전체 수량일 때만 허용하고, replay 정렬은 UTC 시각과 입력 순서를 사용하도록 수정했다.

## 실제 검증

- `python -m unittest discover -s tests -v` (6개 테스트 통과)
- 표준 라이브러리 기반 추가 경계 검증: timezone/naive timestamp, 할인 동률, 환불 누적식, 재고 원자성, 입력·snapshot aliasing, TTL 경계 및 실패 원자성, reserved 부분 취소 거부, normalized duplicate fingerprint

## 한계

- 다중 스레드 안전성, DB, 네트워크는 계약 범위 밖이다.
- 평가용 비공개 테스트 결과는 제공되지 않았다.
