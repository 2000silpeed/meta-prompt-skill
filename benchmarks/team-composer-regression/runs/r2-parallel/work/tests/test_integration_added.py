import unittest
from copy import deepcopy
from shop import OrderBook, replay


def event(eid, kind, oid, at='2026-01-01T00:00:00Z', **extra):
    return dict(id=eid, type=kind, order_id=oid, at=at, **extra)


def reserve_event(eid, oid, lines, **extra):
    return event(eid, 'reserve', oid, lines=lines,
                 expires_at='2026-01-01T01:00:00Z', **extra)


class IntegrationTests(unittest.TestCase):
    def test_unbounded_integer_money_survives_fingerprinting(self):
        huge = 10 ** 5000
        book = OrderBook({'A': 1})
        r = reserve_event('r', 'o', [dict(sku='A', qty=1, unit_price=huge)])
        book.apply(r)
        book.apply(deepcopy(r))
        book.apply(event('c', 'confirm', 'o'))
        book.apply(event('x', 'cancel', 'o'))
        order = book.snapshot()['orders']['o']
        self.assertEqual(order['charged'], huge)
        self.assertEqual(order['refunded'], huge)

    def test_multiline_discount_and_refund_conservation(self):
        # Both allocation ties and zero-price lines travel through the engine.
        for discount in range(13):
            with self.subTest(discount=discount):
                stock = {'B': 3, 'A': 2, 'FREE': 1}
                book = OrderBook(stock)
                lines = [dict(sku='B', qty=3, unit_price=2),
                         dict(sku='A', qty=2, unit_price=3),
                         dict(sku='FREE', qty=1, unit_price=0)]
                book.apply(reserve_event('r', 'o', lines, discount=discount))
                totals = book.snapshot()['orders']['o']['line_totals']
                self.assertEqual(totals, {'B': 6-discount//2,
                                         'A': 6-(discount+1)//2, 'FREE': 0})
                book.apply(event('c', 'confirm', 'o'))
                cancelled = dict.fromkeys(stock, 0)
                for i, sku in enumerate(['A', 'B', 'B', 'FREE', 'A', 'B']):
                    book.apply(event('x'+str(i), 'cancel', 'o',
                                     at='2026-01-02T00:00:00Z', items={sku: 1}))
                    cancelled[sku] += 1
                    snapshot = book.snapshot()
                    order = snapshot['orders']['o']
                    self.assertEqual(order['charged'], 12-discount)
                    self.assertEqual(order['refunded'], sum(
                        totals[k]*cancelled[k]//stock[k] for k in stock))
                    self.assertEqual(snapshot['stock'], cancelled)
                self.assertEqual(order['refunded'], order['charged'])
                self.assertEqual(order['remaining'], dict.fromkeys(stock, 0))
                self.assertEqual(order['status'], 'cancelled')

    def test_multiple_expirations_roll_back_on_inventory_failure(self):
        book = OrderBook({'A': 3, 'B': 2})
        for sku, qty in [('A', 3), ('B', 2)]:
            book.apply(reserve_event('r'+sku, sku,
                                    [dict(sku=sku, qty=qty, unit_price=1)]))
        before = book.snapshot()
        attempt = event('next', 'reserve', 'new', at='2026-01-01T01:00:00Z',
                        expires_at='2026-01-01T02:00:00Z',
                        lines=[dict(sku='A', qty=3, unit_price=1),
                               dict(sku='B', qty=3, unit_price=1)])
        original = deepcopy(attempt)
        with self.assertRaises(ValueError):
            book.apply(attempt)
        self.assertEqual(book.snapshot(), before)
        self.assertEqual(attempt, original)
        attempt['lines'][1]['qty'] = 2
        book.apply(attempt)
        snapshot = book.snapshot()
        self.assertEqual(snapshot['stock'], {'A': 0, 'B': 0})
        for oid in ['A', 'B']:
            self.assertEqual(snapshot['orders'][oid]['status'], 'expired')
            self.assertEqual(snapshot['orders'][oid]['refunded'], 0)
        self.assertEqual(snapshot['as_of'], '2026-01-01T01:00:00+00:00')

    def test_fingerprint_preserves_line_order_and_unknown_nested_fields(self):
        book = OrderBook({'A': 1, 'B': 1})
        r = reserve_event('r', 'o', [dict(sku=k, qty=1, unit_price=1)
                                   for k in ['A', 'B']], meta={'list': [1, {'x': 2}]})
        book.apply(r)
        before = book.snapshot()
        for variant in [dict(r, lines=list(reversed(r['lines']))),
                        dict(r, meta={'list': [1, {'x': 3}]})]:
            with self.assertRaises(ValueError):
                book.apply(variant)
            self.assertEqual(book.snapshot(), before)
        book.apply(deepcopy(r))
        self.assertEqual(book.snapshot(), before)

    def test_replay_is_repeatable_across_offset_day_boundaries(self):
        r = reserve_event('r', 'o', [dict(sku='A', qty=1, unit_price=5)],
                          at='2026-01-01T09:00:00+09:00')
        events = [event('x', 'cancel', 'o', at='2025-12-31T19:02:00-05:00'),
                  event('c', 'confirm', 'o', at='2026-01-01T00:01:00Z'), r]
        original = deepcopy(events)
        first = replay({'A': 1}, events)
        self.assertEqual(first, replay({'A': 1}, events))
        self.assertEqual(events, original)
        self.assertEqual(first['orders']['o']['refunded'], 5)
        self.assertEqual(first['stock'], {'A': 1})


if __name__ == '__main__':
    unittest.main()
