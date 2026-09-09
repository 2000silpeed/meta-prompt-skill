# 변경 및 검증

기존 public API와 계약, 공개 테스트는 유지했습니다.

- clock: 명시적 시간대를 검사하고 UTC로 변환합니다.
- money: bool을 거부하고 정수 비례 할인·SKU 동률 순서·누적 취소 환불을 수정했습니다.
- inventory: 전체 재고 충분 여부를 먼저 확인하여 예약 실패 시 원자성을 보장합니다.
- engine: 입력과 snapshot을 깊은 복사하고, 성공한 staged 상태만 반영합니다. TTL 경계 만료, 확인된 주문의 만료 제외, 예약 부분 취소 거부, UTC 정규화 및 키 순서 무관 중복 판정, 오래된 재전송 허용, UTC 안정 정렬 replay를 수정했습니다.

실제 실행한 검증:

- `python3 -m unittest discover -s tests -v`: 공개 6개 + 추가 9개, 총 15개 통과.
- `python3 -m unittest discover -s tests -p test_regression.py -v`: 추가 9개 통과.

추가 테스트는 매우 큰 정수, 할인 동률, 환불 합계와 분할 불변성, bool 거부, 재고 원자성, UTC 경계, 호출자 데이터와 snapshot의 분리, 확인 이후 TTL, 만료와 이벤트 거부의 전체 롤백, 실패 id 재사용, 중복 payload 및 미지 키, 취소 상태 전이, replay 입력 보존과 동일 시간 안정성을 검사합니다.

남은 계약상 미해결 사항은 없습니다. 숨겨진 평가기나 다른 실행 결과는 열람하지 않았습니다. 다중 스레드·DB·네트워크는 계약 범위 밖입니다.
