# Engine handoff

Implemented the assigned engine repair against CONTRACT.md while preserving the public OrderBook and replay APIs. shop/__init__.py already exports both and required no change.

Changes in shop/engine.py:
- Copy initial stock and return deep snapshot copies to prevent caller aliasing.
- Canonicalize full event payloads with sorted object keys and UTC event/expiry timestamps. Check duplicate IDs before chronological validation or expiration.
- Stage expiration and dispatch on a deep copy, committing only successful events; rejected events preserve stock, orders, as_of, and duplicate records.
- Expire only reserved orders at expires_at <= event time.
- Enforce full cancellation for reserved orders, retaining the contracted inventory and money public API calls for reservations, restoration, and cumulative confirmed refunds.
- Replay by parsed UTC timestamps using stable sorting without modifying caller events.

Added tests/test_engine_added.py covers input/snapshot isolation, canonical and conflicting retransmissions, older duplicate events, expiration boundary rollback, failed-ID reuse, confirmed TTL immunity, cumulative refunds, reserved full cancellation, terminal-order errors, UTC replay ordering and stable ties, and malformed event atomicity.

Validation actually executed:
- `python3 -m unittest discover -s tests -v`: 19 tests passed (public, engine additions, and concurrently completed foundation additions).
- `python3 -m unittest discover -s tests -p test_engine_added.py -v`: 7 tests passed.

Limitations: None identified within the assigned contract and public API scope. Hidden evaluation was not accessed. Foundation modules were used through their public APIs and were not modified by this worker.
