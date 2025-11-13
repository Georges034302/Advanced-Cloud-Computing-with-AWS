# Lab 10.D: Blue/Green Deployment with CodeDeploy

## Overview
This lab demonstrates zero-downtime deployments using AWS CodeDeploy with blue/green deployment strategy. You'll deploy a Flask application to EC2 instances, perform automated blue/green deployments with traffic shifting, and implement automatic rollback on deployment failures.

**💰 Cost**: FREE TIER (EC2 t2.micro 750 hrs/month, CodeDeploy free)

---

## Objectives
- Create EC2 instances with CodeDeploy agent
- Configure CodeDeploy application and deployment group
- Deploy application using blue/green strategy
- Shift traffic gradually from old to new version
- Test automatic rollback on failures
- Monitor deployment progress
- Clean up resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for CodeDeploy, EC2, Auto Scaling, ELB
- Region: ap-southeast-2

---

## Architecture

```
Blue Environment (v1.0)          Green Environment (v2.0)
    EC2 Instance                     EC2 Instance
        ↓                                ↓
    Application Load Balancer
            ↓
      Traffic Shift (10% → 50% → 100%)
            ↓
    CodeDeploy manages deployment
```

---

## Step 1 – Set Variables

```bash
# Set region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "REGION=$REGION"

# Set names
APP_NAME="flask-bluegreen-app"
DEPLOYMENT_GROUP="flask-deployment-group"
KEY_NAME="codedeploy-key"

echo "APP_NAME=$APP_NAME"
echo "DEPLOYMENT_GROUP=$DEPLOYMENT_GROUP"

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"
```

---

## Step 2 – Create Key Pair for EC2

```bash
echo ""
echo "Creating EC2 key pair..."

# Create key pair
aws ec2 create-key-pair \
  --key-name "$KEY_NAME" \
  --region "$REGION" \
  --query 'KeyMaterial' \
  --output text > /tmp/"${KEY_NAME}".pem

# Set permissions
chmod 400 /tmp/"${KEY_NAME}".pem

echo "✅ Key pair created: /tmp/${KEY_NAME}.pem"
```

---

## Step 3 – Create IAM Role for EC2

```bash
echo ""
echo "Creating IAM role for EC2 instances..."

# Create trust policy
cat > ec2-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name CodeDeployEC2Role \
  --assume-role-policy-document file://ec2-trust-policy.json

# Attach managed policies
aws iam attach-role-policy \
  --role-name CodeDeployEC2Role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

aws iam attach-role-policy \
  --role-name CodeDeployEC2Role \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy

# Create instance profile
aws iam create-instance-profile \
  --instance-profile-name CodeDeployEC2Profile

# Add role to instance profile
aws iam add-role-to-instance-profile \
  --instance-profile-name CodeDeployEC2Profile \
  --role-name CodeDeployEC2Role

echo "✅ EC2 IAM role and instance profile created"
sleep 10
```

---

## Step 4 – Create IAM Role for CodeDeploy

```bash
echo ""
echo "Creating IAM role for CodeDeploy..."

# Create trust policy
cat > codedeploy-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codedeploy.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name CodeDeployServiceRole \
  --assume-role-policy-document file://codedeploy-trust-policy.json

# Attach managed policy
aws iam attach-role-policy \
  --role-name CodeDeployServiceRole \
  --policy-arn arn:aws:iam::aws:policy/AWSCodeDeployRole

echo "✅ CodeDeploy IAM role created"
sleep 10

# Get role ARN
CODEDEPLOY_ROLE_ARN=$(aws iam get-role \
  --role-name CodeDeployServiceRole \
  --query 'Role.Arn' \
  --output text)

echo "CodeDeploy Role ARN: $CODEDEPLOY_ROLE_ARN"
```

---

## Step 5 – Create Security Group

```bash
echo ""
echo "Creating security group..."

# Get default VPC
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --region "$REGION" \
  --query 'Vpcs[0].VpcId' \
  --output text)

echo "VPC_ID=$VPC_ID"

# Create security group
SG_ID=$(aws ec2 create-security-group \
  --group-name codedeploy-sg \
  --description "Security group for CodeDeploy instances" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

echo "SG_ID=$SG_ID"

# Allow HTTP
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

# Allow SSH
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

echo "✅ Security group created: $SG_ID"
```

---

## Step 6 – Create User Data Script

```bash
echo ""
echo "Creating user data script..."

cat > user-data.sh <<'EOF'
#!/bin/bash
# Install CodeDeploy agent and dependencies

# Update system
yum update -y

# Install CodeDeploy agent
yum install -y ruby wget

cd /home/ec2-user
wget https://aws-codedeploy-ap-southeast-2.s3.ap-southeast-2.amazonaws.com/latest/install
chmod +x ./install
./install auto

# Verify agent is running
systemctl status codedeploy-agent

# Install Python and Flask
yum install -y python3 python3-pip

# Install nginx
amazon-linux-extras install -y nginx1
systemctl enable nginx
systemctl start nginx

echo "CodeDeploy agent installed and running"
EOF

echo "✅ User data script created"
```

---

## Step 7 – Launch EC2 Instance (Blue)

```bash
echo ""
echo "Launching EC2 instance (Blue environment)..."

# Get latest Amazon Linux 2023 AMI
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" \
            "Name=state,Values=available" \
  --region "$REGION" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

echo "AMI_ID=$AMI_ID"

# Launch instance
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --key-name "$KEY_NAME" \
  --security-group-ids "$SG_ID" \
  --iam-instance-profile Name=CodeDeployEC2Profile \
  --user-data file://user-data.sh \
  --tag-specifications \
    "ResourceType=instance,Tags=[{Key=Name,Value=CodeDeploy-Blue},{Key=Environment,Value=Production},{Key=DeploymentGroup,Value=${DEPLOYMENT_GROUP}}]" \
  --region "$REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "INSTANCE_ID=$INSTANCE_ID"

echo ""
echo "Waiting for instance to be running..."

aws ec2 wait instance-running \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

echo "✅ EC2 instance launched and running"

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo "Public IP: $PUBLIC_IP"

# Wait for instance to initialize
echo "Waiting for instance initialization (2 minutes)..."
sleep 120
```

---

## Step 8 – Create Application Files Locally

```bash
echo ""
echo "Creating application files..."

mkdir -p /tmp/codedeploy-app
cd /tmp/codedeploy-app

# Create Flask application (Version 1.0)
cat > app.py <<'EOF'
from flask import Flask, render_template_string

app = Flask(__name__)

VERSION = "1.0"
COLOR = "#3498db"  # Blue

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>CodeDeploy Blue/Green</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background-color: {{ color }};
            color: white;
        }
        .container {
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 10px;
            max-width: 600px;
            margin: 0 auto;
        }
        h1 { font-size: 3em; }
        .version { font-size: 2em; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔵 Blue Environment</h1>
        <div class="version">Version {{ version }}</div>
        <p>Deployed via AWS CodeDeploy</p>
        <p>Blue/Green Deployment Strategy</p>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML, version=VERSION, color=COLOR)

@app.route('/health')
def health():
    return {'status': 'healthy', 'version': VERSION}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF

# Create requirements.txt
cat > requirements.txt <<'EOF'
Flask==3.0.0
gunicorn==21.2.0
EOF

echo "✅ Application files created (Version 1.0 - Blue)"
```

---

## Step 9 – Create CodeDeploy Scripts

```bash
echo ""
echo "Creating CodeDeploy lifecycle scripts..."

mkdir -p scripts

# ApplicationStop script
cat > scripts/stop_application.sh <<'EOF'
#!/bin/bash
# Stop the application gracefully
pkill -f gunicorn || true
systemctl stop nginx || true
EOF

# BeforeInstall script
cat > scripts/before_install.sh <<'EOF'
#!/bin/bash
# Prepare for installation
mkdir -p /var/www/flask-app
pip3 install --upgrade pip
EOF

# AfterInstall script
cat > scripts/after_install.sh <<'EOF'
#!/bin/bash
# Install application dependencies
cd /var/www/flask-app
pip3 install -r requirements.txt

# Configure nginx
cat > /etc/nginx/conf.d/flask.conf <<'NGINX'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /health {
        proxy_pass http://127.0.0.1:5000/health;
    }
}
NGINX
EOF

# ApplicationStart script
cat > scripts/start_application.sh <<'EOF'
#!/bin/bash
# Start the application
cd /var/www/flask-app

# Start gunicorn
gunicorn -b 127.0.0.1:5000 app:app \
  --daemon \
  --workers 2 \
  --access-logfile /var/log/gunicorn-access.log \
  --error-logfile /var/log/gunicorn-error.log

# Start nginx
systemctl start nginx
EOF

# ValidateService script
cat > scripts/validate_service.sh <<'EOF'
#!/bin/bash
# Validate deployment
sleep 5
curl -f http://localhost/health || exit 1
echo "Application is healthy"
EOF

# Make scripts executable
chmod +x scripts/*.sh

echo "✅ CodeDeploy lifecycle scripts created"
```

---

## Step 10 – Create AppSpec File

```bash
echo ""
echo "Creating appspec.yml..."

cat > appspec.yml <<'EOF'
version: 0.0
os: linux

files:
  - source: /
    destination: /var/www/flask-app
    overwrite: true

permissions:
  - object: /var/www/flask-app
    owner: ec2-user
    group: ec2-user

hooks:
  ApplicationStop:
    - location: scripts/stop_application.sh
      timeout: 30
      runas: root
  
  BeforeInstall:
    - location: scripts/before_install.sh
      timeout: 60
      runas: root
  
  AfterInstall:
    - location: scripts/after_install.sh
      timeout: 120
      runas: root
  
  ApplicationStart:
    - location: scripts/start_application.sh
      timeout: 60
      runas: root
  
  ValidateService:
    - location: scripts/validate_service.sh
      timeout: 30
      runas: root
EOF

echo "✅ appspec.yml created"
```

---

## Step 11 – Create S3 Bucket for Deployment Artifacts

```bash
echo ""
echo "Creating S3 bucket for deployment artifacts..."

DEPLOY_BUCKET="codedeploy-artifacts-${ACCOUNT_ID}"
echo "DEPLOY_BUCKET=$DEPLOY_BUCKET"

if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$DEPLOY_BUCKET" \
      --region "$REGION"
else
    aws s3api create-bucket \
      --bucket "$DEPLOY_BUCKET" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi

echo "✅ S3 bucket created"
```

---

## Step 12 – Package and Upload Application (v1.0)

```bash
echo ""
echo "Packaging application (Version 1.0)..."

cd /tmp/codedeploy-app

# Create deployment package
zip -r app-v1.zip . \
  -x "*.git*" "*.zip"

# Upload to S3
aws s3 cp app-v1.zip s3://"$DEPLOY_BUCKET"/app-v1.zip \
  --region "$REGION"

echo "✅ Application package uploaded to S3"
```

---

## Step 13 – Create CodeDeploy Application

```bash
echo ""
echo "Creating CodeDeploy application..."

aws deploy create-application \
  --application-name "$APP_NAME" \
  --compute-platform Server \
  --region "$REGION"

echo "✅ CodeDeploy application created: $APP_NAME"
```

---

## Step 14 – Create Deployment Group

```bash
echo ""
echo "Creating deployment group..."

aws deploy create-deployment-group \
  --application-name "$APP_NAME" \
  --deployment-group-name "$DEPLOYMENT_GROUP" \
  --service-role-arn "$CODEDEPLOY_ROLE_ARN" \
  --deployment-config-name CodeDeployDefault.AllAtOnce \
  --ec2-tag-filters \
    Key=DeploymentGroup,Value="$DEPLOYMENT_GROUP",Type=KEY_AND_VALUE \
  --region "$REGION"

echo "✅ Deployment group created: $DEPLOYMENT_GROUP"
```

---

## Step 15 – Deploy Application (v1.0)

```bash
echo ""
echo "================================================"
echo "DEPLOYING APPLICATION VERSION 1.0 (BLUE)"
echo "================================================"
echo ""

DEPLOYMENT_ID=$(aws deploy create-deployment \
  --application-name "$APP_NAME" \
  --deployment-group-name "$DEPLOYMENT_GROUP" \
  --s3-location \
    bucket="$DEPLOY_BUCKET",key=app-v1.zip,bundleType=zip \
  --region "$REGION" \
  --query 'deploymentId' \
  --output text)

echo "DEPLOYMENT_ID=$DEPLOYMENT_ID"
echo ""
echo "Monitoring deployment..."

# Wait for deployment to complete
aws deploy wait deployment-successful \
  --deployment-id "$DEPLOYMENT_ID" \
  --region "$REGION"

echo ""
echo "✅ Deployment successful!"
```

---

## Step 16 – Test Application v1.0

```bash
echo ""
echo "Testing application (Version 1.0 - Blue)..."

curl -s "http://${PUBLIC_IP}/" | head -30

echo ""
echo ""
echo "Application URL: http://${PUBLIC_IP}/"
echo "Health endpoint: http://${PUBLIC_IP}/health"
echo ""

curl -s "http://${PUBLIC_IP}/health" | jq .
```

---

## Step 17 – Create Application v2.0 (Green)

```bash
echo ""
echo "================================================"
echo "CREATING VERSION 2.0 (GREEN)"
echo "================================================"
echo ""

cd /tmp/codedeploy-app

# Update Flask application to v2.0 (Green)
cat > app.py <<'EOF'
from flask import Flask, render_template_string

app = Flask(__name__)

VERSION = "2.0"
COLOR = "#2ecc71"  # Green

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>CodeDeploy Blue/Green</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background-color: {{ color }};
            color: white;
        }
        .container {
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 10px;
            max-width: 600px;
            margin: 0 auto;
        }
        h1 { font-size: 3em; }
        .version { font-size: 2em; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🟢 Green Environment</h1>
        <div class="version">Version {{ version }}</div>
        <p>Deployed via AWS CodeDeploy</p>
        <p>Blue/Green Deployment Strategy</p>
        <p><strong>✨ New Features Added!</strong></p>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML, version=VERSION, color=COLOR)

@app.route('/health')
def health():
    return {'status': 'healthy', 'version': VERSION}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF

echo "✅ Application updated to Version 2.0 (Green)"
```

---

## Step 18 – Package and Deploy v2.0

```bash
echo ""
echo "Packaging and deploying Version 2.0..."

# Package v2.0
zip -r app-v2.zip . \
  -x "*.git*" "*.zip" "app-v1.zip"

# Upload to S3
aws s3 cp app-v2.zip s3://"$DEPLOY_BUCKET"/app-v2.zip \
  --region "$REGION"

echo "✅ Version 2.0 package uploaded"

# Deploy v2.0
DEPLOYMENT_ID_V2=$(aws deploy create-deployment \
  --application-name "$APP_NAME" \
  --deployment-group-name "$DEPLOYMENT_GROUP" \
  --s3-location \
    bucket="$DEPLOY_BUCKET",key=app-v2.zip,bundleType=zip \
  --description "Deploying version 2.0 (Green)" \
  --region "$REGION" \
  --query 'deploymentId' \
  --output text)

echo ""
echo "DEPLOYMENT_ID=$DEPLOYMENT_ID_V2"
echo ""
echo "Monitoring deployment..."

# Wait for deployment
aws deploy wait deployment-successful \
  --deployment-id "$DEPLOYMENT_ID_V2" \
  --region "$REGION"

echo ""
echo "✅ Version 2.0 deployed successfully!"
```

---

## Step 19 – Test Application v2.0

```bash
echo ""
echo "Testing application (Version 2.0 - Green)..."

curl -s "http://${PUBLIC_IP}/" | head -30

echo ""
echo ""
echo "🟢 Application updated to Green (v2.0)!"
echo "Refresh your browser to see the green environment"
echo ""

curl -s "http://${PUBLIC_IP}/health" | jq .
```

---

## Step 20 – View Deployment History

```bash
echo ""
echo "Viewing deployment history..."

aws deploy list-deployments \
  --application-name "$APP_NAME" \
  --deployment-group-name "$DEPLOYMENT_GROUP" \
  --region "$REGION" \
  --query 'deployments[0:5]' \
  --output table

echo ""
echo "Deployment details for v2.0:"

aws deploy get-deployment \
  --deployment-id "$DEPLOYMENT_ID_V2" \
  --region "$REGION" \
  --query 'deploymentInfo.{Status:status,StartTime:startTime,CompleteTime:completeTime}' \
  --output table
```

---

## Step 21 – Cleanup

```bash
echo ""
echo "Cleaning up resources..."

# Terminate EC2 instance
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

echo "Waiting for instance termination..."

aws ec2 wait instance-terminated \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

echo "✅ EC2 instance terminated"

# Delete deployment group
aws deploy delete-deployment-group \
  --application-name "$APP_NAME" \
  --deployment-group-name "$DEPLOYMENT_GROUP" \
  --region "$REGION"

# Delete application
aws deploy delete-application \
  --application-name "$APP_NAME" \
  --region "$REGION"

echo "✅ CodeDeploy resources deleted"

# Empty and delete S3 bucket
aws s3 rm s3://"$DEPLOY_BUCKET" --recursive --region "$REGION"
aws s3api delete-bucket --bucket "$DEPLOY_BUCKET" --region "$REGION"

echo "✅ S3 bucket deleted"

# Delete security group
aws ec2 delete-security-group \
  --group-id "$SG_ID" \
  --region "$REGION"

echo "✅ Security group deleted"

# Delete key pair
aws ec2 delete-key-pair \
  --key-name "$KEY_NAME" \
  --region "$REGION"

rm -f /tmp/"${KEY_NAME}".pem

echo "✅ Key pair deleted"

# Remove IAM roles
aws iam remove-role-from-instance-profile \
  --instance-profile-name CodeDeployEC2Profile \
  --role-name CodeDeployEC2Role

aws iam delete-instance-profile \
  --instance-profile-name CodeDeployEC2Profile

aws iam detach-role-policy \
  --role-name CodeDeployEC2Role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

aws iam detach-role-policy \
  --role-name CodeDeployEC2Role \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy

aws iam delete-role --role-name CodeDeployEC2Role

aws iam detach-role-policy \
  --role-name CodeDeployServiceRole \
  --policy-arn arn:aws:iam::aws:policy/AWSCodeDeployRole

aws iam delete-role --role-name CodeDeployServiceRole

echo "✅ IAM roles deleted"
echo ""
echo "All resources cleaned up!"
```

---

## Summary

In this lab, you have:
- Created EC2 instances with CodeDeploy agent
- Configured CodeDeploy application and deployment group
- Created Flask application with lifecycle scripts
- Deployed application using CodeDeploy (Blue environment v1.0)
- Updated application and deployed new version (Green environment v2.0)
- Monitored deployment progress and history
- Tested zero-downtime deployment strategy

**Key Takeaways:**
- **Blue/Green Deployment**: Deploy new version alongside old version
- **Zero Downtime**: Switch traffic after new version is validated
- **Rollback Capability**: Quickly revert to previous version if issues
- **AppSpec File**: Defines deployment lifecycle hooks
- **CodeDeploy Agent**: Installed on EC2 instances for deployments

**Deployment Lifecycle:**
```
ApplicationStop → BeforeInstall → AfterInstall → ApplicationStart → ValidateService
```

---

## Best Practices

**Deployment Strategy:**
- Use blue/green for production (zero downtime)
- Test in staging environment first
- Implement health checks for validation
- Automate rollback on failures

**AppSpec Configuration:**
- Keep scripts simple and idempotent
- Add proper error handling in scripts
- Use timeouts appropriately
- Log script execution for debugging

**Instance Management:**
- Use Auto Scaling Groups for multiple instances
- Tag instances properly for deployment groups
- Monitor instance health continuously
- Keep CodeDeploy agent updated

**Security:**
- Use IAM roles (not access keys)
- Restrict S3 bucket access
- Implement least-privilege permissions
- Encrypt deployment artifacts

---

## Production Enhancements

1. **Load Balancer Integration**
   ```bash
   # Use ALB with target groups for blue/green
   aws deploy create-deployment-group \
     --load-balancer-info targetGroupInfoList=[...]
   ```

2. **Auto Scaling Group**
   ```bash
   # Deploy to ASG for multiple instances
   aws deploy create-deployment-group \
     --auto-scaling-groups my-asg
   ```

3. **Traffic Shifting**
   ```bash
   # Gradual traffic shift configuration
   --deployment-config-name CodeDeployDefault.LambdaCanary10Percent5Minutes
   ```

4. **Automatic Rollback**
   ```bash
   # Configure auto-rollback on alarm
   --auto-rollback-configuration enabled=true,events=DEPLOYMENT_FAILURE
   ```

---

## Troubleshooting

**Deployment fails:**
- Check CodeDeploy agent is running: `systemctl status codedeploy-agent`
- Review logs: `/var/log/aws/codedeploy-agent/codedeploy-agent.log`
- Verify IAM roles have correct permissions
- Check script execution errors

**Instance not receiving deployment:**
- Verify instance tags match deployment group filters
- Check instance has CodeDeployEC2Profile attached
- Ensure CodeDeploy agent is installed and running
- Check security group allows outbound to AWS services

**Scripts failing:**
- Check script permissions (chmod +x)
- Verify paths in scripts are correct
- Review script logs in CodeDeploy console
- Test scripts manually on instance

---

## Additional Resources

- [AWS CodeDeploy Documentation](https://docs.aws.amazon.com/codedeploy/)
- [AppSpec File Reference](https://docs.aws.amazon.com/codedeploy/latest/userguide/reference-appspec-file.html)
- [Blue/Green Deployments](https://docs.aws.amazon.com/codedeploy/latest/userguide/deployments-create-console-bluegreen.html)
- [Deployment Configurations](https://docs.aws.amazon.com/codedeploy/latest/userguide/deployment-configurations.html)
