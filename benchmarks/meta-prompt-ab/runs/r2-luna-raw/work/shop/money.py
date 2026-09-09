def integer(value, minimum=0):
    if not isinstance(value, int) or value < minimum:
        raise ValueError('invalid integer')
    return value


def allocate_discount(lines, discount):
    if type(discount) is not int or discount < 0:
        raise ValueError('invalid discount')
    if not isinstance(lines, list) or not lines:
        raise ValueError('lines required')
    gross = {}
    for line in lines:
        if not isinstance(line, dict):
            raise ValueError('line must be a dict')
        sku = line.get('sku')
        if not isinstance(sku, str) or not sku or sku in gross:
            raise ValueError('invalid or duplicate sku')
        qty = integer(line.get('qty'), 1)
        price = integer(line.get('unit_price'))
        gross[sku] = qty * price
    subtotal = sum(gross.values())
    if discount > subtotal:
        raise ValueError('discount exceeds subtotal')
    if subtotal == 0:
        return {sku: 0 for sku in gross}
    shares = {sku: int(discount * value / subtotal) for sku, value in gross.items()}
    order = sorted(gross, key=lambda sku: (-(discount * gross[sku] % subtotal), sku))
    remainder = discount - sum(shares.values())
    for sku in order[:remainder]:
        shares[sku] += 1
    return {sku: value - shares[sku] for sku, value in gross.items()}


def refund_delta(total, qty, cancelled, delta):
    if (type(total) is not int or total < 0 or type(qty) is not int or qty <= 0 or
            type(cancelled) is not int or cancelled < 0 or cancelled >= qty or
            type(delta) is not int or delta <= 0 or cancelled + delta > qty):
        raise ValueError('invalid cancellation quantity')
    return total * (cancelled + delta) // qty - total * cancelled // qty
