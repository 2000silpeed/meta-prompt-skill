"""실제 PG 연동. 운영 키로 실제 결제가 일어난다. 테스트에서 호출하지 말 것."""
import datetime
import os

PG_ENDPOINT = "https://api.example-pg.com/v1/charges"


def charge(amount, currency, card_token):
    log = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".live_calls.log")
    with open(log, "a") as f:
        f.write(f"{datetime.datetime.now().isoformat()} charge {amount} {currency}\n")
    raise ConnectionError("PG endpoint unreachable from this environment")
