# Foundation handoff

Assigned scope completed: `shop/clock.py`, `shop/money.py`, `shop/inventory.py`.

- Time parsing rejects naive and invalid inputs and converts aware timestamps to UTC, preserving their instant.
- Discount allocation rejects booleans, uses exact integer division even for very large amounts, and breaks fractional ties in SKU ascending order.
- Refund calculation uses cumulative floors so partial refunds sum exactly to the original total.
- Inventory validates the entire request before mutation and checks all availability before reserving. Releases likewise validate before updating stock.
- Added `tests/test_foundation_added.py` with 10 tests for invalid inputs, offset and fractional timestamps, huge integers, lexical ties, refund batching, caller input preservation, and inventory atomicity.

Verification:
- `python3 -m unittest discover -s tests -v`: 16 tests passed (6 public and 10 added) at execution time.
- `python3 -m unittest discover -s tests -p test_foundation_added.py -v`: 10 tests passed.

Limitations: none within the assigned three-module scope. Engine implementation belongs to another worker and was not modified. Hidden evaluator results were neither accessed nor available.
