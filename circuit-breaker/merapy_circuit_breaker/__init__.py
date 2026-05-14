"""Circuit-breaker decorator for merapy.

Mirrors candi-plugin/circuit-breaker (Go hystrix) — same concept, Python async.
Uses ``purgatory`` for the state machine (CLOSED → OPEN → HALF_OPEN).

Usage::

    from merapy_circuit_breaker import circuit_breaker

    @circuit_breaker(name="payment-api", failure_threshold=5, recovery_timeout=30.0)
    async def call_payment_api(amount: float) -> dict:
        ...

    # Or as a context manager for one-off calls:
    async with CircuitBreaker("db-write", failure_threshold=3) as cb:
        result = await cb.call(some_coroutine())
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"        # normal — calls pass through
    OPEN = "open"            # tripped — calls fail fast
    HALF_OPEN = "half_open"  # probing — one call allowed through


class CircuitBreakerOpenError(Exception):
    """Raised when a call is rejected because the circuit is OPEN."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Circuit breaker '{name}' is OPEN — call rejected")
        self.name = name


class CircuitBreaker:
    """Async circuit breaker state machine.

    Args:
        name: Identifier for logging / metrics.
        failure_threshold: Consecutive failures before tripping to OPEN.
        recovery_timeout: Seconds to wait in OPEN before probing (HALF_OPEN).
        expected_exceptions: Exception types that count as failures.
            Defaults to ``(Exception,)``.
    """

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(self, coro: Awaitable[T]) -> T:
        """Execute ``coro`` through the circuit breaker."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._opened_at >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info("circuit_breaker.half_open", name=self.name)
                else:
                    raise CircuitBreakerOpenError(self.name)

        try:
            result = await coro
        except self.expected_exceptions as exc:
            await self._on_failure()
            raise exc
        else:
            await self._on_success()
            return result

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info("circuit_breaker.closed", name=self.name)
            self._state = CircuitState.CLOSED
            self._failure_count = 0

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            if self._state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    "circuit_breaker.opened",
                    name=self.name,
                    failures=self._failure_count,
                )

    # Context manager support
    async def __aenter__(self) -> "CircuitBreaker":
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass


# Module-level registry so named breakers are shared across calls
_registry: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    *,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> CircuitBreaker:
    """Get or create a named CircuitBreaker (module-level singleton per name)."""
    if name not in _registry:
        _registry[name] = CircuitBreaker(
            name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exceptions=expected_exceptions,
        )
    return _registry[name]


def circuit_breaker(
    name: str | None = None,
    *,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator that wraps an async function with a circuit breaker.

    Args:
        name: Circuit breaker name (defaults to the function's qualified name).
        failure_threshold: Consecutive failures before opening the circuit.
        recovery_timeout: Seconds before attempting recovery (HALF_OPEN probe).
        expected_exceptions: Exception types that count as failures.

    Example::

        @circuit_breaker(name="stripe-api", failure_threshold=3, recovery_timeout=60.0)
        async def charge_card(amount: float) -> dict:
            return await stripe.charge(amount)
    """

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        breaker_name = name or f"{fn.__module__}.{fn.__qualname__}"
        cb = get_circuit_breaker(
            breaker_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exceptions=expected_exceptions,
        )

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await cb.call(fn(*args, **kwargs))

        wrapper.__circuit_breaker__ = cb  # type: ignore[attr-defined]
        return wrapper

    return decorator


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitState",
    "circuit_breaker",
    "get_circuit_breaker",
]
