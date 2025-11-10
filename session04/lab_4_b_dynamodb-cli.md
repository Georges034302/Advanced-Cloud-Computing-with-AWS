# Lab 4.A: Amazon S3 Fundamentals and Storage Management

## Overview
This lab introduces Amazon Simple Storage Service (S3), AWS's object storage service. You'll learn how to create and manage S3 buckets, upload and organize objects, configure access permissions, and implement versioning and lifecycle policies. S3 is fundamental to many AWS architectures for data storage, backup, and static website hosting.

## Objectives
- Create and configure S3 buckets
- Upload, download, and manage objects
- Organize data with folders and prefixes
- Configure bucket and object permissions
- Enable versioning for data protection
- Implement lifecycle policies for cost optimization
- Host a static website on S3

## Requirements
- AWS account with S3 permissions
- AWS CLI installed and configured (optional)
- Sample files for upload (images, documents)
- Basic understanding of storage concepts
- Web browser for testing static website

## Steps

### Step 1: Create an S3 Bucket
1. Navigate to S3 console
2. Click "Create bucket"
3. Configure:
   - Bucket name: `my-lab-bucket-[unique-id]` (must be globally unique)
   - AWS Region: Choose your preferred region
   - Object Ownership: ACLs disabled (recommended)
   - Block Public Access: Keep all settings enabled (for now)
   - Bucket Versioning: Disabled (will enable later)
   - Default encryption: Enable with SSE-S3
   - Tags: Add `Environment=Lab`
4. Create bucket

### Step 2: Upload Objects to S3
1. Select your bucket
2. Click "Upload"
3. Add files:
   - Click "Add files" and select multiple files
   - Or drag and drop files
4. Configure properties (keep defaults):
   - Storage class: Standard
   - Server-side encryption: Default
5. Upload files
6. Verify upload in bucket contents view

### Step 3: Organize with Folders and Prefixes
1. Create folder structure:
   - Click "Create folder"
   - Name: `documents/`
   - Create another: `images/`
   - Create another: `backups/`
2. Move/upload files to appropriate folders:
   - Upload documents to `documents/`
   - Upload images to `images/`
3. Note: S3 doesn't have true folders, uses prefixes

### Step 4: Configure Bucket Permissions
1. **Bucket Policy - Public Read Access:**
   - Select bucket → Permissions tab
   - Edit Block Public Access settings
   - Uncheck "Block all public access"
   - Confirm changes
   - Add bucket policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "PublicReadGetObject",
         "Effect": "Allow",
         "Principal": "*",
         "Action": "s3:GetObject",
         "Resource": "arn:aws:s3:::my-lab-bucket-[unique-id]/images/*"
       }
     ]
   }
   ```
   - This makes only objects in `images/` public

2. **Pre-signed URLs for Temporary Access:**
   - Select an object in `documents/`
   - Actions → Share with a presigned URL
   - Expiration: 5 minutes
   - Generate URL
   - Test URL in browser

### Step 5: Enable and Test Versioning
1. Select bucket → Properties
2. Find "Bucket Versioning" → Edit
3. Enable versioning
4. Save changes
5. Test versioning:
   - Create a text file locally: `test.txt` with content "Version 1"
   - Upload to bucket
   - Modify file locally: change content to "Version 2"
   - Upload again with same name
   - Modify once more: "Version 3" and upload
6. View all versions:
   - Toggle "Show versions" in bucket view
   - Observe multiple versions of `test.txt`
   - Download different versions to verify content

### Step 6: Configure Lifecycle Policies
1. Select bucket → Management tab
2. Create lifecycle rule:
   - Name: `optimize-storage-costs`
   - Choose scope: Apply to all objects
3. Lifecycle rule actions:
   - Transition current versions:
     - Days after object creation: 30
     - Storage class: Standard-IA
   - Transition current versions:
     - Days after object creation: 90
     - Storage class: Glacier Flexible Retrieval
   - Delete previous versions:
     - Days after becoming noncurrent: 30
4. Create rule
5. Review rule in Management tab

### Step 7: Host a Static Website
1. Create simple HTML files locally:

**index.html:**
```html
<!DOCTYPE html>
<html>
<head><title>My S3 Website</title></head>
<body>
    <h1>Welcome to My S3 Static Website</h1>
    <p>This site is hosted on Amazon S3!</p>
    <a href="page2.html">Go to Page 2</a>
</body>
</html>
```

**error.html:**
```html
<!DOCTYPE html>
<html>
<head><title>Error</title></head>
<body><h1>404 - Page Not Found</h1></body>
</html>
```

2. Upload both files to bucket root
3. Configure static website hosting:
   - Properties → Static website hosting → Edit
   - Enable static website hosting
   - Hosting type: Host a static website
   - Index document: `index.html`
   - Error document: `error.html`
   - Save changes
4. Note the website endpoint URL
5. Update bucket policy for website access:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "PublicReadGetObject",
         "Effect": "Allow",
         "Principal": "*",
         "Action": "s3:GetObject",
         "Resource": "arn:aws:s3:::my-lab-bucket-[unique-id]/*"
       }
     ]
   }
   ```
6. Access website using endpoint URL

### Step 8: Use AWS CLI (Optional)
1. Configure AWS CLI if not already:
   ```bash
   aws configure
   ```
2. List buckets:
   ```bash
   aws s3 ls
   ```
3. Upload file:
   ```bash
   aws s3 cp myfile.txt s3://my-lab-bucket-[unique-id]/
   ```
4. Sync directory:
   ```bash
   aws s3 sync ./local-folder s3://my-lab-bucket-[unique-id]/synced/
   ```
5. Download file:
   ```bash
   aws s3 cp s3://my-lab-bucket-[unique-id]/myfile.txt ./
   ```

## Validation
- [ ] S3 bucket created with unique name
- [ ] Objects uploaded successfully
- [ ] Folder structure created and organized
- [ ] Bucket policy configured for public access
- [ ] Versioning enabled and tested
- [ ] Lifecycle policy created and active
- [ ] Static website hosted and accessible
- [ ] Pre-signed URL generated and tested
- [ ] AWS CLI commands executed successfully (if applicable)

## Cleanup
1. Delete all objects in bucket:
   - Enable "Show versions" toggle
   - Select all objects and versions
   - Delete permanently
2. Disable static website hosting
3. Delete lifecycle rules
4. Empty bucket completely
5. Delete bucket
6. Verify bucket is removed from S3 console

## Summary
In this lab, you mastered Amazon S3 fundamentals including bucket creation, object management, access control, versioning, and lifecycle policies. You also learned how to host static websites on S3, a cost-effective solution for web content. S3's durability, scalability, and integration with other AWS services make it essential for modern cloud applications.

**Key Takeaways:**
- S3 bucket names must be globally unique
- S3 provides 11 nines (99.999999999%) of durability
- Versioning protects against accidental deletion and overwrites
- Lifecycle policies automate storage class transitions for cost savings
- Static website hosting is simple and cost-effective on S3
- Bucket policies control access at bucket and object level
- Pre-signed URLs provide temporary access without credentials
- Different storage classes optimize costs for different access patterns
- Always enable encryption for sensitive data
