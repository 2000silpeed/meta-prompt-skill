# 독립 검토 결과

공개 계약, shop 전체 모듈, 기존 tests 및 handoff를 검토했다. 지정 work 밖 구현, 비공개 테스트, 평가 결과는 확인하지 않았다.

발견 및 수정: engine의 json.dumps fingerprint는 Python의 기본 정수 10진수 변환 제한 때문에 10**5000을 가격 또는 추가 payload 값으로 가진 유효한 이벤트를 ValueError로 거부했다. 수정 전에 동일 오류를 직접 재현했다. 계약은 정수의 자릿수 상한을 두지 않는다. 문자열 직렬화 대신 자료형 태그와 재귀 tuple로 canonical fingerprint를 구성해 정수를 직접 보존하도록 수정했다. dict 키 정렬, list 순서, 추가 필드, bool/int/float 구별과 UTC 정규화는 유지한다. 전역 Python 제한 설정은 변경하지 않는다.

추가 검증: test_review.py에 큰 정수 예약·청구·정확한 재전송·충돌, 중첩 dict 순서와 payload 자료형 구분, line 순서, 다중 SKU 부분 취소 후 나머지 전체 취소, 여러 주문 동시 만료의 실패 rollback 및 같은 id 재시도를 추가했다. 기존 계약과 기존 테스트 파일은 수정하지 않았다.

실행 결과:
- `python3 -m unittest discover -s tests -v`: 21개 통과.
- `python3 -m unittest discover -s tests -p test_review.py -v`: 독립 검토 테스트 4개 통과.

알려진 계약 미충족 사항은 없다. 검증은 공개 계약 및 로컬 테스트에 한정하며 숨겨진 평가 통과를 주장하지 않는다.
