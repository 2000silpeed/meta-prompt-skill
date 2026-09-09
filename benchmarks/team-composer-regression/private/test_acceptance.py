"""Independent public-contract acceptance tests; standard library only."""
import copy
import unittest
from datetime import datetime, timezone

import shop
import shop.clock
import shop.money
import shop.inventory
import shop.engine


T0 = "2026-01-01T00:00:00Z"
T1 = "2026-01-01T00:01:00Z"
T2 = "2026-01-01T00:02:00Z"
T3 = "2026-01-01T00:03:00Z"
T4 = "2026-01-01T00:04:00Z"


def line(sku="a", qty=3, price=5):
    return {"sku": sku, "qty": qty, "unit_price": price}


def reserve(eid="r", oid="o", at=T0, expiry=T3, lines=None, **extra):
    event = {"id": eid, "type": "reserve", "order_id": oid,
             "at": at, "expires_at": expiry,
             "lines": [line()] if lines is None else lines}
    event.update(extra)
    return event


def event(kind, eid, oid="o", at=T1, **extra):
    result = {"id": eid, "type": kind, "order_id": oid, "at": at}
    result.update(extra)
    return result


class Acceptance(unittest.TestCase):
    def book(self, **kwargs):
        book = shop.OrderBook({"a": 10, "b": 10})
        book.apply(reserve(**kwargs))
        return book

    def rejected(self, book, payload):
        before = book.snapshot()
        with self.assertRaises(ValueError):
            book.apply(payload)
        self.assertEqual(book.snapshot(), before)

    def test_01_public_exports_and_initial_snapshot(self):
        self.assertIs(shop.OrderBook, shop.engine.OrderBook)
        self.assertIs(shop.replay, shop.engine.replay)
        self.assertEqual(shop.OrderBook({}).snapshot(),
                         {"stock": {}, "orders": {}, "as_of": None})

    def test_02_time_offsets_canonicalize_to_utc(self):
        expected = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for value in (T0, "2026-01-01T09:00:00+09:00",
                      "2025-12-31T19:00:00-05:00"):
            self.assertEqual(shop.clock.parse_time(value), expected)
            self.assertEqual(shop.clock.parse_time(value).utcoffset().total_seconds(), 0)

    def test_03_time_requires_datetime_string_and_offset(self):
        for value in (None, 0, True, "2026-01-01", "2026-01-01T00:00:00", "bad"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                shop.clock.parse_time(value)

    def test_04_discount_largest_remainder_and_sku_tie(self):
        rows = [line("c", 1, 1), line("b", 1, 1), line("a", 1, 1)]
        original = copy.deepcopy(rows)
        self.assertEqual(shop.money.allocate_discount(rows, 2), {"a": 0, "b": 0, "c": 1})
        self.assertEqual(rows, original)
        self.assertEqual(shop.money.allocate_discount(
            [line("a", 1, 2), line("b", 1, 3), line("c", 1, 5)], 4),
            {"a": 1, "b": 2, "c": 3})

    def test_05_large_integer_discount_remainder_is_exact(self):
        n = 2 ** 60
        self.assertEqual(shop.money.allocate_discount(
            [line("a", 1, n), line("b", 1, n + 1)], 1), {"a": n, "b": n})

    def test_06_zero_subtotal_and_full_discount(self):
        self.assertEqual(shop.money.allocate_discount([line("a", 2, 0)], 0), {"a": 0})
        self.assertEqual(shop.money.allocate_discount([line("a", 2, 7)], 14), {"a": 0})
        with self.assertRaises(ValueError):
            shop.money.allocate_discount([line("a", 2, 0)], 1)

    def test_07_invalid_line_shapes_and_duplicate_sku(self):
        for rows in ([], {}, [None], [{}], [line("", 1, 1)],
                     [line(), line()], [line("a", 0, 1)], [line("a", 1, -1)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                shop.money.allocate_discount(rows, 0)

    def test_08_discount_rejects_bool_and_noninteger_numbers(self):
        for rows, discount in (([line(qty=True)], 0), ([line(price=False)], 0),
                               ([line()], True), ([line(qty=1.5)], 0),
                               ([line()], -1), ([line()], 16), ([line()], 0.5)):
            with self.subTest(rows=rows, discount=discount), self.assertRaises(ValueError):
                shop.money.allocate_discount(rows, discount)

    def test_09_refund_cumulative_rounding_and_large_integer(self):
        self.assertEqual([shop.money.refund_delta(10, 3, c, 1) for c in range(3)], [3, 3, 4])
        self.assertEqual(shop.money.refund_delta(10, 3, 1, 2), 7)
        n = 2 ** 60 + 7
        self.assertEqual(shop.money.refund_delta(n, 7, 3, 4), n - n * 3 // 7)

    def test_10_refund_domain_validation(self):
        for args in ((-1, 3, 0, 1), (10, 0, 0, 1), (10, 3, -1, 1),
                     (10, 3, 3, 1), (10, 3, 0, 0), (10, 3, 2, 2),
                     (True, 3, 0, 1), (10, True, 0, 1),
                     (10, 3, False, 1), (10, 3, 0, True), (10.0, 3, 0, 1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                shop.money.refund_delta(*args)

    def test_11_inventory_success_in_place_and_items_unchanged(self):
        stock = {"a": 4, "b": 2}
        items = {"a": 3, "b": 2}
        self.assertIsNone(shop.inventory.reserve(stock, items))
        self.assertEqual(stock, {"a": 1, "b": 0})
        self.assertIsNone(shop.inventory.release(stock, items))
        self.assertEqual(stock, {"a": 4, "b": 2})
        self.assertEqual(items, {"a": 3, "b": 2})

    def test_12_inventory_reserve_cross_sku_atomicity(self):
        for items in ({"a": 2, "b": 99}, {"a": 2, "unknown": 1}, {"a": 2, "b": True}):
            stock = {"a": 4, "b": 2}
            with self.subTest(items=items), self.assertRaises(ValueError):
                shop.inventory.reserve(stock, items)
            self.assertEqual(stock, {"a": 4, "b": 2})

    def test_13_inventory_release_cross_sku_atomicity_and_empty_items(self):
        for items in ({"a": 2, "unknown": 1}, {"a": 2, "b": 0}, {}, {"a": False}):
            stock = {"a": 4, "b": 2}
            with self.subTest(items=items), self.assertRaises(ValueError):
                shop.inventory.release(stock, items)
            self.assertEqual(stock, {"a": 4, "b": 2})
        with self.assertRaises(ValueError):
            shop.inventory.reserve({"a": 1}, {})

    def test_14_initial_stock_validation(self):
        for stock in ({"a": True}, {"a": -1}, {"": 2}, {1: 2}, {"a": 1.5}, []):
            with self.subTest(stock=stock), self.assertRaises(ValueError):
                shop.OrderBook(stock)

    def test_15_reserve_snapshot_defaults_and_input_ownership(self):
        stock = {"a": 10}
        payload = reserve()
        original = copy.deepcopy(payload)
        book = shop.OrderBook(stock)
        self.assertIsNone(book.apply(payload))
        self.assertEqual(stock, {"a": 10})
        self.assertEqual(payload, original)
        self.assertEqual(book.snapshot(), {"stock": {"a": 7}, "orders": {"o": {
            "status": "reserved", "remaining": {"a": 3}, "line_totals": {"a": 15},
            "charged": 0, "refunded": 0}}, "as_of": "2026-01-01T00:00:00+00:00"})

    def test_16_confirm_charges_once_without_reserving_again(self):
        book = self.book(discount=5)
        self.assertIsNone(book.apply(event("confirm", "c")))
        order = book.snapshot()["orders"]["o"]
        self.assertEqual((order["status"], order["charged"], order["refunded"]), ("confirmed", 10, 0))
        self.assertEqual(book.snapshot()["stock"]["a"], 7)
        self.rejected(book, event("confirm", "c2", at=T2))

    def test_17_reserved_full_cancel_restores_without_refund(self):
        book = self.book()
        book.apply(event("cancel", "x"))
        order = book.snapshot()["orders"]["o"]
        self.assertEqual((order["status"], order["charged"], order["refunded"]), ("cancelled", 0, 0))
        self.assertEqual(order["remaining"], {"a": 0})
        self.assertEqual(book.snapshot()["stock"], {"a": 10, "b": 10})

    def test_18_reserved_partial_cancel_rejected_full_explicit_allowed(self):
        book = self.book(lines=[line("a", 2, 2), line("b", 1, 3)])
        self.rejected(book, event("cancel", "x", items={"a": 2}))
        self.rejected(book, event("cancel", "x", items={"a": 3}))
        book.apply(event("cancel", "x", items={"a": 2, "b": 1}))
        self.assertEqual(book.snapshot()["orders"]["o"]["remaining"], {"a": 0, "b": 0})

    def test_19_confirmed_partial_cancel_cumulative_rounding(self):
        book = self.book(discount=5)
        book.apply(event("confirm", "c"))
        for index, (refunded, status) in enumerate(((3, "confirmed"), (6, "confirmed"), (10, "cancelled"))):
            book.apply(event("cancel", "x" + str(index), at=T2, items={"a": 1}))
            order = book.snapshot()["orders"]["o"]
            self.assertEqual((order["refunded"], order["charged"], order["status"]), (refunded, 10, status))
            self.assertEqual(order["remaining"], {"a": 2 - index})
            self.assertEqual(book.snapshot()["stock"]["a"], 8 + index)

    def test_20_omitted_cancel_items_cancels_only_remaining(self):
        book = self.book(discount=5)
        book.apply(event("confirm", "c"))
        book.apply(event("cancel", "x1", at=T2, items={"a": 1}))
        book.apply(event("cancel", "x2", at=T2))
        self.assertEqual(book.snapshot()["orders"]["o"]["refunded"], 10)
        self.assertEqual(book.snapshot()["stock"]["a"], 10)

    def test_21_confirmed_cancel_cross_sku_atomicity(self):
        book = self.book(lines=[line("a", 2, 2), line("b", 1, 3)])
        book.apply(event("confirm", "c"))
        for items in ({"a": 1, "b": 2}, {"a": 1, "unknown": 1}, {}, {"a": True}):
            self.rejected(book, event("cancel", "x", at=T2, items=items))

    def test_22_terminal_orders_cannot_confirm_cancel_or_be_reused(self):
        book = self.book()
        book.apply(event("cancel", "x"))
        self.rejected(book, event("confirm", "c", at=T2))
        self.rejected(book, event("cancel", "x2", at=T2))
        self.rejected(book, reserve("r2", at=T2))

    def test_23_expiry_must_be_strictly_after_reserve(self):
        book = shop.OrderBook({"a": 10})
        for expiry in (T0, "2025-12-31T23:59:59Z", "2026-01-01T09:00:00+09:00"):
            self.rejected(book, reserve(expiry=expiry))

    def test_24_exact_ttl_confirm_rejection_rolls_back_everything(self):
        book = self.book(expiry=T2)
        self.rejected(book, event("confirm", "c", at=T2))
        # Failure must preserve both reserved status and the previous clock/id history.
        book.apply(event("confirm", "c", at=T1))
        self.assertEqual(book.snapshot()["orders"]["o"]["status"], "confirmed")

    def test_25_success_at_exact_ttl_expires_and_reuses_released_stock(self):
        book = shop.OrderBook({"a": 3})
        book.apply(reserve(expiry=T2))
        book.apply(reserve("r2", "o2", at=T2, expiry=T3))
        snap = book.snapshot()
        self.assertEqual(snap["stock"], {"a": 0})
        self.assertEqual(snap["orders"]["o"], {"status": "expired", "remaining": {"a": 0},
                         "line_totals": {"a": 15}, "charged": 0, "refunded": 0})
        self.rejected(book, event("cancel", "x", at=T2))
        self.rejected(book, event("confirm", "c", at=T2))
        self.rejected(book, reserve("r3", at=T2))

    def test_26_failed_event_rolls_back_other_orders_expiration(self):
        book = self.book(expiry=T1)
        self.rejected(book, reserve("r2", "o2", at=T2, lines=[line("b", 99, 1)]))
        book.apply(reserve("r2", "o2", at=T2, lines=[line("b", 1, 1)]))
        self.assertEqual(book.snapshot()["orders"]["o"]["status"], "expired")
        self.assertEqual(book.snapshot()["stock"], {"a": 10, "b": 9})

    def test_27_confirmed_order_survives_ttl(self):
        book = self.book(expiry=T2)
        book.apply(event("confirm", "c"))
        book.apply(reserve("r2", "o2", at=T3, expiry=T4, lines=[line("b", 1, 1)]))
        self.assertEqual(book.snapshot()["orders"]["o"]["status"], "confirmed")
        self.assertEqual(book.snapshot()["stock"]["a"], 7)

    def test_28_time_reversal_rejected_equal_timestamp_allowed(self):
        book = self.book()
        book.apply(event("confirm", "c", at=T1))
        self.rejected(book, event("cancel", "x", at=T0))
        book.apply(event("cancel", "x", at=T1))
        self.assertEqual(book.snapshot()["as_of"], "2026-01-01T00:01:00+00:00")

    def test_29_older_duplicate_bypasses_time_and_expiration(self):
        payload = reserve()
        book = shop.OrderBook({"a": 10})
        book.apply(payload)
        book.apply(event("confirm", "c"))
        before = book.snapshot()
        self.assertIsNone(book.apply(copy.deepcopy(payload)))
        self.assertEqual(book.snapshot(), before)

    def test_30_duplicate_fingerprint_normalizes_both_time_fields_and_key_order(self):
        payload = reserve(metadata={"z": 1, "a": [2, 3]})
        book = shop.OrderBook({"a": 10})
        book.apply(payload)
        book.apply(event("confirm", "c"))
        equivalent = dict(reversed(list(payload.items())))
        equivalent["at"] = "2026-01-01T09:00:00+09:00"
        equivalent["expires_at"] = "2025-12-31T19:03:00-05:00"
        equivalent["metadata"] = {"a": [2, 3], "z": 1}
        before = book.snapshot()
        self.assertIsNone(book.apply(equivalent))
        self.assertEqual(book.snapshot(), before)

    def test_31_duplicate_fingerprint_includes_unknown_keys(self):
        book = self.book(metadata={"value": 1})
        self.rejected(book, reserve(metadata={"value": 2}))
        self.rejected(book, reserve())

    def test_32_duplicate_fingerprint_preserves_line_order(self):
        rows = [line("a", 1, 2), line("b", 1, 3)]
        book = self.book(lines=rows)
        self.rejected(book, reserve(lines=list(reversed(rows))))

    def test_33_failed_event_id_can_be_retried_with_corrected_payload(self):
        book = shop.OrderBook({"a": 3})
        self.rejected(book, reserve(lines=[line(qty=4)]))
        self.assertIsNone(book.apply(reserve()))
        self.assertEqual(book.snapshot()["stock"]["a"], 0)

    def test_34_invalid_common_event_fields_only_raise_valueerror(self):
        book = self.book()
        cases = [None, [], {}, event("unknown", "x"), event("confirm", ""),
                 event("confirm", "x", oid=""), event("confirm", "x", at=None)]
        for key in ("id", "type", "order_id", "at"):
            payload = event("confirm", "x")
            del payload[key]
            cases.append(payload)
        for payload in cases:
            with self.subTest(payload=payload):
                self.rejected(book, payload)

    def test_35_snapshot_and_caller_mutations_do_not_alias_internal_state(self):
        stock = {"a": 10}
        payload = reserve(metadata={"nested": [1]})
        original = copy.deepcopy(payload)
        book = shop.OrderBook(stock)
        book.apply(payload)
        expected = book.snapshot()
        stock["a"] = 99
        payload["lines"][0]["qty"] = 99
        payload["metadata"]["nested"].append(2)
        snap = book.snapshot()
        snap["stock"]["a"] = 99
        snap["orders"]["o"]["remaining"]["a"] = 99
        snap["orders"]["o"]["line_totals"]["a"] = 99
        snap["orders"]["o"]["status"] = "cancelled"
        self.assertEqual(book.snapshot(), expected)
        book.apply(original)
        self.assertEqual(book.snapshot(), expected)

    def test_36_cancel_items_caller_ownership(self):
        book = self.book()
        book.apply(event("confirm", "c"))
        payload = event("cancel", "x", items={"a": 1})
        before = copy.deepcopy(payload)
        book.apply(payload)
        self.assertEqual(payload, before)
        payload["items"]["a"] = 99
        book.apply(before)
        self.assertEqual(book.snapshot()["orders"]["o"]["remaining"], {"a": 2})

    def test_37_engine_reserve_cross_sku_failure_is_atomic(self):
        book = shop.OrderBook({"a": 3, "b": 1})
        self.rejected(book, reserve(lines=[line("a", 2, 1), line("b", 2, 1)]))
        self.rejected(book, reserve(lines=[line("a", 2, 1), line("unknown", 1, 1)]))

    def test_38_replay_utc_sort_and_input_immutability(self):
        events = [event("cancel", "x", at="2025-12-31T19:02:00-05:00"),
                  reserve(at="2026-01-01T09:00:00+09:00"),
                  event("confirm", "c", at=T1)]
        original = copy.deepcopy(events)
        stock = {"a": 10}
        first = shop.replay(stock, events)
        self.assertEqual(first["orders"]["o"]["status"], "cancelled")
        self.assertEqual(first["orders"]["o"]["refunded"], 15)
        self.assertEqual(first["as_of"], "2026-01-01T00:02:00+00:00")
        self.assertEqual(shop.replay(stock, events), first)
        self.assertEqual(events, original)
        self.assertEqual(stock, {"a": 10})

    def test_39_replay_equal_instant_stable_order(self):
        events = [reserve(eid="z"), event("confirm", "a", at="2026-01-01T09:00:00+09:00"),
                  event("cancel", "m", at=T0)]
        result = shop.replay({"a": 10}, events)
        self.assertEqual(result["orders"]["o"]["charged"], 15)
        self.assertEqual(result["orders"]["o"]["refunded"], 15)
        with self.assertRaises(ValueError):
            shop.replay({"a": 10}, [events[1], events[0], events[2]])

    def test_40_replay_empty_and_invalid_events(self):
        self.assertEqual(shop.replay({"a": 0}, []), {"stock": {"a": 0}, "orders": {}, "as_of": None})
        for events in ([None], [{}], [event("confirm", "c")], [reserve(at="naive")]):
            with self.subTest(events=events), self.assertRaises(ValueError):
                shop.replay({"a": 10}, events)


if __name__ == "__main__":
    unittest.main()
