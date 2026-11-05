"""장바구니 합계 계산."""
from .money import round_amount, apply_rate


def line_total(unit_price, qty, currency="USD"):
    return round_amount(unit_price * qty, currency)


def cart_total(items, tax_rate=0.0, discount_rate=0.0, currency="USD"):
    """items: [(unit_price, qty), ...]

    정책은 docs/PAYMENT_POLICY.md 참고.
    """
    total = 0.0
    for unit_price, qty in items:
        line = line_total(unit_price, qty, currency)
        line = line - apply_rate(line, discount_rate, currency)
        line = line + apply_rate(line, tax_rate, currency)
        total += line
    return round_amount(total, currency)


def refund_amount(paid, refund_rate, currency="USD"):
    """부분 환불 금액(음수가 아닌 값)."""
    return apply_rate(paid, refund_rate, currency)
