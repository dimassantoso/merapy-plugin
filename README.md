# kapynis-plugin

Pluggable extensions for [kapynis](https://github.com/santosodb/kapynis) — the Python clean-architecture microservice framework. Mirrors [candi-plugin](https://github.com/golangid/candi-plugin) for Go candi.

Each subdirectory is an independent Python package that depends on `kapynis` and implements one of its Protocols (`AppServerFactory`, `Broker`, `SQLDatabase`, etc.) — drop the package into your service's dependencies, register it during boot, and you get an alternative implementation of an interface without touching framework code.

## Plugins

| Directory | candi-plugin counterpart | What it provides |
|---|---|---|
| [sanic-rest/](sanic-rest/) | `fiber-rest` | Sanic adapter for `RESTRouter` |
| [blacksheep-rest/](blacksheep-rest/) | (none — BlackSheep is Python-only) | BlackSheep adapter for `RESTRouter` |
| [tracer-otlp/](tracer-otlp/) | `tracer` | OTLP span exporter for the OpenTelemetry tracer |
| [arangodb/](arangodb/) | `arangodb-adapter` | ArangoDB document / graph database adapter |
| [gcp-pubsub/](gcp-pubsub/) | `gcppubsub` | GCP Pub/Sub `Broker` + subscriber worker |
| [aws-sqs/](aws-sqs/) | `amazonsqs` | AWS SQS `Broker` + worker |
| [stomp-broker/](stomp-broker/) | `stomp-broker` | STOMP protocol `Broker` + worker |
| [circuit-breaker/](circuit-breaker/) | `circuit-breaker` | Circuit-breaker middleware / decorator |
| [oracledb/](oracledb/) | `oracledb-adaptor` | Oracle Database `SQLDatabase` adapter |
| [p2p/](p2p/) | `p2p` | libp2p peer-to-peer `AppServerFactory` |
| [task-queue-admin/](task-queue-admin/) | `task-queue-worker` | Enhanced TaskQueue with GraphQL admin UI + Mongo/Redis backends |

All plugins are **skeleton** at this stage — pyproject + README + a stub class showing the integration point. Implementation is a follow-up; the goal of this repo is to mirror candi-plugin's layout so contributions can flow in one plugin at a time.

## Install one

```bash
pip install ./sanic-rest          # local / editable
# once published to PyPI:
pip install kapynis-sanic-rest
```

## Use one

```python
from merapy_sanic_rest import SanicRESTServer

applications.append(SanicRESTServer(service=service))
```

The kapynis framework only sees the Protocol it expects — the concrete plugin slots in transparently.

## Author a new plugin

Minimal layout:

```
my-plugin/
├── pyproject.toml           # depends on `kapynis`
├── README.md
└── merapy_my_plugin/
    └── __init__.py          # exports an adapter implementing a kapynis Protocol
```

Pick one of the kapynis Protocols (`kapynis.codebase.factory.app_factory.AppServerFactory`, `kapynis.codebase.interfaces.broker.Broker`, etc.) and provide a class that satisfies it structurally. Register the instance during your service's `load_service_configs` and you're done.

## License

MIT — see `LICENSE`.
