# Lab 5.D: Multi-Region Traffic Distribution with Route 53

## Overview
This lab demonstrates how to implement global high availability using Amazon Route 53 for multi-region traffic distribution. You will deploy identical web applications in two AWS regions, configure Route 53 with latency-based routing to direct users to the nearest region, implement health checks for automatic failover, and test regional failover scenarios.

---

## Objectives
- Deploy web application in two AWS regions
- Create Route 53 hosted zone with pseudo domain
- Configure latency-based routing policy
- Set up Route 53 health checks for automatic failover
- Test traffic routing to nearest region
- Simulate regional failure and verify automatic failover
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Default VPCs in both regions (ap-southeast-2, us-east-1)
- IAM permissions for EC2, Route 53, and CloudWatch
- Basic understanding of DNS and routing policies
- Note: Lab uses pseudo domain name (myapp.example.com) for demonstration

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Set regions and resource names
PRIMARY_REGION="ap-southeast-2"     # Sydney
SECONDARY_REGION="us-east-1"        # US East
SG_NAME="lab-route53-sg"
INSTANCE_NAME="route53-demo"

# Domain configuration (pseudo domain for demonstration)
DOMAIN_NAME="myapp.example.com"
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

# Allow HTTP and ICMP for health checks
aws ec2 authorize-security-group-ingress \
  --group-id "$PRIMARY_SG" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region "$PRIMARY_REGION"

aws ec2 authorize-security-group-ingress \
  --group-id "$PRIMARY_SG" \
  --protocol icmp \
  --port -1 \
  --cidr 0.0.0.0/0 \
  --region "$PRIMARY_REGION"

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

# Allow HTTP and ICMP for health checks
aws ec2 authorize-security-group-ingress \
  --group-id "$SECONDARY_SG" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region "$SECONDARY_REGION"

aws ec2 authorize-security-group-ingress \
  --group-id "$SECONDARY_SG" \
  --protocol icmp \
  --port -1 \
  --cidr 0.0.0.0/0 \
  --region "$SECONDARY_REGION"

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
```

---

## Step 4 – Wait for Instances and Get Public IPs

```bash
# Wait for instances to initialize (2-3 minutes)
aws ec2 wait instance-running \
  --instance-ids "$PRIMARY_INSTANCE" \
  --region "$PRIMARY_REGION"

aws ec2 wait instance-running \
  --instance-ids "$SECONDARY_INSTANCE" \
  --region "$SECONDARY_REGION"

# Wait for user data to complete
sleep 60

# Get instance public IPs
PRIMARY_IP=$(aws ec2 describe-instances \
  --instance-ids "$PRIMARY_INSTANCE" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$PRIMARY_REGION")
echo "PRIMARY_IP=$PRIMARY_IP (Sydney: http://${PRIMARY_IP})"

SECONDARY_IP=$(aws ec2 describe-instances \
  --instance-ids "$SECONDARY_INSTANCE" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$SECONDARY_REGION")
echo "SECONDARY_IP=$SECONDARY_IP (US East: http://${SECONDARY_IP})"
```

---

## Step 5 – Create Route 53 Health Checks

```bash
# Create Route 53 health checks
# HTTP health check on /health.html, Interval: 30s, Failure Threshold: 3
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
```

---

## Step 6 – Create Route 53 Hosted Zone

```bash
# Create hosted zone for domain
HOSTED_ZONE_OUTPUT=$(aws route53 create-hosted-zone \
  --name "$DOMAIN_NAME" \
  --caller-reference "$(date +%s)" \
  --hosted-zone-config Comment="Multi-region demo hosted zone")

HOSTED_ZONE_ID=$(echo "$HOSTED_ZONE_OUTPUT" | jq -r '.HostedZone.Id' | cut -d'/' -f3)
echo "HOSTED_ZONE_ID=$HOSTED_ZONE_ID"

# Get name servers
aws route53 get-hosted-zone \
  --id "$HOSTED_ZONE_ID" \
  --query 'DelegationSet.NameServers' \
  --output table
```

---

## Step 7 – Create Latency-Based Routing Records

```bash
# Create latency-based record for primary region (Sydney)
aws route53 change-resource-record-sets \
  --hosted-zone-id "$HOSTED_ZONE_ID" \
  --change-batch "{
    \"Changes\": [{
      \"Action\": \"CREATE\",
      \"ResourceRecordSet\": {
        \"Name\": \"$DOMAIN_NAME\",
        \"Type\": \"A\",
        \"SetIdentifier\": \"Primary-Sydney\",
        \"Region\": \"$PRIMARY_REGION\",
        \"TTL\": 60,
        \"ResourceRecords\": [{\"Value\": \"$PRIMARY_IP\"}],
        \"HealthCheckId\": \"$PRIMARY_HEALTH_CHECK\"
      }
    }]
  }"

# Create latency-based record for secondary region (US East)
aws route53 change-resource-record-sets \
  --hosted-zone-id "$HOSTED_ZONE_ID" \
  --change-batch "{
    \"Changes\": [{
      \"Action\": \"CREATE\",
      \"ResourceRecordSet\": {
        \"Name\": \"$DOMAIN_NAME\",
        \"Type\": \"A\",
        \"SetIdentifier\": \"Secondary-USEast\",
        \"Region\": \"$SECONDARY_REGION\",
        \"TTL\": 60,
        \"ResourceRecords\": [{\"Value\": \"$SECONDARY_IP\"}],
        \"HealthCheckId\": \"$SECONDARY_HEALTH_CHECK\"
      }
    }]
  }"
```

---

## Step 8 – Verify DNS Records

```bash
# List all records in hosted zone
aws route53 list-resource-record-sets \
  --hosted-zone-id "$HOSTED_ZONE_ID" \
  --query "ResourceRecordSets[?Type=='A'].{Name:Name,Type:Type,Region:Region,IP:ResourceRecords[0].Value,HealthCheck:HealthCheckId}" \
  --output table

# Test DNS resolution (may take a few minutes to propagate)
dig +short "$DOMAIN_NAME" @8.8.8.8
```

---

## Step 9 – Test Regional Endpoints

```bash
# Test regional endpoints
curl -s "http://${PRIMARY_IP}" | grep -o "SYDNEY (PRIMARY)"
curl -s "http://${SECONDARY_IP}" | grep -o "US EAST (SECONDARY)"

# Test latency-based routing via domain
curl -s "http://${DOMAIN_NAME}" | grep -o "SYDNEY\\|US EAST"

# Open in browser (Purple=Sydney 🇦🇺, Pink=US East 🇺🇸)
"$BROWSER" "http://${PRIMARY_IP}"
"$BROWSER" "http://${SECONDARY_IP}"
"$BROWSER" "http://${DOMAIN_NAME}"
```

---

## Step 10 – View Health Check Status

```bash
# Wait for health checks to become healthy (1-2 minutes)
sleep 60

# Check primary health
aws route53 get-health-check-status \
  --health-check-id "$PRIMARY_HEALTH_CHECK" \
  --query 'HealthCheckObservations[0:3].{Region:Region,Status:StatusReport.Status,Timestamp:StatusReport.CheckedTime}' \
  --output table

# Check secondary health
aws route53 get-health-check-status \
  --health-check-id "$SECONDARY_HEALTH_CHECK" \
  --query 'HealthCheckObservations[0:3].{Region:Region,Status:StatusReport.Status,Timestamp:StatusReport.CheckedTime}' \
  --output table
```

---

## Step 11 – Simulate Regional Failure

```bash
# Simulate regional failure by stopping primary instance
# Route 53 will detect failure (~90s) and automatically route to secondary region
aws ec2 stop-instances \
  --instance-ids "$PRIMARY_INSTANCE" \
  --region "$PRIMARY_REGION"

# Monitor health check status after 2 minutes
echo "Primary instance stopped. Wait 2 minutes for failover detection."
echo "Monitor: aws route53 get-health-check-status --health-check-id $PRIMARY_HEALTH_CHECK"
```

---

## Step 12 – Monitor Health Checks

```bash
# Wait for health check to detect failure (~2 minutes)
sleep 120

# Check primary health after failure (should show 'Failure')
aws route53 get-health-check-status \
  --health-check-id "$PRIMARY_HEALTH_CHECK" \
  --query 'HealthCheckObservations[0:3].{Region:Region,Status:StatusReport.Status,Timestamp:StatusReport.CheckedTime}' \
  --output table

# Verify secondary is still healthy (should show 'Success')
aws route53 get-health-check-status \
  --health-check-id "$SECONDARY_HEALTH_CHECK" \
  --query 'HealthCheckObservations[0:3].{Region:Region,Status:StatusReport.Status,Timestamp:StatusReport.CheckedTime}' \
  --output table

# Verify automatic failover to secondary region
curl -s "http://${DOMAIN_NAME}" | grep -o "US EAST (SECONDARY)"
```

---

## Step 13 – View CloudWatch Metrics

```bash
# Get Route 53 health check metrics (last 10 minutes)
# Health Check Status: 1.0 = Healthy, 0.0 = Unhealthy
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
```

---

## Step 14 – Review Multi-Region Architecture

```bash
# View deployed resources summary
echo "Primary Region (ap-southeast-2): $PRIMARY_INSTANCE @ $PRIMARY_IP (STOPPED)"
echo "Secondary Region (us-east-1): $SECONDARY_INSTANCE @ $SECONDARY_IP (RUNNING)"
echo "Health Checks: $PRIMARY_HEALTH_CHECK, $SECONDARY_HEALTH_CHECK"
echo "Hosted Zone: $HOSTED_ZONE_ID"
echo "Domain: $DOMAIN_NAME (Routes to: Secondary Region)"
```

---

## Step 15 – Cleanup Resources

```bash
# Delete Route 53 records first
aws route53 change-resource-record-sets \
  --hosted-zone-id "$HOSTED_ZONE_ID" \
  --change-batch "{
    \"Changes\": [
      {
        \"Action\": \"DELETE\",
        \"ResourceRecordSet\": {
          \"Name\": \"$DOMAIN_NAME\",
          \"Type\": \"A\",
          \"SetIdentifier\": \"Primary-Sydney\",
          \"Region\": \"$PRIMARY_REGION\",
          \"TTL\": 60,
          \"ResourceRecords\": [{\"Value\": \"$PRIMARY_IP\"}],
          \"HealthCheckId\": \"$PRIMARY_HEALTH_CHECK\"
        }
      },
      {
        \"Action\": \"DELETE\",
        \"ResourceRecordSet\": {
          \"Name\": \"$DOMAIN_NAME\",
          \"Type\": \"A\",
          \"SetIdentifier\": \"Secondary-USEast\",
          \"Region\": \"$SECONDARY_REGION\",
          \"TTL\": 60,
          \"ResourceRecords\": [{\"Value\": \"$SECONDARY_IP\"}],
          \"HealthCheckId\": \"$SECONDARY_HEALTH_CHECK\"
        }
      }
    ]
  }"

# Delete hosted zone
aws route53 delete-hosted-zone --id "$HOSTED_ZONE_ID"

# Delete health checks
aws route53 delete-health-check --health-check-id "$PRIMARY_HEALTH_CHECK"
aws route53 delete-health-check --health-check-id "$SECONDARY_HEALTH_CHECK"

# Terminate instances
aws ec2 terminate-instances --instance-ids "$PRIMARY_INSTANCE" --region "$PRIMARY_REGION"
aws ec2 terminate-instances --instance-ids "$SECONDARY_INSTANCE" --region "$SECONDARY_REGION"

sleep 30

# Delete security groups
aws ec2 delete-security-group --group-id "$PRIMARY_SG" --region "$PRIMARY_REGION"
aws ec2 delete-security-group --group-id "$SECONDARY_SG" --region "$SECONDARY_REGION"

# Delete local files
rm -f primary-userdata.sh secondary-userdata.sh

echo "✅ Cleanup completed"
```

---

## Summary

In this lab, you have:
- Deployed web applications in two AWS regions (Sydney and US East)
- Created Route 53 hosted zone with pseudo domain (myapp.example.com)
- Configured latency-based routing records for both regions
- Set up Route 53 health checks for automatic failover detection
- Tested regional endpoints and DNS-based routing
- Simulated regional failure by stopping primary instance
- Verified automatic DNS failover to secondary region
- Monitored health check status and CloudWatch metrics
- Cleaned up all resources including DNS records and hosted zone

**Key Takeaways:**
- **Multi-Region Deployment**: High availability across geographic regions
- **Route 53 Hosted Zone**: DNS management with pseudo domain
- **Latency-Based Routing**: Users routed to nearest healthy region automatically
- **Health Checks**: Monitor endpoint availability from multiple locations worldwide
- **Automatic DNS Failover**: Traffic automatically routed away from unhealthy endpoints
- **Health Detection**: ~90 seconds to detect failure and trigger failover
- **Free Tier Note**: Hosted zone costs $0.50/month, health checks may incur charges

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

1. **Use Registered Domain**
   - Register real domain in Route 53 (or use existing domain)
   - Update nameservers at registrar to Route 53 nameservers
   - Replace pseudo domain with real domain name

2. **Add Application Load Balancers**
   - Deploy ALB in each region for multi-AZ redundancy
   - Route 53 Alias records point to ALB endpoints
   - Health checks monitor ALB instead of individual IPs

3. **Database Replication**
   - RDS with cross-region read replicas
   - DynamoDB global tables for multi-region writes
   - Aurora Global Database for fast failover

4. **CloudFront Integration**
   - CloudFront distribution with multiple regional origins
   - Origin failover groups for automatic backup
   - Edge location caching for faster global access

---

