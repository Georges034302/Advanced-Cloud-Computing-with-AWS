# Lab 5.B: Auto Scaling with CloudWatch Alarms

## Overview
This lab demonstrates how to create an Auto Scaling Group (ASG) for EC2 instances with automatic scaling based on CloudWatch metrics and alarms. You will configure target-tracking scaling policies, step-scaling policies, scheduled scaling, and test scale-out/scale-in behavior with load testing.

---

## Objectives
- Create Launch Template with simple web server
- Create Auto Scaling Group across multiple availability zones
- Configure target-tracking scaling policy (CPU-based)
- Set up scheduled scaling for predictable load patterns
- Monitor scaling activities and CloudWatch metrics
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Default VPC with subnets in multiple availability zones
- IAM permissions for EC2, Auto Scaling, and CloudWatch
- Basic understanding of Auto Scaling and CloudWatch concepts

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID dynamically
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set region
REGION="ap-southeast-2"
echo "REGION=$REGION"

# Set Auto Scaling configuration
LAUNCH_TEMPLATE_NAME="lab-asg-template"
echo "LAUNCH_TEMPLATE_NAME=$LAUNCH_TEMPLATE_NAME"

ASG_NAME="lab-auto-scaling-group"
echo "ASG_NAME=$ASG_NAME"

# Set capacity limits (free tier compatible)
MIN_SIZE=1
echo "MIN_SIZE=$MIN_SIZE"

MAX_SIZE=3
echo "MAX_SIZE=$MAX_SIZE"

DESIRED_CAPACITY=1
echo "DESIRED_CAPACITY=$DESIRED_CAPACITY"

# Instance configuration
INSTANCE_TYPE="t2.micro"
echo "INSTANCE_TYPE=$INSTANCE_TYPE"

# Get default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region "$REGION")
echo "VPC_ID=$VPC_ID"

# Get availability zones
AVAILABILITY_ZONES=$(aws ec2 describe-availability-zones \
  --region "$REGION" \
  --query 'AvailabilityZones[?State==`available`].ZoneName' \
  --output text)
echo "AVAILABILITY_ZONES=$AVAILABILITY_ZONES"

# Get subnet IDs across all availability zones
SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[*].SubnetId' \
  --output text \
  --region "$REGION")
echo "SUBNET_IDS=$SUBNET_IDS"

# Convert to comma-separated list for ASG
SUBNET_LIST=$(echo "$SUBNET_IDS" | tr ' ' ',')
echo "SUBNET_LIST=$SUBNET_LIST"

# Verify AWS CLI is configured
aws sts get-caller-identity
```

---

## Step 2 – Create Security Group for Auto Scaling Instances

```bash
# Create security group for Auto Scaling instances
ASG_SG_ID=$(aws ec2 create-security-group \
  --group-name "lab-asg-sg" \
  --description "Security group for Auto Scaling Group instances" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)
echo "ASG_SG_ID=$ASG_SG_ID"

# Allow HTTP access from anywhere
aws ec2 authorize-security-group-ingress \
  --group-id "$ASG_SG_ID" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

# Allow SSH access for troubleshooting
aws ec2 authorize-security-group-ingress \
  --group-id "$ASG_SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

echo "Security group created with HTTP and SSH access"

# Describe security group
aws ec2 describe-security-groups \
  --group-ids "$ASG_SG_ID" \
  --query 'SecurityGroups[0].{GroupId:GroupId,GroupName:GroupName,Description:Description}' \
  --output table \
  --region "$REGION"
```

---

## Step 3 – Get Latest Amazon Linux 2023 AMI

```bash
# Get latest Amazon Linux 2023 AMI ID
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" \
    "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text \
  --region "$REGION")
echo "AMI_ID=$AMI_ID"

# Display AMI details
aws ec2 describe-images \
  --image-ids "$AMI_ID" \
  --query 'Images[0].{ImageId:ImageId,Name:Name,CreationDate:CreationDate}' \
  --output table \
  --region "$REGION"
```

---

## Step 4 – Create Launch Template with User Data

```bash
# Create simple user data script for web server
cat > asg-userdata.sh <<'EOF'
#!/bin/bash
# Update system packages
dnf update -y

# Install Apache web server
dnf install -y httpd

# Get instance metadata
INSTANCE_ID=$(ec2-metadata --instance-id | cut -d " " -f 2)
AVAILABILITY_ZONE=$(ec2-metadata --availability-zone | cut -d " " -f 2)

# Create simple web page showing instance information
cat > /var/www/html/index.html <<HTML
<!DOCTYPE html>
<html>
<head>
    <title>Auto Scaling Demo</title>
    <style>
        body { font-family: Arial; text-align: center; padding: 50px; background: #f0f0f0; }
        .box { background: white; padding: 20px; border-radius: 5px; display: inline-block; }
        h1 { color: #FF9900; }
    </style>
</head>
<body>
    <div class="box">
        <h1>Auto Scaling Instance</h1>
        <p><strong>Instance ID:</strong> ${INSTANCE_ID}</p>
        <p><strong>Availability Zone:</strong> ${AVAILABILITY_ZONE}</p>
        <p>Refresh to see load distribution</p>
    </div>
</body>
</html>
HTML

# Create health check endpoint
echo "OK" > /var/www/html/health.html

# Start and enable Apache
systemctl start httpd
systemctl enable httpd

# Log completion
echo "Web server setup completed" > /var/log/userdata-complete.log
EOF

echo "User data script created"

# Create Launch Template with user data
echo "Creating Launch Template..."

LAUNCH_TEMPLATE_OUTPUT=$(aws ec2 create-launch-template \
  --launch-template-name "$LAUNCH_TEMPLATE_NAME" \
  --version-description "Initial version with web server and stress utility" \
  --launch-template-data "{
    \"ImageId\":\"$AMI_ID\",
    \"InstanceType\":\"$INSTANCE_TYPE\",
    \"SecurityGroupIds\":[\"$ASG_SG_ID\"],
    \"UserData\":\"$(base64 -w0 asg-userdata.sh)\",
    \"TagSpecifications\":[{
      \"ResourceType\":\"instance\",
      \"Tags\":[
        {\"Key\":\"Name\",\"Value\":\"asg-instance\"},
        {\"Key\":\"Lab\",\"Value\":\"5B\"},
        {\"Key\":\"ManagedBy\",\"Value\":\"AutoScaling\"}
      ]
    }],
    \"Monitoring\":{\"Enabled\":true}
  }" \
  --region "$REGION")

# Extract Launch Template ID
LAUNCH_TEMPLATE_ID=$(echo "$LAUNCH_TEMPLATE_OUTPUT" | jq -r '.LaunchTemplate.LaunchTemplateId')
echo "LAUNCH_TEMPLATE_ID=$LAUNCH_TEMPLATE_ID"

echo "✅ Launch Template created successfully"

# Describe Launch Template
aws ec2 describe-launch-templates \
  --launch-template-ids "$LAUNCH_TEMPLATE_ID" \
  --query 'LaunchTemplates[0].{TemplateId:LaunchTemplateId,TemplateName:LaunchTemplateName,LatestVersion:LatestVersionNumber,CreatedTime:CreateTime}' \
  --output table \
  --region "$REGION"
```

---

## Step 5 – Create Auto Scaling Group

```bash
# Create Auto Scaling Group across multiple AZs
echo "Creating Auto Scaling Group..."

aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name "$ASG_NAME" \
  --launch-template "LaunchTemplateId=$LAUNCH_TEMPLATE_ID,Version=\$Latest" \
  --min-size "$MIN_SIZE" \
  --max-size "$MAX_SIZE" \
  --desired-capacity "$DESIRED_CAPACITY" \
  --vpc-zone-identifier "$SUBNET_LIST" \
  --health-check-type EC2 \
  --health-check-grace-period 300 \
  --default-cooldown 300 \
  --tags "Key=Name,Value=asg-instance,PropagateAtLaunch=true" \
    "Key=Lab,Value=5B,PropagateAtLaunch=true" \
  --region "$REGION"

echo "✅ Auto Scaling Group created"

# Wait for ASG to launch initial instances
echo "Waiting for initial instances to launch..."
sleep 30

# Describe Auto Scaling Group
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[0].{Name:AutoScalingGroupName,MinSize:MinSize,MaxSize:MaxSize,DesiredCapacity:DesiredCapacity,Instances:length(Instances),HealthCheckType:HealthCheckType,Subnets:VPCZoneIdentifier}' \
  --output table \
  --region "$REGION"

# List instances in ASG
echo ""
echo "Instances in Auto Scaling Group:"
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[0].Instances[*].{InstanceId:InstanceId,LifecycleState:LifecycleState,HealthStatus:HealthStatus,AZ:AvailabilityZone}' \
  --output table \
  --region "$REGION"
```

---

## Step 6 – Configure Target Tracking Scaling Policy (CPU-based)

```bash
# Create target-tracking scaling policy to maintain average CPU at 40%
echo "Creating target-tracking scaling policy..."

TARGET_TRACKING_POLICY_ARN=$(aws autoscaling put-scaling-policy \
  --auto-scaling-group-name "$ASG_NAME" \
  --policy-name "cpu-target-tracking-40" \
  --policy-type TargetTrackingScaling \
  --target-tracking-configuration '{
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ASGAverageCPUUtilization"
    },
    "TargetValue": 40.0,
    "ScaleInCooldown": 180,
    "ScaleOutCooldown": 60
  }' \
  --region "$REGION" \
  --query 'PolicyARN' \
  --output text)
echo "TARGET_TRACKING_POLICY_ARN=$TARGET_TRACKING_POLICY_ARN"

echo "✅ Target-tracking policy created (Target: 40% CPU)"

# Describe scaling policies
aws autoscaling describe-policies \
  --auto-scaling-group-name "$ASG_NAME" \
  --query 'ScalingPolicies[*].{PolicyName:PolicyName,PolicyType:PolicyType,TargetValue:TargetTrackingConfiguration.TargetValue,Metric:TargetTrackingConfiguration.PredefinedMetricSpecification.PredefinedMetricType}' \
  --output table \
  --region "$REGION"
```

---

## Step 7 – Create Scheduled Scaling Action

```bash
# Calculate future time for scheduled scaling (5 minutes from now)
FUTURE_TIME=$(date -u -d '+5 minutes' +"%Y-%m-%dT%H:%M:00Z")
echo "FUTURE_TIME=$FUTURE_TIME"

# Create scheduled action to scale up
echo "Creating scheduled scaling action..."

aws autoscaling put-scheduled-update-group-action \
  --auto-scaling-group-name "$ASG_NAME" \
  --scheduled-action-name "scale-up-scheduled" \
  --start-time "$FUTURE_TIME" \
  --min-size 2 \
  --desired-capacity 2 \
  --max-size "$MAX_SIZE" \
  --region "$REGION"

echo "✅ Scheduled action created (will execute at $FUTURE_TIME)"

# Create scheduled action to scale down (10 minutes from now)
SCALE_DOWN_TIME=$(date -u -d '+10 minutes' +"%Y-%m-%dT%H:%M:00Z")
echo "SCALE_DOWN_TIME=$SCALE_DOWN_TIME"

aws autoscaling put-scheduled-update-group-action \
  --auto-scaling-group-name "$ASG_NAME" \
  --scheduled-action-name "scale-down-scheduled" \
  --start-time "$SCALE_DOWN_TIME" \
  --min-size 1 \
  --desired-capacity 1 \
  --max-size "$MAX_SIZE" \
  --region "$REGION"

echo "✅ Scale-down scheduled action created (will execute at $SCALE_DOWN_TIME)"

# List scheduled actions
echo ""
echo "Scheduled Actions:"
aws autoscaling describe-scheduled-actions \
  --auto-scaling-group-name "$ASG_NAME" \
  --query 'ScheduledUpdateGroupActions[*].{ActionName:ScheduledActionName,StartTime:StartTime,MinSize:MinSize,DesiredCapacity:DesiredCapacity}' \
  --output table \
  --region "$REGION"
```

---

## Step 8 – View Auto Scaling Group Status

```bash
# Get instance IDs in ASG
INSTANCE_IDS=$(aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[0].Instances[*].InstanceId' \
  --output text \
  --region "$REGION")
echo "INSTANCE_IDS=$INSTANCE_IDS"

# Get public IP of first instance
FIRST_INSTANCE_ID=$(echo "$INSTANCE_IDS" | awk '{print $1}')
echo "FIRST_INSTANCE_ID=$FIRST_INSTANCE_ID"

PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$FIRST_INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$REGION")
echo "PUBLIC_IP=$PUBLIC_IP"

echo ""
echo "================================================"
echo "AUTO SCALING GROUP STATUS"
echo "================================================"
echo ""
echo "Web Application URL: http://${PUBLIC_IP}"
echo ""
echo "Current ASG Configuration:"
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[0].{Name:AutoScalingGroupName,MinSize:MinSize,MaxSize:MaxSize,DesiredCapacity:DesiredCapacity,CurrentInstances:length(Instances)}' \
  --output table \
  --region "$REGION"

echo ""
echo "Instances in ASG:"
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[0].Instances[*].{InstanceId:InstanceId,LifecycleState:LifecycleState,HealthStatus:HealthStatus,AZ:AvailabilityZone}' \
  --output table \
  --region "$REGION"

echo ""
echo "Scaling will occur based on:"
echo "  - Target tracking policy: Maintain 40% CPU"
echo "  - Scheduled actions: Scale at specific times"
echo ""
echo "================================================"
```

---

## Step 9 – Monitor Auto Scaling Activities

```bash
echo ""
echo "================================================"
echo "MONITORING AUTO SCALING"
echo "================================================"
echo ""

# Watch scaling activities
echo "Recent Scaling Activities:"
aws autoscaling describe-scaling-activities \
  --auto-scaling-group-name "$ASG_NAME" \
  --max-records 10 \
  --query 'Activities[*].{Time:StartTime,Description:Description,StatusCode:StatusCode,Cause:Cause}' \
  --output table \
  --region "$REGION"

echo ""
echo "Current ASG State:"
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[0].{Name:AutoScalingGroupName,MinSize:MinSize,MaxSize:MaxSize,DesiredCapacity:DesiredCapacity,CurrentInstances:length(Instances),HealthyInstances:length(Instances[?HealthStatus==`Healthy`])}' \
  --output table \
  --region "$REGION"

echo ""
echo "CloudWatch Alarm States:"
aws cloudwatch describe-alarms \
  --alarm-name-prefix "$ASG_NAME" \
  --query 'MetricAlarms[*].{AlarmName:AlarmName,State:StateValue,Reason:StateReason}' \
  --output table \
  --region "$REGION"

echo ""
echo "To monitor scaling in real-time:"
echo ""
echo "Watch scaling activities:"
echo "  aws autoscaling describe-scaling-activities --auto-scaling-group-name $ASG_NAME --max-records 5 --region $REGION"
echo ""
echo "Watch instance count:"
echo "  aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names $ASG_NAME --region $REGION"
```

---

## Step 10 – View CloudWatch Metrics

```bash
# Get CPU utilization metrics
echo ""
echo "Retrieving CPU utilization metrics..."

aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=AutoScalingGroupName,Value="$ASG_NAME" \
  --start-time "$(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Average,Maximum \
  --region "$REGION" \
  --query 'Datapoints[*].{Timestamp:Timestamp,Average:Average,Maximum:Maximum}' \
  --output table

# Get GroupDesiredCapacity metrics
echo ""
echo "Retrieving desired capacity changes..."

aws cloudwatch get-metric-statistics \
  --namespace AWS/AutoScaling \
  --metric-name GroupDesiredCapacity \
  --dimensions Name=AutoScalingGroupName,Value="$ASG_NAME" \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Average \
  --region "$REGION" \
  --query 'Datapoints[*].{Timestamp:Timestamp,DesiredCapacity:Average}' \
  --output table

# Get GroupInServiceInstances metrics
echo ""
echo "Retrieving in-service instance count..."

aws cloudwatch get-metric-statistics \
  --namespace AWS/AutoScaling \
  --metric-name GroupInServiceInstances \
  --dimensions Name=AutoScalingGroupName,Value="$ASG_NAME" \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Average \
  --region "$REGION" \
  --query 'Datapoints[*].{Timestamp:Timestamp,InServiceInstances:Average}' \
  --output table
```

---

## Step 11 – Cleanup Resources

```bash
echo "Starting cleanup..."

# Delete scheduled actions
echo "Deleting scheduled actions..."
aws autoscaling delete-scheduled-action \
  --auto-scaling-group-name "$ASG_NAME" \
  --scheduled-action-name "scale-up-scheduled" \
  --region "$REGION" 2>/dev/null || true

aws autoscaling delete-scheduled-action \
  --auto-scaling-group-name "$ASG_NAME" \
  --scheduled-action-name "scale-down-scheduled" \
  --region "$REGION" 2>/dev/null || true

# Delete scaling policies
echo "Deleting scaling policies..."
aws autoscaling delete-policy \
  --auto-scaling-group-name "$ASG_NAME" \
  --policy-name "cpu-target-tracking-40" \
  --region "$REGION" 2>/dev/null || true

# Update ASG to zero instances
echo "Scaling Auto Scaling Group to zero..."
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name "$ASG_NAME" \
  --min-size 0 \
  --desired-capacity 0 \
  --region "$REGION"

# Wait for instances to terminate
echo "Waiting for instances to terminate..."
sleep 60

# Delete Auto Scaling Group
echo "Deleting Auto Scaling Group..."
aws autoscaling delete-auto-scaling-group \
  --auto-scaling-group-name "$ASG_NAME" \
  --force-delete \
  --region "$REGION"

# Wait for ASG deletion
echo "Waiting for ASG deletion..."
sleep 30

# Delete Launch Template
echo "Deleting Launch Template..."
aws ec2 delete-launch-template \
  --launch-template-id "$LAUNCH_TEMPLATE_ID" \
  --region "$REGION"

# Delete security group
echo "Deleting security group..."
sleep 10

aws ec2 delete-security-group \
  --group-id "$ASG_SG_ID" \
  --region "$REGION"

# Delete local files
echo "Cleaning up local files..."
rm -f asg-userdata.sh

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- Auto Scaling Group"
echo "- Launch Template"
echo "- Scaling policy (target-tracking)"
echo "- Scheduled actions (2)"
echo "- Security group"
echo "- Local files"
```

---

## Summary

In this lab, you have:
- Created Launch Template with simple web server
- Created Auto Scaling Group across multiple availability zones
- Configured target-tracking scaling policy based on CPU utilization
- Created scheduled scaling actions for predictable load patterns
- Monitored scaling activities and CloudWatch metrics
- Cleaned up all resources

**Key Takeaways:**
- **Auto Scaling**: Automatically adjusts capacity based on demand
- **Target Tracking**: Maintains specific metric at target value (e.g., 40% CPU)
- **Scheduled Scaling**: Scales based on predictable time patterns
- **Health Checks**: Unhealthy instances automatically replaced
- **Multi-AZ**: High availability across availability zones
- **Cost Optimization**: Scale down during low demand periods
- **Free Tier Compatible**: Uses t2.micro instances within free tier limits

**Scaling Policy Types:**
| Policy Type | Use Case | Best For |
|-------------|----------|----------|
| **Target Tracking** | Maintain metric at target | CPU, requests/target |
| **Scheduled** | Predictable patterns | Daily/weekly patterns |
| **Step Scaling** | Aggressive scaling | Sudden spikes (advanced) |

**Best Practices:**
- Use target-tracking for CPU-based scaling (simplest and most effective)
- Set appropriate cooldown periods to avoid rapid scaling
- Configure health check grace period for application startup time
- Use multiple AZs for high availability
- Set meaningful min/max capacity limits
- Schedule scaling for known traffic patterns
- Tag instances for cost tracking
- Monitor CloudWatch metrics regularly

**Real-World Use Cases:**
- **Web Applications**: Handle variable traffic patterns
- **E-commerce**: Scale during peak shopping hours
- **Batch Processing**: Scale for scheduled job processing
- **Gaming**: Handle player activity fluctuations
- **SaaS Applications**: Scale per customer demand
- **API Services**: Handle request rate variations

---

## Additional Resources
- [Auto Scaling User Guide](https://docs.aws.amazon.com/autoscaling/ec2/userguide/)
- [Target Tracking Scaling Policies](https://docs.aws.amazon.com/autoscaling/ec2/userguide/as-scaling-target-tracking.html)
- [Step Scaling Policies](https://docs.aws.amazon.com/autoscaling/ec2/userguide/as-scaling-simple-step.html)
- [Scheduled Scaling](https://docs.aws.amazon.com/autoscaling/ec2/userguide/schedule_time.html)
- [CloudWatch Metrics for Auto Scaling](https://docs.aws.amazon.com/autoscaling/ec2/userguide/as-instance-monitoring.html)
- [Auto Scaling Best Practices](https://docs.aws.amazon.com/autoscaling/ec2/userguide/as-best-practices.html)

---