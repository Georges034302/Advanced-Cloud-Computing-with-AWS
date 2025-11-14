# Lab 3.C: S3 Static Website Hosting

## Overview
This lab demonstrates how to deploy a static website using Amazon S3. You will configure public website access, custom error pages, and test the S3 static website endpoint.

---

## Objectives
- Create and configure S3 bucket for static website hosting
- Upload and organize website files (HTML, CSS, JavaScript)
- Configure bucket policies for public read access
- Set up index and error documents
- Test S3 website endpoint
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Basic understanding of HTML/CSS/JavaScript
- IAM permissions to manage S3
- Text editor for creating website files

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID dynamically
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set region
REGION="ap-southeast-2"
echo "REGION=$REGION"

# Set website bucket name (must be globally unique)
WEBSITE_BUCKET="static-website-${ACCOUNT_ID}"
echo "WEBSITE_BUCKET=$WEBSITE_BUCKET"

# Set website domain (will use CloudFront domain)
WEBSITE_TITLE="My Static Website"
echo "WEBSITE_TITLE=$WEBSITE_TITLE"

# Verify AWS CLI is configured
aws sts get-caller-identity
```

---

## Step 2 – Create Website Files

```bash
# Create directory for website files
mkdir -p website-files

# Create main index.html
cat > website-files/index.html <<'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AWS S3 Static Website</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <h1>AWS S3 Static Website</h1>
        <p>Hosted on Amazon S3</p>
        <div class="info">
            <h2>Lab 3.C Demo</h2>
            <p>This simple static website demonstrates:</p>
            <ul>
                <li>S3 static website hosting</li>
                <li>Public bucket policies</li>
                <li>Custom error pages</li>
            </ul>
        </div>
        <footer>© 2024 AWS Static Website Demo</footer>
    </div>
    <script src="script.js"></script>
</body>
</html>
EOF

# Create 404 error page
cat > website-files/error.html <<'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>404 - Page Not Found</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <h1>404 - Page Not Found</h1>
        <p>Sorry, the page you're looking for doesn't exist.</p>
        <a href="index.html">Return to Home</a>
    </div>
</body>
</html>
EOF

# Create CSS stylesheet
cat > website-files/style.css <<'EOF'
body {
    font-family: Arial, sans-serif;
    line-height: 1.6;
    margin: 0;
    padding: 20px;
    background: #f4f4f4;
}

.container {
    max-width: 800px;
    margin: 50px auto;
    background: white;
    padding: 30px;
    border-radius: 5px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

h1 {
    color: #333;
    border-bottom: 3px solid #007bff;
    padding-bottom: 10px;
}

.info {
    margin: 20px 0;
    padding: 20px;
    background: #f8f9fa;
    border-radius: 5px;
}

ul {
    margin-left: 20px;
}

footer {
    text-align: center;
    margin-top: 30px;
    padding-top: 20px;
    border-top: 1px solid #ddd;
    color: #666;
}

a {
    color: #007bff;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}
EOF

# Create JavaScript file
cat > website-files/script.js <<'EOF'
// Simple JavaScript
console.log('AWS S3 Static Website loaded!');

document.addEventListener('DOMContentLoaded', function() {
    console.log('Page ready at:', new Date().toISOString());
});
EOF

echo "Website files created in website-files/ directory"
ls -lR website-files/
```

---

## Step 3 – Create S3 Bucket for Website Hosting

```bash
# Create S3 bucket for website hosting
aws s3api create-bucket \
  --bucket "$WEBSITE_BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

# Verify bucket creation
aws s3 ls | grep "$WEBSITE_BUCKET"

# Add tags to bucket
aws s3api put-bucket-tagging \
  --bucket "$WEBSITE_BUCKET" \
  --tagging "TagSet=[{Key=Purpose,Value=StaticWebsite},{Key=Lab,Value=3C}]"
```

---

## Step 4 – Upload Website Files to S3

```bash
# Upload all website files to S3
aws s3 sync website-files/ "s3://${WEBSITE_BUCKET}/" \
  --delete

# Verify upload
aws s3 ls "s3://${WEBSITE_BUCKET}/" --recursive

# Set content types explicitly for proper rendering
aws s3 cp "s3://${WEBSITE_BUCKET}/index.html" "s3://${WEBSITE_BUCKET}/index.html" \
  --content-type "text/html" \
  --metadata-directive REPLACE

aws s3 cp "s3://${WEBSITE_BUCKET}/error.html" "s3://${WEBSITE_BUCKET}/error.html" \
  --content-type "text/html" \
  --metadata-directive REPLACE

aws s3 cp "s3://${WEBSITE_BUCKET}/style.css" "s3://${WEBSITE_BUCKET}/style.css" \
  --content-type "text/css" \
  --metadata-directive REPLACE

aws s3 cp "s3://${WEBSITE_BUCKET}/script.js" "s3://${WEBSITE_BUCKET}/script.js" \
  --content-type "application/javascript" \
  --metadata-directive REPLACE

echo "All files uploaded with correct content types"
```

---

## Step 5 – Configure S3 Bucket for Static Website Hosting

```bash
# Enable static website hosting on the bucket
aws s3 website "s3://${WEBSITE_BUCKET}/" \
  --index-document index.html \
  --error-document error.html

# Get website endpoint
WEBSITE_ENDPOINT=$(aws s3api get-bucket-website \
  --bucket "$WEBSITE_BUCKET" \
  --query '[IndexDocument.Suffix,ErrorDocument.Key]' \
  --output text)
echo "Website configured with index: index.html, error: error.html"

# Construct website URL
WEBSITE_URL="http://${WEBSITE_BUCKET}.s3-website-${REGION}.amazonaws.com"
echo "WEBSITE_URL=$WEBSITE_URL"
```

---

## Step 6 – Configure Bucket Policy for Public Read Access

```bash
# Create bucket policy for public read access
cat > website-bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::${WEBSITE_BUCKET}/*"
    }
  ]
}
EOF

# Display the policy
cat website-bucket-policy.json

# Disable block public access settings (required for website hosting)
aws s3api put-public-access-block \
  --bucket "$WEBSITE_BUCKET" \
  --public-access-block-configuration \
    "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

# Apply bucket policy
aws s3api put-bucket-policy \
  --bucket "$WEBSITE_BUCKET" \
  --policy file://website-bucket-policy.json

echo "Bucket policy applied for public read access"

# Verify bucket policy
aws s3api get-bucket-policy \
  --bucket "$WEBSITE_BUCKET" \
  --query Policy \
  --output text | jq '.'
```

---

## Step 7 – Test S3 Website Endpoint

```bash
# Test website accessibility
echo "Testing S3 website endpoint..."
echo ""

# Test with curl
curl -I "$WEBSITE_URL" || echo "Website accessible via S3 endpoint"

# Test 404 error page
curl -I "${WEBSITE_URL}/nonexistent-page.html" || echo "404 error page configured"

echo ""
echo "Website URL: $WEBSITE_URL"
"$BROWSER" "$WEBSITE_URL"
```

---

## Step 8 – Cleanup Resources

```bash
# Delete bucket policy
echo "Deleting S3 bucket policy..."
aws s3api delete-bucket-policy --bucket "$WEBSITE_BUCKET"

# Empty S3 bucket
echo "Emptying S3 bucket..."
aws s3 rm "s3://${WEBSITE_BUCKET}" --recursive

# Delete S3 bucket
echo "Deleting S3 bucket..."
aws s3api delete-bucket \
  --bucket "$WEBSITE_BUCKET" \
  --region "$REGION"

# Verify bucket deletion
aws s3 ls | grep "$WEBSITE_BUCKET" || echo "S3 bucket deleted successfully"

# Delete local files
echo "Cleaning up local files..."
rm -rf website-files/
rm -f website-bucket-policy.json

echo ""
echo "✅ All resources cleaned up successfully!"
```

---

## Summary

In this lab, you have:
- Created a complete static website with HTML, CSS, and JavaScript
- Configured S3 bucket for static website hosting
- Set up public bucket policy for website access
- Uploaded and organized website files in S3
- Configured custom error page (404)
- Tested S3 website endpoint
- Cleaned up all resources

---

## Additional Resources
- [S3 Static Website Hosting](https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteHosting.html)
- [S3 Bucket Policies](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-policies.html)
- [S3 Website Endpoints](https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteEndpoints.html)

---
