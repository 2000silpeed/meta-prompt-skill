def _validate(stock, items):
    if not isinstance(stock, dict) or not isinstance(items, dict) or not items:
        raise ValueError('invalid inventory request')
    for sku, qty in items.items():
        if not isinstance(sku, str) or not sku or sku not in stock or type(qty) is not int or qty <= 0:
            raise ValueError('invalid sku or quantity')
        if type(stock[sku]) is not int or stock[sku] < 0:
            raise ValueError('invalid stock')


def reserve(stock, items):
    _validate(stock, items)
    for sku, qty in items.items():
        if stock[sku] < qty:
            raise ValueError('insufficient stock')
    for sku, qty in items.items():
        stock[sku] -= qty


def release(stock, items):
    _validate(stock, items)
    for sku, qty in items.items():
        stock[sku] += qty
