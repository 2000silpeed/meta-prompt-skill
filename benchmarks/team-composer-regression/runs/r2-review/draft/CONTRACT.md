# 주문·재고 이벤트 엔진 회귀 수정 과제 v2

Goal: shop 패키지의 기존 public API를 유지하며 아래 계약을 만족하도록 버그를 수정한다. 외부 의존성 없이 Python 3.12 표준 라이브러리만 사용한다. 공개 테스트를 통과하는 것만으로 완료로 간주하지 말고 경계값·모듈 간 상호작용을 검사한다.

## API와 모듈 경계

- shop.clock.parse_time(text) -> timezone-aware UTC datetime.
- shop.money.allocate_discount(lines, discount) -> {sku: net_line_total}.
- shop.money.refund_delta(total, qty, cancelled, delta) -> int.
- shop.inventory.reserve(stock, items), release(stock, items): 성공 시 stock을 제자리 수정하고 None 반환, 실패 시 ValueError이며 stock 불변.
- shop.engine.OrderBook(initial_stock), .apply(event), .snapshot().
- shop.engine.replay(initial_stock, events) -> snapshot.
- shop.__init__에서 OrderBook, replay를 export.

함수명과 시그니처를 유지한다. 내부 구현과 helper 추가는 자유다. shop 밖의 기존 테스트·계약을 수정하지 않는다. 자체 테스트 추가 가능. 다중 스레드 안전성·DB·네트워크는 범위 밖이다.

## 데이터와 수치

initial_stock: 비어도 되는 dict[str, int>=0]. 모든 SKU는 비어 있지 않은 문자열. 모든 수치에서 bool은 int로 인정하지 않는다. 입력 객체는 caller 소유이며 절대 수정하지 않는다.
lines: 비어 있지 않은 list of {sku, qty, unit_price}. SKU 중복은 오류. qty는 양의 int, unit_price는 0 이상의 int. 금액은 정수 최소 단위다. discount는 0 이상 subtotal 이하의 int다.
allocate_discount는 각 line gross=qty*unit_price에 비례하여 discount를 배분한다. 먼저 floor(discount*gross/subtotal), 남은 단위는 fractional remainder 큰 순서, 동률이면 SKU 문자열 오름차순으로 1씩 배분한다. 반환값은 각 gross에서 배분액을 뺀 net 총액이다. subtotal=0이면 discount=0만 가능하고 모든 net은 0이다. float를 사용한 근사 대신 정확한 정수 계산이 필요하다. 잘못된 입력은 ValueError.
refund_delta(total,qty,cancelled,delta)는 floor(total*(cancelled+delta)/qty)-floor(total*cancelled/qty)를 반환한다. total>=0, qty>0, 0<=cancelled<qty, delta>0, cancelled+delta<=qty인 int만 허용한다. 마지막 취소까지 합하면 정확히 total이어야 한다.

## 시간과 재고

parse_time은 ISO 8601 날짜+시각+명시적 offset 또는 Z만 허용한다. naive, date-only, non-string은 ValueError. 같은 instant의 다른 offset은 같은 UTC 값이다.
reserve/release의 items는 비어 있지 않은 dict[known_sku, positive_int]이다. reserve는 모든 SKU 재고가 충분할 때만 전체를 차감한다. release는 전체를 증가한다. 오류가 있으면 앞서 처리한 SKU도 변경되지 않는다.

## 이벤트

공통: {id: nonempty str, type: reserve|confirm|cancel, order_id: nonempty str, at: ISO timestamp}.
reserve 추가: {lines: [...], discount: int, expires_at: ISO timestamp}; discount 생략 시 0.
cancel 추가: {items: {sku: qty}}; items 생략 시 현재 남은 수량 전체를 취소한다. 빈 items는 오류.
추가 미지 키는 허용하며 계산에는 사용하지 않지만 중복 판정 fingerprint에는 포함한다. JSON-compatible 입력만 사용한다.

OrderBook.apply는 성공 시 None. snapshot은 아래 구조의 깊은 복사본이다. 초기 snapshot as_of는 null.
{
 "stock": {sku: available_qty},
 "orders": {order_id: {
   "status": "reserved|confirmed|cancelled|expired",
   "remaining": {sku: qty},
   "line_totals": {sku: net_line_total},
   "charged": int,
   "refunded": int
 }},
 "as_of": "YYYY-MM-DDTHH:MM:SS+00:00" 또는 null
}
remaining은 취소·만료된 SKU도 0 값으로 유지한다. charged는 confirm할 때 주문 net 전체 합으로 설정하고 이후 줄이지 않는다. refunded는 confirmed 상태에서 취소한 누적 환불액이며 reserved 취소·만료에는 항상 0이다. 확인된 주문의 일부 취소 후에도 status는 confirmed, 전부 취소하면 cancelled다. 예약 상태에서는 부분 취소를 허용하지 않는다(일부 SKU만 지정했어도 수량 합계가 실제 전체와 같을 때만 전체 취소 인정). 이미 cancelled/expired인 주문의 새로운 confirm/cancel은 오류다.

reserve는 새 order_id만 허용한다. 취소·만료 후에도 같은 order_id를 재사용할 수 없다. expires_at은 reserve.at보다 엄격히 뒤여야 한다. 재고를 즉시 예약 차감한다.
confirm은 reserved 주문만 가능하며 추가 재고 차감 없이 charged를 설정한다. confirm 이후에는 TTL로 만료되지 않는다.
confirmed 취소는 original qty와 최초 net line total로 refund_delta를 계산하고 재고를 즉시 복원한다. 같은 SKU의 누적 취소량을 반영한다. 취소 수량이 remaining보다 크거나 주문에 없는 SKU면 오류다.

## 순서·중복·원자성

새 이벤트의 timestamp는 직전 성공 이벤트의 시간 이상이어야 한다. 동일 시각은 허용된다. apply 시작 시 현재 이벤트 시각 이하의 expires_at을 가진 reserved 주문을 만료 처리하고 전량 재고를 복원한다. 경계값은 expires_at <= at이다. 하지만 이벤트가 결국 거부되면 만료 처리까지 포함한 전체 상태와 as_of, 중복 기록이 모두 이전 상태로 되돌아가야 한다. 예: 정확히 TTL 시각의 confirm은 ValueError이며 이전 reserved snapshot을 유지한다. 이후 다른 성공 이벤트가 진행되면 만료가 반영된다.

event id를 이미 성공 처리했고 payload fingerprint가 같으면 아무것도 바꾸지 않는 no-op이다. 중복 검사는 시간 역행 검사와 만료 처리보다 먼저 수행한다. 따라서 오래된 성공 이벤트의 정확한 재전송도 허용된다. fingerprint는 이벤트 dict의 키 순서를 무시하고 at 및 reserve.expires_at을 UTC ISO 문자열로 정규화한 전체 payload다. lines 순서와 추가 미지 키는 fingerprint에 포함한다. 실패한 이벤트는 id를 소비하지 않는다. 같은 id에 다른 fingerprint면 ValueError이며 상태 불변.

OrderBook.apply가 잘못된 입력을 받으면 ValueError만 발생시키고 전체 상태 불변을 보장한다. initial_stock, event, lines, items 등 호출자 데이터와 snapshot 반환값은 내부 상태와 alias를 공유하지 않는다.
replay는 입력 events를 변경하지 않고 UTC timestamp 오름차순, 같은 시각이면 입력 순서대로 apply한다. 동일 입력을 재실행하면 동일 snapshot을 반환한다. events가 비어 있으면 초기 snapshot 반환. replay의 잘못된 이벤트는 ValueError를 전파한다.

Done when: 위 public API와 계약을 만족하고, `python3 -m unittest discover -s tests -v` 및 직접 추가한 검증을 통과했다. 변경 사항, 실제 실행한 테스트, 남은 한계를 handoff.md에 기록하고 마지막에 completion.json을 작성한다. 평가용 테스트의 결과는 작업 중 제공되지 않는다.
