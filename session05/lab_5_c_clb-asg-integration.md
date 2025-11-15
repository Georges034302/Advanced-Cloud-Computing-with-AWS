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
# Set region and resource names
REGION="ap-southeast-2"
CLB_NAME="lab-clb-asg"
LAUNCH_TEMPLATE_NAME="lab-clb-asg-template"
ASG_NAME="lab-clb-asg-group"
SG_NAME="lab-clb-asg-sg"
MIN_SIZE=2
MAX_SIZE=4
DESIRED_CAPACITY=2

# Get default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region "$REGION")
echo "VPC_ID=$VPC_ID"

# Get availability zones and subnets
AZS=$(aws ec2 describe-availability-zones \
  --region "$REGION" \
  --query 'AvailabilityZones[0:2].ZoneName' \
  --output text)
AZ1=$(echo "$AZS" | awk '{print $1}')
AZ2=$(echo "$AZS" | awk '{print $2}')

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

# Allow HTTP traffic from anywhere
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"
```

---

## Step 3 – Create Classic Load Balancer

```bash
# Create Classic Load Balancer
aws elb create-load-balancer \
  --load-balancer-name "$CLB_NAME" \
  --listeners "Protocol=HTTP,LoadBalancerPort=80,InstanceProtocol=HTTP,InstancePort=80" \
  --subnets "$SUBNET1" "$SUBNET2" \
  --security-groups "$SG_ID" \
  --region "$REGION"

# Configure health check (Target: /health.html, Interval: 30s, Timeout: 5s)
aws elb configure-health-check \
  --load-balancer-name "$CLB_NAME" \
  --health-check \
    Target=HTTP:80/health.html,\
Interval=30,\
Timeout=5,\
UnhealthyThreshold=2,\
HealthyThreshold=2 \
  --region "$REGION"

# Get CLB DNS name
CLB_DNS=$(aws elb describe-load-balancers \
  --load-balancer-names "$CLB_NAME" \
  --query 'LoadBalancerDescriptions[0].DNSName' \
  --output text \
  --region "$REGION")
echo "CLB_DNS=$CLB_DNS"
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
```

---

## Step 6 – Create Auto Scaling Group with CLB

```bash
# Create Auto Scaling Group with CLB integration
# Health Check Type: ELB (uses load balancer health checks)
# Grace Period: 300 seconds for instance startup
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
```

---

## Step 7 – Wait for Instances and Verify Health

```bash
# Wait for instances to launch and become healthy (3-5 minutes)
sleep 60

# Check ASG status
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[0].{Name:AutoScalingGroupName,Desired:DesiredCapacity,Current:length(Instances),MinSize:MinSize,MaxSize:MaxSize}' \
  --output table \
  --region "$REGION"

# List instances in ASG
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[0].Instances[*].{InstanceId:InstanceId,HealthStatus:HealthStatus,LifecycleState:LifecycleState,AZ:AvailabilityZone}' \
  --output table \
  --region "$REGION"

# Wait for instances to pass CLB health checks
sleep 120

# Check CLB instance health
aws elb describe-instance-health \
  --load-balancer-name "$CLB_NAME" \
  --query 'InstanceStates[*].{InstanceId:InstanceId,State:State,ReasonCode:ReasonCode}' \
  --output table \
  --region "$REGION"
```

---

## Step 8 – Test Load Distribution

```bash
# Test load distribution across instances (10 requests)
echo "Testing load distribution: http://${CLB_DNS}"
for i in {1..10}; do
  echo -n "Request $i: "
  curl -s "http://${CLB_DNS}" | grep -oP 'Instance ID:</strong> \K[^<]+'
  sleep 1
done

# Open in browser
"$BROWSER" "http://${CLB_DNS}"
```

---

## Step 9 – Configure Target Tracking Scaling Policy

```bash
# Create target tracking scaling policy (40% CPU)
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

# Stop instance to simulate failure
# ASG will detect unhealthy instance via CLB health check and launch replacement
aws ec2 stop-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

# Monitor replacement activity (wait 5 minutes, then check)
echo "Monitor scaling activities:"
echo "  aws autoscaling describe-scaling-activities --auto-scaling-group-name $ASG_NAME --max-records 5 --region $REGION"
```

---

## Step 11 – Monitor CLB and ASG Metrics

```bash
# Get CLB healthy host count (last 5 minutes)
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

# Get CLB request count (last 5 minutes)
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
```

---

## Step 12 – View Scaling Activities

```bash
# View recent scaling activities
aws autoscaling describe-scaling-activities \
  --auto-scaling-group-name "$ASG_NAME" \
  --max-records 5 \
  --query 'Activities[*].{Time:StartTime,Status:StatusCode,Description:Description,Cause:Cause}' \
  --output table \
  --region "$REGION"

# View current ASG status
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[0].{Name:AutoScalingGroupName,Desired:DesiredCapacity,Min:MinSize,Max:MaxSize,InService:length(Instances[?LifecycleState==`InService`])}' \
  --output table \
  --region "$REGION"
```

---

## Step 13 – Cleanup Resources

```bash
# Delete Auto Scaling Group
aws autoscaling delete-auto-scaling-group \
  --auto-scaling-group-name "$ASG_NAME" \
  --force-delete \
  --region "$REGION"

sleep 30

# Delete Launch Template
aws ec2 delete-launch-template \
  --launch-template-name "$LAUNCH_TEMPLATE_NAME" \
  --region "$REGION"

# Delete Classic Load Balancer
aws elb delete-load-balancer \
  --load-balancer-name "$CLB_NAME" \
  --region "$REGION"

sleep 10

# Delete Security Group
aws ec2 delete-security-group \
  --group-id "$SG_ID" \
  --region "$REGION"

# Delete local files
rm -f clb-asg-userdata.sh

echo "✅ Cleanup completed"
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
