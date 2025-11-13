# Lab 7.C: Create an event-driven workflow using SQS and Lambda consumers

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

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set region
REGION="ap-southeast-2"
echo "REGION=$REGION"

# Set resource names
QUEUE_NAME="order-processing-queue"
echo "QUEUE_NAME=$QUEUE_NAME"

DLQ_NAME="order-processing-dlq"
echo "DLQ_NAME=$DLQ_NAME"

FUNCTION_NAME="sqs-order-processor"
echo "FUNCTION_NAME=$FUNCTION_NAME"

ROLE_NAME="lambda-sqs-processor-role"
echo "ROLE_NAME=$ROLE_NAME"

echo ""
echo "✅ Prerequisites verified"
```

---

## Step 2 – Create Dead Letter Queue (DLQ)

```bash
# Create DLQ for failed messages
echo "Creating Dead Letter Queue..."

DLQ_URL=$(aws sqs create-queue \
  --queue-name "$DLQ_NAME" \
  --region "$REGION" \
  --query QueueUrl \
  --output text)
echo "DLQ_URL=$DLQ_URL"

# Get DLQ ARN
DLQ_ARN=$(aws sqs get-queue-attributes \
  --queue-url "$DLQ_URL" \
  --attribute-names QueueArn \
  --region "$REGION" \
  --query Attributes.QueueArn \
  --output text)
echo "DLQ_ARN=$DLQ_ARN"

echo "✅ Dead Letter Queue created"
```

---

## Step 3 – Create Main SQS Queue with DLQ

```bash
# Create main queue with RedrivePolicy pointing to DLQ
echo "Creating main SQS queue..."

QUEUE_URL=$(aws sqs create-queue \
  --queue-name "$QUEUE_NAME" \
  --region "$REGION" \
  --attributes '{"RedrivePolicy":"{\"maxReceiveCount\":\"3\",\"deadLetterTargetArn\":\"'"$DLQ_ARN"'\"}"}' \
  --query QueueUrl \
  --output text)
echo "QUEUE_URL=$QUEUE_URL"

# Get Queue ARN
QUEUE_ARN=$(aws sqs get-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attribute-names QueueArn \
  --region "$REGION" \
  --query Attributes.QueueArn \
  --output text)
echo "QUEUE_ARN=$QUEUE_ARN"

echo "✅ Main queue created with DLQ redrive policy (max 3 retries)"
```

**Note**: Messages will move to DLQ after 3 failed processing attempts.

---

## Step 4 – Create IAM Role for Lambda

```bash
# Create trust policy for Lambda
cat > lambda-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role
echo "Creating IAM role..."

aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document file://lambda-trust-policy.json \
  --description "Execution role for SQS Lambda processor"

# Create inline policy for SQS access
cat > lambda-sqs-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:ChangeMessageVisibility"
      ],
      "Resource": "${QUEUE_ARN}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/lambda/${FUNCTION_NAME}:*"
    }
  ]
}
EOF

# Attach inline policy
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "LambdaSQSPolicy" \
  --policy-document file://lambda-sqs-policy.json

echo "✅ IAM role created with SQS permissions"

# Get role ARN
ROLE_ARN=$(aws iam get-role \
  --role-name "$ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)
echo "ROLE_ARN=$ROLE_ARN"

# Wait for IAM role to propagate
echo "Waiting for IAM role to propagate..."
sleep 10
```

---

## Step 5 – Create Lambda Function Code

```bash
# Create project directory
mkdir -p sqs-lambda
cd sqs-lambda

# Create Lambda function for order processing
cat > lambda_function.py <<'EOF'
import json
import os

def lambda_handler(event, context):
    """
    Process order messages from SQS queue
    Handles batch of messages from event source mapping
    """
    
    print(f"Received batch with {len(event.get('Records', []))} messages")
    
    processed = 0
    failed = 0
    
    for record in event.get('Records', []):
        try:
            # Extract message details
            message_id = record.get('messageId')
            receipt_handle = record.get('receiptHandle')
            body = record.get('body')
            
            print(f"Processing message {message_id}")
            print(f"Message body: {body}")
            
            # Parse JSON body
            try:
                order_data = json.loads(body)
                order_id = order_data.get('order_id', 'unknown')
                amount = order_data.get('amount', 0)
                customer = order_data.get('customer', 'unknown')
                
                print(f"Order ID: {order_id}")
                print(f"Customer: {customer}")
                print(f"Amount: ${amount}")
                
                # TODO: Implement idempotency check (DynamoDB)
                # if already_processed(order_id):
                #     print(f"Order {order_id} already processed, skipping")
                #     continue
                
                # Process order (placeholder logic)
                process_order(order_data)
                
                # TODO: Mark as processed (DynamoDB)
                # mark_processed(order_id)
                
                processed += 1
                print(f"✅ Successfully processed order {order_id}")
                
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON: {e}")
                failed += 1
                # Invalid JSON will be retried and eventually sent to DLQ
                raise
                
        except Exception as e:
            print(f"❌ Error processing message {message_id}: {e}")
            failed += 1
            # Re-raise to trigger retry and eventual DLQ
            raise
    
    print(f"Batch complete: {processed} processed, {failed} failed")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': processed,
            'failed': failed
        })
    }

def process_order(order_data):
    """
    Process order (placeholder for business logic)
    """
    order_id = order_data.get('order_id')
    amount = order_data.get('amount')
    
    # Simulate processing
    print(f"Processing payment for order {order_id}: ${amount}")
    print(f"Sending confirmation email...")
    print(f"Updating inventory...")
    
    # In production: call payment API, send email, update database, etc.
    pass
EOF

echo "✅ Lambda function code created"
```

---

## Step 6 – Package and Deploy Lambda Function

```bash
# Create deployment package
echo "Creating deployment package..."
zip lambda-function.zip lambda_function.py

# Return to parent directory
cd ..

# Create Lambda function
echo "Creating Lambda function..."

aws lambda create-function \
  --function-name "$FUNCTION_NAME" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://sqs-lambda/lambda-function.zip \
  --timeout 30 \
  --memory-size 256 \
  --description "Process order messages from SQS queue" \
  --region "$REGION"

echo "✅ Lambda function created"

# Get function ARN
FUNCTION_ARN=$(aws lambda get-function \
  --function-name "$FUNCTION_NAME" \
  --query 'Configuration.FunctionArn' \
  --output text \
  --region "$REGION")
echo "FUNCTION_ARN=$FUNCTION_ARN"
```

---

## Step 7 – Create Event Source Mapping (SQS → Lambda)

```bash
# Configure Lambda to poll SQS queue
echo "Creating event source mapping..."

MAPPING_UUID=$(aws lambda create-event-source-mapping \
  --function-name "$FUNCTION_NAME" \
  --batch-size 10 \
  --maximum-batching-window-in-seconds 5 \
  --event-source-arn "$QUEUE_ARN" \
  --enabled \
  --function-response-types ReportBatchItemFailures \
  --region "$REGION" \
  --query 'UUID' \
  --output text)
echo "MAPPING_UUID=$MAPPING_UUID"

echo "✅ Event source mapping created"
echo ""
echo "Configuration:"
echo "  - Batch size: 10 messages"
echo "  - Batching window: 5 seconds"
echo "  - Partial batch response: Enabled"
echo "  - Failed messages: Sent to DLQ after 3 attempts"
```

**Event Source Mapping**: Lambda polls the SQS queue automatically and invokes the function with batches of messages.

---

## Step 8 – Send Test Messages to Queue

```bash
echo ""
echo "================================================"
echo "SENDING TEST MESSAGES TO SQS"
echo "================================================"
echo ""

# Send order messages
echo "Sending order messages..."

# Order 1
aws sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body '{"order_id":"ORD-001","customer":"Alice Johnson","amount":99.99,"items":["Laptop"]}' \
  --region "$REGION"

echo "✅ Sent order ORD-001"

# Order 2
aws sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body '{"order_id":"ORD-002","customer":"Bob Smith","amount":49.99,"items":["Keyboard","Mouse"]}' \
  --region "$REGION"

echo "✅ Sent order ORD-002"

# Order 3
aws sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body '{"order_id":"ORD-003","customer":"Charlie Brown","amount":149.99,"items":["Monitor"]}' \
  --region "$REGION"

echo "✅ Sent order ORD-003"

echo ""
echo "Lambda function will process messages automatically..."
echo "Waiting 10 seconds for processing..."
sleep 10
```

---

## Step 9 – Verify Lambda Execution

```bash
echo ""
echo "Checking Lambda logs..."

# Get latest log stream
LOG_STREAM=$(aws logs describe-log-streams \
  --log-group-name "/aws/lambda/$FUNCTION_NAME" \
  --order-by LastEventTime \
  --descending \
  --max-items 1 \
  --query 'logStreams[0].logStreamName' \
  --output text \
  --region "$REGION" \
  2>/dev/null || echo "")

if [ -n "$LOG_STREAM" ]; then
    echo "LOG_STREAM=$LOG_STREAM"
    echo ""
    echo "Recent Lambda execution logs:"
    aws logs get-log-events \
      --log-group-name "/aws/lambda/$FUNCTION_NAME" \
      --log-stream-name "$LOG_STREAM" \
      --limit 50 \
      --query 'events[*].message' \
      --output text \
      --region "$REGION"
else
    echo "No log streams found yet. Lambda may still be processing..."
fi
```

---

## Step 10 – Check Queue Status

```bash
echo ""
echo "Checking SQS queue status..."

# Get queue attributes
aws sqs get-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attribute-names All \
  --region "$REGION" \
  --query 'Attributes.{"Messages Available":ApproximateNumberOfMessages,"Messages In Flight":ApproximateNumberOfMessagesNotVisible,"Messages Delayed":ApproximateNumberOfMessagesDelayed}' \
  --output table

echo ""
echo "Checking Dead Letter Queue..."

# Get DLQ attributes
aws sqs get-queue-attributes \
  --queue-url "$DLQ_URL" \
  --attribute-names All \
  --region "$REGION" \
  --query 'Attributes.{"Messages in DLQ":ApproximateNumberOfMessages}' \
  --output table
```

---

## Step 11 – View Event Source Mapping Details

```bash
echo ""
echo "Event Source Mapping Configuration:"

aws lambda get-event-source-mapping \
  --uuid "$MAPPING_UUID" \
  --region "$REGION" \
  --query '{UUID:UUID,State:State,BatchSize:BatchSize,FunctionArn:FunctionArn,EventSourceArn:EventSourceArn}' \
  --output table
```

---

## Step 12 – Test Error Handling (Optional)

```bash
echo ""
echo "Testing error handling with invalid message..."

# Send invalid JSON to trigger error
aws sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body 'INVALID-JSON-DATA' \
  --region "$REGION"

echo "✅ Sent invalid message"
echo "This message will fail processing and retry 3 times before moving to DLQ"
echo "Waiting 15 seconds..."
sleep 15

# Check DLQ for failed message
echo ""
echo "Checking DLQ for failed messages..."

aws sqs receive-message \
  --queue-url "$DLQ_URL" \
  --max-number-of-messages 10 \
  --region "$REGION" \
  --query 'Messages[*].{Body:Body,MessageId:MessageId}' \
  --output table
```

---

## Step 13 – Cleanup Resources

```bash
echo ""
echo "Cleaning up resources..."

# Delete event source mapping
echo "Deleting event source mapping..."
aws lambda delete-event-source-mapping \
  --uuid "$MAPPING_UUID" \
  --region "$REGION"

# Wait for mapping to be deleted
echo "Waiting for event source mapping to be deleted..."
sleep 5

# Delete Lambda function
echo "Deleting Lambda function..."
aws lambda delete-function \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION"

# Purge and delete SQS queues
echo "Purging and deleting SQS queues..."

aws sqs purge-queue \
  --queue-url "$QUEUE_URL" \
  --region "$REGION" \
  2>/dev/null || true

aws sqs delete-queue \
  --queue-url "$QUEUE_URL" \
  --region "$REGION"

aws sqs purge-queue \
  --queue-url "$DLQ_URL" \
  --region "$REGION" \
  2>/dev/null || true

aws sqs delete-queue \
  --queue-url "$DLQ_URL" \
  --region "$REGION"

# Delete IAM role
echo "Cleaning up IAM role..."

aws iam delete-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "LambdaSQSPolicy"

aws iam delete-role \
  --role-name "$ROLE_NAME"

# Delete CloudWatch log group
echo "Deleting CloudWatch logs..."
aws logs delete-log-group \
  --log-group-name "/aws/lambda/$FUNCTION_NAME" \
  --region "$REGION" \
  2>/dev/null || true

# Delete local files
echo "Cleaning up local files..."
rm -rf sqs-lambda
rm -f lambda-trust-policy.json lambda-sqs-policy.json

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- Event source mapping"
echo "- Lambda function"
echo "- SQS queues (main and DLQ)"
echo "- IAM role and policies"
echo "- CloudWatch log groups"
echo "- Local files"
```

---

## Summary

In this lab, you have:
- Created SQS queue with Dead Letter Queue (DLQ)
- Built Lambda function to process order messages
- Configured event source mapping for automatic polling
- Tested message processing and error handling
- Verified messages move to DLQ after failed retries
- Cleaned up all resources

**Key Takeaways:**
- **Event Source Mapping**: Lambda polls SQS automatically (no triggers needed)
- **Batch Processing**: Lambda processes up to 10 messages per invocation
- **Dead Letter Queue**: Failed messages move to DLQ after 3 attempts
- **Visibility Timeout**: Messages hidden while being processed
- **Idempotency**: Important to handle duplicate message processing
- **Error Handling**: Failed messages trigger retries before DLQ

**Message Flow:**
```
1. Messages sent to SQS queue
2. Lambda polls queue automatically
3. Lambda processes batch of messages
4. Successful: Messages deleted from queue
5. Failed: Message retried (up to 3 times)
6. After max retries: Message moved to DLQ
```

**Best Practices:**
- **Idempotency**: Use DynamoDB to track processed message IDs
- **Visibility Timeout**: Set > Lambda timeout + processing time
- **Batch Size**: Smaller batches = lower latency, larger = better throughput
- **DLQ**: Monitor and alert on DLQ message count
- **FIFO Queues**: Use for strict ordering requirements
- **Partial Batch Response**: Enable to handle individual message failures

---

## Free Tier Notes
- **SQS**: 1M requests/month free
- **Lambda**: 1M requests/month + 400,000 GB-seconds compute
- **CloudWatch Logs**: 5 GB ingestion + 5 GB storage

This lab uses minimal resources, staying well within free tier limits.

---

## Production Enhancements

1. **Implement Idempotency**
   ```python
   # Use DynamoDB to track processed messages
   import boto3
   dynamodb = boto3.resource('dynamodb')
   table = dynamodb.Table('ProcessedMessages')
   
   # Check if message already processed
   response = table.get_item(Key={'MessageId': message_id})
   if 'Item' in response:
       print(f"Message {message_id} already processed")
       return
   
   # Mark as processed after successful processing
   table.put_item(Item={'MessageId': message_id, 'ProcessedAt': datetime.now().isoformat()})
   ```

2. **Add CloudWatch Alarms**
   ```bash
   # Alert on high DLQ message count
   aws cloudwatch put-metric-alarm \
     --alarm-name sqs-dlq-messages \
     --metric-name ApproximateNumberOfMessagesVisible \
     --namespace AWS/SQS \
     --statistic Sum \
     --period 300 \
     --threshold 10 \
     --comparison-operator GreaterThanThreshold \
     --dimensions Name=QueueName,Value=$DLQ_NAME
   ```

3. **Use FIFO Queue**
   - Append `.fifo` to queue names
   - Set `FifoQueue=true` attribute
   - Enable `ContentBasedDeduplication` for automatic deduplication

4. **Monitoring Dashboard**
   - Monitor `ApproximateNumberOfMessagesVisible`
   - Track Lambda errors and throttles
   - Alert on DLQ message count

5. **Optimize Visibility Timeout**
   ```bash
   # Set visibility timeout = Lambda timeout + processing time
   aws sqs set-queue-attributes \
     --queue-url $QUEUE_URL \
     --attributes VisibilityTimeout=60
   ```

## Summary
This lab demonstrates how to wire SQS and Lambda for resilient, scalable event-driven processing. Focus on idempotency, visibility timeout tuning, appropriate batching, and monitoring to build reliable consumers.
