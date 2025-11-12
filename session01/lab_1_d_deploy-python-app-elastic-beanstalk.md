# Lab 1.D: Deploy a Python Web App on AWS Elastic Beanstalk (ZIP-Based Deployment)

## Overview
This lab demonstrates how to deploy a Python Flask web application on **AWS Elastic Beanstalk (EBS)** using a **ZIP-based code deployment**. Elastic Beanstalk automatically handles provisioning, load balancing, scaling, and monitoring, allowing you to focus on your application code.

---

## Objectives
- Create a Python web app using Flask
- Package the application into a ZIP file
- Deploy it to Elastic Beanstalk using the AWS CLI
- Validate the application through the EBS environment URL
- Clean up resources to avoid costs

---

## Architecture Diagram (Conceptual)
```
Internet → Elastic Load Balancer → Elastic Beanstalk Environment → EC2 Instances (Flask App)
```

---

## Prerequisites
- AWS CLI and Elastic Beanstalk CLI (`eb`) installed and configured (`aws configure`)
- IAM user with permissions for Elastic Beanstalk, EC2, and S3
- Python 3.8+ installed locally

---

## Step 1. Create Project Directory and Files

```bash
# Create and navigate to project directory
mkdir flask-ebs-app && cd flask-ebs-app

# Create app.py
cat > app.py <<'EOF'
from flask import Flask
import os
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>Welcome to Flask on Elastic Beanstalk!</h1>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
EOF

# Create requirements.txt
echo "flask" > requirements.txt
```

---

## Step 2. Initialize Elastic Beanstalk Application

```bash
# Initialize EBS application
eb init -p python-3.8 flask-ebs-app

# Choose your region (e.g., ap-southeast-2 for Sydney)
# This creates an Elastic Beanstalk application configuration.
```

---

## Step 3. Create the Environment

```bash
# Create environment with load balancing enabled
eb create flask-ebs-env --sample --single
```

> The `--single` flag deploys to a single instance (cost-efficient for testing).  
> Wait until the environment status becomes **Ready** before proceeding.

---

## Step 4. Deploy Your Flask App (ZIP-Based)

1. **Package the code:**
   ```bash
   zip -r flask-ebs-app.zip .
   ```

2. **Deploy using AWS CLI:**
   ```bash
   aws elasticbeanstalk create-application-version      --application-name flask-ebs-app      --version-label v1      --source-bundle S3Bucket=$(aws elasticbeanstalk create-storage-location --query S3Bucket --output text),S3Key=flask-ebs-app.zip

   aws s3 cp flask-ebs-app.zip s3://$(aws elasticbeanstalk create-storage-location --query S3Bucket --output text)/flask-ebs-app.zip

   aws elasticbeanstalk update-environment      --environment-name flask-ebs-env      --version-label v1
   ```

Alternatively, use the Elastic Beanstalk CLI for a simpler deployment:
```bash
eb deploy
```

---

## Step 5. Validate the Deployment

Once deployment completes, retrieve the application URL:
```bash
eb status
```

Look for the line:  
`CNAME: flask-ebs-env.ap-southeast-2.elasticbeanstalk.com`

Open it in your browser or test with curl:
```bash
curl http://flask-ebs-env.ap-southeast-2.elasticbeanstalk.com
```
✅ You should see: **“Welcome to Flask on Elastic Beanstalk!”**

---

## Step 6. Monitor Application Health

Check environment health:
```bash
eb health
```

View logs if needed:
```bash
eb logs
```

---

## Step 7. Cleanup Resources

To avoid ongoing charges:
```bash
# Terminate the environment
eb terminate flask-ebs-env --force

# Delete the application
aws elasticbeanstalk delete-application --application-name flask-ebs-app --terminate-env-by-force
```

---

## Summary

In this lab, you have:
- Built and packaged a Python Flask application
- Initialized an Elastic Beanstalk environment
- Deployed your app via ZIP and AWS CLI
- Verified successful deployment and health status
- Cleaned up all related resources

Elastic Beanstalk simplifies application deployment by managing EC2, ELB, and scaling automatically, allowing you to focus entirely on your code.
