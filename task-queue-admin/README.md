# kapynis-task-queue-admin

Enhanced task-queue worker with GraphQL admin UI for kapynis. Builds on the minimal `TaskQueueWorker` shipped in the framework core (poll-based, retry, persistent) and adds:

- GraphQL endpoint for listing / requeueing / cancelling jobs.
- Mongo + Redis storage backends (core ships SQL only).
- Dashboard route mounted on the existing REST server.

Mirrors candi's `task_queue_worker` plugin.

## Status

Skeleton — implementation pending.
