# merapy-sanic-rest

[Sanic](https://sanic.dev/) adapter for merapy's `RESTRouter` — drop-in alternative to the built-in FastAPI / Litestar adapters.

## Why

Sanic is one of the fastest async Python web frameworks. Use this adapter when raw throughput matters more than FastAPI's automatic OpenAPI / Pydantic integration.

## Install

```bash
pip install merapy-sanic-rest
```

## Use

Replace the REST framework selection at service boot:

```python
from merapy_sanic_rest import SanicRESTServer

applications.append(
    SanicRESTServer(
        service=service,
        host="0.0.0.0",
        port=8000,
    )
)
```

The same module REST handlers (those that depend only on the `RESTRouter` Protocol) work unchanged.

## Status

Skeleton only — implementation is a TODO. PRs welcome.
