# Lab 8.A: Monitor EC2 with CloudWatch Dashboard and Alarms
<img width="1536" height="1024" alt="IMG" src="https://github.com/user-attachments/assets/28a8e389-bdf8-4932-9b4f-a2ae05f62b31" />

## Overview
This lab demonstrates AWS CloudWatch monitoring by creating dashboards to visualize EC2 metrics and configuring alarms to detect high resource utilization. You'll launch an EC2 instance, monitor CPU and network metrics in real-time, create a custom dashboard, set up SNS email alerts, and trigger alarms through simulated load.

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

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID and set region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="ap-southeast-2"

# Set resource names
INSTANCE_NAME="cloudwatch-monitored-instance"
DASHBOARD_NAME="EC2-Monitoring-Dashboard"
ALARM_NAME="High-CPU-Alarm"
TOPIC_NAME="cloudwatch-alerts"

# Email address for alarm notifications (IMPORTANT: Change this!)
EMAIL_ADDRESS="your-email@example.com"

echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "REGION=$REGION"
echo "EMAIL_ADDRESS=$EMAIL_ADDRESS"
```

---

## Step 2 – Create SNS Topic for Alarm Notifications

```bash
# Create SNS topic for CloudWatch alarm notifications
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
# Subscribe email to SNS topic for alarm notifications
aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol email \
  --notification-endpoint "$EMAIL_ADDRESS" \
  --region "$REGION"

# ACTION REQUIRED: Check email and confirm subscription
echo "⚠️  Check $EMAIL_ADDRESS for confirmation email and click the link"
read -p "Press Enter after confirming..."
```

---

## Step 4 – Get Default VPC and Latest AMI

```bash
# Get default VPC for EC2 instance
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

## Step 5 – Create Security Group

```bash
# Create security group with SSH access (for potential stress testing)
SG_ID=$(aws ec2 create-security-group \
  --group-name "cloudwatch-monitoring-sg" \
  --description "Security group for CloudWatch monitoring lab" \
  --vpc-id "$DEFAULT_VPC" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

# Allow SSH access from anywhere
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

echo "SG_ID=$SG_ID"
```

---

## Step 6 – Launch EC2 Instance with Detailed Monitoring

```bash
# Launch t2.micro EC2 instance with detailed monitoring enabled (1-minute metric intervals)
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

# Wait for instance to reach running state
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"
echo "Instance is running"
```

---

## Step 7 – View CloudWatch Metrics

```bash
# Wait for CloudWatch metrics to populate (takes ~2 minutes)
sleep 120

# List all available CloudWatch metrics for the instance
aws cloudwatch list-metrics \
  --namespace AWS/EC2 \
  --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
  --region "$REGION" \
  --query 'Metrics[*].MetricName' \
  --output table
```

---

## Step 8 – Get Current CPU Utilization

```bash
# Get CPU utilization statistics for last 5 minutes
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
# Create CloudWatch dashboard JSON with CPU, Network, and Disk I/O widgets
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

# Create dashboard from JSON configuration
aws cloudwatch put-dashboard \
  --dashboard-name "$DASHBOARD_NAME" \
  --dashboard-body file://dashboard-config.json \
  --region "$REGION"

echo "Dashboard URL: https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:name=${DASHBOARD_NAME}"
```

---

## Step 10 – Create CloudWatch Alarm for High CPU

```bash
# Create CloudWatch alarm that triggers when CPU > 70% for 2 consecutive 1-minute periods
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
```

---

## Step 11 – View Alarm Status

```bash
# Check alarm status (OK, ALARM, or INSUFFICIENT_DATA)
aws cloudwatch describe-alarms \
  --alarm-names "$ALARM_NAME" \
  --region "$REGION" \
  --query 'MetricAlarms[0].{Name:AlarmName,State:StateValue,Reason:StateReason}' \
  --output table
```

---

## Step 12 – Generate CPU Load to Trigger Alarm

```bash
# Get instance public IP for reference
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$REGION")
echo "Instance Public IP: $PUBLIC_IP"

# Run CPU stress test via SSM (installs stress tool and runs for 3 minutes)
aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo yum install -y stress","stress --cpu 2 --timeout 180s &"]' \
  --region "$REGION" \
  2>/dev/null || echo "⚠️  SSM not available, skipping automated stress test"

echo "Stress test running - monitoring alarm status every 30 seconds..."

# Monitor alarm status for up to 4 minutes
for i in {1..8}; do
    ALARM_STATE=$(aws cloudwatch describe-alarms \
      --alarm-names "$ALARM_NAME" \
      --region "$REGION" \
      --query 'MetricAlarms[0].StateValue' \
      --output text)
    
    echo "Check $i/8: Alarm state = $ALARM_STATE"
    
    if [ "$ALARM_STATE" = "ALARM" ]; then
        echo "🚨 ALARM TRIGGERED! Check your email for notification"
        break
    fi
    
    sleep 30
done
```

---

## Step 13 – View Alarm History

```bash
# View alarm state change history (last 5 updates)
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
# Display dashboard URL to view CPU spike, network traffic, and disk I/O
echo "View dashboard: https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:name=${DASHBOARD_NAME}"
```

---

## Step 15 – List All Alarms

```bash
# List all CloudWatch alarms in the region
aws cloudwatch describe-alarms \
  --region "$REGION" \
  --query 'MetricAlarms[*].{Name:AlarmName,Metric:MetricName,State:StateValue,Threshold:Threshold}' \
  --output table
```

---

## Step 16 – Cleanup Resources

```bash
# Delete CloudWatch alarm
aws cloudwatch delete-alarms --alarm-names "$ALARM_NAME" --region "$REGION"

# Delete CloudWatch dashboard
aws cloudwatch delete-dashboards --dashboard-names "$DASHBOARD_NAME" --region "$REGION"

# Terminate EC2 instance and wait for termination
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "$REGION"
aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID" --region "$REGION"

# Delete security group
aws ec2 delete-security-group --group-id "$SG_ID" --region "$REGION"

# Unsubscribe email from SNS topic
SUBSCRIPTION_ARN=$(aws sns list-subscriptions-by-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION" \
  --query 'Subscriptions[0].SubscriptionArn' \
  --output text)

if [ "$SUBSCRIPTION_ARN" != "PendingConfirmation" ] && [ -n "$SUBSCRIPTION_ARN" ]; then
    aws sns unsubscribe --subscription-arn "$SUBSCRIPTION_ARN" --region "$REGION"
fi

# Delete SNS topic
aws sns delete-topic --topic-arn "$TOPIC_ARN" --region "$REGION"

# Delete local dashboard configuration file
rm -f dashboard-config.json

echo "Cleanup complete"
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
