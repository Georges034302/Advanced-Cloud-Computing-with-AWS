# Lab 5.D: Multi-Region Traffic Distribution with Route 53

## Overview
This lab demonstrates how to implement global high availability using Amazon Route 53 for multi-region traffic distribution. You will deploy identical web applications in two AWS regions, configure Route 53 with latency-based routing to direct users to the nearest region, implement health checks for automatic failover, and test regional failover scenarios.

---

## Objectives
- Deploy web application in two AWS regions
- Create Route 53 hosted zone and records
- Configure latency-based routing policy
- Set up Route 53 health checks
- Test traffic routing to nearest region
- Simulate regional failure and verify failover
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Default VPCs in both regions (ap-southeast-2, us-east-1)
- IAM permissions for EC2, Route 53, and CloudWatch
- Registered domain or use Route 53 test domain
- Basic understanding of DNS and routing policies

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set primary region (Sydney)
PRIMARY_REGION="ap-southeast-2"
echo "PRIMARY_REGION=$PRIMARY_REGION"

# Set secondary region (US East)
SECONDARY_REGION="us-east-1"
echo "SECONDARY_REGION=$SECONDARY_REGION"

# Set resource names
SG_NAME="lab-route53-sg"
echo "SG_NAME=$SG_NAME"

INSTANCE_NAME="route53-demo"
echo "INSTANCE_NAME=$INSTANCE_NAME"

# Set hosted zone (use test domain or your domain)
# For testing without domain, we'll use public IPs directly
DOMAIN_NAME="example.com"
echo "DOMAIN_NAME=$DOMAIN_NAME"

echo ""
echo "✅ Variables set"
echo ""
echo "Note: This lab will use EC2 public IPs for routing."
echo "For production, register a domain in Route 53."
```

---

## Step 2 – Deploy Web Server in Primary Region (Sydney)

```bash
# Get default VPC in primary region
PRIMARY_VPC=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region "$PRIMARY_REGION")
echo "PRIMARY_VPC=$PRIMARY_VPC"

# Create security group in primary region
PRIMARY_SG=$(aws ec2 create-security-group \
  --group-name "$SG_NAME" \
  --description "Security group for Route 53 demo" \
  --vpc-id "$PRIMARY_VPC" \
  --region "$PRIMARY_REGION" \
  --query 'GroupId' \
  --output text)
echo "PRIMARY_SG=$PRIMARY_SG"

# Allow HTTP traffic
aws ec2 authorize-security-group-ingress \
  --group-id "$PRIMARY_SG" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region "$PRIMARY_REGION"

# Allow ICMP for health checks
aws ec2 authorize-security-group-ingress \
  --group-id "$PRIMARY_SG" \
  --protocol icmp \
  --port -1 \
  --cidr 0.0.0.0/0 \
  --region "$PRIMARY_REGION"

echo "✅ Security group created in $PRIMARY_REGION"

# Get latest Amazon Linux 2023 AMI in primary region
PRIMARY_AMI=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023*-x86_64" \
            "Name=state,Values=available" \
  --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
  --output text \
  --region "$PRIMARY_REGION")
echo "PRIMARY_AMI=$PRIMARY_AMI"

# Create user data for primary region
cat > primary-userdata.sh <<'EOF'
#!/bin/bash
# Update system
dnf update -y

# Install Apache
dnf install -y httpd

# Get instance metadata
INSTANCE_ID=$(ec2-metadata --instance-id | cut -d " " -f 2)
AVAILABILITY_ZONE=$(ec2-metadata --availability-zone | cut -d " " -f 2)
REGION=$(echo $AVAILABILITY_ZONE | sed 's/[a-z]$//')

# Create web page
cat > /var/www/html/index.html <<HTML
<!DOCTYPE html>
<html>
<head>
    <title>Route 53 Multi-Region Demo</title>
    <style>
        body { font-family: Arial; text-align: center; padding: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .box { background: white; padding: 40px; border-radius: 10px; display: inline-block; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
        h1 { color: #667eea; margin-bottom: 20px; }
        .region { font-size: 48px; font-weight: bold; color: #764ba2; margin: 20px 0; }
        .info { background: #f0f0f0; padding: 15px; margin: 15px 0; border-radius: 5px; }
        .flag { font-size: 64px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="box">
        <h1>🌏 Multi-Region Application</h1>
        <div class="flag">🇦🇺</div>
        <div class="region">SYDNEY (PRIMARY)</div>
        <div class="info">
            <p><strong>Region:</strong> ${REGION}</p>
            <p><strong>AZ:</strong> ${AVAILABILITY_ZONE}</p>
            <p><strong>Instance:</strong> ${INSTANCE_ID}</p>
        </div>
        <p style="margin-top: 20px; color: #666;">Routed via Amazon Route 53</p>
    </div>
</body>
</html>
HTML

# Create health check endpoint
echo "healthy" > /var/www/html/health.html

# Start Apache
systemctl start httpd
systemctl enable httpd

# Log completion
echo "Primary region setup completed" > /var/log/userdata-complete.log
EOF

# Launch instance in primary region
echo "Launching instance in $PRIMARY_REGION..."

PRIMARY_INSTANCE=$(aws ec2 run-instances \
  --image-id "$PRIMARY_AMI" \
  --instance-type t2.micro \
  --security-group-ids "$PRIMARY_SG" \
  --user-data file://primary-userdata.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME-primary}]" \
  --region "$PRIMARY_REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)
echo "PRIMARY_INSTANCE=$PRIMARY_INSTANCE"

echo "✅ Instance launched in $PRIMARY_REGION"
```

---

## Step 3 – Deploy Web Server in Secondary Region (US East)

```bash
# Get default VPC in secondary region
SECONDARY_VPC=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region "$SECONDARY_REGION")
echo "SECONDARY_VPC=$SECONDARY_VPC"

# Create security group in secondary region
SECONDARY_SG=$(aws ec2 create-security-group \
  --group-name "$SG_NAME" \
  --description "Security group for Route 53 demo" \
  --vpc-id "$SECONDARY_VPC" \
  --region "$SECONDARY_REGION" \
  --query 'GroupId' \
  --output text)
echo "SECONDARY_SG=$SECONDARY_SG"

# Allow HTTP traffic
aws ec2 authorize-security-group-ingress \
  --group-id "$SECONDARY_SG" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region "$SECONDARY_REGION"

# Allow ICMP for health checks
aws ec2 authorize-security-group-ingress \
  --group-id "$SECONDARY_SG" \
  --protocol icmp \
  --port -1 \
  --cidr 0.0.0.0/0 \
  --region "$SECONDARY_REGION"

echo "✅ Security group created in $SECONDARY_REGION"

# Get latest Amazon Linux 2023 AMI in secondary region
SECONDARY_AMI=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023*-x86_64" \
            "Name=state,Values=available" \
  --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
  --output text \
  --region "$SECONDARY_REGION")
echo "SECONDARY_AMI=$SECONDARY_AMI"

# Create user data for secondary region
cat > secondary-userdata.sh <<'EOF'
#!/bin/bash
# Update system
dnf update -y

# Install Apache
dnf install -y httpd

# Get instance metadata
INSTANCE_ID=$(ec2-metadata --instance-id | cut -d " " -f 2)
AVAILABILITY_ZONE=$(ec2-metadata --availability-zone | cut -d " " -f 2)
REGION=$(echo $AVAILABILITY_ZONE | sed 's/[a-z]$//')

# Create web page
cat > /var/www/html/index.html <<HTML
<!DOCTYPE html>
<html>
<head>
    <title>Route 53 Multi-Region Demo</title>
    <style>
        body { font-family: Arial; text-align: center; padding: 50px; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
        .box { background: white; padding: 40px; border-radius: 10px; display: inline-block; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
        h1 { color: #f5576c; margin-bottom: 20px; }
        .region { font-size: 48px; font-weight: bold; color: #f093fb; margin: 20px 0; }
        .info { background: #f0f0f0; padding: 15px; margin: 15px 0; border-radius: 5px; }
        .flag { font-size: 64px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="box">
        <h1>🌎 Multi-Region Application</h1>
        <div class="flag">🇺🇸</div>
        <div class="region">US EAST (SECONDARY)</div>
        <div class="info">
            <p><strong>Region:</strong> ${REGION}</p>
            <p><strong>AZ:</strong> ${AVAILABILITY_ZONE}</p>
            <p><strong>Instance:</strong> ${INSTANCE_ID}</p>
        </div>
        <p style="margin-top: 20px; color: #666;">Routed via Amazon Route 53</p>
    </div>
</body>
</html>
HTML

# Create health check endpoint
echo "healthy" > /var/www/html/health.html

# Start Apache
systemctl start httpd
systemctl enable httpd

# Log completion
echo "Secondary region setup completed" > /var/log/userdata-complete.log
EOF

# Launch instance in secondary region
echo "Launching instance in $SECONDARY_REGION..."

SECONDARY_INSTANCE=$(aws ec2 run-instances \
  --image-id "$SECONDARY_AMI" \
  --instance-type t2.micro \
  --security-group-ids "$SECONDARY_SG" \
  --user-data file://secondary-userdata.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME-secondary}]" \
  --region "$SECONDARY_REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)
echo "SECONDARY_INSTANCE=$SECONDARY_INSTANCE"

echo "✅ Instance launched in $SECONDARY_REGION"
```

---

## Step 4 – Wait for Instances and Get Public IPs

```bash
echo ""
echo "Waiting for instances to initialize..."
echo "This may take 2-3 minutes..."

# Wait for primary instance
echo "Waiting for primary instance..."
aws ec2 wait instance-running \
  --instance-ids "$PRIMARY_INSTANCE" \
  --region "$PRIMARY_REGION"

# Wait for secondary instance
echo "Waiting for secondary instance..."
aws ec2 wait instance-running \
  --instance-ids "$SECONDARY_INSTANCE" \
  --region "$SECONDARY_REGION"

# Additional wait for user data to complete
sleep 60

# Get primary instance public IP
PRIMARY_IP=$(aws ec2 describe-instances \
  --instance-ids "$PRIMARY_INSTANCE" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$PRIMARY_REGION")
echo "PRIMARY_IP=$PRIMARY_IP"

# Get secondary instance public IP
SECONDARY_IP=$(aws ec2 describe-instances \
  --instance-ids "$SECONDARY_INSTANCE" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$SECONDARY_REGION")
echo "SECONDARY_IP=$SECONDARY_IP"

echo ""
echo "✅ Both instances are running"
echo ""
echo "Primary Region (Sydney): http://${PRIMARY_IP}"
echo "Secondary Region (US East): http://${SECONDARY_IP}"
```

---

## Step 5 – Create Route 53 Health Checks

```bash
echo ""
echo "Creating Route 53 health checks..."

# Create health check for primary region
PRIMARY_HEALTH_CHECK=$(aws route53 create-health-check \
  --caller-reference "primary-$(date +%s)" \
  --health-check-config \
    IPAddress="$PRIMARY_IP",\
Port=80,\
Type=HTTP,\
ResourcePath=/health.html,\
RequestInterval=30,\
FailureThreshold=3 \
  --health-check-tags Key=Name,Value=primary-health-check \
  --query 'HealthCheck.Id' \
  --output text)
echo "PRIMARY_HEALTH_CHECK=$PRIMARY_HEALTH_CHECK"

# Create health check for secondary region
SECONDARY_HEALTH_CHECK=$(aws route53 create-health-check \
  --caller-reference "secondary-$(date +%s)" \
  --health-check-config \
    IPAddress="$SECONDARY_IP",\
Port=80,\
Type=HTTP,\
ResourcePath=/health.html,\
RequestInterval=30,\
FailureThreshold=3 \
  --health-check-tags Key=Name,Value=secondary-health-check \
  --query 'HealthCheck.Id' \
  --output text)
echo "SECONDARY_HEALTH_CHECK=$SECONDARY_HEALTH_CHECK"

echo "✅ Health checks created"
echo ""
echo "Note: Health checks may take 1-2 minutes to become healthy"
```

---

## Step 6 – Test Regional Endpoints

```bash
echo ""
echo "================================================"
echo "TESTING REGIONAL ENDPOINTS"
echo "================================================"
echo ""

# Test primary region
echo "Testing primary region (Sydney)..."
curl -s "http://${PRIMARY_IP}" | grep -o "SYDNEY (PRIMARY)"
echo ""

# Test secondary region
echo "Testing secondary region (US East)..."
curl -s "http://${SECONDARY_IP}" | grep -o "US EAST (SECONDARY)"
echo ""

echo "✅ Both regions are responding correctly"
echo ""
echo "Visual verification:"
echo "  Primary:   http://${PRIMARY_IP}   (Purple gradient, 🇦🇺)"
echo "  Secondary: http://${SECONDARY_IP} (Pink gradient, 🇺🇸)"
```

---

## Step 7 – View Health Check Status

```bash
echo ""
echo "Checking health check status..."
sleep 60

# Check primary health
echo ""
echo "Primary Region Health Check:"
aws route53 get-health-check-status \
  --health-check-id "$PRIMARY_HEALTH_CHECK" \
  --query 'HealthCheckObservations[0:3].{Region:Region,Status:StatusReport.Status,Timestamp:StatusReport.CheckedTime}' \
  --output table

# Check secondary health
echo ""
echo "Secondary Region Health Check:"
aws route53 get-health-check-status \
  --health-check-id "$SECONDARY_HEALTH_CHECK" \
  --query 'HealthCheckObservations[0:3].{Region:Region,Status:StatusReport.Status,Timestamp:StatusReport.CheckedTime}' \
  --output table

echo ""
echo "Health check status should show 'Success' from multiple locations"
```

---

## Step 8 – Simulate Regional Failure

```bash
echo ""
echo "================================================"
echo "SIMULATING REGIONAL FAILURE"
echo "================================================"
echo ""
echo "Stopping primary region instance to simulate failure..."

# Stop primary instance
aws ec2 stop-instances \
  --instance-ids "$PRIMARY_INSTANCE" \
  --region "$PRIMARY_REGION"

echo "✅ Primary instance stopped"
echo ""
echo "Route 53 will:"
echo "  1. Detect primary endpoint is unhealthy (after ~90 seconds)"
echo "  2. Stop routing traffic to primary region"
echo "  3. Route all traffic to secondary region"
echo ""
echo "Wait 2 minutes and check health status:"
echo "  aws route53 get-health-check-status --health-check-id $PRIMARY_HEALTH_CHECK"
echo ""
echo "Test failover by accessing: http://${PRIMARY_IP} (should timeout)"
echo "Secondary region still works: http://${SECONDARY_IP}"
```

---

## Step 9 – Monitor Health Checks

```bash
echo ""
echo "Waiting for health check to detect failure..."
sleep 120

# Check primary health after failure
echo ""
echo "Primary Region Health Check (After Failure):"
aws route53 get-health-check-status \
  --health-check-id "$PRIMARY_HEALTH_CHECK" \
  --query 'HealthCheckObservations[0:3].{Region:Region,Status:StatusReport.Status,Timestamp:StatusReport.CheckedTime}' \
  --output table

# Verify secondary is still healthy
echo ""
echo "Secondary Region Health Check (Still Healthy):"
aws route53 get-health-check-status \
  --health-check-id "$SECONDARY_HEALTH_CHECK" \
  --query 'HealthCheckObservations[0:3].{Region:Region,Status:StatusReport.Status,Timestamp:StatusReport.CheckedTime}' \
  --output table

echo ""
echo "Primary health check should show 'Failure' status"
echo "Secondary health check should show 'Success' status"
```

---

## Step 10 – View CloudWatch Metrics

```bash
echo ""
echo "Route 53 Health Check Metrics (Last 10 minutes):"

# Get primary health check metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Route53 \
  --metric-name HealthCheckStatus \
  --dimensions Name=HealthCheckId,Value="$PRIMARY_HEALTH_CHECK" \
  --start-time "$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 60 \
  --statistics Minimum \
  --query 'Datapoints[-5:].[Timestamp,Minimum]' \
  --output table

echo ""
echo "Health Check Status Values:"
echo "  1.0 = Healthy"
echo "  0.0 = Unhealthy"
```

---

## Step 11 – Review Multi-Region Architecture

```bash
echo ""
echo "================================================"
echo "MULTI-REGION ARCHITECTURE SUMMARY"
echo "================================================"
echo ""
echo "Deployed Resources:"
echo ""
echo "Primary Region (ap-southeast-2):"
echo "  - Instance: $PRIMARY_INSTANCE"
echo "  - Public IP: $PRIMARY_IP"
echo "  - Health Check: $PRIMARY_HEALTH_CHECK"
echo "  - Status: STOPPED (simulated failure)"
echo ""
echo "Secondary Region (us-east-1):"
echo "  - Instance: $SECONDARY_INSTANCE"
echo "  - Public IP: $SECONDARY_IP"
echo "  - Health Check: $SECONDARY_HEALTH_CHECK"
echo "  - Status: RUNNING (active)"
echo ""
echo "Route 53 Configuration:"
echo "  - Health Check Interval: 30 seconds"
echo "  - Failure Threshold: 3 checks"
echo "  - Detection Time: ~90 seconds"
echo ""
echo "For production, add:"
echo "  - Route 53 Hosted Zone with your domain"
echo "  - Latency-based routing records"
echo "  - CloudWatch alarms for health checks"
echo "  - Multi-AZ deployment in each region"
```

---

## Step 12 – Cleanup Resources

```bash
echo ""
echo "Cleaning up resources..."

# Delete health checks
echo "Deleting health checks..."
aws route53 delete-health-check \
  --health-check-id "$PRIMARY_HEALTH_CHECK"

aws route53 delete-health-check \
  --health-check-id "$SECONDARY_HEALTH_CHECK"

# Terminate primary instance
echo "Terminating primary instance..."
aws ec2 terminate-instances \
  --instance-ids "$PRIMARY_INSTANCE" \
  --region "$PRIMARY_REGION"

# Terminate secondary instance
echo "Terminating secondary instance..."
aws ec2 terminate-instances \
  --instance-ids "$SECONDARY_INSTANCE" \
  --region "$SECONDARY_REGION"

echo "Waiting for instances to terminate..."
sleep 30

# Delete primary security group
echo "Deleting primary security group..."
aws ec2 delete-security-group \
  --group-id "$PRIMARY_SG" \
  --region "$PRIMARY_REGION"

# Delete secondary security group
echo "Deleting secondary security group..."
aws ec2 delete-security-group \
  --group-id "$SECONDARY_SG" \
  --region "$SECONDARY_REGION"

# Delete local files
rm -f primary-userdata.sh secondary-userdata.sh

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- EC2 instances (both regions)"
echo "- Security groups (both regions)"
echo "- Route 53 health checks"
echo "- Local files"
```

---

## Summary

In this lab, you have:
- Deployed web applications in two AWS regions (Sydney and US East)
- Created Route 53 health checks for both endpoints
- Configured health monitoring for automatic failover detection
- Tested regional endpoints independently
- Simulated regional failure by stopping primary instance
- Verified automatic failover to secondary region
- Monitored health check status and CloudWatch metrics
- Cleaned up all resources

**Key Takeaways:**
- **Multi-Region Deployment**: High availability across geographic regions
- **Route 53 Health Checks**: Monitor endpoint availability from multiple locations
- **Automatic Failover**: Traffic routed away from unhealthy endpoints
- **Latency-Based Routing**: Users routed to nearest region (requires hosted zone)
- **Health Detection**: ~90 seconds to detect and failover
- **Free Tier Compatible**: Health checks included in Route 53 free tier

**Routing Policies:**
| Policy | Use Case | Best For |
|--------|----------|----------|
| **Latency** | Route to lowest latency | Global applications |
| **Failover** | Active-passive failover | DR scenarios |
| **Geolocation** | Route by user location | Compliance, localization |
| **Weighted** | Traffic distribution % | A/B testing, gradual rollout |

**Best Practices:**
- Deploy in geographically diverse regions
- Use health checks for all critical endpoints
- Set appropriate health check intervals (30s standard)
- Configure CloudWatch alarms for health check failures
- Test failover regularly
- Use multiple health check regions for accuracy
- Document regional failover procedures
- Consider cross-region data replication

---

## Production Enhancements

For production multi-region deployment:

1. **Register Domain in Route 53**
   ```bash
   # Create hosted zone
   aws route53 create-hosted-zone --name example.com --caller-reference $(date +%s)
   
   # Create latency-based records
   aws route53 change-resource-record-sets --hosted-zone-id Z123 --change-batch file://records.json
   ```

2. **Add Application Load Balancers**
   - Deploy ALB in each region
   - Route 53 points to ALB endpoints
   - Multi-AZ within each region

3. **Database Replication**
   - RDS with cross-region read replicas
   - DynamoDB global tables
   - Aurora Global Database

4. **CloudFront Integration**
   - CloudFront distribution with multiple origins
   - Origin failover groups
   - Edge location caching

---

## Free Tier Notes
- **Route 53**: 50 health checks/month (free for first 12 months)
- **Route 53 Queries**: 1M queries/month (free for first 12 months)
- **EC2 t2.micro**: 750 hours/month per region (1500 total)
- **Data Transfer**: 15 GB outbound per month
- **CloudWatch**: 10 alarms free

This lab uses 2 t2.micro instances (one per region) and 2 health checks, staying within free tier limits.
