"""OTLP exporter for kapynis tracer. Skeleton."""

from __future__ import annotations


def install_otlp_exporter(endpoint: str, *, insecure: bool = False) -> None:
    """Attach an OTLP BatchSpanProcessor to the global tracer provider.

    TODO: implement using ``opentelemetry.exporter.otlp.proto.grpc.trace_exporter``.
    """
    raise NotImplementedError


__all__ = ["install_otlp_exporter"]
