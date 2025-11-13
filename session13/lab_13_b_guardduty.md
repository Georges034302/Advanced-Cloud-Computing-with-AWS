# Lab 13.B: Amazon GuardDuty - Threat Detection and Security Monitoring

## Overview
This lab introduces Amazon GuardDuty, a continuous threat detection service that uses machine learning, anomaly detection, and threat intelligence to monitor AWS accounts and workloads. You'll enable GuardDuty, configure data sources, generate sample findings, simulate real-world threats, analyze findings, and set up automated alerting.

**💰 Cost**: GuardDuty: $4.40/month for CloudTrail analysis + $0.80/GB for VPC Flow Logs. Minimal cost for short lab.

---

## Objectives
- Enable GuardDuty detector for threat monitoring
- Configure data sources (CloudTrail, VPC Flow Logs, DNS)
- Generate and analyze sample findings
- Deploy EC2 instance for threat simulation
- Simulate reconnaissance, brute force, and malicious activity
- Filter findings by severity
- Export findings to S3
- Integrate with Security Hub
- Set up automated remediation

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for GuardDuty, EC2, S3, Security Hub
- Region: ap-southeast-2
- Basic understanding of security threats

---

## Architecture

```
AWS Resources (EC2, IAM, S3, etc.)
          ↓
Data Sources:
  - CloudTrail Logs (API calls)
  - VPC Flow Logs (network traffic)
  - DNS Logs (DNS queries)
          ↓
    Amazon GuardDuty
    (ML + Threat Intel)
          ↓
  Security Findings
  ├─ Reconnaissance
  ├─ Unauthorized Access
  ├─ Backdoor/Malware
  └─ Data Exfiltration
          ↓
  EventBridge → Alerts
  Security Hub → Dashboard
```

---

## Step 1 – Set Variables

```bash
# Set region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "REGION=$REGION"

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)

echo "ACCOUNT_ID=$ACCOUNT_ID"
echo ""
echo "================================================"
echo "SETTING UP GUARDDUTY"
echo "================================================"
```

---

## Step 2 – Enable GuardDuty

```bash
echo ""
echo "Enabling GuardDuty detector..."

# Create GuardDuty detector
DETECTOR_ID=$(aws guardduty create-detector \
  --enable \
  --region "$REGION" \
  --query DetectorId \
  --output text)

echo "DETECTOR_ID=$DETECTOR_ID"
echo "✅ GuardDuty enabled and monitoring"
```

---

## Step 3 – Verify GuardDuty Status

```bash
echo ""
echo "Verifying GuardDuty detector status..."

# Get detector details
aws guardduty get-detector \
  --detector-id "$DETECTOR_ID" \
  --region "$REGION" \
  --query '{Status:Status,ServiceRole:ServiceRole,DataSources:DataSources}' \
  --output json

echo ""
echo "✅ GuardDuty is actively monitoring"
echo "   - CloudTrail Events: ✅"
echo "   - VPC Flow Logs: ✅"
echo "   - DNS Logs: ✅"
```

---

## Step 4 – Configure Enhanced Data Sources

```bash
echo ""
echo "Enabling enhanced data sources..."

# Update detector with S3 and Kubernetes protection (if available)
aws guardduty update-detector \
  --detector-id "$DETECTOR_ID" \
  --enable \
  --region "$REGION" 2>/dev/null \
  || echo "Using default data sources"

echo "✅ Data sources configured"
```

---

## Step 5 – Generate Sample Findings

```bash
echo ""
echo "================================================"
echo "GENERATING SAMPLE FINDINGS"
echo "================================================"
echo ""

# Generate sample findings for testing
echo "Creating sample findings (all threat types)..."

aws guardduty create-sample-findings \
  --detector-id "$DETECTOR_ID" \
  --region "$REGION"

echo ""
echo "✅ Sample findings generated!"
echo ""
echo "Sample finding types created:"
echo "  - Recon:EC2/PortProbeUnprotectedPort"
echo "  - UnauthorizedAccess:EC2/SSHBruteForce"
echo "  - Backdoor:EC2/C&CActivity.B"
echo "  - CryptoCurrency:EC2/BitcoinTool.B"
echo "  - Trojan:EC2/DNSDataExfiltration"
echo ""
echo "Wait 1-2 minutes for findings to appear..."
```

---

## Step 6 – List All Findings

```bash
echo ""
echo "Listing all GuardDuty findings..."

# Wait for findings to be available
sleep 90

# List all finding IDs
FINDING_IDS=$(aws guardduty list-findings \
  --detector-id "$DETECTOR_ID" \
  --region "$REGION" \
  --query "FindingIds[]" \
  --output text)

echo "Total findings: $(echo $FINDING_IDS | wc -w)"
echo ""
```

---

## Step 7 – View Detailed Findings

```bash
echo "Getting detailed finding information..."
echo ""

# Get full details of first 5 findings (for brevity)
FIRST_FIVE=$(echo $FINDING_IDS | tr ' ' '\n' | head -5 | tr '\n' ' ')

aws guardduty get-findings \
  --detector-id "$DETECTOR_ID" \
  --region "$REGION" \
  --finding-ids $FIRST_FIVE \
  --query 'Findings[*].[Type,Severity,Title,Description]' \
  --output table

echo ""
echo "✅ Sample findings retrieved"
```

---

## Step 8 – Filter Findings by Severity

```bash
echo ""
echo "================================================"
echo "FILTERING FINDINGS BY SEVERITY"
echo "================================================"
echo ""

# High severity (7-9)
echo "High Severity Findings (7-9):"
HIGH_FINDINGS=$(aws guardduty list-findings \
  --detector-id "$DETECTOR_ID" \
  --region "$REGION" \
  --finding-criteria '{"Criterion":{"severity":{"Gte":7}}}' \
  --query "FindingIds[]" \
  --output text)

echo "Count: $(echo $HIGH_FINDINGS | wc -w)"
echo ""

# Medium severity (4-6)
echo "Medium Severity Findings (4-6):"
MEDIUM_FINDINGS=$(aws guardduty list-findings \
  --detector-id "$DETECTOR_ID" \
  --region "$REGION" \
  --finding-criteria '{"Criterion":{"severity":{"Gte":4,"Lte":6}}}' \
  --query "FindingIds[]" \
  --output text)

echo "Count: $(echo $MEDIUM_FINDINGS | wc -w)"
echo ""

# Low severity (1-3)
echo "Low Severity Findings (1-3):"
LOW_FINDINGS=$(aws guardduty list-findings \
  --detector-id "$DETECTOR_ID" \
  --region "$REGION" \
  --finding-criteria '{"Criterion":{"severity":{"Lte":3}}}' \
  --query "FindingIds[]" \
  --output text)

echo "Count: $(echo $LOW_FINDINGS | wc -w)"
echo ""
echo "✅ Findings categorized by severity"
```

---

## Step 9 – Deploy EC2 Instance for Threat Simulation

```bash
echo ""
echo "================================================"
echo "SIMULATING REAL THREATS"
echo "================================================"
echo ""

# Get latest Amazon Linux 2 AMI
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" \
            "Name=state,Values=available" \
  --region "$REGION" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

echo "AMI_ID=$AMI_ID"
echo ""

# Create security group for testing
echo "Creating security group..."
SG_ID=$(aws ec2 create-security-group \
  --group-name guardduty-test-sg \
  --description "GuardDuty threat simulation" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

echo "SG_ID=$SG_ID"

# Allow SSH from anywhere (for testing)
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

echo "✅ Security group created"
echo ""

# Launch EC2 instance
echo "Launching EC2 instance for threat simulation..."

INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --security-group-ids "$SG_ID" \
  --region "$REGION" \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=GuardDuty-Test}]' \
  --query "Instances[0].InstanceId" \
  --output text)

echo "INSTANCE_ID=$INSTANCE_ID"

# Wait for instance to be running
echo "Waiting for instance to start..."
aws ec2 wait instance-running \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text)

echo "PUBLIC_IP=$PUBLIC_IP"
echo ""
echo "✅ EC2 instance ready for threat simulation"
```

---

## Step 10 – Simulate Port Scan (Reconnaissance)

```bash
echo ""
echo "Simulating port scan attack (reconnaissance)..."
echo ""

# Simulate port scanning from local machine
echo "Running port scan on $PUBLIC_IP..."
echo "(This will trigger Recon:EC2/PortProbeUnprotectedPort)"
echo ""

# Use timeout to limit each connection attempt
for port in 22 80 443 8080 3306 5432 6379 27017; do
  timeout 1 bash -c "echo > /dev/tcp/$PUBLIC_IP/$port" 2>/dev/null \
    && echo "Port $port: Open" \
    || echo "Port $port: Closed/Filtered"
done

echo ""
echo "⚠️  Port scan completed - GuardDuty should detect this"
echo "   Finding type: Recon:EC2/PortProbeUnprotectedPort"
echo "   Severity: Medium"
```

---

## Step 11 – Simulate SSH Brute Force

```bash
echo ""
echo "Simulating SSH brute force attack..."
echo ""

# Attempt multiple failed SSH connections
echo "Attempting repeated SSH connections (will fail - expected)..."

for i in {1..10}; do
  timeout 2 ssh -o StrictHostKeyChecking=no \
    -o ConnectTimeout=1 \
    ec2-user@$PUBLIC_IP "exit" 2>/dev/null \
    || echo "Attempt $i failed (expected)"
done

echo ""
echo "⚠️  SSH brute force simulation completed"
echo "   Finding type: UnauthorizedAccess:EC2/SSHBruteForce"
echo "   Severity: Low to Medium"
echo ""
echo "⏱️  GuardDuty takes 5-15 minutes to analyze and generate findings"
```

---

## Step 12 – Check for Real Findings

```bash
echo ""
echo "Checking for new findings (excluding samples)..."
echo ""

# List non-sample findings
REAL_FINDINGS=$(aws guardduty list-findings \
  --detector-id "$DETECTOR_ID" \
  --region "$REGION" \
  --finding-criteria '{"Criterion":{"service.archived":{"Eq":["false"]}}}' \
  --query "FindingIds[]" \
  --output text)

if [ -z "$REAL_FINDINGS" ]; then
  echo "No new findings yet (GuardDuty analysis in progress)"
  echo "Check again in 10-15 minutes"
else
  echo "New findings detected: $(echo $REAL_FINDINGS | wc -w)"
  
  # Show details
  aws guardduty get-findings \
    --detector-id "$DETECTOR_ID" \
    --region "$REGION" \
    --finding-ids $REAL_FINDINGS \
    --query 'Findings[*].[Type,Severity,Title]' \
    --output table
fi

echo ""
echo "✅ Findings check complete"
```

---

## Step 13 – Create S3 Bucket for Finding Exports

```bash
echo ""
echo "================================================"
echo "EXPORTING FINDINGS"
echo "================================================"
echo ""

# Create S3 bucket for exports
EXPORT_BUCKET="guardduty-findings-${ACCOUNT_ID}"
echo "EXPORT_BUCKET=$EXPORT_BUCKET"

echo "Creating S3 bucket for finding exports..."

aws s3api create-bucket \
  --bucket "$EXPORT_BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

echo "✅ Export bucket created"

# Enable encryption
echo "Enabling bucket encryption..."

aws s3api put-bucket-encryption \
  --bucket "$EXPORT_BUCKET" \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

echo "✅ Bucket encryption enabled"
```

---

## Step 14 – Configure Finding Export to S3

```bash
echo ""
echo "Configuring GuardDuty to export findings to S3..."

# Create bucket policy for GuardDuty
cat > /tmp/guardduty-bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowGuardDutyToWriteFindings",
      "Effect": "Allow",
      "Principal": {
        "Service": "guardduty.amazonaws.com"
      },
      "Action": [
        "s3:PutObject",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::${EXPORT_BUCKET}/*",
        "arn:aws:s3:::${EXPORT_BUCKET}"
      ]
    }
  ]
}
EOF

# Apply bucket policy
aws s3api put-bucket-policy \
  --bucket "$EXPORT_BUCKET" \
  --policy file:///tmp/guardduty-bucket-policy.json

echo "✅ Bucket policy configured for GuardDuty"
echo ""

# Create publishing destination
echo "Creating publishing destination..."

DESTINATION_ID=$(aws guardduty create-publishing-destination \
  --detector-id "$DETECTOR_ID" \
  --destination-type S3 \
  --destination-properties "{\"DestinationArn\":\"arn:aws:s3:::${EXPORT_BUCKET}\",\"KmsKeyArn\":\"\"}" \
  --region "$REGION" \
  --query 'DestinationId' \
  --output text)

echo "DESTINATION_ID=$DESTINATION_ID"
echo "✅ GuardDuty will export findings to S3"
```

---

## Step 15 – Archive Sample Findings

```bash
echo ""
echo "Archiving sample findings (keeping real findings visible)..."

# Archive all sample findings
if [ ! -z "$FINDING_IDS" ]; then
  # Get only sample findings
  SAMPLE_IDS=$(aws guardduty list-findings \
    --detector-id "$DETECTOR_ID" \
    --region "$REGION" \
    --finding-criteria '{"Criterion":{"service.archived":{"Eq":["false"]},"sample":{"Eq":["true"]}}}' \
    --query "FindingIds[]" \
    --output text)
  
  if [ ! -z "$SAMPLE_IDS" ]; then
    aws guardduty archive-findings \
      --detector-id "$DETECTOR_ID" \
      --region "$REGION" \
      --finding-ids $SAMPLE_IDS
    
    echo "✅ Sample findings archived"
  else
    echo "No sample findings to archive"
  fi
else
  echo "No findings to archive"
fi
```

---

## Step 16 – Enable Security Hub Integration

```bash
echo ""
echo "================================================"
echo "INTEGRATING WITH SECURITY HUB"
echo "================================================"
echo ""

# Enable Security Hub
echo "Enabling AWS Security Hub..."

aws securityhub enable-security-hub \
  --region "$REGION" 2>/dev/null \
  && echo "✅ Security Hub enabled" \
  || echo "Security Hub already enabled or not available"

echo ""

# Enable GuardDuty integration
echo "Enabling GuardDuty product integration..."

aws securityhub enable-import-findings-for-product \
  --product-arn "arn:aws:securityhub:${REGION}::product/aws/guardduty" \
  --region "$REGION" 2>/dev/null \
  && echo "✅ GuardDuty findings will flow to Security Hub" \
  || echo "Integration already enabled"
```

---

## Step 17 – Create EventBridge Rule for High Severity Alerts

```bash
echo ""
echo "Creating EventBridge rule for high-severity findings..."

# Create EventBridge rule for high severity
aws events put-rule \
  --name guardduty-high-severity-alert \
  --description "Alert on high severity GuardDuty findings" \
  --event-pattern '{
    "source": ["aws.guardduty"],
    "detail-type": ["GuardDuty Finding"],
    "detail": {
      "severity": [7, 8, 9]
    }
  }' \
  --region "$REGION"

echo "✅ EventBridge rule created"
echo ""
echo "Note: Add SNS topic target to receive email alerts"
```

---

## Step 18 – View GuardDuty Console

```bash
echo ""
echo "================================================"
echo "VIEW FINDINGS IN CONSOLE"
echo "================================================"
echo ""

echo "View GuardDuty findings in the AWS Console:"
echo ""
echo "https://${REGION}.console.aws.amazon.com/guardduty/home?region=${REGION}#/findings"
echo ""
echo "Finding types to look for:"
echo "  - Recon:EC2/PortProbeUnprotectedPort (from port scan)"
echo "  - UnauthorizedAccess:EC2/SSHBruteForce (from SSH attempts)"
echo ""
echo "⏱️  Note: Real findings may take 10-15 minutes to appear"
```

---

## Step 19 – Export Finding Statistics

```bash
echo ""
echo "Generating finding statistics..."

# Get finding statistics
aws guardduty get-findings-statistics \
  --detector-id "$DETECTOR_ID" \
  --finding-statistic-types COUNT_BY_SEVERITY \
  --region "$REGION" \
  --query 'FindingStatistics.CountBySeverity' \
  --output json

echo ""
echo "✅ Statistics generated"
```

---

## Step 20 – Cleanup

```bash
echo ""
echo "================================================"
echo "CLEANUP"
echo "================================================"
echo ""

echo "Cleaning up resources..."

# Terminate EC2 instance
echo "Terminating EC2 instance..."
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" > /dev/null

echo "✅ Instance terminated"

# Wait for termination
aws ec2 wait instance-terminated \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" 2>/dev/null &

# Delete security group (after instance terminates)
sleep 60
aws ec2 delete-security-group \
  --group-id "$SG_ID" \
  --region "$REGION" 2>/dev/null \
  && echo "✅ Security group deleted" \
  || echo "Security group will be deleted after instance termination"

# Delete publishing destination
echo "Deleting publishing destination..."
aws guardduty delete-publishing-destination \
  --detector-id "$DETECTOR_ID" \
  --destination-id "$DESTINATION_ID" \
  --region "$REGION" 2>/dev/null

echo "✅ Publishing destination deleted"

# Delete S3 bucket
echo "Deleting S3 bucket..."
aws s3 rb s3://"$EXPORT_BUCKET" --force --region "$REGION"

echo "✅ Export bucket deleted"

# Delete EventBridge rule
echo "Deleting EventBridge rule..."
aws events remove-targets \
  --rule guardduty-high-severity-alert \
  --ids "1" \
  --region "$REGION" 2>/dev/null

aws events delete-rule \
  --name guardduty-high-severity-alert \
  --region "$REGION" 2>/dev/null

echo "✅ EventBridge rule deleted"

# Disable Security Hub (optional - comment out if you want to keep it)
# aws securityhub disable-security-hub --region "$REGION" 2>/dev/null

# Disable GuardDuty detector
echo "Disabling GuardDuty detector..."
aws guardduty delete-detector \
  --detector-id "$DETECTOR_ID" \
  --region "$REGION"

echo "✅ GuardDuty detector deleted"
echo ""
echo "All resources cleaned up!"
```

---

## Summary

In this lab, you have:
- Enabled Amazon GuardDuty for continuous threat monitoring
- Verified data sources (CloudTrail, VPC Flow Logs, DNS)
- Generated sample findings across all threat categories
- Deployed EC2 instance for threat simulation
- Simulated port scanning and SSH brute force attacks
- Filtered findings by severity levels
- Exported findings to S3 for archival
- Integrated GuardDuty with AWS Security Hub
- Created EventBridge rules for automated alerting
- Reviewed findings in console and CLI

**Key Takeaways:**
- **Continuous Monitoring**: GuardDuty analyzes billions of events across accounts
- **Machine Learning**: Automatically detects anomalies without signatures
- **Threat Intelligence**: Uses AWS and partner threat feeds
- **Low Overhead**: Serverless, no infrastructure to manage
- **Automated Response**: Integrate with EventBridge and Lambda for remediation

---

## Best Practices

**Deployment:**
- Enable GuardDuty in all accounts and regions
- Use AWS Organizations for centralized management
- Enable all data source protection (S3, EKS, etc.)
- Maintain 90-day finding retention

**Detection:**
- Regularly review high and medium severity findings
- Create custom threat lists for your environment
- Tune suppression rules to reduce false positives
- Enable Malware Protection for EC2 and ECS

**Response:**
- Integrate with Security Hub for unified view
- Create EventBridge rules for automated remediation
- Set up SNS notifications for critical findings
- Document incident response playbooks

**Cost Optimization:**
- Monitor CloudTrail event volume
- Optimize VPC Flow Log retention
- Archive old findings to S3
- Use GuardDuty free trial (30 days)

---

## Troubleshooting

**No findings appear:**
- Wait 10-15 minutes after creating resources
- Verify GuardDuty detector is ENABLED
- Check if data sources are active
- Generate sample findings for testing

**Sample findings don't generate:**
- Ensure detector ID is correct
- Check IAM permissions for GuardDuty
- Verify region is correct
- Use: `aws guardduty create-sample-findings --detector-id $DETECTOR_ID`

**Real findings not detected:**
- GuardDuty requires time to establish baselines
- Threat simulation may be too subtle
- Check CloudTrail is logging API calls
- Ensure VPC Flow Logs are enabled

**High costs:**
- Review CloudTrail event volume (top cost driver)
- Disable GuardDuty in unused regions
- Monitor VPC Flow Log data processed
- Use AWS Cost Explorer for GuardDuty breakdown

**Export to S3 fails:**
- Verify bucket policy allows GuardDuty
- Check bucket exists in same region
- Ensure KMS key permissions (if using encryption)
- Review GuardDuty service role permissions

---

## Additional Resources

- [Amazon GuardDuty Documentation](https://docs.aws.amazon.com/guardduty/)
- [GuardDuty Finding Types](https://docs.aws.amazon.com/guardduty/latest/ug/guardduty_finding-types-active.html)
- [GuardDuty Best Practices](https://docs.aws.amazon.com/guardduty/latest/ug/guardduty_best-practices.html)
- [GuardDuty Pricing](https://aws.amazon.com/guardduty/pricing/)
- [Automated Response Guide](https://docs.aws.amazon.com/guardduty/latest/ug/guardduty_findings.html)
