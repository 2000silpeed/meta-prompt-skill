import copy
import unittest

from shop import OrderBook


def event(eid, kind='reserve', oid='o', **extra):
    result = dict(id=eid, type=kind, order_id=oid, at='2026-01-01T00:00:00Z')
    if kind == 'reserve':
        result.update(lines=[dict(sku='A', qty=3, unit_price=4),
                             dict(sku='B', qty=2, unit_price=3)],
                      discount=5, expires_at='2026-01-01T01:00:00Z')
    result.update(extra)
    return result


class ReviewTests(unittest.TestCase):
    def test_unbounded_integer_payload_and_charge(self):
        large = 10**5000
        b = OrderBook({'A': 1})
        r = event('r', lines=[dict(sku='A', qty=1, unit_price=large)], discount=1,
                  extra={'large': large})
        original = copy.deepcopy(r)
        b.apply(r)
        b.apply(event('c', 'confirm'))
        self.assertEqual(b.snapshot()['orders']['o']['charged'], large - 1)
        before = b.snapshot()
        b.apply(copy.deepcopy(r))
        self.assertEqual(b.snapshot(), before)
        self.assertEqual(r, original)
        r['extra']['large'] += 1
        with self.assertRaises(ValueError):
            b.apply(r)
        self.assertEqual(b.snapshot(), before)

    def test_fingerprint_structure_order_and_types(self):
        b = OrderBook({'A': 3, 'B': 2})
        r = event('r', extra={'number': 1, 'nested': [True, None, {'a': 1, 'b': 2}]})
        b.apply(r)
        duplicate = copy.deepcopy(r)
        duplicate['extra']['nested'][2] = {'b': 2, 'a': 1}
        b.apply(duplicate)
        before = b.snapshot()
        for changed in [True, 1.0, '1', {'int': 1}, [1]]:
            conflicting = copy.deepcopy(r)
            conflicting['extra']['number'] = changed
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                b.apply(conflicting)
            self.assertEqual(b.snapshot(), before)
        conflicting = copy.deepcopy(r)
        conflicting['lines'].reverse()
        with self.assertRaises(ValueError):
            b.apply(conflicting)

    def test_multisku_refund_after_exhausting_one_line(self):
        b = OrderBook({'A': 3, 'B': 2})
        b.apply(event('r'))
        b.apply(event('c', 'confirm'))
        b.apply(event('x', 'cancel', items={'A': 3, 'B': 1}))
        order = b.snapshot()['orders']['o']
        self.assertEqual(order['remaining'], {'A': 0, 'B': 1})
        self.assertEqual(order['status'], 'confirmed')
        b.apply(event('y', 'cancel'))
        order = b.snapshot()['orders']['o']
        self.assertEqual(order['remaining'], {'A': 0, 'B': 0})
        self.assertEqual(order['refunded'], order['charged'])
        self.assertEqual(order['charged'], 13)
        self.assertEqual(b.snapshot()['stock'], {'A': 3, 'B': 2})

    def test_multiple_expirations_are_rolled_back_together(self):
        b = OrderBook({'A': 6, 'B': 4})
        b.apply(event('r1', oid='one'))
        b.apply(event('r2', oid='two'))
        before = b.snapshot()
        failure = event('retry', 'cancel', oid='one', at='2026-01-01T01:00:00Z')
        with self.assertRaises(ValueError):
            b.apply(failure)
        self.assertEqual(b.snapshot(), before)
        b.apply(event('retry', oid='three', at='2026-01-01T01:00:00Z',
                      expires_at='2026-01-01T02:00:00Z'))
        snapshot = b.snapshot()
        for oid in ['one', 'two']:
            self.assertEqual(snapshot['orders'][oid]['status'], 'expired')
            self.assertEqual(snapshot['orders'][oid]['remaining'], {'A': 0, 'B': 0})
        self.assertEqual(snapshot['stock'], {'A': 3, 'B': 2})


if __name__ == '__main__':
    unittest.main()
