"""OTLP span exporter for merapy's OpenTelemetry tracer.

Attaches an OTLP gRPC or HTTP exporter to the global TracerProvider that
``merapy.tracer.init_tracer()`` sets up. Call this *after* ``init_tracer()``.

Mirrors candi-plugin/tracer/sentrytracer — different backend (OTLP instead of
Sentry) but same concept: a separately installable exporter wired into the
framework's tracer.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def install_otlp_grpc_exporter(
    endpoint: str = "http://localhost:4317",
    *,
    insecure: bool = True,
    headers: dict[str, str] | None = None,
    timeout: int = 10,
) -> None:
    """Attach an OTLP gRPC BatchSpanProcessor to the global TracerProvider.

    Call after ``merapy.tracer.init_tracer(service_name)``::

        from merapy.tracer import init_tracer
        from merapy_tracer_otlp import install_otlp_grpc_exporter

        init_tracer("my-service")
        install_otlp_grpc_exporter("http://jaeger:4317")

    Args:
        endpoint: OTLP gRPC collector endpoint (default: localhost:4317).
        insecure: Skip TLS verification (default True for local dev).
        headers: Optional metadata headers sent with every export request.
        timeout: Export timeout in seconds.
    """
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        insecure=insecure,
        headers=headers or {},
        timeout=timeout,
    )
    _attach(exporter)


def install_otlp_http_exporter(
    endpoint: str = "http://localhost:4318/v1/traces",
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 10,
) -> None:
    """Attach an OTLP HTTP/protobuf BatchSpanProcessor to the global TracerProvider.

    Args:
        endpoint: OTLP HTTP collector endpoint (default: localhost:4318/v1/traces).
        headers: Optional HTTP headers sent with every export request.
        timeout: Export timeout in seconds.
    """
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers=headers or {},
        timeout=timeout,
    )
    _attach(exporter)


def _attach(exporter: object) -> None:
    """Add a BatchSpanProcessor to the current global TracerProvider.

    Raises ``RuntimeError`` if ``init_tracer()`` has not been called yet.
    """
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        raise RuntimeError(
            "No TracerProvider found. Call merapy.tracer.init_tracer() before "
            "installing an OTLP exporter."
        )
    provider.add_span_processor(BatchSpanProcessor(exporter))  # type: ignore[arg-type]


__all__ = ["install_otlp_grpc_exporter", "install_otlp_http_exporter"]
