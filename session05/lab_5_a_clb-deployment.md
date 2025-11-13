# Lab 5.A: Deploy Web Application Behind Classic Load Balancer

## Overview
This lab demonstrates how to deploy a simple web application behind an AWS Classic Load Balancer (CLB). Classic Load Balancers are included in the AWS Free Tier (750 hours/month), making this an ideal lab for learning load balancing concepts without incurring costs. You will create a CLB, launch multiple EC2 instances, configure health checks, and test load distribution.

**Note:** While Application Load Balancers (ALB) are more modern and feature-rich, they are NOT included in the free tier. This lab uses Classic Load Balancer which is free tier eligible and still widely used in production.

---

## Objectives
- Create Classic Load Balancer in default VPC
- Launch multiple EC2 instances running simple web servers
- Configure security groups for load balancer and instances
- Set up health checks to monitor instance status
- Test load distribution across multiple instances
- Verify failover when instances become unhealthy
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Default VPC with public subnets in multiple availability zones
- IAM permissions to manage EC2 and ELB resources
- Basic understanding of load balancing concepts

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

# Get first two availability zones
AZ_1=$(echo "$AVAILABILITY_ZONES" | awk '{print $1}')
echo "AZ_1=$AZ_1"

AZ_2=$(echo "$AVAILABILITY_ZONES" | awk '{print $2}')
echo "AZ_2=$AZ_2"

# Get subnet IDs for each AZ
SUBNET_1=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=availability-zone,Values=$AZ_1" \
  --query 'Subnets[0].SubnetId' \
  --output text \
  --region "$REGION")
echo "SUBNET_1=$SUBNET_1"

SUBNET_2=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=availability-zone,Values=$AZ_2" \
  --query 'Subnets[0].SubnetId' \
  --output text \
  --region "$REGION")
echo "SUBNET_2=$SUBNET_2"

# Verify AWS CLI is configured
aws sts get-caller-identity
```

---

## Step 2 – Create Security Groups

```bash
# Create security group for load balancer
ELB_SG_ID=$(aws ec2 create-security-group \
  --group-name "lab-elb-sg" \
  --description "Security group for Classic Load Balancer - HTTP access" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)
echo "ELB_SG_ID=$ELB_SG_ID"

# Allow HTTP access from anywhere to load balancer
aws ec2 authorize-security-group-ingress \
  --group-id "$ELB_SG_ID" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

echo "Load balancer security group created with HTTP access"

# Create security group for web server instances
WEB_SG_ID=$(aws ec2 create-security-group \
  --group-name "lab-web-sg" \
  --description "Security group for web servers - allow from ELB only" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)
echo "WEB_SG_ID=$WEB_SG_ID"

# Allow HTTP access only from load balancer security group
aws ec2 authorize-security-group-ingress \
  --group-id "$WEB_SG_ID" \
  --protocol tcp \
  --port 80 \
  --source-group "$ELB_SG_ID" \
  --region "$REGION"

# Allow SSH access for troubleshooting (optional - restrict to your IP in production)
aws ec2 authorize-security-group-ingress \
  --group-id "$WEB_SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

echo "Web server security group created"

# Describe security groups
aws ec2 describe-security-groups \
  --group-ids "$ELB_SG_ID" "$WEB_SG_ID" \
  --query 'SecurityGroups[*].{GroupId:GroupId,GroupName:GroupName,Description:Description}' \
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

## Step 4 – Launch EC2 Instances in Multiple Availability Zones

```bash
# Create user data script for web server
cat > web-server-userdata.sh <<'EOF'
#!/bin/bash
# Update system
dnf update -y

# Install Apache web server
dnf install -y httpd

# Get instance metadata
INSTANCE_ID=$(ec2-metadata --instance-id | cut -d " " -f 2)
AVAILABILITY_ZONE=$(ec2-metadata --availability-zone | cut -d " " -f 2)
LOCAL_IP=$(ec2-metadata --local-ipv4 | cut -d " " -f 2)

# Create custom web page showing instance details
cat > /var/www/html/index.html <<HTML
<!DOCTYPE html>
<html>
<head>
    <title>Load Balancer Demo</title>
    <style>
        body { font-family: Arial; text-align: center; padding: 50px; background: #f0f0f0; }
        .container { background: white; padding: 30px; border-radius: 10px; display: inline-block; }
        h1 { color: #FF9900; }
        .info { background: #232F3E; color: white; padding: 15px; margin: 10px; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Load Balancer Demo</h1>
        <div class="info">
            <h2>Instance: ${INSTANCE_ID}</h2>
            <p>Availability Zone: ${AVAILABILITY_ZONE}</p>
            <p>Private IP: ${LOCAL_IP}</p>
        </div>
        <p>Refresh this page to see load distribution across instances</p>
    </div>
</body>
</html>
HTML

# Start and enable Apache
systemctl start httpd
systemctl enable httpd

# Create health check endpoint
echo "OK" > /var/www/html/health.html

echo "Web server setup completed" > /var/log/userdata-complete.log
EOF

echo "User data script created"

# Launch first instance in AZ1
echo "Launching instance 1 in $AZ_1..."

INSTANCE_1_OUTPUT=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --subnet-id "$SUBNET_1" \
  --security-group-ids "$WEB_SG_ID" \
  --user-data file://web-server-userdata.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=web-server-1},{Key=Lab,Value=5A}]" \
  --count 1 \
  --region "$REGION")

INSTANCE_1_ID=$(echo "$INSTANCE_1_OUTPUT" | jq -r '.Instances[0].InstanceId')
echo "INSTANCE_1_ID=$INSTANCE_1_ID"

# Launch second instance in AZ2
echo "Launching instance 2 in $AZ_2..."

INSTANCE_2_OUTPUT=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --subnet-id "$SUBNET_2" \
  --security-group-ids "$WEB_SG_ID" \
  --user-data file://web-server-userdata.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=web-server-2},{Key=Lab,Value=5A}]" \
  --count 1 \
  --region "$REGION")

INSTANCE_2_ID=$(echo "$INSTANCE_2_OUTPUT" | jq -r '.Instances[0].InstanceId')
echo "INSTANCE_2_ID=$INSTANCE_2_ID"

# Wait for both instances to be running
echo "Waiting for instances to be running..."
aws ec2 wait instance-running \
  --instance-ids "$INSTANCE_1_ID" "$INSTANCE_2_ID" \
  --region "$REGION"

echo "✅ Both instances are now running!"

# Get instance details
aws ec2 describe-instances \
  --instance-ids "$INSTANCE_1_ID" "$INSTANCE_2_ID" \
  --query 'Reservations[*].Instances[*].{InstanceId:InstanceId,State:State.Name,AZ:Placement.AvailabilityZone,PublicIP:PublicIpAddress,PrivateIP:PrivateIpAddress}' \
  --output table \
  --region "$REGION"

echo ""
echo "Wait 2-3 minutes for web servers to complete initialization"
```

---

## Step 5 – Create Classic Load Balancer

```bash
# Create Classic Load Balancer across both availability zones
echo "Creating Classic Load Balancer..."

ELB_NAME="lab-web-clb"

aws elb create-load-balancer \
  --load-balancer-name "$ELB_NAME" \
  --listeners "Protocol=HTTP,LoadBalancerPort=80,InstanceProtocol=HTTP,InstancePort=80" \
  --subnets "$SUBNET_1" "$SUBNET_2" \
  --security-groups "$ELB_SG_ID" \
  --region "$REGION"

echo "Classic Load Balancer created"

# Get load balancer DNS name
ELB_DNS=$(aws elb describe-load-balancers \
  --load-balancer-names "$ELB_NAME" \
  --query 'LoadBalancerDescriptions[0].DNSName' \
  --output text \
  --region "$REGION")
echo "ELB_DNS=$ELB_DNS"

# Display load balancer details
aws elb describe-load-balancers \
  --load-balancer-names "$ELB_NAME" \
  --query 'LoadBalancerDescriptions[0].{Name:LoadBalancerName,DNS:DNSName,Subnets:Subnets,SecurityGroups:SecurityGroups}' \
  --output json \
  --region "$REGION" | jq '.'
```

---

## Step 6 – Configure Health Check

```bash
# Configure health check for instances
echo "Configuring health check..."

aws elb configure-health-check \
  --load-balancer-name "$ELB_NAME" \
  --health-check "Target=HTTP:80/health.html,Interval=30,Timeout=5,UnhealthyThreshold=2,HealthyThreshold=2" \
  --region "$REGION"

echo "Health check configured"

# Display health check settings
aws elb describe-load-balancers \
  --load-balancer-names "$ELB_NAME" \
  --query 'LoadBalancerDescriptions[0].HealthCheck' \
  --output json \
  --region "$REGION" | jq '.'
```

---

## Step 7 – Register Instances with Load Balancer

```bash
# Register both instances with the load balancer
echo "Registering instances with load balancer..."

aws elb register-instances-with-load-balancer \
  --load-balancer-name "$ELB_NAME" \
  --instances "$INSTANCE_1_ID" "$INSTANCE_2_ID" \
  --region "$REGION"

echo "Instances registered with load balancer"

# Check instance health status
echo ""
echo "Checking instance health (may take 1-2 minutes)..."
sleep 30

aws elb describe-instance-health \
  --load-balancer-name "$ELB_NAME" \
  --region "$REGION" \
  --query 'InstanceStates[*].{InstanceId:InstanceId,State:State,ReasonCode:ReasonCode,Description:Description}' \
  --output table

echo ""
echo "Wait for both instances to show 'InService' state"
echo "You can check status with:"
echo "  aws elb describe-instance-health --load-balancer-name $ELB_NAME --region $REGION"
```

---

## Step 8 – Test Load Balancer

```bash
echo ""
echo "================================================"
echo "LOAD BALANCER TESTING"
echo "================================================"
echo ""
echo "Load Balancer DNS: $ELB_DNS"
echo "Load Balancer URL: http://${ELB_DNS}"
echo ""
echo "Testing load distribution..."
echo ""

# Test load balancer multiple times to see different instances
for i in {1..6}; do
  echo "Request $i:"
  curl -s "http://${ELB_DNS}" | grep -E "(Instance:|Availability Zone:|Private IP:)" | sed 's/<[^>]*>//g' | sed 's/^[[:space:]]*//'
  echo "---"
  sleep 1
done

echo ""
echo "================================================"
echo ""
echo "Open in browser to see full page:"
echo "  http://${ELB_DNS}"
echo ""
echo "Refresh multiple times to see traffic distributed across instances"
```

---

## Step 9 – Test Failover Behavior

```bash
echo ""
echo "================================================"
echo "TESTING FAILOVER"
echo "================================================"
echo ""
echo "Simulating instance failure by stopping one instance..."

# Stop first instance to simulate failure
aws ec2 stop-instances \
  --instance-ids "$INSTANCE_1_ID" \
  --region "$REGION"

echo "Instance $INSTANCE_1_ID stopped"
echo ""
echo "Waiting for health check to detect failure (60-90 seconds)..."

# Wait and check health status
sleep 60

aws elb describe-instance-health \
  --load-balancer-name "$ELB_NAME" \
  --region "$REGION" \
  --query 'InstanceStates[*].{InstanceId:InstanceId,State:State,Description:Description}' \
  --output table

echo ""
echo "Testing load balancer (should only route to healthy instance)..."
echo ""

# Test that traffic only goes to healthy instance
for i in {1..3}; do
  echo "Request $i:"
  curl -s "http://${ELB_DNS}" | grep -E "Instance:" | sed 's/<[^>]*>//g' | sed 's/^[[:space:]]*//'
  echo "---"
  sleep 1
done

echo ""
echo "✅ Load balancer automatically routes traffic only to healthy instances"
echo ""
echo "Restarting stopped instance..."

# Restart the stopped instance
aws ec2 start-instances \
  --instance-ids "$INSTANCE_1_ID" \
  --region "$REGION"

echo "Instance restarted. It will rejoin the load balancer when healthy."
```

---

## Step 10 – View Load Balancer Metrics (Optional)

```bash
# Get CloudWatch metrics for load balancer
echo ""
echo "Retrieving CloudWatch metrics..."

# Get request count
aws cloudwatch get-metric-statistics \
  --namespace AWS/ELB \
  --metric-name RequestCount \
  --dimensions Name=LoadBalancerName,Value="$ELB_NAME" \
  --start-time "$(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Sum \
  --region "$REGION" \
  --query 'Datapoints[*].{Timestamp:Timestamp,Requests:Sum}' \
  --output table

# Get healthy host count
aws cloudwatch get-metric-statistics \
  --namespace AWS/ELB \
  --metric-name HealthyHostCount \
  --dimensions Name=LoadBalancerName,Value="$ELB_NAME" \
  --start-time "$(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Average \
  --region "$REGION" \
  --query 'Datapoints[*].{Timestamp:Timestamp,HealthyHosts:Average}' \
  --output table

# List available metrics
echo ""
echo "Available CloudWatch metrics for ELB:"
aws cloudwatch list-metrics \
  --namespace AWS/ELB \
  --dimensions Name=LoadBalancerName,Value="$ELB_NAME" \
  --region "$REGION" \
  --query 'Metrics[*].MetricName' \
  --output text | tr '\t' '\n' | sort -u
```

---

## Step 11 – Cleanup Resources

```bash
# Deregister instances from load balancer
echo "Deregistering instances from load balancer..."
aws elb deregister-instances-from-load-balancer \
  --load-balancer-name "$ELB_NAME" \
  --instances "$INSTANCE_1_ID" "$INSTANCE_2_ID" \
  --region "$REGION"

# Delete load balancer
echo "Deleting load balancer..."
aws elb delete-load-balancer \
  --load-balancer-name "$ELB_NAME" \
  --region "$REGION"

echo "Load balancer deleted"

# Terminate EC2 instances
echo "Terminating EC2 instances..."
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_1_ID" "$INSTANCE_2_ID" \
  --region "$REGION"

# Wait for instances to terminate
echo "Waiting for instances to terminate..."
aws ec2 wait instance-terminated \
  --instance-ids "$INSTANCE_1_ID" "$INSTANCE_2_ID" \
  --region "$REGION"

echo "Instances terminated"

# Delete security groups (wait a moment for dependencies to clear)
echo "Deleting security groups..."
sleep 10

aws ec2 delete-security-group \
  --group-id "$WEB_SG_ID" \
  --region "$REGION"

aws ec2 delete-security-group \
  --group-id "$ELB_SG_ID" \
  --region "$REGION"

# Delete local files
echo "Cleaning up local files..."
rm -f web-server-userdata.sh

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- Classic Load Balancer"
echo "- EC2 instances (2)"
echo "- Security groups (2)"
echo "- Local files"
```

---

## Summary

In this lab, you have:
- Created Classic Load Balancer (CLB) in default VPC across two availability zones
- Launched EC2 instances running Apache web servers in different AZs
- Configured security groups for load balancer and instances
- Set up health checks to monitor instance status
- Registered instances with load balancer
- Tested load distribution across multiple instances
- Simulated failover by stopping an instance
- Verified automatic traffic routing to healthy instances only
- Monitored load balancer metrics with CloudWatch

**Key Takeaways:**
- **Classic Load Balancer**: Free tier eligible (750 hours/month)
- **High Availability**: Distributes traffic across multiple AZs
- **Health Checks**: Automatically removes unhealthy instances from rotation
- **Automatic Failover**: Traffic redirected to healthy instances
- **Simple Configuration**: Easy to set up for basic load balancing needs
- **Cost Effective**: Free tier makes it ideal for learning and testing

**Classic Load Balancer vs Application Load Balancer:**
| Feature | Classic Load Balancer | Application Load Balancer |
|---------|----------------------|---------------------------|
| **Free Tier** | ✅ Yes (750 hrs/month) | ❌ No |
| **Protocol** | HTTP, HTTPS, TCP, SSL | HTTP, HTTPS only |
| **Path-based Routing** | ❌ No | ✅ Yes |
| **Host-based Routing** | ❌ No | ✅ Yes |
| **WebSocket** | ❌ No | ✅ Yes |
| **HTTP/2** | ❌ No | ✅ Yes |
| **Target Types** | EC2 instances only | EC2, IP, Lambda |
| **Use Case** | Simple load balancing | Modern applications |
| **Cost** | Lower | Higher |

**When to Use Classic Load Balancer:**
- ✅ Learning and testing (free tier)
- ✅ Simple applications with basic load balancing
- ✅ Legacy applications already using CLB
- ✅ TCP/SSL load balancing needed
- ✅ Budget-constrained projects

**When to Upgrade to ALB:**
- Modern microservices architectures
- Need path-based or host-based routing
- Container-based applications (ECS, EKS)
- Need advanced features (WebSocket, HTTP/2)
- Complex routing rules required

**Real-World Use Cases:**
- **Web Applications**: Distribute traffic across multiple web servers
- **High Availability**: Ensure application availability during instance failures
- **Multi-AZ Deployment**: Protect against availability zone failures
- **Scalability**: Add/remove instances based on demand
- **Maintenance**: Remove instances from rotation during updates

**Best Practices:**
- Deploy load balancer in at least two availability zones
- Configure meaningful health check endpoints
- Use security groups to restrict traffic (defense in depth)
- Monitor CloudWatch metrics for performance insights
- Set appropriate health check intervals (balance detection speed vs cost)
- Use Auto Scaling Groups for automatic instance management
- Enable access logs for troubleshooting (requires S3 bucket)
- Test failover behavior regularly

---

## Additional Resources
- [Classic Load Balancer User Guide](https://docs.aws.amazon.com/elasticloadbalancing/latest/classic/introduction.html)
- [AWS Free Tier Details](https://aws.amazon.com/free/)
- [ELB Health Checks](https://docs.aws.amazon.com/elasticloadbalancing/latest/classic/elb-healthchecks.html)
- [CloudWatch Metrics for ELB](https://docs.aws.amazon.com/elasticloadbalancing/latest/classic/elb-cloudwatch-metrics.html)
- [Elastic Load Balancing FAQs](https://aws.amazon.com/elasticloadbalancing/faqs/)

---
