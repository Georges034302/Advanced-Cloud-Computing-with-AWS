# Lab 7.C: Create an event-driven workflow using SQS and Lambda consumers
<img width="1424" height="765" alt="IMG" src="https://github.com/user-attachments/assets/e610a0e2-185b-40cf-bf40-ec7e84fb80c5" />

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
# Get AWS account ID and set region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="ap-southeast-2"

# Set resource names
QUEUE_NAME="order-processing-queue"
DLQ_NAME="order-processing-dlq"
FUNCTION_NAME="sqs-order-processor"
ROLE_NAME="lambda-sqs-processor-role"

echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "REGION=$REGION"
```

---

## Step 2 – Create Dead Letter Queue (DLQ)

```bash
# Create Dead Letter Queue for failed messages after max retries
DLQ_URL=$(aws sqs create-queue \
  --queue-name "$DLQ_NAME" \
  --region "$REGION" \
  --query QueueUrl \
  --output text)

# Get DLQ ARN (needed for main queue's redrive policy)
DLQ_ARN=$(aws sqs get-queue-attributes \
  --queue-url "$DLQ_URL" \
  --attribute-names QueueArn \
  --region "$REGION" \
  --query Attributes.QueueArn \
  --output text)

echo "DLQ_URL=$DLQ_URL"
echo "DLQ_ARN=$DLQ_ARN"
```

---

## Step 3 – Create Main SQS Queue with DLQ

```bash
# Create main SQS queue with RedrivePolicy (sends to DLQ after 3 failed attempts)
QUEUE_URL=$(aws sqs create-queue \
  --queue-name "$QUEUE_NAME" \
  --region "$REGION" \
  --attributes '{"RedrivePolicy":"{\"maxReceiveCount\":\"3\",\"deadLetterTargetArn\":\"'"$DLQ_ARN"'\"}"}' \
  --query QueueUrl \
  --output text)

# Get Queue ARN (needed for Lambda event source mapping)
QUEUE_ARN=$(aws sqs get-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attribute-names QueueArn \
  --region "$REGION" \
  --query Attributes.QueueArn \
  --output text)

echo "QUEUE_URL=$QUEUE_URL"
echo "QUEUE_ARN=$QUEUE_ARN"
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

# Create IAM role for Lambda service
aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document file://lambda-trust-policy.json \
  --description "Execution role for SQS Lambda processor"

# Create permissions policy for SQS access and CloudWatch logs
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

# Attach inline policy to role
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "LambdaSQSPolicy" \
  --policy-document file://lambda-sqs-policy.json

# Get role ARN for Lambda function creation
ROLE_ARN=$(aws iam get-role \
  --role-name "$ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)
echo "ROLE_ARN=$ROLE_ARN"

# Wait for IAM role to propagate globally
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
```

---

## Step 6 – Package and Deploy Lambda Function

```bash
# Create deployment package with Python code
zip lambda-function.zip lambda_function.py
cd ..

# Create Lambda function with Python 3.12 runtime
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

# Get function ARN for event source mapping
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
# Configure Lambda to automatically poll SQS queue and process messages in batches
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
```

**Event Source Mapping**: Lambda polls the SQS queue automatically and invokes the function with batches of messages.

---

## Step 8 – Send Test Messages to Queue

```bash
# Send test order messages to SQS queue (Lambda will process automatically)
aws sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body '{"order_id":"ORD-001","customer":"Alice Johnson","amount":99.99,"items":["Laptop"]}' \
  --region "$REGION"

aws sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body '{"order_id":"ORD-002","customer":"Bob Smith","amount":49.99,"items":["Keyboard","Mouse"]}' \
  --region "$REGION"

aws sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body '{"order_id":"ORD-003","customer":"Charlie Brown","amount":149.99,"items":["Monitor"]}' \
  --region "$REGION"

# Wait for Lambda to poll and process messages
sleep 10
```

---

## Step 9 – Verify Lambda Execution

```bash
# Get latest log stream from Lambda execution
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
    # Display recent Lambda execution logs showing message processing
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
# Check main queue status (should be empty after processing)
aws sqs get-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attribute-names All \
  --region "$REGION" \
  --query 'Attributes.{"Messages Available":ApproximateNumberOfMessages,"Messages In Flight":ApproximateNumberOfMessagesNotVisible,"Messages Delayed":ApproximateNumberOfMessagesDelayed}' \
  --output table

# Check Dead Letter Queue for failed messages
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
# View event source mapping configuration details
aws lambda get-event-source-mapping \
  --uuid "$MAPPING_UUID" \
  --region "$REGION" \
  --query '{UUID:UUID,State:State,BatchSize:BatchSize,FunctionArn:FunctionArn,EventSourceArn:EventSourceArn}' \
  --output table
```

---

## Step 12 – Test Error Handling (Optional)

```bash
# Send invalid JSON message to test error handling and DLQ behavior
aws sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body 'INVALID-JSON-DATA' \
  --region "$REGION"

# Wait for Lambda to retry 3 times and move message to DLQ
sleep 15

# Check DLQ for the failed message
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
# Delete event source mapping (stops Lambda from polling SQS)
aws lambda delete-event-source-mapping \
  --uuid "$MAPPING_UUID" \
  --region "$REGION"

# Wait for mapping deletion to complete
sleep 5

# Delete Lambda function
aws lambda delete-function \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION"

# Purge and delete main SQS queue
aws sqs purge-queue \
  --queue-url "$QUEUE_URL" \
  --region "$REGION" \
  2>/dev/null || true

aws sqs delete-queue \
  --queue-url "$QUEUE_URL" \
  --region "$REGION"

# Purge and delete Dead Letter Queue
aws sqs purge-queue \
  --queue-url "$DLQ_URL" \
  --region "$REGION" \
  2>/dev/null || true

aws sqs delete-queue \
  --queue-url "$DLQ_URL" \
  --region "$REGION"

# Delete IAM role policy and role
aws iam delete-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "LambdaSQSPolicy"

aws iam delete-role \
  --role-name "$ROLE_NAME"

# Delete CloudWatch log group
aws logs delete-log-group \
  --log-group-name "/aws/lambda/$FUNCTION_NAME" \
  --region "$REGION" \
  2>/dev/null || true

# Delete local files
rm -rf sqs-lambda
rm -f lambda-trust-policy.json lambda-sqs-policy.json
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
