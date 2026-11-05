from datetime import datetime, timezone
from zoneinfo import ZoneInfo


UTC = timezone.utc
WIB = ZoneInfo('Asia/Jakarta')


def utc_now(tz: timezone | ZoneInfo = UTC) -> datetime:
    if tz is UTC:
        return datetime.now(UTC)
    return datetime.now(UTC).astimezone(tz)


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
