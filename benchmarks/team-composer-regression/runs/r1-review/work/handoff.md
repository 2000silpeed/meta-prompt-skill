# 제작 초안 완료

shop public API와 CONTRACT.md를 확인하고 전체 모듈을 수정·검증했다. 기존 공개 테스트와 계약은 변경하지 않았다.

- clock: naive 시간을 거부하고 명시적 offset을 실제 UTC instant로 변환한다.
- money: bool을 거부하고 큰 정수에도 정확한 할인 배분, SKU 사전순 동률 처리, 누적 취소량 기준 환불 차액을 계산한다.
- inventory: 전체 요청 검증 후 재고를 변경하여 실패 시 원자성을 보장한다.
- engine: 입력 및 snapshot 복사, UTC 정규화 및 키 순서를 무시하는 전체 payload fingerprint, 시간 검사 전 중복 처리, 복사본에서의 만료·이벤트 처리 후 성공 시 commit을 구현했다. 예약만 TTL 경계에서 만료되고 예약 부분 취소를 거부한다. replay는 UTC instant 기준 안정 정렬한다.
- shop.__init__의 OrderBook 및 replay export는 확인 후 유지했다.

실제 실행한 검증:

- `python3 -m unittest discover -s tests -v`: 공개 테스트 6개와 추가 회귀 테스트 11개, 총 17개 통과.
- `python3 -m unittest discover -s tests -p test_regression.py -v`: 추가 테스트 11개 통과. 큰 정수와 배분 동률, 환불 보존, 입력 거부, 재고 원자성, alias 격리, 중복 정규화, 실패 만료 rollback 및 id 재사용, confirmed TTL 면제, 전체 예약 취소, replay UTC 순서 및 결정성을 검증했다.

알려진 계약 미충족 사항은 없다. 검증 범위는 공개 계약과 로컬 테스트이며 숨겨진 평가 결과를 사용하지 않았다. 다중 스레드, DB, 네트워크는 계약의 범위 밖이다.


# 독립 검토 후 최종 수정

engine fingerprint의 Python 정수 직렬화 자릿수 제한을 재현하고, 자료형을 보존하는 canonical tuple로 교체했다. 정수 제한이 없는 계약을 만족하며 중복 판정 의미와 이벤트 원자성을 유지한다. 상세 발견 사항은 review.md에 기록했다.

최종 실행: `python3 -m unittest discover -s tests -v` 21개 통과; `python3 -m unittest discover -s tests -p test_review.py -v` 4개 통과. 추가 검증은 큰 정수, 구조 및 타입을 포함한 fingerprint, 다중 SKU 환불, 여러 예약의 만료 rollback을 다룬다. 알려진 계약 미충족 사항은 없다.
