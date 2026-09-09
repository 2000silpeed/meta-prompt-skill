import copy
import unittest
from datetime import timezone
from shop import OrderBook, replay
from shop.clock import parse_time
from shop.inventory import reserve, release
from shop.money import allocate_discount, refund_delta


def ev(eid, kind='reserve', oid='o', at='2026-01-01T00:00:00Z', **extra):
    result = dict(id=eid, type=kind, order_id=oid, at=at)
    if kind == 'reserve':
        result.update(lines=[dict(sku='A', qty=3, unit_price=4)], discount=2,
                      expires_at='2026-01-01T01:00:00Z')
    result.update(extra)
    return result


class RegressionTests(unittest.TestCase):
    def test_money_exact_and_ties(self):
        self.assertEqual(allocate_discount([dict(sku=s, qty=1, unit_price=1) for s in ['ZZ','B','A']], 2),
                         {'ZZ':1,'B':0,'A':0})
        n = 10**100
        self.assertEqual(allocate_discount([dict(sku='A',qty=1,unit_price=n),dict(sku='B',qty=1,unit_price=n)],1), {'A':n-1,'B':n})
        self.assertEqual(allocate_discount([dict(sku='A',qty=3,unit_price=0)],0), {'A':0})
        for total in range(20):
            for qty in range(1,10):
                self.assertEqual(sum(refund_delta(total,qty,c,1) for c in range(qty)), total)
                for c in range(qty):
                    for d in range(1,qty-c+1):
                        self.assertEqual(refund_delta(total,qty,c,d),sum(refund_delta(total,qty,k,1) for k in range(c,c+d)))

    def test_invalid_numbers(self):
        for field in ['qty','unit_price']:
            line=dict(sku='A',qty=1,unit_price=1); line[field]=True
            with self.assertRaises(ValueError): allocate_discount([line],0)
        for lines,discount in [([],0),([dict(sku='A',qty=1,unit_price=1)]*2,0),([dict(sku='A',qty=1,unit_price=0)],1),([dict(sku='A',qty=1,unit_price=1)],True)]:
            with self.assertRaises(ValueError): allocate_discount(lines,discount)
        for args in [(True,1,0,1),(1,True,0,1),(1,1,False,1),(1,1,0,True),(1,1,1,1),(1,2,0,3)]:
            with self.assertRaises(ValueError): refund_delta(*args)

    def test_clock(self):
        for value in [None,1,'2026-01-01','2026-01-01T00:00:00','broken']:
            with self.assertRaises(ValueError): parse_time(value)
        self.assertEqual(parse_time('2025-12-31T19:00:00-05:00'),parse_time('2026-01-01T09:00:00+09:00'))
        self.assertIs(parse_time('2026-01-01T09:00:00+09:00').tzinfo,timezone.utc)

    def test_inventory_atomic(self):
        for operation in [reserve,release]:
            for items in [{},{'A':1,'unknown':1},{'A':1,'B':True},{'A':1,'B':0}]:
                stock={'A':5,'B':2}; before=stock.copy()
                with self.assertRaises(ValueError): operation(stock,items)
                self.assertEqual(stock,before)
            stock={'A':5,'B':2}; self.assertIsNone(operation(stock,{'A':1,'B':2}))
        stock={'A':5,'B':2}
        with self.assertRaises(ValueError): reserve(stock,{'A':1,'B':3})
        self.assertEqual(stock,{'A':5,'B':2})

    def test_aliasing_and_refund_lifecycle(self):
        initial={'A':10}; b=OrderBook(initial); event=ev('r'); saved=copy.deepcopy(event)
        b.apply(event); self.assertEqual(event,saved); self.assertEqual(initial,{'A':10})
        initial['A']=0; event['lines'][0]['qty']=999
        snap=b.snapshot(); snap['stock']['A']=0; snap['orders']['o']['remaining']['A']=100
        self.assertEqual(b.snapshot()['stock']['A'],7)
        b.apply(ev('c','confirm',at='2026-01-01T00:10:00Z'))
        for i in range(3):
            b.apply(ev(str(i),'cancel',at='2026-01-01T02:00:00Z',items={'A':1}))
            order=b.snapshot()['orders']['o']
            self.assertEqual(order['refunded'],10*(i+1)//3)
            self.assertEqual(order['charged'],10)
            self.assertEqual(order['status'],'cancelled' if i==2 else 'confirmed')
        self.assertEqual(b.snapshot()['stock']['A'],10)

    def test_expiry_rollback_and_id_reuse_after_failure(self):
        b=OrderBook({'A':10}); b.apply(ev('r')); before=b.snapshot()
        with self.assertRaises(ValueError): b.apply(ev('c','confirm',at='2026-01-01T01:00:00Z'))
        self.assertEqual(b.snapshot(),before)
        b.apply(ev('c',oid='other',at='2026-01-01T01:00:00Z',expires_at='2026-01-01T02:00:00Z'))
        self.assertEqual(b.snapshot()['orders']['o']['status'],'expired')
        self.assertEqual(b.snapshot()['orders']['o']['remaining'],{'A':0})
        self.assertEqual(b.snapshot()['stock']['A'],7)
        before=b.snapshot()
        for kind in ['reserve','confirm','cancel']:
            with self.assertRaises(ValueError): b.apply(ev('bad',kind,at='2026-01-01T01:00:00Z'))
            self.assertEqual(b.snapshot(),before)

    def test_duplicates_and_unknown_keys(self):
        b=OrderBook({'A':10}); first=ev('r',custom={'z':2,'a':1}); b.apply(first)
        b.apply(ev('c','confirm',at='2026-01-01T00:10:00Z')); before=b.snapshot()
        duplicate=dict(reversed(list(first.items())))
        duplicate['at']='2026-01-01T09:00:00+09:00'
        duplicate['expires_at']='2025-12-31T20:00:00-05:00'
        duplicate['custom']={'a':1,'z':2}
        self.assertIsNone(b.apply(duplicate)); self.assertEqual(b.snapshot(),before)
        duplicate['custom']['a']=2
        with self.assertRaises(ValueError): b.apply(duplicate)
        self.assertEqual(b.snapshot(),before)

    def test_invalid_events_and_reserved_partial(self):
        b=OrderBook({'A':10}); b.apply(ev('r')); before=b.snapshot()
        for event in [None,[],{},ev('x','cancel',items={}),ev('x','cancel',items={'A':1}),ev('x','cancel',items={'B':3}),ev('x','cancel',items={'A':True}),ev('x','cancel',items={'A':4}),ev('x','confirm',at='2025-01-01T00:00:00Z')]:
            with self.assertRaises(ValueError): b.apply(event)
            self.assertEqual(b.snapshot(),before)
        b.apply(ev('x','cancel'))
        self.assertEqual(b.snapshot()['orders']['o']['refunded'],0)
        self.assertEqual(b.snapshot()['stock'],{'A':10})

    def test_replay_utc_stable_and_input_preservation(self):
        reserve_event=ev('r',at='2026-01-01T09:00:00+09:00')
        confirm_event=ev('c','confirm',at='2026-01-01T00:01:00Z')
        events=[confirm_event,reserve_event]; saved=copy.deepcopy(events)
        result=replay({'A':10},events)
        self.assertEqual(result['orders']['o']['status'],'confirmed')
        self.assertEqual(events,saved)
        self.assertEqual(result,replay({'A':10},events))
        confirm_event['at']=reserve_event['at']
        self.assertEqual(replay({'A':10},[reserve_event,confirm_event])['orders']['o']['status'],'confirmed')
        for events in [[None],[{}],[{'at':'bad'}]]:
            with self.assertRaises(ValueError): replay({'A':10},events)

if __name__ == '__main__':
    unittest.main()
