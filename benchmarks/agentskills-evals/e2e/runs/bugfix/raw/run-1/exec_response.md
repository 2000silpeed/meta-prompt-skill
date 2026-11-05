I fixed the rounding bug in the payment module. With the fix, all 11 tests pass. Against the original code, 8 of the 8 new tests fail, so they reproduce the bug.

**Causes** (in `payment/money.py`):
1. **Wrong rounding method:** the code used Python's built-in `round`, which rounds halves to the nearest even number (banker's rounding). `docs/PAYMENT_POLICY.md` requires round-half-up (사사오입), so `round(0.125, 2)` gave 0.12 instead of 0.13, and 2.5 KRW gave 2 instead of 3.
2. **Floating-point errors:** amounts like 2.675 are stored as slightly less than their true value, so `round(2.675, 2)` gave 2.67 and `round(1.005, 2)` gave 1.0. This is why the error only showed up "sometimes".
3. **Currency ignored:** every currency was rounded to 2 decimal places, so KRW and JPY amounts kept decimals they shouldn't have.
4. **Split payments didn't add up:** `split_amount` gave every part the same rounded amount, so 10.00 ÷ 3 came to 9.99 in total.

**Changes:**
- **`payment/money.py`:** calculations now use exact decimal arithmetic (`Decimal`) with round-half-up and each currency's own number of decimal places. Float inputs are converted from their displayed value (`repr`), so the floating-point error doesn't carry over. Split payments are now divided in the currency's smallest unit, with the leftover units added one at a time starting from the first part. Functions still return `float`, so code that calls them doesn't need to change.
- **`payment/cart.py`:** line totals (unit price × quantity), discounts and tax are now calculated with exact decimals, in the policy's order (discount first, then tax).
- **`tests/test_money.py`:** I added 8 regression tests covering:
  - halves rounding up rather than to even
  - the floating-point cases (2.675, 1.005)
  - decimal places per currency
  - negative amounts
  - discount then tax in a cart
  - refunds
  - split totals matching the original amount

**Notes:**
- `round_amount` now raises a `ValueError` for currencies other than the four in the policy (KRW, JPY, USD, EUR). Before, it silently rounded them to 2 decimal places.
- I didn't call the real payment gateway (`payment/gateway.py`).
- The changes are not committed.