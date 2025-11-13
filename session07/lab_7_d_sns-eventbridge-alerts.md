# Lab 7.D: Monitor EC2 with SNS Email Alerts and EventBridge

## Overview
This lab demonstrates event-driven alerting using Amazon SNS and EventBridge. You'll create an SNS topic with email subscription, configure EventBridge to monitor EC2 instance state changes, and receive email notifications when instances start, stop, or terminate. This is a fundamental pattern for infrastructure monitoring and alerting.

---

## Objectives
- Create SNS topic for notifications
- Subscribe email address to receive alerts
- Configure EventBridge rule to monitor EC2 state changes
- Launch EC2 instance to trigger alerts
- Receive email notifications for state changes
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Valid email address for notifications
- IAM permissions for SNS, EventBridge, EC2, and IAM
- Basic understanding of event-driven architecture

---

## Architecture

```
EC2 State Change → EventBridge Rule → SNS Topic → Email Notification
(Start/Stop/Terminate)   (Captures)     (Publishes)   (You receive)
```

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
TOPIC_NAME="ec2-state-alerts"
echo "TOPIC_NAME=$TOPIC_NAME"

RULE_NAME="ec2-state-change-rule"
echo "RULE_NAME=$RULE_NAME"

INSTANCE_NAME="test-monitored-instance"
echo "INSTANCE_NAME=$INSTANCE_NAME"

# Set your email address (CHANGE THIS!)
EMAIL_ADDRESS="your-email@example.com"
echo "EMAIL_ADDRESS=$EMAIL_ADDRESS"

echo ""
echo "⚠️  IMPORTANT: Change EMAIL_ADDRESS to your real email!"
echo ""
echo "✅ Prerequisites verified"
```

---

## Step 2 – Create SNS Topic

```bash
# Create SNS topic for EC2 alerts
echo "Creating SNS topic..."

TOPIC_ARN=$(aws sns create-topic \
  --name "$TOPIC_NAME" \
  --region "$REGION" \
  --query TopicArn \
  --output text)
echo "TOPIC_ARN=$TOPIC_ARN"

echo "✅ SNS topic created"
```

---

## Step 3 – Subscribe Email to SNS Topic

```bash
# Subscribe email address to receive notifications
echo "Subscribing email to SNS topic..."

SUBSCRIPTION_ARN=$(aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol email \
  --notification-endpoint "$EMAIL_ADDRESS" \
  --region "$REGION" \
  --query SubscriptionArn \
  --output text)
echo "SUBSCRIPTION_ARN=$SUBSCRIPTION_ARN"

echo ""
echo "✅ Email subscription created"
echo ""
echo "================================================"
echo "⚠️  ACTION REQUIRED"
echo "================================================"
echo "Check your email inbox: $EMAIL_ADDRESS"
echo "Subject: 'AWS Notification - Subscription Confirmation'"
echo "Click the 'Confirm subscription' link in the email"
echo ""
echo "Press Enter after confirming your email subscription..."
read
```

---

## Step 4 – Verify Email Subscription

```bash
# Check subscription status
echo "Verifying email subscription..."

aws sns list-subscriptions-by-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION" \
  --query 'Subscriptions[*].{Endpoint:Endpoint,Protocol:Protocol,Status:SubscriptionArn}' \
  --output table

echo ""
echo "If Status shows 'PendingConfirmation', check your email!"
echo "If Status shows an ARN, you're subscribed! ✅"
```

---

## Step 5 – Test SNS with Manual Message

```bash
echo ""
echo "Sending test email notification..."

# Send test message to verify email works
aws sns publish \
  --topic-arn "$TOPIC_ARN" \
  --subject "Test: SNS Email Notification" \
  --message "This is a test message from your SNS topic. If you receive this, email notifications are working correctly!" \
  --region "$REGION"

echo ""
echo "✅ Test message sent"
echo "Check your email for the test notification"
echo ""
echo "Press Enter to continue..."
read
```

---

## Step 6 – Create EventBridge Rule for EC2 State Changes

```bash
# Create EventBridge rule to capture EC2 state changes
echo "Creating EventBridge rule..."

aws events put-rule \
  --name "$RULE_NAME" \
  --description "Monitor EC2 instance state changes (running, stopped, terminated)" \
  --event-pattern '{
    "source": ["aws.ec2"],
    "detail-type": ["EC2 Instance State-change Notification"],
    "detail": {
      "state": ["pending", "running", "stopping", "stopped", "shutting-down", "terminated"]
    }
  }' \
  --state ENABLED \
  --region "$REGION"

echo "✅ EventBridge rule created"

# Get rule ARN
RULE_ARN=$(aws events describe-rule \
  --name "$RULE_NAME" \
  --query 'Arn' \
  --output text \
  --region "$REGION")
echo "RULE_ARN=$RULE_ARN"
```

---

## Step 7 – Add SNS Topic as EventBridge Target

```bash
# Configure EventBridge to send events to SNS topic
echo "Adding SNS as target for EventBridge rule..."

aws events put-targets \
  --rule "$RULE_NAME" \
  --targets "Id"="1","Arn"="$TOPIC_ARN" \
  --region "$REGION"

echo "✅ SNS topic added as EventBridge target"
```

---

## Step 8 – Grant EventBridge Permission to Publish to SNS

```bash
# Allow EventBridge to publish messages to SNS topic
echo "Granting EventBridge permission to publish to SNS..."

aws sns set-topic-attributes \
  --topic-arn "$TOPIC_ARN" \
  --attribute-name Policy \
  --attribute-value '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Service": "events.amazonaws.com"
        },
        "Action": "SNS:Publish",
        "Resource": "'"$TOPIC_ARN"'"
      }
    ]
  }' \
  --region "$REGION"

echo "✅ Permission granted"
```

---

## Step 9 – Get Default VPC and Subnet

```bash
# Get default VPC for EC2 instance
echo "Getting default VPC..."

DEFAULT_VPC=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region "$REGION")
echo "DEFAULT_VPC=$DEFAULT_VPC"

# Get default subnet
DEFAULT_SUBNET=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$DEFAULT_VPC" \
  --query 'Subnets[0].SubnetId' \
  --output text \
  --region "$REGION")
echo "DEFAULT_SUBNET=$DEFAULT_SUBNET"

# Get latest Amazon Linux 2023 AMI
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text \
  --region "$REGION")
echo "AMI_ID=$AMI_ID"
```

---

## Step 10 – Launch EC2 Instance (Trigger Alert)

```bash
echo ""
echo "================================================"
echo "LAUNCHING EC2 INSTANCE"
echo "================================================"
echo ""
echo "This will trigger EventBridge → SNS → Email notification!"
echo ""

# Launch t2.micro EC2 instance
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --subnet-id "$DEFAULT_SUBNET" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
  --region "$REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)
echo "INSTANCE_ID=$INSTANCE_ID"

echo ""
echo "✅ EC2 instance launched: $INSTANCE_ID"
echo ""
echo "EventBridge will capture state changes:"
echo "  1. pending → running (2 email notifications)"
echo ""
echo "Check your email for EC2 state change notifications!"
echo ""
echo "Waiting 30 seconds for instance to start..."
sleep 30
```

---

## Step 11 – Check Instance Status

```bash
# Verify instance is running
echo "Checking instance status..."

aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].{InstanceId:InstanceId,State:State.Name,Type:InstanceType,LaunchTime:LaunchTime}' \
  --output table

echo ""
echo "Instance should be 'running'"
echo "You should have received email notifications for:"
echo "  - Instance pending"
echo "  - Instance running"
```

---

## Step 12 – Stop Instance (Trigger Stop Alert)

```bash
echo ""
echo "================================================"
echo "STOPPING EC2 INSTANCE"
echo "================================================"
echo ""

# Stop EC2 instance
aws ec2 stop-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

echo "✅ Stop command sent"
echo ""
echo "EventBridge will capture:"
echo "  - Instance stopping"
echo "  - Instance stopped"
echo ""
echo "Check your email for stop notifications!"
echo ""
echo "Waiting 30 seconds for instance to stop..."
sleep 30
```

---

## Step 13 – Check Stopped Status

```bash
# Verify instance is stopped
echo "Checking instance status..."

aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].{InstanceId:InstanceId,State:State.Name}' \
  --output table

echo ""
echo "Instance should be 'stopped'"
echo "You should have received email notifications for:"
echo "  - Instance stopping"
echo "  - Instance stopped"
```

---

## Step 14 – Terminate Instance (Trigger Terminate Alert)

```bash
echo ""
echo "================================================"
echo "TERMINATING EC2 INSTANCE"
echo "================================================"
echo ""

# Terminate EC2 instance
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

echo "✅ Terminate command sent"
echo ""
echo "EventBridge will capture:"
echo "  - Instance shutting-down"
echo "  - Instance terminated"
echo ""
echo "Check your email for termination notifications!"
echo ""
echo "Waiting 30 seconds for termination..."
sleep 30
```

---

## Step 15 – Verify All Email Notifications

```bash
echo ""
echo "================================================"
echo "EMAIL NOTIFICATIONS SUMMARY"
echo "================================================"
echo ""
echo "You should have received 6 email notifications:"
echo ""
echo "1. ✉️  Test message (Step 5)"
echo "2. ✉️  Instance pending"
echo "3. ✉️  Instance running"
echo "4. ✉️  Instance stopping"
echo "5. ✉️  Instance stopped"
echo "6. ✉️  Instance shutting-down"
echo "7. ✉️  Instance terminated"
echo ""
echo "Each email contains JSON with instance details:"
echo "  - Instance ID"
echo "  - State change (old → new)"
echo "  - Timestamp"
echo "  - Region"
```

---

## Step 16 – View EventBridge Metrics

```bash
echo ""
echo "Checking EventBridge rule invocations..."

# Get EventBridge rule details
aws events describe-rule \
  --name "$RULE_NAME" \
  --region "$REGION" \
  --query '{Name:Name,State:State,EventPattern:EventPattern}' \
  --output table

echo ""
echo "EventBridge rule has been invoked ~6 times (EC2 state changes)"
```

---

## Step 17 – View SNS Topic Details

```bash
echo ""
echo "SNS Topic Details:"

aws sns get-topic-attributes \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION" \
  --query 'Attributes.{TopicArn:TopicArn,DisplayName:DisplayName,SubscriptionsConfirmed:SubscriptionsConfirmed}' \
  --output table

echo ""
echo "Subscriptions:"
aws sns list-subscriptions-by-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION" \
  --query 'Subscriptions[*].{Endpoint:Endpoint,Protocol:Protocol}' \
  --output table
```

---

## Step 18 – Cleanup Resources

```bash
echo ""
echo "Cleaning up resources..."

# Verify instance is terminated (cleanup only if somehow still exists)
echo "Checking if instance needs cleanup..."
INSTANCE_STATE=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].State.Name' \
  --output text \
  2>/dev/null || echo "terminated")

if [ "$INSTANCE_STATE" != "terminated" ]; then
    echo "Terminating instance..."
    aws ec2 terminate-instances \
      --instance-ids "$INSTANCE_ID" \
      --region "$REGION"
    echo "Waiting for termination..."
    aws ec2 wait instance-terminated \
      --instance-ids "$INSTANCE_ID" \
      --region "$REGION"
fi

# Remove EventBridge target
echo "Removing EventBridge target..."
aws events remove-targets \
  --rule "$RULE_NAME" \
  --ids "1" \
  --region "$REGION"

# Delete EventBridge rule
echo "Deleting EventBridge rule..."
aws events delete-rule \
  --name "$RULE_NAME" \
  --region "$REGION"

# Unsubscribe email
echo "Unsubscribing email..."
aws sns list-subscriptions-by-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION" \
  --query 'Subscriptions[*].SubscriptionArn' \
  --output text | while read SUB_ARN; do
    if [ "$SUB_ARN" != "PendingConfirmation" ] && [ -n "$SUB_ARN" ]; then
        aws sns unsubscribe \
          --subscription-arn "$SUB_ARN" \
          --region "$REGION"
    fi
done

# Delete SNS topic
echo "Deleting SNS topic..."
aws sns delete-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION"

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- EC2 instance terminated"
echo "- EventBridge rule deleted"
echo "- Email unsubscribed"
echo "- SNS topic deleted"
```

---

## Summary

In this lab, you have:
- Created SNS topic for email notifications
- Subscribed and confirmed email address
- Configured EventBridge rule to monitor EC2 state changes
- Launched EC2 instance and received email alerts
- Stopped instance and received email alerts
- Terminated instance and received email alerts
- Cleaned up all resources

**Key Takeaways:**
- **SNS**: Pub/Sub messaging service for notifications
- **EventBridge**: Event bus that captures AWS service events
- **Email Notifications**: Simple, reliable alerting mechanism
- **Event-Driven**: No polling needed, instant notifications
- **EC2 State Changes**: Capture pending, running, stopping, stopped, shutting-down, terminated
- **Fan-out Pattern**: One event → multiple subscribers (we used one email, could add more)

**Event Flow:**
```
1. EC2 instance state changes
2. EventBridge captures state-change event
3. EventBridge rule matches event pattern
4. EventBridge publishes to SNS topic
5. SNS sends email to all subscribers
6. You receive email notification
```

**Email Notification Example:**
```json
{
  "version": "0",
  "id": "12345678-1234-1234-1234-123456789012",
  "detail-type": "EC2 Instance State-change Notification",
  "source": "aws.ec2",
  "account": "123456789012",
  "time": "2025-11-13T10:30:00Z",
  "region": "ap-southeast-2",
  "resources": [
    "arn:aws:ec2:ap-southeast-2:123456789012:instance/i-1234567890abcdef0"
  ],
  "detail": {
    "instance-id": "i-1234567890abcdef0",
    "state": "running"
  }
}
```

---

## Best Practices

**SNS Email:**
- Always confirm subscriptions before testing
- Use meaningful subject lines
- Consider email filters for high-volume alerts
- Test with manual message before live events

**EventBridge:**
- Use specific event patterns (avoid wildcards)
- Test rules with small scope first
- Monitor rule invocations and failures
- Use multiple targets for redundancy

**EC2 Monitoring:**
- Monitor state changes for auto-recovery
- Alert on unexpected terminations
- Track instance lifecycle for compliance
- Combine with CloudWatch alarms for comprehensive monitoring

**Security:**
- Limit SNS topic access with IAM policies
- Use HTTPS for webhook endpoints
- Validate event sources in Lambda functions
- Enable CloudTrail for audit logging

**Cost Optimization:**
- SNS email is essentially free (1,000 free/month)
- EventBridge events are free (14M free/month)
- Use message filtering to reduce noise
- Consider SQS for buffering high-volume events

---

## Free Tier Notes
- **SNS**: 1,000 email notifications/month free
- **EventBridge**: 14 million events/month free (first year)
- **EC2**: t2.micro 750 hours/month free (first year)

This lab uses minimal resources, staying well within free tier limits.

---

## Production Enhancements

1. **Add Multiple Email Subscribers**
   ```bash
   # Subscribe team members
   aws sns subscribe \
     --topic-arn $TOPIC_ARN \
     --protocol email \
     --notification-endpoint team@example.com
   ```

2. **Add Message Filtering**
   ```bash
   # Only alert on terminated instances
   aws sns set-subscription-attributes \
     --subscription-arn $SUBSCRIPTION_ARN \
     --attribute-name FilterPolicy \
     --attribute-value '{"detail":{"state":["terminated"]}}'
   ```

3. **Add Lambda for Custom Processing**
   ```python
   # Lambda to process events before sending
   def lambda_handler(event, context):
       instance_id = event['detail']['instance-id']
       state = event['detail']['state']
       
       # Custom logic: only alert if production instance
       if 'prod' in get_instance_tags(instance_id):
           send_custom_alert(instance_id, state)
   ```

4. **Add CloudWatch Dashboard**
   ```bash
   # Create dashboard for EC2 monitoring
   aws cloudwatch put-dashboard \
     --dashboard-name EC2-Monitoring \
     --dashboard-body file://dashboard.json
   ```

5. **Integrate with PagerDuty/Slack**
   - Add Lambda subscriber to format messages
   - Call PagerDuty/Slack API from Lambda
   - Rich notifications with instance details

6. **Add DLQ for Failed Deliveries**
   ```bash
   # Create DLQ for failed email deliveries
   aws sqs create-queue --queue-name sns-email-dlq
   
   # Configure SNS to use DLQ
   aws sns set-subscription-attributes \
     --subscription-arn $SUBSCRIPTION_ARN \
     --attribute-name RedrivePolicy \
     --attribute-value '{"deadLetterTargetArn":"arn:aws:sqs:region:account:sns-email-dlq"}'
   ```

---

## Troubleshooting

**Email not received:**
- Check spam/junk folder
- Verify subscription is confirmed (not PendingConfirmation)
- Test with manual `sns publish` command
- Check SNS topic policy allows EventBridge

**EventBridge not triggering:**
- Verify rule is ENABLED
- Check event pattern matches EC2 events
- Verify target is configured correctly
- Check EventBridge has permission to publish to SNS

**EC2 instance issues:**
- Check default VPC exists
- Verify AMI is available in region
- Check IAM permissions for EC2 operations
- Review EC2 console for error messages

**Cleanup errors:**
- Wait for instance to fully terminate
- Check subscription status before unsubscribing
- Verify EventBridge targets removed before deleting rule
