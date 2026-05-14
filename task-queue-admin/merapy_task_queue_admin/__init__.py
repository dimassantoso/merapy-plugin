"""Enhanced task-queue worker with admin UI. Skeleton."""

from __future__ import annotations


class TaskQueueAdmin:
    """Adds GraphQL admin schema + Mongo/Redis backends to the core TaskQueueWorker.

    TODO: extend ``kapynis.codebase.app.task_queue_worker`` with an admin
    GraphQL schema mounted onto the REST app; add pluggable storage backends.
    """

    name = "task-queue-admin"


__all__ = ["TaskQueueAdmin"]
