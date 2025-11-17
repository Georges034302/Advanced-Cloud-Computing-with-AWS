# Lab 8.C: VPC Flow Logs for Network Traffic Monitoring

## Overview
This lab demonstrates VPC Flow Logs for monitoring network traffic in your VPC. Flow Logs capture information about IP traffic going to and from network interfaces, enabling security analysis, troubleshooting connectivity issues, and detecting suspicious activity. You'll enable Flow Logs, send logs to CloudWatch, analyze traffic patterns with Logs Insights, and create alarms for security threats.


---

## Objectives
- Enable VPC Flow Logs for network traffic capture
- Send Flow Logs to CloudWatch Logs
- Analyze accepted and rejected connections
- Query traffic patterns with CloudWatch Logs Insights
- Create metric filters for security monitoring
- Set up alarms for suspicious activity (port scans, rejected traffic)
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Valid email address for security notifications
- IAM permissions for VPC, CloudWatch, SNS, IAM
- Understanding of TCP/IP and network security

---

## Step 1 – Set Environment Variables

```bash
# Configure environment variables
REGION="ap-southeast-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
LOG_GROUP_NAME="/aws/vpc/flowlogs"
ROLE_NAME="VPCFlowLogsToCloudWatchRole"
TOPIC_NAME="vpc-security-alerts"
ALARM_NAME="Suspicious-Network-Activity"
VPC_NAME="flowlogs-vpc"

echo "Region: $REGION | Account: $ACCOUNT_ID | VPC: $VPC_NAME"
```

---

## Step 2 – Create SNS Topic for Security Alerts

```bash
# Create SNS topic for Flow Logs alarms
TOPIC_ARN=$(aws sns create-topic \
  --name "$TOPIC_NAME" \
  --region "$REGION" \
  --query TopicArn \
  --output text)

echo "Topic ARN: $TOPIC_ARN"
```

---

## Step 3 – Subscribe Email to SNS Topic

```bash
# Subscribe email to receive security notifications
read -p "Enter your email address: " EMAIL_ADDRESS

aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol email \
  --notification-endpoint "$EMAIL_ADDRESS" \
  --region "$REGION"

read -p "Confirm subscription in email, then press Enter..."
```

---

## Step 4 – Create VPC

```bash
# Create VPC with 10.0.0.0/16 CIDR block
VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=$VPC_NAME}]" \
  --region "$REGION" \
  --query 'Vpc.VpcId' \
  --output text)

echo "VPC ID: $VPC_ID"
```

---

## Step 5 – Create Subnet and Internet Gateway

```bash
# Create public subnet in AZ-a
SUBNET_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_ID" \
  --cidr-block 10.0.1.0/24 \
  --availability-zone "${REGION}a" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=flowlogs-subnet}]" \
  --region "$REGION" \
  --query 'Subnet.SubnetId' \
  --output text)

echo "Subnet ID: $SUBNET_ID"

# Create and attach Internet Gateway
IGW_ID=$(aws ec2 create-internet-gateway \
  --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=flowlogs-igw}]" \
  --region "$REGION" \
  --query 'InternetGateway.InternetGatewayId' \
  --output text)

aws ec2 attach-internet-gateway \
  --vpc-id "$VPC_ID" \
  --internet-gateway-id "$IGW_ID" \
  --region "$REGION"

echo "IGW ID: $IGW_ID"
```

---

## Step 6 – Create CloudWatch Logs Group

```bash
# Create CloudWatch Logs group for VPC Flow Logs
aws logs create-log-group \
  --log-group-name "$LOG_GROUP_NAME" \
  --region "$REGION"

echo "Log group: $LOG_GROUP_NAME"
```

---

## Step 7 – Create IAM Role for VPC Flow Logs

```bash
# Create trust policy allowing VPC Flow Logs to assume role
cat > trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "vpc-flow-logs.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role
aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document file://trust-policy.json

ROLE_ARN=$(aws iam get-role \
  --role-name "$ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)

echo "Role ARN: $ROLE_ARN"
```

---

## Step 8 – Attach Policy to IAM Role

```bash
# Create policy allowing VPC Flow Logs to write to CloudWatch Logs
cat > logs-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:${LOG_GROUP_NAME}:*"
    }
  ]
}
EOF

# Attach inline policy to role
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "VPCFlowLogsPolicy" \
  --policy-document file://logs-policy.json
```

---

## Step 9 – Enable VPC Flow Logs

```bash
# Wait for IAM role to propagate
sleep 10

# Enable VPC Flow Logs (ALL traffic to CloudWatch Logs)
FLOW_LOG_ID=$(aws ec2 create-flow-logs \
  --resource-type VPC \
  --resource-ids "$VPC_ID" \
  --traffic-type ALL \
  --log-destination-type cloud-watch-logs \
  --log-group-name "$LOG_GROUP_NAME" \
  --deliver-logs-permission-arn "$ROLE_ARN" \
  --region "$REGION" \
  --query 'FlowLogIds[0]' \
  --output text)

echo "Flow Log ID: $FLOW_LOG_ID (ALL traffic → CloudWatch Logs)"
```

---

## Step 10 – Launch EC2 Instance to Generate Traffic

```bash
# Get latest Amazon Linux 2023 AMI
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text \
  --region "$REGION")

# Create security group allowing SSH
SG_ID=$(aws ec2 create-security-group \
  --group-name "flowlogs-sg" \
  --description "Security group for Flow Logs lab" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

# Launch instance without key pair (to generate rejected SSH traffic)
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SG_ID" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=flowlogs-test}]" \
  --region "$REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Instance ID: $INSTANCE_ID"

# Wait for instance to be running
aws ec2 wait instance-running \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"
```

---

## Step 11 – Generate Network Traffic

```bash
# Get instance public IP
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$REGION")

echo "Instance Public IP: $PUBLIC_IP"

# Generate accepted traffic (AWS API calls)
aws ec2 describe-instances --region "$REGION" > /dev/null
aws s3 ls > /dev/null 2>&1

# Simulate rejected traffic (SSH connection attempts without key)
for i in {1..5}; do
    timeout 2 nc -zv "$PUBLIC_IP" 22 2>/dev/null || true
    sleep 1
done

# Simulate port scan (rejected traffic on closed ports)
for port in 80 443 3306 5432 8080; do
    timeout 1 nc -zv "$PUBLIC_IP" "$port" 2>/dev/null || true
done

echo "Waiting 3min for Flow Logs to be delivered to CloudWatch Logs..."
sleep 180
```

---

## Step 12 – Query All Flow Logs

```bash
# Calculate time range (last 10 minutes)
START_TIME=$(($(date +%s) - 600))
END_TIME=$(date +%s)

# Query 1: Recent Flow Log records
aws logs start-query \
  --log-group-name "$LOG_GROUP_NAME" \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --query-string 'fields @timestamp, srcAddr, dstAddr, srcPort, dstPort, protocol, action, packets, bytes
| sort @timestamp desc
| limit 20' \
  --region "$REGION" > query-result.json

QUERY_ID=$(cat query-result.json | grep -o '"queryId": "[^"]*' | grep -o '[^"]*$')
echo "Query ID: $QUERY_ID"

# Wait for query to complete and get results
sleep 5

aws logs get-query-results \
  --query-id "$QUERY_ID" \
  --region "$REGION" \
  --query 'results[*]' \
  --output table
```

---

## Step 13 – Query Rejected Traffic Only

```bash
# Query 2: Rejected connections (blocked by security groups)
aws logs start-query \
  --log-group-name "$LOG_GROUP_NAME" \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --query-string 'fields @timestamp, srcAddr, dstAddr, dstPort, protocol, action
| filter action = "REJECT"
| stats count() by dstPort
| sort count desc' \
  --region "$REGION" > query-result2.json

QUERY_ID2=$(cat query-result2.json | grep -o '"queryId": "[^"]*' | grep -o '[^"]*$')

sleep 5

aws logs get-query-results \
  --query-id "$QUERY_ID2" \
  --region "$REGION" \
  --query 'results[*]' \
  --output table
```

---

## Step 14 – Query Top Talkers

```bash
# Query 3: Top source IP addresses (most active)
aws logs start-query \
  --log-group-name "$LOG_GROUP_NAME" \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --query-string 'fields srcAddr, dstAddr, bytes
| stats sum(bytes) as totalBytes by srcAddr
| sort totalBytes desc
| limit 10' \
  --region "$REGION" > query-result3.json

QUERY_ID3=$(cat query-result3.json | grep -o '"queryId": "[^"]*' | grep -o '[^"]*$')

sleep 5

aws logs get-query-results \
  --query-id "$QUERY_ID3" \
  --region "$REGION" \
  --query 'results[*]' \
  --output table
```

---

## Step 15 – Query by Protocol

```bash
# Query 4: Traffic breakdown by protocol (6=TCP, 17=UDP, 1=ICMP)
aws logs start-query \
  --log-group-name "$LOG_GROUP_NAME" \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --query-string 'fields protocol
| stats count() by protocol' \
  --region "$REGION" > query-result4.json

QUERY_ID4=$(cat query-result4.json | grep -o '"queryId": "[^"]*' | grep -o '[^"]*$')

sleep 5

aws logs get-query-results \
  --query-id "$QUERY_ID4" \
  --region "$REGION" \
  --query 'results[*]' \
  --output table
```

---

## Step 16 – Create Metric Filter for Rejected Traffic

```bash
# Create metric filter to track rejected connections
FILTER_PATTERN='[version, account, eni, source, destination, srcport, destport, protocol, packets, bytes, windowstart, windowend, action="REJECT", flowlogstatus]'

aws logs put-metric-filter \
  --log-group-name "$LOG_GROUP_NAME" \
  --filter-name "RejectedConnections" \
  --filter-pattern "$FILTER_PATTERN" \
  --metric-transformations \
    metricName=RejectedConnectionCount,metricNamespace=VPC/FlowLogs,metricValue=1,defaultValue=0 \
  --region "$REGION"
```

---

## Step 17 – Create CloudWatch Alarm for High Rejected Traffic

```bash
# Create alarm to trigger on high rejected traffic (>10 in 5min = port scan)
aws cloudwatch put-metric-alarm \
  --alarm-name "$ALARM_NAME" \
  --alarm-description "Alert when rejected connections exceed threshold (possible port scan)" \
  --metric-name RejectedConnectionCount \
  --namespace VPC/FlowLogs \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions "$TOPIC_ARN" \
  --treat-missing-data notBreaching \
  --region "$REGION"

echo "Alarm will trigger on >10 rejected connections in 5min → SNS email"
```

---

## Step 18 – View Flow Logs Console

```bash
# View VPC Flow Logs in AWS Console
echo "https://${REGION}.console.aws.amazon.com/vpc/home?region=${REGION}#FlowLogs:"
```

---

## Step 19 – Cleanup Resources

```bash
# Terminate EC2 instance
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

aws ec2 wait instance-terminated \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

# Delete VPC Flow Logs
aws ec2 delete-flow-logs \
  --flow-log-ids "$FLOW_LOG_ID" \
  --region "$REGION"

# Delete CloudWatch alarm
aws cloudwatch delete-alarms \
  --alarm-names "$ALARM_NAME" \
  --region "$REGION"

# Delete metric filter
aws logs delete-metric-filter \
  --log-group-name "$LOG_GROUP_NAME" \
  --filter-name "RejectedConnections" \
  --region "$REGION"

# Delete CloudWatch Logs group
aws logs delete-log-group \
  --log-group-name "$LOG_GROUP_NAME" \
  --region "$REGION"

# Delete security group
aws ec2 delete-security-group \
  --group-id "$SG_ID" \
  --region "$REGION"

# Detach and delete Internet Gateway
aws ec2 detach-internet-gateway \
  --vpc-id "$VPC_ID" \
  --internet-gateway-id "$IGW_ID" \
  --region "$REGION"

aws ec2 delete-internet-gateway \
  --internet-gateway-id "$IGW_ID" \
  --region "$REGION"

# Delete subnet
aws ec2 delete-subnet \
  --subnet-id "$SUBNET_ID" \
  --region "$REGION"

# Delete VPC
aws ec2 delete-vpc \
  --vpc-id "$VPC_ID" \
  --region "$REGION"

# Delete IAM role policy and role
aws iam delete-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "VPCFlowLogsPolicy"

aws iam delete-role \
  --role-name "$ROLE_NAME"

# Unsubscribe email from SNS
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
aws sns delete-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION"

# Delete local policy files
rm -f trust-policy.json logs-policy.json query-result*.json

echo "Cleanup complete: VPC, Flow Logs, EC2, CloudWatch, IAM, SNS deleted"
```

---

## Summary

In this lab, you have:
- Created VPC with subnet and Internet Gateway
- Enabled VPC Flow Logs for network traffic monitoring
- Configured CloudWatch Logs for log delivery
- Launched EC2 instance to generate network traffic
- Generated accepted and rejected traffic patterns
- Queried Flow Logs with CloudWatch Logs Insights (all traffic, rejected only, top talkers, protocols)
- Created metric filter to track rejected connections
- Set up CloudWatch alarm for suspicious activity (port scans)
- Cleaned up all resources

**Key Takeaways:**
- **VPC Flow Logs**: Capture all IP traffic in your VPC
- **Traffic Types**: ALL (accepted + rejected), ACCEPT only, REJECT only
- **Log Format**: 14 default fields (version, account, ENI, IPs, ports, protocol, action, etc.)
- **CloudWatch Integration**: Real-time log delivery and querying
- **Security Monitoring**: Detect port scans, DDoS, unauthorized access
- **Troubleshooting**: Diagnose connectivity issues, routing problems
- **Compliance**: Network audit trails for regulatory requirements

**Flow Log Record Fields:**
```
version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status
```

**Example Flow Log Record:**
```
2 123456789012 eni-abc123 192.168.1.10 10.0.1.5 45123 22 6 5 2500 1610000000 1610000030 REJECT OK
```

**Interpretation:**
- Version: 2
- Account: 123456789012
- ENI: eni-abc123
- Source: 192.168.1.10:45123
- Destination: 10.0.1.5:22
- Protocol: 6 (TCP)
- Packets: 5
- Bytes: 2500
- Action: REJECT (security group blocked)
- Status: OK (logging successful)

**Common Logs Insights Queries:**
```sql
-- Top rejected ports (possible attack targets)
filter action = "REJECT"
| stats count() by dstPort
| sort count desc

-- Top source IPs (identify attackers)
stats count() by srcAddr
| sort count desc
| limit 10

-- Bandwidth usage by destination
stats sum(bytes) as totalBytes by dstAddr
| sort totalBytes desc

-- SSH connections
filter dstPort = 22
| stats count() by srcAddr, action

-- Traffic to specific instance
filter dstAddr = "10.0.1.5"
| fields @timestamp, srcAddr, srcPort, dstPort, action
```

---

## Best Practices

**Flow Logs Configuration:**
- Enable Flow Logs at VPC level (captures all subnets)
- Use CloudWatch Logs for real-time analysis
- Use S3 for long-term storage (cheaper than CloudWatch)
- Enable custom log format for additional fields (TCP flags, VPC ID, subnet ID)
- Set appropriate retention period (7-30 days for CloudWatch, indefinite for S3)

**Security Monitoring:**
- Alert on high rejected connection counts (port scanning)
- Monitor traffic from known malicious IPs
- Track unusual destination ports (backdoors, malware)
- Analyze SSH/RDP login attempts
- Detect data exfiltration (high outbound traffic)

**Performance Optimization:**
- Exclude AWS service traffic to reduce log volume
- Use sampling (1 in 10 packets) for high-traffic VPCs
- Aggregate logs in S3 with Athena for historical analysis
- Use VPC Flow Logs Insights in Console (faster than Logs Insights)

---

## Production Enhancements

1. **Custom Log Format**
   ```bash
   # Include TCP flags, VPC ID, subnet ID
   aws ec2 create-flow-logs \
     --resource-ids "$VPC_ID" \
     --traffic-type ALL \
     --log-destination-type cloud-watch-logs \
     --log-group-name "$LOG_GROUP_NAME" \
     --deliver-logs-permission-arn "$ROLE_ARN" \
     --log-format '${version} ${account-id} ${interface-id} ${srcaddr} ${dstaddr} ${srcport} ${dstport} ${protocol} ${packets} ${bytes} ${start} ${end} ${action} ${log-status} ${vpc-id} ${subnet-id} ${tcp-flags}'
   ```

2. **S3 Destination for Long-Term Storage**
   ```bash
   # Send Flow Logs to S3 (cheaper than CloudWatch)
   aws ec2 create-flow-logs \
     --resource-ids "$VPC_ID" \
     --traffic-type ALL \
     --log-destination-type s3 \
     --log-destination "arn:aws:s3:::my-flow-logs-bucket"
   ```

3. **Athena Integration for S3 Logs**
   ```sql
   -- Create Athena table for S3 Flow Logs
   CREATE EXTERNAL TABLE IF NOT EXISTS vpc_flow_logs (
     version int,
     account string,
     interfaceid string,
     sourceaddress string,
     destinationaddress string,
     sourceport int,
     destinationport int,
     protocol int,
     numpackets int,
     numbytes bigint,
     starttime int,
     endtime int,
     action string,
     logstatus string
   ) PARTITIONED BY (dt string)
   ROW FORMAT DELIMITED
   FIELDS TERMINATED BY ' '
   LOCATION 's3://my-flow-logs-bucket/AWSLogs/'
   ```

4. **GuardDuty Integration**
   - Enable GuardDuty (uses Flow Logs automatically)
   - Detects malicious IPs, port scanning, unusual API calls
   - Machine learning-based threat detection

5. **EventBridge Integration**
   ```bash
   # Trigger Lambda on high rejected traffic
   aws events put-rule \
     --name flowlogs-rejected-traffic \
     --event-pattern '{
       "source": ["aws.logs"],
       "detail-type": ["CloudWatch Logs Filter Match"],
       "detail": {
         "filterName": ["RejectedConnections"]
       }
     }'
   ```

---

## Troubleshooting

**No Flow Logs appearing:**
- Wait 5-15 minutes for first logs
- Verify IAM role has correct trust policy
- Check IAM role has PutLogEvents permission
- Ensure CloudWatch Logs group exists
- Verify Flow Logs are enabled: `aws ec2 describe-flow-logs`

**Incomplete logs:**
- Check ENI has traffic (ping, SSH, API calls)
- Verify security group allows traffic
- Ensure instance is running (not stopped)
- Review log-status field in Flow Logs

**Queries return no results:**
- Wait 5-10 minutes after generating traffic
- Check time range (use last 30 minutes)
- Verify log group name is correct
- Test with simpler query first

**High CloudWatch Logs costs:**
- Switch to S3 destination (70% cheaper)
- Enable sampling (log 1 in 10 packets)
- Reduce retention period (7 days vs 30 days)
- Exclude AWS service traffic

---

## Additional Resources

- [VPC Flow Logs Documentation](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html)
- [Flow Logs Record Format](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-records-examples.html)
- [CloudWatch Logs Insights Query Syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html)
- [VPC Security Best Practices](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-best-practices.html)
