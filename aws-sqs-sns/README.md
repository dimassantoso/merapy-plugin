# merapy-aws-sqs-sns

AWS SQS (broker + worker) and SNS (publisher) for merapy.

Mirrors [candi-plugin/amazonsqs](https://github.com/golangid/candi-plugin/tree/master/amazonsqs) — SQS consumer + publisher. SNS is added as a publish-only complement (fan-out to queues, Lambda, HTTP endpoints).

## Install

```bash
pip install merapy-aws-sqs-sns
# requires aioboto3
pip install aioboto3
```

## SQS — broker + worker

```python
from merapy_aws_sqs import SQSBroker, SQSWorker, WORKER_TYPE
from merapy.codebase.types import Worker

# In load_service_configs:
broker = SQSBroker(
    region="ap-southeast-1",
    # aws_access_key_id="...",      # optional — uses env/IAM role by default
    # aws_secret_access_key="...",
    # endpoint_url="http://localhost:4566",  # LocalStack
)
deps = DependencyBuilder().with_broker(WORKER_TYPE, broker).build()

# In service applications:
applications.append(SQSWorker(service, broker, max_messages=10, wait_seconds=20))
```

### Module handler

```python
from merapy.codebase.types import EventContext, Worker
from merapy_aws_sqs import WORKER_TYPE

class OrderSQSHandler:
    def mount_handlers(self, group):
        group.add("my-order-queue", self._handle)  # queue name or full URL

    async def _handle(self, ctx: EventContext) -> None:
        payload = ctx.body  # raw bytes
        print(ctx.key, payload)
```

### Publish to SQS

```python
from merapy.shared.publisher_argument import PublisherArgument

await broker.publisher().publish_message(PublisherArgument(
    topic="https://sqs.ap-southeast-1.amazonaws.com/123456789/my-queue",
    message=b'{"event":"order_created","id":"abc"}',
    headers={"content-type": "application/json"},
))
```

## SNS — publish only

SNS is fan-out only — there is no consumer side in this plugin. Subscribers (SQS queues, Lambda, HTTP) are configured in AWS.

```python
from merapy_aws_sqs import SNSPublisher
from merapy.shared.publisher_argument import PublisherArgument

sns = SNSPublisher(region="ap-southeast-1")

await sns.publish_message(PublisherArgument(
    topic="arn:aws:sns:ap-southeast-1:123456789012:my-topic",
    message=b'{"event":"order_created"}',
    headers={"content-type": "application/json"},
))
```

## LocalStack (local dev)

```python
broker = SQSBroker(region="us-east-1", endpoint_url="http://localhost:4566")
sns = SNSPublisher(region="us-east-1", endpoint_url="http://localhost:4566")
```

## Status

Implemented — SQS broker/worker/publisher and SNS publisher. Requires `aioboto3`.
