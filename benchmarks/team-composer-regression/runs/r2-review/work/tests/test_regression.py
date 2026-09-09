from copy import deepcopy
import unittest

from shop import OrderBook, replay
from shop.clock import parse_time
from shop.inventory import reserve, release
from shop.money import allocate_discount, refund_delta


def evt(eid, kind='reserve', oid='o', at='2026-01-01T00:00:00Z', **kw):
    return dict(id=eid, type=kind, order_id=oid, at=at, **kw)


def reservation(eid='r', oid='o', **kw):
    args = dict(lines=[dict(sku='A', qty=3, unit_price=4)], discount=2,
                expires_at='2026-01-01T01:00:00Z')
    args.update(kw)
    return evt(eid, oid=oid, **args)


class RegressionTests(unittest.TestCase):
    def test_time_validation_and_conversion(self):
        for value in (None, 123, '', '2026-01-01', '2026-01-01T00:00:00'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_time(value)
        self.assertEqual(parse_time('2026-01-01T01:30:00+01:30'),
                         parse_time('2026-01-01T00:00:00Z'))

    def test_exact_discount_and_tie_break(self):
        lines = [dict(sku=sku, qty=1, unit_price=10**100 + 1) for sku in ('ZZZ', 'A')]
        self.assertEqual(allocate_discount(lines, 1), {'ZZZ':10**100 + 1, 'A':10**100})
        self.assertEqual(sum(allocate_discount(lines, 10**99 + 1).values()),
                         2 * (10**100 + 1) - (10**99 + 1))
        self.assertEqual(allocate_discount([dict(sku='A', qty=1, unit_price=0)], 0), {'A':0})

    def test_money_rejects_bool_and_invalid_lines(self):
        for key in ('qty', 'unit_price'):
            line = dict(sku='A', qty=1, unit_price=1); line[key] = True
            with self.assertRaises(ValueError): allocate_discount([line], 0)
        line = dict(sku='A', qty=1, unit_price=1)
        for lines, discount in (([line], True), ([line, line], 0), ([], 0), ([line], 2)):
            with self.assertRaises(ValueError): allocate_discount(lines, discount)
        for args in ((True, 3, 0, 1), (10, True, 0, 1), (10, 3, False, 1), (10, 3, 0, True), (10, 3, 3, 1)):
            with self.assertRaises(ValueError): refund_delta(*args)

    def test_refund_telescopes(self):
        for total in range(20):
            for qty in range(1, 10):
                self.assertEqual(sum(refund_delta(total, qty, c, 1) for c in range(qty)), total)
                for first in range(1, qty):
                    self.assertEqual(refund_delta(total, qty, 0, first) + refund_delta(total, qty, first, qty-first), total)

    def test_inventory_atomic_and_validation(self):
        for op in (reserve, release):
            for items in ({'A':1,'B':True}, {'A':1,'X':1}, {}, {'A':0}):
                stock = {'A':3, 'B':0}
                with self.assertRaises(ValueError): op(stock, items)
                self.assertEqual(stock, {'A':3,'B':0})
        stock = {'A':3,'B':0}
        with self.assertRaises(ValueError): reserve(stock, {'A':1,'B':1})
        self.assertEqual(stock, {'A':3,'B':0})
        self.assertIsNone(release(stock, {'A':2}))
        self.assertIsNone(reserve(stock, {'A':2}))

    def test_ownership(self):
        stock = {'A':5}; e = reservation(); original = deepcopy(e)
        book = OrderBook(stock); book.apply(e)
        self.assertEqual(stock, {'A':5}); self.assertEqual(e, original)
        e['lines'][0]['qty'] = 99; stock['A'] = 99
        snap = book.snapshot(); snap['stock']['A'] = 99
        snap['orders']['o']['remaining']['A'] = 99
        snap['orders']['o']['line_totals']['A'] = 99
        self.assertEqual(book.snapshot()['stock'], {'A':2})
        self.assertEqual(book.snapshot()['orders']['o']['remaining'], {'A':3})
        self.assertEqual(book.snapshot()['orders']['o']['line_totals'], {'A':10})

    def test_ttl_rollback_and_failed_id_reuse(self):
        book = OrderBook({'A':6}); book.apply(reservation()); before = book.snapshot()
        with self.assertRaises(ValueError):
            book.apply(evt('x', 'confirm', at='2026-01-01T01:00:00Z'))
        self.assertEqual(book.snapshot(), before)
        book.apply(reservation('x', 'next', at='2026-01-01T01:00:00Z', expires_at='2026-01-01T02:00:00Z'))
        snap = book.snapshot()
        self.assertEqual(snap['orders']['o']['status'], 'expired')
        self.assertEqual(snap['orders']['o']['remaining'], {'A':0})
        self.assertEqual(snap['stock'], {'A':3})

    def test_confirmed_never_expires_and_refunds_original(self):
        book = OrderBook({'A':3}); book.apply(reservation())
        book.apply(evt('c', 'confirm'))
        for n, expected in ((1,3), (2,6), (3,10)):
            book.apply(evt('x'+str(n), 'cancel', at='2026-01-01T02:00:00Z', items={'A':1}))
            order = book.snapshot()['orders']['o']
            self.assertEqual(order['charged'], 10); self.assertEqual(order['refunded'], expected)
            self.assertEqual(order['status'], 'cancelled' if n == 3 else 'confirmed')
        self.assertEqual(book.snapshot()['stock'], {'A':3})
        before = book.snapshot()
        for kind in ('confirm', 'cancel'):
            with self.assertRaises(ValueError): book.apply(evt('new', kind, at='2026-01-01T02:00:00Z'))
            self.assertEqual(book.snapshot(), before)

    def test_reserved_full_cancel_only(self):
        book = OrderBook({'A':3, 'B':2})
        book.apply(reservation(lines=[dict(sku='A',qty=3,unit_price=4),dict(sku='B',qty=2,unit_price=1)]))
        before = book.snapshot()
        for items in ({'A':3}, {'A':2,'B':2}, {}, {'A':4}, {'X':1}, {'A':True}):
            with self.assertRaises(ValueError): book.apply(evt('x','cancel',items=items))
            self.assertEqual(book.snapshot(), before)
        book.apply(evt('x','cancel',items={'A':3,'B':2}))
        self.assertEqual(book.snapshot()['orders']['o']['refunded'], 0)
        self.assertEqual(book.snapshot()['stock'], {'A':3,'B':2})
        with self.assertRaises(ValueError): book.apply(reservation('new'))

    def test_duplicate_canonicalization_precedes_clock(self):
        book = OrderBook({'A':4}); e = reservation(extra={'z':1,'a':2}); book.apply(e)
        book.apply(evt('c','confirm',at='2026-01-01T00:10:00Z'))
        before = book.snapshot()
        duplicate = dict(reversed(list(e.items())))
        duplicate['extra'] = {'a':2,'z':1}
        duplicate['at'] = '2026-01-01T09:00:00+09:00'
        duplicate['expires_at'] = '2026-01-01T10:00:00+09:00'
        self.assertIsNone(book.apply(duplicate)); self.assertEqual(book.snapshot(), before)
        duplicate['extra']['z'] = 2
        with self.assertRaises(ValueError): book.apply(duplicate)
        self.assertEqual(book.snapshot(), before)
        with self.assertRaises(ValueError): book.apply(evt('old','cancel'))
        self.assertEqual(book.snapshot(), before)

    def test_replay_utc_stable_and_input_preserved(self):
        events = [evt('c','confirm',at='2026-01-01T00:01:00Z'),
                  reservation(at='2026-01-01T09:00:00+09:00'),
                  evt('x','cancel',at='2026-01-01T00:01:00Z',items={'A':1})]
        original = deepcopy(events)
        result = replay({'A':3}, events)
        self.assertEqual(result['orders']['o']['refunded'],3)
        self.assertEqual(replay({'A':3}, events), result)
        self.assertEqual(events, original)
        for bad in ([None], [{}], [{'at':3}], None):
            with self.assertRaises(ValueError): replay({}, bad)

    def test_invalid_events_always_atomic(self):
        book = OrderBook({'A':3}); book.apply(reservation()); before = book.snapshot()
        for bad in (None, [], {}, evt('', 'confirm'), evt('x','bad'),
                    evt('x','confirm',at=None), reservation('x','other',lines=None),
                    evt('x','cancel',items=[]), reservation('x','other',discount=True)):
            with self.assertRaises(ValueError): book.apply(bad)
            self.assertEqual(book.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
