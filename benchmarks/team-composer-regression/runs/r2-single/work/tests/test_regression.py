from copy import deepcopy
import unittest
from shop import OrderBook, replay
from shop.clock import parse_time
from shop.money import allocate_discount, refund_delta
from shop.inventory import reserve, release


def ev(eid, kind='reserve', oid='o', at='2026-01-01T00:00:00Z', **kw):
    result = dict(id=eid, type=kind, order_id=oid, at=at)
    if kind == 'reserve':
        result.update(lines=[dict(sku='A', qty=3, unit_price=4)], discount=2,
                      expires_at='2026-01-01T01:00:00Z')
    result.update(kw)
    return result


class RegressionTests(unittest.TestCase):
    def test_exact_discount_and_ties(self):
        lines = [dict(sku=s, qty=1, unit_price=10**100+1) for s in ['ZZ', 'A', 'B']]
        saved = deepcopy(lines)
        result = allocate_discount(lines, 4)
        self.assertEqual(result, {'ZZ':10**100, 'A':10**100-1, 'B':10**100})
        self.assertEqual(lines, saved)
        self.assertEqual(allocate_discount([dict(sku='A', qty=2, unit_price=0)], 0), {'A':0})

    def test_invalid_money(self):
        for lines, discount in [(None,0), ([],0), ([{}],0),
            ([dict(sku='A',qty=True,unit_price=1)],0),
            ([dict(sku='A',qty=1,unit_price=False)],0),
            ([dict(sku='A',qty=1,unit_price=1)],True),
            ([dict(sku='A',qty=1,unit_price=1)]*2,0),
            ([dict(sku='A',qty=1,unit_price=0)],1)]:
            with self.subTest(lines=lines, discount=discount), self.assertRaises(ValueError):
                allocate_discount(lines, discount)
        for args in [(True,1,0,1),(1,True,0,1),(1,1,False,1),(1,1,0,True),
                     (1,0,0,1),(1,2,2,1),(1,2,0,3)]:
            with self.assertRaises(ValueError): refund_delta(*args)

    def test_refund_conservation(self):
        for total in range(30):
            for qty in range(1,12):
                self.assertEqual(sum(refund_delta(total,qty,n,1) for n in range(qty)),total)
                for first in range(1,qty):
                    self.assertEqual(refund_delta(total,qty,0,first) + refund_delta(total,qty,first,qty-first), total)

    def test_time_validation(self):
        for value in [None, 1, True, '2026-01-01', '2026-01-01T12:00:00', 'bad']:
            with self.assertRaises(ValueError): parse_time(value)
        self.assertEqual(parse_time('2026-01-01T00:00:00Z'), parse_time('2025-12-31T19:00:00-05:00'))

    def test_inventory_atomic_errors(self):
        for func in [reserve, release]:
            for items in [{}, {'A':1,'X':1}, {'A':1,'B':True}, {'A':1,'B':-1}]:
                stock = {'A':2,'B':0}
                with self.assertRaises(ValueError): func(stock,items)
                self.assertEqual(stock, {'A':2,'B':0})
        stock = {'A':2,'B':0}
        self.assertIsNone(release(stock, {'A':1,'B':2}))
        self.assertIsNone(reserve(stock, {'A':3,'B':2}))
        self.assertEqual(stock, {'A':0,'B':0})

    def test_alias_and_cumulative_refunds(self):
        stock = {'A':5}; event = ev('r'); original = deepcopy(event)
        b = OrderBook(stock); b.apply(event)
        self.assertEqual(event, original); self.assertEqual(stock, {'A':5})
        event['lines'][0]['qty'] = 100
        snap = b.snapshot(); snap['stock']['A'] = 100; snap['orders']['o']['remaining']['A'] = 100
        b.apply(ev('c','confirm'))
        for i in range(3):
            b.apply(ev('x'+str(i),'cancel',items={'A':1}))
            self.assertEqual(b.snapshot()['orders']['o']['refunded'], [3,6,10][i])
        order = b.snapshot()['orders']['o']
        self.assertEqual((order['status'],order['charged'],order['remaining']), ('cancelled',10,{'A':0}))
        self.assertEqual(b.snapshot()['stock'], {'A':5})

    def test_rollback_ttl_and_id_reuse(self):
        b=OrderBook({'A':9}); b.apply(ev('r')); before=b.snapshot()
        with self.assertRaises(ValueError): b.apply(ev('c','confirm',at='2026-01-01T01:00:00Z'))
        self.assertEqual(b.snapshot(), before)
        b.apply(ev('c','confirm',at='2026-01-01T00:30:00Z'))
        b.apply(ev('r2',oid='other',at='2026-01-01T02:00:00Z', expires_at='2026-01-01T03:00:00Z'))
        self.assertEqual(b.snapshot()['orders']['o']['status'], 'confirmed')
        b.apply(ev('r3',oid='third',at='2026-01-01T03:00:00Z', expires_at='2026-01-01T04:00:00Z'))
        self.assertEqual(b.snapshot()['orders']['other']['status'], 'expired')
        before=b.snapshot()
        for event in [ev('bad',oid='other',at='2026-01-01T03:00:00Z'),
                      ev('bad','cancel',oid='other',at='2026-01-01T03:00:00Z')]:
            with self.assertRaises(ValueError): b.apply(event)
            self.assertEqual(b.snapshot(),before)

    def test_reserved_partial_and_invalid_events(self):
        b=OrderBook({'A':3}); b.apply(ev('r')); before=b.snapshot()
        for event in [ev('x','cancel',items={'A':1}), ev('x','cancel',items={}),
                      ev('x','cancel',items={'A':True}),ev('x','cancel',items={'X':1}),
                      None, [], {}, ev('x','nonsense'), ev('x','confirm',at='2025-01-01T00:00:00Z')]:
            with self.assertRaises(ValueError): b.apply(event)
            self.assertEqual(b.snapshot(),before)
        b.apply(ev('x','cancel'))
        self.assertEqual(b.snapshot()['orders']['o']['refunded'],0)
        self.assertEqual(b.snapshot()['stock'],{'A':3})

    def test_fingerprints(self):
        b=OrderBook({'A':4}); event=ev('r',extra={'z':1,'a':[1,2]}); b.apply(event)
        b.apply(ev('c','confirm',at='2026-01-01T00:30:00Z')); before=b.snapshot()
        duplicate=dict(reversed(list(event.items())))
        duplicate['at']='2025-12-31T19:00:00-05:00'
        duplicate['expires_at']='2026-01-01T10:00:00+09:00'
        duplicate['extra']={'a':[1,2],'z':1}
        self.assertIsNone(b.apply(duplicate)); self.assertEqual(b.snapshot(),before)
        duplicate['extra']['z']=2
        with self.assertRaises(ValueError): b.apply(duplicate)
        self.assertEqual(b.snapshot(),before)

    def test_replay_utc_stability(self):
        events=[ev('c','confirm',at='2025-12-31T20:00:00-05:00'),
                ev('r',expires_at='2026-01-01T02:00:00Z')]
        original=deepcopy(events)
        result=replay({'A':3},events)
        self.assertEqual(result['orders']['o']['status'],'confirmed')
        self.assertEqual(replay({'A':3},events),result); self.assertEqual(events,original)
        self.assertEqual(replay({'A':3},[ev('r'),ev('c','confirm')])['orders']['o']['status'],'confirmed')
        for invalid in [None,[{}],[None]]:
            with self.assertRaises(ValueError): replay({},invalid)

if __name__ == '__main__': unittest.main()
