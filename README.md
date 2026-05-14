# merapy-plugin

Pluggable extensions for [merapy](https://github.com/dimassantoso/merapy) — the Python clean-architecture microservice framework. Mirrors [candi-plugin](https://github.com/golangid/candi-plugin) for Go candi.

Each subdirectory is an independent Python package that depends on `merapy` and implements one of its Protocols (`AppServerFactory`, `Broker`, `SQLDatabase`, etc.) — drop the package into your service's dependencies, register it during boot, and you get an alternative implementation without touching framework code.

## Plugins

| Directory | PyPI name | candi-plugin counterpart | What it provides | Status |
|---|---|---|---|---|
| [aws-sqs/](aws-sqs/) | `merapy-aws-sqs-sns` | `amazonsqs` | AWS SQS `Broker` + worker + SNS publisher | ✅ Implemented |
| [circuit-breaker/](circuit-breaker/) | `merapy-circuit-breaker` | `circuit-breaker` | Async circuit-breaker decorator | ✅ Implemented |
| [oracledb/](oracledb/) | `merapy-oracledb` | `oracledb-adaptor` | Oracle `SQLDatabase` via SQLAlchemy async | ✅ Implemented |
| [tracer-otlp/](tracer-otlp/) | `merapy-tracer-otlp` | `tracer/sentrytracer` | OTLP gRPC/HTTP span exporter | ✅ Implemented |
| [p2p/](p2p/) | `merapy-p2p` | `p2p` | Raw TCP/UDP `AppServerFactory` (asyncio) | ✅ Implemented |
| [gcp-pubsub/](gcp-pubsub/) | `merapy-gcp-pubsub` | `gcppubsub` | GCP Pub/Sub `Broker` + subscriber worker | 🚧 Skeleton |
| [stomp-broker/](stomp-broker/) | `merapy-stomp-broker` | `stomp-broker` | STOMP `Broker` + worker (ActiveMQ, RabbitMQ STOMP) | 🚧 Skeleton |
| [sanic-rest/](sanic-rest/) | `merapy-sanic-rest` | `fiber-rest` | Sanic `RESTRouter` + `AppServerFactory` | 🚧 Skeleton |
| [blacksheep-rest/](blacksheep-rest/) | `merapy-blacksheep-rest` | `echo-rest` | BlackSheep `RESTRouter` + `AppServerFactory` | 🚧 Skeleton |
| [arangodb/](arangodb/) | `merapy-arangodb` | `arangodb-adapter` | ArangoDB document/graph database adapter | 🚧 Skeleton |
| [task-queue-admin/](task-queue-admin/) | `merapy-task-queue-admin` | `task-queue-worker` | Mongo/Redis backends for task queue worker | 🚧 Skeleton |

> **Note on SNS:** candi-plugin only has SQS. `merapy-aws-sqs-sns` adds SNS as a publish-only complement — SNS fan-out to SQS queues, Lambda, HTTP endpoints is configured in AWS; this plugin handles the publish side.

> **Note on p2p:** candi's p2p uses raw TCP/UDP (`net.Listen`), not libp2p. This port uses `asyncio.start_server` / `create_datagram_endpoint` — no external dependencies.

> **Note on tracer:** candi's tracer plugin is Sentry. merapy uses OTLP instead — vendor-neutral, works with Jaeger, Tempo, Honeycomb, Datadog, etc.

## Install

```bash
pip install merapy-aws-sqs-sns      # SQS + SNS
pip install merapy-circuit-breaker  # circuit breaker
pip install merapy-oracledb         # Oracle DB
pip install merapy-tracer-otlp      # OTLP exporter
pip install merapy-p2p              # TCP/UDP P2P
```

## Quick examples

### AWS SQS + SNS

```python
from merapy_aws_sqs import SQSBroker, SQSWorker, SNSPublisher, WORKER_TYPE

broker = SQSBroker(region="ap-southeast-1")
deps = DependencyBuilder().with_broker(WORKER_TYPE, broker).build()
applications.append(SQSWorker(service, broker))

# Publish to SNS:
sns = SNSPublisher(region="ap-southeast-1")
await sns.publish_message(PublisherArgument(topic="arn:aws:sns:...", message=b"..."))
```

### Circuit breaker

```python
from merapy_circuit_breaker import circuit_breaker

@circuit_breaker(name="payment-api", failure_threshold=5, recovery_timeout=30.0)
async def charge_card(amount: float) -> dict: ...
```

### Oracle DB

```python
from merapy_oracledb import init_oracle_database

db = init_oracle_database("oracle+oracledb://user:pass@host:1521/?service_name=XEPDB1")
deps = DependencyBuilder().with_sql_db(db).build()
```

### OTLP tracer

```python
from merapy.tracer import init_tracer
from merapy_tracer_otlp import install_otlp_grpc_exporter

init_tracer("my-service")
install_otlp_grpc_exporter("http://jaeger:4317")
```

### P2P TCP

```python
from merapy_p2p import P2PTCPServer
applications.append(P2PTCPServer(service, port=9100))
```

## Author a new plugin

```
my-plugin/
├── pyproject.toml           # depends on merapy
├── README.md
└── merapy_my_plugin/
    └── __init__.py          # implements a merapy Protocol
```

Pick a Protocol (`AppServerFactory`, `Broker`, `SQLDatabase`, etc.) and provide a class that satisfies it structurally. Register during `load_service_configs` and you're done.

## License

MIT — see `LICENSE`.
