import unittest

from shop import OrderBook, replay
from shop.clock import parse_time
from shop.inventory import release, reserve
from shop.money import allocate_discount, refund_delta


def reserve_event(eid='r', oid='o', at='2026-01-01T00:00:00Z', expires='2026-01-01T01:00:00Z'):
    return {
        'id': eid, 'type': 'reserve', 'order_id': oid, 'at': at,
        'expires_at': expires,
        'lines': [
            {'sku': 'A', 'qty': 2, 'unit_price': 5},
            {'sku': 'B', 'qty': 1, 'unit_price': 5},
        ],
        'discount': 2,
    }


class AdditionalTests(unittest.TestCase):
    def test_bool_is_not_numeric(self):
        with self.assertRaises(ValueError):
            allocate_discount([{'sku': 'A', 'qty': True, 'unit_price': 2}], 0)
        with self.assertRaises(ValueError):
            refund_delta(1, True, 0, 1)

    def test_discount_tie_uses_sku(self):
        lines = [
            {'sku': 'Z', 'qty': 1, 'unit_price': 1},
            {'sku': 'A', 'qty': 1, 'unit_price': 1},
        ]
        self.assertEqual(allocate_discount(lines, 1), {'Z': 1, 'A': 0})

    def test_refund_telescopes(self):
        self.assertEqual([refund_delta(10, 3, c, 1) for c in range(3)], [3, 3, 4])

    def test_inventory_operations_are_atomic(self):
        stock = {'A': 1, 'B': 0}
        with self.assertRaises(ValueError):
            reserve(stock, {'A': 1, 'B': 1})
        self.assertEqual(stock, {'A': 1, 'B': 0})
        with self.assertRaises(ValueError):
            release(stock, {'A': 1, 'C': 1})
        self.assertEqual(stock, {'A': 1, 'B': 0})

    def test_input_and_snapshot_are_not_aliased(self):
        stock = {'A': 3, 'B': 2}
        event = reserve_event()
        book = OrderBook(stock)
        book.apply(event)
        stock['A'] = 99
        event['lines'][0]['qty'] = 99
        snap = book.snapshot()
        snap['stock']['A'] = 99
        snap['orders']['o']['remaining']['A'] = 99
        self.assertEqual(book.snapshot()['stock']['A'], 1)
        self.assertEqual(book.snapshot()['orders']['o']['remaining']['A'], 2)

    def test_exact_expiry_failure_is_fully_atomic(self):
        book = OrderBook({'A': 3, 'B': 2})
        book.apply(reserve_event())
        before = book.snapshot()
        with self.assertRaises(ValueError):
            book.apply({'id': 'c', 'type': 'confirm', 'order_id': 'o',
                        'at': '2026-01-01T01:00:00Z'})
        self.assertEqual(book.snapshot(), before)

    def test_expiry_commits_with_later_success(self):
        book = OrderBook({'A': 3, 'B': 2})
        book.apply(reserve_event())
        book.apply(reserve_event('r2', 'o2', at='2026-01-01T01:00:00Z',
                                 expires='2026-01-01T02:00:00Z'))
        snap = book.snapshot()
        self.assertEqual(snap['orders']['o']['status'], 'expired')
        self.assertEqual(snap['orders']['o']['remaining'], {'A': 0, 'B': 0})

    def test_confirmed_order_does_not_expire(self):
        book = OrderBook({'A': 5, 'B': 3})
        book.apply(reserve_event())
        book.apply({'id': 'c', 'type': 'confirm', 'order_id': 'o',
                    'at': '2026-01-01T00:30:00Z'})
        book.apply(reserve_event('r2', 'o2', at='2026-01-01T02:00:00Z',
                                 expires='2026-01-01T03:00:00Z'))
        self.assertEqual(book.snapshot()['orders']['o']['status'], 'confirmed')

    def test_reserved_partial_cancel_is_rejected(self):
        book = OrderBook({'A': 3, 'B': 2})
        book.apply(reserve_event())
        before = book.snapshot()
        with self.assertRaises(ValueError):
            book.apply({'id': 'x', 'type': 'cancel', 'order_id': 'o',
                        'at': '2026-01-01T00:10:00Z', 'items': {'A': 1}})
        self.assertEqual(book.snapshot(), before)

    def test_confirmed_refunds_by_line(self):
        book = OrderBook({'A': 3, 'B': 2})
        book.apply(reserve_event())
        book.apply({'id': 'c', 'type': 'confirm', 'order_id': 'o',
                    'at': '2026-01-01T00:10:00Z'})
        book.apply({'id': 'x1', 'type': 'cancel', 'order_id': 'o',
                    'at': '2026-01-01T00:20:00Z', 'items': {'A': 1}})
        book.apply({'id': 'x2', 'type': 'cancel', 'order_id': 'o',
                    'at': '2026-01-01T00:30:00Z'})
        order = book.snapshot()['orders']['o']
        self.assertEqual(order['status'], 'cancelled')
        self.assertEqual(order['refunded'], order['charged'])

    def test_duplicate_normalizes_offsets_and_key_order(self):
        event = reserve_event()
        book = OrderBook({'A': 3, 'B': 2})
        book.apply(event)
        duplicate = {
            'discount': 2,
            'lines': event['lines'],
            'expires_at': '2026-01-01T10:00:00+09:00',
            'at': '2026-01-01T09:00:00+09:00',
            'order_id': 'o', 'type': 'reserve', 'id': 'r',
        }
        self.assertIsNone(book.apply(duplicate))

    def test_replay_orders_by_instant_stably(self):
        events = [
            reserve_event(at='2026-01-01T09:00:00+09:00'),
            {'id': 'c', 'type': 'confirm', 'order_id': 'o',
             'at': '2026-01-01T00:00:00Z'},
        ]
        original = [dict(e) for e in events]
        result = replay({'A': 3, 'B': 2}, events)
        self.assertEqual(result['orders']['o']['status'], 'confirmed')
        self.assertEqual(events, original)

    def test_parse_rejects_naive_and_date_only(self):
        for value in ('2026-01-01T00:00:00', '2026-01-01', None):
            with self.assertRaises(ValueError):
                parse_time(value)


if __name__ == '__main__':
    unittest.main()
