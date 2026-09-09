# 변경 및 검증

기존 public API와 공개 계약·테스트를 유지하며 shop 모듈을 수정했다.

- clock: 명시적 시간대 검증과 UTC instant 변환.
- money: bool 수치 거부, 큰 정수에서도 정확한 할인 배분, SKU 오름차순 동률 처리, 누적 floor 차이에 따른 환불.
- inventory: 모든 재고 충분 여부를 확인한 뒤 차감하여 실패 시 원자성 보장.
- engine: 초기 입력과 snapshot 깊은 복사, 전체 상태 staging을 통한 실패 롤백, 전체 payload의 키 정렬과 UTC 시간 정규화 fingerprint, 시간 순서 검사보다 먼저 중복 처리, reserved 주문만 TTL 경계 이하에서 만료, 예약 부분 취소 거부, UTC 기준 안정 replay 정렬.

실제 실행한 명령:

- `python3 -m unittest discover -s tests -v` — 공개 6개와 추가 10개, 총 16개 통과.
- `python3 -m unittest discover -s tests -p test_regression.py -v` — 추가 10개 통과.

추가 검증은 큰 정수·할인 동률·제로 금액·bool 거부, 다양한 수량의 누적 환불 보존, 재고 오류 원자성, 입력과 snapshot 비공유, TTL 경계 실패 롤백 및 실패 id 재사용, confirmed TTL 유지, 예약 부분 취소 거부, 시간대/키 순서 정규화 중복과 충돌, replay UTC 정렬 및 같은 시각 입력 순서를 포함한다.

남은 알려진 계약 미충족 사항은 없다. 숨겨진 평가 결과는 확인하지 않았다. 다중 스레드·DB·네트워크는 계약상 범위 밖이다.
