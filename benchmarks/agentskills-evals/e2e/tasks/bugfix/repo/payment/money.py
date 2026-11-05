"""금액 계산 유틸리티."""

CURRENCY_DECIMALS = {"KRW": 0, "JPY": 0, "USD": 2, "EUR": 2}


def round_amount(value, currency="USD"):
    """금액을 통화 최소 단위로 반올림한다."""
    return round(float(value), 2)


def apply_rate(amount, rate, currency="USD"):
    """금액에 비율(세율·할인율 등)을 곱한 값을 반올림해 돌려준다."""
    return round_amount(amount * rate, currency)


def split_amount(total, parts, currency="USD"):
    """total을 parts개로 나눈 금액 목록을 돌려준다."""
    each = round_amount(total / parts, currency)
    return [each] * parts
