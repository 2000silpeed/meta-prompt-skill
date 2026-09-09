import copy
import itertools
import unittest
from shop import OrderBook, replay
from shop.clock import parse_time
from shop.inventory import reserve, release
from shop.money import allocate_discount, refund_delta


def ev(eid='r', kind='reserve', oid='o', at='2026-01-01T00:00:00Z', **extra):
    return dict(id=eid, type=kind, order_id=oid, at=at, **extra)


def reservation(**extra):
    data = dict(lines=[dict(sku='A', qty=3, unit_price=4)], discount=2,
                expires_at='2026-01-01T01:00:00Z')
    data.update(extra)
    return ev(**data)


class ContractTests(unittest.TestCase):
    def assert_rejected(self, book, event):
        before = copy.deepcopy(book.__dict__)
        with self.assertRaises(ValueError):
            book.apply(event)
        self.assertEqual(book.__dict__, before)

    def test_clock(self):
        for value in [None, 1, True, '', '2026-01-01', '2026-01-01T12:00:00']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_time(value)
        self.assertEqual(parse_time('2026-01-01T09:00:00+09:00').isoformat(),
                         '2026-01-01T00:00:00+00:00')
        self.assertEqual(parse_time('2025-12-31T19:00:00-05:00'),
                         parse_time('2026-01-01T00:00:00Z'))

    def test_discount_exact_and_ties(self):
        lines = [dict(sku=s, qty=1, unit_price=1) for s in ['ZZ', 'B', 'A']]
        for permutation in itertools.permutations(lines):
            self.assertEqual(allocate_discount(list(permutation), 1), {'ZZ':1, 'B':1, 'A':0})
        huge = 10**400
        self.assertEqual(allocate_discount([dict(sku='A',qty=1,unit_price=huge),
                                            dict(sku='B',qty=1,unit_price=huge)],3),
                         {'A':huge-2,'B':huge-1})
        self.assertEqual(allocate_discount([dict(sku='A',qty=1,unit_price=0)],0),{'A':0})

    def test_money_validation(self):
        line = dict(sku='A', qty=1, unit_price=2)
        for lines, discount in [(None,0),([],0),([None],0),([line,line],0),([line],True),
                                ([line],-1),([line],3),([dict(line,qty=True)],0),
                                ([dict(line,unit_price=False)],0)]:
            with self.subTest(lines=lines,discount=discount), self.assertRaises(ValueError):
                allocate_discount(lines,discount)
        for args in [(True,1,0,1),(1,True,0,1),(1,1,False,1),(1,1,0,True),
                     (-1,1,0,1),(1,0,0,1),(1,1,1,1),(1,2,0,3),(1,2,0,0)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                refund_delta(*args)

    def test_refund_conservation(self):
        for total in range(31):
            for qty in range(1,12):
                self.assertEqual(sum(refund_delta(total,qty,n,1) for n in range(qty)),total)
                for cut in range(1,qty):
                    self.assertEqual(refund_delta(total,qty,0,cut)+refund_delta(total,qty,cut,qty-cut),total)

    def test_inventory_atomic(self):
        for fn in [reserve,release]:
            for items in [{}, {'A':1,'Z':1},{'A':1,'B':True},{'A':1,'B':0},None]:
                stock={'A':3,'B':2}; before=stock.copy()
                with self.subTest(fn=fn,items=items), self.assertRaises(ValueError): fn(stock,items)
                self.assertEqual(stock,before)
            stock={'A':3,'B':2}; items={'A':1,'B':2}
            self.assertIsNone(fn(stock,items))
            self.assertEqual(items,{'A':1,'B':2})
        stock={'A':3,'B':0}
        with self.assertRaises(ValueError): reserve(stock,{'A':1,'B':1})
        self.assertEqual(stock,{'A':3,'B':0})

    def test_alias_isolation(self):
        stock={'A':9}; book=OrderBook(stock); event=reservation(); original=copy.deepcopy(event)
        book.apply(event); self.assertEqual(stock,{'A':9}); self.assertEqual(event,original)
        expected=book.snapshot(); stock['A']=0; event['lines'][0]['qty']=99
        snap=book.snapshot(); snap['stock']['A']=0; snap['orders']['o']['remaining']['A']=99
        snap['orders']['o']['line_totals']['A']=99
        self.assertEqual(book.snapshot(),expected)

    def test_duplicates(self):
        book=OrderBook({'A':9}); first=reservation(extra={'x':1,'y':[1,2]}); book.apply(first)
        book.apply(ev('c','confirm',at='2026-01-01T00:10:00Z'))
        expected=book.snapshot()
        same=dict(reversed(list(first.items())))
        same['at']='2026-01-01T09:00:00+09:00'; same['expires_at']='2026-01-01T10:00:00+09:00'
        same['extra']={'y':[1,2],'x':1}
        self.assertIsNone(book.apply(same)); self.assertEqual(book.snapshot(),expected)
        self.assert_rejected(book,dict(first, extra={'x':2}))
        self.assert_rejected(book,dict(first, discount=1))

    def test_line_order_fingerprint(self):
        book=OrderBook({'A':9,'B':9})
        first=reservation(lines=[dict(sku='A',qty=1,unit_price=4),dict(sku='B',qty=1,unit_price=4)])
        book.apply(first)
        self.assert_rejected(book,dict(first,lines=list(reversed(first['lines']))))

    def test_expiry_boundary_rollback_and_retry(self):
        book=OrderBook({'A':9}); book.apply(reservation())
        bad=ev('next','confirm',at='2026-01-01T01:00:00Z')
        self.assert_rejected(book,bad)
        good=reservation(eid='next',oid='new',at='2026-01-01T01:00:00Z',expires_at='2026-01-01T02:00:00Z')
        book.apply(good)
        self.assertEqual(book.snapshot()['orders']['o']['status'],'expired')
        self.assertEqual(book.snapshot()['orders']['o']['remaining'],{'A':0})
        self.assertEqual(book.snapshot()['stock'],{'A':6})
        self.assert_rejected(book,ev('bad','cancel',at='2026-01-01T01:00:00Z'))

    def test_confirmed_no_expiry_and_refund(self):
        book=OrderBook({'A':9}); book.apply(reservation())
        book.apply(ev('c','confirm'))
        for n, expected in [(1,3),(2,6),(3,10)]:
            book.apply(ev(str(n),'cancel',at='2026-01-01T02:00:00Z',items={'A':1}))
            order=book.snapshot()['orders']['o']
            self.assertEqual(order['charged'],10); self.assertEqual(order['refunded'],expected)
            self.assertEqual(order['remaining'],{'A':3-n})
            self.assertEqual(order['status'],'cancelled' if n==3 else 'confirmed')
        self.assertEqual(book.snapshot()['stock'],{'A':9})
        self.assert_rejected(book,ev('late','confirm',at='2026-01-01T02:00:00Z'))

    def test_reserved_cancel_full_only_and_no_reuse(self):
        book=OrderBook({'A':9}); book.apply(reservation())
        self.assert_rejected(book,ev('x','cancel',items={'A':1}))
        book.apply(ev('x','cancel'))
        self.assertEqual(book.snapshot()['orders']['o']['refunded'],0)
        self.assertEqual(book.snapshot()['stock'],{'A':9})
        self.assert_rejected(book,reservation(eid='r2'))
        self.assert_rejected(book,ev('y','cancel'))

    def test_invalid_events_and_time(self):
        book=OrderBook({'A':9}); book.apply(reservation())
        for event in [None,[],{},ev('', 'confirm'),ev('bad','other'),
                      ev('bad','confirm',oid='missing'),ev('bad','cancel',items={}),
                      ev('bad','cancel',items={'Z':1}),ev('bad','cancel',items={'A':True}),
                      ev('bad','cancel',items={'A':4}),ev('bad','confirm',at='2025-12-31T23:00:00Z'),
                      reservation(eid='bad',oid='new',lines=[dict(sku='A',qty=100,unit_price=1)])]:
            with self.subTest(event=event): self.assert_rejected(book,event)
        for stock in [None,[],{'':1},{'A':True},{'A':-1},{1:2}]:
            with self.assertRaises(ValueError): OrderBook(stock)

    def test_replay_utc_stable_and_immutable(self):
        reserve_event=reservation(at='2026-01-01T09:00:00+09:00')
        confirm_event=ev('c','confirm',at='2026-01-01T00:01:00Z')
        events=[confirm_event,reserve_event]; original=copy.deepcopy(events)
        result=replay({'A':9},events)
        self.assertEqual(result['orders']['o']['status'],'confirmed')
        self.assertEqual(events,original); self.assertEqual(result,replay({'A':9},events))
        confirm_event['at']='2026-01-01T00:00:00Z'
        self.assertEqual(replay({'A':9},[reserve_event,confirm_event])['orders']['o']['status'],'confirmed')
        with self.assertRaises(ValueError): replay({'A':9},[confirm_event,reserve_event])
        for invalid in [None,[None],[{}],[ev(at=None)]]:
            with self.assertRaises(ValueError): replay({'A':9},invalid)

if __name__ == '__main__':
    unittest.main()
