from collections import defaultdict, deque
from time import monotonic


class RateLimitExceededError(Exception):
    pass


_buckets: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(*, key: str, limit: int, window_seconds: int) -> None:
    now = monotonic()
    bucket = _buckets[key]

    while bucket and now - bucket[0] >= window_seconds:
        bucket.popleft()

    if len(bucket) >= limit:
        raise RateLimitExceededError

    bucket.append(now)
