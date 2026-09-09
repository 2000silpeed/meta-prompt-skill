from copy import deepcopy
import json
from .clock import parse_time
from .money import allocate_discount, refund_delta
from .inventory import reserve, release

def _fingerprint(event):
    value = deepcopy(event)
    value['at'] = parse_time(value.get('at')).isoformat()
    if value.get('type') == 'reserve':
        value['expires_at'] = parse_time(value.get('expires_at')).isoformat()
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)

class OrderBook:
    def __init__(self, initial_stock):
        if not isinstance(initial_stock, dict) or any(not isinstance(k, str) or not k or type(v) is not int or v < 0 for k, v in initial_stock.items()):
            raise ValueError('invalid initial stock')
        self.stock, self.orders, self.seen, self.as_of = deepcopy(initial_stock), {}, {}, None

    def snapshot(self):
        return deepcopy({'stock': self.stock, 'orders': {oid: {k: order[k] for k in ('status','remaining','line_totals','charged','refunded')} for oid, order in self.orders.items()}, 'as_of': self.as_of.isoformat() if self.as_of is not None else None})

    def apply(self, event):
        if not isinstance(event, dict): raise ValueError('event must be a dict')
        for f in ('id','order_id','type'):
            if not isinstance(event.get(f), str) or not event[f]: raise ValueError('invalid envelope')
        if event['type'] not in ('reserve','confirm','cancel'): raise ValueError('unknown event type')
        fp = _fingerprint(event)
        if event['id'] in self.seen:
            if self.seen[event['id']] != fp: raise ValueError('conflicting duplicate id')
            return None
        now = parse_time(event.get('at'))
        if self.as_of is not None and now < self.as_of: raise ValueError('time went backwards')
        staged = deepcopy(self)
        staged._expire(now); staged._dispatch(event, now)
        staged.as_of, staged.seen[event['id']] = now, fp
        self.__dict__ = staged.__dict__
        return None

    def _expire(self, now):
        for o in self.orders.values():
            if o['status'] == 'reserved' and o['expires_at'] <= now:
                release(self.stock, o['remaining']); o['remaining'] = {s: 0 for s in o['remaining']}; o['status'] = 'expired'

    def _dispatch(self, event, now):
        oid, kind = event['order_id'], event['type']
        if kind == 'reserve':
            if oid in self.orders: raise ValueError('order id already used')
            lines = event.get('lines'); totals = allocate_discount(lines, event.get('discount', 0)); expiry = parse_time(event.get('expires_at'))
            if expiry <= now: raise ValueError('expiry must be later')
            items = {line['sku']: line['qty'] for line in lines}; reserve(self.stock, items)
            self.orders[oid] = {'status':'reserved','remaining':deepcopy(items),'line_totals':totals,'charged':0,'refunded':0,'original':deepcopy(items),'cancelled':{s:0 for s in items},'expires_at':expiry}
            return
        if oid not in self.orders: raise ValueError('unknown order')
        o = self.orders[oid]
        if kind == 'confirm':
            if o['status'] != 'reserved': raise ValueError('order is not reserved')
            o['status'], o['charged'] = 'confirmed', sum(o['line_totals'].values()); return
        if o['status'] not in ('reserved','confirmed'): raise ValueError('order not cancellable')
        items = event['items'] if 'items' in event else {s:q for s,q in o['remaining'].items() if q}
        if not isinstance(items, dict) or not items: raise ValueError('invalid cancellation')
        for s,q in items.items():
            if s not in o['remaining'] or type(q) is not int or q <= 0 or q > o['remaining'][s]: raise ValueError('invalid cancellation item')
        if o['status'] == 'reserved' and sum(items.values()) != sum(o['remaining'].values()): raise ValueError('reserved order requires full cancellation')
        for s,q in items.items():
            if o['status'] == 'confirmed': o['refunded'] += refund_delta(o['line_totals'][s], o['original'][s], o['cancelled'][s], q)
            o['remaining'][s] -= q; o['cancelled'][s] += q
        release(self.stock, items)
        if all(q == 0 for q in o['remaining'].values()): o['status'] = 'cancelled'

def replay(initial_stock, events):
    try: ordered = sorted(events, key=lambda e: parse_time(e.get('at')))
    except (TypeError, AttributeError, KeyError, ValueError) as exc: raise ValueError('invalid replay events') from exc
    book = OrderBook(initial_stock)
    for event in ordered: book.apply(event)
    return book.snapshot()
