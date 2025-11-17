# Lab 8.B: CloudTrail API Auditing and Monitoring

## Overview
This lab demonstrates AWS CloudTrail for API activity logging and security auditing. CloudTrail records all API calls made in your AWS account, creating a complete audit trail for compliance, security analysis, and troubleshooting. You'll enable CloudTrail, store logs in S3, send logs to CloudWatch for real-time monitoring, query logs with Logs Insights, and create alarms for critical API operations.

---

## Objectives
- Enable CloudTrail for comprehensive API activity logging
- Create S3 bucket for long-term log storage with encryption
- Configure CloudWatch Logs for real-time log delivery
- Query API calls with CloudWatch Logs Insights
- Create metric filters for security-critical operations
- Set up CloudWatch alarms for suspicious API activity
- View CloudTrail event history in the console
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Valid email address for security notifications
- IAM permissions for CloudTrail, S3, CloudWatch, SNS, IAM
- Understanding of AWS API operations

---

## Step 1 – Set Environment Variables

```bash
# Configure environment variables
REGION="ap-southeast-2"
ACCOUNT_ID="013709423315"
TOPIC_NAME="cloudtrail-security-alerts"
BUCKET_NAME="cloudtrail-logs-${ACCOUNT_ID}"
TRAIL_NAME="security-audit-trail"
LOG_GROUP_NAME="/aws/cloudtrail/security-audit"
ROLE_NAME="CloudTrailLogsRole"
ALARM_NAME="DeleteBucket-Alert"

echo "Trail: $TRAIL_NAME | Bucket: $BUCKET_NAME | Region: $REGION"
```

---

## Step 2 – Create SNS Topic for Security Alerts

```bash
# Create SNS topic for CloudTrail alarms
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

## Step 4 – Create S3 Bucket for CloudTrail Logs

```bash
# Create S3 bucket for CloudTrail logs
aws s3api create-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

echo "Bucket: $BUCKET_NAME"
```

---

## Step 5 – Enable S3 Bucket Encryption and Block Public Access

```bash
# Block all public access
aws s3api put-public-access-block \
  --bucket "$BUCKET_NAME" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
  --region "$REGION"

# Enable server-side encryption (AES256)
aws s3api put-bucket-encryption \
  --bucket "$BUCKET_NAME" \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }' \
  --region "$REGION"
```

---

## Step 6 – Create S3 Bucket Policy for CloudTrail

```bash
# Create bucket policy allowing CloudTrail to write logs
cat > bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AWSCloudTrailAclCheck",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudtrail.amazonaws.com"
      },
      "Action": "s3:GetBucketAcl",
      "Resource": "arn:aws:s3:::${BUCKET_NAME}"
    },
    {
      "Sid": "AWSCloudTrailWrite",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudtrail.amazonaws.com"
      },
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/AWSLogs/${ACCOUNT_ID}/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-acl": "bucket-owner-full-control"
        }
      }
    }
  ]
}
EOF

# Apply bucket policy
aws s3api put-bucket-policy \
  --bucket "$BUCKET_NAME" \
  --policy file://bucket-policy.json \
  --region "$REGION"
```

---

## Step 7 – Create CloudWatch Logs Group

```bash
# Create CloudWatch Logs group for real-time log analysis
aws logs create-log-group \
  --log-group-name "$LOG_GROUP_NAME" \
  --region "$REGION"

echo "Log group: $LOG_GROUP_NAME"
```

---

## Step 8 – Create IAM Role for CloudTrail to CloudWatch Logs

```bash
# Create trust policy allowing CloudTrail to assume role
cat > trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudtrail.amazonaws.com"
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

## Step 9 – Attach Policy to IAM Role

```bash
# Create policy allowing CloudTrail to write to CloudWatch Logs
cat > logs-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:${LOG_GROUP_NAME}:*"
    }
  ]
}
EOF

# Attach inline policy to role
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "CloudTrailLogsPolicy" \
  --policy-document file://logs-policy.json
```

---

## Step 10 – Create CloudTrail

```bash
# Wait for IAM role to propagate
sleep 10

# Create multi-region CloudTrail with log file validation
aws cloudtrail create-trail \
  --name "$TRAIL_NAME" \
  --s3-bucket-name "$BUCKET_NAME" \
  --is-multi-region-trail \
  --enable-log-file-validation \
  --cloud-watch-logs-log-group-arn "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:${LOG_GROUP_NAME}:*" \
  --cloud-watch-logs-role-arn "$ROLE_ARN" \
  --region "$REGION"

echo "CloudTrail features: multi-region, log validation, S3 + CloudWatch Logs"
```

---

## Step 11 – Start Logging

```bash
# Start CloudTrail logging
aws cloudtrail start-logging \
  --name "$TRAIL_NAME" \
  --region "$REGION"

# Verify trail status
TRAIL_STATUS=$(aws cloudtrail get-trail-status \
  --name "$TRAIL_NAME" \
  --region "$REGION" \
  --query 'IsLogging' \
  --output text)

echo "CloudTrail logging status: $TRAIL_STATUS"
```

---

## Step 12 – Generate Test API Calls

```bash
# Generate S3 API calls for CloudTrail to capture
aws s3api list-buckets --region "$REGION" > /dev/null
aws s3api get-bucket-location --bucket "$BUCKET_NAME" --region "$REGION" > /dev/null

# Generate EC2 API call
aws ec2 describe-instances --region "$REGION" > /dev/null

# Generate IAM API call
aws iam get-user 2>/dev/null || echo "No IAM user (using role)"

echo "Waiting 2min for logs to be delivered to CloudWatch Logs..."
sleep 120
```

---

## Step 13 – Query Logs with CloudWatch Logs Insights

```bash
# Calculate time range (last 10 minutes)
START_TIME=$(($(date +%s) - 600))
END_TIME=$(date +%s)

# Query 1: Recent API calls
aws logs start-query \
  --log-group-name "$LOG_GROUP_NAME" \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --query-string 'fields eventTime, eventName, userIdentity.principalId, sourceIPAddress
| filter eventName != "AssumeRole"
| sort eventTime desc
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

## Step 14 – Query for S3 Operations

```bash
# Query 2: S3 operations only
aws logs start-query \
  --log-group-name "$LOG_GROUP_NAME" \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --query-string 'fields eventTime, eventName, requestParameters.bucketName, errorCode
| filter eventSource = "s3.amazonaws.com"
| sort eventTime desc
| limit 20' \
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

## Step 15 – Query for Failed API Calls

```bash
## Step 15 – Query for Failed API Calls

```bash
# Query 3: Failed API calls (errors)
aws logs start-query \
  --log-group-name "$LOG_GROUP_NAME" \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --query-string 'fields eventTime, eventName, errorCode, errorMessage, userIdentity.principalId
| filter errorCode != ""
| sort eventTime desc
| limit 20' \
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

## Step 16 – Create Metric Filter for DeleteBucket Calls

```bash
# Create metric filter to track DeleteBucket API calls
FILTER_PATTERN='{ $.eventName = "DeleteBucket" }'

aws logs put-metric-filter \
  --log-group-name "$LOG_GROUP_NAME" \
  --filter-name "DeleteBucketCalls" \
  --filter-pattern "$FILTER_PATTERN" \
  --metric-transformations \
    metricName=DeleteBucketCount,metricNamespace=CloudTrail/Security,metricValue=1,defaultValue=0 \
  --region "$REGION"
```

---

## Step 17 – Create CloudWatch Alarm for DeleteBucket

```bash
# Create alarm to trigger on DeleteBucket API calls
aws cloudwatch put-metric-alarm \
  --alarm-name "$ALARM_NAME" \
  --alarm-description "Alert when S3 bucket is deleted" \
  --metric-name DeleteBucketCount \
  --namespace CloudTrail/Security \
  --statistic Sum \
  --period 60 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --alarm-actions "$TOPIC_ARN" \
  --treat-missing-data notBreaching \
  --region "$REGION"

echo "Alarm will trigger on DeleteBucket calls → SNS email notification"
```

---

## Step 18 – View CloudTrail Event History

```bash
# View recent CloudTrail events via API
aws cloudtrail lookup-events \
  --max-results 10 \
  --region "$REGION" \
  --query 'Events[*].{Time:EventTime,Event:EventName,User:Username,Resource:Resources[0].ResourceName}' \
  --output table
```

---

## Step 19 – View CloudTrail Console URL

```bash
# View CloudTrail events in AWS Console
echo "https://${REGION}.console.aws.amazon.com/cloudtrail/home?region=${REGION}#/events"
```

---

## Step 20 – Cleanup Resources

```bash
# Stop CloudTrail logging
aws cloudtrail stop-logging \
  --name "$TRAIL_NAME" \
  --region "$REGION"

# Delete CloudTrail
aws cloudtrail delete-trail \
  --name "$TRAIL_NAME" \
  --region "$REGION"

# Delete CloudWatch alarm
aws cloudwatch delete-alarms \
  --alarm-names "$ALARM_NAME" \
  --region "$REGION"

# Delete metric filter
aws logs delete-metric-filter \
  --log-group-name "$LOG_GROUP_NAME" \
  --filter-name "DeleteBucketCalls" \
  --region "$REGION"

# Delete CloudWatch Logs group
aws logs delete-log-group \
  --log-group-name "$LOG_GROUP_NAME" \
  --region "$REGION"

# Delete IAM role policy
aws iam delete-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "CloudTrailLogsPolicy"

# Delete IAM role
aws iam delete-role \
  --role-name "$ROLE_NAME"

# Empty and delete S3 bucket
aws s3 rm s3://"$BUCKET_NAME" --recursive --region "$REGION"

aws s3api delete-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$REGION"

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
rm -f bucket-policy.json trust-policy.json logs-policy.json query-result*.json

echo "Cleanup complete: CloudTrail, S3, CloudWatch Logs, IAM role, SNS deleted"
```

---

## Summary

In this lab, you have:
- Enabled CloudTrail for multi-region API activity logging
- Created encrypted S3 bucket for long-term log storage
- Configured CloudWatch Logs for real-time log delivery
- Created IAM role for CloudTrail to write to CloudWatch Logs
- Generated test API calls (S3, EC2, IAM operations)
- Queried logs with CloudWatch Logs Insights (all calls, S3 only, errors)
- Created metric filter to track DeleteBucket operations
- Set up CloudWatch alarm to notify on suspicious activity
- Viewed CloudTrail event history via CLI
- Cleaned up all resources

**Key Takeaways:**
- **CloudTrail**: Records ALL API calls in your AWS account
- **Multi-Region Trail**: Captures events from all AWS regions
- **Log File Validation**: Prevents log tampering with digital signatures
- **S3 Storage**: Long-term audit log retention (years)
- **CloudWatch Logs**: Real-time log analysis and alerting
- **Logs Insights**: SQL-like queries for log analysis
- **Metric Filters**: Convert log patterns to CloudWatch metrics
- **Security Monitoring**: Detect suspicious API activity automatically

**CloudTrail Event Structure:**
```json
{
  "eventTime": "2024-01-15T10:30:00Z",
  "eventName": "DeleteBucket",
  "userIdentity": {
    "type": "IAMUser",
    "principalId": "AIDAI...",
    "userName": "admin"
  },
  "sourceIPAddress": "203.0.113.42",
  "requestParameters": {
    "bucketName": "my-bucket"
  },
  "responseElements": null,
  "errorCode": "NoSuchBucket"
}
```

**Common CloudTrail Event Names:**
- **IAM**: CreateUser, DeleteUser, AttachUserPolicy, CreateAccessKey
- **S3**: CreateBucket, DeleteBucket, PutBucketPolicy, PutObject
- **EC2**: RunInstances, TerminateInstances, AuthorizeSecurityGroupIngress
- **Lambda**: CreateFunction, DeleteFunction, UpdateFunctionCode
- **RDS**: CreateDBInstance, DeleteDBInstance, ModifyDBInstance

**Logs Insights Query Patterns:**
```sql
-- Top API callers
fields userIdentity.principalId, eventName
| stats count() by userIdentity.principalId
| sort count desc

-- Failed authentication attempts
filter errorCode = "AccessDenied"
| fields eventTime, eventName, sourceIPAddress

-- Root account usage
filter userIdentity.type = "Root"
| fields eventTime, eventName, sourceIPAddress

-- Console sign-in events
filter eventName = "ConsoleLogin"
| fields eventTime, responseElements.ConsoleLogin, sourceIPAddress
```

---

## Best Practices

**CloudTrail Setup:**
- Enable multi-region trails (capture all regions in one trail)
- Turn on log file validation (prevent tampering)
- Use S3 lifecycle policies for cost optimization (archive to Glacier)
- Enable CloudWatch Logs for real-time alerting
- Restrict S3 bucket access (no public access)
- Use S3 bucket encryption (SSE-S3 or SSE-KMS)

**Log Analysis:**
- Create metric filters for critical operations (DeleteTrail, DeleteBucket, Root usage)
- Set up alarms for security events (unauthorized access, privilege escalation)
- Query logs regularly with Logs Insights
- Export logs to SIEM for advanced analytics
- Review event history for compliance audits

**Security Monitoring:**
- Alert on:
  * Root account usage
  * Console login failures
  * IAM policy changes
  * S3 bucket policy modifications
  * Security group changes
  * CloudTrail configuration changes
  * Unauthorized API calls (AccessDenied)

---

## Production Enhancements

1. **Enable Data Events**
   ```bash
   # Track S3 object-level operations (GetObject, PutObject, DeleteObject)
   aws cloudtrail put-event-selectors \
     --trail-name "$TRAIL_NAME" \
     --event-selectors '[{
       "ReadWriteType": "All",
       "IncludeManagementEvents": true,
       "DataResources": [{
         "Type": "AWS::S3::Object",
         "Values": ["arn:aws:s3:::my-sensitive-bucket/*"]
       }]
     }]'
   ```

2. **CloudTrail Lake (Advanced Analytics)**
   ```bash
   # Create event data store for 7-year retention and advanced queries
   aws cloudtrail create-event-data-store \
     --name "security-audit-store" \
     --retention-period 2557 \
     --multi-region-enabled
   ```

3. **EventBridge Integration**
   ```bash
   # Trigger Lambda on specific API calls in real-time
   aws events put-rule \
     --name cloudtrail-delete-bucket \
     --event-pattern '{
       "source": ["aws.s3"],
       "detail-type": ["AWS API Call via CloudTrail"],
       "detail": {"eventName": ["DeleteBucket"]}
     }'
   ```

4. **S3 Lifecycle Policy**
   ```bash
   # Archive old CloudTrail logs to Glacier after 90 days
   aws s3api put-bucket-lifecycle-configuration \
     --bucket "$BUCKET_NAME" \
     --lifecycle-configuration '{
       "Rules": [{
         "Status": "Enabled",
         "Transitions": [{
           "Days": 90,
           "StorageClass": "GLACIER"
         }]
       }]
     }'
   ```

5. **Cross-Account Logging**
   - Create organization trail in AWS Organizations
   - Centralize logs from all accounts to security account
   - Use CloudTrail Lake for cross-account queries

6. **Automated Threat Detection**
   - Integrate with AWS GuardDuty (uses CloudTrail automatically)
   - Use AWS Security Hub for centralized security findings
   - Deploy AWS Config rules for compliance monitoring

---

## Troubleshooting

**No logs appearing in S3:**
- Wait 15-30 minutes for first log delivery
- Verify S3 bucket policy allows CloudTrail access
- Check trail status: `aws cloudtrail get-trail-status`
- Ensure trail is started: `aws cloudtrail start-logging`

**No logs in CloudWatch:**
- Verify IAM role has correct trust policy
- Check IAM role has PutLogEvents permission
- Ensure CloudWatch Logs group exists
- Wait 5-10 minutes for propagation

**Queries return no results:**
- Wait 2-5 minutes after generating API calls
- Check time range (use last 30 minutes)
- Verify log group name is correct
- Ensure CloudTrail is delivering to CloudWatch Logs

**Alarm not triggering:**
- Verify metric filter pattern matches event structure
- Check alarm threshold and evaluation periods
- Confirm SNS subscription is active
- Test metric filter with manual put-metric-data

**Permission errors:**
- Ensure IAM user/role has CloudTrail permissions
- Verify S3 bucket is not encrypted with customer-managed KMS key
- Check IAM role trust policy allows CloudTrail service

---

## Additional Resources

- [AWS CloudTrail Documentation](https://docs.aws.amazon.com/cloudtrail/)
- [CloudTrail Log Event Reference](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference.html)
- [CloudWatch Logs Insights Query Syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html)
- [CloudTrail Security Best Practices](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/best-practices-security.html)
