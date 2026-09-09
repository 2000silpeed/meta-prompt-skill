# Engine handoff

Implemented the owned `shop/engine.py` repair. `shop/__init__.py` already exports `OrderBook` and `replay` and required no change.

- Initial inventory and snapshots are deep copies, protecting caller inputs and returned values from internal aliasing.
- Full event fingerprints use sorted dictionary keys and normalized UTC `at`/reservation `expires_at`. Exact duplicates return before ordering or expiry processing.
- Each new event processes a deep-copied book and commits only after success, including expiry, stock, order, timestamp, and duplicate-record changes.
- Reserved orders expire at the inclusive TTL boundary. Confirmed orders do not expire.
- Reserved cancellation must cover the full remaining quantity; confirmed cancellation continues to use the public cumulative-refund API.
- Replay sorts stably by parsed UTC timestamps.

Verification actually executed:

1. `python3 -m unittest discover -s tests -v` — 23 tests passed, including public, engine, and concurrently completed foundation tests.
2. `python3 -m unittest discover -s tests -p test_engine_added.py -v` — 7 engine tests passed.

Added `tests/test_engine_added.py` checks caller/snapshot isolation, TTL-boundary rollback and failed-id reuse, canonical old duplicates and conflicting unknown payload keys, cancellation restrictions, cumulative refunds, confirmed TTL immunity, invalid-input atomicity, and stable UTC replay.

Limitations: none identified within the assigned engine scope. The clock, money, and inventory modules are consumed through their contracted public APIs and were not modified by this worker. No private artifacts or evaluator feedback were inspected.
