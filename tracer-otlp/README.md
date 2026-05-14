# kapynis-tracer-otlp

OTLP (OpenTelemetry Protocol) span exporter wiring for kapynis's tracer.

The framework's `kapynis.tracer.init_tracer()` only attaches a console exporter by default; this plugin adds an OTLP exporter so spans can be shipped to Jaeger / Tempo / a vendor backend.

## Status

Skeleton — implementation pending.
