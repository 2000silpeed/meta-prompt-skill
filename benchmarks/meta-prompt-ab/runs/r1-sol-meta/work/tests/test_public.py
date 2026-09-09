import unittest
from shop import OrderBook, replay
from shop.money import allocate_discount, refund_delta
from shop.inventory import reserve
from shop.clock import parse_time


def event(eid='r', kind='reserve', oid='o', at='2026-01-01T00:00:00Z', **extra):
    return dict(id=eid, type=kind, order_id=oid, at=at, **extra)


def reservation():
    return event(lines=[dict(sku='A', qty=2, unit_price=100)], expires_at='2026-01-01T01:00:00Z')


class PublicTests(unittest.TestCase):
    def test_happy_path(self):
        b=OrderBook({'A':5}); b.apply(reservation())
        b.apply(event('c','confirm',at='2026-01-01T00:10:00Z'))
        self.assertEqual(b.snapshot()['stock'],{'A':3})
        self.assertEqual(b.snapshot()['orders']['o']['charged'],200)

    def test_refund_keeps_last_unit(self):
        self.assertEqual(refund_delta(10,3,2,1),4)

    def test_timezone(self):
        self.assertEqual(parse_time('2026-01-01T09:00:00+09:00'),parse_time('2026-01-01T00:00:00Z'))

    def test_atomic_stock(self):
        stock={'A':2,'B':0}
        with self.assertRaises(ValueError): reserve(stock,{'A':1,'B':1})
        self.assertEqual(stock,{'A':2,'B':0})

    def test_discount_conservation(self):
        self.assertEqual(sum(allocate_discount([{'sku':'A','qty':1,'unit_price':10},{'sku':'B','qty':1,'unit_price':10}],3).values()),17)

    def test_empty_replay(self):
        self.assertEqual(replay({'A':1},[]),{'stock':{'A':1},'orders':{},'as_of':None})

if __name__=='__main__': unittest.main()
