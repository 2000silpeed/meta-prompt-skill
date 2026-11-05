from decimal import Decimal
from .money import _r, _d
def line_total(unit_price, qty, currency="USD"):
    return _r(_d(unit_price) * qty, currency)
def cart_total(items, tax_rate=0.0, discount_rate=0.0, currency="USD"):
    total = Decimal(0)
    for unit_price, qty in items:
        line = line_total(unit_price, qty, currency)
        line = line - _r(line * _d(discount_rate), currency)
        line = line + _r(line * _d(tax_rate), currency)
        total += line
    return float(_r(total, currency))
def refund_amount(paid, refund_rate, currency="USD"):
    return float(_r(_d(paid) * _d(refund_rate), currency))
