# Lab 3.A: Manage S3 buckets with versioning, encryption, and lifecycle rules

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

Replace placeholders: YOUR_BUCKET_NAME, REGION, ACCOUNT_ID, KMS_KEY_ALIAS (e.g., lab-s3-kms), DAYS_FOR_IA, DAYS_FOR_GLACIER.

### 1. Create the bucket
```bash
export BUCKET=YOUR_BUCKET_NAME
export REGION=us-east-1

aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
  $( [ "$REGION" = "us-east-1" ] || echo "--create-bucket-configuration LocationConstraint=$REGION" )
```

### 2. Enable versioning
```bash
aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
```

(Optional: MFA Delete requires root and console operations; not covered here.)

### 3. Create a KMS key (for SSE-KMS) and grant usage to S3
```bash
# create CMK
aws kms create-key --description "KMS for $BUCKET" --query KeyMetadata.KeyId --output text
# create alias (replace returned KeyId as KEY_ID)
aws kms create-alias --alias-name "alias/lab-s3-kms" --target-key-id KEY_ID
# allow S3 to use the key (example key policy minimal snippet)
cat > key-policy.json <<'EOF'
{
  "Version":"2012-10-17",
  "Statement":[
    {
      "Sid":"Allow S3 Use",
      "Effect":"Allow",
      "Principal": { "Service": "s3.amazonaws.com" },
      "Action":[ "kms:Encrypt","kms:Decrypt","kms:GenerateDataKey","kms:ReEncrypt*" ],
      "Resource":"*"
    }
  ]
}
EOF

aws kms put-key-policy --key-id KEY_ID --policy-name default --policy file://key-policy.json
```

### 4. Set default bucket encryption (SSE-KMS example)
```bash
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration '{
  "Rules":[
    {
      "ApplyServerSideEncryptionByDefault":{
        "SSEAlgorithm":"aws:kms",
        "KMSMasterKeyID":"arn:aws:kms:REGION:ACCOUNT_ID:key/KEY_ID"
      }
    }
  ]
}'
```

(For SSE-S3 use "SSEAlgorithm":"AES256".)

### 5. Enforce HTTPS and encrypted uploads with a bucket policy
```bash
cat > bucket-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyHttp",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [ "arn:aws:s3:::$BUCKET", "arn:aws:s3:::$BUCKET/*" ],
      "Condition": { "Bool": { "aws:SecureTransport": "false" } }
    },
    {
      "Sid": "RequireSSE",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::$BUCKET/*",
      "Condition": {
        "StringNotEquals": { "s3:x-amz-server-side-encryption": "aws:kms" }
      }
    }
  ]
}
EOF

aws s3api put-bucket-policy --bucket "$BUCKET" --policy file://bucket-policy.json
```

### 6. Add lifecycle configuration (transition + expiration)
Example: transition to STANDARD_IA after 30 days, GLACIER after 90 days, expire current versions after 365 days, noncurrent versions after 90 days.

```bash
cat > lifecycle.json <<'EOF'
{
  "Rules": [
    {
      "ID": "TransitionToIAAndGlacier",
      "Status": "Enabled",
      "Filter": { "Prefix": "" },
      "Transitions": [
        { "Days": 30, "StorageClass": "STANDARD_IA" },
        { "Days": 90, "StorageClass": "GLACIER" }
      ],
      "Expiration": { "Days": 365 },
      "NoncurrentVersionTransitions": [
        { "NoncurrentDays": 30, "StorageClass": "STANDARD_IA" },
        { "NoncurrentDays": 90, "StorageClass": "GLACIER" }
      ],
      "NoncurrentVersionExpiration": { "NoncurrentDays": 180 }
    }
  ]
}
EOF

aws s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" --lifecycle-configuration file://lifecycle.json
```

Notes:
- Use GLACIER or DEEP_ARCHIVE storage classes depending on retrieval needs; GLACIER retrieval has cost and delay implications.
- For AWS regions with different class names, consult docs.

### 7. Test versioning and encryption
```bash
# upload object v1
aws s3 cp README.md s3://$BUCKET/README.md
# upload v2
aws s3 cp README.md s3://$BUCKET/README.md --metadata comment="v2"
# list versions
aws s3api list-object-versions --bucket "$BUCKET" --prefix README.md
# check encryption metadata
aws s3api head-object --bucket "$BUCKET" --key README.md --query '[ServerSideEncryption, SSEKMSKeyId]' --output text
```

### 8. Observe lifecycle behavior
- Lifecycle transitions and expirations are asynchronous (can take up to 24+ hours).
- Use S3 Storage Lens / Inventory or S3 analytics to validate transitions.
- Check object storage class with head-object and list-objects-v2.

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
# Remove lifecycle, policy, and encryption, then empty and delete bucket
aws s3api delete-bucket-lifecycle --bucket "$BUCKET" || true
aws s3api delete-bucket-policy --bucket "$BUCKET" || true
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration '{}' || true

# To delete bucket with versions, remove versions first:
aws s3api list-object-versions --bucket "$BUCKET" --query 'Versions[].{Key:Key,VersionId:VersionId}' --output json |
  jq -c '.[]' | while read v; do
    k=$(echo $v | jq -r .Key)
    vid=$(echo $v | jq -r .VersionId)
    aws s3api delete-object --bucket "$BUCKET" --key "$k" --version-id "$vid"
  done

# delete delete markers
aws s3api list-object-versions --bucket "$BUCKET" --query 'DeleteMarkers[].{Key:Key,VersionId:VersionId}' --output json |
  jq -c '.[]' | while read v; do
    k=$(echo $v | jq -r .Key)
    vid=$(echo $v | jq -r .VersionId)
    aws s3api delete-object --bucket "$BUCKET" --key "$k" --version-id "$vid"
  done

aws s3api delete-bucket --bucket "$BUCKET"
# Optionally delete CMK (careful: requires disabling and policy updates)
```

## Summary
This lab demonstrates S3 versioning, encryption with SSE-KMS/SSE-S3, lifecycle policies to reduce storage costs, and policy controls to enforce secure uploads. Use lifecycle rules and encryption to meet retention, compliance, and cost goals.
