# Lab 14.C: Amazon S3 - Cross-Region Replication for Disaster Recovery

## Overview
This lab demonstrates Amazon S3 Cross-Region Replication (CRR), which automatically and asynchronously copies objects from a source bucket in one region to a destination bucket in another region. You'll configure CRR with versioning, test object replication, verify delete marker replication, and monitor replication metrics.

---

## Objectives
- Create source and destination S3 buckets in different regions
- Enable versioning on both buckets (required for CRR)
- Create IAM role with replication permissions
- Configure cross-region replication rules
- Upload objects and verify replication
- Test version replication on object updates
- Test delete marker replication
- Monitor replication metrics
- Clean up multi-region resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for S3 and IAM operations
- Regions: ap-southeast-2 (source), us-west-2 (destination)
- Understanding of S3 versioning

---

## Architecture

```
Source Bucket (ap-southeast-2)
├─ Versioning: Enabled
├─ Replication Rule: All objects
└─ IAM Role: S3CRRRole
          ↓
  Asynchronous Replication
  (Typically < 15 minutes)
          ↓
Destination Bucket (us-west-2)
├─ Versioning: Enabled
├─ Receives: Objects + Versions
└─ Receives: Delete Markers

Benefits:
- Geographic redundancy
- Disaster recovery
- Compliance (data residency)
- Lower latency access
```

---

## Step 1 – Set Variables

```bash
# Set regions
SRC_REGION="ap-southeast-2"
DEST_REGION="us-west-2"

echo "SRC_REGION=$SRC_REGION"
echo "DEST_REGION=$DEST_REGION"

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)

echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set bucket names (must be globally unique)
SRC_BUCKET="crr-source-${ACCOUNT_ID}"
DEST_BUCKET="crr-destination-${ACCOUNT_ID}"

echo "SRC_BUCKET=$SRC_BUCKET"
echo "DEST_BUCKET=$DEST_BUCKET"
echo ""
echo "================================================"
echo "S3 CROSS-REGION REPLICATION"
echo "================================================"
```

---

## Step 2 – Create Source Bucket

```bash
echo ""
echo "Creating source bucket in $SRC_REGION..."

# Create source bucket
aws s3api create-bucket \
  --bucket "$SRC_BUCKET" \
  --region "$SRC_REGION" \
  --create-bucket-configuration LocationConstraint="$SRC_REGION"

echo "✅ Source bucket created: $SRC_BUCKET"

# Add tags
aws s3api put-bucket-tagging \
  --bucket "$SRC_BUCKET" \
  --tagging "TagSet=[{Key=Purpose,Value=CRR-Source},{Key=Environment,Value=Demo}]"

echo "✅ Bucket tags applied"
```

---

## Step 3 – Create Destination Bucket

```bash
echo ""
echo "Creating destination bucket in $DEST_REGION..."

# Create destination bucket
aws s3api create-bucket \
  --bucket "$DEST_BUCKET" \
  --region "$DEST_REGION" \
  --create-bucket-configuration LocationConstraint="$DEST_REGION"

echo "✅ Destination bucket created: $DEST_BUCKET"

# Add tags
aws s3api put-bucket-tagging \
  --bucket "$DEST_BUCKET" \
  --tagging "TagSet=[{Key=Purpose,Value=CRR-Destination},{Key=Environment,Value=Demo}]"

echo "✅ Bucket tags applied"
```

---

## Step 4 – Enable Versioning on Both Buckets

```bash
echo ""
echo "Enabling versioning (required for CRR)..."

# Enable versioning on source bucket
aws s3api put-bucket-versioning \
  --bucket "$SRC_BUCKET" \
  --versioning-configuration Status=Enabled

echo "✅ Versioning enabled on source bucket"

# Enable versioning on destination bucket
aws s3api put-bucket-versioning \
  --bucket "$DEST_BUCKET" \
  --versioning-configuration Status=Enabled

echo "✅ Versioning enabled on destination bucket"
```

---

## Step 5 – Create IAM Role for Replication

```bash
echo ""
echo "================================================"
echo "CONFIGURING IAM ROLE"
echo "================================================"
echo ""

echo "Creating IAM role for S3 replication..."

# Create trust policy
cat > /tmp/crr-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "s3.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name S3CRRRole \
  --assume-role-policy-document file:///tmp/crr-trust-policy.json \
  --description "IAM role for S3 Cross-Region Replication"

echo "✅ IAM role created: S3CRRRole"

# Get role ARN
ROLE_ARN=$(aws iam get-role \
  --role-name S3CRRRole \
  --query 'Role.Arn' \
  --output text)

echo "ROLE_ARN=$ROLE_ARN"
```

---

## Step 6 – Attach Replication Policy to Role

```bash
echo ""
echo "Attaching replication permissions to role..."

# Create replication policy
cat > /tmp/crr-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetReplicationConfiguration",
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::${SRC_BUCKET}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObjectVersionForReplication",
        "s3:GetObjectVersionAcl",
        "s3:GetObjectVersionTagging"
      ],
      "Resource": "arn:aws:s3:::${SRC_BUCKET}/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ReplicateObject",
        "s3:ReplicateDelete",
        "s3:ReplicateTags"
      ],
      "Resource": "arn:aws:s3:::${DEST_BUCKET}/*"
    }
  ]
}
EOF

# Attach inline policy
aws iam put-role-policy \
  --role-name S3CRRRole \
  --policy-name S3CRRPolicy \
  --policy-document file:///tmp/crr-policy.json

echo "✅ Replication policy attached"
```

---

## Step 7 – Configure Cross-Region Replication

```bash
echo ""
echo "================================================"
echo "ENABLING CROSS-REGION REPLICATION"
echo "================================================"
echo ""

echo "Configuring replication rule..."

# Create replication configuration
cat > /tmp/replication-config.json <<EOF
{
  "Role": "${ROLE_ARN}",
  "Rules": [
    {
      "ID": "ReplicateAllObjects",
      "Status": "Enabled",
      "Priority": 1,
      "DeleteMarkerReplication": {
        "Status": "Enabled"
      },
      "Filter": {
        "Prefix": ""
      },
      "Destination": {
        "Bucket": "arn:aws:s3:::${DEST_BUCKET}",
        "ReplicationTime": {
          "Status": "Enabled",
          "Time": {
            "Minutes": 15
          }
        },
        "Metrics": {
          "Status": "Enabled",
          "EventThreshold": {
            "Minutes": 15
          }
        }
      }
    }
  ]
}
EOF

# Wait for IAM role to propagate
echo "Waiting 10 seconds for IAM role to propagate..."
sleep 10

# Apply replication configuration
aws s3api put-bucket-replication \
  --bucket "$SRC_BUCKET" \
  --replication-configuration file:///tmp/replication-config.json

echo "✅ Cross-region replication enabled"
echo "   Replication rule: All objects"
echo "   Delete markers: Replicated"
echo "   Target: $DEST_BUCKET in $DEST_REGION"
```

---

## Step 8 – Upload Test Files

```bash
echo ""
echo "================================================"
echo "TESTING REPLICATION"
echo "================================================"
echo ""

echo "Creating test files..."

# Create sample files
cat > /tmp/document1.txt <<EOF
CRR Test Document 1
Created: $(date)
Region: ${SRC_REGION}
Purpose: Cross-Region Replication Testing
EOF

cat > /tmp/document2.txt <<EOF
CRR Test Document 2
Created: $(date)
Region: ${SRC_REGION}
Purpose: Disaster Recovery
EOF

cat > /tmp/image.txt <<EOF
Simulated Image File
Size: Large
Format: JPEG (simulated)
EOF

echo "✅ Test files created"
echo ""

# Upload files to source bucket
echo "Uploading files to source bucket..."

aws s3 cp /tmp/document1.txt \
  s3://"$SRC_BUCKET"/documents/document1.txt \
  --metadata "type=document,version=1"

aws s3 cp /tmp/document2.txt \
  s3://"$SRC_BUCKET"/documents/document2.txt \
  --metadata "type=document,version=1"

aws s3 cp /tmp/image.txt \
  s3://"$SRC_BUCKET"/images/image.txt \
  --metadata "type=image,format=jpg"

echo "✅ Files uploaded to source bucket"
```

---

## Step 9 – List Source Bucket Objects

```bash
echo ""
echo "Listing objects in source bucket:"

# List objects
aws s3 ls s3://"$SRC_BUCKET"/ --recursive

echo ""
echo "✅ Source bucket contains 3 objects"
```

---

## Step 10 – Wait for Replication

```bash
echo ""
echo "Waiting for replication to complete..."
echo "(CRR typically takes 15 seconds to 15 minutes)"
echo ""

# Wait for replication
WAIT_TIME=0
MAX_WAIT=180

while [ $WAIT_TIME -lt $MAX_WAIT ]; do
  OBJECT_COUNT=$(aws s3 ls s3://"$DEST_BUCKET"/ --recursive 2>/dev/null | wc -l)
  
  echo "Progress: $OBJECT_COUNT/3 objects replicated (waited ${WAIT_TIME}s)"
  
  if [ "$OBJECT_COUNT" -eq 3 ]; then
    echo ""
    echo "✅ All objects replicated successfully!"
    break
  fi
  
  sleep 15
  WAIT_TIME=$((WAIT_TIME + 15))
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
  echo ""
  echo "⚠️  Replication taking longer than expected (check replication status)"
fi
```

---

## Step 11 – Verify Replication in Destination

```bash
echo ""
echo "Listing objects in destination bucket:"

# List replicated objects
aws s3 ls s3://"$DEST_BUCKET"/ --recursive

echo ""
echo "✅ Objects successfully replicated to $DEST_REGION"
```

---

## Step 12 – Test Version Replication

```bash
echo ""
echo "================================================"
echo "TESTING VERSION REPLICATION"
echo "================================================"
echo ""

echo "Updating document1.txt with new version..."

# Create updated version
cat > /tmp/document1-v2.txt <<EOF
CRR Test Document 1 - VERSION 2
Updated: $(date)
Region: ${SRC_REGION}
Purpose: Testing version replication
Changes: Content updated to test versioning
EOF

# Upload new version
aws s3 cp /tmp/document1-v2.txt \
  s3://"$SRC_BUCKET"/documents/document1.txt \
  --metadata "type=document,version=2"

echo "✅ New version uploaded"
echo ""
echo "Waiting 30 seconds for version replication..."
sleep 30
```

---

## Step 13 – Verify Version Replication

```bash
echo ""
echo "Checking versions in source bucket:"

# List versions in source
aws s3api list-object-versions \
  --bucket "$SRC_BUCKET" \
  --prefix "documents/document1.txt" \
  --query 'Versions[*].{Key:Key,VersionId:VersionId,IsLatest:IsLatest,LastModified:LastModified}' \
  --output table

echo ""
echo "Checking versions in destination bucket:"

# List versions in destination
aws s3api list-object-versions \
  --bucket "$DEST_BUCKET" \
  --prefix "documents/document1.txt" \
  --query 'Versions[*].{Key:Key,VersionId:VersionId,IsLatest:IsLatest,LastModified:LastModified}' \
  --output table

echo ""
echo "✅ Version replication verified"
```

---

## Step 14 – Test Delete Marker Replication

```bash
echo ""
echo "================================================"
echo "TESTING DELETE MARKER REPLICATION"
echo "================================================"
echo ""

echo "Deleting document2.txt from source bucket..."

# Delete object (creates delete marker)
aws s3 rm s3://"$SRC_BUCKET"/documents/document2.txt

echo "✅ Object deleted (delete marker created)"
echo ""
echo "Waiting 30 seconds for delete marker replication..."
sleep 30
```

---

## Step 15 – Verify Delete Marker Replication

```bash
echo ""
echo "Checking delete markers in source bucket:"

# List delete markers in source
aws s3api list-object-versions \
  --bucket "$SRC_BUCKET" \
  --prefix "documents/document2.txt" \
  --query 'DeleteMarkers[*].{Key:Key,VersionId:VersionId,IsLatest:IsLatest}' \
  --output table

echo ""
echo "Checking delete markers in destination bucket:"

# List delete markers in destination
aws s3api list-object-versions \
  --bucket "$DEST_BUCKET" \
  --prefix "documents/document2.txt" \
  --query 'DeleteMarkers[*].{Key:Key,VersionId:VersionId,IsLatest:IsLatest}' \
  --output table

echo ""
echo "✅ Delete marker replication verified"
echo "   Object appears deleted in both regions"
```

---

## Step 16 – Check Replication Status

```bash
echo ""
echo "Checking replication configuration..."

# Get replication configuration
aws s3api get-bucket-replication \
  --bucket "$SRC_BUCKET" \
  --query 'ReplicationConfiguration.{Role:Role,Rules:Rules[*].{ID:ID,Status:Status,Priority:Priority}}' \
  --output json

echo ""
echo "✅ Replication configuration active"
```

---

## Step 17 – Cleanup

```bash
echo ""
echo "================================================"
echo "CLEANUP"
echo "================================================"
echo ""

echo "Cleaning up resources..."

# Delete all object versions from source bucket
echo "Deleting objects from source bucket..."
aws s3api list-object-versions \
  --bucket "$SRC_BUCKET" \
  --query 'Versions[*].{Key:Key,VersionId:VersionId}' \
  --output json | jq -r '.[] | "--key \(.Key) --version-id \(.VersionId)"' | \
  while read params; do
    aws s3api delete-object --bucket "$SRC_BUCKET" $params 2>/dev/null
  done

# Delete delete markers from source
aws s3api list-object-versions \
  --bucket "$SRC_BUCKET" \
  --query 'DeleteMarkers[*].{Key:Key,VersionId:VersionId}' \
  --output json | jq -r '.[] | "--key \(.Key) --version-id \(.VersionId)"' | \
  while read params; do
    aws s3api delete-object --bucket "$SRC_BUCKET" $params 2>/dev/null
  done

echo "✅ Source bucket objects deleted"

# Delete all object versions from destination bucket
echo "Deleting objects from destination bucket..."
aws s3api list-object-versions \
  --bucket "$DEST_BUCKET" \
  --query 'Versions[*].{Key:Key,VersionId:VersionId}' \
  --output json | jq -r '.[] | "--key \(.Key) --version-id \(.VersionId)"' | \
  while read params; do
    aws s3api delete-object --bucket "$DEST_BUCKET" $params 2>/dev/null
  done

# Delete delete markers from destination
aws s3api list-object-versions \
  --bucket "$DEST_BUCKET" \
  --query 'DeleteMarkers[*].{Key:Key,VersionId:VersionId}' \
  --output json | jq -r '.[] | "--key \(.Key) --version-id \(.VersionId)"' | \
  while read params; do
    aws s3api delete-object --bucket "$DEST_BUCKET" $params 2>/dev/null
  done

echo "✅ Destination bucket objects deleted"

# Delete buckets
echo "Deleting buckets..."
aws s3api delete-bucket \
  --bucket "$SRC_BUCKET"

aws s3api delete-bucket \
  --bucket "$DEST_BUCKET"

echo "✅ Buckets deleted"

# Delete IAM policy and role
echo "Deleting IAM role and policy..."
aws iam delete-role-policy \
  --role-name S3CRRRole \
  --policy-name S3CRRPolicy

aws iam delete-role \
  --role-name S3CRRRole

echo "✅ IAM resources deleted"

# Clean up temp files
rm -f /tmp/crr-trust-policy.json /tmp/crr-policy.json /tmp/replication-config.json
rm -f /tmp/document1.txt /tmp/document2.txt /tmp/image.txt /tmp/document1-v2.txt

echo ""
echo "All resources cleaned up!"
```

---

## Summary

In this lab, you have:
- Created source and destination S3 buckets in different regions
- Enabled versioning on both buckets (required for CRR)
- Created IAM role with appropriate replication permissions
- Configured cross-region replication with all-object rule
- Uploaded multiple test files to source bucket
- Verified automatic replication to destination bucket
- Tested version replication by updating objects
- Tested delete marker replication
- Monitored replication status and metrics
- Cleaned up multi-region resources

**Key Takeaways:**
- **Automatic Replication**: Objects replicated asynchronously (seconds to minutes)
- **Versioning Required**: Both buckets must have versioning enabled
- **Delete Markers**: Can be configured to replicate or not
- **IAM Permissions**: Requires specific role with replication permissions
- **Use Cases**: DR, compliance, latency reduction, data sovereignty

---

## Best Practices

**Configuration:**
- Enable versioning before configuring replication
- Use replication time control for predictable replication
- Configure metrics and alarms for replication failures
- Use prefix/tag filters to replicate specific objects only
- Enable replication for existing objects if needed

**Security:**
- Use AWS KMS for encryption at rest
- Configure key policies for cross-region key access
- Enable bucket policies to prevent accidental deletion
- Use S3 Object Lock for compliance requirements
- Enable MFA delete for critical buckets

**Performance:**
- Monitor replication latency with CloudWatch
- Use S3 Transfer Acceleration for faster uploads
- Consider multi-part upload for large objects
- Use appropriate storage classes in destination
- Monitor data transfer costs

**Cost Optimization:**
- Use lifecycle policies in destination bucket
- Replicate only necessary objects (use filters)
- Monitor replication bandwidth costs
- Use S3 Intelligent-Tiering
- Consider same-region replication (SRR) if cross-region not needed

**Monitoring:**
- Set up CloudWatch alarms for replication failures
- Monitor ReplicationLatency metric
- Track BytesPendingReplication metric
- Use S3 Event Notifications for replication events
- Review S3 access logs regularly

---

## Troubleshooting

**Objects not replicating:**
- Verify versioning enabled on both buckets
- Check IAM role permissions and trust policy
- Verify replication rule is enabled
- Check object is uploaded after replication configured
- Review CloudWatch metrics for errors

**Replication lag is high:**
- Check object size (large objects take longer)
- Verify network connectivity between regions
- Monitor BytesPendingReplication metric
- Check for replication throttling
- Consider using Replication Time Control (RTC)

**Delete markers not replicating:**
- Verify DeleteMarkerReplication is enabled
- Check object was deleted, not permanently deleted
- Ensure versioning is enabled
- Review replication configuration

**Permission errors:**
- Verify IAM role has AssumeRole policy for s3.amazonaws.com
- Check source bucket permissions in IAM policy
- Verify destination bucket permissions in IAM policy
- Ensure role ARN is correct in replication config

**Cannot delete bucket:**
- Must delete all object versions first
- Must delete all delete markers
- Use list-object-versions to find all versions
- Consider using lifecycle policies for bulk deletion

**High costs:**
- Monitor data transfer charges (cross-region)
- Use replication filters to limit objects
- Check for unnecessary version replication
- Review storage class in destination
- Consider lifecycle policies to reduce storage

---

## Additional Resources

- [S3 Replication Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication.html)
- [Replication Configuration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication-add-config.html)
- [Replication Time Control](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication-time-control.html)
- [S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)
- [S3 Pricing](https://aws.amazon.com/s3/pricing/)
- [Monitoring Replication](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication-metrics.html)
