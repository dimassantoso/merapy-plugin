# AGENTS.md — merapy-plugin workspace context

## What this is

**merapy-plugin** — pluggable extensions for [merapy](https://github.com/dimassantoso/merapy).
Each subdirectory is an independent Python package implementing a merapy Protocol.

## Key paths

| What | Where |
|------|-------|
| AWS SQS + SNS | `aws-sqs-sns/merapy_aws_sqs/` |
| GCP Pub/Sub | `gcp-pubsub/merapy_gcp_pubsub/` |
| STOMP broker | `stomp-broker/merapy_stomp/` |
| P2P TCP/UDP | `p2p/merapy_p2p/` |
| Sanic REST | `sanic-rest/merapy_sanic_rest/` |
| BlackSheep REST | `blacksheep-rest/merapy_blacksheep_rest/` |
| Oracle DB | `oracledb/merapy_oracledb/` |
| ArangoDB | `arangodb/merapy_arangodb/` |
| Circuit breaker | `circuit-breaker/merapy_circuit_breaker/` |
| OTLP tracer | `tracer-otlp/merapy_tracer_otlp/` |
| Task queue admin | `task-queue-admin/merapy_task_queue_admin/` |

## Plugin → merapy Protocol mapping

| Plugin | Protocol | Registration |
|--------|----------|-------------|
| `aws-sqs-sns` | `Broker` | `DependencyBuilder.with_broker(Worker.AMAZONSQS, broker)` |
| `gcp-pubsub` | `Broker` | `DependencyBuilder.with_broker(Worker.GCP_PUBSUB, broker)` |
| `stomp-broker` | `Broker` | `DependencyBuilder.with_broker(Worker.STOMP, broker)` |
| `p2p` | `AppServerFactory` | `applications.append(P2PTCPServer(service, port=9100))` |
| `sanic-rest` | `AppServerFactory` + `RESTRouter` | `applications.append(SanicRESTServer(service))` |
| `blacksheep-rest` | `AppServerFactory` + `RESTRouter` | `applications.append(BlackSheepRESTServer(service))` |
| `oracledb` | `SQLDatabase` | `DependencyBuilder.with_sql_db(init_oracle_database(...))` |
| `arangodb` | custom `ArangoDatabase` | `DependencyBuilder.with_extended("arangodb", init_arangodb(...))` |
| `circuit-breaker` | standalone decorator | `@circuit_breaker(name="...", failure_threshold=5)` |
| `tracer-otlp` | OTel exporter | `install_otlp_grpc_exporter("http://jaeger:4317")` |
| `task-queue-admin` | `AppServerFactory` | `applications.append(TaskQueueAdminWorker(service, store=MongoJobStore(...)))` |

## Worker / Server enum values (defined in merapy core)

```python
from merapy.codebase.types import Worker, Server

Worker.AMAZONSQS  # "amazonsqs_broker"
Worker.GCP_PUBSUB # "gcp_pubsub"
Worker.STOMP      # "stomp_broker"
Server.P2P_TCP    # "p2p_tcp"
Server.P2P_UDP    # "p2p_udp"
```

**Never use raw string casts** like `Worker("amazonsqs_broker")` — `StrEnum` raises `ValueError` for unknown values. Always use the enum member.

## Critical rules

1. **Worker enum** — use `Worker.AMAZONSQS` / `Worker.GCP_PUBSUB` / `Worker.STOMP`, not raw strings.
2. **Server enum** — use `Server.P2P_TCP` / `Server.P2P_UDP`, not raw strings.
3. **SQLAlchemy 2.x** — use `async_sessionmaker(engine)`, not `sessionmaker(bind=engine)`.
4. **BlackSheep router** — store `_RouteSpec` tuples, flush via `app.router.add_route()`. Never iterate the router object.
5. **Sanic blueprints** — use `Blueprint.group()` for nesting. Never call `.blueprint()` on a Blueprint.
6. **aioboto3 client** — reuse a single client per `serve()` lifetime (open once, not per message).
7. **TaskQueueAdminWorker** — set `self._session_factory = None` so the dashboard shows task names without DB queries.
8. **ArangoDB** — registered via `with_extended("arangodb", db)`, not `with_sql_db()`.
9. **STOMP broker** — requires explicit `await broker.connect()` before `publisher()` is available (done automatically by `STOMPWorker.serve()`).
10. **tracer-otlp** — call `init_tracer()` first, then `install_otlp_grpc_exporter()`.

## Common pitfalls

| Problem | Fix |
|---------|-----|
| `ValueError: 'amazonsqs_broker' is not a valid Worker` | Use `Worker.AMAZONSQS` |
| `AttributeError: 'Blueprint' object has no attribute 'blueprint'` | Use `Blueprint.group()` in sanic-rest |
| `SADeprecationWarning: sessionmaker(bind=...)` | Use `async_sessionmaker(engine)` in oracledb |
| `RuntimeError: STOMPBroker not connected` | `STOMPWorker.serve()` calls `connect()` automatically; don't call `publisher()` before `serve()` |
| `RuntimeError: No TracerProvider found` | Call `init_tracer()` before `install_otlp_grpc_exporter()` |
| ArangoDB `health()` fails | `python-arango` async `ping()` requires `AsyncDatabase` wrapper — use `client.db(...).begin_async_execution()` |
