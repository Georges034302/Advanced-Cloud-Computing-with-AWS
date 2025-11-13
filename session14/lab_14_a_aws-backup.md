# Lab 14.A: AWS Backup - Centralized Backup Solution

## Overview
This lab introduces AWS Backup, a fully managed service that centralizes and automates backups across AWS services including EC2, EBS, RDS, DynamoDB, and EFS. You'll create a backup vault, configure backup plans with schedules and lifecycle policies, perform on-demand backups, and restore resources from backups.

---

## Objectives
- Create AWS Backup Vault with encryption
- Configure backup plan with schedules and retention policies
- Create IAM service role for AWS Backup
- Launch EC2 instance for backup testing
- Assign resources to backup plan
- Perform on-demand backup
- Monitor backup job status
- Restore EC2 instance from backup
- Clean up backup vault and resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for AWS Backup, EC2, IAM
- Region: ap-southeast-2
- Basic understanding of backup strategies

---

## Architecture

```
AWS Backup Vault (Encrypted)
          ↓
    Backup Plan
    ├─ Schedule: Daily at 5 AM UTC
    ├─ Retention: 30 days
    └─ Lifecycle: Delete after 30 days
          ↓
  Protected Resources
  ├─ EC2 Instances
  ├─ EBS Volumes
  ├─ RDS Databases
  └─ DynamoDB Tables
          ↓
  Recovery Points
  (Point-in-time backups)
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

# Set backup vault and plan names
VAULT_NAME="central-backup-vault"
PLAN_NAME="daily-backup-plan"

echo "VAULT_NAME=$VAULT_NAME"
echo "PLAN_NAME=$PLAN_NAME"
echo ""
echo "================================================"
echo "AWS BACKUP CONFIGURATION"
echo "================================================"
```

---

## Step 2 – Create Backup Vault

```bash
echo ""
echo "Creating backup vault..."

# Create backup vault with default KMS encryption
aws backup create-backup-vault \
  --backup-vault-name "$VAULT_NAME" \
  --region "$REGION"

echo "✅ Backup vault created: $VAULT_NAME"
```

---

## Step 3 – Create IAM Service Role

```bash
echo ""
echo "Creating IAM service role for AWS Backup..."

# Check if role already exists
ROLE_EXISTS=$(aws iam get-role \
  --role-name AWSBackupDefaultServiceRole \
  2>/dev/null)

if [ $? -eq 0 ]; then
  echo "AWSBackupDefaultServiceRole already exists"
else
  # Create trust policy
  cat > /tmp/backup-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "backup.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

  # Create role
  aws iam create-role \
    --role-name AWSBackupDefaultServiceRole \
    --assume-role-policy-document file:///tmp/backup-trust-policy.json \
    --description "Default service role for AWS Backup"

  # Attach managed policies
  aws iam attach-role-policy \
    --role-name AWSBackupDefaultServiceRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup

  aws iam attach-role-policy \
    --role-name AWSBackupDefaultServiceRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores

  echo "✅ IAM role created and policies attached"
fi

# Set role ARN
BACKUP_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/AWSBackupDefaultServiceRole"
echo "BACKUP_ROLE_ARN=$BACKUP_ROLE_ARN"
```

---

## Step 4 – Create Backup Plan

```bash
echo ""
echo "Creating backup plan with daily schedule..."

# Create backup plan JSON
cat > /tmp/backup-plan.json <<EOF
{
  "BackupPlanName": "${PLAN_NAME}",
  "Rules": [
    {
      "RuleName": "DailyBackupRule",
      "TargetBackupVaultName": "${VAULT_NAME}",
      "ScheduleExpression": "cron(0 5 * * ? *)",
      "StartWindowMinutes": 60,
      "CompletionWindowMinutes": 180,
      "Lifecycle": {
        "DeleteAfterDays": 30
      },
      "RecoveryPointTags": {
        "BackupType": "Automated",
        "Environment": "Demo"
      }
    }
  ]
}
EOF

# Create backup plan
PLAN_ID=$(aws backup create-backup-plan \
  --backup-plan file:///tmp/backup-plan.json \
  --region "$REGION" \
  --query 'BackupPlanId' \
  --output text)

echo "PLAN_ID=$PLAN_ID"
echo "✅ Backup plan created"
echo "   Schedule: Daily at 5:00 AM UTC"
echo "   Retention: 30 days"
```

---

## Step 5 – Launch EC2 Instance for Backup

```bash
echo ""
echo "================================================"
echo "CREATING RESOURCES TO BACKUP"
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

echo "Launching EC2 instance..."

# Launch instance with tags
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --region "$REGION" \
  --tag-specifications 'ResourceType=instance,Tags=[
    {Key=Name,Value=BackupTestInstance},
    {Key=BackupEnabled,Value=true},
    {Key=Environment,Value=Demo}
  ]' \
  --query "Instances[0].InstanceId" \
  --output text)

echo "INSTANCE_ID=$INSTANCE_ID"

# Wait for instance to be running
echo "Waiting for instance to start..."
aws ec2 wait instance-running \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

echo "✅ EC2 instance launched and running"
```

---

## Step 6 – Assign Resource to Backup Plan

```bash
echo ""
echo "Assigning EC2 instance to backup plan..."

# Create backup selection
aws backup create-backup-selection \
  --backup-plan-id "$PLAN_ID" \
  --backup-selection "{
    \"SelectionName\": \"EC2BackupSelection\",
    \"IamRoleArn\": \"${BACKUP_ROLE_ARN}\",
    \"Resources\": [
      \"arn:aws:ec2:${REGION}:${ACCOUNT_ID}:instance/${INSTANCE_ID}\"
    ],
    \"ListOfTags\": [
      {
        \"ConditionType\": \"STRINGEQUALS\",
        \"ConditionKey\": \"BackupEnabled\",
        \"ConditionValue\": \"true\"
      }
    ]
  }" \
  --region "$REGION"

echo "✅ EC2 instance assigned to backup plan"
echo "   Automated backups will run daily at 5 AM UTC"
```

---

## Step 7 – Start On-Demand Backup

```bash
echo ""
echo "================================================"
echo "PERFORMING ON-DEMAND BACKUP"
echo "================================================"
echo ""

echo "Starting immediate backup of EC2 instance..."

# Start on-demand backup
BACKUP_JOB_ID=$(aws backup start-backup-job \
  --backup-vault-name "$VAULT_NAME" \
  --resource-arn "arn:aws:ec2:${REGION}:${ACCOUNT_ID}:instance/${INSTANCE_ID}" \
  --iam-role-arn "$BACKUP_ROLE_ARN" \
  --region "$REGION" \
  --query 'BackupJobId' \
  --output text)

echo "BACKUP_JOB_ID=$BACKUP_JOB_ID"
echo "✅ Backup job started"
```

---

## Step 8 – Monitor Backup Job

```bash
echo ""
echo "Monitoring backup job progress..."
echo "(This may take 2-5 minutes)"
echo ""

# Monitor backup job status
while true; do
  STATUS=$(aws backup describe-backup-job \
    --backup-job-id "$BACKUP_JOB_ID" \
    --region "$REGION" \
    --query 'State' \
    --output text)
  
  PERCENT=$(aws backup describe-backup-job \
    --backup-job-id "$BACKUP_JOB_ID" \
    --region "$REGION" \
    --query 'PercentDone' \
    --output text)
  
  echo "Status: $STATUS - Progress: ${PERCENT}%"
  
  if [ "$STATUS" == "COMPLETED" ]; then
    echo ""
    echo "✅ Backup completed successfully!"
    break
  elif [ "$STATUS" == "FAILED" ] || [ "$STATUS" == "ABORTED" ]; then
    echo "❌ Backup failed with status: $STATUS"
    break
  fi
  
  sleep 10
done
```

---

## Step 9 – List Recovery Points

```bash
echo ""
echo "Listing recovery points in backup vault..."

# List all recovery points
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name "$VAULT_NAME" \
  --region "$REGION" \
  --query 'RecoveryPoints[*].{
    RecoveryPointArn:RecoveryPointArn,
    ResourceType:ResourceType,
    CreationDate:CreationDate,
    Status:Status,
    Size:BackupSizeInBytes
  }' \
  --output table

echo ""
echo "✅ Recovery points listed"
```

---

## Step 10 – Get Recovery Point ARN

```bash
echo ""
echo "Getting recovery point ARN for restore..."

# Get the latest recovery point
RECOVERY_POINT_ARN=$(aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name "$VAULT_NAME" \
  --region "$REGION" \
  --query 'sort_by(RecoveryPoints, &CreationDate)[-1].RecoveryPointArn' \
  --output text)

echo "RECOVERY_POINT_ARN=$RECOVERY_POINT_ARN"
echo ""
echo "✅ Recovery point identified"
```

---

## Step 11 – Restore EC2 Instance

```bash
echo ""
echo "================================================"
echo "RESTORING FROM BACKUP"
echo "================================================"
echo ""

echo "Starting restore job..."

# Prepare restore metadata
cat > /tmp/restore-metadata.json <<EOF
{
  "InstanceType": "t2.micro",
  "SubnetId": ""
}
EOF

# Start restore job
RESTORE_JOB_ID=$(aws backup start-restore-job \
  --recovery-point-arn "$RECOVERY_POINT_ARN" \
  --metadata file:///tmp/restore-metadata.json \
  --iam-role-arn "$BACKUP_ROLE_ARN" \
  --region "$REGION" \
  --query 'RestoreJobId' \
  --output text)

echo "RESTORE_JOB_ID=$RESTORE_JOB_ID"
echo "✅ Restore job started"
```

---

## Step 12 – Monitor Restore Job

```bash
echo ""
echo "Monitoring restore job progress..."
echo "(This may take 3-10 minutes)"
echo ""

# Monitor restore job status
while true; do
  RESTORE_STATUS=$(aws backup describe-restore-job \
    --restore-job-id "$RESTORE_JOB_ID" \
    --region "$REGION" \
    --query 'Status' \
    --output text)
  
  echo "Restore Status: $RESTORE_STATUS"
  
  if [ "$RESTORE_STATUS" == "COMPLETED" ]; then
    echo ""
    echo "✅ Restore completed successfully!"
    
    # Get restored resource ID
    RESTORED_RESOURCE=$(aws backup describe-restore-job \
      --restore-job-id "$RESTORE_JOB_ID" \
      --region "$REGION" \
      --query 'CreatedResourceArn' \
      --output text)
    
    echo "RESTORED_RESOURCE=$RESTORED_RESOURCE"
    break
  elif [ "$RESTORE_STATUS" == "FAILED" ] || [ "$RESTORE_STATUS" == "ABORTED" ]; then
    echo "❌ Restore failed with status: $RESTORE_STATUS"
    break
  fi
  
  sleep 15
done
```

---

## Step 13 – View Backup Plan Details

```bash
echo ""
echo "Viewing backup plan details..."

# Get backup plan details
aws backup get-backup-plan \
  --backup-plan-id "$PLAN_ID" \
  --region "$REGION" \
  --query 'BackupPlan.{
    Name:BackupPlanName,
    Rules:Rules[*].{
      Name:RuleName,
      Schedule:ScheduleExpression,
      Retention:Lifecycle.DeleteAfterDays
    }
  }' \
  --output json

echo ""
echo "✅ Backup plan details retrieved"
```

---

## Step 14 – List Backup Jobs

```bash
echo ""
echo "Listing all backup jobs..."

# List recent backup jobs
aws backup list-backup-jobs \
  --by-backup-vault-name "$VAULT_NAME" \
  --region "$REGION" \
  --query 'BackupJobs[*].{
    JobId:BackupJobId,
    ResourceType:ResourceType,
    Status:State,
    Created:CreationDate,
    Completed:CompletionDate
  }' \
  --output table

echo ""
echo "✅ Backup jobs listed"
```

---

## Step 15 – Cleanup

```bash
echo ""
echo "================================================"
echo "CLEANUP"
echo "================================================"
echo ""

echo "Cleaning up resources..."

# Terminate original EC2 instance
echo "Terminating original EC2 instance..."
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" > /dev/null

echo "✅ Original instance terminated"

# Terminate restored instance if exists
if [ ! -z "$RESTORED_RESOURCE" ]; then
  RESTORED_INSTANCE_ID=$(echo "$RESTORED_RESOURCE" | awk -F'/' '{print $NF}')
  
  echo "Terminating restored instance..."
  aws ec2 terminate-instances \
    --instance-ids "$RESTORED_INSTANCE_ID" \
    --region "$REGION" > /dev/null 2>&1
  
  echo "✅ Restored instance terminated"
fi

# Wait for instances to terminate
sleep 30

# Delete recovery points
echo "Deleting recovery points..."
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name "$VAULT_NAME" \
  --region "$REGION" \
  --query 'RecoveryPoints[*].RecoveryPointArn' \
  --output text | while read RP_ARN; do
    aws backup delete-recovery-point \
      --backup-vault-name "$VAULT_NAME" \
      --recovery-point-arn "$RP_ARN" \
      --region "$REGION" 2>/dev/null
done

echo "✅ Recovery points deleted"

# Delete backup selections
echo "Deleting backup selections..."
SELECTION_ID=$(aws backup list-backup-selections \
  --backup-plan-id "$PLAN_ID" \
  --region "$REGION" \
  --query 'BackupSelectionsList[0].SelectionId' \
  --output text 2>/dev/null)

if [ ! -z "$SELECTION_ID" ] && [ "$SELECTION_ID" != "None" ]; then
  aws backup delete-backup-selection \
    --backup-plan-id "$PLAN_ID" \
    --selection-id "$SELECTION_ID" \
    --region "$REGION"
fi

echo "✅ Backup selections deleted"

# Delete backup plan
echo "Deleting backup plan..."
aws backup delete-backup-plan \
  --backup-plan-id "$PLAN_ID" \
  --region "$REGION"

echo "✅ Backup plan deleted"

# Delete backup vault (after recovery points are gone)
echo "Deleting backup vault..."
sleep 10

aws backup delete-backup-vault \
  --backup-vault-name "$VAULT_NAME" \
  --region "$REGION" 2>/dev/null \
  && echo "✅ Backup vault deleted" \
  || echo "⚠️  Vault will be deleted after recovery points are fully removed"

# Clean up temp files
rm -f /tmp/backup-plan.json /tmp/backup-trust-policy.json /tmp/restore-metadata.json

echo ""
echo "All resources cleaned up!"
```

---

## Summary

In this lab, you have:
- Created AWS Backup Vault for centralized backup storage
- Configured IAM service role with appropriate permissions
- Created backup plan with daily schedule and 30-day retention
- Launched EC2 instance for backup testing
- Assigned resource to backup plan using tags
- Performed on-demand backup of EC2 instance
- Monitored backup job progress to completion
- Listed recovery points in backup vault
- Restored EC2 instance from recovery point
- Monitored restore job completion
- Cleaned up all backup resources

**Key Takeaways:**
- **Centralized Management**: Single console for all AWS backup operations
- **Automated Backups**: Schedule-based backups reduce manual work
- **Lifecycle Policies**: Automatic retention and deletion saves costs
- **Cross-Service**: Backup EC2, RDS, DynamoDB, EFS from one place
- **Compliance**: Meet retention requirements with audit trails

---

## Best Practices

**Backup Planning:**
- Create separate backup plans for different RPO/RTO requirements
- Use lifecycle policies to transition to cold storage
- Enable AWS Backup Audit Manager for compliance
- Tag resources consistently for automated selection
- Test restore procedures regularly

**Security:**
- Use AWS KMS CMKs for encryption at rest
- Enable backup vault lock for immutable backups
- Implement least privilege IAM policies
- Enable CloudTrail logging for audit trails
- Use cross-region backup for disaster recovery

**Cost Optimization:**
- Set appropriate retention periods
- Use lifecycle policies for cold storage
- Delete unnecessary recovery points
- Monitor backup storage usage
- Use AWS Organizations for bulk discounts

**Monitoring:**
- Set up SNS notifications for backup failures
- Monitor backup job metrics in CloudWatch
- Use AWS Backup reports for compliance
- Alert on missed backup windows
- Track recovery point age

---

## Troubleshooting

**AccessDeniedException:**
- Verify AWSBackupDefaultServiceRole exists
- Check IAM role trust policy allows backup.amazonaws.com
- Ensure role has AWSBackupServiceRolePolicyForBackup policy
- Verify resource-based policies allow backup access

**Backup job fails:**
- Check EC2 instance is running or stopped (not terminated)
- Verify instance has required tags
- Ensure backup vault is in same region
- Check EBS volume encryption compatibility
- Review CloudTrail logs for specific errors

**Cannot delete backup vault:**
- Must delete all recovery points first
- Wait for recovery points to fully delete (can take minutes)
- Check for backup vault access policies
- Ensure no active backup jobs

**Restore fails:**
- Verify IAM role has restore permissions
- Check subnet and VPC still exist
- Ensure security groups are valid
- Verify instance type is available in AZ
- Check for conflicting resource names

**High costs:**
- Review retention periods (default 35 days)
- Delete unnecessary recovery points
- Use cold storage lifecycle policies
- Monitor backup frequency
- Consider AWS Backup Audit Manager costs

---

## Additional Resources

- [AWS Backup Documentation](https://docs.aws.amazon.com/aws-backup/)
- [AWS Backup Best Practices](https://docs.aws.amazon.com/aws-backup/latest/devguide/best-practices.html)
- [Supported Resources](https://docs.aws.amazon.com/aws-backup/latest/devguide/whatisbackup.html#supported-resources)
- [AWS Backup Pricing](https://aws.amazon.com/backup/pricing/)
- [Backup Plans and Rules](https://docs.aws.amazon.com/aws-backup/latest/devguide/creating-a-backup-plan.html)
