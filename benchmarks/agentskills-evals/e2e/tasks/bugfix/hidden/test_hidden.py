from decimal import Decimal
from payment.money import round_amount, apply_rate, split_amount
from payment.cart import cart_total, refund_amount


def D(x):
    return Decimal(str(x))


def eq(a, b):
    return D(a) == D(b)


def test_half_up_float_artifact():          # 2.675 is 2.67499.. in binary float
    assert eq(round_amount(2.675, "USD"), "2.68")


def test_half_up_not_bankers():
    assert eq(round_amount(0.125, "USD"), "0.13")


def test_half_up_1_005():
    assert eq(round_amount(1.005, "USD"), "1.01")


def test_krw_zero_decimals():
    assert eq(round_amount(1234.5, "KRW"), "1235")


def test_jpy_zero_decimals():
    assert eq(round_amount(99.4, "JPY"), "99")


def test_negative_half_up_away_from_zero():
    assert eq(round_amount(-2.675, "USD"), "-2.68")


def test_apply_rate_tax():
    assert eq(apply_rate(19.99, 0.1, "USD"), "2.00")


def test_cart_discount_then_tax():
    # line 33.33*3=99.99 ; discount 10% = 10.00 (9.999) -> 89.99 ; tax 7.5% = 6.75 (6.749..) -> 96.74
    assert eq(cart_total([(33.33, 3)], tax_rate=0.075, discount_rate=0.1, currency="USD"), "96.74")


def test_cart_krw():
    assert eq(cart_total([(1050, 3)], tax_rate=0.1, currency="KRW"), "3465")


def test_split_remainder_front():
    assert [D(x) for x in split_amount(10.00, 3, "USD")] == [D("3.34"), D("3.33"), D("3.33")]


def test_split_sum_exact_krw():
    parts = split_amount(10000, 3, "KRW")
    assert sum(D(x) for x in parts) == D("10000") and [D(x) for x in parts] == [D("3334"), D("3333"), D("3333")]


def test_refund_half_up():
    assert eq(refund_amount(20.25, 0.5, "USD"), "10.13")


def test_visible_still_pass_round_simple():
    assert eq(round_amount(10.123, "USD"), "10.12")


def test_visible_still_pass_cart_basic():
    assert eq(cart_total([(10.0, 2), (5.5, 1)], currency="USD"), "25.5")
