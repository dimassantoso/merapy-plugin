# merapy-circuit-breaker

Async circuit-breaker decorator for merapy. Wraps outbound calls (HTTP, DB, broker) to fail fast when a dependency is unhealthy and recover gracefully.

Mirrors [candi-plugin/circuit-breaker](https://github.com/golangid/candi-plugin/tree/master/circuit-breaker) (Go hystrix). No external dependencies — pure asyncio state machine.

## Install

```bash
pip install merapy-circuit-breaker
```

## Use

### As a decorator

```python
from merapy_circuit_breaker import circuit_breaker

@circuit_breaker(name="payment-api", failure_threshold=5, recovery_timeout=30.0)
async def charge_card(amount: float) -> dict:
    return await stripe_client.charge(amount)
```

### As a context manager

```python
from merapy_circuit_breaker import CircuitBreaker

cb = CircuitBreaker("db-write", failure_threshold=3, recovery_timeout=60.0)

async with cb:
    result = await cb.call(some_db_write())
```

### Shared named breakers

```python
from merapy_circuit_breaker import get_circuit_breaker

cb = get_circuit_breaker("external-api", failure_threshold=5)
result = await cb.call(fetch_data())
```

## States

| State | Behaviour |
|-------|-----------|
| `CLOSED` | Normal — all calls pass through |
| `OPEN` | Tripped — calls raise `CircuitBreakerOpenError` immediately |
| `HALF_OPEN` | Probing — one call allowed; success → CLOSED, failure → OPEN |

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `failure_threshold` | `5` | Consecutive failures before opening |
| `recovery_timeout` | `30.0` | Seconds in OPEN before probing |
| `expected_exceptions` | `(Exception,)` | Exception types that count as failures |

## Status

Implemented — pure asyncio, no external dependencies.
