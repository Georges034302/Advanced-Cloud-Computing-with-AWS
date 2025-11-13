# Lab 8.A: Monitor EC2 with CloudWatch Dashboard and Alarms

## Overview
This lab demonstrates AWS CloudWatch monitoring by creating dashboards to visualize EC2 metrics and configuring alarms to detect high resource utilization. You'll launch an EC2 instance, monitor CPU and network metrics in real-time, create a custom dashboard, set up SNS email alerts, and trigger alarms through simulated load.

**💰 Cost**: FREE (CloudWatch basic monitoring, 10 alarms free, 1K SNS emails/month)

---

## Objectives
- Launch EC2 instance with CloudWatch monitoring
- View built-in CloudWatch metrics (CPU, Network, Disk)
- Create CloudWatch dashboard with multiple widgets
- Configure SNS topic for email notifications
- Create CloudWatch alarms for high CPU utilization
- Test alarm triggers with stress testing
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Valid email address for alarm notifications
- IAM permissions for EC2, CloudWatch, SNS, and IAM
- Basic understanding of CloudWatch metrics

---

## Architecture

```
EC2 Instance → CloudWatch Metrics → Dashboard (Visualization)
                    ↓
              Alarm Threshold → SNS Topic → Email Notification
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
INSTANCE_NAME="cloudwatch-monitored-instance"
echo "INSTANCE_NAME=$INSTANCE_NAME"

DASHBOARD_NAME="EC2-Monitoring-Dashboard"
echo "DASHBOARD_NAME=$DASHBOARD_NAME"

ALARM_NAME="High-CPU-Alarm"
echo "ALARM_NAME=$ALARM_NAME"

TOPIC_NAME="cloudwatch-alerts"
echo "TOPIC_NAME=$TOPIC_NAME"

# Set your email for alarms (CHANGE THIS!)
EMAIL_ADDRESS="your-email@example.com"
echo "EMAIL_ADDRESS=$EMAIL_ADDRESS"

echo ""
echo "⚠️  IMPORTANT: Change EMAIL_ADDRESS to your real email!"
echo ""
echo "✅ Prerequisites verified"
```

---

## Step 2 – Create SNS Topic for Alarm Notifications

```bash
# Create SNS topic for CloudWatch alarms
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
# Subscribe email to receive alarm notifications
echo "Subscribing email to SNS topic..."

aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol email \
  --notification-endpoint "$EMAIL_ADDRESS" \
  --region "$REGION"

echo ""
echo "✅ Email subscription created"
echo ""
echo "================================================"
echo "⚠️  ACTION REQUIRED"
echo "================================================"
echo "Check your email inbox: $EMAIL_ADDRESS"
echo "Subject: 'AWS Notification - Subscription Confirmation'"
echo "Click the 'Confirm subscription' link"
echo ""
echo "Press Enter after confirming..."
read
```

---

## Step 4 – Get Default VPC and Latest AMI

```bash
# Get default VPC
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

## Step 5 – Create Security Group

```bash
# Create security group for EC2 instance
echo "Creating security group..."

SG_ID=$(aws ec2 create-security-group \
  --group-name "cloudwatch-monitoring-sg" \
  --description "Security group for CloudWatch monitoring lab" \
  --vpc-id "$DEFAULT_VPC" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)
echo "SG_ID=$SG_ID"

# Allow SSH access (for stress testing later)
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

echo "✅ Security group created with SSH access"
```

---

## Step 6 – Launch EC2 Instance with Detailed Monitoring

```bash
echo ""
echo "================================================"
echo "LAUNCHING EC2 INSTANCE"
echo "================================================"
echo ""

# Launch t2.micro instance with detailed monitoring
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --subnet-id "$DEFAULT_SUBNET" \
  --security-group-ids "$SG_ID" \
  --monitoring Enabled=true \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
  --region "$REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)
echo "INSTANCE_ID=$INSTANCE_ID"

echo "✅ EC2 instance launched with detailed monitoring enabled"
echo ""
echo "Waiting for instance to be running..."
aws ec2 wait instance-running \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

echo "✅ Instance is running"
```

---

## Step 7 – View CloudWatch Metrics

```bash
echo ""
echo "Waiting 2 minutes for metrics to populate..."
sleep 120

echo ""
echo "Available CloudWatch metrics for instance:"

# List available metrics for the instance
aws cloudwatch list-metrics \
  --namespace AWS/EC2 \
  --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
  --region "$REGION" \
  --query 'Metrics[*].MetricName' \
  --output table

echo ""
echo "Common EC2 metrics:"
echo "  - CPUUtilization: Percentage of CPU used"
echo "  - NetworkIn: Bytes received"
echo "  - NetworkOut: Bytes sent"
echo "  - DiskReadBytes: Bytes read from disk"
echo "  - DiskWriteBytes: Bytes written to disk"
```

---

## Step 8 – Get Current CPU Utilization

```bash
echo ""
echo "Getting current CPU utilization..."

# Get CPU utilization for last 5 minutes
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
  --start-time "$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Average \
  --region "$REGION" \
  --query 'Datapoints[*].{Time:Timestamp,CPU:Average}' \
  --output table
```

---

## Step 9 – Create CloudWatch Dashboard

```bash
echo ""
echo "Creating CloudWatch dashboard..."

# Create dashboard with CPU and Network metrics
cat > dashboard-config.json <<EOF
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          [ "AWS/EC2", "CPUUtilization", { "stat": "Average", "label": "CPU Utilization" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "${REGION}",
        "title": "EC2 CPU Utilization",
        "period": 300,
        "yAxis": {
          "left": {
            "min": 0,
            "max": 100
          }
        }
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          [ "AWS/EC2", "NetworkIn", { "stat": "Sum", "label": "Network In" } ],
          [ ".", "NetworkOut", { "stat": "Sum", "label": "Network Out" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "${REGION}",
        "title": "Network Traffic",
        "period": 300,
        "yAxis": {
          "left": {
            "min": 0
          }
        }
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          [ "AWS/EC2", "DiskReadBytes", { "stat": "Sum", "label": "Disk Read" } ],
          [ ".", "DiskWriteBytes", { "stat": "Sum", "label": "Disk Write" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "${REGION}",
        "title": "Disk I/O",
        "period": 300
      }
    }
  ]
}
EOF

# Create dashboard
aws cloudwatch put-dashboard \
  --dashboard-name "$DASHBOARD_NAME" \
  --dashboard-body file://dashboard-config.json \
  --region "$REGION"

echo "✅ CloudWatch dashboard created"
echo ""
echo "Dashboard URL:"
echo "https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:name=${DASHBOARD_NAME}"
```

---

## Step 10 – Create CloudWatch Alarm for High CPU

```bash
echo ""
echo "Creating CloudWatch alarm for high CPU..."

# Create alarm that triggers when CPU > 70% for 2 consecutive periods
aws cloudwatch put-metric-alarm \
  --alarm-name "$ALARM_NAME" \
  --alarm-description "Alert when CPU exceeds 70%" \
  --metric-name CPUUtilization \
  --namespace AWS/EC2 \
  --statistic Average \
  --period 60 \
  --evaluation-periods 2 \
  --threshold 70 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
  --alarm-actions "$TOPIC_ARN" \
  --region "$REGION"

echo "✅ CloudWatch alarm created"
echo ""
echo "Alarm configuration:"
echo "  - Metric: CPUUtilization"
echo "  - Threshold: > 70%"
echo "  - Evaluation: 2 periods of 60 seconds"
echo "  - Action: Send email via SNS"
```

---

## Step 11 – View Alarm Status

```bash
echo ""
echo "Checking alarm status..."

aws cloudwatch describe-alarms \
  --alarm-names "$ALARM_NAME" \
  --region "$REGION" \
  --query 'MetricAlarms[0].{Name:AlarmName,State:StateValue,Reason:StateReason}' \
  --output table

echo ""
echo "Alarm states:"
echo "  - OK: Metric is below threshold"
echo "  - ALARM: Metric exceeded threshold"
echo "  - INSUFFICIENT_DATA: Not enough data yet"
```

---

## Step 12 – Generate CPU Load to Trigger Alarm

```bash
echo ""
echo "================================================"
echo "TRIGGERING ALARM WITH CPU LOAD"
echo "================================================"
echo ""

# Get instance public IP for SSH (optional - for manual testing)
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$REGION")
echo "Instance Public IP: $PUBLIC_IP"

echo ""
echo "Option 1: Using SSM (no SSH key needed)"
echo "Running CPU stress test via SSM..."

# Install stress tool and run it
aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo yum install -y stress","stress --cpu 2 --timeout 180s &"]' \
  --region "$REGION" \
  2>/dev/null || echo "⚠️  SSM not available, skipping automated stress test"

echo ""
echo "Stress test running for 3 minutes..."
echo "CPU will spike to ~100% triggering the alarm"
echo ""
echo "Monitoring alarm status (checking every 30 seconds)..."
echo ""

# Monitor alarm for 4 minutes
for i in {1..8}; do
    ALARM_STATE=$(aws cloudwatch describe-alarms \
      --alarm-names "$ALARM_NAME" \
      --region "$REGION" \
      --query 'MetricAlarms[0].StateValue' \
      --output text)
    
    echo "Check $i/8: Alarm state = $ALARM_STATE"
    
    if [ "$ALARM_STATE" = "ALARM" ]; then
        echo ""
        echo "🚨 ALARM TRIGGERED! 🚨"
        echo "Check your email for notification"
        break
    fi
    
    sleep 30
done
```

---

## Step 13 – View Alarm History

```bash
echo ""
echo "Viewing alarm history..."

aws cloudwatch describe-alarm-history \
  --alarm-name "$ALARM_NAME" \
  --history-item-type StateUpdate \
  --max-records 5 \
  --region "$REGION" \
  --query 'AlarmHistoryItems[*].{Time:Timestamp,Summary:HistorySummary}' \
  --output table
```

---

## Step 14 – View Dashboard Metrics

```bash
echo ""
echo "================================================"
echo "DASHBOARD CREATED"
echo "================================================"
echo ""
echo "View your dashboard in AWS Console:"
echo "https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:name=${DASHBOARD_NAME}"
echo ""
echo "Dashboard widgets:"
echo "  1. CPU Utilization (should show spike)"
echo "  2. Network Traffic"
echo "  3. Disk I/O"
echo ""
echo "You can customize dashboards with additional widgets:"
echo "  - Line graphs, bar charts, numbers"
echo "  - Multiple metrics per widget"
echo "  - Custom time ranges"
echo "  - Annotations and alarms"
```

---

## Step 15 – List All Alarms

```bash
echo ""
echo "All CloudWatch alarms in this region:"

aws cloudwatch describe-alarms \
  --region "$REGION" \
  --query 'MetricAlarms[*].{Name:AlarmName,Metric:MetricName,State:StateValue,Threshold:Threshold}' \
  --output table
```

---

## Step 16 – Cleanup Resources

```bash
echo ""
echo "Cleaning up resources..."

# Delete CloudWatch alarm
echo "Deleting CloudWatch alarm..."
aws cloudwatch delete-alarms \
  --alarm-names "$ALARM_NAME" \
  --region "$REGION"

# Delete CloudWatch dashboard
echo "Deleting CloudWatch dashboard..."
aws cloudwatch delete-dashboards \
  --dashboard-names "$DASHBOARD_NAME" \
  --region "$REGION"

# Terminate EC2 instance
echo "Terminating EC2 instance..."
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

echo "Waiting for instance to terminate..."
aws ec2 wait instance-terminated \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

# Delete security group
echo "Deleting security group..."
aws ec2 delete-security-group \
  --group-id "$SG_ID" \
  --region "$REGION"

# Unsubscribe email from SNS
echo "Unsubscribing email from SNS..."
SUBSCRIPTION_ARN=$(aws sns list-subscriptions-by-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION" \
  --query 'Subscriptions[0].SubscriptionArn' \
  --output text)

if [ "$SUBSCRIPTION_ARN" != "PendingConfirmation" ] && [ -n "$SUBSCRIPTION_ARN" ]; then
    aws sns unsubscribe \
      --subscription-arn "$SUBSCRIPTION_ARN" \
      --region "$REGION"
fi

# Delete SNS topic
echo "Deleting SNS topic..."
aws sns delete-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION"

# Delete local files
rm -f dashboard-config.json

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- CloudWatch alarm"
echo "- CloudWatch dashboard"
echo "- EC2 instance"
echo "- Security group"
echo "- SNS topic and subscription"
```

---

## Summary

In this lab, you have:
- Launched EC2 instance with detailed CloudWatch monitoring enabled
- Viewed built-in CloudWatch metrics (CPU, Network, Disk)
- Created custom CloudWatch dashboard with multiple metric widgets
- Configured SNS topic for email notifications
- Created CloudWatch alarm for high CPU utilization (>70%)
- Triggered alarm by generating CPU load with stress test
- Received email notification when alarm triggered
- Viewed alarm history and state changes
- Cleaned up all resources

**Key Takeaways:**
- **CloudWatch Metrics**: Automatic collection of resource metrics
- **Dashboards**: Visual representation of multiple metrics
- **Alarms**: Automated monitoring with threshold-based alerts
- **SNS Integration**: Email notifications for alarm state changes
- **Detailed Monitoring**: 1-minute granularity (vs 5-minute basic)
- **Statistic Types**: Average, Sum, Min, Max, SampleCount

**Metric Collection:**
```
EC2 Instance → CloudWatch Agent → Metrics (every 1 or 5 minutes)
                                     ↓
                              Alarm Evaluates Threshold
                                     ↓
                              Triggers SNS Notification
```

**Alarm States:**
- **OK**: Metric is within threshold
- **ALARM**: Metric breached threshold
- **INSUFFICIENT_DATA**: Not enough data to evaluate

**Dashboard Widget Types:**
- **Line**: Time series data
- **Stacked area**: Cumulative metrics
- **Number**: Single metric value
- **Bar**: Comparison across dimensions
- **Pie**: Percentage distribution

---

## Best Practices

**Monitoring:**
- Enable detailed monitoring for critical instances (1-minute intervals)
- Use composite alarms for complex conditions
- Set appropriate evaluation periods (avoid false alarms)
- Monitor burst balance for T2/T3 instances
- Create dashboards per environment (dev, staging, prod)

**Alarms:**
- Use meaningful alarm names and descriptions
- Set realistic thresholds based on historical data
- Configure multiple notification channels (SNS, Lambda, Auto Scaling)
- Test alarms regularly to ensure they work
- Document alarm response procedures

**Cost Optimization:**
- Basic monitoring is free (5-minute intervals)
- Detailed monitoring costs $2.10/instance/month
- First 10 alarms are free, $0.10/alarm after
- Dashboard is free, API calls may incur charges
- Use metric filters sparingly (charged per GB ingested)

**Dashboard Design:**
- Group related metrics together
- Use consistent time ranges across widgets
- Add horizontal annotations for thresholds
- Include alarm status in dashboards
- Share dashboards across teams

---

## Free Tier Notes
- **CloudWatch**: 10 alarms free, 1M API requests, 5GB logs ingestion
- **SNS**: 1,000 email notifications/month free
- **EC2**: t2.micro 750 hours/month free (first year)

This lab uses minimal resources, staying well within free tier limits.

---

## Production Enhancements

1. **Multi-Dimensional Alarms**
   ```bash
   # Alarm across multiple instances
   aws cloudwatch put-metric-alarm \
     --alarm-name fleet-high-cpu \
     --metric-name CPUUtilization \
     --namespace AWS/EC2 \
     --statistic Average \
     --period 300 \
     --evaluation-periods 2 \
     --threshold 80 \
     --comparison-operator GreaterThanThreshold \
     --dimensions Name=AutoScalingGroupName,Value=my-asg
   ```

2. **Composite Alarms**
   ```bash
   # Combine multiple alarms with AND/OR logic
   aws cloudwatch put-composite-alarm \
     --alarm-name critical-system-failure \
     --alarm-rule "ALARM(high-cpu-alarm) AND ALARM(high-memory-alarm)"
   ```

3. **Auto Scaling Integration**
   - Use CloudWatch alarms to trigger Auto Scaling policies
   - Scale out when CPU > 70%, scale in when < 30%

4. **Lambda Integration**
   - Trigger Lambda function from CloudWatch alarm
   - Automated remediation (restart service, clear cache, etc.)

5. **Cross-Account Monitoring**
   - Share dashboards across AWS accounts
   - Aggregate metrics from multiple accounts

6. **Custom Metrics**
   ```bash
   # Publish custom application metrics
   aws cloudwatch put-metric-data \
     --namespace MyApp/Orders \
     --metric-name OrdersPerMinute \
     --value 150 \
     --unit Count
   ```

---

## Troubleshooting

**No metrics appearing:**
- Wait 5-10 minutes for first metrics
- Verify detailed monitoring is enabled
- Check instance is running
- Ensure CloudWatch agent is installed (for custom metrics)

**Alarm not triggering:**
- Verify threshold is set correctly
- Check evaluation periods (need consistent breach)
- Confirm SNS subscription is active
- Review alarm history for state changes

**Dashboard not loading:**
- Check dashboard JSON syntax
- Verify metric namespace and dimensions
- Ensure permissions for CloudWatch:GetMetricData
- Try recreating dashboard from console first

**Email not received:**
- Confirm email subscription (check spam folder)
- Verify SNS topic has correct permissions
- Check alarm action points to correct topic ARN
- Test SNS topic with manual publish
