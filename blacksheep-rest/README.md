# merapy-blacksheep-rest

[BlackSheep](https://www.neoteroi.dev/blacksheep/) adapter for merapy's `RESTRouter` — drop-in alternative to the built-in FastAPI / Litestar adapters. Mirrors [candi-plugin/echo-rest](https://github.com/golangid/candi-plugin/tree/master/echo-rest).

## Install

```bash
pip install merapy-blacksheep-rest blacksheep uvicorn
```

## Use

```python
from merapy_blacksheep_rest import BlackSheepRESTServer

applications.append(BlackSheepRESTServer(service))
```

Module REST handlers that depend only on the `RESTRouter` Protocol work unchanged. Runs under uvicorn (same as FastAPI/Litestar adapters).

## Status

Implemented — `BlackSheepRESTServer` (AppServerFactory) + `BlackSheepRouteWrapper` (RESTRouter).
