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
# Get AWS account ID and set region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="ap-southeast-2"

# Set resource names
TOPIC_NAME="ec2-state-alerts"
RULE_NAME="ec2-state-change-rule"
INSTANCE_NAME="test-monitored-instance"

# IMPORTANT: Change this to your real email address!
EMAIL_ADDRESS="your-email@example.com"

echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "REGION=$REGION"
echo "EMAIL_ADDRESS=$EMAIL_ADDRESS"
```

---

## Step 2 – Create SNS Topic

```bash
# Create SNS topic for EC2 state change alerts
TOPIC_ARN=$(aws sns create-topic \
  --name "$TOPIC_NAME" \
  --region "$REGION" \
  --query TopicArn \
  --output text)
echo "TOPIC_ARN=$TOPIC_ARN"
```

---

## Step 3 – Subscribe Email to SNS Topic

```bash
# Subscribe email address to SNS topic for notifications
SUBSCRIPTION_ARN=$(aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol email \
  --notification-endpoint "$EMAIL_ADDRESS" \
  --region "$REGION" \
  --query SubscriptionArn \
  --output text)
echo "SUBSCRIPTION_ARN=$SUBSCRIPTION_ARN"

# ACTION REQUIRED: Check email and confirm subscription
echo "⚠️  Check $EMAIL_ADDRESS for confirmation email and click the link"
read -p "Press Enter after confirming subscription..."
```

---

## Step 4 – Verify Email Subscription

```bash
# Verify email subscription is confirmed (Status should show ARN, not PendingConfirmation)
aws sns list-subscriptions-by-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION" \
  --query 'Subscriptions[*].{Endpoint:Endpoint,Protocol:Protocol,Status:SubscriptionArn}' \
  --output table
```

---

## Step 5 – Test SNS with Manual Message

```bash
# Send test message to verify email notifications work
aws sns publish \
  --topic-arn "$TOPIC_ARN" \
  --subject "Test: SNS Email Notification" \
  --message "This is a test message from your SNS topic. If you receive this, email notifications are working correctly!" \
  --region "$REGION"

echo "Test message sent - check your email"
read -p "Press Enter to continue..."
```

---

## Step 6 – Create EventBridge Rule for EC2 State Changes

```bash
# Create EventBridge rule to monitor EC2 state changes (pending, running, stopping, stopped, shutting-down, terminated)
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

# Get rule ARN for reference
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
# Configure EventBridge rule to publish events to SNS topic
aws events put-targets \
  --rule "$RULE_NAME" \
  --targets "Id"="1","Arn"="$TOPIC_ARN" \
  --region "$REGION"
```

---

## Step 8 – Grant EventBridge Permission to Publish to SNS

```bash
# Grant EventBridge service permission to publish to SNS topic
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
```

---

## Step 9 – Get Default VPC and Subnet

```bash
# Get default VPC for launching EC2 instance
DEFAULT_VPC=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region "$REGION")

# Get default subnet from VPC
DEFAULT_SUBNET=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$DEFAULT_VPC" \
  --query 'Subnets[0].SubnetId' \
  --output text \
  --region "$REGION")

# Get latest Amazon Linux 2023 AMI ID
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text \
  --region "$REGION")

echo "DEFAULT_VPC=$DEFAULT_VPC"
echo "DEFAULT_SUBNET=$DEFAULT_SUBNET"
echo "AMI_ID=$AMI_ID"
```

---

## Step 10 – Launch EC2 Instance (Trigger Alert)

```bash
# Launch t2.micro EC2 instance (triggers EventBridge → SNS → Email)
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --subnet-id "$DEFAULT_SUBNET" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
  --region "$REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)
echo "INSTANCE_ID=$INSTANCE_ID"

echo "Instance launching - check email for state change notifications (pending, running)"
sleep 30
```

---

## Step 11 – Check Instance Status

```bash
# Verify instance is running (should have received 2 emails: pending, running)
aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].{InstanceId:InstanceId,State:State.Name,Type:InstanceType,LaunchTime:LaunchTime}' \
  --output table
```

---

## Step 12 – Stop Instance (Trigger Stop Alert)

```bash
# Stop EC2 instance (triggers email notifications for stopping, stopped)
aws ec2 stop-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

echo "Instance stopping - check email for notifications"
sleep 30
```

---

## Step 13 – Check Stopped Status

```bash
# Verify instance is stopped (should have received 2 more emails: stopping, stopped)
aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].{InstanceId:InstanceId,State:State.Name}' \
  --output table
```

---

## Step 14 – Terminate Instance (Trigger Terminate Alert)

```bash
# Terminate EC2 instance (triggers email notifications for shutting-down, terminated)
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

echo "Instance terminating - check email for final notifications"
sleep 30
```

---

## Step 15 – Verify All Email Notifications

```bash
# Summary: You should have received 7 email notifications
echo "Expected emails: Test + pending + running + stopping + stopped + shutting-down + terminated"
```

---

## Step 16 – View EventBridge Metrics

```bash
# View EventBridge rule details (rule was invoked ~6 times for EC2 state changes)
aws events describe-rule \
  --name "$RULE_NAME" \
  --region "$REGION" \
  --query '{Name:Name,State:State,EventPattern:EventPattern}' \
  --output table
```

---

## Step 17 – View SNS Topic Details

```bash
# View SNS topic details and subscriptions
aws sns get-topic-attributes \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION" \
  --query 'Attributes.{TopicArn:TopicArn,DisplayName:DisplayName,SubscriptionsConfirmed:SubscriptionsConfirmed}' \
  --output table

aws sns list-subscriptions-by-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION" \
  --query 'Subscriptions[*].{Endpoint:Endpoint,Protocol:Protocol}' \
  --output table
```

---

## Step 18 – Cleanup Resources

```bash
# Verify instance is terminated (terminate if still running)
INSTANCE_STATE=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].State.Name' \
  --output text \
  2>/dev/null || echo "terminated")

if [ "$INSTANCE_STATE" != "terminated" ]; then
    aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "$REGION"
    aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID" --region "$REGION"
fi

# Remove EventBridge target
aws events remove-targets \
  --rule "$RULE_NAME" \
  --ids "1" \
  --region "$REGION"

# Delete EventBridge rule
aws events delete-rule \
  --name "$RULE_NAME" \
  --region "$REGION"

# Unsubscribe email from SNS topic
aws sns list-subscriptions-by-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION" \
  --query 'Subscriptions[*].SubscriptionArn' \
  --output text | while read SUB_ARN; do
    if [ "$SUB_ARN" != "PendingConfirmation" ] && [ -n "$SUB_ARN" ]; then
        aws sns unsubscribe --subscription-arn "$SUB_ARN" --region "$REGION"
    fi
done

# Delete SNS topic
aws sns delete-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION"

echo "Cleanup complete"
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
