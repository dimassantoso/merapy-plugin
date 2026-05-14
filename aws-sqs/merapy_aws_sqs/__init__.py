"""AWS SQS broker + worker for merapy. Skeleton."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from merapy.codebase.factory.service_factory import ServiceFactory


class SQSBroker:
    name = "aws-sqs"

    async def close(self) -> None:
        raise NotImplementedError


class SQSWorker:
    name = "aws-sqs-worker"

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service

    async def serve(self) -> None:
        raise NotImplementedError

    async def shutdown(self) -> None:
        raise NotImplementedError


__all__ = ["SQSBroker", "SQSWorker"]
