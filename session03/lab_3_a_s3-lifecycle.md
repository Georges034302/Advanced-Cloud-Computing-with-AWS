# Lab 3.A: Manage S3 buckets with versioning, encryption, and lifecycle rules
<img width="1024" height="1024" alt="IMG" src="https://github.com/user-attachments/assets/cfbe70fa-5a29-4ac5-b641-5efe4cea7992" />

## Overview
This lab teaches how to create and manage Amazon S3 buckets with object versioning, server-side encryption (SSE-S3 and SSE-KMS), bucket policies to enforce secure uploads, and lifecycle rules to transition and expire objects. You'll validate versioning behavior, encrypted storage, and cost-saving lifecycle transitions.

## Objectives
- Create an S3 bucket with versioning enabled
- Configure default encryption (SSE-S3 and SSE-KMS example)
- Create and use a KMS key for SSE-KMS
- Enforce HTTPS and required encryption with a bucket policy
- Define lifecycle rules: transition to STANDARD_IA / GLACIER / DEEP_ARCHIVE and expire older versions
- Validate versioning, encryption, and lifecycle behavior
- Clean up resources

## Prerequisites
- AWS CLI configured and authenticated
- jq (optional) for JSON handling
- awscli v2 recommended
- Permissions to manage S3, KMS, and IAM

---

## Steps (CLI examples)

### 1. Set Variables and Create the Bucket
```bash
# Get AWS account ID
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set region and bucket name
export REGION="ap-southeast-2"
echo "REGION=$REGION"

export BUCKET="s3-lifecycle-lab-${ACCOUNT_ID}"
echo "BUCKET=$BUCKET"

# Create bucket in ap-southeast-2
aws s3api create-bucket \
  --bucket "$BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

echo "Bucket created: $BUCKET"
```

### 2. Enable versioning
```bash
# Enable versioning on the bucket to keep multiple versions of objects
aws s3api put-bucket-versioning \
  --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled

echo "Versioning enabled on bucket: $BUCKET"
```

(Optional: MFA Delete requires root and console operations; not covered here.)

### 3. Create a KMS key (for SSE-KMS) and grant usage to S3
```bash
# Create a Customer Managed Key (CMK) and capture the KeyId
# This key will be used for server-side encryption of S3 objects
export KEY_ID=$(aws kms create-key \
  --description "KMS key for S3 bucket $BUCKET" \
  --query KeyMetadata.KeyId \
  --output text)
echo "KEY_ID=$KEY_ID"

# Create a human-readable alias for the KMS key
# Makes it easier to reference the key instead of using the long KeyId
aws kms create-alias \
  --alias-name "alias/lab-s3-kms" \
  --target-key-id "$KEY_ID"

echo "KMS key created with alias: alias/lab-s3-kms"

# Create a complete KMS key policy
# This policy allows:
#   1. Account root to manage the key (required for key administration)
#   2. S3 service to use the key for encryption/decryption operations
cat > key-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Enable IAM User Permissions",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::${ACCOUNT_ID}:root"
      },
      "Action": "kms:*",
      "Resource": "*"
    },
    {
      "Sid": "Allow S3 to use the key",
      "Effect": "Allow",
      "Principal": {
        "Service": "s3.amazonaws.com"
      },
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:GenerateDataKey",
        "kms:ReEncrypt*",
        "kms:DescribeKey"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "s3.${REGION}.amazonaws.com"
        }
      }
    }
  ]
}
EOF

# Apply the key policy to the KMS key
# The 'default' policy name is required for the primary key policy
aws kms put-key-policy \
  --key-id "$KEY_ID" \
  --policy-name default \
  --policy file://key-policy.json

echo "KMS key policy updated"
```

### 4. Set default bucket encryption (SSE-KMS example)
```bash
# Set default encryption to SSE-KMS (Server-Side Encryption with KMS)
# All objects uploaded to this bucket will be automatically encrypted
# BucketKeyEnabled reduces KMS API calls and costs
aws s3api put-bucket-encryption \
  --bucket "$BUCKET" \
  --server-side-encryption-configuration "{
    \"Rules\": [
      {
        \"ApplyServerSideEncryptionByDefault\": {
          \"SSEAlgorithm\": \"aws:kms\",
          \"KMSMasterKeyID\": \"arn:aws:kms:${REGION}:${ACCOUNT_ID}:key/${KEY_ID}\"
        },
        \"BucketKeyEnabled\": true
      }
    ]
  }"

echo "Bucket encryption enabled with SSE-KMS"

# Verify encryption configuration was applied correctly
aws s3api get-bucket-encryption --bucket "$BUCKET"
```

**Note:** For SSE-S3 (simpler, no KMS key needed), use:
```bash
# Alternative: Use SSE-S3 (Amazon S3-managed encryption keys)
# Simpler than SSE-KMS but less control over key management
# AES256 is the S3-managed encryption algorithm
aws s3api put-bucket-encryption \
  --bucket "$BUCKET" \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        },
        "BucketKeyEnabled": false
      }
    ]
  }'
```

### 5. Enforce HTTPS and encrypted uploads with a bucket policy
```bash
# Create a bucket policy that enforces security best practices:
#   1. Deny all requests not using HTTPS (secure transport)
#   2. Deny PutObject requests without KMS encryption
# Variable interpolation uses double quotes in heredoc
cat > bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::${BUCKET}",
        "arn:aws:s3:::${BUCKET}/*"
      ],
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    },
    {
      "Sid": "RequireKMSEncryption",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::${BUCKET}/*",
      "Condition": {
        "StringNotEquals": {
          "s3:x-amz-server-side-encryption": "aws:kms"
        }
      }
    }
  ]
}
EOF

# Apply the bucket policy to enforce security requirements
aws s3api put-bucket-policy \
  --bucket "$BUCKET" \
  --policy file://bucket-policy.json

echo "Bucket policy applied (enforces HTTPS and KMS encryption)"

# Verify bucket policy was applied correctly
# Parse JSON output with jq for better readability
aws s3api get-bucket-policy --bucket "$BUCKET" --query Policy --output text | jq .
```

### 6. Add lifecycle configuration (transition + expiration)
Example: transition to STANDARD_IA after 30 days, GLACIER_IR after 90 days, expire current versions after 730 days (2 years), noncurrent versions after 365 days.

```bash
# Create lifecycle policy to automatically manage object storage classes
# This reduces costs by moving older objects to cheaper storage tiers
# Single quotes in heredoc prevent variable interpolation
cat > lifecycle.json <<'EOF'
{
  "Rules": [
    {
      "ID": "TransitionAndExpireObjects",
      "Status": "Enabled",
      "Filter": {
        "Prefix": ""
      },
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 90,
          "StorageClass": "GLACIER_IR"
        },
        {
          "Days": 180,
          "StorageClass": "DEEP_ARCHIVE"
        }
      ],
      "Expiration": {
        "Days": 730
      },
      "NoncurrentVersionTransitions": [
        {
          "NoncurrentDays": 30,
          "StorageClass": "STANDARD_IA"
        },
        {
          "NoncurrentDays": 90,
          "StorageClass": "GLACIER_IR"
        }
      ],
      "NoncurrentVersionExpiration": {
        "NoncurrentDays": 365
      }
    }
  ]
}
EOF

# Apply the lifecycle configuration to the bucket
# Changes take effect immediately but transitions are asynchronous
aws s3api put-bucket-lifecycle-configuration \
  --bucket "$BUCKET" \
  --lifecycle-configuration file://lifecycle.json

echo "Lifecycle configuration applied"

# Verify lifecycle configuration was applied correctly
aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET"
```

**Notes:**
- **STANDARD_IA**: Infrequent Access (cheaper than STANDARD, min 30 days)
- **GLACIER_IR**: Glacier Instant Retrieval (min 90 days, instant access)
- **DEEP_ARCHIVE**: Lowest cost (min 180 days, 12-48 hour retrieval)
- Transitions must be in increasing order of days
- Expiration must be after all transitions
- Lifecycle actions are asynchronous and can take 24-48 hours

### 7. Test versioning and encryption
```bash
# Create test files with different content
# These will be used to test versioning behavior
echo "Version 1 of test file" > test-file.txt
echo "Version 2 of test file" > test-file-v2.txt
echo "Version 3 of test file" > test-file-v3.txt

# Upload version 1 with KMS encryption explicitly specified
aws s3api put-object \
  --bucket "$BUCKET" \
  --key test-file.txt \
  --body test-file.txt \
  --server-side-encryption aws:kms \
  --ssekms-key-id "$KEY_ID"
echo "Uploaded version 1"

# Upload version 2 - overwrites v1, but v1 is preserved as noncurrent version
# This demonstrates how versioning keeps all versions of an object
# Upload version 2 with KMS encryption
aws s3api put-object \
  --bucket "$BUCKET" \
  --key test-file.txt \
  --body test-file-v2.txt \
  --server-side-encryption aws:kms \
  --ssekms-key-id "$KEY_ID"
echo "Uploaded version 2"

# Upload version 3 - v2 becomes noncurrent, v3 is the latest version
# Upload version 3 with KMS encryption
aws s3api put-object \
  --bucket "$BUCKET" \
  --key test-file.txt \
  --body test-file-v3.txt \
  --server-side-encryption aws:kms \
  --ssekms-key-id "$KEY_ID"
echo "Uploaded version 3"

# List all versions of the test file
echo "Listing all versions:"
aws s3api list-object-versions \
  --bucket "$BUCKET" \
  --prefix test-file.txt \
  --query 'Versions[].{Key:Key,VersionId:VersionId,IsLatest:IsLatest,LastModified:LastModified,Size:Size}' \
  --output table

# Check encryption metadata of the latest version
echo "Checking encryption:"
aws s3api head-object \
  --bucket "$BUCKET" \
  --key test-file.txt \
  --query '{Encryption:ServerSideEncryption,KMSKeyId:SSEKMSKeyId,StorageClass:StorageClass}' \
  --output table

# Verify versioning status is still enabled
echo "\nVerifying versioning status:"
aws s3api get-bucket-versioning --bucket "$BUCKET"
```

### 8. Observe lifecycle behavior
```bash
# Check current storage class of all objects in the bucket
# Initially, all objects will be in STANDARD storage class
# Re-run this command periodically to observe lifecycle transitions
echo "Checking storage class:"
aws s3api list-objects-v2 \
  --bucket "$BUCKET" \
  --query 'Contents[].{Key:Key,StorageClass:StorageClass,LastModified:LastModified}' \
  --output table

# Note: Objects start in STANDARD storage class
# Lifecycle transitions happen asynchronously (24-48 hours after rule conditions are met)

echo "\n⏰ Lifecycle transitions are asynchronous and take 24-48 hours"
echo "Objects will transition according to these rules:"
echo "  - Day 30: STANDARD → STANDARD_IA"
echo "  - Day 90: STANDARD_IA → GLACIER_IR"
echo "  - Day 180: GLACIER_IR → DEEP_ARCHIVE"
echo "  - Day 730: Objects expire and are deleted"
echo "\nTo monitor transitions over time, re-run the list-objects-v2 command above"
```

**Monitoring Tips:**
- Use S3 Storage Lens for storage class analytics
- Use S3 Inventory for detailed object reports
- Check storage class with `head-object` for specific objects
- Lifecycle metrics available in CloudWatch after transitions occur

## Validation Checklist
- [ ] Bucket created and versioning enabled
- [ ] Default encryption applied (SSE-KMS or SSE-S3)
- [ ] KMS key created and accessible by S3
- [ ] Bucket policy enforces HTTPS and required encryption
- [ ] Lifecycle rules present and configured as intended
- [ ] Uploaded objects show versions and encryption metadata
- [ ] Objects transition to lower-cost storage per lifecycle rules

## Cleanup
```bash
echo "Starting cleanup..."

# Remove bucket policy first to avoid conflicts during deletion
# Redirect errors to /dev/null and show friendly message if no policy exists
echo "Removing bucket policy..."
aws s3api delete-bucket-policy --bucket "$BUCKET" 2>/dev/null || echo "No bucket policy to remove"

# Remove lifecycle configuration before deleting objects
echo "Removing lifecycle configuration..."
aws s3api delete-bucket-lifecycle --bucket "$BUCKET" 2>/dev/null || echo "No lifecycle configuration to remove"

# Suspend versioning to prevent new versions during cleanup
# This doesn't delete existing versions, just stops creating new ones
echo "Suspending versioning..."
aws s3api put-bucket-versioning \
  --bucket "$BUCKET" \
  --versioning-configuration Status=Suspended

# Delete all object versions (required before bucket deletion)
# List all versions and parse with jq
echo "Deleting all object versions..."
VERSIONS=$(aws s3api list-object-versions \
  --bucket "$BUCKET" \
  --query 'Versions[].{Key:Key,VersionId:VersionId}' \
  --output json)

# Check if there are any versions to delete
if [ "$VERSIONS" != "null" ] && [ "$VERSIONS" != "[]" ]; then
  # Loop through each version and delete it
  echo "$VERSIONS" | jq -c '.[]' | while read -r version; do
    KEY=$(echo "$version" | jq -r '.Key')
    VERSION_ID=$(echo "$version" | jq -r '.VersionId')
    echo "Deleting: $KEY (version: $VERSION_ID)"
    # Delete specific version by VersionId
    aws s3api delete-object \
      --bucket "$BUCKET" \
      --key "$KEY" \
      --version-id "$VERSION_ID" > /dev/null
  done
else
  echo "No versions to delete"
fi

# Delete all delete markers (created when objects are deleted in versioned buckets)
# Delete markers are special version markers, not actual objects
echo "Deleting all delete markers..."
DELETE_MARKERS=$(aws s3api list-object-versions \
  --bucket "$BUCKET" \
  --query 'DeleteMarkers[].{Key:Key,VersionId:VersionId}' \
  --output json)

# Check if there are any delete markers
if [ "$DELETE_MARKERS" != "null" ] && [ "$DELETE_MARKERS" != "[]" ]; then
  # Loop through each delete marker and remove it
  echo "$DELETE_MARKERS" | jq -c '.[]' | while read -r marker; do
    KEY=$(echo "$marker" | jq -r '.Key')
    VERSION_ID=$(echo "$marker" | jq -r '.VersionId')
    echo "Deleting delete marker: $KEY (version: $VERSION_ID)"
    # Remove delete marker by VersionId
    aws s3api delete-object \
      --bucket "$BUCKET" \
      --key "$KEY" \
      --version-id "$VERSION_ID" > /dev/null
  done
else
  echo "No delete markers to delete"
fi

# Delete the empty bucket
# Bucket must be empty (no versions or delete markers) before deletion
echo "Deleting bucket..."
aws s3api delete-bucket --bucket "$BUCKET"
echo "Bucket deleted: $BUCKET"

# Schedule KMS key deletion with mandatory 7-30 day waiting period
# This is a safety feature to prevent accidental key deletion
if [ -n "$KEY_ID" ]; then
  echo "Scheduling KMS key deletion..."
  aws kms schedule-key-deletion \
    --key-id "$KEY_ID" \
    --pending-window-in-days 7
  echo "KMS key scheduled for deletion in 7 days: $KEY_ID"
  echo "To cancel: aws kms cancel-key-deletion --key-id $KEY_ID"
fi

# Clean up local JSON and test files
echo "Cleaning up local files..."
rm -f bucket-policy.json lifecycle.json key-policy.json test-file*.txt

echo "\n✅ Cleanup complete!"
```

## Summary
This lab demonstrates S3 versioning, encryption with SSE-KMS/SSE-S3, lifecycle policies to reduce storage costs, and policy controls to enforce secure uploads. Use lifecycle rules and encryption to meet retention, compliance, and cost goals.
