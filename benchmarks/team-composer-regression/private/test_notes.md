# Independent acceptance tests

Source: only `../fixture/CONTRACT.md` and the authoring instructions in `TEST_AUTHOR.md` were read. No candidate implementation, public tests, or benchmark output was consulted. Tests use Python's standard library and the candidate's documented `shop` API.

The suite has 40 individually named observable acceptance tests. Validation variants use small grouped subtests where the same contract rule applies. Coverage includes public exports, UTC timestamps, exact integer discount allocation, refund rounding, inventory atomicity, validation, order lifecycle, TTL boundaries and transactional rollback, event ordering and duplicate history, ownership/deep snapshots, and replay.

Critical expected values are derived directly from the contract:

- Gross totals `2, 3, 5`, discount `4`: floor allocations `0, 1, 2`; the remaining unit goes to the first SKU's `8/10` remainder, producing net `1, 2, 3`.
- Gross totals `2**60` and `2**60 + 1`, discount `1`: the second SKU has the strictly larger integer remainder despite float precision limits, so both net totals equal `2**60`.
- A three-unit line with gross `15` and discount `5` has original net `10`; consecutive one-unit cancellations refund `3, 3, 4`. Batched final two-unit cancellation refunds `7`.
- Confirmation exactly at expiry fails and preserves the earlier reserved snapshot. Reusing the failed ID at a valid earlier time checks rollback of the clock and duplicate record too.
- Replay uses equivalent UTC instants with different textual offsets, including an equal-instant reserve/confirm/cancel sequence whose input order is essential.

No candidate execution was performed while authoring. Syntax and test count can be verified without importing or reading any implementation. Tests do not assume exception messages, undocumented helper functions, extra stock validation in inventory helpers, or unspecified ISO serialization of fractional seconds.
