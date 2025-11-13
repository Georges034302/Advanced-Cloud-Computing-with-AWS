# Lab 13.A: AWS Config - Track Resource Compliance

## Overview
This lab introduces AWS Config, a service that continuously monitors and records AWS resource configurations and evaluates them against compliance rules. You'll enable AWS Config, create compliance rules, deploy non-compliant resources, detect violations, remediate issues, and verify compliance.

**💰 Cost**: AWS Config: $0.003 per configuration item + $0.001 per rule evaluation. Minimal cost for short lab.

---

## Objectives
- Enable AWS Config with configuration recorder and delivery channel
- Track configuration changes for AWS resources
- Create AWS Config managed compliance rules
- Deploy intentionally non-compliant resources
- Detect and evaluate compliance violations
- Remediate non-compliant resources
- Verify compliance status

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for AWS Config, S3, EC2, IAM
- Region: ap-southeast-2

---

## Architecture

```
AWS Resources (EC2, S3, etc.)
          ↓
  Configuration Recorder
          ↓
  S3 Bucket (Config Logs)
          ↓
  Compliance Rules Evaluation
  ├─ Required Tags
  ├─ S3 Versioning
  └─ EC2 SSM Management
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

# Set bucket name for Config logs
BUCKET_NAME="aws-config-logs-${ACCOUNT_ID}"
echo "BUCKET_NAME=$BUCKET_NAME"
```

---

## Step 2 – Create S3 Bucket for Config Logs

```bash
echo ""
echo "Creating S3 bucket for AWS Config logs..."

# Create bucket
aws s3api create-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

echo "✅ Bucket created: $BUCKET_NAME"

# Enable bucket encryption
echo "Enabling bucket encryption..."

aws s3api put-bucket-encryption \
  --bucket "$BUCKET_NAME" \
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

## Step 3 – Create IAM Service-Linked Role for AWS Config

```bash
echo ""
echo "Creating IAM service-linked role for AWS Config..."

# Create service-linked role (if not exists)
aws iam create-service-linked-role \
  --aws-service-name config.amazonaws.com 2>/dev/null \
  || echo "Service-linked role already exists"

echo "✅ IAM role ready for AWS Config"

# The role ARN will be
CONFIG_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig"
echo "CONFIG_ROLE_ARN=$CONFIG_ROLE_ARN"
```

---

## Step 4 – Create Delivery Channel

```bash
echo ""
echo "================================================"
echo "CONFIGURING AWS CONFIG"
echo "================================================"
echo ""

# Create delivery channel
echo "Creating delivery channel to S3..."

aws configservice put-delivery-channel \
  --delivery-channel "name=default,s3BucketName=$BUCKET_NAME" \
  --region "$REGION"

echo "✅ Delivery channel created (logs → $BUCKET_NAME)"
```

---

## Step 5 – Create and Start Configuration Recorder

```bash
echo ""
echo "Creating configuration recorder..."

# Create configuration recorder
aws configservice put-configuration-recorder \
  --configuration-recorder "{
    \"name\": \"default\",
    \"roleARN\": \"$CONFIG_ROLE_ARN\",
    \"recordingGroup\": {
      \"allSupported\": true,
      \"includeGlobalResourceTypes\": true
    }
  }" \
  --region "$REGION"

echo "✅ Configuration recorder created"

# Start recording
echo "Starting configuration recorder..."

aws configservice start-configuration-recorder \
  --configuration-recorder-name default \
  --region "$REGION"

echo "✅ AWS Config is now recording resource configurations"
```

---

## Step 6 – Create Config Rule: Required Tags

```bash
echo ""
echo "================================================"
echo "CREATING COMPLIANCE RULES"
echo "================================================"
echo ""

echo "Creating rule: required-tags (check for Environment tag)..."

# Create required-tags rule
aws configservice put-config-rule \
  --config-rule '{
    "ConfigRuleName": "required-tags",
    "Description": "Ensure EC2 instances have Environment tag",
    "Scope": {
      "ComplianceResourceTypes": ["AWS::EC2::Instance"]
    },
    "Source": {
      "Owner": "AWS",
      "SourceIdentifier": "REQUIRED_TAGS"
    },
    "InputParameters": "{\"tag1Key\":\"Environment\"}"
  }' \
  --region "$REGION"

echo "✅ Rule created: required-tags"
```

---

## Step 7 – Create Config Rule: S3 Bucket Versioning

```bash
echo ""
echo "Creating rule: s3-bucket-versioning-enabled..."

# Create S3 versioning rule
aws configservice put-config-rule \
  --config-rule '{
    "ConfigRuleName": "s3-bucket-versioning-enabled",
    "Description": "Ensure all S3 buckets have versioning enabled",
    "Source": {
      "Owner": "AWS",
      "SourceIdentifier": "S3_BUCKET_VERSIONING_ENABLED"
    }
  }' \
  --region "$REGION"

echo "✅ Rule created: s3-bucket-versioning-enabled"
```

---

## Step 8 – Create Config Rule: EC2 Managed by SSM

```bash
echo ""
echo "Creating rule: ec2-instance-managed-by-ssm..."

# Create EC2 SSM rule
aws configservice put-config-rule \
  --config-rule '{
    "ConfigRuleName": "ec2-instance-managed-by-ssm",
    "Description": "Ensure EC2 instances are managed by Systems Manager",
    "Source": {
      "Owner": "AWS",
      "SourceIdentifier": "EC2_INSTANCE_MANAGED_BY_SSM"
    }
  }' \
  --region "$REGION"

echo "✅ Rule created: ec2-instance-managed-by-ssm"
echo ""
echo "All compliance rules created!"
```

---

## Step 9 – View Config Rules

```bash
echo ""
echo "Listing all Config rules..."

aws configservice describe-config-rules \
  --region "$REGION" \
  --query 'ConfigRules[*].[ConfigRuleName,ConfigRuleState]' \
  --output table

echo ""
echo "✅ Config rules are active"
```

---

## Step 10 – Create Non-Compliant EC2 Instance

```bash
echo ""
echo "================================================"
echo "CREATING NON-COMPLIANT RESOURCES"
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

# Launch EC2 instance WITHOUT Environment tag (non-compliant)
echo "Launching EC2 instance WITHOUT required Environment tag..."

INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --region "$REGION" \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=NonCompliantInstance}]' \
  --query "Instances[0].InstanceId" \
  --output text)

echo "INSTANCE_ID=$INSTANCE_ID"
echo "⚠️  Instance created WITHOUT Environment tag (non-compliant)"
```

---

## Step 11 – Create Non-Compliant S3 Bucket

```bash
echo ""
echo "Creating S3 bucket WITHOUT versioning (non-compliant)..."

# Create bucket without versioning
BAD_BUCKET="unversioned-bucket-${ACCOUNT_ID}"
echo "BAD_BUCKET=$BAD_BUCKET"

aws s3api create-bucket \
  --bucket "$BAD_BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

echo "⚠️  S3 bucket created WITHOUT versioning (non-compliant)"
```

---

## Step 12 – Wait for Config to Record Resources

```bash
echo ""
echo "Waiting for AWS Config to record new resources..."
echo "(Config takes 1-2 minutes to detect new resources)"

sleep 90

echo "✅ Resources should now be recorded"
```

---

## Step 13 – Trigger Compliance Evaluation

```bash
echo ""
echo "================================================"
echo "EVALUATING COMPLIANCE"
echo "================================================"
echo ""

echo "Triggering compliance evaluation for all rules..."

# Start evaluation for all rules
aws configservice start-config-rules-evaluation \
  --config-rule-names \
    required-tags \
    s3-bucket-versioning-enabled \
    ec2-instance-managed-by-ssm \
  --region "$REGION"

echo ""
echo "Waiting for evaluation to complete (30 seconds)..."
sleep 30

echo "✅ Evaluation triggered"
```

---

## Step 14 – View Compliance Results

```bash
echo ""
echo "================================================"
echo "COMPLIANCE RESULTS (BEFORE FIX)"
echo "================================================"
echo ""

# Get compliance summary
aws configservice describe-compliance-by-config-rule \
  --region "$REGION" \
  --output table

echo ""
echo "Expected results:"
echo "  - required-tags: NON_COMPLIANT (EC2 missing Environment tag)"
echo "  - s3-bucket-versioning-enabled: NON_COMPLIANT (bucket without versioning)"
echo "  - ec2-instance-managed-by-ssm: NON_COMPLIANT (no SSM agent configured)"
```

---

## Step 15 – Get Detailed Non-Compliant Resources

```bash
echo ""
echo "Getting detailed non-compliant resources..."
echo ""

# Check required-tags compliance
echo "Non-compliant EC2 instances (missing Environment tag):"
aws configservice get-compliance-details-by-config-rule \
  --config-rule-name required-tags \
  --compliance-types NON_COMPLIANT \
  --region "$REGION" \
  --query 'EvaluationResults[*].EvaluationResultIdentifier.EvaluationResultQualifier.ResourceId' \
  --output table

echo ""

# Check S3 versioning compliance
echo "Non-compliant S3 buckets (versioning disabled):"
aws configservice get-compliance-details-by-config-rule \
  --config-rule-name s3-bucket-versioning-enabled \
  --compliance-types NON_COMPLIANT \
  --region "$REGION" \
  --query 'EvaluationResults[*].EvaluationResultIdentifier.EvaluationResultQualifier.ResourceId' \
  --output table

echo ""
echo "✅ Non-compliant resources identified"
```

---

## Step 16 – Fix Non-Compliant EC2 Instance

```bash
echo ""
echo "================================================"
echo "REMEDIATING NON-COMPLIANT RESOURCES"
echo "================================================"
echo ""

echo "Fixing EC2 instance: Adding Environment tag..."

# Add required Environment tag
aws ec2 create-tags \
  --resources "$INSTANCE_ID" \
  --tags Key=Environment,Value=Dev \
  --region "$REGION"

echo "✅ Environment=Dev tag added to instance $INSTANCE_ID"
```

---

## Step 17 – Fix Non-Compliant S3 Bucket

```bash
echo ""
echo "Fixing S3 bucket: Enabling versioning..."

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket "$BAD_BUCKET" \
  --versioning-configuration Status=Enabled \
  --region "$REGION"

echo "✅ Versioning enabled on bucket $BAD_BUCKET"
```

---

## Step 18 – Re-Evaluate Compliance

```bash
echo ""
echo "Re-evaluating compliance after fixes..."

# Trigger re-evaluation
aws configservice start-config-rules-evaluation \
  --config-rule-names \
    required-tags \
    s3-bucket-versioning-enabled \
  --region "$REGION"

echo ""
echo "Waiting for re-evaluation (30 seconds)..."
sleep 30

echo "✅ Re-evaluation complete"
```

---

## Step 19 – View Updated Compliance Results

```bash
echo ""
echo "================================================"
echo "COMPLIANCE RESULTS (AFTER FIX)"
echo "================================================"
echo ""

# Get updated compliance summary
aws configservice describe-compliance-by-config-rule \
  --region "$REGION" \
  --output table

echo ""
echo "Expected results:"
echo "  - required-tags: COMPLIANT ✅"
echo "  - s3-bucket-versioning-enabled: COMPLIANT ✅"
echo "  - ec2-instance-managed-by-ssm: Still NON_COMPLIANT (SSM agent not configured)"
```

---

## Step 20 – Cleanup

```bash
echo ""
echo "Cleaning up resources..."

# Terminate EC2 instance
echo "Terminating EC2 instance..."
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" > /dev/null

echo "✅ Instance terminated"

# Delete S3 bucket
echo "Deleting S3 bucket..."
aws s3 rb s3://"$BAD_BUCKET" --force --region "$REGION"

echo "✅ Bucket deleted"

# Delete Config rules
echo "Deleting Config rules..."
aws configservice delete-config-rule \
  --config-rule-name required-tags \
  --region "$REGION"

aws configservice delete-config-rule \
  --config-rule-name s3-bucket-versioning-enabled \
  --region "$REGION"

aws configservice delete-config-rule \
  --config-rule-name ec2-instance-managed-by-ssm \
  --region "$REGION"

echo "✅ Config rules deleted"

# Stop configuration recorder
echo "Stopping configuration recorder..."
aws configservice stop-configuration-recorder \
  --configuration-recorder-name default \
  --region "$REGION"

echo "✅ Configuration recorder stopped"

# Delete configuration recorder
aws configservice delete-configuration-recorder \
  --configuration-recorder-name default \
  --region "$REGION" 2>/dev/null

# Delete delivery channel
aws configservice delete-delivery-channel \
  --delivery-channel-name default \
  --region "$REGION" 2>/dev/null

echo "✅ Config recorder and delivery channel deleted"

# Delete Config logs bucket
echo "Deleting Config logs bucket..."
aws s3 rb s3://"$BUCKET_NAME" --force --region "$REGION"

echo "✅ Config logs bucket deleted"
echo ""
echo "All resources cleaned up!"
```

---

## Summary

In this lab, you have:
- Enabled AWS Config with configuration recorder and delivery channel
- Created S3 bucket for configuration logs with encryption
- Set up three AWS Config managed rules for compliance
- Deployed non-compliant EC2 instance and S3 bucket
- Evaluated compliance status
- Identified non-compliant resources
- Remediated issues by adding tags and enabling versioning
- Re-evaluated and verified compliance

**Key Takeaways:**
- **Continuous Monitoring**: AWS Config tracks all resource changes
- **Compliance Rules**: Use managed or custom rules for governance
- **Automatic Detection**: Violations detected immediately
- **Audit Trail**: All configurations stored in S3 for compliance audits
- **Remediation**: Manual or automated fixes with AWS Systems Manager

---

## Best Practices

**Configuration:**
- Enable AWS Config in all regions and accounts
- Use AWS Organizations for multi-account Config
- Enable global resource recording (IAM, etc.)
- Encrypt S3 bucket for Config logs

**Rules:**
- Start with AWS managed rules (100+ available)
- Create custom rules with Lambda for specific needs
- Use conformance packs for industry standards (PCI-DSS, HIPAA)
- Tag resources for better organization

**Remediation:**
- Use AWS Systems Manager Automation for auto-remediation
- Set up SNS notifications for compliance violations
- Integrate with Security Hub for centralized view
- Regular compliance reports for audits

**Cost Optimization:**
- Monitor configuration items recorded
- Use resource-specific recording (not all resources)
- Disable rules you don't need
- Archive old config logs to Glacier

---

## Troubleshooting

**Rule shows INSUFFICIENT_DATA:**
- Wait for resources to be recorded (takes 1-2 minutes)
- Trigger manual evaluation
- Ensure resources exist that match rule scope

**Access Denied errors:**
- Verify service-linked role exists
- Check S3 bucket permissions
- Ensure IAM permissions for Config service

**Rules not evaluating:**
- Check if recorder is running
- Verify delivery channel is configured
- Ensure resources match rule scope
- Check CloudWatch Logs for rule errors

**High costs:**
- Review number of configuration items
- Limit recording to specific resource types
- Delete unused rules
- Check evaluation frequency

---

## Additional Resources

- [AWS Config Documentation](https://docs.aws.amazon.com/config/)
- [Managed Rules Reference](https://docs.aws.amazon.com/config/latest/developerguide/managed-rules-by-aws-config.html)
- [Conformance Packs](https://docs.aws.amazon.com/config/latest/developerguide/conformance-packs.html)
- [AWS Config Pricing](https://aws.amazon.com/config/pricing/)
- [Auto Remediation](https://docs.aws.amazon.com/config/latest/developerguide/remediation.html)
