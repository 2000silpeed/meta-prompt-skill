import copy
import unittest

from shop import OrderBook, replay
from shop.clock import parse_time
from shop.inventory import release, reserve
from shop.money import allocate_discount, refund_delta


def reserve_event(eid='r', oid='o', at='2026-01-01T00:00:00Z', expires='2026-01-01T01:00:00Z'):
    return {
        'id': eid,
        'type': 'reserve',
        'order_id': oid,
        'at': at,
        'lines': [
            {'sku': 'A', 'qty': 3, 'unit_price': 10},
            {'sku': 'B', 'qty': 1, 'unit_price': 10},
        ],
        'discount': 1,
        'expires_at': expires,
    }


class AdditionalContractTests(unittest.TestCase):
    def test_time_requires_offset_and_normalizes(self):
        with self.assertRaises(ValueError):
            parse_time('2026-01-01T00:00:00')
        with self.assertRaises(ValueError):
            parse_time('2026-01-01')
        self.assertEqual(
            parse_time('2026-01-01T09:00:00+09:00').isoformat(),
            '2026-01-01T00:00:00+00:00',
        )

    def test_money_is_exact_and_rejects_bool(self):
        lines = [
            {'sku': 'B', 'qty': 1, 'unit_price': 1},
            {'sku': 'A', 'qty': 1, 'unit_price': 1},
        ]
        self.assertEqual(allocate_discount(lines, 1), {'B': 1, 'A': 0})
        self.assertEqual([refund_delta(10, 3, n, 1) for n in range(3)], [3, 3, 4])
        with self.assertRaises(ValueError):
            allocate_discount([{'sku': 'A', 'qty': True, 'unit_price': 1}], 0)

    def test_inventory_operations_are_atomic(self):
        stock = {'A': 2, 'B': 0}
        with self.assertRaises(ValueError):
            reserve(stock, {'A': 1, 'B': 1})
        self.assertEqual(stock, {'A': 2, 'B': 0})
        with self.assertRaises(ValueError):
            release(stock, {'A': 1, 'missing': 1})
        self.assertEqual(stock, {'A': 2, 'B': 0})

    def test_inputs_and_snapshots_do_not_alias(self):
        stock = {'A': 5, 'B': 5}
        event = reserve_event()
        original = copy.deepcopy(event)
        book = OrderBook(stock)
        stock['A'] = 99
        book.apply(event)
        event['lines'][0]['qty'] = 99
        snapshot = book.snapshot()
        snapshot['stock']['A'] = 99
        snapshot['orders']['o']['remaining']['A'] = 99
        self.assertEqual(event, {**original, 'lines': [{**original['lines'][0], 'qty': 99}, original['lines'][1]]})
        self.assertEqual(book.snapshot()['stock']['A'], 2)
        self.assertEqual(book.snapshot()['orders']['o']['remaining']['A'], 3)

    def test_expiration_boundary_rolls_back_with_rejected_event(self):
        book = OrderBook({'A': 5, 'B': 5})
        book.apply(reserve_event())
        before = book.snapshot()
        with self.assertRaises(ValueError):
            book.apply({'id': 'c', 'type': 'confirm', 'order_id': 'o', 'at': '2026-01-01T01:00:00Z'})
        self.assertEqual(book.snapshot(), before)
        book.apply({
            'id': 'r2', 'type': 'reserve', 'order_id': 'o2',
            'at': '2026-01-01T01:00:00Z',
            'lines': [{'sku': 'A', 'qty': 1, 'unit_price': 1}],
            'expires_at': '2026-01-01T02:00:00Z',
        })
        self.assertEqual(book.snapshot()['orders']['o']['status'], 'expired')

    def test_duplicate_normalizes_time_and_precedes_chronology(self):
        book = OrderBook({'A': 5, 'B': 5})
        first = reserve_event(at='2026-01-01T09:00:00+09:00', expires='2026-01-01T10:00:00+09:00')
        book.apply(first)
        book.apply({'id': 'c', 'type': 'confirm', 'order_id': 'o', 'at': '2026-01-01T00:30:00Z'})
        retry = reserve_event(at='2026-01-01T00:00:00Z', expires='2026-01-01T01:00:00Z')
        self.assertIsNone(book.apply(retry))
        before = book.snapshot()
        retry['extra'] = 1
        with self.assertRaises(ValueError):
            book.apply(retry)
        self.assertEqual(book.snapshot(), before)

    def test_reserved_cancel_requires_whole_order(self):
        book = OrderBook({'A': 5, 'B': 5})
        book.apply(reserve_event())
        before = book.snapshot()
        with self.assertRaises(ValueError):
            book.apply({
                'id': 'x', 'type': 'cancel', 'order_id': 'o',
                'at': '2026-01-01T00:10:00Z', 'items': {'A': 1},
            })
        self.assertEqual(book.snapshot(), before)

    def test_confirmed_partial_cancel_refunds_cumulatively(self):
        book = OrderBook({'A': 5, 'B': 5})
        event = reserve_event()
        event['lines'] = [{'sku': 'A', 'qty': 3, 'unit_price': 10}]
        event['discount'] = 20
        book.apply(event)
        book.apply({'id': 'c', 'type': 'confirm', 'order_id': 'o', 'at': '2026-01-01T00:01:00Z'})
        for index in range(3):
            book.apply({
                'id': 'x' + str(index), 'type': 'cancel', 'order_id': 'o',
                'at': '2026-01-01T00:0{}:00Z'.format(index + 2), 'items': {'A': 1},
            })
        order = book.snapshot()['orders']['o']
        self.assertEqual(order['refunded'], 10)
        self.assertEqual(order['charged'], 10)
        self.assertEqual(order['status'], 'cancelled')

    def test_replay_uses_utc_order_without_mutating_events(self):
        reservation = reserve_event(at='2026-01-01T01:00:00+01:00')
        confirmation = {'id': 'c', 'type': 'confirm', 'order_id': 'o', 'at': '2026-01-01T00:30:00Z'}
        events = [confirmation, reservation]
        original = copy.deepcopy(events)
        result = replay({'A': 5, 'B': 5}, events)
        self.assertEqual(result['orders']['o']['status'], 'confirmed')
        self.assertEqual(events, original)


if __name__ == '__main__':
    unittest.main()
