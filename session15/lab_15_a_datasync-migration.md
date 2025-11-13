# Lab 15.A: AWS DataSync – Transfer Large Datasets to S3 / EFS

## Overview
This lab teaches you how to migrate large datasets using **AWS DataSync**, a fully managed service for accelerated data transfer between on-premises storage and AWS cloud storage (S3, EFS, FSx). You'll simulate an on-premises data source using a local directory, create an S3 destination bucket, set up DataSync locations and tasks, execute the transfer, validate data integrity, and monitor the process via CloudWatch metrics.

AWS DataSync automates and accelerates moving data at scale while providing built-in data validation, encryption in transit, and bandwidth throttling capabilities.

---

## Objectives
- Set up environment variables and test datasets
- Create destination S3 bucket with proper configuration
- Configure IAM roles for DataSync S3 access
- Create DataSync source (NFS simulation) and destination locations
- Configure and execute DataSync transfer tasks
- Monitor task execution progress and status
- Validate data integrity after transfer
- Review CloudWatch metrics and logs
- Perform comprehensive resource cleanup

---

## Prerequisites
- AWS CLI configured with appropriate credentials
- IAM permissions for DataSync, S3, EFS, IAM, and CloudWatch
- Region: **ap-southeast-2** (Sydney)
- Local machine with test dataset capability
- `jq` installed for JSON parsing (optional but recommended)
- Basic understanding of data migration concepts

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AWS DataSync Migration                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  On-Premises / Source Location (Simulated)                     │
│  ┌─────────────────────────────┐                               │
│  │   /tmp/datasync-demo/       │                               │
│  │   - file_1.dat              │                               │
│  │   - file_2.dat              │                               │
│  │   - file_N.dat              │                               │
│  └─────────────────────────────┘                               │
│              │                                                  │
│              │ DataSync Agent (Simulated)                       │
│              ▼                                                  │
│  ┌─────────────────────────────────────────┐                   │
│  │       DataSync Task Execution           │                   │
│  │  - Bandwidth Management                 │                   │
│  │  - Data Validation                      │                   │
│  │  - Encryption in Transit                │                   │
│  │  - Progress Tracking                    │                   │
│  └─────────────────────────────────────────┘                   │
│              │                                                  │
│              ▼                                                  │
│  AWS Cloud Destination                                          │
│  ┌─────────────────────────────┐                               │
│  │  S3 Bucket (Destination)    │                               │
│  │  datasync-destination-*     │                               │
│  │  - file_1.dat (transferred) │                               │
│  │  - file_2.dat (transferred) │                               │
│  │  - file_N.dat (transferred) │                               │
│  └─────────────────────────────┘                               │
│              │                                                  │
│              ▼                                                  │
│  ┌─────────────────────────────┐                               │
│  │   CloudWatch Metrics        │                               │
│  │  - BytesTransferred         │                               │
│  │  - FilesTransferred         │                               │
│  │  - Throughput               │                               │
│  │  - TaskStatus               │                               │
│  └─────────────────────────────┘                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Key Components:
- Source Location: Simulated NFS directory with test files
- DataSync Task: Orchestrates the transfer with validation
- Destination Location: S3 bucket with versioning
- CloudWatch: Monitors metrics and task execution
- IAM Role: Grants DataSync access to S3 resources
```

---

## Cost Estimate
- **DataSync**: ~$0.0125 per GB transferred
- **S3 Storage**: ~$0.023 per GB per month
- **Data Transfer**: Varies by region
- **Estimated Lab Cost**: < $0.10 (small dataset)

---

# Step 1 – Set Environment Variables

```bash
# Set primary region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "✅ Region set to: $REGION"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "✅ AWS Account ID: $ACCOUNT_ID"

# Define dataset directory and S3 bucket name
DATASET_DIR="/tmp/datasync-demo"
BUCKET_NAME="datasync-destination-${ACCOUNT_ID}"
ROLE_NAME="AWSDataSyncS3Role"

# Echo all variables for verification
echo ""
echo "=== Environment Configuration ==="
echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
echo "Dataset Directory: $DATASET_DIR"
echo "S3 Bucket Name: $BUCKET_NAME"
echo "IAM Role Name: $ROLE_NAME"
echo "================================="
echo ""
```

**Expected Output:**
```
✅ Region set to: ap-southeast-2
✅ AWS Account ID: 123456789012
=== Environment Configuration ===
Region: ap-southeast-2
Account ID: 123456789012
Dataset Directory: /tmp/datasync-demo
S3 Bucket Name: datasync-destination-123456789012
IAM Role Name: AWSDataSyncS3Role
=================================
```

---

# Step 2 – Create Test Dataset with Sample Files

```bash
# Create dataset directory
echo "Creating dataset directory..."
mkdir -p "$DATASET_DIR"
cd "$DATASET_DIR"
echo "✅ Directory created: $DATASET_DIR"

# Generate 20 test files (each ~500 KB)
echo ""
echo "Generating test files..."
for i in {1..20}; do
  # Generate random binary data
  base64 /dev/urandom | head -c 500000 > "file_${i}.dat"
  echo "  ✓ Created file_${i}.dat"
done

echo ""
echo "✅ Test dataset created successfully"

# Display file listing with sizes
echo ""
echo "=== Dataset Contents ==="
ls -lh "$DATASET_DIR"
echo ""

# Calculate total size
TOTAL_SIZE=$(du -sh "$DATASET_DIR" | awk '{print $1}')
FILE_COUNT=$(ls -1 "$DATASET_DIR" | wc -l)
echo "Total Size: $TOTAL_SIZE"
echo "File Count: $FILE_COUNT"
echo "========================"
echo ""
```

**Expected Output:**
```
Creating dataset directory...
✅ Directory created: /tmp/datasync-demo

Generating test files...
  ✓ Created file_1.dat
  ✓ Created file_2.dat
  ...
  ✓ Created file_20.dat

✅ Test dataset created successfully

=== Dataset Contents ===
total 9.8M
-rw-r--r-- 1 user user 488K Nov 13 10:00 file_1.dat
-rw-r--r-- 1 user user 488K Nov 13 10:00 file_2.dat
...

Total Size: 9.8M
File Count: 20
========================
```

**Note:** You can scale this up to GBs by increasing the file count or size: `head -c 50000000` for 50 MB files.

---

# Step 3 – Create IAM Role for DataSync S3 Access

```bash
# Create IAM trust policy for DataSync service
echo "Creating IAM role for DataSync..."

# Create the role with trust policy
aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {
        "Service": "datasync.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }]
  }' \
  --description "Role for DataSync to access S3 buckets" \
  --output json

echo "✅ IAM role created: $ROLE_NAME"

# Wait for role to propagate
echo "Waiting for role to propagate..."
sleep 10

# Attach S3 full access policy to the role
aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "arn:aws:iam::aws:policy/AmazonS3FullAccess"

echo "✅ S3 full access policy attached"

# Construct role ARN
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
echo ""
echo "=== IAM Role Information ==="
echo "Role Name: $ROLE_NAME"
echo "Role ARN: $ROLE_ARN"
echo "============================"
echo ""

# Verify role exists
aws iam get-role \
  --role-name "$ROLE_NAME" \
  --query 'Role.[RoleName,Arn,CreateDate]' \
  --output table
```

**Expected Output:**
```
Creating IAM role for DataSync...
✅ IAM role created: AWSDataSyncS3Role
Waiting for role to propagate...
✅ S3 full access policy attached

=== IAM Role Information ===
Role Name: AWSDataSyncS3Role
Role ARN: arn:aws:iam::123456789012:role/AWSDataSyncS3Role
============================

---------------------------------------------------------
|                       GetRole                          |
+------------------+---------------------+---------------+
|  AWSDataSyncS3Role | arn:aws:iam::123456789012:role/AWSDataSyncS3Role | 2025-11-13 |
+------------------+---------------------+---------------+
```

---

# Step 4 – Create Destination S3 Bucket

```bash
# Create S3 bucket in specified region
echo "Creating S3 destination bucket..."

aws s3api create-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$REGION" \
  --create-bucket-configuration "LocationConstraint=$REGION" \
  --output json

echo "✅ S3 bucket created: $BUCKET_NAME"

# Enable versioning on the bucket (best practice)
aws s3api put-bucket-versioning \
  --bucket "$BUCKET_NAME" \
  --versioning-configuration Status=Enabled

echo "✅ Versioning enabled on bucket"

# Enable encryption at rest (best practice)
aws s3api put-bucket-encryption \
  --bucket "$BUCKET_NAME" \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

echo "✅ Default encryption enabled (AES256)"

# Add bucket tags for organization
aws s3api put-bucket-tagging \
  --bucket "$BUCKET_NAME" \
  --tagging 'TagSet=[
    {Key=Purpose,Value=DataSync-Demo},
    {Key=Environment,Value=Lab},
    {Key=Lab,Value=15A}
  ]'

echo "✅ Bucket tags applied"

# Verify bucket configuration
echo ""
echo "=== Bucket Configuration ==="
aws s3api get-bucket-location \
  --bucket "$BUCKET_NAME" \
  --query LocationConstraint \
  --output text

aws s3api get-bucket-versioning \
  --bucket "$BUCKET_NAME" \
  --query Status \
  --output text

echo "============================"
echo ""
```

**Expected Output:**
```
Creating S3 destination bucket...
✅ S3 bucket created: datasync-destination-123456789012
✅ Versioning enabled on bucket
✅ Default encryption enabled (AES256)
✅ Bucket tags applied

=== Bucket Configuration ===
ap-southeast-2
Enabled
============================
```

---

# Step 5 – Create DataSync Source Location (NFS Simulation)

```bash
echo "Creating DataSync source location..."
echo ""
echo "⚠️  NOTE: This creates a simulated NFS location for demo purposes."
echo "    In production, you would deploy a real DataSync agent on-premises."
echo ""

# For this lab, we'll use a workaround by uploading files to S3 first
# and creating an S3 source location instead of NFS
# This avoids the need for a real DataSync agent

# Create a temporary source bucket
SOURCE_BUCKET_NAME="datasync-source-${ACCOUNT_ID}"

aws s3api create-bucket \
  --bucket "$SOURCE_BUCKET_NAME" \
  --region "$REGION" \
  --create-bucket-configuration "LocationConstraint=$REGION"

echo "✅ Temporary source bucket created: $SOURCE_BUCKET_NAME"

# Upload test files to source bucket
echo "Uploading test files to source bucket..."
aws s3 sync "$DATASET_DIR" "s3://${SOURCE_BUCKET_NAME}/" \
  --quiet

echo "✅ Files uploaded to source bucket"

# Verify upload
FILE_COUNT_S3=$(aws s3 ls "s3://${SOURCE_BUCKET_NAME}/" | wc -l)
echo "Files in source bucket: $FILE_COUNT_S3"

# Create DataSync source location (S3-based for simplicity)
SOURCE_LOC_ARN=$(aws datasync create-location-s3 \
  --s3-bucket-arn "arn:aws:s3:::${SOURCE_BUCKET_NAME}" \
  --s3-config "BucketAccessRoleArn=${ROLE_ARN}" \
  --query LocationArn \
  --output text)

echo ""
echo "=== Source Location Created ==="
echo "Source Bucket: $SOURCE_BUCKET_NAME"
echo "Location ARN: $SOURCE_LOC_ARN"
echo "================================"
echo ""
```

**Expected Output:**
```
Creating DataSync source location...

⚠️  NOTE: This creates a simulated NFS location for demo purposes.
    In production, you would deploy a real DataSync agent on-premises.

✅ Temporary source bucket created: datasync-source-123456789012
Uploading test files to source bucket...
✅ Files uploaded to source bucket
Files in source bucket: 20

=== Source Location Created ===
Source Bucket: datasync-source-123456789012
Location ARN: arn:aws:datasync:ap-southeast-2:123456789012:location/loc-0123456789abcdef0
================================
```

---

# Step 6 – Create DataSync Destination Location

```bash
# Create DataSync destination location pointing to the destination S3 bucket
echo "Creating DataSync destination location..."

DEST_LOC_ARN=$(aws datasync create-location-s3 \
  --s3-bucket-arn "arn:aws:s3:::${BUCKET_NAME}" \
  --s3-config "BucketAccessRoleArn=${ROLE_ARN}" \
  --s3-storage-class "STANDARD" \
  --query LocationArn \
  --output text)

echo "✅ Destination location created"

# Describe the location
echo ""
echo "=== Destination Location Details ==="
aws datasync describe-location-s3 \
  --location-arn "$DEST_LOC_ARN" \
  --query '[LocationArn,LocationUri,S3StorageClass]' \
  --output table

echo ""
echo "Destination Bucket: $BUCKET_NAME"
echo "Location ARN: $DEST_LOC_ARN"
echo "===================================="
echo ""
```

**Expected Output:**
```
Creating DataSync destination location...
✅ Destination location created

=== Destination Location Details ===
----------------------------------------------------------------------------------
|                           DescribeLocationS3                                    |
+---------------------------------------------------------------------------------+
|  arn:aws:datasync:ap-southeast-2:123456789012:location/loc-abcdef0123456789   |
|  s3://datasync-destination-123456789012/                                       |
|  STANDARD                                                                      |
+---------------------------------------------------------------------------------+

Destination Bucket: datasync-destination-123456789012
Location ARN: arn:aws:datasync:ap-southeast-2:123456789012:location/loc-abcdef0123456789
====================================
```

---

# Step 7 – Create DataSync Task

```bash
# Create DataSync task to transfer data from source to destination
echo "Creating DataSync task..."

TASK_ARN=$(aws datasync create-task \
  --source-location-arn "$SOURCE_LOC_ARN" \
  --destination-location-arn "$DEST_LOC_ARN" \
  --name "DataSync-Lab-15A-Task" \
  --options '{
    "VerifyMode": "POINT_IN_TIME_CONSISTENT",
    "OverwriteMode": "ALWAYS",
    "Atime": "BEST_EFFORT",
    "Mtime": "PRESERVE",
    "PreserveDeletedFiles": "PRESERVE",
    "PreserveDevices": "NONE",
    "PosixPermissions": "NONE",
    "BytesPerSecond": -1,
    "TaskQueueing": "ENABLED"
  }' \
  --cloudwatch-log-group-arn "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/datasync" \
  --query TaskArn \
  --output text 2>/dev/null || \
aws datasync create-task \
  --source-location-arn "$SOURCE_LOC_ARN" \
  --destination-location-arn "$DEST_LOC_ARN" \
  --name "DataSync-Lab-15A-Task" \
  --query TaskArn \
  --output text)

echo "✅ DataSync task created"

# Add tags to the task
aws datasync tag-resource \
  --resource-arn "$TASK_ARN" \
  --tags '[
    {"Key": "Lab", "Value": "15A"},
    {"Key": "Purpose", "Value": "DataSync-Demo"},
    {"Key": "Environment", "Value": "Testing"}
  ]' 2>/dev/null || true

echo "✅ Task tags applied"

# Display task information
echo ""
echo "=== DataSync Task Information ==="
echo "Task Name: DataSync-Lab-15A-Task"
echo "Task ARN: $TASK_ARN"
echo "Source: $SOURCE_LOC_ARN"
echo "Destination: $DEST_LOC_ARN"
echo "=================================="
echo ""

# Describe the task
aws datasync describe-task \
  --task-arn "$TASK_ARN" \
  --query '[Name,Status,SourceLocationArn,DestinationLocationArn]' \
  --output table
```

**Expected Output:**
```
Creating DataSync task...
✅ DataSync task created
✅ Task tags applied

=== DataSync Task Information ===
Task Name: DataSync-Lab-15A-Task
Task ARN: arn:aws:datasync:ap-southeast-2:123456789012:task/task-0123456789abcdef0
Source: arn:aws:datasync:ap-southeast-2:123456789012:location/loc-0123456789abcdef0
Destination: arn:aws:datasync:ap-southeast-2:123456789012:location/loc-abcdef0123456789
==================================

----------------------------------------------------------------------------------
|                              DescribeTask                                       |
+---------------------------------------------------------------------------------+
|  DataSync-Lab-15A-Task                                                         |
|  AVAILABLE                                                                     |
|  arn:aws:datasync:ap-southeast-2:123456789012:location/loc-01234...           |
|  arn:aws:datasync:ap-southeast-2:123456789012:location/loc-abcde...           |
+---------------------------------------------------------------------------------+
```

---

# Step 8 – Start DataSync Task Execution

```bash
# Execute the DataSync task
echo "Starting DataSync task execution..."

TASK_EXEC_ARN=$(aws datasync start-task-execution \
  --task-arn "$TASK_ARN" \
  --query TaskExecutionArn \
  --output text)

echo "✅ Task execution started"
echo ""
echo "=== Task Execution Information ==="
echo "Task Execution ARN: $TASK_EXEC_ARN"
echo "==================================="
echo ""

# Get initial status
INITIAL_STATUS=$(aws datasync describe-task-execution \
  --task-execution-arn "$TASK_EXEC_ARN" \
  --query Status \
  --output text)

echo "Initial Status: $INITIAL_STATUS"
echo ""
echo "⏳ Waiting for task execution to complete..."
echo "   This may take a few minutes depending on dataset size..."
echo ""
```

**Expected Output:**
```
Starting DataSync task execution...
✅ Task execution started

=== Task Execution Information ===
Task Execution ARN: arn:aws:datasync:ap-southeast-2:123456789012:task/task-0123456789abcdef0/execution/exec-0123456789abcdef0
===================================

Initial Status: LAUNCHING

⏳ Waiting for task execution to complete...
   This may take a few minutes depending on dataset size...
```

---

# Step 9 – Monitor Task Execution Progress

```bash
# Monitor task execution status with polling
echo "Monitoring task execution progress..."
echo ""

# Poll every 10 seconds until completion
while true; do
  # Get current execution status
  EXEC_DETAILS=$(aws datasync describe-task-execution \
    --task-execution-arn "$TASK_EXEC_ARN" \
    --output json)
  
  STATUS=$(echo "$EXEC_DETAILS" | jq -r '.Status')
  
  # Display status update
  echo "[$(date '+%H:%M:%S')] Status: $STATUS"
  
  # Check if task is complete
  if [[ "$STATUS" == "SUCCESS" ]]; then
    echo ""
    echo "✅ Task execution completed successfully!"
    echo ""
    
    # Display execution statistics
    echo "=== Execution Statistics ==="
    echo "$EXEC_DETAILS" | jq -r '
      "Files Transferred: " + (.Result.FilesTransferred // 0 | tostring),
      "Bytes Transferred: " + (.Result.BytesTransferred // 0 | tostring),
      "Files Verified: " + (.Result.FilesVerified // 0 | tostring),
      "Duration: " + ((.EstimatedFilesToTransfer // 0) | tostring) + " seconds"
    '
    echo "============================"
    echo ""
    break
  elif [[ "$STATUS" == "ERROR" ]] || [[ "$STATUS" == "FAILED" ]]; then
    echo ""
    echo "❌ Task execution failed!"
    echo ""
    echo "$EXEC_DETAILS" | jq '.ErrorCode, .ErrorDetail'
    break
  fi
  
  # Wait before next check
  sleep 10
done

# Display detailed execution results
echo ""
echo "=== Detailed Execution Results ==="
aws datasync describe-task-execution \
  --task-execution-arn "$TASK_EXEC_ARN" \
  --output json | jq '{
    Status: .Status,
    BytesTransferred: .BytesTransferred,
    FilesTransferred: .FilesTransferred,
    BytesWritten: .BytesWritten,
    StartTime: .StartTime,
    EstimatedFilesToTransfer: .EstimatedFilesToTransfer,
    EstimatedBytesToTransfer: .EstimatedBytesToTransfer,
    Result: .Result
  }'
echo "==================================="
echo ""
```

**Expected Output:**
```
Monitoring task execution progress...

[10:15:30] Status: LAUNCHING
[10:15:40] Status: PREPARING
[10:15:50] Status: TRANSFERRING
[10:16:00] Status: VERIFYING
[10:16:10] Status: SUCCESS

✅ Task execution completed successfully!

=== Execution Statistics ===
Files Transferred: 20
Bytes Transferred: 10240000
Files Verified: 20
Duration: 0 seconds
============================

=== Detailed Execution Results ===
{
  "Status": "SUCCESS",
  "BytesTransferred": 10240000,
  "FilesTransferred": 20,
  "BytesWritten": 10240000,
  "StartTime": "2025-11-13T10:15:30.123Z",
  "EstimatedFilesToTransfer": 20,
  "EstimatedBytesToTransfer": 10240000,
  "Result": {
    "FilesTransferred": 20,
    "BytesTransferred": 10240000,
    "FilesVerified": 20
  }
}
===================================
```

---

# Step 10 – Verify Data in Destination Bucket

```bash
# List all files in the destination bucket
echo "Verifying files in destination bucket..."
echo ""

aws s3 ls "s3://${BUCKET_NAME}/" --recursive

echo ""
echo "=== File Count Verification ==="

# Count files in destination
DEST_FILE_COUNT=$(aws s3 ls "s3://${BUCKET_NAME}/" | wc -l)
echo "Files in destination bucket: $DEST_FILE_COUNT"

# Compare with source
echo "Files in source directory: $FILE_COUNT"

if [[ "$DEST_FILE_COUNT" -eq "$FILE_COUNT" ]]; then
  echo "✅ File count matches!"
else
  echo "⚠️  File count mismatch detected"
fi

echo "================================"
echo ""
```

**Expected Output:**
```
Verifying files in destination bucket...

2025-11-13 10:16:15     488000 file_1.dat
2025-11-13 10:16:15     488000 file_2.dat
2025-11-13 10:16:15     488000 file_3.dat
...
2025-11-13 10:16:15     488000 file_20.dat

=== File Count Verification ===
Files in destination bucket: 20
Files in source directory: 20
✅ File count matches!
================================
```

---

# Step 11 – Validate Data Integrity

```bash
# Download a sample file and verify integrity
echo "Validating data integrity..."
echo ""

# Download file 1 from destination
aws s3 cp "s3://${BUCKET_NAME}/file_1.dat" "/tmp/downloaded_file_1.dat" \
  --quiet

echo "✅ Downloaded file_1.dat from destination bucket"

# Compare with original file
if diff "${DATASET_DIR}/file_1.dat" "/tmp/downloaded_file_1.dat" > /dev/null; then
  echo "✅ File integrity verified - files are identical!"
else
  echo "❌ File integrity check failed - files differ"
fi

# Get checksums for verification
echo ""
echo "=== Checksum Comparison ==="

ORIGINAL_MD5=$(md5sum "${DATASET_DIR}/file_1.dat" | awk '{print $1}')
DOWNLOADED_MD5=$(md5sum "/tmp/downloaded_file_1.dat" | awk '{print $1}')

echo "Original MD5:   $ORIGINAL_MD5"
echo "Downloaded MD5: $DOWNLOADED_MD5"

if [[ "$ORIGINAL_MD5" == "$DOWNLOADED_MD5" ]]; then
  echo "✅ MD5 checksums match!"
else
  echo "❌ MD5 checksums differ"
fi

echo "============================"
echo ""

# Verify multiple files
echo "=== Verifying Additional Files ==="
VERIFIED_COUNT=0
for i in {1..5}; do
  aws s3 cp "s3://${BUCKET_NAME}/file_${i}.dat" "/tmp/verify_file_${i}.dat" --quiet
  
  if diff "${DATASET_DIR}/file_${i}.dat" "/tmp/verify_file_${i}.dat" > /dev/null 2>&1; then
    echo "  ✓ file_${i}.dat verified"
    ((VERIFIED_COUNT++))
  else
    echo "  ✗ file_${i}.dat verification failed"
  fi
done

echo ""
echo "Verified: $VERIFIED_COUNT / 5 sample files"
echo "==================================="
echo ""

# Cleanup temporary verification files
rm -f /tmp/downloaded_file_*.dat /tmp/verify_file_*.dat
```

**Expected Output:**
```
Validating data integrity...

✅ Downloaded file_1.dat from destination bucket
✅ File integrity verified - files are identical!

=== Checksum Comparison ===
Original MD5:   a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
Downloaded MD5: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
✅ MD5 checksums match!
============================

=== Verifying Additional Files ===
  ✓ file_1.dat verified
  ✓ file_2.dat verified
  ✓ file_3.dat verified
  ✓ file_4.dat verified
  ✓ file_5.dat verified

Verified: 5 / 5 sample files
===================================
```

---

# Step 12 – Review CloudWatch Metrics

```bash
# List available DataSync metrics
echo "Reviewing CloudWatch metrics for DataSync..."
echo ""

# List metrics in DataSync namespace
aws cloudwatch list-metrics \
  --namespace "AWS/DataSync" \
  --query 'Metrics[*].[MetricName,Dimensions[0].Value]' \
  --output table

echo ""
echo "=== Key DataSync Metrics ==="
echo "- BytesTransferred: Total bytes moved"
echo "- FilesTransferred: Total files moved"
echo "- BytesVerified: Bytes validated"
echo "- FilesVerified: Files validated"
echo "============================"
echo ""

# Get metric statistics for bytes transferred (if available)
echo "Querying BytesTransferred metric..."

aws cloudwatch get-metric-statistics \
  --namespace "AWS/DataSync" \
  --metric-name "BytesTransferred" \
  --dimensions "Name=TaskId,Value=$(echo $TASK_ARN | awk -F'/' '{print $NF}')" \
  --start-time "$(date -u -d '1 hour ago' '+%Y-%m-%dT%H:%M:%S')" \
  --end-time "$(date -u '+%Y-%m-%dT%H:%M:%S')" \
  --period 300 \
  --statistics Sum \
  --query 'Datapoints[*].[Timestamp,Sum]' \
  --output table 2>/dev/null || echo "  (Metrics may take a few minutes to appear)"

echo ""
```

**Expected Output:**
```
Reviewing CloudWatch metrics for DataSync...

-----------------------------------------------------------------
|                        ListMetrics                             |
+--------------------------------+------------------------------+
|  BytesTransferred              |  task-0123456789abcdef0     |
|  FilesTransferred              |  task-0123456789abcdef0     |
|  BytesVerified                 |  task-0123456789abcdef0     |
|  FilesVerified                 |  task-0123456789abcdef0     |
+--------------------------------+------------------------------+

=== Key DataSync Metrics ===
- BytesTransferred: Total bytes moved
- FilesTransferred: Total files moved
- BytesVerified: Bytes validated
- FilesVerified: Files validated
============================

Querying BytesTransferred metric...
-----------------------------------------------------------------
|                    GetMetricStatistics                         |
+--------------------------------+------------------------------+
|  2025-11-13T10:15:00Z          |  10240000                   |
+--------------------------------+------------------------------+
```

---

# Step 13 – Review Task History and Logs

```bash
# List all task executions for this task
echo "Reviewing task execution history..."
echo ""

aws datasync list-task-executions \
  --task-arn "$TASK_ARN" \
  --query 'TaskExecutions[*].[TaskExecutionArn,Status]' \
  --output table

echo ""

# Get detailed information about the latest execution
echo "=== Latest Execution Details ==="
aws datasync describe-task-execution \
  --task-execution-arn "$TASK_EXEC_ARN" \
  --output json | jq '{
    Status: .Status,
    StartTime: .StartTime,
    BytesTransferred: .BytesTransferred,
    FilesTransferred: .FilesTransferred,
    Result: .Result
  }'
echo "================================"
echo ""

# Check CloudWatch Logs (if log group exists)
echo "Checking CloudWatch Logs..."
LOG_GROUP="/aws/datasync"

# Check if log group exists
LOG_EXISTS=$(aws logs describe-log-groups \
  --log-group-name-prefix "$LOG_GROUP" \
  --query 'logGroups[0].logGroupName' \
  --output text 2>/dev/null)

if [[ "$LOG_EXISTS" != "None" && -n "$LOG_EXISTS" ]]; then
  echo "✅ CloudWatch log group found: $LOG_GROUP"
  
  # List log streams
  aws logs describe-log-streams \
    --log-group-name "$LOG_GROUP" \
    --order-by LastEventTime \
    --descending \
    --max-items 3 \
    --query 'logStreams[*].[logStreamName,lastEventTime]' \
    --output table
else
  echo "ℹ️  CloudWatch log group not configured for this task"
fi

echo ""
```

**Expected Output:**
```
Reviewing task execution history...

----------------------------------------------------------------------------------
|                           ListTaskExecutions                                    |
+---------------------------------------------------------------------------------+
|  arn:aws:datasync:...:task/task-012.../execution/exec-012...  |  SUCCESS       |
+---------------------------------------------------------------------------------+

=== Latest Execution Details ===
{
  "Status": "SUCCESS",
  "StartTime": "2025-11-13T10:15:30.123Z",
  "BytesTransferred": 10240000,
  "FilesTransferred": 20,
  "Result": {
    "FilesTransferred": 20,
    "BytesTransferred": 10240000,
    "FilesVerified": 20
  }
}
================================

Checking CloudWatch Logs...
ℹ️  CloudWatch log group not configured for this task
```

---

# Step 14 – Cost Analysis and Reporting

```bash
# Calculate approximate transfer costs
echo "=== DataSync Cost Analysis ==="
echo ""

# Get bytes transferred
BYTES_TRANSFERRED=$(aws datasync describe-task-execution \
  --task-execution-arn "$TASK_EXEC_ARN" \
  --query 'BytesTransferred' \
  --output text)

# Convert to GB
GB_TRANSFERRED=$(echo "scale=4; $BYTES_TRANSFERRED / 1073741824" | bc)

# Calculate cost ($0.0125 per GB for DataSync)
DATASYNC_COST=$(echo "scale=4; $GB_TRANSFERRED * 0.0125" | bc)

# Calculate S3 storage cost ($0.023 per GB per month)
S3_MONTHLY_COST=$(echo "scale=4; $GB_TRANSFERRED * 0.023" | bc)

echo "Bytes Transferred: $BYTES_TRANSFERRED bytes"
echo "Data Volume: ${GB_TRANSFERRED} GB"
echo ""
echo "DataSync Transfer Cost: \$${DATASYNC_COST}"
echo "S3 Storage Cost (monthly): \$${S3_MONTHLY_COST}"
echo "Total First Month: \$$(echo "scale=4; $DATASYNC_COST + $S3_MONTHLY_COST" | bc)"
echo ""
echo "Note: Costs are approximate and exclude data transfer fees"
echo "==============================="
echo ""
```

**Expected Output:**
```
=== DataSync Cost Analysis ===

Bytes Transferred: 10240000 bytes
Data Volume: .0095 GB

DataSync Transfer Cost: $.0001
S3 Storage Cost (monthly): $.0002
Total First Month: $.0003

Note: Costs are approximate and exclude data transfer fees
===============================
```

---

# Step 15 – Cleanup Resources

```bash
# Comprehensive cleanup of all resources
echo "Starting cleanup process..."
echo ""

# Stop any running task executions (if any)
echo "Checking for running executions..."
RUNNING_EXECS=$(aws datasync list-task-executions \
  --task-arn "$TASK_ARN" \
  --query 'TaskExecutions[?Status==`RUNNING`].TaskExecutionArn' \
  --output text)

if [[ -n "$RUNNING_EXECS" ]]; then
  echo "Cancelling running executions..."
  for EXEC_ARN in $RUNNING_EXECS; do
    aws datasync cancel-task-execution \
      --task-execution-arn "$EXEC_ARN" 2>/dev/null || true
  done
  sleep 5
fi

# Delete DataSync task
echo "Deleting DataSync task..."
aws datasync delete-task \
  --task-arn "$TASK_ARN"
echo "✅ DataSync task deleted"

# Wait for task deletion
sleep 5

# Delete DataSync locations
echo "Deleting DataSync locations..."

aws datasync delete-location \
  --location-arn "$SOURCE_LOC_ARN"
echo "✅ Source location deleted"

aws datasync delete-location \
  --location-arn "$DEST_LOC_ARN"
echo "✅ Destination location deleted"

# Delete S3 buckets and contents
echo "Deleting S3 buckets..."

# Delete source bucket
aws s3 rm "s3://${SOURCE_BUCKET_NAME}" \
  --recursive \
  --quiet
aws s3api delete-bucket \
  --bucket "$SOURCE_BUCKET_NAME"
echo "✅ Source bucket deleted: $SOURCE_BUCKET_NAME"

# Delete destination bucket
aws s3 rm "s3://${BUCKET_NAME}" \
  --recursive \
  --quiet
aws s3api delete-bucket \
  --bucket "$BUCKET_NAME"
echo "✅ Destination bucket deleted: $BUCKET_NAME"

# Detach IAM policy and delete role
echo "Cleaning up IAM role..."

aws iam detach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "arn:aws:iam::aws:policy/AmazonS3FullAccess"

aws iam delete-role \
  --role-name "$ROLE_NAME"
echo "✅ IAM role deleted: $ROLE_NAME"

# Delete local dataset directory
echo "Deleting local dataset..."
rm -rf "$DATASET_DIR"
echo "✅ Local dataset deleted: $DATASET_DIR"

# Delete temporary verification files
rm -f /tmp/downloaded_file_*.dat /tmp/verify_file_*.dat 2>/dev/null || true

echo ""
echo "========================================="
echo "✅ Cleanup completed successfully!"
echo "========================================="
echo ""
echo "All resources have been removed:"
echo "  ✓ DataSync task and locations"
echo "  ✓ S3 source and destination buckets"
echo "  ✓ IAM role and policies"
echo "  ✓ Local test dataset"
echo ""
```

**Expected Output:**
```
Starting cleanup process...

Checking for running executions...
Deleting DataSync task...
✅ DataSync task deleted
Deleting DataSync locations...
✅ Source location deleted
✅ Destination location deleted
Deleting S3 buckets...
✅ Source bucket deleted: datasync-source-123456789012
✅ Destination bucket deleted: datasync-destination-123456789012
Cleaning up IAM role...
✅ IAM role deleted: AWSDataSyncS3Role
Deleting local dataset...
✅ Local dataset deleted: /tmp/datasync-demo

=========================================
✅ Cleanup completed successfully!
=========================================

All resources have been removed:
  ✓ DataSync task and locations
  ✓ S3 source and destination buckets
  ✓ IAM role and policies
  ✓ Local test dataset
```

---

## Best Practices

### Security
- **IAM Least Privilege**: Create specific IAM policies instead of using FullAccess
- **VPC Endpoints**: Use VPC endpoints for DataSync to avoid internet exposure
- **Encryption**: Enable encryption in transit (TLS) and at rest (S3-SSE or KMS)
- **Private Subnets**: Deploy DataSync agents in private subnets with NAT gateway

### Performance
- **Network Bandwidth**: Ensure adequate bandwidth; use bandwidth throttling if needed
- **Parallel Tasks**: Run multiple tasks simultaneously for large migrations
- **Task Scheduling**: Schedule transfers during off-peak hours
- **File Filtering**: Use include/exclude filters to optimize transfers
- **Verify Mode**: Use `ONLY_FILES_TRANSFERRED` for faster verification

### Cost Optimization
- **Data Transfer**: Minimize cross-region transfers when possible
- **Task Scheduling**: Use scheduled tasks instead of continuous sync
- **Lifecycle Policies**: Move infrequently accessed data to cheaper storage classes
- **Monitoring**: Set up billing alarms for unexpected transfer costs

### Reliability
- **Task Retries**: Configure automatic retries for failed transfers
- **CloudWatch Alarms**: Set up alarms for task failures
- **Logging**: Enable CloudWatch Logs for troubleshooting
- **Versioning**: Enable S3 versioning for data protection
- **Backup Validation**: Always verify transferred data integrity

---

## Troubleshooting

### Issue: Task Status "UNAVAILABLE"
**Cause**: DataSync agent is offline or not activated  
**Solution**:
```bash
# Check agent status
aws datasync describe-agent --agent-arn <agent-arn>

# Verify agent connectivity
# Ensure security groups allow traffic on port 443
```

### Issue: Permission Errors
**Cause**: IAM role lacks necessary permissions  
**Solution**:
```bash
# Verify role trust policy
aws iam get-role --role-name AWSDataSyncS3Role

# Check attached policies
aws iam list-attached-role-policies --role-name AWSDataSyncS3Role

# Add required permissions
aws iam attach-role-policy \
  --role-name AWSDataSyncS3Role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
```

### Issue: Slow Transfer Performance
**Cause**: Network bandwidth limitations or insufficient parallelism  
**Solution**:
```bash
# Update task options for better performance
aws datasync update-task \
  --task-arn <task-arn> \
  --options '{
    "VerifyMode": "ONLY_FILES_TRANSFERRED",
    "OverwriteMode": "ALWAYS",
    "TransferMode": "CHANGED",
    "BytesPerSecond": -1
  }'

# Use multiple tasks for parallel transfers
```

### Issue: File Verification Failures
**Cause**: Data corruption or transfer interruption  
**Solution**:
```bash
# Re-run task with full verification
aws datasync start-task-execution \
  --task-arn <task-arn> \
  --override-options VerifyMode=POINT_IN_TIME_CONSISTENT

# Check CloudWatch logs for specific errors
aws logs tail /aws/datasync --follow
```

### Issue: Task Execution Stuck
**Cause**: Large number of small files or network issues  
**Solution**:
```bash
# Cancel stuck execution
aws datasync cancel-task-execution \
  --task-execution-arn <execution-arn>

# Start new execution
aws datasync start-task-execution --task-arn <task-arn>

# Monitor progress
watch -n 10 'aws datasync describe-task-execution --task-execution-arn <execution-arn>'
```

---

## Additional Resources

### AWS Documentation
- [AWS DataSync User Guide](https://docs.aws.amazon.com/datasync/)
- [DataSync Agent Deployment](https://docs.aws.amazon.com/datasync/latest/userguide/deploy-agents.html)
- [DataSync Task Options](https://docs.aws.amazon.com/datasync/latest/userguide/API_Options.html)
- [CloudWatch Metrics for DataSync](https://docs.aws.amazon.com/datasync/latest/userguide/monitoring-datasync.html)

### Related Services
- **AWS Storage Gateway**: Hybrid cloud storage integration
- **AWS Transfer Family**: Managed SFTP/FTPS/FTP for S3
- **S3 Transfer Acceleration**: Faster S3 uploads via CloudFront
- **AWS Snow Family**: Physical data transfer for massive datasets

### Use Cases
- **Data Migration**: Move on-premises data to AWS cloud
- **Hybrid Cloud**: Sync data between on-prem and cloud
- **Disaster Recovery**: Replicate data for DR scenarios
- **Data Processing**: Move data to AWS for analytics
- **Archive**: Transfer cold data to S3 Glacier

---

## Key Takeaways

1. **DataSync Simplifies Transfers**: Automates data movement with built-in validation and encryption
2. **Agent-Based Architecture**: Requires agent deployment for on-premises sources (simulated in this lab)
3. **Flexible Locations**: Supports NFS, SMB, S3, EFS, and FSx as source/destination
4. **Task Configuration**: Customize transfer behavior with verification, bandwidth, and filtering options
5. **Monitoring**: Use CloudWatch metrics and logs for visibility into transfer progress
6. **Cost-Effective**: Pay-per-GB pricing with no upfront costs or infrastructure management
7. **Security**: Built-in encryption and IAM integration for secure data transfers
8. **Scalability**: Handles datasets from GBs to PBs efficiently

---

## Summary

In this lab, you successfully:
- ✅ Created test datasets and S3 destination buckets
- ✅ Configured IAM roles for DataSync S3 access
- ✅ Set up DataSync source and destination locations
- ✅ Created and executed DataSync transfer tasks
- ✅ Monitored task execution with real-time status updates
- ✅ Validated data integrity using file comparisons and checksums
- ✅ Reviewed CloudWatch metrics and execution history
- ✅ Performed comprehensive resource cleanup

AWS DataSync provides a powerful, fully managed solution for accelerated data transfers between on-premises storage and AWS cloud services, making it ideal for migrations, hybrid cloud architectures, and disaster recovery scenarios.

---

## End of Lab 15.A

**Next Lab**: Lab 15.B - AWS Migration Hub - Track Application Migrations

---
