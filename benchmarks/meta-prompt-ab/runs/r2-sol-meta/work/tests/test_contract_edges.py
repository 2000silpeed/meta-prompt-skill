import copy
import unittest

from shop import OrderBook, replay
from shop.clock import parse_time
from shop.money import allocate_discount, refund_delta


def event(eid, kind, oid, at, **extra):
    return dict(id=eid, type=kind, order_id=oid, at=at, **extra)


class ContractEdgeTests(unittest.TestCase):
    def test_exact_money_and_bool_validation(self):
        lines = [
            {'sku': 'B', 'qty': 1, 'unit_price': 1},
            {'sku': 'A', 'qty': 1, 'unit_price': 1},
        ]
        self.assertEqual(allocate_discount(lines, 1), {'B': 1, 'A': 0})
        self.assertEqual(sum(refund_delta(10, 3, n, 1) for n in range(3)), 10)
        with self.assertRaises(ValueError):
            allocate_discount([{'sku': 'A', 'qty': True, 'unit_price': 1}], 0)

    def test_ttl_failure_is_fully_atomic(self):
        book = OrderBook({'A': 2})
        book.apply(event(
            'r', 'reserve', 'o', '2026-01-01T00:00:00Z',
            lines=[{'sku': 'A', 'qty': 1, 'unit_price': 1}],
            expires_at='2026-01-01T01:00:00Z',
        ))
        before = book.snapshot()
        with self.assertRaises(ValueError):
            book.apply(event('c', 'confirm', 'o', '2026-01-01T01:00:00Z'))
        self.assertEqual(book.snapshot(), before)

    def test_duplicate_precedes_time_check_and_normalizes_offsets(self):
        book = OrderBook({'A': 1})
        original = event(
            'r', 'reserve', 'o', '2026-01-01T00:00:00Z',
            lines=[{'sku': 'A', 'qty': 1, 'unit_price': 1}],
            expires_at='2026-01-01T01:00:00Z',
        )
        book.apply(original)
        book.apply(event('c', 'confirm', 'o', '2026-01-01T00:30:00Z'))
        before = book.snapshot()
        duplicate = copy.deepcopy(original)
        duplicate['at'] = '2025-12-31T19:00:00-05:00'
        duplicate['expires_at'] = '2025-12-31T20:00:00-05:00'
        book.apply(duplicate)
        self.assertEqual(book.snapshot(), before)

    def test_inputs_and_snapshots_do_not_alias(self):
        stock = {'A': 2}
        book = OrderBook(stock)
        stock['A'] = 99
        self.assertEqual(book.snapshot()['stock'], {'A': 2})
        snapshot = book.snapshot()
        snapshot['stock']['A'] = 0
        self.assertEqual(book.snapshot()['stock'], {'A': 2})

    def test_replay_orders_by_instant_and_preserves_input(self):
        events = [
            event('c', 'confirm', 'o', '2026-01-01T09:30:00+09:00'),
            event(
                'r', 'reserve', 'o', '2025-12-31T19:00:00-05:00',
                lines=[{'sku': 'A', 'qty': 1, 'unit_price': 1}],
                expires_at='2026-01-01T02:00:00Z',
            ),
        ]
        before = copy.deepcopy(events)
        result = replay({'A': 1}, events)
        self.assertEqual(result['orders']['o']['status'], 'confirmed')
        self.assertEqual(events, before)

    def test_naive_time_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_time('2026-01-01T00:00:00')


if __name__ == '__main__':
    unittest.main()
