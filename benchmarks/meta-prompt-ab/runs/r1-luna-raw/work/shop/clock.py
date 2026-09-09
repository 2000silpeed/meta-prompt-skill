from datetime import datetime, timezone


def parse_time(text):
    if not isinstance(text, str) or 'T' not in text:
        raise ValueError('timestamp must be an ISO string with time and offset')
    try:
        if text.endswith('Z'):
            value = datetime.fromisoformat(text[:-1] + '+00:00')
        else:
            value = datetime.fromisoformat(text)
        if value.tzinfo is None:
            raise ValueError('timezone required')
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('invalid timestamp') from exc
