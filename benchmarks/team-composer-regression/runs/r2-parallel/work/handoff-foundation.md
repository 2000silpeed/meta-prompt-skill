# Foundation handoff

Implemented the assigned contracts in shop/clock.py, shop/money.py, and shop/inventory.py. Public function signatures are unchanged.

- Timestamps reject naive/non-string/date-only input, preserve the instant when converting offsets to UTC, and report conversion overflow as ValueError.
- Money rejects bool numeric inputs; proportional discounts use exact integer floors and SKU ascending remainder ties. Refunds use the cumulative floor difference so final cancellations conserve the original net total.
- Inventory validates the stock and all requested items before mutation. Reserve checks every quantity before subtracting, preventing partial changes on insufficient stock. Release validates the whole request before adding.
- Added tests/test_foundation_added.py for offset date rollover, invalid timestamps, huge exact money values, discount ties, caller input preservation, invalid numeric types, cumulative refund conservation, and atomic inventory failures.

Validation actually run:

1. `python3 -m unittest discover -s tests -v` — 12 tests passed (six public and six added foundation tests).
2. `python3 -m unittest discover -s tests -p test_foundation_added.py -v` — six foundation tests passed.

Limitations: No known limitations within the three assigned modules. Engine implementation is owned by another worker and was not modified. No private tests or evaluator artifacts were inspected.
