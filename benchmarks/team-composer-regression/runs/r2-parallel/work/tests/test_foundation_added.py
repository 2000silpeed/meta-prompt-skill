import unittest
from copy import deepcopy
from datetime import timezone
from shop.clock import parse_time
from shop.money import allocate_discount, refund_delta
from shop.inventory import reserve, release


class FoundationTests(unittest.TestCase):
    def test_timestamp_normalization_and_validation(self):
        self.assertEqual(parse_time('2026-01-01T00:30:00+01:00'),
                         parse_time('2025-12-31T23:30:00Z'))
        self.assertIs(parse_time('2026-01-01T00:00:00Z').tzinfo, timezone.utc)
        for value in [None, True, 123, '', '2026-01-01',
                      '2026-01-01T00:00:00', '2026-02-30T00:00:00Z',
                      '0001-01-01T00:00:00+01:00']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_time(value)

    def test_discount_ties_and_large_exact_values(self):
        lines = [{'sku': sku, 'qty': 1, 'unit_price': 10} for sku in ['ZZ', 'A', 'B']]
        original = deepcopy(lines)
        self.assertEqual(allocate_discount(lines, 2), {'ZZ': 10, 'A': 9, 'B': 9})
        self.assertEqual(lines, original)
        huge = 10 ** 400
        self.assertEqual(allocate_discount([
            {'sku': 'B', 'qty': 1, 'unit_price': huge},
            {'sku': 'A', 'qty': 1, 'unit_price': huge}], huge + 1),
            {'B': huge // 2, 'A': huge // 2 - 1})
        self.assertEqual(allocate_discount([{'sku': 'A', 'qty': 4, 'unit_price': 0}], 0), {'A': 0})

    def test_discount_invalid_inputs(self):
        valid = [{'sku': 'A', 'qty': 2, 'unit_price': 3}]
        for discount in [True, False, -1, 7, 1.0, None]:
            with self.subTest(discount=discount), self.assertRaises(ValueError):
                allocate_discount(valid, discount)
        invalid = [[], {}, [None], valid * 2]
        for field, values in [('sku', ['', None, 1]), ('qty', [True, 0, -1, 1.0]),
                              ('unit_price', [False, -1, None, 2.5])]:
            for value in values:
                line = dict(valid[0]); line[field] = value
                invalid.append([line])
        for lines in invalid:
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                allocate_discount(lines, 0)

    def test_refunds_are_cumulative_and_conserved(self):
        for total in [0, 1, 10, 101, 10 ** 100 + 1]:
            for qty in range(1, 12):
                self.assertEqual(sum(refund_delta(total, qty, c, 1) for c in range(qty)), total)
                for cancelled in range(qty):
                    delta = qty - cancelled
                    self.assertEqual(refund_delta(total, qty, cancelled, delta),
                                     sum(refund_delta(total, qty, c, 1) for c in range(cancelled, qty)))
        for args in [(-1, 3, 0, 1), (10, 0, 0, 1), (10, 3, -1, 1),
                     (10, 3, 3, 1), (10, 3, 0, 0), (10, 3, 2, 2)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                refund_delta(*args)
        for index in range(4):
            for bad in [True, False, 1.0, None]:
                args = [10, 3, 0, 1]; args[index] = bad
                with self.subTest(args=args), self.assertRaises(ValueError):
                    refund_delta(*args)

    def test_inventory_is_atomic_and_items_unchanged(self):
        for operation in [reserve, release]:
            for items in [{}, {'A': 1, 'unknown': 1}, {'A': 1, 'B': True},
                          {'A': 1, 'B': -1}, {'A': 1, 'B': 0}, None]:
                stock = {'A': 3, 'B': 2}
                before = deepcopy(stock)
                with self.subTest(operation=operation.__name__, items=items), self.assertRaises(ValueError):
                    operation(stock, items)
                self.assertEqual(stock, before)
            stock = {'A': 3, 'B': 2}; items = {'A': 2, 'B': 1}
            self.assertIsNone(operation(stock, items))
            self.assertEqual(items, {'A': 2, 'B': 1})
            self.assertEqual(stock, {'A': 1, 'B': 1} if operation is reserve else {'A': 5, 'B': 3})
        stock = {'A': 3, 'B': 0}
        with self.assertRaises(ValueError):
            reserve(stock, {'A': 1, 'B': 1})
        self.assertEqual(stock, {'A': 3, 'B': 0})

    def test_inventory_rejects_invalid_stock(self):
        for operation in [reserve, release]:
            for stock in [{'A': True}, {'A': -1}, {'A': 3, 'B': False}, {'A': 3, '': 0}, []]:
                before = deepcopy(stock)
                with self.subTest(stock=stock), self.assertRaises(ValueError):
                    operation(stock, {'A': 1})
                self.assertEqual(stock, before)
