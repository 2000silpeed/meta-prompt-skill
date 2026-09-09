import unittest
from copy import deepcopy
from shop import OrderBook, replay
from shop.clock import parse_time
from shop.inventory import reserve, release
from shop.money import allocate_discount, refund_delta


def ev(eid, kind, oid='o', at='2026-01-01T00:00:00Z', **extra):
    return dict(id=eid, type=kind, order_id=oid, at=at, **extra)


def reservation(eid='r', oid='o', **extra):
    payload = dict(lines=[dict(sku='A', qty=3, unit_price=4)], discount=2,
                   expires_at='2026-01-01T01:00:00Z')
    payload.update(extra)
    return ev(eid, 'reserve', oid, **payload)


class ContractChecks(unittest.TestCase):
    def test_time_validation(self):
        for value in [None, 4, True, '2026-01-01', '2026-01-01T00:00:00', 'bad']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_time(value)
        self.assertEqual(parse_time('2026-01-01T09:00:00+09:00'), parse_time('2026-01-01T00:00:00Z'))
        self.assertEqual(parse_time('2025-12-31T19:00:00-05:00'), parse_time('2026-01-01T00:00:00Z'))

    def test_exact_allocation_and_validation(self):
        self.assertEqual(allocate_discount([dict(sku='Z',qty=1,unit_price=1),dict(sku='AA',qty=1,unit_price=1)],1), {'Z':1,'AA':0})
        huge=10**100
        self.assertEqual(allocate_discount([dict(sku='B',qty=1,unit_price=huge),dict(sku='A',qty=1,unit_price=huge)],huge+1), {'B':huge//2,'A':huge//2-1})
        self.assertEqual(allocate_discount([dict(sku='A',qty=1,unit_price=0)],0),{'A':0})
        bad_lines=[[],None,[None],[dict(sku='',qty=1,unit_price=1)], [dict(sku='A',qty=True,unit_price=1)], [dict(sku='A',qty=1,unit_price=False)], [dict(sku='A',qty=1,unit_price=1)]*2]
        for lines in bad_lines:
            with self.subTest(lines=lines), self.assertRaises(ValueError): allocate_discount(lines,0)
        for discount in [True,-1,2,1.0,None]:
            with self.subTest(discount=discount), self.assertRaises(ValueError):
                allocate_discount([dict(sku='A',qty=1,unit_price=1)],discount)

    def test_refunds_exhaustive(self):
        for total in range(30):
            for qty in range(1,10):
                self.assertEqual(sum(refund_delta(total,qty,c,1) for c in range(qty)),total)
                for cancelled in range(qty):
                    for delta in range(1,qty-cancelled+1):
                        self.assertEqual(refund_delta(total,qty,cancelled,delta),total*(cancelled+delta)//qty-total*cancelled//qty)
        for args in [(True,1,0,1),(1,True,0,1),(1,1,False,1),(1,1,0,True),(1,0,0,1),(1,2,2,1),(1,2,0,3)]:
            with self.assertRaises(ValueError): refund_delta(*args)

    def test_inventory_atomicity(self):
        for fn in [reserve,release]:
            for items in [{},{'A':1,'B':True},{'A':1,'X':1},{'A':1,'B':0}]:
                stock={'A':5,'B':0}; before=deepcopy(stock)
                with self.assertRaises(ValueError): fn(stock,items)
                self.assertEqual(stock,before)
        stock={'A':5,'B':0}
        with self.assertRaises(ValueError): reserve(stock,{'A':1,'B':1})
        self.assertEqual(stock,{'A':5,'B':0})
        self.assertIsNone(release(stock,{'B':1}))
        self.assertIsNone(reserve(stock,{'A':2,'B':1}))
        self.assertEqual(stock,{'A':3,'B':0})

    def test_aliases(self):
        stock={'A':5}; b=OrderBook(stock); stock['A']=100
        r=reservation(); orig=deepcopy(r); b.apply(r); self.assertEqual(r,orig)
        r['lines'][0]['qty']=100
        snap=b.snapshot(); snap['stock']['A']=99; snap['orders']['o']['remaining']['A']=99; snap['orders']['o']['line_totals']['A']=99
        self.assertEqual(b.snapshot()['stock'],{'A':2})
        self.assertEqual(b.snapshot()['orders']['o']['remaining'],{'A':3})
        self.assertEqual(b.snapshot()['orders']['o']['line_totals'],{'A':10})

    def test_duplicates_and_ordering(self):
        b=OrderBook({'A':5}); r=reservation(note={'x':1,'y':2}); b.apply(r)
        b.apply(ev('c','confirm',at='2026-01-01T00:30:00Z'))
        before=b.snapshot()
        duplicate=dict(reversed(list(r.items())))
        duplicate['at']='2026-01-01T09:00:00+09:00'
        duplicate['expires_at']='2026-01-01T10:00:00+09:00'
        duplicate['note']={'y':2,'x':1}
        self.assertIsNone(b.apply(duplicate)); self.assertEqual(b.snapshot(),before)
        duplicate['note']['x']=9
        with self.assertRaises(ValueError): b.apply(duplicate)
        self.assertEqual(b.snapshot(),before)
        with self.assertRaises(ValueError): b.apply(ev('old','cancel'))
        self.assertEqual(b.snapshot(),before)

    def test_expiry_transaction(self):
        b=OrderBook({'A':5}); b.apply(reservation()); before=b.snapshot()
        with self.assertRaises(ValueError): b.apply(ev('retry','confirm',at='2026-01-01T01:00:00Z'))
        self.assertEqual(b.snapshot(),before)
        b.apply(reservation('retry','next',at='2026-01-01T01:00:00Z',expires_at='2026-01-01T02:00:00Z'))
        snap=b.snapshot(); self.assertEqual(snap['orders']['o']['status'],'expired')
        self.assertEqual(snap['orders']['o']['remaining'],{'A':0})
        self.assertEqual(snap['stock'],{'A':2})
        for kind in ['confirm','cancel']:
            with self.assertRaises(ValueError): b.apply(ev('bad',kind,at='2026-01-01T01:00:00Z'))
            self.assertEqual(b.snapshot(),snap)
        with self.assertRaises(ValueError): b.apply(reservation('reuse',at='2026-01-01T01:00:00Z',expires_at='2026-01-01T02:00:00Z'))
        self.assertEqual(b.snapshot(),snap)

    def test_cancellation(self):
        b=OrderBook({'A':5}); b.apply(reservation()); before=b.snapshot()
        with self.assertRaises(ValueError): b.apply(ev('x','cancel',items={'A':1}))
        self.assertEqual(b.snapshot(),before)
        b.apply(ev('c','confirm'))
        for i, expected in enumerate([3,6,10],1):
            b.apply(ev('x'+str(i),'cancel',at='2026-01-01T02:00:00Z',items={'A':1}))
            order=b.snapshot()['orders']['o']
            self.assertEqual(order['refunded'],expected); self.assertEqual(order['charged'],10)
            self.assertEqual(order['status'],'cancelled' if i==3 else 'confirmed')
        self.assertEqual(b.snapshot()['stock'],{'A':5})
        b=OrderBook({'A':5}); b.apply(reservation()); b.apply(ev('x','cancel'))
        self.assertEqual(b.snapshot()['orders']['o']['refunded'],0)
        self.assertEqual(b.snapshot()['orders']['o']['status'],'cancelled')

    def test_invalid_events_rollback(self):
        b=OrderBook({'A':5}); b.apply(reservation()); before=b.snapshot()
        for bad in [None,[],{},ev('','cancel'),ev('bad','unknown'),ev('bad','cancel',items={}),ev('bad','cancel',items={'A':True}),ev('bad','cancel',items={'X':1}),ev('bad','cancel',items={'A':4}),reservation('bad','new',lines=[dict(sku='A',qty=3,unit_price=1),dict(sku='B',qty=1,unit_price=1)]),reservation('bad','new',expires_at='2026-01-01T00:00:00Z')]:
            with self.subTest(bad=bad), self.assertRaises(ValueError): b.apply(bad)
            self.assertEqual(b.snapshot(),before)
        b.apply(ev('bad','cancel'))

    def test_replay_utc_stability(self):
        r=reservation(at='2026-01-01T09:00:00+09:00'); c=ev('c','confirm',at='2026-01-01T00:01:00Z')
        events=[c,r]; before=deepcopy(events)
        snap=replay({'A':5},events); self.assertEqual(snap['orders']['o']['status'],'confirmed')
        self.assertEqual(events,before); self.assertEqual(replay({'A':5},events),snap)
        c['at']=r['at']; self.assertEqual(replay({'A':5},[r,c])['orders']['o']['charged'],10)
        with self.assertRaises(ValueError): replay({'A':5},[c,r])
        for events in [[None],[{}],[{'at':'bad'}],None]:
            with self.assertRaises(ValueError): replay({},events)

if __name__=='__main__': unittest.main()
