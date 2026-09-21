"""Per-IP rate limiting for sensitive endpoints.

Uses ``slowapi`` with an in-process window counter (``MemoryStorage``). The
limiter is intentionally scoped to individual routes via ``@limiter.limit``
decorators (no global default), so only the endpoints that need brute-force
protection are throttled.

Note: in-memory storage is per-process. For horizontally scaled deployments
the limiter should be pointed at a shared backend (e.g. Redis) through
``Limiter(storage_uri=...)``.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, headers_enabled=True)