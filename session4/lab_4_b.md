# Lab 4.B: S3 Advanced Features - Replication, Encryption, and CloudFront

## Overview
This lab explores advanced S3 features including Cross-Region Replication (CRR), server-side encryption options, S3 Transfer Acceleration, and CloudFront integration for global content delivery. These features are critical for building resilient, secure, and high-performance applications with global reach.

## Objectives
- Configure S3 Cross-Region Replication (CRR)
- Implement different encryption methods (SSE-S3, SSE-KMS, SSE-C)
- Enable S3 Transfer Acceleration for faster uploads
- Integrate S3 with CloudFront CDN
- Configure CloudFront distributions for global delivery
- Implement S3 Object Lock for compliance
- Use S3 Analytics and Insights

## Requirements
- Completed Lab 4.A or equivalent S3 knowledge
- AWS account with S3 and CloudFront permissions
- Access to multiple AWS regions
- Understanding of encryption concepts
- AWS KMS knowledge (helpful)

## Steps

### Step 1: Create Source and Destination Buckets for Replication
1. **Create source bucket:**
   - Name: `source-bucket-[unique-id]`
   - Region: us-east-1 (or your primary region)
   - Enable versioning (required for replication)
   - Enable default encryption

2. **Create destination bucket:**
   - Name: `destination-bucket-[unique-id]`
   - Region: us-west-2 (different region)
   - Enable versioning
   - Enable default encryption

### Step 2: Configure Cross-Region Replication
1. Navigate to source bucket → Management
2. Create replication rule:
   - Name: `cross-region-replication-rule`
   - Status: Enabled
   - Priority: 1
3. Source configuration:
   - Rule scope: Apply to all objects
4. Destination:
   - Bucket: `destination-bucket-[unique-id]`
   - Region: us-west-2
   - IAM role: Create new role (AWS will create automatically)
5. Additional replication options:
   - Replication Time Control (RTC): Optional (enables 15-min SLA)
   - Replicate delete markers: Enable
   - Replica modification sync: Enable
6. Create rule

### Step 3: Test Cross-Region Replication
1. Upload files to source bucket:
   ```bash
   echo "Test CRR" > test-crr.txt
   aws s3 cp test-crr.txt s3://source-bucket-[unique-id]/
   ```
2. Wait 1-2 minutes
3. Check destination bucket:
   ```bash
   aws s3 ls s3://destination-bucket-[unique-id]/
   ```
4. Verify object was replicated
5. Check replication metrics in source bucket

### Step 4: Configure Server-Side Encryption with KMS
1. Navigate to AWS KMS service
2. Create customer managed key:
   - Key type: Symmetric
   - Key usage: Encrypt and decrypt
   - Alias: `s3-encryption-key`
   - Key administrators: Your IAM user
   - Key users: Your IAM user
3. Create bucket with KMS encryption:
   - Name: `encrypted-bucket-[unique-id]`
   - Default encryption: AWS-KMS
   - KMS key: `s3-encryption-key`
4. Upload object to test encryption:
   - Upload file
   - Check object properties → Server-side encryption settings
   - Verify KMS key is used

### Step 5: Test Different Encryption Methods
1. **SSE-S3 (default):**
   ```bash
   aws s3 cp file.txt s3://encrypted-bucket-[unique-id]/ \
     --server-side-encryption AES256
   ```

2. **SSE-KMS:**
   ```bash
   aws s3 cp file.txt s3://encrypted-bucket-[unique-id]/ \
     --server-side-encryption aws:kms \
     --ssekms-key-id arn:aws:kms:region:account:key/key-id
   ```

3. View encryption metadata:
   ```bash
   aws s3api head-object \
     --bucket encrypted-bucket-[unique-id] \
     --key file.txt
   ```

### Step 6: Enable S3 Transfer Acceleration
1. Select source bucket → Properties
2. Find "Transfer acceleration" → Edit
3. Enable Transfer Acceleration
4. Note the accelerated endpoint:
   - `source-bucket-[unique-id].s3-accelerate.amazonaws.com`
5. Test speed comparison:
   - Visit: https://s3-accelerate-speedtest.s3-accelerate.amazonaws.com/
   - Compare standard vs accelerated transfer speeds
6. Upload using accelerated endpoint:
   ```bash
   aws s3 cp large-file.zip s3://source-bucket-[unique-id]/ \
     --endpoint-url https://s3-accelerate.amazonaws.com
   ```

### Step 7: Create CloudFront Distribution
1. Navigate to CloudFront service
2. Create distribution:
   - Origin domain: Select your S3 bucket
   - Origin access: Origin access control (OAC)
   - Create new OAC
3. Default cache behavior:
   - Viewer protocol policy: Redirect HTTP to HTTPS
   - Allowed HTTP methods: GET, HEAD
   - Cache policy: CachingOptimized
4. Settings:
   - Price class: Use all edge locations (or select region)
   - Alternate domain name (CNAME): Optional
   - SSL Certificate: Default CloudFront certificate
5. Create distribution
6. Wait for deployment (Status: Enabled, State: Deployed)

### Step 8: Update S3 Bucket Policy for CloudFront OAC
1. CloudFront will provide policy statement
2. Navigate to S3 bucket → Permissions
3. Edit bucket policy to add CloudFront access:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "AllowCloudFrontServicePrincipal",
         "Effect": "Allow",
         "Principal": {
           "Service": "cloudfront.amazonaws.com"
         },
         "Action": "s3:GetObject",
         "Resource": "arn:aws:s3:::source-bucket-[unique-id]/*",
         "Condition": {
           "StringEquals": {
             "AWS:SourceArn": "arn:aws:cloudfront::account:distribution/distribution-id"
           }
         }
       }
     ]
   }
   ```
4. Block direct S3 public access (CloudFront only)

### Step 9: Test CloudFront Distribution
1. Copy CloudFront domain name (e.g., `d123456.cloudfront.net`)
2. Upload test file to S3 bucket:
   - Create `test.html` file
   - Upload to bucket
3. Access via CloudFront:
   - `https://d123456.cloudfront.net/test.html`
4. Monitor CloudFront cache behavior:
   - First request: Cache miss (retrieves from S3)
   - Second request: Cache hit (served from edge)
5. View CloudFront metrics in console

### Step 10: Configure S3 Object Lock (Compliance Mode)
1. Create new bucket with Object Lock:
   - Name: `compliance-bucket-[unique-id]`
   - Enable Object Lock during creation
   - Note: Cannot be enabled after creation
2. Configure default retention:
   - Mode: Compliance
   - Duration: 30 days
3. Upload object with retention:
   ```bash
   aws s3api put-object \
     --bucket compliance-bucket-[unique-id] \
     --key protected.txt \
     --body file.txt \
     --object-lock-mode COMPLIANCE \
     --object-lock-retain-until-date "2024-12-31T00:00:00Z"
   ```
4. Attempt to delete (should fail)
5. Verify object cannot be deleted before retention period

### Step 11: Enable S3 Analytics
1. Select your main bucket → Metrics
2. Create analytics configuration:
   - Name: `storage-analytics`
   - Scope: All objects (or use filters)
   - Export destination: Optional (can export to another bucket)
3. Wait 24-48 hours for data collection
4. Review storage class analysis:
   - Access patterns
   - Recommendations for lifecycle policies
5. Use insights to optimize storage costs

## Validation
- [ ] Cross-Region Replication configured and working
- [ ] Objects replicate from source to destination bucket
- [ ] KMS encryption configured and tested
- [ ] Different encryption methods (SSE-S3, SSE-KMS) working
- [ ] Transfer Acceleration enabled and tested
- [ ] CloudFront distribution created and deployed
- [ ] Content accessible via CloudFront domain
- [ ] S3 bucket policy updated for CloudFront OAC
- [ ] Object Lock configured and retention enforced
- [ ] S3 Analytics configuration created

## Cleanup
1. Delete CloudFront distribution:
   - Disable distribution first
   - Wait for status change
   - Delete distribution
2. Delete replication rule from source bucket
3. Delete all objects from all buckets (including versions)
4. Delete buckets:
   - `source-bucket-[unique-id]`
   - `destination-bucket-[unique-id]`
   - `encrypted-bucket-[unique-id]`
   - `compliance-bucket-[unique-id]`
5. Delete KMS key:
   - Schedule key deletion (7-30 day waiting period)
6. Verify all resources removed

## Summary
In this lab, you explored advanced S3 features that enhance security, performance, and compliance. You configured Cross-Region Replication for disaster recovery, implemented encryption with KMS, accelerated transfers with Transfer Acceleration, and integrated CloudFront for global content delivery. These capabilities enable enterprise-grade storage solutions on AWS.

**Key Takeaways:**
- Cross-Region Replication requires versioning on both buckets
- KMS encryption provides additional audit and access control
- Transfer Acceleration uses CloudFront edge locations for faster uploads
- CloudFront OAC is the recommended method for S3 integration
- Object Lock provides WORM (Write Once Read Many) functionality
- S3 Analytics helps optimize storage class selection
- CloudFront caching reduces S3 request costs and improves performance
- Encryption in transit (HTTPS) and at rest should always be enabled
- Replication does not replicate existing objects by default
