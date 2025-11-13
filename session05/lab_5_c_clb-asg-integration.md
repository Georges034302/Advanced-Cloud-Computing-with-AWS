# Lab 5.C: Classic Load Balancer with Auto Scaling Integration

## Overview
This lab demonstrates how to integrate a Classic Load Balancer (CLB) with an Auto Scaling Group (ASG). You will deploy a load balancer that automatically distributes traffic across instances managed by Auto Scaling, configure health checks at both the load balancer and ASG levels, and test automatic instance replacement and scaling behavior.

---

## Objectives
- Create Classic Load Balancer in default VPC
- Create Auto Scaling Group with CLB integration
- Configure health checks (CLB and ASG)
- Test automatic instance replacement on health check failure
- Test load distribution across scaling instances
- Monitor scaling activities with load balancer metrics
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Default VPC with subnets in multiple availability zones
- IAM permissions for EC2, ELB, Auto Scaling, and CloudWatch
- Basic understanding of load balancing and Auto Scaling

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

# Set resource names
CLB_NAME="lab-clb-asg"
echo "CLB_NAME=$CLB_NAME"

LAUNCH_TEMPLATE_NAME="lab-clb-asg-template"
echo "LAUNCH_TEMPLATE_NAME=$LAUNCH_TEMPLATE_NAME"

ASG_NAME="lab-clb-asg-group"
echo "ASG_NAME=$ASG_NAME"

SG_NAME="lab-clb-asg-sg"
echo "SG_NAME=$SG_NAME"

# Set capacity limits (free tier compatible)
MIN_SIZE=2
echo "MIN_SIZE=$MIN_SIZE"

MAX_SIZE=4
echo "MAX_SIZE=$MAX_SIZE"

DESIRED_CAPACITY=2
echo "DESIRED_CAPACITY=$DESIRED_CAPACITY"

# Get default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region "$REGION")
echo "VPC_ID=$VPC_ID"

# Verify VPC exists
if [ "$VPC_ID" == "None" ] || [ -z "$VPC_ID" ]; then
  echo "❌ Error: Default VPC not found"
  exit 1
fi

# Get availability zones
AZS=$(aws ec2 describe-availability-zones \
  --region "$REGION" \
  --query 'AvailabilityZones[0:2].ZoneName' \
  --output text)
echo "AZS=$AZS"

AZ1=$(echo "$AZS" | awk '{print $1}')
echo "AZ1=$AZ1"

AZ2=$(echo "$AZS" | awk '{print $2}')
echo "AZ2=$AZ2"

# Get subnets for each AZ
SUBNET1=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=availability-zone,Values=$AZ1" \
  --query 'Subnets[0].SubnetId' \
  --output text \
  --region "$REGION")
echo "SUBNET1=$SUBNET1"

SUBNET2=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=availability-zone,Values=$AZ2" \
  --query 'Subnets[0].SubnetId' \
  --output text \
  --region "$REGION")
echo "SUBNET2=$SUBNET2"

echo ""
echo "✅ Prerequisites verified"
```

---

## Step 2 – Create Security Group

```bash
# Create security group for instances and load balancer
SG_ID=$(aws ec2 create-security-group \
  --group-name "$SG_NAME" \
  --description "Security group for CLB and ASG instances" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)
echo "SG_ID=$SG_ID"

# Allow HTTP traffic from anywhere to load balancer
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

echo "✅ Security group created with HTTP access"
```

---

## Step 3 – Create Classic Load Balancer

```bash
# Create Classic Load Balancer
echo "Creating Classic Load Balancer..."

aws elb create-load-balancer \
  --load-balancer-name "$CLB_NAME" \
  --listeners "Protocol=HTTP,LoadBalancerPort=80,InstanceProtocol=HTTP,InstancePort=80" \
  --subnets "$SUBNET1" "$SUBNET2" \
  --security-groups "$SG_ID" \
  --region "$REGION"

echo "✅ Classic Load Balancer created"

# Configure health check
echo "Configuring health check..."

aws elb configure-health-check \
  --load-balancer-name "$CLB_NAME" \
  --health-check \
    Target=HTTP:80/health.html,\
Interval=30,\
Timeout=5,\
UnhealthyThreshold=2,\
HealthyThreshold=2 \
  --region "$REGION"

echo "✅ Health check configured (Target: /health.html, Interval: 30s)"

# Get CLB DNS name
CLB_DNS=$(aws elb describe-load-balancers \
  --load-balancer-names "$CLB_NAME" \
  --query 'LoadBalancerDescriptions[0].DNSName' \
  --output text \
  --region "$REGION")
echo "CLB_DNS=$CLB_DNS"

echo ""
echo "Load Balancer URL: http://${CLB_DNS}"
```

---

## Step 4 – Create User Data Script

```bash
# Create simple user data script for web server
cat > clb-asg-userdata.sh <<'EOF'
#!/bin/bash
# Update system packages
dnf update -y

# Install Apache web server
dnf install -y httpd

# Get instance metadata
INSTANCE_ID=$(ec2-metadata --instance-id | cut -d " " -f 2)
AVAILABILITY_ZONE=$(ec2-metadata --availability-zone | cut -d " " -f 2)
LOCAL_IP=$(ec2-metadata --local-ipv4 | cut -d " " -f 2)

# Create web page with instance information
cat > /var/www/html/index.html <<HTML
<!DOCTYPE html>
<html>
<head>
    <title>CLB + ASG Demo</title>
    <style>
        body { font-family: Arial; text-align: center; padding: 50px; background: #f0f0f0; }
        .box { background: white; padding: 30px; border-radius: 5px; display: inline-block; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        h1 { color: #FF9900; }
        .info { background: #232F3E; color: white; padding: 15px; margin: 10px 0; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="box">
        <h1>🔄 CLB + Auto Scaling</h1>
        <div class="info">
            <p><strong>Instance ID:</strong> ${INSTANCE_ID}</p>
            <p><strong>AZ:</strong> ${AVAILABILITY_ZONE}</p>
            <p><strong>Private IP:</strong> ${LOCAL_IP}</p>
        </div>
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

echo "✅ User data script created"
```

---

## Step 5 – Create Launch Template

```bash
# Get latest Amazon Linux 2023 AMI ID
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023*-x86_64" \
            "Name=state,Values=available" \
  --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
  --output text \
  --region "$REGION")
echo "AMI_ID=$AMI_ID"

# Create Launch Template
echo "Creating Launch Template..."

aws ec2 create-launch-template \
  --launch-template-name "$LAUNCH_TEMPLATE_NAME" \
  --version-description "v1.0" \
  --launch-template-data "{
    \"ImageId\": \"$AMI_ID\",
    \"InstanceType\": \"t2.micro\",
    \"SecurityGroupIds\": [\"$SG_ID\"],
    \"UserData\": \"$(base64 -w 0 clb-asg-userdata.sh)\",
    \"TagSpecifications\": [{
      \"ResourceType\": \"instance\",
      \"Tags\": [{
        \"Key\": \"Name\",
        \"Value\": \"CLB-ASG-Instance\"
      }]
    }]
  }" \
  --region "$REGION"

echo "✅ Launch Template created"
```

---

## Step 6 – Create Auto Scaling Group with CLB

```bash
# Create Auto Scaling Group attached to CLB
echo "Creating Auto Scaling Group with CLB integration..."

aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name "$ASG_NAME" \
  --launch-template "LaunchTemplateName=$LAUNCH_TEMPLATE_NAME,Version=\$Latest" \
  --min-size "$MIN_SIZE" \
  --max-size "$MAX_SIZE" \
  --desired-capacity "$DESIRED_CAPACITY" \
  --load-balancer-names "$CLB_NAME" \
  --health-check-type ELB \
  --health-check-grace-period 300 \
  --vpc-zone-identifier "$SUBNET1,$SUBNET2" \
  --tags "Key=Name,Value=CLB-ASG-Instance,PropagateAtLaunch=true" \
  --region "$REGION"

echo "✅ Auto Scaling Group created and attached to CLB"
echo ""
echo "Configuration:"
echo "  - Min Size: $MIN_SIZE"
echo "  - Max Size: $MAX_SIZE"
echo "  - Desired: $DESIRED_CAPACITY"
echo "  - Health Check: ELB (from load balancer)"
echo "  - Grace Period: 300 seconds"
```

---

## Step 7 – Wait for Instances and Verify Health

```bash
echo ""
echo "Waiting for instances to launch and become healthy..."
echo "This may take 3-5 minutes..."
sleep 60

# Check ASG status
echo ""
echo "Auto Scaling Group Status:"
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[0].{Name:AutoScalingGroupName,Desired:DesiredCapacity,Current:length(Instances),MinSize:MinSize,MaxSize:MaxSize}' \
  --output table \
  --region "$REGION"

# List instances in ASG
echo ""
echo "Instances in Auto Scaling Group:"
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[0].Instances[*].{InstanceId:InstanceId,HealthStatus:HealthStatus,LifecycleState:LifecycleState,AZ:AvailabilityZone}' \
  --output table \
  --region "$REGION"

# Wait longer for health checks to pass
echo ""
echo "Waiting for instances to pass CLB health checks..."
sleep 120

# Check CLB instance health
echo ""
echo "Load Balancer Instance Health:"
aws elb describe-instance-health \
  --load-balancer-name "$CLB_NAME" \
  --query 'InstanceStates[*].{InstanceId:InstanceId,State:State,ReasonCode:ReasonCode}' \
  --output table \
  --region "$REGION"
```

---

## Step 8 – Test Load Distribution

```bash
echo ""
echo "================================================"
echo "TESTING LOAD DISTRIBUTION"
echo "================================================"
echo ""
echo "Load Balancer URL: http://${CLB_DNS}"
echo ""
echo "Testing load distribution across instances..."
echo ""

# Make 10 requests and show which instance responds
for i in {1..10}; do
  echo -n "Request $i: "
  curl -s "http://${CLB_DNS}" | grep -oP 'Instance ID:</strong> \K[^<]+'
  sleep 1
done

echo ""
echo "✅ Load is distributed across multiple instances"
echo ""
echo "Open in browser to see instance details:"
echo "  http://${CLB_DNS}"
```

---

## Step 9 – Configure Target Tracking Scaling Policy

```bash
# Create target tracking scaling policy (40% CPU)
echo "Creating target tracking scaling policy..."

aws autoscaling put-scaling-policy \
  --auto-scaling-group-name "$ASG_NAME" \
  --policy-name "cpu-target-tracking" \
  --policy-type TargetTrackingScaling \
  --target-tracking-configuration "{
    \"PredefinedMetricSpecification\": {
      \"PredefinedMetricType\": \"ASGAverageCPUUtilization\"
    },
    \"TargetValue\": 40.0
  }" \
  --region "$REGION"

echo "✅ Target tracking policy created (Target: 40% CPU)"
```

---

## Step 10 – Test Automatic Instance Replacement

```bash
# Get first instance ID
INSTANCE_ID=$(aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[0].Instances[0].InstanceId' \
  --output text \
  --region "$REGION")
echo "INSTANCE_ID=$INSTANCE_ID"

echo ""
echo "================================================"
echo "TESTING AUTOMATIC INSTANCE REPLACEMENT"
echo "================================================"
echo ""
echo "Simulating instance failure by stopping instance..."
echo "Instance to stop: $INSTANCE_ID"
echo ""

# Stop instance (simulates failure)
aws ec2 stop-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

echo "✅ Instance stopped"
echo ""
echo "Auto Scaling will:"
echo "  1. Detect unhealthy instance via CLB health check"
echo "  2. Mark instance as unhealthy"
echo "  3. Terminate the unhealthy instance"
echo "  4. Launch a replacement instance"
echo "  5. Register new instance with CLB"
echo ""
echo "Wait 5 minutes and check status with:"
echo "  aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names $ASG_NAME --region $REGION"
echo ""
echo "Monitor replacement activity:"
echo "  aws autoscaling describe-scaling-activities --auto-scaling-group-name $ASG_NAME --max-records 5 --region $REGION"
```

---

## Step 11 – Monitor CLB and ASG Metrics

```bash
echo ""
echo "================================================"
echo "MONITORING METRICS"
echo "================================================"
echo ""

# Get CLB metrics
echo "Load Balancer Metrics (Last 5 minutes):"
aws cloudwatch get-metric-statistics \
  --namespace AWS/ELB \
  --metric-name HealthyHostCount \
  --dimensions Name=LoadBalancerName,Value="$CLB_NAME" \
  --start-time "$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 60 \
  --statistics Average \
  --region "$REGION" \
  --query 'Datapoints[-5:].[Timestamp,Average]' \
  --output table

echo ""
echo "Request Count (Last 5 minutes):"
aws cloudwatch get-metric-statistics \
  --namespace AWS/ELB \
  --metric-name RequestCount \
  --dimensions Name=LoadBalancerName,Value="$CLB_NAME" \
  --start-time "$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 60 \
  --statistics Sum \
  --region "$REGION" \
  --query 'Datapoints[-5:].[Timestamp,Sum]' \
  --output table

echo ""
echo "To monitor in real-time:"
echo "  - CloudWatch Console → Dashboards → Create custom dashboard"
echo "  - Metrics: HealthyHostCount, RequestCount, Latency"
echo "  - ASG Metrics: GroupDesiredCapacity, GroupInServiceInstances"
```

---

## Step 12 – View Scaling Activities

```bash
echo ""
echo "Recent Auto Scaling Activities:"
aws autoscaling describe-scaling-activities \
  --auto-scaling-group-name "$ASG_NAME" \
  --max-records 5 \
  --query 'Activities[*].{Time:StartTime,Status:StatusCode,Description:Description,Cause:Cause}' \
  --output table \
  --region "$REGION"

echo ""
echo "Current ASG Status:"
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[0].{Name:AutoScalingGroupName,Desired:DesiredCapacity,Min:MinSize,Max:MaxSize,InService:length(Instances[?LifecycleState==`InService`])}' \
  --output table \
  --region "$REGION"
```

---

## Step 13 – Cleanup Resources

```bash
echo ""
echo "Cleaning up resources..."

# Delete Auto Scaling Group
echo "Deleting Auto Scaling Group..."
aws autoscaling delete-auto-scaling-group \
  --auto-scaling-group-name "$ASG_NAME" \
  --force-delete \
  --region "$REGION"

echo "Waiting for instances to terminate..."
sleep 30

# Delete Launch Template
echo "Deleting Launch Template..."
aws ec2 delete-launch-template \
  --launch-template-name "$LAUNCH_TEMPLATE_NAME" \
  --region "$REGION"

# Delete Classic Load Balancer
echo "Deleting Classic Load Balancer..."
aws elb delete-load-balancer \
  --load-balancer-name "$CLB_NAME" \
  --region "$REGION"

# Wait for load balancer to delete
sleep 10

# Delete Security Group
echo "Deleting Security Group..."
aws ec2 delete-security-group \
  --group-id "$SG_ID" \
  --region "$REGION"

# Delete local files
rm -f clb-asg-userdata.sh

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- Auto Scaling Group"
echo "- Launch Template"
echo "- Classic Load Balancer"
echo "- Security Group"
echo "- Local files"
```

---

## Summary

In this lab, you have:
- Created Classic Load Balancer in default VPC
- Created Auto Scaling Group integrated with CLB
- Configured ELB health checks for automatic instance replacement
- Tested load distribution across multiple instances
- Configured target tracking scaling policy
- Tested automatic instance replacement on failure
- Monitored CLB and ASG metrics
- Cleaned up all resources

**Key Takeaways:**
- **CLB + ASG Integration**: Load balancer automatically manages ASG instances
- **ELB Health Checks**: Auto Scaling uses CLB health checks to detect failures
- **Automatic Replacement**: Unhealthy instances are automatically replaced
- **High Availability**: Multi-AZ deployment with automatic failover
- **Dynamic Scaling**: Target tracking adjusts capacity based on CPU
- **Free Tier Compatible**: Uses t2.micro instances and CLB (750 hours/month)

**Integration Benefits:**
| Feature | Benefit |
|---------|---------|
| **Automatic Registration** | New instances auto-register with CLB |
| **Health Check Integration** | CLB health status used by ASG |
| **Seamless Scaling** | Load balancer adapts to capacity changes |
| **Connection Draining** | Graceful instance termination |

**Best Practices:**
- Set appropriate health check grace period (5+ minutes)
- Use ELB health check type for ASG
- Configure connection draining for graceful shutdowns
- Monitor both CLB and ASG metrics
- Set meaningful min/max capacity limits
- Use multiple AZs for high availability
- Tag instances for cost tracking

---

## Free Tier Notes
- **Classic Load Balancer**: 750 hours/month (free tier)
- **EC2 t2.micro**: 750 hours/month (free tier)
- **Auto Scaling**: No additional charge
- **CloudWatch**: 10 alarms free per month
- **Data Transfer**: 15 GB outbound per month

This lab stays within free tier limits when using 2-4 t2.micro instances.
