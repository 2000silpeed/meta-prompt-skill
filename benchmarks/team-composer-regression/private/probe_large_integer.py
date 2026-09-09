#!/usr/bin/env python3
"""Exploratory probe derived from r1-review's finding; NOT the frozen score."""
from copy import deepcopy
import json
from pathlib import Path
import sys

candidate=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(candidate))
from shop import OrderBook

stage='reserve'
result={'kind':'post-hoc exploratory observation','source':'r1-review reviewer finding',
        'int_string_limit':sys.get_int_max_str_digits(),'passed':False}
try:
    price=10**5000
    b=OrderBook({'A':2})
    reserve={'id':'r','type':'reserve','order_id':'o','at':'2026-01-01T00:00:00Z',
             'expires_at':'2026-01-01T01:00:00Z',
             'lines':[{'sku':'A','qty':1,'unit_price':price}]}
    b.apply(reserve)
    assert b.snapshot()['orders']['o']['line_totals']=={'A':price}
    stage='confirm'
    b.apply({'id':'c','type':'confirm','order_id':'o','at':'2026-01-01T00:01:00Z'})
    assert b.snapshot()['orders']['o']['charged']==price
    stage='older duplicate'
    before=b.snapshot(); b.apply(deepcopy(reserve)); assert b.snapshot()==before
    stage='full cancellation'
    b.apply({'id':'x','type':'cancel','order_id':'o','at':'2026-01-01T00:02:00Z'})
    snap=b.snapshot()
    assert snap['orders']['o']['refunded']==price and snap['stock']=={'A':2}
    result['passed']=True
except Exception as exc:
    result.update(failed_stage=stage,error_type=type(exc).__name__,error=str(exc))
print(json.dumps(result,ensure_ascii=False))
