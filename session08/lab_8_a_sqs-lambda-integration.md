# Lab 8.A: Create an event-driven workflow using SQS and Lambda consumers

## Overview
Build a resilient event-driven workflow using Amazon SQS queues and AWS Lambda consumers. This lab covers standard and FIFO queues, Dead-Letter Queues (DLQs), Lambda event source mappings, batch processing, visibility timeout tuning, idempotency, retries/DLQs, monitoring, and cleanup.

## Objectives
- Create SQS queues (standard and DLQ)
- Create a Lambda consumer with least-privilege IAM role
- Configure event source mapping (batch size, bisect on error)
- Implement idempotent processing and error handling patterns
- Validate retry and DLQ behavior
- Monitor with CloudWatch and clean up resources

## Prerequisites
- AWS CLI v2 configured
- Python 3.12 or Node.js for Lambda code
- jq (optional) for JSON parsing
- IAM permissions to create SQS, Lambda, IAM resources

---

## Variables (replace as needed)
- REGION=us-east-1
- QUEUE_NAME=lab-queue
- DLQ_NAME=lab-queue-dlq
- LAMBDA_NAME=lab-sqs-consumer
- ROLE_NAME=lab-lambda-sqs-role

---

## Steps (CLI examples)

### 1. Create DLQ and main queue
```bash
# create DLQ
DLQ_URL=$(aws sqs create-queue --queue-name $DLQ_NAME --region $REGION --query QueueUrl --output text)
DLQ_ARN=$(aws sqs get-queue-attributes --queue-url $DLQ_URL --attribute-names QueueArn --region $REGION --query Attributes.QueueArn --output text)

# create main queue with RedrivePolicy to DLQ (standard queue example)
aws sqs create-queue --queue-name $QUEUE_NAME --region $REGION --attributes \
  RedrivePolicy='{"maxReceiveCount":"5","deadLetterTargetArn":"'"$DLQ_ARN"'"}'
QUEUE_URL=$(aws sqs get-queue-url --queue-name $QUEUE_NAME --region $REGION --query QueueUrl --output text)
QUEUE_ARN=$(aws sqs get-queue-attributes --queue-url $QUEUE_URL --attribute-names QueueArn --region $REGION --query Attributes.QueueArn --output text)
```

Notes:
- For FIFO queue append .fifo to name and set FifoQueue=true and ContentBasedDeduplication as needed.

### 2. Create Lambda execution role (least-privilege)
```bash
cat > trust.json <<'EOF'
{
  "Version":"2012-10-17",
  "Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]
}
EOF

aws iam create-role --role-name $ROLE_NAME --assume-role-policy-document file://trust.json --region $REGION || true

cat > policy.json <<'EOF'
{
  "Version":"2012-10-17",
  "Statement":[
    {"Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],"Resource":"arn:aws:logs:*:*:*"},
    {"Effect":"Allow","Action":["sqs:ChangeMessageVisibility","sqs:DeleteMessage","sqs:ReceiveMessage","sqs:GetQueueAttributes"],"Resource":"'"$QUEUE_ARN"'"}
  ]
}
EOF

aws iam put-role-policy --role-name $ROLE_NAME --policy-name LambdaSqsPolicy --policy-document file://policy.json --region $REGION
aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole --region $REGION
ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --region $REGION --query Role.Arn --output text)
```

### 3. Create Lambda function (Python example)
Create simple idempotent consumer that uses messageId to avoid reprocessing (store processed IDs in DynamoDB for production; here it logs and deletes message).

```bash
mkdir -p session08 && cat > session08/consumer.py <<'PY'
import json
import boto3
import os

def lambda_handler(event, context):
    for record in event.get('Records', []):
        body = record.get('body')
        message_id = record.get('messageId')
        print(f"Processing message {message_id}: {body}")
        # TODO: implement idempotent store/check (e.g., DynamoDB)
    return {"status": "ok"}
PY

zip -j consumer.zip session08/consumer.py

aws lambda create-function --function-name $LAMBDA_NAME \
  --runtime python3.12 --handler consumer.lambda_handler \
  --zip-file fileb://consumer.zip --role $ROLE_ARN --timeout 30 --memory-size 256 --region $REGION
```

### 4. Grant SQS permission to invoke Lambda (not required for event source mapping) and create event source mapping
Event source mapping polls SQS; Lambda does not need Lambda add-permission for SQS mapping.

```bash
aws lambda create-event-source-mapping \
  --function-name $LAMBDA_NAME \
  --batch-size 10 \
  --maximum-batching-window-in-seconds 10 \
  --event-source-arn $QUEUE_ARN \
  --enabled \
  --bisect-on-function-error \
  --maximum-record-age-in-seconds 3600 \
  --maximum-retry-attempts 2 \
  --region $REGION
```

Settings explained:
- batch-size: number of messages per Lambda invocation
- bisect-on-function-error: splits batch on failure to isolate bad messages
- maximum-retry-attempts + DLQ: controls retries before message returns to queue and hits DLQ via RedrivePolicy

### 5. Test end-to-end
Send test messages:
```bash
aws sqs send-message --queue-url $QUEUE_URL --message-body '{"order":"123","amount":9.99}' --region $REGION
aws sqs send-message --queue-url $QUEUE_URL --message-body '{"order":"124","amount":19.99}' --region $REGION
```

Inspect Lambda logs:
```bash
aws logs describe-log-streams --log-group-name /aws/lambda/$LAMBDA_NAME --region $REGION
aws logs filter-log-events --log-group-name /aws/lambda/$LAMBDA_NAME --limit 50 --region $REGION
```

Simulate failures:
- Throw an exception in lambda_handler to observe retries and DLQ delivery after maxReceiveCount.

### 6. Best practices & patterns
- Use idempotency (DynamoDB conditional writes or dedupe keys).
- Tune visibility timeout > Lambda timeout + processing time.
- Use small batch sizes for latency-sensitive processing.
- Use SQS FIFO for strict ordering and exactly-once semantics (with deduplication).
- Use SQS -> Lambda via SQS event source mapping for at-least-once delivery; implement idempotency to avoid duplicate side-effects.
- For very high throughput, consider SQS -> Kinesis or SQS -> ECS consumers.

### 7. Monitoring & Alerting
- CloudWatch metrics: ApproximateNumberOfMessagesVisible, ApproximateNumberOfMessagesNotVisible, NumberOfMessagesDeleted.
- Lambda metrics: Invocations, Duration, Errors, Throttles.
- Create CloudWatch alarm on ApproximateNumberOfMessagesVisible to alert on processing backlog.

Example alarm (backlog alert):
```bash
aws cloudwatch put-metric-alarm --alarm-name sqs-backlog-$QUEUE_NAME \
  --metric-name ApproximateNumberOfMessagesVisible --namespace AWS/SQS \
  --statistic Sum --period 300 --threshold 100 --comparison-operator GreaterThanThreshold \
  --dimensions Name=QueueName,Value=$QUEUE_NAME --evaluation-periods 1 --region $REGION
```

### 8. Cleanup
```bash
aws lambda update-function-configuration --function-name $LAMBDA_NAME --environment Variables={} --region $REGION || true
aws lambda delete-function --function-name $LAMBDA_NAME --region $REGION || true
aws sqs delete-queue --queue-url $QUEUE_URL --region $REGION || true
aws sqs delete-queue --queue-url $DLQ_URL --region $REGION || true
aws iam delete-role-policy --role-name $ROLE_NAME --policy-name LambdaSqsPolicy --region $REGION || true
aws iam detach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole --region $REGION || true
aws iam delete-role --role-name $ROLE_NAME --region $REGION || true
rm -f consumer.zip session08/consumer.py
```

## Validation checklist
- [ ] SQS main queue and DLQ created
- [ ] Lambda consumer registered and running
- [ ] Event source mapping configured with appropriate batch and retry settings
- [ ] Messages processed and visible in Lambda logs
- [ ] Failed messages move to DLQ after configured attempts
- [ ] Monitoring and alerts configured

## Summary
This lab demonstrates how to wire SQS and Lambda for resilient, scalable event-driven processing. Focus on idempotency, visibility timeout tuning, appropriate batching, and monitoring to build reliable consumers.
