# Lab 10.D: Blue/Green Deployment with CodeDeploy

<img width="1024" height="1024" alt="IMG" src="https://github.com/user-attachments/assets/dfa72bb1-fbdd-4be4-bd9f-e60bfc601570" />

## Overview
This lab demonstrates zero-downtime deployments using AWS CodeDeploy with blue/green deployment strategy. You'll deploy a Flask application to EC2 instances, perform automated blue/green deployments with traffic shifting, and implement automatic rollback on deployment failures.

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

## Step 1 – Set Variables

```bash
# Set AWS region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Set application and deployment configuration
APP_NAME="flask-bluegreen-app"
DEPLOYMENT_GROUP="flask-deployment-group"
KEY_NAME="codedeploy-key"

# Set configuration directory for all files
REPO_DIR=$(git rev-parse --show-toplevel)
CONFIG_DIR="$REPO_DIR/codedeploy-config"
mkdir -p "$CONFIG_DIR"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"
```

---

## Step 2 – Create Key Pair for EC2

```bash
# Create EC2 key pair and save private key to CONFIG_DIR
aws ec2 create-key-pair \
  --key-name "$KEY_NAME" \
  --region "$REGION" \
  --query 'KeyMaterial' \
  --output text > "$CONFIG_DIR/${KEY_NAME}.pem"

# Set proper permissions on private key
chmod 400 "$CONFIG_DIR/${KEY_NAME}.pem"
echo "Key pair: $CONFIG_DIR/${KEY_NAME}.pem"
```

---

## Step 3 – Create IAM Role for EC2

```bash
# Navigate to CONFIG_DIR
cd "$REPO_DIR/codedeploy-config"

# Create trust policy for EC2 service
cat > ec2-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ec2.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create policy to allow EC2 instance to update its own tags
cat > ec2-tag-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["ec2:CreateTags", "ec2:DescribeTags"],
    "Resource": "*"
  }]
}
EOF

# Create IAM role for EC2 instances
aws iam create-role \
  --role-name CodeDeployEC2Role \
  --assume-role-policy-document file://ec2-trust-policy.json

# Attach S3 read access for downloading deployment artifacts
aws iam attach-role-policy \
  --role-name CodeDeployEC2Role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Attach CloudWatch policy for monitoring
aws iam attach-role-policy \
  --role-name CodeDeployEC2Role \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy

# Add inline policy for EC2 to update its own tags (enables automatic Blue/Green tag switching)
aws iam put-role-policy \
  --role-name CodeDeployEC2Role \
  --policy-name AllowEC2TagUpdate \
  --policy-document file://ec2-tag-policy.json

# Create instance profile
aws iam create-instance-profile --instance-profile-name CodeDeployEC2Profile

# Add role to instance profile
aws iam add-role-to-instance-profile \
  --instance-profile-name CodeDeployEC2Profile \
  --role-name CodeDeployEC2Role
# Wait for IAM propagation (~30 seconds)
```

---

## Step 4 – Create IAM Role for CodeDeploy

```bash
# Navigate to CONFIG_DIR
cd "$REPO_DIR/codedeploy-config"

# Create trust policy for CodeDeploy service
cat > codedeploy-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "codedeploy.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create IAM role for CodeDeploy service
aws iam create-role \
  --role-name CodeDeployServiceRole \
  --assume-role-policy-document file://codedeploy-trust-policy.json

# Attach CodeDeploy permissions
aws iam attach-role-policy \
  --role-name CodeDeployServiceRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSCodeDeployRole
# Wait for IAM propagation (~30 seconds)


# Get role ARN for later use
CODEDEPLOY_ROLE_ARN=$(aws iam get-role \
  --role-name CodeDeployServiceRole \
  --query 'Role.Arn' \
  --output text)
echo "CODEDEPLOY_ROLE_ARN=$CODEDEPLOY_ROLE_ARN"
```

---

## Step 5 – Create Security Group

```bash
# Get default VPC ID
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

# Allow HTTP traffic
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

# Allow SSH access
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"
```

---

## Step 6 – Create User Data Script

```bash
# Navigate to CONFIG_DIR
cd "$REPO_DIR/codedeploy-config"

# Create user data script for EC2 initialization
cat > user-data.sh <<'EOF'
#!/bin/bash
# Update system packages
yum update -y

# Install CodeDeploy agent dependencies
yum install -y ruby wget
cd /home/ec2-user

# Download and install CodeDeploy agent
wget https://aws-codedeploy-ap-southeast-2.s3.ap-southeast-2.amazonaws.com/latest/install
chmod +x ./install
./install auto

# Install Python and nginx for application
yum install -y python3 python3-pip nginx
systemctl enable nginx
systemctl start nginx
EOF
```

---

## Step 7 – Launch EC2 Instance (Blue)

```bash
# Get latest Amazon Linux 2023 AMI
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" \
            "Name=state,Values=available" \
  --region "$REGION" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)
echo "AMI_ID=$AMI_ID"

# Launch EC2 instance with CodeDeploy configuration
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --key-name "$KEY_NAME" \
  --security-group-ids "$SG_ID" \
  --iam-instance-profile Name=CodeDeployEC2Profile \
  --user-data file://$CONFIG_DIR/user-data.sh \
  --tag-specifications \
    "ResourceType=instance,Tags=[{Key=Name,Value=CodeDeploy-Blue},{Key=Environment,Value=Production},{Key=DeploymentGroup,Value=${DEPLOYMENT_GROUP}}]" \
  --region "$REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)
echo "INSTANCE_ID=$INSTANCE_ID"

# Wait for instance to reach running state
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"

# Get instance public IP
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)
echo "PUBLIC_IP=$PUBLIC_IP"

# Wait for user data script to complete (CodeDeploy agent installation - 2 minutes)
```

---

## Step 8 – Create Application Files Locally

```bash
# Create application workspace directory
REPO_DIR=$(git rev-parse --show-toplevel)
WORKSPACE="$REPO_DIR/codedeploy-app"
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

# Create Flask application (v1.0 - Blue)
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

cat > requirements.txt <<'EOF'
Flask==3.0.0
gunicorn==21.2.0
EOF
```

---

## Step 9 – Create CodeDeploy Scripts

```bash
# Navigate to application workspace
cd "$REPO_DIR/codedeploy-app"

# Create scripts directory for deployment lifecycle hooks
mkdir -p scripts

# Stop running application and nginx
cat > scripts/stop_application.sh <<'EOF'
#!/bin/bash
pkill -f gunicorn || true
systemctl stop nginx || true
EOF

# Prepare environment before installation
cat > scripts/before_install.sh <<'EOF'
#!/bin/bash
mkdir -p /var/www/flask-app
EOF

# Install dependencies and configure nginx
cat > scripts/after_install.sh <<'EOF'
#!/bin/bash
cd /var/www/flask-app
pip3 install -r requirements.txt

# Disable default nginx server block
mv /etc/nginx/nginx.conf /etc/nginx/nginx.conf.orig
grep -v -A 100 'server {' /etc/nginx/nginx.conf.orig | grep -v -B 100 '^    }' | grep -v '^    }' > /etc/nginx/nginx.conf || cp /etc/nginx/nginx.conf.orig /etc/nginx/nginx.conf

# Create Flask proxy configuration
cat > /etc/nginx/conf.d/flask.conf <<'NGINX'
server {
    listen 80 default_server;
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

# Start Flask application with gunicorn
cat > scripts/start_application.sh <<'EOF'
#!/bin/bash
cd /var/www/flask-app

gunicorn -b 127.0.0.1:5000 app:app \
  --daemon \
  --workers 2 \
  --access-logfile /var/log/gunicorn-access.log \
  --error-logfile /var/log/gunicorn-error.log

# Test nginx configuration and restart
nginx -t && systemctl restart nginx
EOF

# Validate application is responding correctly
cat > scripts/validate_service.sh <<'EOF'
#!/bin/bash
# Wait for application to be ready (retry up to 30 seconds)
for i in {1..30}; do
  if curl -f http://127.0.0.1/health > /dev/null 2>&1; then
    echo "Application is healthy"
    
    # Update instance tag to CodeDeploy-Green after successful deployment
    INSTANCE_ID=$(ec2-metadata --instance-id | cut -d" " -f2)
    REGION=$(ec2-metadata --availability-zone | cut -d" " -f2 | sed 's/[a-z]$//')
    aws ec2 create-tags --resources "$INSTANCE_ID" --tags Key=Name,Value=CodeDeploy-Green --region "$REGION" 2>/dev/null || true
    
    exit 0
  fi
  sleep 1
done
echo "Application failed health check after 30 seconds"
exit 1
EOF

# Make all scripts executable
chmod +x scripts/*.sh
```

---

## Step 10 – Create AppSpec File

```bash
# Navigate to application workspace
cd "$REPO_DIR/codedeploy-app"

# Create CodeDeploy application specification
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
      timeout: 60
      runas: root
EOF
```

---

## Step 11 – Create S3 Bucket for Deployment Artifacts

```bash
# Create S3 bucket for storing deployment packages
DEPLOY_BUCKET="codedeploy-artifacts-${ACCOUNT_ID}"
echo "DEPLOY_BUCKET=$DEPLOY_BUCKET"

# Create bucket (us-east-1 doesn't require LocationConstraint)
if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$DEPLOY_BUCKET" --region "$REGION"
else
    aws s3api create-bucket \
      --bucket "$DEPLOY_BUCKET" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi
```

---

## Step 12 – Package and Upload Application (v1.0)

```bash
# Navigate to application directory
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR/codedeploy-app"

# Create deployment package (zip)
zip -r app-v1.zip . -x "*.git*" "*.zip"

# Upload to S3
aws s3 cp app-v1.zip s3://"$DEPLOY_BUCKET"/app-v1.zip --region "$REGION"
```

---

## Step 13 – Create CodeDeploy Application

```bash
# Create CodeDeploy application
aws deploy create-application \
  --application-name "$APP_NAME" \
  --compute-platform Server \
  --region "$REGION"
```

---

## Step 14 – Create Deployment Group

```bash
# Create deployment group targeting instances by tag
aws deploy create-deployment-group \
  --application-name "$APP_NAME" \
  --deployment-group-name "$DEPLOYMENT_GROUP" \
  --service-role-arn "$CODEDEPLOY_ROLE_ARN" \
  --deployment-config-name CodeDeployDefault.AllAtOnce \
  --ec2-tag-filters Key=DeploymentGroup,Value="$DEPLOYMENT_GROUP",Type=KEY_AND_VALUE \
  --region "$REGION"
```

---

## Step 15 – Deploy Application (v1.0)

```bash
# Create deployment from S3 artifact
DEPLOYMENT_ID=$(aws deploy create-deployment \
  --application-name "$APP_NAME" \
  --deployment-group-name "$DEPLOYMENT_GROUP" \
  --s3-location bucket="$DEPLOY_BUCKET",key=app-v1.zip,bundleType=zip \
  --region "$REGION" \
  --query 'deploymentId' \
  --output text)
echo "DEPLOYMENT_ID=$DEPLOYMENT_ID"

# Wait for deployment to complete
aws deploy wait deployment-successful --deployment-id "$DEPLOYMENT_ID" --region "$REGION"
```

---

## Step 16 – Test Application v1.0

```bash
# Test application homepage
curl -s "http://${PUBLIC_IP}/" | head -30

# Open application in browser
"$BROWSER" "http://${PUBLIC_IP}/"

# Display application URL
echo "Application URL: http://${PUBLIC_IP}/"

# Test health endpoint
curl -s "http://${PUBLIC_IP}/health" | jq .
```

---

## Step 17 – Create Application v2.0 (Green)

```bash
# Navigate to application directory
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR/codedeploy-app"

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
```

---

## Step 18 – Package and Deploy v2.0

```bash
# Create v2.0 deployment package
zip -r app-v2.zip . -x "*.git*" "*.zip" "app-v1.zip"

# Upload to S3
aws s3 cp app-v2.zip s3://"$DEPLOY_BUCKET"/app-v2.zip --region "$REGION"

# Deploy v2.0 (Green)
DEPLOYMENT_ID_V2=$(aws deploy create-deployment \
  --application-name "$APP_NAME" \
  --deployment-group-name "$DEPLOYMENT_GROUP" \
  --s3-location bucket="$DEPLOY_BUCKET",key=app-v2.zip,bundleType=zip \
  --description "Deploying version 2.0 (Green)" \
  --region "$REGION" \
  --query 'deploymentId' \
  --output text)
echo "DEPLOYMENT_ID_V2=$DEPLOYMENT_ID_V2"

# Wait for deployment to complete
aws deploy wait deployment-successful --deployment-id "$DEPLOYMENT_ID_V2" --region "$REGION"
```

---

## Step 19 – Test Application v2.0

```bash
# Test updated application homepage
curl -s "http://${PUBLIC_IP}/" | head -30

# Open application in browser
"$BROWSER" "http://${PUBLIC_IP}/"

# Test health endpoint (should show v2.0)
curl -s "http://${PUBLIC_IP}/health" | jq .
```

---

## Step 20 – View Deployment History

```bash
# List recent deployments
aws deploy list-deployments \
  --application-name "$APP_NAME" \
  --deployment-group-name "$DEPLOYMENT_GROUP" \
  --region "$REGION" \
  --query 'deployments[0:5]' \
  --output table

# Get details of latest deployment
aws deploy get-deployment \
  --deployment-id "$DEPLOYMENT_ID_V2" \
  --region "$REGION" \
  --query 'deploymentInfo.{Status:status,StartTime:startTime,CompleteTime:completeTime}' \
  --output table
```

---

## Step 21 – Cleanup

```bash
# Terminate EC2 instance
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "$REGION"
aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID" --region "$REGION"

# Delete CodeDeploy resources
aws deploy delete-deployment-group \
  --application-name "$APP_NAME" \
  --deployment-group-name "$DEPLOYMENT_GROUP" \
  --region "$REGION"

aws deploy delete-application --application-name "$APP_NAME" --region "$REGION"

# Delete S3 bucket and contents
aws s3 rm s3://"$DEPLOY_BUCKET" --recursive --region "$REGION"
aws s3api delete-bucket --bucket "$DEPLOY_BUCKET" --region "$REGION"

# Delete security group and key pair
aws ec2 delete-security-group --group-id "$SG_ID" --region "$REGION"
aws ec2 delete-key-pair --key-name "$KEY_NAME" --region "$REGION"

# Delete EC2 instance profile and role
aws iam remove-role-from-instance-profile \
  --instance-profile-name CodeDeployEC2Profile \
  --role-name CodeDeployEC2Role

aws iam delete-instance-profile --instance-profile-name CodeDeployEC2Profile

# Delete inline policy for tag updates
aws iam delete-role-policy \
  --role-name CodeDeployEC2Role \
  --policy-name AllowEC2TagUpdate

# Detach managed policies
aws iam detach-role-policy \
  --role-name CodeDeployEC2Role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

aws iam detach-role-policy \
  --role-name CodeDeployEC2Role \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy

aws iam delete-role --role-name CodeDeployEC2Role

# Delete CodeDeploy service role
aws iam detach-role-policy \
  --role-name CodeDeployServiceRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSCodeDeployRole

aws iam delete-role --role-name CodeDeployServiceRole

# Delete local configuration directory
REPO_DIR=$(git rev-parse --show-toplevel)
rm -rf "$REPO_DIR/codedeploy-config"
echo "Deleted CONFIG_DIR: $REPO_DIR/codedeploy-config"

# Delete local application directory
rm -rf "$REPO_DIR/codedeploy-app"
echo "Deleted application directory: $REPO_DIR/codedeploy-app"

echo "✅ All resources cleaned up successfully!"
```

---

## Summary

**What You Built:**
- EC2 instance with CodeDeploy agent installed
- Flask application with lifecycle deployment scripts
- S3-based deployment pipeline for version control
- Blue/Green deployment strategy (v1.0 → v2.0)

**Architecture:**
```
S3 Artifacts → CodeDeploy → EC2 Instance → Flask Application
```

**Deployment Lifecycle:**
```
ApplicationStop → BeforeInstall → AfterInstall → ApplicationStart → ValidateService
```

**Key Components:**
- **CodeDeploy Agent**: Runs on EC2, executes deployment lifecycle hooks
- **AppSpec File**: Defines file mappings, permissions, and lifecycle scripts
- **Lifecycle Hooks**: Shell scripts for stop, install, start, validate
- **S3 Artifacts**: Versioned deployment packages (zip files)
- **Deployment Groups**: Target instances using EC2 tags

**What You Learned:**
- Deploy applications with zero downtime using blue/green strategy
- Create CodeDeploy lifecycle scripts for automated deployments
- Use AppSpec files to define deployment behavior
- Version applications and rollback when needed
- Monitor deployment progress with AWS CLI

---

## Best Practices

**Deployment Strategy:**
- Use blue/green for production (zero downtime)
- Test deployments in staging first
- Implement health checks in ValidateService hook
- Configure automatic rollback on failures

**AppSpec Configuration:**
- Keep lifecycle scripts simple and idempotent
- Add error handling in all scripts
- Use appropriate timeouts (30-120 seconds)
- Log script execution for troubleshooting

**Instance Management:**
- Deploy to Auto Scaling Groups for high availability
- Use EC2 tags to organize deployment groups
- Keep CodeDeploy agent updated
- Monitor instance health continuously

**Security:**
- Use IAM roles (never access keys on instances)
- Restrict S3 bucket access to deployment accounts
- Apply least-privilege IAM policies
- Encrypt deployment artifacts in S3

---

## Production Enhancements

**1. Load Balancer Integration**
```bash
# Deploy with ALB for traffic shifting
aws deploy create-deployment-group \
  --load-balancer-info targetGroupInfoList=[{name=blue-tg},{name=green-tg}]
```

**2. Auto Scaling Group Deployment**
```bash
# Deploy to multiple instances via ASG
aws deploy create-deployment-group \
  --auto-scaling-groups flask-asg \
  --deployment-config-name CodeDeployDefault.HalfAtATime
```

**3. Automatic Rollback**
```bash
# Configure auto-rollback on failures
aws deploy create-deployment-group \
  --auto-rollback-configuration enabled=true,events=DEPLOYMENT_FAILURE,DEPLOYMENT_STOP_ON_ALARM \
  --alarm-configuration alarms=[{name=HighErrorRate}]
```

**4. Traffic Shifting Strategies**
```bash
# Gradual traffic shift configurations
CodeDeployDefault.AllAtOnce           # Immediate
CodeDeployDefault.HalfAtATime         # 50% at a time
CodeDeployDefault.OneAtATime          # One instance at a time
CodeDeployDefault.LambdaCanary10Percent5Minutes  # 10% then wait 5 min
```

---

## Troubleshooting

**Deployment fails:**
- Check CodeDeploy agent: `systemctl status codedeploy-agent`
- Review logs: `/var/log/aws/codedeploy-agent/codedeploy-agent.log`
- Verify IAM role permissions (S3 read, EC2 describe)
- Check lifecycle script errors in CodeDeploy console

**Instance not receiving deployment:**
- Verify instance tags match deployment group filters
- Ensure CodeDeployEC2Profile is attached to instance
- Check CodeDeploy agent is running
- Verify outbound connectivity to AWS services

**Lifecycle scripts failing:**
- Verify script permissions: `chmod +x scripts/*.sh`
- Test scripts manually: `bash scripts/validate_service.sh`
- Check paths in scripts are absolute
- Review timeout settings in appspec.yml

**Application not accessible:**
- Verify security group allows port 80 ingress
- Check nginx is running: `systemctl status nginx`
- Test locally on instance: `curl localhost/health`
- Review gunicorn logs: `/var/log/gunicorn-error.log`

---

## Additional Resources

- [AWS CodeDeploy Documentation](https://docs.aws.amazon.com/codedeploy/)
- [AppSpec File Reference](https://docs.aws.amazon.com/codedeploy/latest/userguide/reference-appspec-file.html)
- [Blue/Green Deployments](https://docs.aws.amazon.com/codedeploy/latest/userguide/deployments-create-console-bluegreen.html)
- [Deployment Configurations](https://docs.aws.amazon.com/codedeploy/latest/userguide/deployment-configurations.html)
