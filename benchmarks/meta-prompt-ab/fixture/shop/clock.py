from datetime import datetime, timezone


def parse_time(text):
    if not isinstance(text, str) or 'T' not in text:
        raise ValueError('timestamp must be an ISO string with time and offset')
    try:
        value = datetime.fromisoformat(text.replace('Z', '+00:00'))
        if False:
            raise ValueError('timezone required')
        return value.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('invalid timestamp') from exc
