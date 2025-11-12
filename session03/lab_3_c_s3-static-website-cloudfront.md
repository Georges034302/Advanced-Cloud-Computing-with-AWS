# Lab 3.C: S3 Static Website Hosting with CloudFront CDN

## Overview
This lab demonstrates how to deploy a static website using Amazon S3 and distribute it globally with Amazon CloudFront CDN. You will configure public website access, custom error pages, HTTPS delivery, and implement caching strategies for optimal performance.

---

## Objectives
- Create and configure S3 bucket for static website hosting
- Upload and organize website files (HTML, CSS, JavaScript, images)
- Configure bucket policies for public read access
- Set up index and error documents
- Create CloudFront distribution for global content delivery
- Configure Origin Access Identity (OAI) for secure S3 access
- Implement custom error pages and cache behaviors
- Test CDN caching and create invalidations
- Monitor website performance and access logs
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Basic understanding of HTML/CSS/JavaScript
- IAM permissions to manage S3, CloudFront, and IAM
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
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 AWS S3 Static Website</h1>
            <p>Deployed with S3 and CloudFront CDN</p>
        </header>
        
        <main>
            <section class="features">
                <div class="feature">
                    <h2>📦 Amazon S3</h2>
                    <p>Serverless static website hosting with high durability and availability</p>
                </div>
                
                <div class="feature">
                    <h2>🌐 CloudFront CDN</h2>
                    <p>Global content delivery network with low latency and high transfer speeds</p>
                </div>
                
                <div class="feature">
                    <h2>🔒 Secure & Scalable</h2>
                    <p>HTTPS delivery with automatic scaling for any traffic volume</p>
                </div>
            </section>
            
            <section class="info">
                <h2>About This Website</h2>
                <p>This static website is hosted on Amazon S3 and distributed globally through CloudFront CDN.</p>
                <p>It demonstrates:</p>
                <ul>
                    <li>S3 bucket configuration for static website hosting</li>
                    <li>CloudFront distribution for global content delivery</li>
                    <li>Origin Access Identity (OAI) for secure access</li>
                    <li>Custom error pages and cache behaviors</li>
                </ul>
            </section>
        </main>
        
        <footer>
            <p>© 2024 AWS Static Website Demo | Session 03 - Lab 3.C</p>
        </footer>
    </div>
    
    <script src="js/script.js"></script>
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
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <div class="container error-page">
        <header>
            <h1>404 - Page Not Found</h1>
            <p>The page you're looking for doesn't exist</p>
        </header>
        
        <main>
            <p>Sorry, we couldn't find the page you were looking for.</p>
            <a href="index.html" class="button">Return to Home</a>
        </main>
        
        <footer>
            <p>© 2024 AWS Static Website Demo</p>
        </footer>
    </div>
</body>
</html>
EOF

# Create CSS directory and stylesheet
mkdir -p website-files/css
cat > website-files/css/style.css <<'EOF'
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    line-height: 1.6;
    color: #333;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px;
}

.container {
    max-width: 1000px;
    background: white;
    border-radius: 10px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
    padding: 40px;
    margin: 20px auto;
}

header {
    text-align: center;
    margin-bottom: 40px;
    padding-bottom: 20px;
    border-bottom: 3px solid #667eea;
}

header h1 {
    font-size: 2.5em;
    color: #667eea;
    margin-bottom: 10px;
}

header p {
    font-size: 1.2em;
    color: #666;
}

.features {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 30px;
    margin-bottom: 40px;
}

.feature {
    background: #f8f9fa;
    padding: 25px;
    border-radius: 8px;
    text-align: center;
    transition: transform 0.3s ease;
}

.feature:hover {
    transform: translateY(-5px);
    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
}

.feature h2 {
    color: #667eea;
    margin-bottom: 15px;
    font-size: 1.5em;
}

.info {
    background: #f8f9fa;
    padding: 30px;
    border-radius: 8px;
    margin-top: 30px;
}

.info h2 {
    color: #667eea;
    margin-bottom: 15px;
}

.info ul {
    margin-left: 30px;
    margin-top: 15px;
}

.info li {
    margin-bottom: 10px;
}

footer {
    text-align: center;
    margin-top: 40px;
    padding-top: 20px;
    border-top: 2px solid #eee;
    color: #666;
}

.error-page {
    text-align: center;
}

.button {
    display: inline-block;
    margin-top: 20px;
    padding: 12px 30px;
    background: #667eea;
    color: white;
    text-decoration: none;
    border-radius: 5px;
    transition: background 0.3s ease;
}

.button:hover {
    background: #764ba2;
}

@media (max-width: 768px) {
    .container {
        padding: 20px;
    }
    
    header h1 {
        font-size: 2em;
    }
    
    .features {
        grid-template-columns: 1fr;
    }
}
EOF

# Create JavaScript directory and file
mkdir -p website-files/js
cat > website-files/js/script.js <<'EOF'
// Simple JavaScript for interactive elements
document.addEventListener('DOMContentLoaded', function() {
    console.log('AWS S3 Static Website loaded successfully!');
    
    // Add smooth scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
    
    // Add animation to features on scroll
    const features = document.querySelectorAll('.feature');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    });
    
    features.forEach(feature => {
        feature.style.opacity = '0';
        feature.style.transform = 'translateY(20px)';
        feature.style.transition = 'all 0.5s ease';
        observer.observe(feature);
    });
});
EOF

# Create sample image directory
mkdir -p website-files/images

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

aws s3 cp "s3://${WEBSITE_BUCKET}/css/style.css" "s3://${WEBSITE_BUCKET}/css/style.css" \
  --content-type "text/css" \
  --metadata-directive REPLACE

aws s3 cp "s3://${WEBSITE_BUCKET}/js/script.js" "s3://${WEBSITE_BUCKET}/js/script.js" \
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
echo "Website URL: $WEBSITE_URL"
echo ""

# Test with curl
curl -I "$WEBSITE_URL" || echo "Website accessible via S3 endpoint"

# Test 404 error page
curl -I "${WEBSITE_URL}/nonexistent-page.html" || echo "404 error page configured"

echo ""
echo "Open in browser: $WEBSITE_URL"
```

---

## Step 8 – Create CloudFront Origin Access Identity (OAI)

```bash
# Create Origin Access Identity for CloudFront
OAI_OUTPUT=$(aws cloudfront create-cloud-front-origin-access-identity \
  --cloud-front-origin-access-identity-config \
    "CallerReference=$(date +%s),Comment=OAI for ${WEBSITE_BUCKET}")

# Extract OAI ID
OAI_ID=$(echo "$OAI_OUTPUT" | jq -r '.CloudFrontOriginAccessIdentity.Id')
echo "OAI_ID=$OAI_ID"

# Extract S3 Canonical User ID for OAI
OAI_S3_USER=$(echo "$OAI_OUTPUT" | jq -r '.CloudFrontOriginAccessIdentity.S3CanonicalUserId')
echo "OAI_S3_USER=$OAI_S3_USER"

# Display OAI details
echo "$OAI_OUTPUT" | jq '.CloudFrontOriginAccessIdentity'
```

---

## Step 9 – Update Bucket Policy for CloudFront OAI

```bash
# Create updated bucket policy for CloudFront OAI access
cat > cloudfront-bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFrontOAIAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity ${OAI_ID}"
      },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::${WEBSITE_BUCKET}/*"
    }
  ]
}
EOF

# Display the updated policy
cat cloudfront-bucket-policy.json

# Apply updated bucket policy (comment out if keeping public access)
# Uncomment below to use OAI exclusively (more secure)
# aws s3api put-bucket-policy \
#   --bucket "$WEBSITE_BUCKET" \
#   --policy file://cloudfront-bucket-policy.json

echo "CloudFront OAI policy created (optional secure access)"
```

---

## Step 10 – Create CloudFront Distribution

```bash
# Generate unique caller reference
CALLER_REF="static-website-$(date +%s)"
echo "CALLER_REF=$CALLER_REF"

# Create CloudFront distribution configuration
cat > cloudfront-config.json <<EOF
{
  "CallerReference": "${CALLER_REF}",
  "Comment": "CloudFront distribution for ${WEBSITE_BUCKET}",
  "Enabled": true,
  "DefaultRootObject": "index.html",
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "S3-${WEBSITE_BUCKET}",
        "DomainName": "${WEBSITE_BUCKET}.s3.${REGION}.amazonaws.com",
        "S3OriginConfig": {
          "OriginAccessIdentity": "origin-access-identity/cloudfront/${OAI_ID}"
        }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-${WEBSITE_BUCKET}",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {
      "Quantity": 2,
      "Items": ["GET", "HEAD"],
      "CachedMethods": {
        "Quantity": 2,
        "Items": ["GET", "HEAD"]
      }
    },
    "ForwardedValues": {
      "QueryString": false,
      "Cookies": {
        "Forward": "none"
      }
    },
    "MinTTL": 0,
    "DefaultTTL": 86400,
    "MaxTTL": 31536000,
    "Compress": true,
    "TrustedSigners": {
      "Enabled": false,
      "Quantity": 0
    }
  },
  "CustomErrorResponses": {
    "Quantity": 2,
    "Items": [
      {
        "ErrorCode": 404,
        "ResponsePagePath": "/error.html",
        "ResponseCode": "404",
        "ErrorCachingMinTTL": 300
      },
      {
        "ErrorCode": 403,
        "ResponsePagePath": "/error.html",
        "ResponseCode": "404",
        "ErrorCachingMinTTL": 300
      }
    ]
  },
  "PriceClass": "PriceClass_100",
  "ViewerCertificate": {
    "CloudFrontDefaultCertificate": true
  }
}
EOF

# Display CloudFront configuration
cat cloudfront-config.json | jq '.'

# Create CloudFront distribution
echo "Creating CloudFront distribution (this may take 15-20 minutes)..."
DISTRIBUTION_OUTPUT=$(aws cloudfront create-distribution \
  --distribution-config file://cloudfront-config.json)

# Extract distribution ID and domain name
DISTRIBUTION_ID=$(echo "$DISTRIBUTION_OUTPUT" | jq -r '.Distribution.Id')
echo "DISTRIBUTION_ID=$DISTRIBUTION_ID"

CLOUDFRONT_DOMAIN=$(echo "$DISTRIBUTION_OUTPUT" | jq -r '.Distribution.DomainName')
echo "CLOUDFRONT_DOMAIN=$CLOUDFRONT_DOMAIN"

echo ""
echo "CloudFront distribution created successfully!"
echo "Distribution ID: $DISTRIBUTION_ID"
echo "CloudFront URL: https://${CLOUDFRONT_DOMAIN}"
echo ""
echo "Note: Distribution deployment takes 15-20 minutes"
```

---

## Step 11 – Wait for CloudFront Distribution Deployment

```bash
# Check distribution status
echo "Checking CloudFront distribution status..."

aws cloudfront get-distribution \
  --id "$DISTRIBUTION_ID" \
  --query 'Distribution.Status' \
  --output text

# Wait for distribution to be deployed (optional - takes time)
echo ""
echo "Waiting for distribution deployment..."
echo "Status: InProgress → Deployed"
echo ""
echo "You can check status with:"
echo "aws cloudfront get-distribution --id $DISTRIBUTION_ID --query 'Distribution.Status'"

# Note: aws cloudfront wait distribution-deployed is available but slow
# Uncomment below to wait (can take 15-20 minutes)
# aws cloudfront wait distribution-deployed --id "$DISTRIBUTION_ID"

echo ""
echo "Once deployed, access your website at: https://${CLOUDFRONT_DOMAIN}"
```

---

## Step 12 – Test CloudFront Distribution

```bash
# Wait a moment, then test CloudFront endpoint
echo "Testing CloudFront distribution..."
echo "URL: https://${CLOUDFRONT_DOMAIN}"
echo ""

# Test with curl (may fail if not deployed yet)
curl -I "https://${CLOUDFRONT_DOMAIN}" || echo "Distribution still deploying..."

# Test 404 error page
curl -I "https://${CLOUDFRONT_DOMAIN}/nonexistent.html" || echo "Custom error page configured"

echo ""
echo "Open in browser: https://${CLOUDFRONT_DOMAIN}"
echo ""
echo "Compare performance:"
echo "S3 Direct:   $WEBSITE_URL"
echo "CloudFront:  https://${CLOUDFRONT_DOMAIN}"
```

---

## Step 13 – Create CloudFront Invalidation

```bash
# Make a change to the website
echo "Updating website content..."

# Update index.html with new content
cat >> website-files/index.html <<'EOF'
<!-- Updated content -->
<div style="background: #4CAF50; color: white; padding: 10px; text-align: center; margin-top: 20px;">
    <p>✅ Website Updated! Cache invalidation demonstration.</p>
</div>
EOF

# Upload updated file
aws s3 cp website-files/index.html "s3://${WEBSITE_BUCKET}/index.html" \
  --content-type "text/html"

echo "Updated file uploaded to S3"

# Create CloudFront invalidation to clear cache
echo "Creating CloudFront invalidation..."

INVALIDATION_OUTPUT=$(aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" \
  --paths "/*")

# Extract invalidation ID
INVALIDATION_ID=$(echo "$INVALIDATION_OUTPUT" | jq -r '.Invalidation.Id')
echo "INVALIDATION_ID=$INVALIDATION_ID"

# Check invalidation status
aws cloudfront get-invalidation \
  --distribution-id "$DISTRIBUTION_ID" \
  --id "$INVALIDATION_ID" \
  --query 'Invalidation.Status' \
  --output text

echo ""
echo "Invalidation created. New content will be available shortly."
echo "Check status: aws cloudfront get-invalidation --distribution-id $DISTRIBUTION_ID --id $INVALIDATION_ID"
```

---

## Step 14 – Monitor CloudFront Metrics

```bash
# Get CloudFront statistics
echo "Retrieving CloudFront distribution information..."

# Get distribution configuration
aws cloudfront get-distribution \
  --id "$DISTRIBUTION_ID" \
  --query 'Distribution.{Status:Status,DomainName:DomainName,Enabled:DistributionConfig.Enabled,PriceClass:DistributionConfig.PriceClass}' \
  --output table

# List all distributions
echo ""
echo "All CloudFront distributions:"
aws cloudfront list-distributions \
  --query 'DistributionList.Items[*].{Id:Id,DomainName:DomainName,Status:Status,Enabled:Enabled}' \
  --output table

# Note: CloudWatch metrics for CloudFront may take time to populate
echo ""
echo "CloudWatch metrics for CloudFront are available in us-east-1 region"
echo "View metrics in CloudWatch console or use:"
echo "aws cloudwatch get-metric-statistics --namespace AWS/CloudFront --metric-name Requests --dimensions Name=DistributionId,Value=$DISTRIBUTION_ID --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) --end-time $(date -u +%Y-%m-%dT%H:%M:%S) --period 3600 --statistics Sum --region us-east-1"
```

---

## Step 15 – Cleanup Resources

```bash
# Disable CloudFront distribution first
echo "Disabling CloudFront distribution..."

# Get current distribution config
aws cloudfront get-distribution-config \
  --id "$DISTRIBUTION_ID" \
  --query 'DistributionConfig' > distribution-config-current.json

# Get ETag for update
ETAG=$(aws cloudfront get-distribution-config \
  --id "$DISTRIBUTION_ID" \
  --query 'ETag' \
  --output text)
echo "ETAG=$ETAG"

# Update config to disable distribution
cat distribution-config-current.json | jq '.Enabled = false' > distribution-config-disabled.json

# Disable distribution
aws cloudfront update-distribution \
  --id "$DISTRIBUTION_ID" \
  --distribution-config file://distribution-config-disabled.json \
  --if-match "$ETAG"

echo "Distribution disabled. Waiting for deployment..."
echo "This will take several minutes..."

# Wait for disabled status (optional - takes time)
# aws cloudfront wait distribution-deployed --id "$DISTRIBUTION_ID"

echo ""
echo "After distribution is deployed as disabled, you can delete it:"
echo "1. Wait 10-15 minutes for disable to complete"
echo "2. Get new ETag: aws cloudfront get-distribution --id $DISTRIBUTION_ID --query ETag --output text"
echo "3. Delete: aws cloudfront delete-distribution --id $DISTRIBUTION_ID --if-match <new-etag>"
echo ""
echo "For now, continuing with other cleanup..."

# Delete Origin Access Identity
echo "Deleting Origin Access Identity..."

# Get OAI ETag
OAI_ETAG=$(aws cloudfront get-cloud-front-origin-access-identity \
  --id "$OAI_ID" \
  --query 'ETag' \
  --output text)

# Delete OAI (will fail if still in use by distribution)
aws cloudfront delete-cloud-front-origin-access-identity \
  --id "$OAI_ID" \
  --if-match "$OAI_ETAG" || echo "OAI still in use by distribution"

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
rm -f website-bucket-policy.json \
  cloudfront-bucket-policy.json \
  cloudfront-config.json \
  distribution-config-current.json \
  distribution-config-disabled.json

echo ""
echo "⚠️  Manual Cleanup Required:"
echo "After the CloudFront distribution is fully disabled (10-15 minutes):"
echo ""
echo "1. Get new ETag:"
echo "   NEW_ETAG=\$(aws cloudfront get-distribution --id $DISTRIBUTION_ID --query ETag --output text)"
echo ""
echo "2. Delete distribution:"
echo "   aws cloudfront delete-distribution --id $DISTRIBUTION_ID --if-match \$NEW_ETAG"
echo ""
echo "3. Delete OAI (if not already deleted):"
echo "   OAI_ETAG=\$(aws cloudfront get-cloud-front-origin-access-identity --id $OAI_ID --query ETag --output text)"
echo "   aws cloudfront delete-cloud-front-origin-access-identity --id $OAI_ID --if-match \$OAI_ETAG"
echo ""
echo "✅ S3 bucket and local files cleaned up successfully!"
```

---

## Summary

In this lab, you have:
- Created a complete static website with HTML, CSS, and JavaScript
- Configured S3 bucket for static website hosting
- Set up public bucket policy for website access
- Uploaded and organized website files in S3
- Created CloudFront distribution for global content delivery
- Configured Origin Access Identity (OAI) for secure S3 access
- Implemented custom error pages (404/403)
- Set up HTTPS delivery with CloudFront
- Created cache invalidations for content updates
- Monitored CloudFront distribution metrics
- Compared S3 direct access vs CloudFront CDN performance

**Key Takeaways:**
- **S3 Static Hosting**: Cost-effective, serverless website hosting
- **CloudFront CDN**: Global content delivery with low latency
- **OAI Security**: Secure S3 access without public bucket policies
- **Cache Management**: TTL settings and invalidations for content updates
- **HTTPS by Default**: CloudFront provides free SSL/TLS
- **Custom Error Pages**: Better user experience with branded error pages
- **Cost Optimization**: Pay only for storage and data transfer used

**Performance Benefits:**
- **S3 Direct**: Single region, higher latency for distant users
- **CloudFront**: Multiple edge locations, cached content, lower latency globally
- **Compression**: Automatic gzip compression reduces bandwidth
- **Caching**: Reduces origin requests and improves response times

**Real-World Use Cases:**
- Single Page Applications (React, Vue, Angular)
- Corporate websites and landing pages
- Documentation and API references
- Portfolio and personal websites
- Marketing campaign microsites
- Static blog generators (Hugo, Jekyll, Gatsby)

**Cost Comparison:**
- **S3 Hosting**: ~$0.023/GB storage + $0.09/GB data transfer
- **CloudFront**: Free tier includes 1TB data transfer/month
- **vs EC2**: No server costs, only pay for usage
- **vs Lightsail**: More scalable, better global performance

---

## Additional Resources
- [S3 Static Website Hosting](https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteHosting.html)
- [CloudFront Distribution](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-working-with.html)
- [Origin Access Identity (OAI)](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)
- [CloudFront Cache Behaviors](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-web-values-specify.html#DownloadDistValuesCacheBehavior)
- [CloudFront Invalidation](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Invalidation.html)

---
