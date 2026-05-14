"""Circuit-breaker for merapy. Skeleton."""

from __future__ import annotations

from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


def circuit_breaker(
    *,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorate an async function with a circuit breaker. TODO: implement."""

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        raise NotImplementedError

    return decorator


__all__ = ["circuit_breaker"]
