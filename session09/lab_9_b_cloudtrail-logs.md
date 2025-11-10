# Lab 9.B: Track and audit API calls using CloudTrail and Log Insights

## Overview
Enable AWS CloudTrail to capture account activity (management & data events), deliver logs to an encrypted S3 bucket and CloudWatch Logs, and use CloudWatch Logs Insights / CloudTrail Lake to analyze and alert on sensitive API calls. Validate auditability, log file integrity, and create queries & alarms for suspicious activity.

## Objectives
- Create a CloudTrail (multi-region) and enable log file validation
- Deliver CloudTrail events to an encrypted S3 bucket and to CloudWatch Logs
- Capture management events and data events (S3 object-level, Lambda)
- Use CloudWatch Logs Insights and CloudTrail Lake for queries and investigations
- Create metric filters / alarms or EventBridge rules to notify on critical events
- Verify log integrity and perform cleanup

## Prerequisites
- AWS CLI v2 configured
- jq (optional) for JSON parsing
- IAM permissions: cloudtrail:*, s3:*, logs:*, events:*, sns:*, kms:*, iam:*
- Region: REGION variable set

---

## Variables (replace before running)
- REGION=us-east-1
- ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
- TRAIL_NAME=lab-cloudtrail
- BUCKET_NAME=lab-cloudtrail-logs-${ACCOUNT_ID}-${REGION}
- LOG_GROUP_NAME=/aws/cloudtrail/lab-logs
- SNS_TOPIC_NAME=lab-cloudtrail-alerts
- ROLE_NAME=lab-cloudtrail-logs-role

---

## Steps (CLI)

### 1. Create an encrypted S3 bucket for CloudTrail logs
```bash
aws s3api create-bucket --bucket $BUCKET_NAME --region $REGION \
  $( [ "$REGION" = "us-east-1" ] || echo "--create-bucket-configuration LocationConstraint=$REGION" )

aws s3api put-public-access-block --bucket $BUCKET_NAME --public-access-block-configuration '{
  "BlockPublicAcls": true,
  "IgnorePublicAcls": true,
  "BlockPublicPolicy": true,
  "RestrictPublicBuckets": true
}' --region $REGION

# Optional: enable default encryption (SSE-S3)
aws s3api put-bucket-encryption --bucket $BUCKET_NAME --server-side-encryption-configuration '{
  "Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]
}' --region $REGION
```

### 2. Create CloudWatch Logs group and IAM role for CloudTrail -> Logs
```bash
aws logs create-log-group --log-group-name $LOG_GROUP_NAME --region $REGION

# Create role trust policy for CloudTrail to write to CloudWatch Logs
cat > trust-logs.json <<'EOF'
{
  "Version":"2012-10-17",
  "Statement":[{"Effect":"Allow","Principal":{"Service":"cloudtrail.amazonaws.com"},"Action":"sts:AssumeRole"}]
}
EOF

aws iam create-role --role-name $ROLE_NAME --assume-role-policy-document file://trust-logs.json --region $REGION || true

# Attach inline policy allowing PutLogEvents / CreateLogStream
cat > cw-policy.json <<'EOF'
{
  "Version":"2012-10-17",
  "Statement":[
    {"Effect":"Allow","Action":["logs:CreateLogStream","logs:PutLogEvents","logs:DescribeLogStreams"],"Resource":"arn:aws:logs:*:*:log-group:$LOG_GROUP_NAME:*"}
  ]
}
EOF

aws iam put-role-policy --role-name $ROLE_NAME --policy-name CloudTrailPutLogs --policy-document file://cw-policy.json --region $REGION

ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --region $REGION --query Role.Arn --output text)
```

### 3. Create the CloudTrail (multi-region) and enable log delivery + validation + CloudWatch Logs
```bash
aws cloudtrail create-trail \
  --name $TRAIL_NAME \
  --s3-bucket-name $BUCKET_NAME \
  --is-multi-region-trail true \
  --enable-log-file-validation true \
  --cloud-watch-logs-log-group-arn arn:aws:logs:$REGION:$ACCOUNT_ID:log-group:$LOG_GROUP_NAME \
  --cloud-watch-logs-role-arn $ROLE_ARN \
  --region $REGION

aws cloudtrail start-logging --name $TRAIL_NAME --region $REGION
```

### 4. Enable data events (S3 object-level, Lambda) for specific resources
Data events are not enabled by default; add advanced event selectors:
```bash
aws cloudtrail put-event-selectors --trail-name $TRAIL_NAME --region $REGION \
  --event-selectors '[
    {
      "ReadWriteType":"All",
      "IncludeManagementEvents":true,
      "DataResources":[
        {"Type":"AWS::S3::Object","Values":["arn:aws:s3:::'"$BUCKET_NAME"'/*"]},
        {"Type":"AWS::Lambda::Function","Values":["arn:aws:lambda:'"$REGION"':'"$ACCOUNT_ID"':function:*"]}
      ]
    }
  ]'
```

### 5. Create SNS topic for alerts and subscribe an email
```bash
SNS_ARN=$(aws sns create-topic --name $SNS_TOPIC_NAME --region $REGION --query TopicArn --output text)
aws sns subscribe --topic-arn $SNS_ARN --protocol email --notification-endpoint you@example.com --region $REGION
```

### 6. Create EventBridge rule to detect critical API calls and notify via SNS
Example: detect ConsoleLogin failures and root usage (management events)
```bash
aws events put-rule --name lab-cloudtrail-alarms --event-pattern '{
  "source":["aws.signin","aws.cloudtrail"],
  "detail-type":["AWS Console Sign In via CloudTrail","AWS API Call via CloudTrail"],
  "detail": {
    "eventName": ["ConsoleLogin","ConsoleLoginFailed","RootLogin","DeleteTrail"],
    "errorCode": [{"exists": true}]
  }
}' --region $REGION

aws events put-targets --rule lab-cloudtrail-alarms --targets "Id"="1","Arn"="$SNS_ARN" --region $REGION
```

(Adjust event-pattern to your monitoring needs; use CloudTrail eventName values like AssumeRole, CreateUser, DeleteBucket.)

### 7. Query CloudTrail logs using CloudWatch Logs Insights
Sample queries to investigate events (select correct log group name):

- Failed ConsoleLogins:
```sql
fields @timestamp, eventName, userIdentity.principalId, sourceIPAddress, errorMessage
| filter eventName = "ConsoleLogin" and responseElements.ConsoleLogin = "Failure"
| sort @timestamp desc
| limit 50
```

- API calls by a principal (examples via aws logs insights CLI):
```bash
aws logs start-query --log-group-name $LOG_GROUP_NAME --start-time $(($(date +%s)-3600)) --end-time $(date +%s) --query-string '
fields @timestamp, eventName, userIdentity.userName, sourceIPAddress, awsRegion
| filter userIdentity.userName = "alice"
| sort @timestamp desc
| limit 50
' --region $REGION
```

- Find AssumeRole events:
```sql
fields @timestamp, eventName, userIdentity.sessionContext.sessionIssuer.userName, requestParameters, sourceIPAddress
| filter eventName = "AssumeRole"
| sort @timestamp desc
| limit 100
```

### 8. Use CloudTrail Lake (optional) for SQL-style queries across events
Create a saved query in CloudTrail Lake or run ad-hoc queries to search across historical events (use console or aws cloudtrail-data CLI). Example:
```bash
aws cloudtrail-data start-query --query "SELECT eventTime, eventName, userIdentity, sourceIPAddress FROM $AWS::CloudTrail.Event WHERE eventName = 'ConsoleLogin' ORDER BY eventTime DESC LIMIT 50"
```
(Use CloudTrail Lake documentation for proper syntax and permissions.)

### 9. Create metric filter & alarm for sensitive API usage
Create a metric filter on CloudWatch Logs to count DeleteBucket or DeleteTrail events and alarm on >0 occurrences:
```bash
aws logs put-metric-filter --log-group-name $LOG_GROUP_NAME --filter-name DeleteTrailFilter \
  --filter-pattern '{ $.eventName = "DeleteTrail" }' \
  --metric-transformations metricName=DeleteTrailCount,metricNamespace=Lab/CloudTrail,metricValue=1 --region $REGION

aws cloudwatch put-metric-alarm --alarm-name Lab-DeleteTrail-Alarm --metric-name DeleteTrailCount --namespace Lab/CloudTrail \
  --statistic Sum --period 300 --evaluation-periods 1 --threshold 0.5 --comparison-operator GreaterThanThreshold \
  --alarm-actions $SNS_ARN --region $REGION
```

### 10. Verify log file integrity and validation
CloudTrail log file validation creates digest files and signature verification; verify log-file-validation status:
```bash
aws cloudtrail get-trail-status --name $TRAIL_NAME --region $REGION
```

---

## Validation checklist
- [ ] Multi-region CloudTrail created and logging
- [ ] Logs delivered to encrypted S3 bucket and CloudWatch Logs
- [ ] Data events enabled for S3/Lambda as required
- [ ] EventBridge rule / SNS notifications configured and tested
- [ ] CloudWatch Logs Insights queries return expected audit events
- [ ] Metric filters and alarms trigger on sensitive API activity
- [ ] Log file validation enabled and status OK

## Cleanup
```bash
aws cloudtrail stop-logging --name $TRAIL_NAME --region $REGION
aws cloudtrail delete-trail --name $TRAIL_NAME --region $REGION

aws logs delete-log-group --log-group-name $LOG_GROUP_NAME --region $REGION || true
aws sns delete-topic --topic-arn $SNS_ARN --region $REGION || true

# Remove bucket contents then delete bucket
aws s3 rm s3://$BUCKET_NAME --recursive --region $REGION || true
aws s3api delete-bucket --bucket $BUCKET_NAME --region $REGION || true

aws iam delete-role-policy --role-name $ROLE_NAME --policy-name CloudTrailPutLogs --region $REGION || true
aws iam delete-role --role-name $ROLE_NAME --region $REGION || true
```

## Notes & best practices
- Enable multi-region trails to ensure all API activity is captured.
- Turn on log file validation to detect tampering.
- Enable data events selectively (S3, Lambda) due to cost.
- Use KMS to encrypt S3 logs for added protection.
- Integrate alerts with incident response tools (PagerDuty, Slack).
- Retain logs per compliance requirements and restrict S3 access via bucket policies.

## Summary
This lab configures CloudTrail for comprehensive API auditing, routes logs to S3 and CloudWatch Logs, demonstrates Log Insights and CloudTrail Lake queries, and builds alerting for sensitive API activity. Use these patterns to maintain auditability and detect suspicious account activity.
