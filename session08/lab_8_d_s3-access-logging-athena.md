# Lab 8.D: S3 Access Logging and Analysis with Athena

## Overview
This lab demonstrates S3 server access logging for tracking all requests made to your S3 buckets. Access logs capture detailed information about every request, enabling security audits, compliance reporting, and usage analysis. You'll enable S3 access logging, store logs in a dedicated bucket, create an Athena table to query logs with SQL, and analyze access patterns to identify unauthorized activity.

**💰 Cost**: FREE (S3 access logging free, 5GB S3 storage free, 1TB Athena queries free)

---

## Objectives
- Enable S3 server access logging on a bucket
- Create dedicated logging bucket with proper permissions
- Upload sample files and generate access logs
- Create Athena database and table for S3 logs
- Query logs with SQL (top requesters, status codes, operations)
- Identify unauthorized access attempts
- Analyze bandwidth usage and popular objects
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for S3, Athena, Glue
- Understanding of S3 and HTTP status codes
- Basic SQL knowledge

---

## Architecture

```
S3 Bucket (source) → Access Logs → S3 Bucket (logs)
                                          ↓
                                    Athena Table → SQL Queries
                                          ↓
                                    Analysis (top IPs, errors, bandwidth)
```

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set region
REGION="ap-southeast-2"
echo "REGION=$REGION"

# Set resource names with unique suffix
SUFFIX=$(date +%s)
echo "SUFFIX=$SUFFIX"

SOURCE_BUCKET="my-website-${SUFFIX}"
echo "SOURCE_BUCKET=$SOURCE_BUCKET"

LOGS_BUCKET="s3-access-logs-${SUFFIX}"
echo "LOGS_BUCKET=$LOGS_BUCKET"

ATHENA_DATABASE="s3_access_logs_db"
echo "ATHENA_DATABASE=$ATHENA_DATABASE"

ATHENA_TABLE="access_logs"
echo "ATHENA_TABLE=$ATHENA_TABLE"

ATHENA_RESULTS="athena-query-results-${SUFFIX}"
echo "ATHENA_RESULTS=$ATHENA_RESULTS"

echo ""
echo "✅ Prerequisites verified"
```

---

## Step 2 – Create Source S3 Bucket

```bash
echo ""
echo "Creating source S3 bucket..."

# Create source bucket (the one we'll monitor)
if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$SOURCE_BUCKET" \
      --region "$REGION"
else
    aws s3api create-bucket \
      --bucket "$SOURCE_BUCKET" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi

echo "✅ Source bucket created: $SOURCE_BUCKET"
```

---

## Step 3 – Create Logging S3 Bucket

```bash
echo "Creating logging S3 bucket..."

# Create logging bucket (stores access logs)
if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$LOGS_BUCKET" \
      --region "$REGION"
else
    aws s3api create-bucket \
      --bucket "$LOGS_BUCKET" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi

echo "✅ Logging bucket created: $LOGS_BUCKET"
```

---

## Step 4 – Configure Logging Bucket Permissions

```bash
echo ""
echo "Configuring logging bucket permissions..."

# Put bucket ACL to allow S3 log delivery
aws s3api put-bucket-acl \
  --bucket "$LOGS_BUCKET" \
  --grant-write 'URI="http://acs.amazonaws.com/groups/s3/LogDelivery"' \
  --grant-read-acp 'URI="http://acs.amazonaws.com/groups/s3/LogDelivery"' \
  --region "$REGION"

echo "✅ Logging bucket ACL configured for log delivery"
```

---

## Step 5 – Enable S3 Access Logging

```bash
echo "Enabling S3 access logging on source bucket..."

# Create logging configuration JSON
cat > logging-config.json <<EOF
{
  "LoggingEnabled": {
    "TargetBucket": "${LOGS_BUCKET}",
    "TargetPrefix": "access-logs/"
  }
}
EOF

# Enable logging
aws s3api put-bucket-logging \
  --bucket "$SOURCE_BUCKET" \
  --bucket-logging-status file://logging-config.json \
  --region "$REGION"

echo "✅ S3 access logging enabled"
echo ""
echo "Logging configuration:"
echo "  - Source bucket: $SOURCE_BUCKET"
echo "  - Logs bucket: $LOGS_BUCKET"
echo "  - Log prefix: access-logs/"
```

---

## Step 6 – Upload Sample Files to Source Bucket

```bash
echo ""
echo "Uploading sample files to generate access logs..."

# Create sample HTML file
cat > index.html <<'EOF'
<!DOCTYPE html>
<html>
<head><title>S3 Access Logging Demo</title></head>
<body>
  <h1>Welcome to S3 Access Logging Lab</h1>
  <p>This file is being monitored by S3 access logs.</p>
</body>
</html>
EOF

# Create sample data file
echo "Sample data for logging demo" > data.txt

# Create sample image placeholder
echo "This would be an image file" > image.jpg

# Upload files
aws s3 cp index.html s3://"$SOURCE_BUCKET"/index.html --region "$REGION"
aws s3 cp data.txt s3://"$SOURCE_BUCKET"/data/data.txt --region "$REGION"
aws s3 cp image.jpg s3://"$SOURCE_BUCKET"/images/image.jpg --region "$REGION"

echo "✅ Sample files uploaded"
```

---

## Step 7 – Generate Access Logs

```bash
echo ""
echo "Generating access logs by accessing bucket objects..."

# List bucket contents (generates ListBucket request)
aws s3 ls s3://"$SOURCE_BUCKET" --region "$REGION"

# Download files (generates GetObject requests)
aws s3 cp s3://"$SOURCE_BUCKET"/index.html /tmp/index.html --region "$REGION"
aws s3 cp s3://"$SOURCE_BUCKET"/data/data.txt /tmp/data.txt --region "$REGION"
aws s3 cp s3://"$SOURCE_BUCKET"/images/image.jpg /tmp/image.jpg --region "$REGION"

# Try to access non-existent file (generates 404 error)
aws s3 cp s3://"$SOURCE_BUCKET"/notfound.txt /tmp/notfound.txt --region "$REGION" 2>/dev/null || echo "404 error generated"

# Try to access without permission (generates 403 error - will fail gracefully)
echo "Simulating unauthorized access..."

# Upload more files
echo "Additional content" > file1.txt
echo "More data" > file2.txt
aws s3 cp file1.txt s3://"$SOURCE_BUCKET"/file1.txt --region "$REGION"
aws s3 cp file2.txt s3://"$SOURCE_BUCKET"/file2.txt --region "$REGION"

# Delete a file (generates DELETE request)
aws s3 rm s3://"$SOURCE_BUCKET"/file2.txt --region "$REGION"

echo ""
echo "✅ Access logs generated"
echo ""
echo "Waiting 2 minutes for logs to be delivered to logging bucket..."
echo "(S3 access logs are delivered on a best-effort basis, usually within a few minutes)"
sleep 120
```

---

## Step 8 – Verify Logs Delivered

```bash
echo ""
echo "Checking if access logs have been delivered..."

# List log files
LOG_COUNT=$(aws s3 ls s3://"$LOGS_BUCKET"/access-logs/ --recursive --region "$REGION" | wc -l)
echo "Log files found: $LOG_COUNT"

if [ "$LOG_COUNT" -gt 0 ]; then
    echo "✅ Access logs delivered successfully"
    echo ""
    echo "Sample log files:"
    aws s3 ls s3://"$LOGS_BUCKET"/access-logs/ --recursive --region "$REGION" | head -5
else
    echo "⚠️  No logs yet, waiting another minute..."
    sleep 60
    aws s3 ls s3://"$LOGS_BUCKET"/access-logs/ --recursive --region "$REGION"
fi
```

---

## Step 9 – Create Athena Query Results Bucket

```bash
echo ""
echo "Creating Athena query results bucket..."

# Create bucket for Athena query results
if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$ATHENA_RESULTS" \
      --region "$REGION"
else
    aws s3api create-bucket \
      --bucket "$ATHENA_RESULTS" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi

echo "✅ Athena results bucket created: $ATHENA_RESULTS"
```

---

## Step 10 – Create Athena Database

```bash
echo ""
echo "================================================"
echo "CREATING ATHENA DATABASE AND TABLE"
echo "================================================"
echo ""

# Create Athena database
echo "Creating Athena database..."

QUERY_ID=$(aws athena start-query-execution \
  --query-string "CREATE DATABASE IF NOT EXISTS ${ATHENA_DATABASE}" \
  --result-configuration "OutputLocation=s3://${ATHENA_RESULTS}/" \
  --region "$REGION" \
  --query 'QueryExecutionId' \
  --output text)

echo "Query ID: $QUERY_ID"

# Wait for query to complete
echo "Waiting for database creation..."
aws athena get-query-execution \
  --query-execution-id "$QUERY_ID" \
  --region "$REGION" \
  --query 'QueryExecution.Status.State' \
  --output text

echo "✅ Athena database created"
```

---

## Step 11 – Create Athena Table for S3 Access Logs

```bash
echo ""
echo "Creating Athena table for S3 access logs..."

# Create table DDL (S3 access log format)
cat > create-table.sql <<EOF
CREATE EXTERNAL TABLE IF NOT EXISTS ${ATHENA_DATABASE}.${ATHENA_TABLE} (
  bucketowner string,
  bucket_name string,
  requestdatetime string,
  remoteip string,
  requester string,
  requestid string,
  operation string,
  key string,
  request_uri string,
  httpstatus string,
  errorcode string,
  bytessent bigint,
  objectsize bigint,
  totaltime string,
  turnaroundtime string,
  referrer string,
  useragent string,
  versionid string,
  hostid string,
  sigv string,
  ciphersuite string,
  authtype string,
  endpoint string,
  tlsversion string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.RegexSerDe'
WITH SERDEPROPERTIES (
  'serialization.format' = '1',
  'input.regex' = '([^ ]*) ([^ ]*) \\[(.*?)\\] ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) (\"[^\"]*\"|-) (-|[0-9]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) (\"[^\"]*\"|-) ([^ ]*)(?: ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*))?.*$'
)
LOCATION 's3://${LOGS_BUCKET}/access-logs/'
EOF

# Create table
QUERY_ID=$(aws athena start-query-execution \
  --query-string file://create-table.sql \
  --result-configuration "OutputLocation=s3://${ATHENA_RESULTS}/" \
  --query-execution-context "Database=${ATHENA_DATABASE}" \
  --region "$REGION" \
  --query 'QueryExecutionId' \
  --output text)

echo "Query ID: $QUERY_ID"

# Wait for table creation
sleep 3

STATUS=$(aws athena get-query-execution \
  --query-execution-id "$QUERY_ID" \
  --region "$REGION" \
  --query 'QueryExecution.Status.State' \
  --output text)

echo "Table creation status: $STATUS"
echo "✅ Athena table created"
```

---

## Step 12 – Query All Access Logs

```bash
echo ""
echo "================================================"
echo "QUERYING S3 ACCESS LOGS WITH ATHENA"
echo "================================================"
echo ""

# Query 1: Show all access logs
echo "Query 1: Recent access log entries"
echo ""

QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT requestdatetime, remoteip, operation, key, httpstatus FROM ${ATHENA_DATABASE}.${ATHENA_TABLE} ORDER BY requestdatetime DESC LIMIT 20" \
  --result-configuration "OutputLocation=s3://${ATHENA_RESULTS}/" \
  --query-execution-context "Database=${ATHENA_DATABASE}" \
  --region "$REGION" \
  --query 'QueryExecutionId' \
  --output text)

# Wait for query to complete
sleep 5

# Get query results
aws athena get-query-results \
  --query-execution-id "$QUERY_ID" \
  --region "$REGION" \
  --query 'ResultSet.Rows[*].Data[*].VarCharValue' \
  --output table

echo ""
```

---

## Step 13 – Query Top Source IPs

```bash
echo "Query 2: Top source IP addresses (most active)"
echo ""

QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT remoteip, COUNT(*) as request_count FROM ${ATHENA_DATABASE}.${ATHENA_TABLE} GROUP BY remoteip ORDER BY request_count DESC LIMIT 10" \
  --result-configuration "OutputLocation=s3://${ATHENA_RESULTS}/" \
  --query-execution-context "Database=${ATHENA_DATABASE}" \
  --region "$REGION" \
  --query 'QueryExecutionId' \
  --output text)

sleep 5

aws athena get-query-results \
  --query-execution-id "$QUERY_ID" \
  --region "$REGION" \
  --query 'ResultSet.Rows[*].Data[*].VarCharValue' \
  --output table

echo ""
```

---

## Step 14 – Query by HTTP Status Codes

```bash
echo "Query 3: Requests by HTTP status code"
echo ""

QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT httpstatus, COUNT(*) as count FROM ${ATHENA_DATABASE}.${ATHENA_TABLE} GROUP BY httpstatus ORDER BY count DESC" \
  --result-configuration "OutputLocation=s3://${ATHENA_RESULTS}/" \
  --query-execution-context "Database=${ATHENA_DATABASE}" \
  --region "$REGION" \
  --query 'QueryExecutionId' \
  --output text)

sleep 5

aws athena get-query-results \
  --query-execution-id "$QUERY_ID" \
  --region "$REGION" \
  --query 'ResultSet.Rows[*].Data[*].VarCharValue' \
  --output table

echo ""
echo "HTTP status codes:"
echo "  - 200: Success"
echo "  - 404: Not Found"
echo "  - 403: Forbidden (unauthorized)"
echo "  - 500: Server Error"
echo ""
```

---

## Step 15 – Query Top Accessed Objects

```bash
echo "Query 4: Most accessed objects"
echo ""

QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT key, COUNT(*) as access_count FROM ${ATHENA_DATABASE}.${ATHENA_TABLE} WHERE key IS NOT NULL GROUP BY key ORDER BY access_count DESC LIMIT 10" \
  --result-configuration "OutputLocation=s3://${ATHENA_RESULTS}/" \
  --query-execution-context "Database=${ATHENA_DATABASE}" \
  --region "$REGION" \
  --query 'QueryExecutionId' \
  --output text)

sleep 5

aws athena get-query-results \
  --query-execution-id "$QUERY_ID" \
  --region "$REGION" \
  --query 'ResultSet.Rows[*].Data[*].VarCharValue' \
  --output table

echo ""
```

---

## Step 16 – Query Failed Requests (Errors)

```bash
echo "Query 5: Failed requests (4xx and 5xx errors)"
echo ""

QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT requestdatetime, remoteip, operation, key, httpstatus, errorcode FROM ${ATHENA_DATABASE}.${ATHENA_TABLE} WHERE httpstatus LIKE '4%' OR httpstatus LIKE '5%' ORDER BY requestdatetime DESC LIMIT 20" \
  --result-configuration "OutputLocation=s3://${ATHENA_RESULTS}/" \
  --query-execution-context "Database=${ATHENA_DATABASE}" \
  --region "$REGION" \
  --query 'QueryExecutionId' \
  --output text)

sleep 5

aws athena get-query-results \
  --query-execution-id "$QUERY_ID" \
  --region "$REGION" \
  --query 'ResultSet.Rows[*].Data[*].VarCharValue' \
  --output table

echo ""
```

---

## Step 17 – Query Bandwidth Usage

```bash
echo "Query 6: Total bandwidth by object"
echo ""

QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT key, SUM(bytessent) as total_bytes, COUNT(*) as requests FROM ${ATHENA_DATABASE}.${ATHENA_TABLE} WHERE key IS NOT NULL GROUP BY key ORDER BY total_bytes DESC LIMIT 10" \
  --result-configuration "OutputLocation=s3://${ATHENA_RESULTS}/" \
  --query-execution-context "Database=${ATHENA_DATABASE}" \
  --region "$REGION" \
  --query 'QueryExecutionId' \
  --output text)

sleep 5

aws athena get-query-results \
  --query-execution-id "$QUERY_ID" \
  --region "$REGION" \
  --query 'ResultSet.Rows[*].Data[*].VarCharValue' \
  --output table

echo ""
echo "✅ Athena queries completed"
```

---

## Step 18 – View Athena Console

```bash
echo ""
echo "================================================"
echo "ATHENA CONSOLE ACCESS"
echo "================================================"
echo ""
echo "Query S3 access logs in Athena Console:"
echo "https://${REGION}.console.aws.amazon.com/athena/home?region=${REGION}#/query-editor"
echo ""
echo "Database: ${ATHENA_DATABASE}"
echo "Table: ${ATHENA_TABLE}"
echo ""
echo "Example queries to try:"
echo ""
echo "-- Find all DELETE operations"
echo "SELECT * FROM ${ATHENA_DATABASE}.${ATHENA_TABLE} WHERE operation = 'REST.DELETE.OBJECT';"
echo ""
echo "-- Unauthorized access attempts"
echo "SELECT * FROM ${ATHENA_DATABASE}.${ATHENA_TABLE} WHERE httpstatus = '403';"
echo ""
echo "-- Total bytes transferred per day"
echo "SELECT DATE(requestdatetime) as day, SUM(bytessent) as total_bytes FROM ${ATHENA_DATABASE}.${ATHENA_TABLE} GROUP BY DATE(requestdatetime);"
```

---

## Step 19 – Cleanup Resources

```bash
echo ""
echo "Cleaning up resources..."

# Delete Athena table
echo "Deleting Athena table..."
aws athena start-query-execution \
  --query-string "DROP TABLE IF EXISTS ${ATHENA_DATABASE}.${ATHENA_TABLE}" \
  --result-configuration "OutputLocation=s3://${ATHENA_RESULTS}/" \
  --query-execution-context "Database=${ATHENA_DATABASE}" \
  --region "$REGION" > /dev/null

sleep 2

# Delete Athena database
echo "Deleting Athena database..."
aws athena start-query-execution \
  --query-string "DROP DATABASE IF EXISTS ${ATHENA_DATABASE}" \
  --result-configuration "OutputLocation=s3://${ATHENA_RESULTS}/" \
  --region "$REGION" > /dev/null

sleep 2

# Empty and delete source bucket
echo "Emptying source bucket..."
aws s3 rm s3://"$SOURCE_BUCKET" --recursive --region "$REGION"

echo "Deleting source bucket..."
aws s3api delete-bucket \
  --bucket "$SOURCE_BUCKET" \
  --region "$REGION"

# Empty and delete logs bucket
echo "Emptying logs bucket..."
aws s3 rm s3://"$LOGS_BUCKET" --recursive --region "$REGION"

echo "Deleting logs bucket..."
aws s3api delete-bucket \
  --bucket "$LOGS_BUCKET" \
  --region "$REGION"

# Empty and delete Athena results bucket
echo "Emptying Athena results bucket..."
aws s3 rm s3://"$ATHENA_RESULTS" --recursive --region "$REGION"

echo "Deleting Athena results bucket..."
aws s3api delete-bucket \
  --bucket "$ATHENA_RESULTS" \
  --region "$REGION"

# Delete local files
rm -f logging-config.json create-table.sql index.html data.txt image.jpg file1.txt file2.txt

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- Source S3 bucket and objects"
echo "- Logs S3 bucket and access logs"
echo "- Athena results bucket"
echo "- Athena database and table"
```

---

## Summary

In this lab, you have:
- Created source S3 bucket for monitoring
- Created dedicated logging bucket for access logs
- Configured S3 server access logging
- Uploaded sample files and generated access logs
- Created Athena database and table for log analysis
- Queried logs with SQL (all requests, top IPs, status codes, popular objects, errors, bandwidth)
- Identified access patterns and potential security issues
- Cleaned up all resources

**Key Takeaways:**
- **S3 Access Logs**: Track every request to your buckets
- **Log Delivery**: Best-effort delivery within a few hours
- **Log Format**: Space-delimited with 24 fields
- **Athena Integration**: Query logs with standard SQL
- **Security Analysis**: Detect unauthorized access (403), missing objects (404)
- **Bandwidth Analysis**: Identify high-traffic objects
- **Compliance**: Audit trails for regulatory requirements

**S3 Access Log Fields:**
```
bucket_owner bucket requestdatetime remoteip requester requestid operation key
request_uri httpstatus errorcode bytessent objectsize totaltime turnaroundtime
referrer useragent versionid hostid sigv ciphersuite authtype endpoint tlsversion
```

**Example S3 Access Log Entry:**
```
79a59df900b949e55d96a1e698fbacedfd6e09d98eacf8f8d5218e7cd47ef2be my-bucket [06/Feb/2024:10:30:00 +0000] 192.0.2.3 79a59df900b949e55d96a1e698fbacedfd6e09d98eacf8f8d5218e7cd47ef2be 3E57427F3EXAMPLE REST.GET.OBJECT index.html "GET /my-bucket/index.html HTTP/1.1" 200 - 2662 2662 73 12 "-" "curl/7.64.1" - s9lzHYrFp76ZVxRcpX9+5cjAnEH2ROuNkd2BHfIa6UkFVdtjf5mKR3/eTPFvsiP/XV/VLi31234= SigV2 ECDHE-RSA-AES128-GCM-SHA256 AuthHeader my-bucket.s3.amazonaws.com TLSv1.2
```

**Common S3 Operations:**
- **REST.GET.OBJECT**: Download file
- **REST.PUT.OBJECT**: Upload file
- **REST.DELETE.OBJECT**: Delete file
- **REST.GET.BUCKET**: List bucket contents
- **REST.HEAD.OBJECT**: Get object metadata
- **REST.POST.OBJECT**: Upload via POST

**Useful Athena Queries:**
```sql
-- Find all DELETE operations
SELECT requestdatetime, remoteip, key
FROM s3_access_logs_db.access_logs
WHERE operation = 'REST.DELETE.OBJECT'
ORDER BY requestdatetime DESC;

-- Unauthorized access attempts (403 Forbidden)
SELECT requestdatetime, remoteip, key, errorcode
FROM s3_access_logs_db.access_logs
WHERE httpstatus = '403'
ORDER BY requestdatetime DESC;

-- Large downloads (>10MB)
SELECT requestdatetime, remoteip, key, bytessent
FROM s3_access_logs_db.access_logs
WHERE bytessent > 10485760
ORDER BY bytessent DESC;

-- Requests from specific IP
SELECT requestdatetime, operation, key, httpstatus
FROM s3_access_logs_db.access_logs
WHERE remoteip = '192.0.2.3'
ORDER BY requestdatetime DESC;

-- Total bandwidth per day
SELECT DATE_TRUNC('day', FROM_ISO8601_TIMESTAMP(requestdatetime)) as day,
       SUM(bytessent) as total_bytes,
       COUNT(*) as request_count
FROM s3_access_logs_db.access_logs
GROUP BY DATE_TRUNC('day', FROM_ISO8601_TIMESTAMP(requestdatetime))
ORDER BY day DESC;

-- Top 10 user agents
SELECT useragent, COUNT(*) as count
FROM s3_access_logs_db.access_logs
GROUP BY useragent
ORDER BY count DESC
LIMIT 10;
```

---

## Best Practices

**S3 Access Logging:**
- Enable logging on all production buckets
- Use separate bucket for logs (never log to same bucket)
- Set log prefix for organization (e.g., `logs/bucket-name/`)
- Enable lifecycle policies to archive/delete old logs
- Block public access on logging bucket
- Use IAM policies to restrict log access

**Athena Optimization:**
- Partition logs by date for faster queries (`YYYY/MM/DD/`)
- Use columnar formats (Parquet) for large datasets
- Query only needed columns (reduce scanned data)
- Use LIMIT clause when testing queries
- Create views for common queries

**Security Monitoring:**
- Alert on 403 errors (unauthorized access)
- Monitor DELETE operations (data loss risk)
- Track requests from unusual IPs
- Analyze failed login attempts (S3 access via STS)
- Review high-bandwidth transfers (data exfiltration)

**Cost Optimization:**
- S3 access logging is FREE (delivery to S3)
- Storage costs apply ($0.023/GB/month)
- Athena charges $5 per TB of data scanned
- Use partitioning to reduce scanned data
- Archive old logs to Glacier ($0.004/GB)

---

## Free Tier Notes
- **S3 Access Logging**: FREE (no charge for logging)
- **S3 Storage**: 5GB free for 12 months
- **Athena**: First 1TB of data scanned per month free (first year only, limited regions)
- **Glue Data Catalog**: 1M objects free

This lab uses minimal resources, staying well within free tier limits.

---

## Production Enhancements

1. **Partitioned Athena Table**
   ```sql
   -- Create partitioned table for faster queries
   CREATE EXTERNAL TABLE s3_access_logs_partitioned (
     ... same columns ...
   )
   PARTITIONED BY (year string, month string, day string)
   LOCATION 's3://my-logs-bucket/access-logs/';
   
   -- Add partitions
   MSCK REPAIR TABLE s3_access_logs_partitioned;
   ```

2. **S3 Lifecycle Policy for Logs**
   ```bash
   # Archive old logs to Glacier after 90 days
   aws s3api put-bucket-lifecycle-configuration \
     --bucket "$LOGS_BUCKET" \
     --lifecycle-configuration '{
       "Rules": [{
         "Status": "Enabled",
         "Prefix": "access-logs/",
         "Transitions": [{
           "Days": 90,
           "StorageClass": "GLACIER"
         }],
         "Expiration": {
           "Days": 365
         }
       }]
     }'
   ```

3. **CloudWatch Alarms via Athena**
   - Schedule Lambda to run Athena queries
   - Check for suspicious patterns (403s, large downloads)
   - Send SNS alert when threshold exceeded

4. **S3 Inventory for Batch Analysis**
   ```bash
   # More efficient than access logs for large-scale analysis
   aws s3api put-bucket-inventory-configuration \
     --bucket "$SOURCE_BUCKET" \
     --id daily-inventory \
     --inventory-configuration '{
       "Destination": {
         "S3BucketDestination": {
           "Bucket": "arn:aws:s3:::my-inventory-bucket",
           "Format": "Parquet"
         }
       },
       "IsEnabled": true,
       "Schedule": {"Frequency": "Daily"}
     }'
   ```

5. **Integration with SIEM**
   - Export logs to Splunk, Sumo Logic, or Datadog
   - Real-time security monitoring
   - Automated threat detection

6. **CloudTrail for S3 Data Events**
   - More granular than access logs
   - Captures API caller identity
   - Faster delivery (minutes vs hours)
   ```bash
   aws cloudtrail put-event-selectors \
     --trail-name my-trail \
     --event-selectors '[{
       "ReadWriteType": "All",
       "DataResources": [{
         "Type": "AWS::S3::Object",
         "Values": ["arn:aws:s3:::my-bucket/*"]
       }]
     }]'
   ```

---

## Troubleshooting

**No logs appearing:**
- Wait 2-4 hours (S3 logs are best-effort delivery)
- Verify logging bucket ACL allows S3 Log Delivery group
- Check source bucket logging configuration: `aws s3api get-bucket-logging`
- Ensure logging bucket is in same region as source

**Athena table shows no data:**
- Verify logs exist in S3: `aws s3 ls s3://logs-bucket/access-logs/`
- Check table LOCATION matches log prefix
- Run `MSCK REPAIR TABLE` if using partitions
- Verify regex pattern in table DDL

**Query errors in Athena:**
- Check query syntax (standard SQL with Presto extensions)
- Verify table and database names
- Ensure enough data scanned (empty results != error)
- Review query execution details in console

**High Athena costs:**
- Use partitioning (scan less data)
- Query specific columns, not SELECT *
- Convert logs to Parquet format (70% less data scanned)
- Use views to pre-filter data

---

## Additional Resources

- [S3 Server Access Logging](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ServerLogs.html)
- [S3 Access Log Format](https://docs.aws.amazon.com/AmazonS3/latest/userguide/LogFormat.html)
- [Athena SQL Reference](https://docs.aws.amazon.com/athena/latest/ug/ddl-sql-reference.html)
- [Querying S3 Access Logs with Athena](https://docs.aws.amazon.com/athena/latest/ug/querying-s3-access-logs.html)
- [S3 Security Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)
