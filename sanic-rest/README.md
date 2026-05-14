# merapy-sanic-rest

[Sanic](https://sanic.dev/) adapter for merapy's `RESTRouter` — drop-in alternative to the built-in FastAPI / Litestar adapters. Mirrors [candi-plugin/fiber-rest](https://github.com/golangid/candi-plugin/tree/master/fiber-rest).

## Install

```bash
pip install merapy-sanic-rest sanic
```

## Use

```python
from merapy_sanic_rest import SanicRESTServer

applications.append(SanicRESTServer(service, host="0.0.0.0", port=8000))
```

Module REST handlers that depend only on the `RESTRouter` Protocol work unchanged.

## Status

Implemented — `SanicRESTServer` (AppServerFactory) + `SanicRouteWrapper` (RESTRouter).
