# 모델별 일반 지시 vs 메타 프롬프트 결과

같은 상세 명세와 시작 코드, 모델별 medium 추론 설정, 사전에 고정한 41개 평가 테스트를 사용했다.

| 모델 | 조건 | 실행 수 | 테스트 통과 합계 | 평균 시간 (최소–최대) |
|---|---|---:|---:|---:|
| astra | raw | 2 | 80/82 | 98.7초 (86.5–111.0) |
| astra | meta | 2 | 80/82 | 137.1초 (104.0–170.1) |
| sol | raw | 2 | 80/82 | 328.3초 (325.9–330.7) |
| sol | meta | 2 | 80/82 | 245.3초 (186.0–304.6) |
| luna | raw | 2 | 76/82 | 125.9초 (112.5–139.4) |
| luna | meta | 2 | 80/82 | 130.5초 (113.7–147.2) |

## 모델 내 차이

메타 − 일반. 양수 시간은 메타 조건이 더 오래 걸렸다는 뜻이다.

| 모델 | 통과 항목 차이 (2회 합계) | 평균 시간 차이 |
|---|---:|---:|
| gpt-6-astra | +0 | +38.3초 |
| gpt-5.6-sol | +0 | -83.0초 |
| gpt-5.6-luna | +4 | +4.5초 |

## 원본 실행

| 실행 | 평가 | 공개·저장된 자체 테스트 | 시간 |
|---|---:|---|---:|
| r1-astra-raw | 40/41 | 통과 | 111.0초 |
| r1-astra-meta | 40/41 | 통과 | 170.1초 |
| r1-sol-meta | 40/41 | 통과 | 304.6초 |
| r1-sol-raw | 40/41 | 통과 | 325.9초 |
| r1-luna-raw | 37/41 | 통과 | 112.5초 |
| r1-luna-meta | 40/41 | 통과 | 113.7초 |
| r2-luna-meta | 40/41 | 통과 | 147.2초 |
| r2-luna-raw | 39/41 | 통과 | 139.4초 |
| r2-sol-raw | 40/41 | 통과 | 330.7초 |
| r2-sol-meta | 40/41 | 통과 | 186.0초 |
| r2-astra-meta | 40/41 | 통과 | 104.0초 |
| r2-astra-raw | 40/41 | 통과 | 86.5초 |

## 실패 항목

- r1-astra-raw: test_acceptance.ExtendedAcceptance.test_41_unbounded_integer_event_lifecycle
- r1-astra-meta: test_acceptance.ExtendedAcceptance.test_41_unbounded_integer_event_lifecycle
- r1-sol-meta: test_acceptance.ExtendedAcceptance.test_41_unbounded_integer_event_lifecycle
- r1-sol-raw: test_acceptance.ExtendedAcceptance.test_41_unbounded_integer_event_lifecycle
- r1-luna-raw: test_acceptance.Acceptance.test_08_discount_rejects_bool_and_noninteger_numbers, test_acceptance.Acceptance.test_10_refund_domain_validation, test_acceptance.Acceptance.test_18_reserved_partial_cancel_rejected_full_explicit_allowed, test_acceptance.ExtendedAcceptance.test_41_unbounded_integer_event_lifecycle
- r1-luna-meta: test_acceptance.ExtendedAcceptance.test_41_unbounded_integer_event_lifecycle
- r2-luna-meta: test_acceptance.ExtendedAcceptance.test_41_unbounded_integer_event_lifecycle
- r2-luna-raw: test_acceptance.Acceptance.test_08_discount_rejects_bool_and_noninteger_numbers, test_acceptance.ExtendedAcceptance.test_41_unbounded_integer_event_lifecycle
- r2-sol-raw: test_acceptance.ExtendedAcceptance.test_41_unbounded_integer_event_lifecycle
- r2-sol-meta: test_acceptance.ExtendedAcceptance.test_41_unbounded_integer_event_lifecycle
- r2-astra-meta: test_acceptance.ExtendedAcceptance.test_41_unbounded_integer_event_lifecycle
- r2-astra-raw: test_acceptance.ExtendedAcceptance.test_41_unbounded_integer_event_lifecycle

한 상세 명세 과제의 조건당 두 번 관측이다. 모델별 전용 가이드 수준이 다르며 Astra는 범용 폴백이다. 금액·토큰 비용은 미측정이다. 테스트 점수와 시간의 차이를 일반적인 모델·프롬프트 우열로 확대하지 않는다.

[실험 조건](PROTOCOL.md)
