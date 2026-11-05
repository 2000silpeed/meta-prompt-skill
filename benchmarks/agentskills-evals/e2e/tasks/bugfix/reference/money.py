from decimal import Decimal, ROUND_HALF_UP
CURRENCY_DECIMALS = {"KRW": 0, "JPY": 0, "USD": 2, "EUR": 2}
def _q(c): return Decimal(1).scaleb(-CURRENCY_DECIMALS[c])
def _d(v): return v if isinstance(v, Decimal) else Decimal(str(v))
def _r(value, currency):
    return _d(value).quantize(_q(currency), rounding=ROUND_HALF_UP)
def round_amount(value, currency="USD"):
    return float(_r(value, currency))
def apply_rate(amount, rate, currency="USD"):
    return float(_r(_d(amount) * _d(rate), currency))
def split_amount(total, parts, currency="USD"):
    t = _r(total, currency); unit = _q(currency)
    base = (t / parts).quantize(unit, rounding="ROUND_DOWN"); rem = int((t - base * parts) / unit)
    return [float(base + unit if i < rem else base) for i in range(parts)]
