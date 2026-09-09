import copy
import unittest
from datetime import timezone
from shop.clock import parse_time
from shop.money import allocate_discount, refund_delta
from shop.inventory import reserve, release


class FoundationTests(unittest.TestCase):
    def test_utc_offsets_and_fraction(self):
        expected = parse_time('2026-01-01T00:00:00.123456Z')
        for timestamp in ('2026-01-01T09:00:00.123456+09:00',
                          '2025-12-31T19:00:00.123456-05:00'):
            self.assertEqual(parse_time(timestamp), expected)
            self.assertIs(parse_time(timestamp).tzinfo, timezone.utc)

    def test_invalid_times(self):
        for value in (None, True, 0, [], {}, '', '2026-01-01',
                      '2026-01-01T00:00:00', '2026-02-30T00:00:00Z',
                      '0001-01-01T00:00:00+01:00', '2026-01-01T00:00:00+25:00'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_time(value)

    def test_discount_ties_are_lexical_and_input_unchanged(self):
        lines = [dict(sku=s, qty=1, unit_price=1) for s in ('ZZZ', 'B', 'A')]
        before = copy.deepcopy(lines)
        self.assertEqual(allocate_discount(lines, 2), {'ZZZ': 1, 'B': 0, 'A': 0})
        self.assertEqual(lines, before)

    def test_huge_exact_discount(self):
        n = 10 ** 400
        lines = [dict(sku='A', qty=1, unit_price=n + 1),
                 dict(sku='B', qty=1, unit_price=n)]
        self.assertEqual(allocate_discount(lines, n),
                         {'A': n // 2 + 1, 'B': n // 2})
        self.assertEqual(allocate_discount(lines, 2 * n + 1), {'A': 0, 'B': 0})

    def test_zero_subtotal(self):
        lines = [dict(sku='A', qty=5, unit_price=0)]
        self.assertEqual(allocate_discount(lines, 0), {'A': 0})
        with self.assertRaises(ValueError):
            allocate_discount(lines, 1)

    def test_discount_validation(self):
        good = dict(sku='A', qty=1, unit_price=3)
        for discount in (True, False, -1, 4, 0.0, None):
            with self.subTest(discount=discount), self.assertRaises(ValueError):
                allocate_discount([good], discount)
        for lines in (None, {}, [], [None], [good, good],
                      [dict(good, sku='')], [dict(good, sku=4)],
                      [dict(good, qty=True)], [dict(good, qty=0)],
                      [dict(good, unit_price=False)], [dict(good, unit_price=-1)],
                      [dict(sku='A', qty=1)]):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                allocate_discount(lines, 0)

    def test_refund_telescopes_for_different_batches(self):
        for total in (0, 1, 10, 10 ** 100 + 3):
            for qty in range(1, 12):
                single = [refund_delta(total, qty, i, 1) for i in range(qty)]
                self.assertEqual(sum(single), total)
                for start in range(qty):
                    for delta in range(1, qty - start + 1):
                        self.assertEqual(refund_delta(total, qty, start, delta),
                                         sum(single[start:start + delta]))

    def test_refund_validation(self):
        for args in ((-1, 3, 0, 1), (1, 0, 0, 1), (1, 3, -1, 1),
                     (1, 3, 3, 1), (1, 3, 0, 0), (1, 3, 2, 2)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                refund_delta(*args)
        for index in range(4):
            for bad in (True, False, None, 1.0, '1'):
                args = [10, 3, 0, 1]
                args[index] = bad
                with self.subTest(args=args), self.assertRaises(ValueError):
                    refund_delta(*args)

    def test_inventory_atomic_validation_and_round_trip(self):
        for fn in (reserve, release):
            for items in ({}, {'A': 1, 'Z': 1}, {'A': 1, 'B': False},
                          {'A': 1, 'B': -1}, {'A': 1, 'B': 1.0}, None):
                stock = {'A': 3, 'B': 2}
                with self.subTest(fn=fn.__name__, items=items), self.assertRaises(ValueError):
                    fn(stock, items)
                self.assertEqual(stock, {'A': 3, 'B': 2})
            for stock in ({'A': 3, 'B': True}, {'A': 3, '': 1}, {'A': -1}):
                before = stock.copy()
                with self.assertRaises(ValueError):
                    fn(stock, {'A': 1})
                self.assertEqual(stock, before)
        stock = {'A': 3, 'B': 2}
        items = {'A': 2, 'B': 2}
        self.assertIsNone(reserve(stock, items))
        self.assertEqual(stock, {'A': 1, 'B': 0})
        self.assertIsNone(release(stock, items))
        self.assertEqual(stock, {'A': 3, 'B': 2})
        self.assertEqual(items, {'A': 2, 'B': 2})

    def test_reservation_shortage_rolls_back(self):
        stock = {'A': 3, 'B': 0}
        with self.assertRaises(ValueError):
            reserve(stock, {'A': 2, 'B': 1})
        self.assertEqual(stock, {'A': 3, 'B': 0})
