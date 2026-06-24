"""
Network Resilience — wrappers, interceptors, and utilities that make all
network-dependent EVO tools robust against transient failures.

Design principles
-----------------
1. **Every network call goes through a retry wrapper** with exponential backoff,
   jitter, and configurable max attempts (default 3).
2. **Connection pooling** avoids per-request TCP/TLS handshake overhead.
3. **Circuit-breaker** state is tracked per *service endpoint* so that a
   persistently failing backend is not hammered.
4. **Graceful degradation** — when a backend fails after all retries, fall
   back to a degraded alternative result instead of crashing.
5. **Timeouts are explicit and configurable** from ``config.py`` defaults.
"""

from __future__ import annotations

import random
import time
import logging
from typing import Any, Callable

from mind.rate_limiter import RetryWithBackoff, RateLimiter

logger = logging.getLogger("evo.network_resilience")

# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

_CIRCUIT_STATE: dict[str, dict] = {}
_CIRCUIT_LOCK: Any = None

try:
    import threading
    _CIRCUIT_LOCK = threading.Lock()
except ImportError:
    _CIRCUIT_LOCK = None


class CircuitBreakerState:
    """Per-endpoint circuit breaker state machine.

    States:
      CLOSED   — normal operation, requests pass through.
      OPEN     — requests are rejected immediately for ``recovery_timeout``.
      HALF_OPEN — one probe request is allowed; success reverts to CLOSED,
                  failure reopens the circuit.
    """

    __slots__ = ("failure_count", "failure_threshold", "recovery_timeout",
                 "last_failure_time", "state")

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = 0.0
        self.state = "CLOSED"

    def record_success(self) -> None:
        self.failure_count = 0
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        # HALF_OPEN — allow one probe
        return True


def _circuit_breaker(endpoint: str) -> CircuitBreakerState:
    """Get or create a circuit breaker for *endpoint*."""
    if _CIRCUIT_LOCK:
        with _CIRCUIT_LOCK:
            if endpoint not in _CIRCUIT_STATE:
                _CIRCUIT_STATE[endpoint] = CircuitBreakerState()
            return _CIRCUIT_STATE[endpoint]
    if endpoint not in _CIRCUIT_STATE:
        _CIRCUIT_STATE[endpoint] = CircuitBreakerState()
    return _CIRCUIT_STATE[endpoint]


# ---------------------------------------------------------------------------
# Connection pool (urllib)
# ---------------------------------------------------------------------------

_URLLIB_POOL: dict[str, Any] = {}


def _get_opener_for_base(base_url: str, timeout: int = 15) -> Any:
    """Return a cached ``urllib.request.OpenerDirector`` with connection reuse."""
    import urllib.request
    key = (base_url, timeout)
    if key in _URLLIB_POOL:
        return _URLLIB_POOL[key]
    opener = urllib.request.build_opener()
    opener.addheaders = [
        ("User-Agent", "evo-ai/1.0"),
        ("Connection", "keep-alive"),
        ("Accept", "*/*"),
    ]
    _URLLIB_POOL[key] = opener
    return opener


# ---------------------------------------------------------------------------
# Retry execution with circuit breaker
# ---------------------------------------------------------------------------

def resilient_call(
    operation: Callable,
    *args: Any,
    endpoint: str = "generic",
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_multiplier: float = 2.0,
    should_retry: Callable[[Exception], bool] | None = None,
    on_retry: Callable[[Exception, int, float], Any] | None = None,
    circuit_breaker_threshold: int = 0,
    circuit_breaker_recovery: float = 30.0,
    fallback: Callable[[], Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Execute *operation* with retry, backoff, jitter, optional circuit
    breaker, and optional fallback."""
    cb: CircuitBreakerState | None = None
    if circuit_breaker_threshold > 0:
        cb = _circuit_breaker(endpoint)
        cb.failure_threshold = circuit_breaker_threshold
        cb.recovery_timeout = circuit_breaker_recovery

    # Circuit breaker check (fast-fail)
    if cb is not None and not cb.allow_request():
        msg = f"Circuit breaker OPEN for '{endpoint}' — request rejected."
        logger.warning(msg)
        if fallback is not None:
            logger.info("Invoking fallback for '%s'", endpoint)
            return fallback()
        raise RuntimeError(msg)

    effective_should_retry: Callable[[Exception], bool] | None
    if should_retry is not None:
        effective_should_retry = should_retry
    else:
        effective_should_retry = RetryWithBackoff.is_retryable_error

    def _wrapped_on_retry(exc: Exception, attempt: int, delay: float) -> None:
        if cb is not None:
            cb.record_failure()
        if on_retry is not None:
            on_retry(exc, attempt, delay)

    try:
        result = RetryWithBackoff.execute(
            operation,
            *args,
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            backoff_multiplier=backoff_multiplier,
            should_retry=effective_should_retry,
            on_retry=_wrapped_on_retry,
            logger=logger,
            **kwargs,
        )
        if cb is not None:
            cb.record_success()
        return result
    except Exception as exc:
        if cb is not None:
            cb.record_failure()
        if fallback is not None:
            logger.warning("All %d retries exhausted for '%s' — invoking fallback.",
                           max_retries, endpoint)
            return fallback()
        raise


# ---------------------------------------------------------------------------
# Convenience: create a resilient callable
# ---------------------------------------------------------------------------

def resilient(
    operation: Callable,
    *,
    endpoint: str = "generic",
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_multiplier: float = 2.0,
    circuit_breaker_threshold: int = 0,
    circuit_breaker_recovery: float = 30.0,
    fallback: Callable | None = None,
) -> Callable:
    """Return a wrapper that turns *operation* into a resilient callable."""
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return resilient_call(
            operation, *args,
            endpoint=endpoint,
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            backoff_multiplier=backoff_multiplier,
            circuit_breaker_threshold=circuit_breaker_threshold,
            circuit_breaker_recovery=circuit_breaker_recovery,
            fallback=fallback,
            **kwargs,
        )
    return wrapper


# ---------------------------------------------------------------------------
# Urllib request with retry + connection reuse
# ---------------------------------------------------------------------------

def urlopen_retry(
    url: str,
    *,
    timeout: int = 15,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    max_retries: int = 3,
    base_delay: float = 1.0,
    endpoint: str = "generic_urlopen",
) -> Any:
    """Open *url* with connection pooling, timeout, and retry."""
    import urllib.request
    import urllib.error

    base_url = url[:url.index("/", 8)] if url.startswith("https://") else url
    opener = _get_opener_for_base(base_url, timeout)

    def _do_request() -> Any:
        req = urllib.request.Request(url, data=data, headers=headers or {},
                                     method=method)
        return opener.open(req, timeout=timeout)

    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, urllib.error.HTTPError):
            return exc.code in (429, 500, 502, 503, 504)
        if isinstance(exc, (urllib.error.URLError, ConnectionError,
                            TimeoutError, OSError)):
            return True
        return RetryWithBackoff.is_retryable_error(exc)

    return resilient_call(
        _do_request,
        endpoint=endpoint,
        max_retries=max_retries,
        base_delay=base_delay,
        should_retry=_is_retryable,
    )


# ---------------------------------------------------------------------------
# Health check helpers
# ---------------------------------------------------------------------------

def check_endpoint_health(
    url: str,
    timeout: float = 5.0,
    expected_status: int = 200,
) -> dict:
    """Quick health-check for an HTTP endpoint (no retry)."""
    import urllib.request
    import urllib.error
    start = time.monotonic()
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = (time.monotonic() - start) * 1000
            return {
                "alive": resp.status == expected_status,
                "latency_ms": round(latency, 1),
                "status": resp.status,
            }
    except (urllib.error.URLError, urllib.error.HTTPError,
            ConnectionError, TimeoutError, OSError) as exc:
        latency = (time.monotonic() - start) * 1000
        return {
            "alive": False,
            "latency_ms": round(latency, 1),
            "status": getattr(exc, "code", 0),
        }


# ---------------------------------------------------------------------------
# DNS caching (lightweight)
# ---------------------------------------------------------------------------

_DNS_CACHE: dict[str, str] = {}
_DNS_CACHE_TTL: float = 300.0


def _cached_resolve(hostname: str) -> str | None:
    """Resolve *hostname* to an IP, caching the result for 5 minutes."""
    import socket
    now = time.monotonic()
    cached = _DNS_CACHE.get(hostname)
    if cached is not None:
        parts = cached.split("|")
        if len(parts) == 2 and (now - float(parts[1])) < _DNS_CACHE_TTL:
            return parts[0]
    try:
        ip = socket.gethostbyname(hostname)
        _DNS_CACHE[hostname] = f"{ip}|{now}"
        return ip
    except socket.gaierror:
        _DNS_CACHE[hostname] = f"__FAIL__|{now}"
        return None


# ---------------------------------------------------------------------------
# Pre-configured instances
# ---------------------------------------------------------------------------

github_rate_limiter = RateLimiter(max_tokens=10, refill_rate=2, min_delay=0.25)
