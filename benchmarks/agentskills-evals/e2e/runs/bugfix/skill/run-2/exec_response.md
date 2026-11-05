I found and fixed the root cause: amounts were stored and calculated as `float` and rounded with Python's built-in `round(x, 2)`. The documented rounding policy is used as-is. 31 regression tests failed before the fix, and all 41 tests (3 existing + 38 new) pass after it.

I didn't have to stop for a policy decision: `docs/PAYMENT_POLICY.md` clearly defines round-half-up, decimals per currency (KRW·JPY 0, USD·EUR 2), and how to hand out split remainders. I made no commits or pushes, and nothing calls `gateway.py`.

## 1. 근본 원인

**`payment/money.py:8` — `return round(float(value), 2)`.** This one line breaks two rules in the policy:

- **Binary float plus Python's `round`, which is not HALF_UP.**
  - Some values look like they end in exactly 5 but are stored slightly below it, so they round down:
    - `1.005` is stored as 1.00499999… → 1.0 (should be 1.01)
    - `2.675` → 2.67 (should be 2.68)
    - `0.015` → 0.01 (should be 0.02)
  - When the half is stored exactly, Python's `round` goes to the even digit: `0.125` → 0.12 (should be 0.13). A refund of `-1.005` gives -1.0 (should be -1.01).
  - This is why it only goes wrong "sometimes": the error appears only for particular values.
- **The currency is ignored.** The second argument is hard-coded to 2 decimals, so KRW/JPY `1000.5` stays 1000.5 (should be 1001), and `2.5` stays 2.5 (should be 3).

**Same cause, second location: `payment/cart.py:6, 14–19`.** Even after fixing `round_amount`, the cart still does its arithmetic in float, so results still drift.
- Example: price 0.21, 5% discount (0.01), then the line is `0.21 - 0.01 = 0.19999999999999998`. 7.5% tax on that is 0.01499… → 0.01, for a total of **0.21**. It should be 0.20 × 0.075 = 0.015 → 0.02, for a total of **0.22**.
- `line_total(1.115, 3)` is also off: in float the product is 3.3449999… → 3.34 (should be 3.35).
- A sweep (2,999 prices × 4 discount rates × 3 tax rates) found 552 wrong results with only `round_amount` fixed, and 0 after the fix.

**Separate cause, fixed alongside: `payment/money.py:18–19` (`split_amount`).** It never hands out the remainder. `100 ÷ 3` gives `[33.33]*3`, which adds up to 99.99. The policy requires the parts to add up to the original amount, with each leftover unit going to the earliest parts first.

## 2. 수정 내용

- **`payment/money.py`**
  - Added `to_decimal`: a float is converted to Decimal through its shortest decimal form (`repr`), not with `Decimal(float)`, so the binary error is not carried over.
  - Added `round_decimal`: uses the number of decimals for each currency with `ROUND_HALF_UP`. An unsupported currency now raises `ValueError`.
  - `round_amount` and `apply_rate` now calculate in Decimal internally.
  - `split_amount` now works in integer smallest units: it uses `divmod` and gives each leftover unit to the earliest parts first. Negative amounts are split by absolute value and the sign is put back.
- **`payment/cart.py`**: the whole cart calculation (line total, discount, tax, running sum) and the refund now use Decimal. The order of steps and where rounding happens are unchanged and still follow the policy.
- Function signatures and return types are unchanged (inputs: float/int/str/Decimal; return: `float`).

## 3. 테스트

New file: `tests/test_rounding_policy.py` (38 tests). It covers:
- **HALF_UP boundary values:** 0.005, 0.015, 1.005, 2.675, 0.125, 0, and 9,999,999,999.995.
- **Negative amounts (refunds):** rounded away from zero.
- **KRW/JPY:** includes 2.5 → 3 and -2.5 → -3.
- **Other rounding inputs:** EUR, unknown currency rejected, and string/Decimal inputs.
- **Rates and lines:** `apply_rate` and `line_total` (cases where float multiplication goes wrong).
- **Cart:** discount → tax cases in USD and KRW.
- **Refunds:** `refund_amount`.
- **Splits:** 100 ÷ 3 in USD and KRW, 0.05 ÷ 3, a negative amount, 0, and a very large amount, each checking that the parts add up exactly.

Results:
- **Before the fix:** 31 failed, 10 passed (the 3 existing tests passed).
- **After the fix:** `python3 -m pytest -q` → **41 passed**. The 3 existing tests' expected values were not changed.

**Where float is still used:** the public functions still return `float`. Changing the return type would change the public interface, and `test_round_simple` (`== 10.12`) assumes a float. Every calculation happens in Decimal, and only the final rounded value is converted to float. If a caller does more arithmetic on those floats, the same problem can come back.

## 4. 보고만 하고 하지 않은 것

- **Interface change (proposal):** return `Decimal` or an integer number of smallest units from the money functions, and have callers pass strings or Decimal instead of float. This needs every caller updated and changes to the existing tests, so I didn't implement it.
- **Behaviour change:** an unknown currency now raises `ValueError`. Before, it was silently rounded to 2 decimals. Callers passing lowercase codes like `"usd"` will get an error.
- **Schema / gateway integration:** there is no database code in this repo. `gateway.py` takes `amount` as a float and the format sent to the payment gateway isn't documented. Please check that DB columns are `NUMERIC`/integer smallest units, and that the gateway expects integer smallest units (e.g. cents).
- **Existing tests:** I didn't find any expected values that look wrong.

## 5. 미확인 사항

- **Negative splits:** the policy only says to add the remainder "from the earliest parts first." I assumed that for negative amounts this means by absolute value (-100 ÷ 3 → [-33.34, -33.33, -33.33]).
- **Float inputs:** I assumed a float input means the decimal number it prints as (its shortest `repr`). If a caller has already done float arithmetic before passing the value in (e.g. passes `0.1+0.2`), that error is already in the input and can't be corrected here.
- **Call sites:** there are no callers of these functions in the repo, so I couldn't check how amounts are parsed on the way in or serialized in API responses.