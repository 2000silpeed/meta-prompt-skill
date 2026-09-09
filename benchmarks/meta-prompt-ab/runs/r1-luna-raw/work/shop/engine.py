from copy import deepcopy
import json
from .clock import parse_time
from .money import allocate_discount, refund_delta
from .inventory import reserve, release


class OrderBook:
    def __init__(self, initial_stock):
        if not isinstance(initial_stock, dict) or any(
            not isinstance(k, str) or not k or type(v) is not int or v < 0
            for k, v in initial_stock.items()
        ):
            raise ValueError('invalid initial stock')
        self.stock = deepcopy(initial_stock)
        self.orders = {}
        self.seen = {}
        self.as_of = None

    def snapshot(self):
        return ({
            'stock': deepcopy(self.stock),
            'orders': {oid: {k: deepcopy(order[k]) for k in ['status', 'remaining', 'line_totals', 'charged', 'refunded']}
                       for oid, order in self.orders.items()},
            'as_of': self.as_of.isoformat() if self.as_of is not None else None,
        })

    def apply(self, event):
        try:
            if not isinstance(event, dict):
                raise ValueError('event must be a dict')
            for field in ['id', 'order_id', 'type']:
                if not isinstance(event.get(field), str) or not event[field]:
                    raise ValueError('invalid envelope')
            if event['type'] not in ['reserve', 'confirm', 'cancel']:
                raise ValueError('unknown event type')
            now = parse_time(event.get('at'))
            canonical = deepcopy(event)
            canonical['at'] = now.isoformat()
            if event['type'] == 'reserve':
                canonical['expires_at'] = parse_time(event.get('expires_at')).isoformat()
            fingerprint = json.dumps(canonical, sort_keys=True, separators=(',', ':'), allow_nan=False)
            if event['id'] in self.seen:
                if self.seen[event['id']] != fingerprint:
                    raise ValueError('conflicting duplicate id')
                return None
            if self.as_of is not None and now < self.as_of:
                raise ValueError('time went backwards')
            staged = deepcopy(self)
            staged._expire(now)
            staged._dispatch(event, now)
            staged.as_of = now
            staged.seen[event['id']] = fingerprint
            self.__dict__ = staged.__dict__
            return None
        except (TypeError, KeyError, AttributeError, OverflowError) as exc:
            raise ValueError('invalid event') from exc

    def _expire(self, now):
        for order in self.orders.values():
            if order['status'] == 'reserved' and order['expires_at'] <= now:
                release(self.stock, order['remaining'])
                order['remaining'] = {sku: 0 for sku in order['remaining']}
                order['status'] = 'expired'

    def _dispatch(self, event, now):
        oid = event['order_id']
        kind = event['type']
        if kind == 'reserve':
            if oid in self.orders:
                raise ValueError('order id already used')
            totals = allocate_discount(event.get('lines'), event.get('discount', 0))
            expiry = parse_time(event.get('expires_at'))
            if expiry <= now:
                raise ValueError('expiry must be later')
            items = {line['sku']: line['qty'] for line in event['lines']}
            reserve(self.stock, items)
            self.orders[oid] = dict(status='reserved', remaining=deepcopy(items),
                                   line_totals=totals, charged=0, refunded=0,
                                   original=deepcopy(items), cancelled={sku: 0 for sku in items},
                                   expires_at=expiry)
            return
        if oid not in self.orders:
            raise ValueError('unknown order')
        order = self.orders[oid]
        if kind == 'confirm':
            if order['status'] != 'reserved':
                raise ValueError('order is not reserved')
            order['status'] = 'confirmed'
            order['charged'] = sum(order['line_totals'].values())
            return
        if order['status'] not in ['reserved', 'confirmed']:
            raise ValueError('order not cancellable')
        items = event.get('items', {k: v for k, v in order['remaining'].items() if v})
        if not isinstance(items, dict) or not items:
            raise ValueError('invalid cancellation')
        for sku, qty in items.items():
            if sku not in order['remaining'] or type(qty) is not int or qty <= 0 or qty > order['remaining'][sku]:
                raise ValueError('invalid cancellation item')
        if order['status'] == 'reserved' and any(order['remaining'][sku] != qty for sku, qty in order['remaining'].items()):
            raise ValueError('reserved cancellation must be full')
        for sku, qty in items.items():
            if order['status'] == 'confirmed':
                order['refunded'] += refund_delta(order['line_totals'][sku], order['original'][sku], order['cancelled'][sku], qty)
            order['remaining'][sku] -= qty
            order['cancelled'][sku] += qty
        release(self.stock, items)
        if all(qty == 0 for qty in order['remaining'].values()):
            order['status'] = 'cancelled'


def replay(initial_stock, events):
    try:
        ordered = sorted(enumerate(events), key=lambda p: (parse_time(p[1]['at']), p[0]))
    except (TypeError, KeyError, AttributeError) as exc:
        raise ValueError('invalid replay events') from exc
    book = OrderBook(initial_stock)
    for _, event in ordered:
        book.apply(event)
    return book.snapshot()
