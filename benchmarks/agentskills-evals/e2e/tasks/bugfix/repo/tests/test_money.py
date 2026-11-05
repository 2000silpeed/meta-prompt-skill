from payment.money import round_amount, split_amount
from payment.cart import cart_total


def test_round_simple():
    assert round_amount(10.123, "USD") == 10.12


def test_cart_basic():
    assert cart_total([(10.0, 2), (5.5, 1)], currency="USD") == 25.5


def test_split_even():
    assert split_amount(9.0, 3, "USD") == [3.0, 3.0, 3.0]
