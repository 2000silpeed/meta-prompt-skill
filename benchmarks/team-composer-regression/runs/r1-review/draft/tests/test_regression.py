import copy
import unittest

from shop import OrderBook, replay
from shop.clock import parse_time
from shop.inventory import reserve, release
from shop.money import allocate_discount, refund_delta


def event(eid, kind='reserve', oid='o', at='2026-01-01T00:00:00Z', **extra):
    result = dict(id=eid, type=kind, order_id=oid, at=at)
    if kind == 'reserve':
        result.update(lines=[dict(sku='A', qty=3, unit_price=4)], discount=2,
                      expires_at='2026-01-01T01:00:00Z')
    result.update(extra)
    return result


class RegressionTests(unittest.TestCase):
    def test_exact_money_and_tie(self):
        lines = [dict(sku=sku, qty=1, unit_price=10**100 + 1) for sku in ['z', 'aa', 'a']]
        net = allocate_discount(lines, 2)
        self.assertEqual(net, {'z':10**100+1, 'aa':10**100, 'a':10**100})
        self.assertEqual(allocate_discount([dict(sku='A',qty=1,unit_price=0)],0), {'A':0})
        for qty in range(1, 15):
            for total in range(30):
                self.assertEqual(sum(refund_delta(total,qty,i,1) for i in range(qty)),total)
                for i in range(qty):
                    self.assertEqual(refund_delta(total,qty,i,qty-i),total-total*i//qty)

    def test_invalid_money(self):
        valid = dict(sku='A',qty=1,unit_price=1)
        for lines, discount in [(None,0),([],0),([valid,valid],0),([valid],True),([valid],2),
                                ([dict(valid,qty=True)],0),([dict(valid,unit_price=False)],0)]:
            with self.subTest(lines=lines,discount=discount), self.assertRaises(ValueError):
                allocate_discount(lines,discount)
        for args in [(True,1,0,1),(1,True,0,1),(1,1,False,1),(1,1,0,True),(1,0,0,1),
                     (1,1,1,1),(1,3,2,2),(-1,1,0,1)]:
            with self.subTest(args=args), self.assertRaises(ValueError): refund_delta(*args)

    def test_time_validation(self):
        for value in [None, 1, '2026-01-01','2026-01-01T00:00:00','nonsense']:
            with self.subTest(value=value), self.assertRaises(ValueError): parse_time(value)
        self.assertEqual(parse_time('2025-12-31T19:00:00-05:00'),parse_time('2026-01-01T00:00:00Z'))

    def test_inventory_atomicity(self):
        for operation in [reserve,release]:
            for items in [{}, {'A':1,'B':True},{'A':1,'X':1},{'A':1,'B':-1}]:
                stock={'A':3,'B':2}; before=copy.deepcopy(stock)
                with self.subTest(operation=operation,items=items), self.assertRaises(ValueError): operation(stock,items)
                self.assertEqual(stock,before)
        stock={'A':3,'B':2}
        self.assertIsNone(reserve(stock,{'A':2,'B':2}))
        self.assertIsNone(release(stock,{'A':2,'B':2}))
        self.assertEqual(stock,{'A':3,'B':2})

    def test_aliases(self):
        stock={'A':6}; b=OrderBook(stock); stock['A']=0
        e=event('r'); original=copy.deepcopy(e); b.apply(e)
        self.assertEqual(e,original)
        e['lines'][0]['qty']=100
        snap=b.snapshot(); snap['stock']['A']=999; snap['orders']['o']['remaining']['A']=999
        snap['orders']['o']['line_totals']['A']=999
        self.assertEqual(b.snapshot()['stock'],{'A':3})
        self.assertEqual(b.snapshot()['orders']['o']['remaining'],{'A':3})
        self.assertEqual(b.snapshot()['orders']['o']['line_totals'],{'A':10})

    def test_duplicate_normalization_and_unknown_keys(self):
        b=OrderBook({'A':6}); r=event('r', extra={'x':1,'y':2}); b.apply(r)
        b.apply(event('c','confirm',at='2026-01-01T00:10:00Z'))
        snap=b.snapshot()
        duplicate=dict(reversed(list(r.items())))
        duplicate.update(at='2026-01-01T09:00:00+09:00',expires_at='2026-01-01T10:00:00+09:00',extra={'y':2,'x':1})
        self.assertIsNone(b.apply(duplicate)); self.assertEqual(b.snapshot(),snap)
        duplicate['extra']['x']=3
        with self.assertRaises(ValueError): b.apply(duplicate)
        self.assertEqual(b.snapshot(),snap)

    def test_expiry_rollback_and_id_retry(self):
        b=OrderBook({'A':3}); b.apply(event('r')); snap=b.snapshot()
        for e in [event('fail','confirm',at='2026-01-01T01:00:00Z'),
                  event('fail',oid='new',at='2026-01-01T01:00:00Z',expires_at='2026-01-01T02:00:00Z',lines=[dict(sku='X',qty=1,unit_price=1)])]:
            with self.assertRaises(ValueError): b.apply(e)
            self.assertEqual(b.snapshot(),snap)
        b.apply(event('fail',oid='new',at='2026-01-01T01:00:00Z',expires_at='2026-01-01T02:00:00Z'))
        self.assertEqual(b.snapshot()['orders']['o']['status'],'expired')
        self.assertEqual(b.snapshot()['orders']['o']['remaining'],{'A':0})
        self.assertEqual(b.snapshot()['stock'],{'A':0})

    def test_confirmed_refunds_and_no_expiry(self):
        b=OrderBook({'A':3}); b.apply(event('r')); b.apply(event('c','confirm'))
        for i, refund in enumerate([3,6,10],1):
            b.apply(event(str(i),'cancel',at='2026-01-01T02:00:00Z',items={'A':1}))
            order=b.snapshot()['orders']['o']
            self.assertEqual(order['refunded'],refund); self.assertEqual(order['charged'],10)
            self.assertEqual(order['status'],'cancelled' if i==3 else 'confirmed')
        self.assertEqual(b.snapshot()['stock'],{'A':3})
        for kind in ['confirm','cancel','reserve']:
            with self.assertRaises(ValueError): b.apply(event('new',kind,at='2026-01-01T02:00:00Z'))

    def test_reserved_full_cancel_only(self):
        b=OrderBook({'A':3}); b.apply(event('r')); snap=b.snapshot()
        for items in [{'A':1},{},{'X':3},{'A':4},{'A':True}]:
            with self.assertRaises(ValueError): b.apply(event('bad','cancel',items=items))
            self.assertEqual(b.snapshot(),snap)
        b.apply(event('bad','cancel'))
        self.assertEqual(b.snapshot()['stock'],{'A':3})
        self.assertEqual(b.snapshot()['orders']['o']['refunded'],0)

    def test_replay_utc_stability_and_inputs(self):
        r=event('r',at='2026-01-01T09:00:00+09:00')
        c=event('c','confirm',at='2026-01-01T00:00:00Z')
        x=event('x','cancel',at='2025-12-31T19:01:00-05:00')
        events=[x,r,c]; original=copy.deepcopy(events)
        snapshot=replay({'A':3},events)
        self.assertEqual(snapshot['orders']['o']['status'],'cancelled')
        self.assertEqual(snapshot,replay({'A':3},events)); self.assertEqual(events,original)
        for bad in [[None],[{}],[dict(r,at='bad')],None]:
            with self.assertRaises(ValueError): replay({'A':3},bad)

    def test_bad_envelopes_and_backwards(self):
        b=OrderBook({'A':3}); b.apply(event('r')); snap=b.snapshot()
        for e in [None, [], {}, event('', 'confirm'), event('x','nope'),
                  event('x','confirm',at='2025-12-31T23:00:00Z'),event('x','confirm',oid='missing')]:
            with self.subTest(e=e), self.assertRaises(ValueError): b.apply(e)
            self.assertEqual(b.snapshot(),snap)
        for stock in [None,[],{'':1},{'A':True},{'A':-1}]:
            with self.assertRaises(ValueError): OrderBook(stock)


if __name__ == '__main__': unittest.main()
