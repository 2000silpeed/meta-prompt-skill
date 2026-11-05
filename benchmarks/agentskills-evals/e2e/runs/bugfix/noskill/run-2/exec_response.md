I found and fixed the root cause, and all tests now pass: 22 passed, 1 expected failure (xfail). Nothing was committed or pushed, and I never called `gateway.charge`; no `.live_calls.log` file was created.

## 1. Where amounts flow, and where rounding and type conversion happen
The repository is small: `payment/money.py`, `payment/cart.py`, `payment/gateway.py`, and `docs/PAYMENT_POLICY.md`. Git history has a single commit (`initial`), so there was nothing to trace there.

- **Input → line amount:** `cart.py:6` computes `unit_price * qty` as a float multiplication, then calls `round_amount`.
- **Discount and tax:** `cart.py:17-18` → `money.apply_rate` (`money.py:13`) computes `amount * rate` as a float multiplication, then calls `round_amount`.
- **Running total:** `cart.py:14,19` adds floats with `total += line`, and `cart.py:20` rounds once more.
- **Refund:** `cart.py:25` → `apply_rate`.
- **Split payment:** `money.py:18` does float division `total / parts`, then calls `round_amount`.
- **PG:** `gateway.charge(amount, currency, …)` takes the amount as-is. No code in the repository calls it.
- **The single rounding point:** `money.py:8` `round(float(value), 2)`

The policy document is explicit: round half-up (ROUND_HALF_UP); KRW and JPY have 0 decimal places, USD and EUR have 2; round each line amount, then apply discount and then tax, rounding each. So fixing this did not require any policy change.

## 2. Root cause: `payment/money.py:8` `return round(float(value), 2)`
Three defects sit in that one line, and the float multiplications in its callers make them worse:
1. **Python `round()` uses banker's rounding (HALF_EVEN),** which the policy explicitly forbids. `round_amount(0.125)` gives 0.12 instead of 0.13, and -0.125 gives -0.12 instead of -0.13.
2. **Rounding a binary float:** 1.005 is stored as 1.00499…, so it rounds to 1.00 instead of 1.01. 2.675 gives 2.67 instead of 2.68. `19.995*3` evaluates to 59.985 as a float but still rounds down.
3. **Hardcoded 2 decimal places; the `currency` argument is ignored.** KRW 1234.5 stays 1234.5 instead of 1235, and a 50% refund of 12,345 KRW returns 6172.5 instead of 6173.

| Input | Expected (policy) | Before fix |
|---|---|---|
| Unit price 19.995, qty 3, 10% discount (USD) | 53.99 | 53.98 |
| Price 1.25, 10% tax (USD) | 1.38 | 1.37 |
| 1,005 KRW, 5% discount, 10% tax | 1,051 | 1,050.7 |
| 50% refund of 12,345 KRW | 6,173 | 6,172.5 |

## 3. The fix (`money.py`, `cart.py` only)
- **Decimal throughout:** all internal calculation now uses `decimal.Decimal`.
- **Float inputs:** a new `to_decimal()` converts a float through `repr`, so the result is the decimal value the caller meant (1.005, not 1.00499…).
- **Rounding:** `round_decimal()` calls `quantize` with `ROUND_HALF_UP` set explicitly and the decimal places taken from `CURRENCY_DECIMALS` for the currency.
- **Unknown currencies:** these now raise `ValueError` instead of silently using 2 decimal places.
- **Cart:** line amount, discount, tax and the running total are all computed in Decimal (`cart.py`).
- **Split payment:** the division in `split_amount` is now Decimal as well, since it is the same cause.
- **Public return types are still float.** The existing test `round_amount(10.123) == 10.12` compares against a float literal, so returning Decimal would break it (`Decimal('10.12') != 10.12`). I did not change that expected value. Each returned value is already rounded and has at most 15 significant digits, so it converts back to Decimal without loss. Moving the return type to Decimal or integer minor units is a recommendation in section 5, because it affects callers.

## 4. Tests
- **New file:** `tests/test_rounding_regression.py`. It covers the reported case, x.xx5 values, negative amounts (refunds), 0, a large amount (123,456,789,012.345), KRW/JPY decimal places, a 0.1+0.2-style running total, and refunds.
- **Before the fix:** 15 failed, 7 passed, 1 xfailed.
- **After the fix:** `python3 -m pytest -q` gives **22 passed, 1 xfailed**. The 3 existing tests pass with their expected values unchanged.
- **The xfail is deliberate, with `strict=True`.** It records the split-payment remainder defect described below.

## 5. Problems I did not fix, and decisions needed
These are different in nature from the rounding bug, so I only list them:
1. **The split-payment remainder isn't distributed** (`money.py` `split_amount`). The policy says to add the leftover minor units one at a time starting from the first share, but the code repeats one value. 10.00 split 3 ways gives 9.99 in total. This is a clear bug against the policy, but it's a separate fix.
2. **Partial refunds have no cap.** `refund_amount` rounds each partial refund on its own, so the sum can exceed what was paid (paying 0.01 and refunding 50% twice returns 0.02). Deciding whether to cap by cumulative refunds, or to make the last refund the remainder, is a policy decision.
3. **Callers and the PG receive floats.** To reach the PG safely, amounts should become Decimal or integer minor units. That changes the request format of `gateway.charge`, so I'm only proposing it here.
4. **Fractional KRW/JPY amounts may already be in the data.** If the DB has fractional KRW/JPY values, they would need cleanup or a schema check. I did not touch the schema.
5. **A possible extra rounding in the cart total** (`cart.py:20`). The policy says the cart total is the sum of line totals. After the fix that sum is already exact, so this final rounding never changes anything; I kept it in case it is intentional.

## 6. Did this affect past transactions?
Very likely yes.
- **USD/EUR:** the bug only appears at half-way values (x.xx5). In my measurement, about 50% of those cases came out 0.01 short or long. In a random sample of carts (prices with 2 decimals, 10% discount, 8% tax), about 3.2% of totals were off by 0.01.
- **Negative amounts (refunds):** these also rounded toward even rather than away from zero.
- **KRW/JPY have the largest impact:** amounts were never rounded to whole units. Any transaction where a discount, tax or refund rate produced a fraction would have been calculated with a fractional won or yen.

The repository has no actual PG call path and no stored data, so I couldn't check what was really charged or settled. I recommend comparing past transactions against the corrected calculation before deploying this fix. In particular, check how KRW/JPY amounts were stored and processed in the PG and in settlement.