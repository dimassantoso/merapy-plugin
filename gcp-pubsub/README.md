# merapy-gcp-pubsub

GCP Pub/Sub broker + subscriber worker for merapy. Mirrors [candi-plugin/gcppubsub](https://github.com/golangid/candi-plugin/tree/master/gcppubsub).

## Install

```bash
pip install merapy-gcp-pubsub google-cloud-pubsub
```

## Use

```python
from merapy_gcp_pubsub import GCPPubSubBroker, GCPPubSubWorker, WORKER_TYPE

broker = GCPPubSubBroker(
    project="my-gcp-project",
    credentials_file="/path/to/service-account.json",  # optional, uses ADC if omitted
)
deps = DependencyBuilder().with_broker(WORKER_TYPE, broker).build()
applications.append(GCPPubSubWorker(service, broker, subscriber_id="my-service"))
```

### Module handler

```python
from merapy.codebase.types import EventContext
from merapy_gcp_pubsub import WORKER_TYPE

class OrderPubSubHandler:
    def mount_handlers(self, group):
        group.add("orders-topic", self._handle)  # topic name

    async def _handle(self, ctx: EventContext) -> None:
        print(ctx.key, ctx.body)
```

### Publish

```python
from merapy.shared.publisher_argument import PublisherArgument

await broker.publisher().publish_message(PublisherArgument(
    topic="projects/my-project/topics/orders-topic",
    message=b'{"event":"order_created"}',
))
```

Topics and subscriptions are **auto-created** if they don't exist. Subscription ID = `{subscriber_id}_{topic_name}`.

## Status

Implemented — pull-based subscriber, auto topic/subscription creation, auto-ack.
