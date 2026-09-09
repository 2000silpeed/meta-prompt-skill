from copy import deepcopy
import json
import math

from .clock import parse_time
from .inventory import release, reserve
from .money import allocate_discount, refund_delta


def _nonempty_string(value):
    return isinstance(value, str) and bool(value)


def _validate_json(value):
    """Validate the strict data model accepted by JSON, including string keys."""
    if value is None or isinstance(value, (str, bool)) or type(value) is int:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError('non-finite JSON number')
        return
    if isinstance(value, list):
        for item in value:
            _validate_json(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError('JSON object keys must be strings')
            _validate_json(item)
        return
    raise ValueError('event must be JSON-compatible')


def _event_header(event):
    if not isinstance(event, dict):
        raise ValueError('event must be a dict')
    _validate_json(event)
    for field in ('id', 'type', 'order_id'):
        if not _nonempty_string(event.get(field)):
            raise ValueError('invalid event envelope')
    if event['type'] not in ('reserve', 'confirm', 'cancel'):
        raise ValueError('unknown event type')
    return parse_time(event.get('at'))


def _fingerprint(event, now):
    canonical = deepcopy(event)
    canonical['at'] = now.isoformat()
    if event['type'] == 'reserve':
        expiry = parse_time(event.get('expires_at'))
        canonical['expires_at'] = expiry.isoformat()
    return json.dumps(canonical, sort_keys=True, separators=(',', ':'), allow_nan=False)


class OrderBook:
    def __init__(self, initial_stock):
        if not isinstance(initial_stock, dict) or any(
            not isinstance(sku, str) or not sku or type(qty) is not int or qty < 0
            for sku, qty in initial_stock.items()
        ):
            raise ValueError('invalid initial stock')
        self.stock = deepcopy(initial_stock)
        self.orders = {}
        self.seen = {}
        self.as_of = None

    def snapshot(self):
        result = {
            'stock': self.stock,
            'orders': {
                oid: {
                    key: order[key]
                    for key in ('status', 'remaining', 'line_totals', 'charged', 'refunded')
                }
                for oid, order in self.orders.items()
            },
            'as_of': self.as_of.isoformat() if self.as_of is not None else None,
        }
        return deepcopy(result)

    def apply(self, event):
        try:
            now = _event_header(event)
            fingerprint = _fingerprint(event, now)

            # Successful retries precede chronology and expiration checks.
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
        except ValueError:
            raise
        except (TypeError, KeyError, AttributeError, OverflowError, RecursionError) as exc:
            raise ValueError('invalid event') from exc

    def _expire(self, now):
        for order in self.orders.values():
            if order['status'] == 'reserved' and order['expires_at'] <= now:
                items = {sku: qty for sku, qty in order['remaining'].items() if qty > 0}
                if items:
                    release(self.stock, items)
                order['remaining'] = {sku: 0 for sku in order['remaining']}
                order['status'] = 'expired'

    def _dispatch(self, event, now):
        oid = event['order_id']
        kind = event['type']
        if kind == 'reserve':
            self._reserve_order(oid, event, now)
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
        self._cancel_order(order, event)

    def _reserve_order(self, oid, event, now):
        if oid in self.orders:
            raise ValueError('order id already used')
        if 'lines' not in event:
            raise ValueError('lines required')
        totals = allocate_discount(event['lines'], event.get('discount', 0))
        expiry = parse_time(event.get('expires_at'))
        if expiry <= now:
            raise ValueError('expiry must be later')
        items = {line['sku']: line['qty'] for line in event['lines']}
        reserve(self.stock, items)
        self.orders[oid] = {
            'status': 'reserved',
            'remaining': deepcopy(items),
            'line_totals': deepcopy(totals),
            'charged': 0,
            'refunded': 0,
            'original': deepcopy(items),
            'cancelled': {sku: 0 for sku in items},
            'expires_at': expiry,
        }

    def _cancel_order(self, order, event):
        if order['status'] not in ('reserved', 'confirmed'):
            raise ValueError('order not cancellable')
        if 'items' in event:
            items = event['items']
        else:
            items = {sku: qty for sku, qty in order['remaining'].items() if qty > 0}
        if not isinstance(items, dict) or not items:
            raise ValueError('invalid cancellation')
        for sku, qty in items.items():
            if (
                not isinstance(sku, str)
                or not sku
                or sku not in order['remaining']
                or type(qty) is not int
                or qty <= 0
                or qty > order['remaining'][sku]
            ):
                raise ValueError('invalid cancellation item')
        if order['status'] == 'reserved' and sum(items.values()) != sum(order['remaining'].values()):
            raise ValueError('reserved cancellation must be full')

        was_confirmed = order['status'] == 'confirmed'
        for sku, qty in items.items():
            if was_confirmed:
                order['refunded'] += refund_delta(
                    order['line_totals'][sku],
                    order['original'][sku],
                    order['cancelled'][sku],
                    qty,
                )
            order['remaining'][sku] -= qty
            order['cancelled'][sku] += qty
        release(self.stock, items)
        if all(qty == 0 for qty in order['remaining'].values()):
            order['status'] = 'cancelled'


def replay(initial_stock, events):
    try:
        copied_events = deepcopy(events)
        indexed = list(enumerate(copied_events))
        ordered = sorted(indexed, key=lambda pair: (parse_time(pair[1].get('at')), pair[0]))
    except ValueError:
        raise
    except (TypeError, KeyError, AttributeError, OverflowError, RecursionError) as exc:
        raise ValueError('invalid replay events') from exc
    book = OrderBook(initial_stock)
    for _, event in ordered:
        book.apply(event)
    return book.snapshot()
