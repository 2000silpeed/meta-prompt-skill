import unittest
from copy import deepcopy

from shop import OrderBook, replay


START = '2026-01-01T00:00:00Z'
TTL = '2026-01-01T01:00:00Z'
LATER = '2026-01-01T02:00:00Z'


def event(eid, kind, oid='o', at=START, **fields):
    return dict(id=eid, type=kind, order_id=oid, at=at, **fields)


def reservation(eid='r', oid='o', **fields):
    values = dict(lines=[dict(sku='B', qty=2, unit_price=3),
                        dict(sku='A', qty=3, unit_price=2)],
                  discount=3, expires_at=TTL)
    values.update(fields)
    return event(eid, 'reserve', oid, **values)


class IntegrationTests(unittest.TestCase):
    def test_multisku_allocation_and_cumulative_refund(self):
        book = OrderBook({'A': 3, 'B': 2})
        book.apply(reservation())
        self.assertEqual(book.snapshot()['orders']['o']['line_totals'], {'A': 4, 'B': 5})
        book.apply(event('c', 'confirm'))
        book.apply(event('x1', 'cancel', items={'A': 1, 'B': 1}))
        self.assertEqual(book.snapshot()['orders']['o']['refunded'], 3)
        book.apply(event('x2', 'cancel', items={'A': 2}))
        self.assertEqual(book.snapshot()['orders']['o']['remaining'], {'A': 0, 'B': 1})
        book.apply(event('x3', 'cancel', at=LATER))
        order = book.snapshot()['orders']['o']
        self.assertEqual((order['charged'], order['refunded'], order['status']), (9, 9, 'cancelled'))
        self.assertEqual(book.snapshot()['stock'], {'A': 3, 'B': 2})

    def test_expiry_then_failed_multisku_reserve_is_atomic(self):
        book = OrderBook({'A': 3, 'B': 2})
        book.apply(reservation())
        before = book.snapshot()
        bad = reservation('next', 'new', at=TTL, expires_at=LATER,
                          lines=[dict(sku='A', qty=1, unit_price=1),
                                 dict(sku='B', qty=3, unit_price=1)], discount=0)
        with self.assertRaises(ValueError):
            book.apply(bad)
        self.assertEqual(book.snapshot(), before)
        bad['lines'][1]['qty'] = 2
        book.apply(bad)
        self.assertEqual(book.snapshot()['orders']['o']['status'], 'expired')
        self.assertEqual(book.snapshot()['stock'], {'A': 2, 'B': 0})

    def test_reserved_multisku_partial_rejection_and_full_cancel(self):
        book = OrderBook({'A': 3, 'B': 2})
        book.apply(reservation())
        before = book.snapshot()
        for items in ({'A': 3}, {'A': 4, 'B': 1}, {'A': 3, 'B': True}):
            with self.assertRaises(ValueError):
                book.apply(event('x', 'cancel', items=items))
            self.assertEqual(book.snapshot(), before)
        book.apply(event('x', 'cancel', items={'A': 3, 'B': 2}))
        self.assertEqual(book.snapshot()['stock'], {'A': 3, 'B': 2})
        self.assertEqual(book.snapshot()['orders']['o']['refunded'], 0)

    def test_fingerprint_preserves_lines_order_and_nested_unknown_values(self):
        book = OrderBook({'A': 3, 'B': 2})
        original = reservation(metadata={'outer': {'x': [1, 2], 'y': True}})
        book.apply(original)
        before = book.snapshot()
        duplicate = deepcopy(original)
        duplicate['metadata'] = {'outer': {'y': True, 'x': [1, 2]}}
        duplicate['expires_at'] = '2026-01-01T10:00:00+09:00'
        book.apply(duplicate)
        for changed in (dict(duplicate, lines=list(reversed(duplicate['lines']))),
                        dict(duplicate, metadata={'outer': {'x': [2, 1], 'y': True}})):
            with self.assertRaises(ValueError):
                book.apply(changed)
            self.assertEqual(book.snapshot(), before)

    def test_zero_price_end_to_end_and_replay_input_preservation(self):
        events = [reservation(lines=[dict(sku='A', qty=2, unit_price=0)], discount=0),
                  event('c', 'confirm'), event('x', 'cancel', at=LATER)]
        before = deepcopy(events)
        result = replay({'A': 2}, events)
        self.assertEqual(result['stock'], {'A': 2})
        self.assertEqual(result['orders']['o']['remaining'], {'A': 0})
        self.assertEqual(result['orders']['o']['charged'], 0)
        self.assertEqual(result['orders']['o']['refunded'], 0)
        self.assertEqual(events, before)
        self.assertEqual(result, replay({'A': 2}, events))


if __name__ == '__main__':
    unittest.main()
