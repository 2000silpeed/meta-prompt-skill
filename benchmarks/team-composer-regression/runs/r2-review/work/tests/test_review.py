"""Independent contract tests added during review."""
from copy import deepcopy
import unittest

from shop import OrderBook, replay
from shop.money import allocate_discount


def event(eid, kind, oid, at='2026-01-01T00:00:00Z', **extra):
    return dict(id=eid, type=kind, order_id=oid, at=at, **extra)


def reservation(eid, oid, lines, **extra):
    return event(eid, 'reserve', oid, lines=lines,
                 expires_at='2026-01-01T01:00:00Z', **extra)


class ReviewTests(unittest.TestCase):
    def test_multiple_expirations_rollback_then_reuse_failed_id(self):
        book = OrderBook({'A': 3, 'B': 2})
        book.apply(reservation('r1', 'one', [dict(sku='A', qty=3, unit_price=7)]))
        book.apply(reservation('r2', 'two', [dict(sku='B', qty=2, unit_price=0)]))
        before = book.snapshot()
        with self.assertRaises(ValueError):
            book.apply(event('retry', 'cancel', 'missing', '2026-01-01T01:00:00Z'))
        self.assertEqual(book.snapshot(), before)
        book.apply(event('retry', 'reserve', 'three', '2026-01-01T01:00:00Z',
                         lines=[dict(sku='A', qty=3, unit_price=1)],
                         expires_at='2026-01-01T02:00:00Z'))
        result = book.snapshot()
        self.assertEqual(result['stock'], {'A': 0, 'B': 2})
        for oid, sku in [('one', 'A'), ('two', 'B')]:
            self.assertEqual(result['orders'][oid], dict(status='expired',
                remaining={sku: 0}, line_totals={sku: 21 if sku == 'A' else 0},
                charged=0, refunded=0))

    def test_zero_price_and_exhausted_sku_omitted_cancel(self):
        book = OrderBook({'A': 2, 'B': 3})
        book.apply(reservation('r', 'o', [dict(sku='A', qty=2, unit_price=0),
                                           dict(sku='B', qty=3, unit_price=4)], discount=2))
        book.apply(event('c', 'confirm', 'o'))
        book.apply(event('x', 'cancel', 'o', items={'A': 2, 'B': 1}))
        before = book.snapshot()
        with self.assertRaises(ValueError):
            book.apply(event('bad', 'cancel', 'o', items={'B': 1, 'A': 1}))
        self.assertEqual(book.snapshot(), before)
        book.apply(event('rest', 'cancel', 'o'))
        self.assertEqual(book.snapshot()['stock'], {'A': 2, 'B': 3})
        self.assertEqual(book.snapshot()['orders']['o'], dict(status='cancelled',
            remaining={'A': 0, 'B': 0}, line_totals={'A': 0, 'B': 10},
            charged=10, refunded=10))

    def test_line_order_and_unknown_keys_participate_in_fingerprint(self):
        book = OrderBook({'A': 1, 'B': 1})
        first = reservation('r', 'o', [dict(sku='A', qty=1, unit_price=1),
                                      dict(sku='B', qty=1, unit_price=1)],
                            metadata={'nested': [1, {'x': True}]})
        book.apply(first)
        before = book.snapshot()
        changed = deepcopy(first)
        changed['lines'].reverse()
        with self.assertRaises(ValueError):
            book.apply(changed)
        changed = deepcopy(first)
        changed['metadata']['nested'][1]['x'] = False
        with self.assertRaises(ValueError):
            book.apply(changed)
        self.assertEqual(book.snapshot(), before)
        book.apply(deepcopy(first))
        self.assertEqual(book.snapshot(), before)

    def test_discount_remainder_is_fractional_not_gross_order(self):
        lines = [dict(sku='A', qty=1, unit_price=8),
                 dict(sku='B', qty=1, unit_price=7),
                 dict(sku='C', qty=1, unit_price=5)]
        self.assertEqual(allocate_discount(lines, 3), {'A': 7, 'B': 6, 'C': 4})
        self.assertEqual(allocate_discount(lines, 20), {'A': 0, 'B': 0, 'C': 0})

    def test_empty_stock_and_same_instant_replay_stability(self):
        self.assertEqual(replay({}, []), {'stock': {}, 'orders': {}, 'as_of': None})
        events = [reservation('r', 'o', [dict(sku='A', qty=1, unit_price=0)]),
                  event('c', 'confirm', 'o', '2026-01-01T09:00:00+09:00'),
                  event('x', 'cancel', 'o', '2025-12-31T19:00:00-05:00')]
        original = deepcopy(events)
        self.assertEqual(replay({'A': 1}, events)['orders']['o']['status'], 'cancelled')
        self.assertEqual(events, original)
        with self.assertRaises(ValueError):
            replay({'A': 1}, [events[1], events[0], events[2]])


if __name__ == '__main__':
    unittest.main()
