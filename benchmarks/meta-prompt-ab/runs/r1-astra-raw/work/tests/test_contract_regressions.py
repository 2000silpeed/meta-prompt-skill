import copy
import unittest

from shop import OrderBook, replay
from shop.clock import parse_time
from shop.inventory import reserve, release
from shop.money import allocate_discount, refund_delta


def event(eid, kind='reserve', oid='o', at='2026-01-01T00:00:00Z', **kwargs):
    return dict(id=eid, type=kind, order_id=oid, at=at, **kwargs)


def reservation(eid='r', oid='o', **kwargs):
    data = dict(lines=[dict(sku='A', qty=3, unit_price=4)], discount=2,
                expires_at='2026-01-01T01:00:00Z')
    data.update(kwargs)
    return event(eid, oid=oid, **data)


class ContractRegressions(unittest.TestCase):
    def book(self):
        b = OrderBook({'A':10, 'B':5})
        b.apply(reservation())
        return b

    def rejects_unchanged(self, b, ev):
        before = b.snapshot()
        seen = copy.deepcopy(b.seen)
        with self.assertRaises(ValueError):
            b.apply(ev)
        self.assertEqual(b.snapshot(), before)
        self.assertEqual(b.seen, seen)

    def test_time_validation(self):
        for bad in [None, True, 123, '', '2026-01-01', '2026-01-01T01:02:03',
                    '2026-13-01T00:00:00Z', '0001-01-01T00:00:00+01:00']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_time(bad)
        self.assertEqual(parse_time('2025-12-31T19:00:00-05:00'),
                         parse_time('2026-01-01T00:00:00Z'))

    def test_money_exact_large_ties_and_zero(self):
        self.assertEqual(allocate_discount([dict(sku='Z',qty=1,unit_price=1),
                                            dict(sku='AA',qty=1,unit_price=1)],1),
                         {'Z':1,'AA':0})
        n=10**100
        self.assertEqual(allocate_discount([dict(sku='A',qty=1,unit_price=n),
                                            dict(sku='B',qty=1,unit_price=n)],2*n-1),
                         {'A':0,'B':1})
        self.assertEqual(allocate_discount([dict(sku='A',qty=2,unit_price=0)],0), {'A':0})
        for total in range(21):
            for qty in range(1,8):
                self.assertEqual(sum(refund_delta(total,qty,c,1) for c in range(qty)),total)

    def test_money_validation(self):
        base = dict(sku='A',qty=1,unit_price=1)
        bad_lines = [None, [], [None], [base,base], [dict(base,sku='')],
                     [dict(base,qty=True)], [dict(base,unit_price=False)],
                     [dict(base,qty=0)], [dict(base,unit_price=-1)]]
        for lines in bad_lines:
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                allocate_discount(lines,0)
        for discount in [True, -1, 2, 0.5, None]:
            with self.assertRaises(ValueError):
                allocate_discount([base],discount)
        for args in [(True,1,0,1),(1,True,0,1),(1,1,False,1),
                     (1,1,0,True),(1,0,0,1),(1,1,1,1),(1,2,0,3)]:
            with self.assertRaises(ValueError): refund_delta(*args)

    def test_inventory_atomic_validation(self):
        for action in [reserve,release]:
            for items in [{}, {'A':1,'C':1}, {'A':1,'B':True}, {'A':0}]:
                stock={'A':3,'B':1}; before=stock.copy()
                with self.assertRaises(ValueError): action(stock,items)
                self.assertEqual(stock,before)
        stock={'A':3,'B':1}
        with self.assertRaises(ValueError): reserve(stock,{'A':1,'B':2})
        self.assertEqual(stock,{'A':3,'B':1})
        self.assertIsNone(reserve(stock,{'A':2,'B':1}))
        self.assertIsNone(release(stock,{'A':2,'B':1}))
        self.assertEqual(stock,{'A':3,'B':1})

    def test_input_and_snapshot_isolation(self):
        stock={'A':10}; ev=reservation(); originals=copy.deepcopy((stock,ev))
        b=OrderBook(stock); b.apply(ev)
        self.assertEqual((stock,ev), originals)
        stock['A']=0; ev['lines'][0]['qty']=100
        snap=b.snapshot(); snap['stock']['A']=0
        snap['orders']['o']['remaining']['A']=0
        snap['orders']['o']['line_totals']['A']=0
        self.assertEqual(b.snapshot()['stock']['A'],7)
        self.assertEqual(b.snapshot()['orders']['o']['remaining']['A'],3)
        self.assertEqual(b.snapshot()['orders']['o']['line_totals']['A'],10)

    def test_duplicate_canonical_and_old(self):
        b=self.book()
        b.apply(event('c','confirm',at='2026-01-01T00:10:00Z'))
        before=b.snapshot()
        duplicate=dict(reversed(list(reservation().items())))
        duplicate['at']='2026-01-01T09:00:00+09:00'
        duplicate['expires_at']='2026-01-01T10:00:00+09:00'
        self.assertIsNone(b.apply(duplicate))
        self.assertEqual(b.snapshot(),before)
        self.rejects_unchanged(b,dict(duplicate,unknown=True))

    def test_fingerprint_includes_line_order_and_nested_extras(self):
        b=OrderBook({'A':10,'B':10})
        ev=reservation(lines=[dict(sku='A',qty=1,unit_price=1),dict(sku='B',qty=1,unit_price=1)],
                       discount=0,extra={'x':1,'y':2})
        b.apply(ev)
        identical=copy.deepcopy(ev); identical['extra']={'y':2,'x':1}
        b.apply(identical)
        changed=copy.deepcopy(ev); changed['lines'].reverse()
        self.rejects_unchanged(b,changed)
        changed=copy.deepcopy(ev); changed['extra']['x']=2
        self.rejects_unchanged(b,changed)

    def test_ttl_boundary_rollback_then_success(self):
        b=self.book()
        self.rejects_unchanged(b,event('x','confirm',at='2026-01-01T01:00:00Z'))
        b.apply(reservation(eid='x',oid='second',at='2026-01-01T01:00:00Z',
                            expires_at='2026-01-01T02:00:00Z'))
        snap=b.snapshot()
        self.assertEqual(snap['stock']['A'],7)
        self.assertEqual(snap['orders']['o']['status'],'expired')
        self.assertEqual(snap['orders']['o']['remaining'],{'A':0})
        self.rejects_unchanged(b,event('bad','cancel',at='2026-01-01T01:00:00Z'))
        self.rejects_unchanged(b,reservation(eid='again',at='2026-01-01T01:00:00Z',
                                           expires_at='2026-01-01T03:00:00Z'))

    def test_confirmed_does_not_expire_and_refunds_accumulate(self):
        b=self.book(); b.apply(event('c','confirm'))
        for i in range(3):
            b.apply(event(str(i),'cancel',at='2026-01-01T02:00:00Z',items={'A':1}))
            order=b.snapshot()['orders']['o']
            self.assertEqual(order['refunded'],10*(i+1)//3)
            self.assertEqual(order['status'],'cancelled' if i==2 else 'confirmed')
            self.assertEqual(order['charged'],10)
        self.assertEqual(b.snapshot()['stock']['A'],10)
        self.rejects_unchanged(b,event('extra','confirm',at='2026-01-01T02:00:00Z'))

    def test_reserved_full_only(self):
        b=self.book()
        self.rejects_unchanged(b,event('x','cancel',items={'A':1}))
        b.apply(event('x','cancel'))
        order=b.snapshot()['orders']['o']
        self.assertEqual(order['status'],'cancelled')
        self.assertEqual(order['charged'],0)
        self.assertEqual(order['refunded'],0)
        self.assertEqual(b.snapshot()['stock']['A'],10)

    def test_invalid_events_atomic_and_id_not_consumed(self):
        b=self.book()
        for ev in [None,[],{},event('x','other'),event('x','cancel',items={}),
                   event('x','cancel',items={'A':True}),event('x','cancel',items={'B':1}),
                   event('x','cancel',items={'A':4}),event('x','confirm',oid='missing'),
                   reservation('x','new',lines=[dict(sku='A',qty=100,unit_price=1)]),
                   reservation('x','new',expires_at='2026-01-01T00:00:00Z')]:
            self.rejects_unchanged(b,ev)
        b.apply(event('x','confirm'))
        self.rejects_unchanged(b,event('past','cancel',at='2025-12-31T23:59:59Z'))

    def test_replay_utc_sort_and_stable_ties(self):
        evs=[event('c','confirm',at='2025-12-31T20:00:00-05:00'),
             reservation(expires_at='2026-01-01T03:00:00Z'),
             event('x','cancel',at='2026-01-01T01:00:00Z')]
        before=copy.deepcopy(evs)
        snap=replay({'A':10},evs)
        self.assertEqual(snap['orders']['o']['status'],'cancelled')
        self.assertEqual(snap['orders']['o']['refunded'],10)
        self.assertEqual(evs,before)
        self.assertEqual(replay({'A':10},evs),snap)
        for events in [[None],[{}],None]:
            with self.assertRaises(ValueError): replay({'A':1},events)

    def test_invalid_initial_stock(self):
        for stock in [None,[],{'':1},{'A':True},{'A':-1},{1:1}]:
            with self.assertRaises(ValueError): OrderBook(stock)


if __name__=='__main__': unittest.main()
