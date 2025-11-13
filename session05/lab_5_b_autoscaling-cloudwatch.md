# Lab 5.B: Auto Scaling with CloudWatch Alarms

## Overview
This lab demonstrates how to create an Auto Scaling Group (ASG) for EC2 instances with automatic scaling based on CloudWatch metrics and alarms. You will configure target-tracking scaling policies, step-scaling policies, scheduled scaling, and test scale-out/scale-in behavior with load testing.

---

## Objectives
- Create Launch Template with user data for web server
- Create Auto Scaling Group across multiple availability zones
- Configure target-tracking scaling policy (CPU-based)
- Configure step-scaling policy with CloudWatch alarms
- Set up scheduled scaling for predictable load patterns
- Test scaling behavior with load generation
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
# Create user data script for web server with CPU stress utility
cat > asg-userdata.sh <<'EOF'
#!/bin/bash
# Update system packages
dnf update -y

# Install Apache web server
dnf install -y httpd

# Install stress utility for load testing
dnf install -y stress-ng

# Get instance metadata
INSTANCE_ID=$(ec2-metadata --instance-id | cut -d " " -f 2)
AVAILABILITY_ZONE=$(ec2-metadata --availability-zone | cut -d " " -f 2)
LOCAL_IP=$(ec2-metadata --local-ipv4 | cut -d " " -f 2)
HOSTNAME=$(hostname)

# Create custom web page with instance information
cat > /var/www/html/index.html <<HTML
<!DOCTYPE html>
<html>
<head>
    <title>Auto Scaling Demo</title>
    <style>
        body { font-family: Arial; text-align: center; padding: 50px; background: #f5f5f5; }
        .container { background: white; padding: 30px; border-radius: 10px; display: inline-block; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #FF9900; margin-bottom: 20px; }
        .info { background: #232F3E; color: white; padding: 20px; margin: 15px 0; border-radius: 5px; }
        .info p { margin: 10px 0; font-size: 16px; }
        .label { font-weight: bold; color: #FF9900; }
        .actions { margin-top: 20px; }
        .button { display: inline-block; padding: 10px 20px; margin: 5px; background: #FF9900; color: white; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Auto Scaling Group Demo</h1>
        <div class="info">
            <p><span class="label">Instance ID:</span> ${INSTANCE_ID}</p>
            <p><span class="label">Availability Zone:</span> ${AVAILABILITY_ZONE}</p>
            <p><span class="label">Private IP:</span> ${LOCAL_IP}</p>
            <p><span class="label">Hostname:</span> ${HOSTNAME}</p>
        </div>
        <div class="actions">
            <a href="/cpu-load" class="button">Generate CPU Load</a>
            <a href="/status" class="button">Check Status</a>
        </div>
        <p style="margin-top: 20px; color: #666;">Refresh to see load distribution across instances</p>
    </div>
</body>
</html>
HTML

# Create health check endpoint
echo "OK" > /var/www/html/health.html

# Create status page
cat > /var/www/html/status.html <<HTML
<!DOCTYPE html>
<html>
<head><title>Status</title></head>
<body>
<h1>Instance Status</h1>
<p>Instance is healthy and serving requests</p>
<p>Uptime: \$(uptime)</p>
</body>
</html>
HTML

# Create CPU load script endpoint
cat > /var/www/html/cpu-load <<'SCRIPT'
#!/bin/bash
echo "Content-type: text/html"
echo ""
echo "<html><body><h1>Generating CPU Load...</h1>"
echo "<p>Running stress test for 300 seconds (5 minutes)</p>"
echo "<p>This will trigger Auto Scaling scale-out</p>"
echo "</body></html>"

# Run stress in background
nohup stress-ng --cpu 2 --timeout 300s &> /dev/null &
SCRIPT

chmod +x /var/www/html/cpu-load

# Configure Apache to execute CGI scripts
cat >> /etc/httpd/conf/httpd.conf <<CONF
<Directory "/var/www/html">
    Options +ExecCGI
    AddHandler cgi-script .cgi
</Directory>
CONF

# Start and enable Apache
systemctl start httpd
systemctl enable httpd

# Log completion
echo "Web server and stress utility setup completed" > /var/log/userdata-complete.log
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

## Step 7 – Create Step Scaling Policy with CloudWatch Alarms

```bash
# Create step scaling policy for aggressive scale-out on high CPU
echo "Creating step scaling policy..."

STEP_POLICY_ARN=$(aws autoscaling put-scaling-policy \
  --auto-scaling-group-name "$ASG_NAME" \
  --policy-name "high-cpu-step-scaling" \
  --policy-type StepScaling \
  --adjustment-type PercentChangeInCapacity \
  --metric-aggregation-type Average \
  --step-adjustments '[
    {
      "MetricIntervalLowerBound": 0,
      "MetricIntervalUpperBound": 10,
      "ScalingAdjustment": 10
    },
    {
      "MetricIntervalLowerBound": 10,
      "ScalingAdjustment": 20
    }
  ]' \
  --region "$REGION" \
  --query 'PolicyARN' \
  --output text)
echo "STEP_POLICY_ARN=$STEP_POLICY_ARN"

echo "✅ Step scaling policy created"

# Create CloudWatch alarm for high CPU (triggers step scaling)
echo "Creating CloudWatch alarm for high CPU..."

aws cloudwatch put-metric-alarm \
  --alarm-name "${ASG_NAME}-HighCPU-StepScaling" \
  --alarm-description "Trigger step scaling when CPU exceeds 70%" \
  --metric-name CPUUtilization \
  --namespace AWS/EC2 \
  --statistic Average \
  --period 60 \
  --evaluation-periods 2 \
  --threshold 70 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=AutoScalingGroupName,Value="$ASG_NAME" \
  --alarm-actions "$STEP_POLICY_ARN" \
  --region "$REGION"

echo "✅ CloudWatch alarm created (Threshold: 70% CPU)"

# Create scale-in policy for low CPU
echo "Creating scale-in policy..."

SCALE_IN_POLICY_ARN=$(aws autoscaling put-scaling-policy \
  --auto-scaling-group-name "$ASG_NAME" \
  --policy-name "low-cpu-scale-in" \
  --policy-type StepScaling \
  --adjustment-type ChangeInCapacity \
  --metric-aggregation-type Average \
  --step-adjustments '[
    {
      "MetricIntervalUpperBound": 0,
      "ScalingAdjustment": -1
    }
  ]' \
  --region "$REGION" \
  --query 'PolicyARN' \
  --output text)
echo "SCALE_IN_POLICY_ARN=$SCALE_IN_POLICY_ARN"

# Create CloudWatch alarm for low CPU (triggers scale-in)
aws cloudwatch put-metric-alarm \
  --alarm-name "${ASG_NAME}-LowCPU-ScaleIn" \
  --alarm-description "Trigger scale-in when CPU below 20%" \
  --metric-name CPUUtilization \
  --namespace AWS/EC2 \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 20 \
  --comparison-operator LessThanThreshold \
  --dimensions Name=AutoScalingGroupName,Value="$ASG_NAME" \
  --alarm-actions "$SCALE_IN_POLICY_ARN" \
  --region "$REGION"

echo "✅ Scale-in alarm created (Threshold: 20% CPU)"

# List all alarms
echo ""
echo "CloudWatch Alarms:"
aws cloudwatch describe-alarms \
  --alarm-name-prefix "$ASG_NAME" \
  --query 'MetricAlarms[*].{AlarmName:AlarmName,Metric:MetricName,Threshold:Threshold,State:StateValue}' \
  --output table \
  --region "$REGION"
```

---

## Step 8 – Create Scheduled Scaling Action

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

## Step 9 – Test Auto Scaling with Load Generation

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
echo "LOAD TESTING INSTRUCTIONS"
echo "================================================"
echo ""
echo "Instance URL: http://${PUBLIC_IP}"
echo ""
echo "Option 1: Manual testing (open in browser)"
echo "  1. Visit: http://${PUBLIC_IP}"
echo "  2. Click 'Generate CPU Load' button"
echo "  3. Wait 2-3 minutes and watch Auto Scaling scale out"
echo ""
echo "Option 2: Automated testing (run command below)"
echo ""
cat > generate-load.sh <<LOADSCRIPT
#!/bin/bash
# Generate load on ASG instances to trigger scaling

echo "Generating CPU load on instance $PUBLIC_IP..."
echo "This will run for 5 minutes (300 seconds)"
echo ""

# SSH into instance and run stress (requires key pair)
# ssh -i your-key.pem ec2-user@$PUBLIC_IP "stress-ng --cpu 2 --timeout 300s"

# Alternative: Use AWS Systems Manager to run stress command
INSTANCE_ID="$FIRST_INSTANCE_ID"
COMMAND_ID=\$(aws ssm send-command \\
  --document-name "AWS-RunShellScript" \\
  --parameters 'commands=["stress-ng --cpu 2 --timeout 300s"]' \\
  --instance-ids "\$INSTANCE_ID" \\
  --region "$REGION" \\
  --query 'Command.CommandId' \\
  --output text)

echo "Command ID: \$COMMAND_ID"
echo "CPU load generation started on instance \$INSTANCE_ID"
echo ""
echo "Monitor scaling activity with:"
echo "  aws autoscaling describe-scaling-activities --auto-scaling-group-name $ASG_NAME --region $REGION"
LOADSCRIPT

chmod +x generate-load.sh

echo "Load generation script created: generate-load.sh"
echo ""
echo "================================================"
```

---

## Step 10 – Monitor Auto Scaling Activities

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
echo "To monitor in real-time, run these commands:"
echo ""
echo "Watch scaling activities:"
echo "  watch -n 10 'aws autoscaling describe-scaling-activities --auto-scaling-group-name $ASG_NAME --max-records 5 --region $REGION --output table'"
echo ""
echo "Watch instance count:"
echo "  watch -n 10 'aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names $ASG_NAME --region $REGION --query \"AutoScalingGroups[0].Instances[*].[InstanceId,LifecycleState,HealthStatus]\" --output table'"
echo ""
echo "Watch CloudWatch metrics:"
echo "  watch -n 10 'aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUUtilization --dimensions Name=AutoScalingGroupName,Value=$ASG_NAME --start-time \$(date -u -d \"10 minutes ago\" +%Y-%m-%dT%H:%M:%S) --end-time \$(date -u +%Y-%m-%dT%H:%M:%S) --period 60 --statistics Average --region $REGION --query \"Datapoints[-5:]\" --output table'"
```

---

## Step 11 – View CloudWatch Metrics

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

## Step 12 – Cleanup Resources

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

aws autoscaling delete-policy \
  --auto-scaling-group-name "$ASG_NAME" \
  --policy-name "high-cpu-step-scaling" \
  --region "$REGION" 2>/dev/null || true

aws autoscaling delete-policy \
  --auto-scaling-group-name "$ASG_NAME" \
  --policy-name "low-cpu-scale-in" \
  --region "$REGION" 2>/dev/null || true

# Delete CloudWatch alarms
echo "Deleting CloudWatch alarms..."
aws cloudwatch delete-alarms \
  --alarm-names "${ASG_NAME}-HighCPU-StepScaling" "${ASG_NAME}-LowCPU-ScaleIn" \
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
rm -f asg-userdata.sh generate-load.sh

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- Auto Scaling Group"
echo "- Launch Template"
echo "- Scaling policies (3)"
echo "- CloudWatch alarms (2)"
echo "- Scheduled actions (2)"
echo "- Security group"
echo "- Local files"
```

---

## Summary

In this lab, you have:
- Created Launch Template with user data for web server and load testing
- Created Auto Scaling Group across multiple availability zones
- Configured target-tracking scaling policy based on CPU utilization
- Set up step-scaling policies with CloudWatch alarms
- Created scheduled scaling actions for predictable load patterns
- Tested auto scaling behavior with load generation
- Monitored scaling activities and CloudWatch metrics
- Cleaned up all resources

**Key Takeaways:**
- **Auto Scaling**: Automatically adjusts capacity based on demand
- **Target Tracking**: Maintains specific metric at target value (e.g., 40% CPU)
- **Step Scaling**: Scales in steps based on alarm thresholds
- **Scheduled Scaling**: Scales based on predictable time patterns
- **CloudWatch Integration**: Alarms trigger scaling actions
- **Health Checks**: Unhealthy instances automatically replaced
- **Multi-AZ**: High availability across availability zones
- **Cost Optimization**: Scale down during low demand periods

**Scaling Policy Types:**
| Policy Type | Use Case | Response Time | Best For |
|-------------|----------|---------------|----------|
| **Target Tracking** | Maintain metric at target | Moderate | CPU, requests/target |
| **Step Scaling** | Aggressive scaling | Fast | Sudden spikes |
| **Scheduled** | Predictable patterns | Proactive | Daily/weekly patterns |
| **Simple Scaling** | Single adjustment | Slow | Basic use cases |

**Best Practices:**
- Use target-tracking for most common metrics (CPU, ALB requests)
- Set appropriate cooldown periods to avoid flapping
- Configure health check grace period for slow-starting applications
- Use multiple AZs for high availability
- Monitor CloudWatch metrics and alarms regularly
- Test scaling policies under controlled load
- Set meaningful min/max capacity limits
- Use lifecycle hooks for graceful instance termination
- Enable detailed monitoring for faster response
- Tag instances for cost tracking and management

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
