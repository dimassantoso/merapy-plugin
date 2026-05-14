# merapy-tracer-otlp

OTLP (OpenTelemetry Protocol) span exporter wiring for merapy's tracer.

The framework's `merapy.tracer.init_tracer()` only attaches a console exporter by default; this plugin adds an OTLP exporter so spans can be shipped to Jaeger / Tempo / a vendor backend.

## Status

Skeleton — implementation pending.
