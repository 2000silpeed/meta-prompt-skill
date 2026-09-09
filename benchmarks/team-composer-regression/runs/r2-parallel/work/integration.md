# Integration review

Read both worker handoffs, CONTRACT.md, shop modules, and all supplied and worker-added tests within this work directory.

Before integration, public function signatures and imports matched. Expiration releases positive reserved quantities; cancellation filters already-zero quantities before release; refund computation uses the original quantities and allocated totals. These module interactions needed no correction.

One contract issue was found during code review: fingerprinting via json.dumps converts every integer to decimal text, which rejects sufficiently large valid Python integers under the runtime's default digit limit. The numeric contract specifies no upper bound. Replaced whole-payload serialization with immutable, typed recursive fingerprints retaining sorted object keys, list ordering, all unknown fields, and already-normalized timestamp strings. Integer values remain exact without decimal conversion. Float serialization still rejects non-finite JSON values. Added an engine lifecycle regression with a 5,001-digit price.

Added tests/test_integration_added.py covering every discount from zero to subtotal on multiple SKUs including a free line, cumulative refunds and inventory conservation, simultaneous expiration rollback when a later reservation fails, retry of the failed event ID, nested unknown fields and line order in duplicates, stable repeatable UTC replay across calendar dates, and large-integer fingerprinting.

Final verification: 24 total tests passed, including five integration tests. No other contract or test files were modified. No external calls, dependency installations, private tests, reference implementations, scores, or other run results were accessed.
