# merapy-tracer-otlp

OTLP (OpenTelemetry Protocol) span exporter for merapy's tracer. Ships spans to Jaeger, Grafana Tempo, Honeycomb, Datadog, or any OTLP-compatible backend.

Mirrors [candi-plugin/tracer/sentrytracer](https://github.com/golangid/candi-plugin/tree/master/tracer/sentrytracer) — different backend (OTLP instead of Sentry) but same concept: a separately installable exporter wired into the framework tracer.

## Install

```bash
pip install merapy-tracer-otlp
# includes both gRPC and HTTP exporters
```

## Use

Call **after** `merapy.tracer.init_tracer()`:

```python
from merapy.tracer import init_tracer
from merapy_tracer_otlp import install_otlp_grpc_exporter, install_otlp_http_exporter

# In load_service_configs or main.py:
init_tracer("my-service")

# gRPC (default port 4317 — Jaeger, Tempo, OTel Collector):
install_otlp_grpc_exporter("http://jaeger:4317")

# HTTP/protobuf (default port 4318):
install_otlp_http_exporter("http://tempo:4318/v1/traces")
```

## LocalStack / dev

```python
install_otlp_grpc_exporter("http://localhost:4317", insecure=True)
```

## Status

Implemented — gRPC and HTTP exporters, both using `BatchSpanProcessor`.
