from copy import deepcopy
import json
from .clock import parse_time
from .money import allocate_discount, refund_delta
from .inventory import reserve, release

def _fingerprint(event):
    value = deepcopy(event)
    value['at'] = parse_time(value['at']).isoformat()
    if value.get('type') == 'reserve' and 'expires_at' in value:
        value['expires_at'] = parse_time(value['expires_at']).isoformat()
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('event must be JSON-compatible') from exc

class OrderBook:
    def __init__(self, initial_stock):
        if not isinstance(initial_stock, dict) or any(not isinstance(k, str) or not k or type(v) is not int or v < 0 for k, v in initial_stock.items()):
            raise ValueError('invalid initial stock')
        self.stock, self.orders, self.seen, self.as_of = deepcopy(initial_stock), {}, {}, None

    def snapshot(self):
        return {'stock': deepcopy(self.stock),
                'orders': {oid: {k: deepcopy(order[k]) for k in ('status','remaining','line_totals','charged','refunded')} for oid, order in self.orders.items()},
                'as_of': self.as_of.isoformat() if self.as_of else None}

    def apply(self, event):
        if not isinstance(event, dict):
            raise ValueError('event must be a dict')
        for key in ('id','type','order_id','at'):
            if not isinstance(event.get(key), str) or not event[key]:
                raise ValueError('invalid envelope')
        if event['type'] not in ('reserve','confirm','cancel'):
            raise ValueError('unknown event type')
        now = parse_time(event['at'])
        fp = _fingerprint(event)
        if event['id'] in self.seen:
            if self.seen[event['id']] != fp:
                raise ValueError('conflicting duplicate id')
            return None
        if self.as_of is not None and now < self.as_of:
            raise ValueError('time went backwards')
        staged = deepcopy(self)
        staged._expire(now)
        staged._dispatch(event, now)
        staged.as_of, staged.seen[event['id']] = now, fp
        self.__dict__ = staged.__dict__

    def _expire(self, now):
        for order in self.orders.values():
            if order['status'] == 'reserved' and order['expires_at'] <= now:
                release(self.stock, order['remaining'])
                order['remaining'] = {sku: 0 for sku in order['remaining']}
                order['status'] = 'expired'

    def _dispatch(self, event, now):
        oid, kind = event['order_id'], event['type']
        if kind == 'reserve':
            if oid in self.orders:
                raise ValueError('order id already used')
            lines = event.get('lines')
            totals = allocate_discount(lines, event.get('discount', 0))
            expiry = parse_time(event.get('expires_at'))
            if expiry <= now:
                raise ValueError('expiry must be later')
            items = {line['sku']: line['qty'] for line in lines}
            reserve(self.stock, items)
            self.orders[oid] = {'status':'reserved','remaining':deepcopy(items),'line_totals':deepcopy(totals),'charged':0,'refunded':0,'original':deepcopy(items),'cancelled':{s:0 for s in items},'expires_at':expiry}
            return
        if oid not in self.orders:
            raise ValueError('unknown order')
        order = self.orders[oid]
        if kind == 'confirm':
            if order['status'] != 'reserved':
                raise ValueError('order is not reserved')
            order['status'], order['charged'] = 'confirmed', sum(order['line_totals'].values())
            return
        if order['status'] not in ('reserved','confirmed'):
            raise ValueError('order not cancellable')
        items = event.get('items')
        if items is None:
            items = {s:q for s,q in order['remaining'].items() if q}
        if not isinstance(items, dict) or not items:
            raise ValueError('invalid cancellation')
        for sku, qty in items.items():
            if sku not in order['remaining'] or type(qty) is not int or qty <= 0 or qty > order['remaining'][sku]:
                raise ValueError('invalid cancellation item')
        if order['status'] == 'reserved' and sum(items.values()) != sum(order['remaining'].values()):
            raise ValueError('reserved cancellation must be full')
        for sku, qty in items.items():
            if order['status'] == 'confirmed':
                order['refunded'] += refund_delta(order['line_totals'][sku], order['original'][sku], order['cancelled'][sku], qty)
            order['remaining'][sku] -= qty
            order['cancelled'][sku] += qty
        release(self.stock, items)
        if not any(order['remaining'].values()):
            order['status'] = 'cancelled'

def replay(initial_stock, events):
    if not isinstance(events, list):
        raise ValueError('invalid replay events')
    try:
        ordered = sorted(events, key=lambda e: parse_time(e['at']))
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError('invalid replay events') from exc
    book = OrderBook(initial_stock)
    for event in ordered:
        book.apply(event)
    return book.snapshot()
