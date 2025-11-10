# Lab 8.B: Send multi-channel notifications using SNS and EventBridge rules

## Overview
Configure multi-channel notifications using Amazon SNS and Amazon EventBridge. This lab covers creating SNS topics and subscriptions (email, SMS, SQS, Lambda, HTTP), publishing messages, using message filtering, and creating EventBridge rules that forward AWS events or custom events to SNS and other targets. Includes best practices for retry, DLQ, and IAM.

## Objectives
- Create SNS topics and subscriptions (email, SMS, SQS, Lambda, HTTP)
- Configure message filtering and raw vs structured messages
- Create EventBridge rules to route AWS service events and custom events to SNS (and other targets)
- Test notifications and subscriptions end-to-end
- Implement DLQ and retry considerations
- Clean up resources

## Prerequisites
- AWS CLI v2 configured
- Email address and/or phone for SMS verification
- Permissions: sns:*, events:*, iam:PassRole (if using some targets)

---

## Variables (example)
- REGION=us-east-1
- ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
- TOPIC_NAME=lab-notifications
- SUB_EMAIL=you@example.com
- SUB_SMS=+15551234567
- SQS_QUEUE_NAME=lab-notification-queue
- LAMBDA_NAME=lab-notify-processor
- RULE_NAME=lab-event-rule

---

## Steps (CLI examples)

### 1. Create SNS topic
```bash
TOPIC_ARN=$(aws sns create-topic --name $TOPIC_NAME --region $REGION --query TopicArn --output text)
echo "Topic ARN: $TOPIC_ARN"
```

### 2. Create subscriptions
Email subscription (confirm via email link):
```bash
aws sns subscribe --topic-arn $TOPIC_ARN --protocol email --notification-endpoint $SUB_EMAIL --region $REGION
```

SMS subscription (immediate):
```bash
aws sns subscribe --topic-arn $TOPIC_ARN --protocol sms --notification-endpoint "$SUB_SMS" --region $REGION
```

SQS subscription:
```bash
# create queue
SQS_URL=$(aws sqs create-queue --queue-name $SQS_QUEUE_NAME --region $REGION --query QueueUrl --output text)
SQS_ARN=$(aws sqs get-queue-attributes --queue-url $SQS_URL --attribute-names QueueArn --region $REGION --query Attributes.QueueArn --output text)

# allow SNS to send to the queue (policy)
aws sqs set-queue-attributes --queue-url $SQS_URL --attributes \
  Policy='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"sns.amazonaws.com"},"Action":"sqs:SendMessage","Resource":"'"$SQS_ARN"'","Condition":{"ArnEquals":{"aws:SourceArn":"'"$TOPIC_ARN"'"}}}]}' \
  --region $REGION

aws sns subscribe --topic-arn $TOPIC_ARN --protocol sqs --notification-endpoint $SQS_ARN --region $REGION
```

Lambda subscription:
```bash
# create a simple lambda to receive notifications (assumes role exists)
zip -j lambda-notify.zip ./lambda_handler.py
LAMBDA_ARN=$(aws lambda create-function --function-name $LAMBDA_NAME --runtime python3.12 --handler lambda_handler.lambda_handler --zip-file fileb://lambda-notify.zip --role arn:aws:iam::$ACCOUNT_ID:role/lab-lambda-role --query FunctionArn --output text --region $REGION)
aws lambda add-permission --function-name $LAMBDA_NAME --statement-id sns-invoke --action "lambda:InvokeFunction" --principal sns.amazonaws.com --source-arn $TOPIC_ARN --region $REGION
aws sns subscribe --topic-arn $TOPIC_ARN --protocol lambda --notification-endpoint $LAMBDA_ARN --region $REGION
```

HTTP endpoint subscription (example):
```bash
aws sns subscribe --topic-arn $TOPIC_ARN --protocol http --notification-endpoint "https://example.com/endpoint" --region $REGION
```

### 3. Publish test message
Structured message with subject:
```bash
aws sns publish --topic-arn $TOPIC_ARN --subject "Lab notification" --message "Test message from lab" --region $REGION
```

Raw JSON message to preserve structure:
```bash
aws sns publish --topic-arn $TOPIC_ARN --message '{"key":"value","severity":"critical"}' --message-structure json --region $REGION
```

### 4. Message filtering
Create subscription filter policy so only messages with severity=critical are sent to a particular subscriber:
```bash
aws sns set-subscription-attributes --subscription-arn <SUB_ARN> --attribute-name FilterPolicy --attribute-value '{"severity":["critical"]}' --region $REGION
```
Publish messages with attribute:
```bash
aws sns publish --topic-arn $TOPIC_ARN --message "critical event" --message-attributes '{"severity":{"DataType":"String","StringValue":"critical"}}' --region $REGION
```

### 5. Create EventBridge rule to route AWS events to SNS
Example: forward EC2 instance state-change events to SNS:
```bash
aws events put-rule --name $RULE_NAME --event-pattern '{
  "source":["aws.ec2"],
  "detail-type":["EC2 Instance State-change Notification"],
  "detail": { "state": ["running","stopped","terminated"] }
}' --region $REGION

aws events put-targets --rule $RULE_NAME --targets "Id"="1","Arn"="$TOPIC_ARN" --region $REGION

# Grant EventBridge permission to publish to SNS
aws sns subscribe --topic-arn $TOPIC_ARN --protocol lambda --notification-endpoint $LAMBDA_ARN --region $REGION || true
aws events put-permission --statement-id allow-sns-publish --principal events.amazonaws.com --action events:PutEvents --region $REGION || true
```

Example: custom event to EventBridge and rule forwarding to SNS:
```bash
# create rule matching custom source/type
aws events put-rule --name custom-alert-rule --event-pattern '{
  "source": ["my.app"],
  "detail-type": ["alert"]
}' --region $REGION

aws events put-targets --rule custom-alert-rule --targets "Id"="1","Arn"="$TOPIC_ARN" --region $REGION

# put custom event
aws events put-events --entries '[{"Source":"my.app","DetailType":"alert","Detail":"{\"msg\":\"disk full\",\"severity\":\"high\"}"}]' --region $REGION
```

### 6. DLQ and retry considerations
- SNS retries deliveries to HTTP/HTTPS endpoints; configure HTTPS endpoints and use a subscription endpoint that returns 2xx.
- For durable processing, route notifications to SQS and process with consumers; configure SQS DLQ for unprocessed messages.
- For Lambda subscribers, configure function DLQ or use destinations to capture failures.

### 7. Monitoring and auditing
- SNS metrics: NumberOfMessagesPublished, NumberOfNotificationsDelivered, NumberOfNotificationsFailed.
- EventBridge metrics: Invocations, FailedInvocations.
- Enable CloudWatch Alarms for failures and high error rates.

Useful commands:
```bash
# SNS metrics example
aws cloudwatch get-metric-statistics --metric-name NumberOfNotificationsFailed --namespace AWS/SNS --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ) --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) --period 300 --statistics Sum --dimensions Name=TopicName,Value=$TOPIC_NAME --region $REGION
```

### 8. Cleanup
```bash
# delete event rule targets and rule
aws events remove-targets --rule $RULE_NAME --ids 1 --region $REGION
aws events delete-rule --name $RULE_NAME --region $REGION

# unsubscribe all subscriptions
for sa in $(aws sns list-subscriptions-by-topic --topic-arn $TOPIC_ARN --region $REGION --query Subscriptions[].SubscriptionArn --output text); do
  [ "$sa" != "PendingConfirmation" ] && aws sns unsubscribe --subscription-arn $sa --region $REGION || true
done

# delete topic
aws sns delete-topic --topic-arn $TOPIC_ARN --region $REGION

# delete SQS queue if created
aws sqs delete-queue --queue-url $SQS_URL --region $REGION || true

# delete lambda if created
aws lambda delete-function --function-name $LAMBDA_NAME --region $REGION || true
```

---

## Validation checklist
- [ ] SNS topic created and visible in console
- [ ] Subscriptions confirmed (email confirmation clicked, SMS received)
- [ ] SQS and Lambda subscriptions receive messages
- [ ] EventBridge rule triggers and forwards events to SNS
- [ ] Message filtering works as expected
- [ ] DLQ/retry patterns validated
- [ ] CloudWatch metrics and alarms configured

## Notes & best practices
- Use SQS as durable subscriber for downstream processing.
- Use message attributes and filtering to reduce fan-out noise.
- Use IAM least-privilege for SNS and EventBridge roles.
- Prefer HTTPS endpoints with validation and authentication.
- Monitor delivery failures and tune retry/visibility timeouts.

## Summary
This lab configures SNS and EventBridge to deliver multi-channel notifications for AWS events and custom application events. It demonstrates subscription types, filtering, routing via EventBridge, and operational practices for reliability and observability.
