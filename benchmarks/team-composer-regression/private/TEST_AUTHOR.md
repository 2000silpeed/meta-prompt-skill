공개 계약만 바탕으로 독립 평가용 unittest 테스트를 작성한다. 다른 구현·실행 결과를 읽지 않는다.
읽을 수 있는 계약: ../fixture/CONTRACT.md (이 파일 위치 기준).
쓰기 범위: 이 private 디렉터리의 test_acceptance.py와 test_notes.md만.
테스트는 import shop 으로 candidate API를 사용한다. Python 표준 라이브러리만 사용한다.
단일 메서드 안에 수십 subTest를 넣기보다 관측 가능한 계약 30~45개를 이름 있는 test 메서드로 나눈다.
특히 exact TTL confirm 거절의 rollback, older duplicate bypass, fingerprint timezone canonicalization, partial cancellations rounding, cross-SKU atomicity, snapshots aliasing, replay stable sort, large integer discount remainder를 다룬다. 난도가 높다는 이유로 계약에 없는 새 요구를 만들지 않는다. 정확한 기대값은 계약에서 계산한다.
평가 완료 시 파일 두 개의 경로를 보고한다. 에이전트 추가 호출이나 외부 네트워크 사용은 하지 않는다.
