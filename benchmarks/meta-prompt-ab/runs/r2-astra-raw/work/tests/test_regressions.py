import copy
import unittest
from shop import OrderBook, replay
from shop.clock import parse_time
from shop.inventory import reserve, release
from shop.money import allocate_discount, refund_delta


def event(eid='r', kind='reserve', oid='o', at='2026-01-01T00:00:00Z', **extra):
    return dict(id=eid, type=kind, order_id=oid, at=at, **extra)


def reservation(eid='r', oid='o', **extra):
    data = dict(lines=[dict(sku='A', qty=3, unit_price=4)], discount=2,
                expires_at='2026-01-01T01:00:00Z')
    data.update(extra)
    return event(eid, oid=oid, **data)


class RegressionTests(unittest.TestCase):
    def test_exact_large_money_and_ties(self):
        n = 10 ** 400
        self.assertEqual(allocate_discount([dict(sku='B', qty=1, unit_price=n),
                                            dict(sku='A', qty=1, unit_price=n)], 1),
                         {'B': n, 'A': n-1})
        self.assertEqual(allocate_discount([dict(sku='A', qty=2, unit_price=0)], 0), {'A': 0})

    def test_refund_conservation(self):
        for total in range(20):
            for qty in range(1, 10):
                self.assertEqual(sum(refund_delta(total, qty, n, 1) for n in range(qty)), total)

    def test_invalid_money(self):
        for value in [True, False, None, -1, 1.5, '1']:
            with self.assertRaises(ValueError):
                allocate_discount([dict(sku='A', qty=1, unit_price=2)], value)
        for args in [(True, 1, 0, 1), (1, True, 0, 1), (1, 1, False, 1),
                     (1, 1, 0, True), (1, 1, 1, 1), (1, 2, 0, 3)]:
            with self.assertRaises(ValueError): refund_delta(*args)

    def test_times(self):
        self.assertEqual(parse_time('2026-01-01T01:00:00+01:00').isoformat(), '2026-01-01T00:00:00+00:00')
        for value in [None, 12, '2026-01-01', '2026-01-01T00:00:00', 'bad']:
            with self.assertRaises(ValueError): parse_time(value)

    def test_inventory_atomic_validation(self):
        for function in [reserve, release]:
            for items in [{'A': 1, 'X': 1}, {'A': 1, 'B': True}, {}, {'A': -1}]:
                stock = {'A': 4, 'B': 3}
                with self.assertRaises(ValueError): function(stock, items)
                self.assertEqual(stock, {'A': 4, 'B': 3})
        stock = {'A': 1}
        self.assertIsNone(reserve(stock, {'A': 1}))
        self.assertIsNone(release(stock, {'A': 1}))
        self.assertEqual(stock, {'A': 1})

    def test_alias_isolation(self):
        stock = {'A': 10}; e = reservation(); original = copy.deepcopy(e)
        book = OrderBook(stock); book.apply(e)
        self.assertEqual(stock, {'A': 10}); self.assertEqual(e, original)
        stock['A'] = 0; e['lines'][0]['qty'] = 999
        snap = book.snapshot(); snap['stock']['A'] = 0
        snap['orders']['o']['remaining']['A'] = 999
        snap['orders']['o']['line_totals']['A'] = 999
        self.assertEqual(book.snapshot()['stock'], {'A': 7})
        self.assertEqual(book.snapshot()['orders']['o']['remaining'], {'A': 3})
        self.assertEqual(book.snapshot()['orders']['o']['line_totals'], {'A': 10})

    def test_duplicate_normalization_and_old_noop(self):
        book = OrderBook({'A': 10}); first = reservation(); first['extra'] = {'a': 1, 'b': 2}
        book.apply(first)
        book.apply(event('c', 'confirm', at='2026-01-01T00:10:00Z'))
        before = book.snapshot()
        duplicate = dict(reversed(list(first.items())))
        duplicate.update(at='2026-01-01T09:00:00+09:00', expires_at='2026-01-01T10:00:00+09:00', extra={'b': 2, 'a': 1})
        self.assertIsNone(book.apply(duplicate)); self.assertEqual(book.snapshot(), before)
        duplicate['extra']['a'] = 3
        with self.assertRaises(ValueError): book.apply(duplicate)
        self.assertEqual(book.snapshot(), before)

    def test_expiry_boundary_atomic_and_failed_id_reusable(self):
        book = OrderBook({'A': 10}); book.apply(reservation()); before = book.snapshot()
        with self.assertRaises(ValueError):
            book.apply(event('x', 'confirm', at='2026-01-01T01:00:00Z'))
        self.assertEqual(book.snapshot(), before)
        book.apply(reservation('x', 'second', at='2026-01-01T01:00:00Z', expires_at='2026-01-01T02:00:00Z'))
        self.assertEqual(book.snapshot()['orders']['o']['status'], 'expired')
        self.assertEqual(book.snapshot()['orders']['o']['remaining'], {'A': 0})
        self.assertEqual(book.snapshot()['stock'], {'A': 7})

    def test_confirmed_survives_ttl_and_refunds(self):
        book = OrderBook({'A': 10}); book.apply(reservation())
        book.apply(event('c', 'confirm'))
        for n, amount in enumerate([3, 6, 10], 1):
            book.apply(event('x'+str(n), 'cancel', at='2026-01-01T02:00:00Z', items={'A': 1}))
            order = book.snapshot()['orders']['o']
            self.assertEqual(order['refunded'], amount)
            self.assertEqual(order['charged'], 10)
            self.assertEqual(order['status'], 'cancelled' if n == 3 else 'confirmed')
        self.assertEqual(book.snapshot()['stock'], {'A': 10})
        with self.assertRaises(ValueError): book.apply(reservation('again'))

    def test_reserved_cancel_full_only(self):
        book = OrderBook({'A': 10}); book.apply(reservation()); before = book.snapshot()
        with self.assertRaises(ValueError): book.apply(event('x', 'cancel', items={'A': 1}))
        self.assertEqual(book.snapshot(), before)
        book.apply(event('x', 'cancel'))
        self.assertEqual(book.snapshot()['orders']['o']['refunded'], 0)
        self.assertEqual(book.snapshot()['orders']['o']['status'], 'cancelled')

    def test_invalid_event_rollback(self):
        book = OrderBook({'A': 10}); book.apply(reservation()); before = book.snapshot()
        for invalid in [None, [], {}, event('x', 'unknown'), event('x', 'cancel', items={}),
                        reservation('x', 'new', lines=[dict(sku='A', qty=True, unit_price=1)]),
                        event('x', 'cancel', at='2025-12-31T00:00:00Z')]:
            with self.assertRaises(ValueError): book.apply(invalid)
            self.assertEqual(book.snapshot(), before)

    def test_replay_utc_stable_and_immutable(self):
        events = [event('c', 'confirm', at='2025-12-31T20:01:00-04:00'),
                  reservation(at='2026-01-01T09:00:00+09:00'),
                  event('x', 'cancel', at='2025-12-31T20:01:00-04:00', items={'A': 1})]
        before = copy.deepcopy(events)
        result = replay({'A': 10}, events)
        self.assertEqual(result['orders']['o']['refunded'], 3)
        self.assertEqual(events, before)
        self.assertEqual(replay({'A': 10}, events), result)
        for invalid in [[{}], [None], None]:
            with self.assertRaises(ValueError): replay({}, invalid)


if __name__ == '__main__':
    unittest.main()
