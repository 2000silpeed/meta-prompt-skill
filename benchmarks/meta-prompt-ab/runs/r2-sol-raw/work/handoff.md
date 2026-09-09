# Handoff

## Changes

- Corrected ISO timestamp parsing so explicit offsets are required and converted to the actual UTC instant.
- Made discount allocation exact with integer arithmetic and the required SKU tie-break; corrected cumulative refund deltas and rejected booleans as integers.
- Made inventory reservation and release validate completely before mutation.
- Isolated `OrderBook` state from caller-owned stock, events, and snapshots.
- Reworked event application to use a staged deep copy, providing rollback of expiry, state, `as_of`, and duplicate records on every rejected event.
- Implemented inclusive TTL expiry for reserved orders only, full-only cancellation before confirmation, line-based cumulative refunds after confirmation, and proper terminal statuses.
- Canonicalized duplicate fingerprints by recursively ignoring dict key order and normalizing event timestamps to UTC; exact old duplicates are checked before time ordering and expiry.
- Made replay sort by parsed UTC instants while preserving input order for ties.
- Added `tests/test_additional.py` with contract-focused edge cases.

## Verification

- `python -m unittest -v tests.test_public` — 6 tests passed.
- `python -m unittest discover -s tests -v` — 19 tests passed.
- `python -m compileall -q shop tests` — passed with no output.

## Limitations

- No known functional limitations within the contract scope.
