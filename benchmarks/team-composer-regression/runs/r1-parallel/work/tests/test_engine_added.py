import unittest
from copy import deepcopy
from shop import OrderBook, replay


def ev(eid, kind='reserve', oid='o', at='2026-01-01T00:00:00Z', **extra):
    return dict(id=eid, type=kind, order_id=oid, at=at, **extra)


def reservation(eid='r', oid='o', **extra):
    fields = dict(lines=[dict(sku='A', qty=3, unit_price=4)], discount=2,
                  expires_at='2026-01-01T01:00:00Z')
    fields.update(extra)
    return ev(eid, oid=oid, **fields)


class EngineAddedTests(unittest.TestCase):
    def book(self):
        book = OrderBook({'A': 10, 'B': 2})
        book.apply(reservation())
        return book

    def assertRejected(self, book, event):
        before = book.snapshot()
        with self.assertRaises(ValueError):
            book.apply(event)
        self.assertEqual(book.snapshot(), before)

    def test_no_aliases(self):
        stock = {'A': 10}
        event = reservation()
        original = deepcopy(event)
        book = OrderBook(stock)
        book.apply(event)
        self.assertEqual(stock, {'A': 10})
        self.assertEqual(event, original)
        stock['A'] = 0
        event['lines'][0]['qty'] = 100
        snapshot = book.snapshot()
        snapshot['stock']['A'] = 100
        snapshot['orders']['o']['remaining']['A'] = 100
        snapshot['orders']['o']['line_totals']['A'] = 100
        self.assertEqual(book.snapshot()['stock'], {'A': 7})
        self.assertEqual(book.snapshot()['orders']['o']['remaining'], {'A': 3})
        self.assertEqual(book.snapshot()['orders']['o']['line_totals'], {'A': 10})

    def test_expiry_rollback_and_failed_id_reuse(self):
        book = self.book()
        self.assertRejected(book, ev('next', 'confirm', at='2026-01-01T01:00:00Z'))
        book.apply(reservation('next', 'other', at='2026-01-01T01:00:00Z',
                               expires_at='2026-01-01T02:00:00Z'))
        snapshot = book.snapshot()
        self.assertEqual(snapshot['orders']['o']['status'], 'expired')
        self.assertEqual(snapshot['orders']['o']['remaining'], {'A': 0})
        self.assertEqual(snapshot['stock']['A'], 7)
        self.assertRejected(book, ev('bad', 'cancel', at='2026-01-01T01:00:00Z'))
        self.assertRejected(book, reservation('again', at='2026-01-01T01:00:00Z',
                                              expires_at='2026-01-01T02:00:00Z'))

    def test_duplicates_canonical_and_old(self):
        book = OrderBook({'A': 10})
        original = reservation(metadata={'a': 1, 'b': 2})
        book.apply(original)
        book.apply(ev('c', 'confirm', at='2026-01-01T00:30:00Z'))
        before = book.snapshot()
        reordered = dict(reversed(list(original.items())))
        reordered['at'] = '2026-01-01T09:00:00+09:00'
        reordered['expires_at'] = '2026-01-01T10:00:00+09:00'
        reordered['metadata'] = {'b': 2, 'a': 1}
        self.assertIsNone(book.apply(reordered))
        self.assertEqual(book.snapshot(), before)
        reordered['metadata']['a'] = 2
        self.assertRejected(book, reordered)

    def test_reserved_partial_and_full_cancel(self):
        book = self.book()
        self.assertRejected(book, ev('partial', 'cancel', items={'A': 1}))
        book.apply(ev('all', 'cancel'))
        order = book.snapshot()['orders']['o']
        self.assertEqual((order['status'], order['refunded'], order['charged']), ('cancelled', 0, 0))
        self.assertEqual(book.snapshot()['stock']['A'], 10)
        self.assertRejected(book, ev('again', 'confirm'))

    def test_confirmed_refunds_and_no_ttl(self):
        book = self.book()
        book.apply(ev('c', 'confirm'))
        for index, expected in enumerate([3, 6, 10]):
            book.apply(ev(str(index), 'cancel', at='2026-01-01T02:00:00Z', items={'A': 1}))
            order = book.snapshot()['orders']['o']
            self.assertEqual(order['refunded'], expected)
            self.assertEqual(order['charged'], 10)
            self.assertEqual(order['status'], 'cancelled' if index == 2 else 'confirmed')
        self.assertEqual(book.snapshot()['stock']['A'], 10)

    def test_invalid_inputs_atomic(self):
        for stock in [None, [], {'': 1}, {'A': True}, {'A': -1}]:
            with self.assertRaises(ValueError):
                OrderBook(stock)
        book = self.book()
        for event in [None, [], {}, ev('x', 'other'), ev('x', 'cancel', items={}),
                      ev('x', 'cancel', items={'A': True}), ev('x', 'cancel', items={'B': 1}),
                      ev('x', 'cancel', items={'A': 4}), ev('x', 'cancel', at='2025-01-01T00:00:00Z'),
                      reservation('x', 'new', lines=[dict(sku='A', qty=100, unit_price=1)]),
                      reservation('x', 'new', expires_at='2026-01-01T00:00:00Z')]:
            self.assertRejected(book, event)

    def test_replay_utc_and_stable_order(self):
        events = [ev('c', 'confirm', at='2025-12-31T20:00:00-04:00'),
                  reservation(at='2026-01-01T08:00:00+09:00')]
        before = deepcopy(events)
        result = replay({'A': 10}, events)
        self.assertEqual(result['orders']['o']['status'], 'confirmed')
        self.assertEqual(events, before)
        self.assertEqual(result, replay({'A': 10}, events))
        self.assertEqual(replay({'A': 10}, [reservation(), ev('c', 'confirm')])['orders']['o']['charged'], 10)
        with self.assertRaises(ValueError):
            replay({'A': 10}, [ev('c', 'confirm'), reservation()])
        for invalid in [None, [None], [{}], [dict(at='invalid')]]:
            with self.assertRaises(ValueError):
                replay({'A': 10}, invalid)


if __name__ == '__main__':
    unittest.main()
