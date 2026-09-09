from copy import deepcopy
import json
from .clock import parse_time
from .money import allocate_discount, refund_delta
from .inventory import reserve, release

def _fingerprint(event):
    if type(event) is not dict: raise ValueError('event must be a dict')
    value = deepcopy(event)
    value['at'] = parse_time(value.get('at')).isoformat()
    if value.get('type') == 'reserve' and 'expires_at' in value:
        value['expires_at'] = parse_time(value['expires_at']).isoformat()
    try: return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc: raise ValueError('event must be JSON-compatible') from exc

class OrderBook:
    def __init__(self, initial_stock):
        if type(initial_stock) is not dict or any(type(k) is not str or not k or type(v) is not int or v < 0 for k,v in initial_stock.items()): raise ValueError('invalid initial stock')
        self.stock, self.orders, self.seen, self.as_of = deepcopy(initial_stock), {}, {}, None

    def snapshot(self):
        return {'stock':deepcopy(self.stock), 'orders':{oid:{k:deepcopy(order[k]) for k in ('status','remaining','line_totals','charged','refunded')} for oid,order in self.orders.items()}, 'as_of':self.as_of.isoformat() if self.as_of is not None else None}

    def apply(self, event):
        fingerprint = _fingerprint(event); eid = event.get('id')
        if type(eid) is not str or not eid: raise ValueError('invalid envelope')
        if eid in self.seen:
            if self.seen[eid] != fingerprint: raise ValueError('conflicting duplicate id')
            return None
        for field in ('type','order_id'):
            if type(event.get(field)) is not str or not event[field]: raise ValueError('invalid envelope')
        if event['type'] not in ('reserve','confirm','cancel'): raise ValueError('unknown event type')
        now = parse_time(event.get('at'))
        if self.as_of is not None and now < self.as_of: raise ValueError('time went backwards')
        staged = deepcopy(self); staged._expire(now); staged._dispatch(event, now); staged.as_of = now; staged.seen[eid] = fingerprint
        self.__dict__ = staged.__dict__

    def _expire(self, now):
        for order in self.orders.values():
            if order['status'] == 'reserved' and order['expires_at'] <= now:
                remaining = {k:v for k,v in order['remaining'].items() if v}
                if remaining: release(self.stock, remaining)
                order['remaining'] = {k:0 for k in order['remaining']}; order['status'] = 'expired'

    def _dispatch(self, event, now):
        oid, kind = event['order_id'], event['type']
        if kind == 'reserve':
            if oid in self.orders: raise ValueError('order id already used')
            lines = event.get('lines'); totals = allocate_discount(lines, event.get('discount',0)); expiry = parse_time(event.get('expires_at'))
            if expiry <= now: raise ValueError('expiry must be later')
            items = {line['sku']:line['qty'] for line in lines}; reserve(self.stock, items)
            self.orders[oid] = {'status':'reserved','remaining':deepcopy(items),'line_totals':totals,'charged':0,'refunded':0,'original':deepcopy(items),'cancelled':{k:0 for k in items},'expires_at':expiry}; return
        if oid not in self.orders: raise ValueError('unknown order')
        order = self.orders[oid]
        if kind == 'confirm':
            if order['status'] != 'reserved': raise ValueError('order is not reserved')
            order['status'], order['charged'] = 'confirmed', sum(order['line_totals'].values()); return
        if order['status'] not in ('reserved','confirmed'): raise ValueError('order not cancellable')
        items = event.get('items', {k:v for k,v in order['remaining'].items() if v})
        if type(items) is not dict or not items: raise ValueError('invalid cancellation')
        for sku,qty in items.items():
            if sku not in order['remaining'] or type(qty) is not int or qty <= 0 or qty > order['remaining'][sku]: raise ValueError('invalid cancellation item')
        if order['status'] == 'reserved' and sum(items.values()) != sum(order['remaining'].values()): raise ValueError('reserved cancellation must be full')
        for sku,qty in items.items():
            if order['status'] == 'confirmed': order['refunded'] += refund_delta(order['line_totals'][sku],order['original'][sku],order['cancelled'][sku],qty)
            order['remaining'][sku] -= qty; order['cancelled'][sku] += qty
        release(self.stock, items)
        if all(qty == 0 for qty in order['remaining'].values()): order['status'] = 'cancelled'

def replay(initial_stock, events):
    try: ordered = sorted(list(events), key=lambda e: parse_time(e.get('at')))
    except (TypeError, AttributeError, ValueError) as exc: raise ValueError('invalid replay events') from exc
    book = OrderBook(initial_stock)
    for event in ordered: book.apply(event)
    return book.snapshot()
