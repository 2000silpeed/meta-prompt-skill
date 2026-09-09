from datetime import datetime, timezone
import re

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")

def parse_time(text):
    if not isinstance(text, str) or not _ISO.fullmatch(text):
        raise ValueError('timestamp must include an explicit offset')
    try:
        value = datetime.fromisoformat(text[:-1] + '+00:00' if text.endswith('Z') else text)
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('invalid timestamp') from exc
