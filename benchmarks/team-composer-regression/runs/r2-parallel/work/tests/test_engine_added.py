import unittest
from copy import deepcopy
from shop import OrderBook, replay


def ev(eid='r', kind='reserve', oid='o', at='2026-01-01T00:00:00Z', **kw):
    return dict(id=eid, type=kind, order_id=oid, at=at, **kw)


def reservation(eid='r', oid='o', at='2026-01-01T00:00:00Z', **kw):
    return ev(eid, oid=oid, at=at, lines=[dict(sku='A', qty=3, unit_price=4)],
              discount=2, expires_at='2026-01-01T01:00:00Z', **kw)


class EngineAddedTests(unittest.TestCase):
    def test_inputs_and_snapshots_are_independent(self):
        stock = {'A': 5}
        event = reservation()
        original = deepcopy(event)
        b = OrderBook(stock)
        b.apply(event)
        self.assertEqual(stock, {'A': 5})
        self.assertEqual(event, original)
        event['lines'][0]['qty'] = 99
        snap = b.snapshot()
        snap['stock']['A'] = 99
        snap['orders']['o']['remaining']['A'] = 99
        self.assertEqual(b.snapshot()['stock']['A'], 2)
        self.assertEqual(b.snapshot()['orders']['o']['remaining']['A'], 3)

    def test_duplicates_before_ordering_and_expiry(self):
        b = OrderBook({'A': 9})
        r = reservation(meta={'a': 1, 'b': 2})
        b.apply(r)
        b.apply(ev('c', 'confirm', at='2026-01-01T00:10:00Z'))
        before = b.snapshot()
        retransmit = dict(reversed(list(r.items())))
        retransmit['at'] = '2026-01-01T09:00:00+09:00'
        retransmit['expires_at'] = '2026-01-01T10:00:00+09:00'
        retransmit['meta'] = {'b': 2, 'a': 1}
        b.apply(retransmit)
        self.assertEqual(b.snapshot(), before)
        retransmit['meta']['a'] = 3
        with self.assertRaises(ValueError):
            b.apply(retransmit)
        self.assertEqual(b.snapshot(), before)

    def test_expiration_rollback_and_failed_id_reuse(self):
        b = OrderBook({'A': 6})
        b.apply(reservation())
        before = b.snapshot()
        with self.assertRaises(ValueError):
            b.apply(ev('next', 'confirm', at='2026-01-01T01:00:00Z'))
        self.assertEqual(b.snapshot(), before)
        b.apply(ev('next', oid='new', at='2026-01-01T01:00:00Z',
                   lines=[dict(sku='A', qty=6, unit_price=1)],
                   expires_at='2026-01-01T02:00:00Z'))
        self.assertEqual(b.snapshot()['orders']['o']['status'], 'expired')
        self.assertEqual(b.snapshot()['orders']['o']['remaining'], {'A': 0})
        self.assertEqual(b.snapshot()['stock'], {'A': 0})

    def test_confirmed_never_expires_and_cumulative_refunds(self):
        b = OrderBook({'A': 3})
        b.apply(reservation())
        b.apply(ev('c', 'confirm'))
        for i, expected in enumerate([3, 6, 10], 1):
            b.apply(ev('x' + str(i), 'cancel', at='2026-01-01T02:00:00Z', items={'A': 1}))
            order = b.snapshot()['orders']['o']
            self.assertEqual(order['refunded'], expected)
            self.assertEqual(order['charged'], 10)
            self.assertEqual(order['status'], 'cancelled' if i == 3 else 'confirmed')
        self.assertEqual(b.snapshot()['stock'], {'A': 3})

    def test_reserved_cancellation_must_be_full(self):
        b = OrderBook({'A': 3})
        b.apply(reservation())
        before = b.snapshot()
        with self.assertRaises(ValueError):
            b.apply(ev('x', 'cancel', items={'A': 1}))
        self.assertEqual(b.snapshot(), before)
        b.apply(ev('x', 'cancel'))
        self.assertEqual(b.snapshot()['orders']['o']['refunded'], 0)
        self.assertEqual(b.snapshot()['stock'], {'A': 3})
        for e in [ev('y', 'confirm'), ev('y', 'cancel'), reservation('y')]:
            before = b.snapshot()
            with self.assertRaises(ValueError):
                b.apply(e)
            self.assertEqual(b.snapshot(), before)

    def test_replay_utc_sort_and_equal_time_stability(self):
        r = reservation(at='2026-01-01T09:00:00+09:00')
        c = ev('c', 'confirm', at='2026-01-01T00:01:00Z')
        events = [c, r]
        original = deepcopy(events)
        self.assertEqual(replay({'A': 3}, events)['orders']['o']['charged'], 10)
        self.assertEqual(events, original)
        self.assertEqual(replay({'A': 3}, [r, ev('c', 'confirm')])['orders']['o']['status'], 'confirmed')
        with self.assertRaises(ValueError):
            replay({'A': 3}, [ev('c', 'confirm'), r])

    def test_invalid_events_are_atomic(self):
        b = OrderBook({'A': 3})
        b.apply(reservation())
        before = b.snapshot()
        bad = [None, [], {}, ev('c', 'unknown'), ev('c', 'cancel', items={}),
               ev('c', 'cancel', items={'A': True}), ev('c', 'cancel', items={'B': 1}),
               ev('c', 'cancel', items={'A': 4}), ev('c', 'confirm', at='bad'),
               ev('c', 'confirm', at='2025-12-31T00:00:00Z')]
        for event in bad:
            with self.subTest(event=event):
                with self.assertRaises(ValueError):
                    b.apply(event)
                self.assertEqual(b.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
