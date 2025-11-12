# Lab 1.D: Deploy a Python Web App on AWS Elastic Beanstalk
<img width="1536" height="534" alt="IMG" src="https://github.com/user-attachments/assets/4efda192-be84-4d3c-8b56-4c7618e143cc" />

## Overview
This lab demonstrates how to deploy a Python Flask web application on **AWS Elastic Beanstalk**. Elastic Beanstalk automatically handles provisioning, load balancing, scaling, and monitoring, allowing you to focus on your application code.

---

## Objectives
- Create a Python web app using Flask
- Deploy it to Elastic Beanstalk using the EB CLI
- Validate the application through the environment URL
- Clean up resources to avoid costs

---

## Architecture Diagram (Conceptual)
```
Internet → Elastic Beanstalk Environment → EC2 Instance (Flask App)
```

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM user with permissions for Elastic Beanstalk, EC2, and S3
- Python 3.8+ installed locally
- Elastic Beanstalk CLI (`eb`) installed

---

## Step 1 – Verify and Install EB CLI

```bash
# Check if EB CLI is installed
if command -v eb &> /dev/null; then
    echo "EB CLI is installed"
    eb --version
else
    echo "EB CLI not found. Installing..."
    # Install EB CLI using pip
    pip3 install awsebcli --upgrade --user
fi

# Verify installation
eb --version
```

---

## Step 2 – Create Project Directory and Files

```bash
# Create project directory
mkdir flask-ebs-app

# Navigate to project directory
cd flask-ebs-app

# Create application.py (Elastic Beanstalk looks for this file)
cat > application.py <<'EOF'
from flask import Flask
import os

# Elastic Beanstalk expects the Flask app to be named 'application'
application = Flask(__name__)

@application.route('/')
def home():
    return "<h1>Welcome to Flask on Elastic Beanstalk!</h1><p>Deployed from Sydney (ap-southeast-2)</p>"

@application.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
EOF

# Verify the file was created
cat application.py

# Create requirements.txt with Flask dependency
echo "flask" > requirements.txt

# Verify requirements.txt
cat requirements.txt
```

---

## Step 3 – Initialize Elastic Beanstalk Application

```bash
# Set application and environment names
APP_NAME="flask-ebs-app"
echo "APP_NAME=$APP_NAME"

ENV_NAME="flask-ebs-env"
echo "ENV_NAME=$ENV_NAME"

# Set region (consistent with other labs)
REGION="ap-southeast-2"
echo "REGION=$REGION"

# Initialize Elastic Beanstalk application with Python 3.11
eb init \
  --platform python-3.11 \
  --region $REGION \
  $APP_NAME

# The init command creates .elasticbeanstalk configuration directory
ls -la .elasticbeanstalk/
```

> **Note:** During `eb init`, you may be prompted to set up SSH for your instances. Select 'Y' and choose your existing key pair or create a new one.

---

## Step 4 – Create and Deploy the Environment

```bash
# Create a single-instance environment (cost-effective for testing)
eb create $ENV_NAME \
  --single \
  --instance-types t3.micro \
  --region $REGION

# This command will:
# 1. Create an S3 bucket for application versions
# 2. Upload your application code
# 3. Create an EC2 instance
# 4. Deploy your Flask application
# 5. Configure security groups and IAM roles
# Wait 5-10 minutes for environment creation to complete
```

> The `--single` flag deploys to a single EC2 instance without a load balancer (cost-efficient for testing).

---

## Step 5 – Validate the Deployment

```bash
# Check environment status
eb status

# Get the environment URL (CNAME)
APP_URL=$(eb status | grep "CNAME" | awk '{print $2}')
echo "APP_URL=$APP_URL"

# Test the application using curl
curl http://$APP_URL

# Test the health endpoint
curl http://$APP_URL/health

# Open the application in your browser
"$BROWSER" "http://$APP_URL"
"$BROWSER" "http://$APP_URL/health"
```

✅ You should see: **"Welcome to Flask on Elastic Beanstalk!"**

---

## Step 6 – Monitor Application Health

```bash
# Check environment health status
eb health

# View detailed health information
eb health --refresh

# View recent logs
eb logs

# Stream logs in real-time (press Ctrl+C to stop)
# eb logs --stream
```

---

## Step 7 – Cleanup Resources

To avoid ongoing charges, delete all resources:

```bash
# Terminate the Elastic Beanstalk environment
# This will delete the EC2 instance, security groups, and related resources
eb terminate $ENV_NAME --force

# Wait for termination to complete (this may take a few minutes)
echo "Waiting for environment termination..."
sleep 60

# Verify environment is terminated
aws elasticbeanstalk describe-environments \
  --environment-names $ENV_NAME \
  --region $REGION \
  --query 'Environments[0].Status'

# Delete the Elastic Beanstalk application
aws elasticbeanstalk delete-application \
  --application-name $APP_NAME \
  --region $REGION

# Wait for application deletion
sleep 10

# Set the S3 bucket name (created automatically by Elastic Beanstalk)
BUCKET_NAME="elasticbeanstalk-$REGION-$(aws sts get-caller-identity --query Account --output text)"
echo "BUCKET_NAME=$BUCKET_NAME"

# List bucket contents to verify it's empty
aws s3 ls s3://$BUCKET_NAME/ --recursive

# Remove bucket policy (has explicit deny for s3:DeleteBucket)
aws s3api delete-bucket-policy \
  --bucket $BUCKET_NAME

# Delete the S3 bucket
aws s3 rb s3://$BUCKET_NAME

# Verify bucket deletion
aws s3 ls | grep elasticbeanstalk || echo "S3 bucket successfully deleted"

# Navigate back to parent directory
cd ..

# Remove the local project directory
rm -rf flask-ebs-app

# Verify cleanup completed
echo "Cleanup completed. Verifying no applications exist..."
aws elasticbeanstalk describe-applications \
  --region $REGION \
  --query 'Applications[?ApplicationName==`flask-ebs-app`]'
```

> **Note:** The Elastic Beanstalk S3 bucket has a policy with an explicit deny for `s3:DeleteBucket` for safety. We must remove this policy before deleting the bucket.

---

## Summary

In this lab, you have:
- Installed and verified the Elastic Beanstalk CLI
- Built a Python Flask application with proper WSGI configuration
- Initialized an Elastic Beanstalk application
- Deployed your app to a single-instance environment
- Verified successful deployment and monitored health status
- Cleaned up all related resources including S3 bucket

Elastic Beanstalk simplifies application deployment by managing EC2, security groups, and scaling automatically, allowing you to focus entirely on your code.
