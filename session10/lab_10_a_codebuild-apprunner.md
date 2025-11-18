# Lab 10.A: CodeBuild + App Runner - Code-Based Deployment

<img width="1200" height="634" alt="IMG" src="https://github.com/user-attachments/assets/9f2d9df8-99e8-45b2-a1a3-00d75ae6cd9d" />

## Overview
This lab demonstrates AWS-native CI/CD using CodeBuild and App Runner with code-based deployment. You'll connect GitHub to AWS CodeBuild, package a Flask application as a zip file, and deploy it to App Runner using source code (not containers). This showcases AWS's fully managed build and deployment pipeline.

---

## Objectives
- Connect GitHub repository to AWS CodeBuild
- Create Flask application with buildspec.yml
- Configure CodeBuild for zip packaging (code-based)
- Deploy to App Runner using source code (not Docker)
- Understand AWS-native CI/CD pipeline
- Test automated builds and deployments

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Git installed (`git --version`)
- GitHub account with existing repository 
- IAM permissions for CodeBuild, App Runner, S3, IAM
- Region: ap-southeast-2

---

## Step 1 – Set Variables

```bash
# Set AWS region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Dynamically get GitHub repository info from git remote
GITHUB_URL=$(git remote get-url origin)
GITHUB_OWNER=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/]([^/]+)/.*|\1|')
GITHUB_REPO=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/][^/]+/([^.]+)(\.git)?$|\1|')

# Application configuration
APP_FOLDER="flask-apprunner-app"
SERVICE_NAME="flask-joke-service"

# Get account ID and set bucket name
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ARTIFACT_BUCKET="codebuild-artifacts-${ACCOUNT_ID}"

echo "REGION=$REGION"
echo "GITHUB_OWNER=$GITHUB_OWNER"
echo "GITHUB_REPO=$GITHUB_REPO"
echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "ARTIFACT_BUCKET=$ARTIFACT_BUCKET"
```

---

## Step 2 – Verify GitHub Repository

```bash
# Navigate to repository root and sync with remote
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR"
git checkout main
git pull origin main
```

---

## Step 3 – Create S3 Bucket for Build Artifacts

```bash
# Create S3 bucket (us-east-1 doesn't require LocationConstraint)
if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION"
else
    aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi
```

---

## Step 4 – Create Application Directory

```bash
# Create and navigate to application directory
WORKSPACE="$REPO_DIR/$APP_FOLDER"
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"
```

---

## Step 5 – Create Flask Application

```bash
# Create Flask API with joke endpoints
cat > app.py <<'EOF'
from flask import Flask, jsonify
import random

app = Flask(__name__)

jokes = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why did the developer go broke? Because he used up all his cache!",
    "How do you comfort a JavaScript bug? You console it!",
    "Why do Java developers wear glasses? Because they don't C#!",
    "What's a programmer's favorite hangout place? Foo Bar!"
]

@app.route('/')
def home():
    return jsonify({
        "message": "Flask Joke API on App Runner",
        "endpoints": {
            "/": "API info",
            "/joke": "Get random joke",
            "/health": "Health check"
        }
    })

@app.route('/joke')
def get_joke():
    return jsonify({"joke": random.choice(jokes)})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
EOF
```

---

## Step 6 – Create Requirements File

```bash
# Define Python dependencies
cat > requirements.txt <<'EOF'
Flask==2.3.0
Werkzeug==2.3.0
gunicorn==21.2.0
EOF
```

---

## Step 7 – Create BuildSpec for CodeBuild

```bash
# Create build specification for packaging application
cat > buildspec.yml <<'EOF'
version: 0.2

phases:
  build:
    commands:
      - zip -r flask-app.zip app.py requirements.txt

  post_build:
    commands:
      - aws s3 cp flask-app.zip s3://$ARTIFACT_BUCKET/flask-app-latest.zip
      - echo "Artifact uploaded to S3"

artifacts:
  files:
    - flask-app.zip
EOF
```

---

## Step 8 – Commit and Push to GitHub

```bash
# Commit Flask application files to GitHub
git add "$APP_FOLDER/"
git commit -m "Add Flask joke API for App Runner"
git push origin main
```

---

## Step 9 – Create IAM Role for App Runner

```bash
# Create trust policy for App Runner task role
cat > apprunner-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "tasks.apprunner.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role for App Runner instances
aws iam create-role \
  --role-name AppRunnerInstanceRole \
  --assume-role-policy-document file://apprunner-trust-policy.json
```

---

## Step 10 – Create IAM Role for App Runner Access

```bash
# Create trust policy for App Runner build service
cat > apprunner-access-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "build.apprunner.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role for App Runner to access S3 artifacts
aws iam create-role \
  --role-name AppRunnerAccessRole \
  --assume-role-policy-document file://apprunner-access-trust-policy.json

# Create S3 access policy for artifact bucket
cat > apprunner-access-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${ARTIFACT_BUCKET}",
        "arn:aws:s3:::${ARTIFACT_BUCKET}/*"
      ]
    }
  ]
}
EOF

# Attach policy to role
aws iam put-role-policy \
  --role-name AppRunnerAccessRole \
  --policy-name AppRunnerS3Access \
  --policy-document file://apprunner-access-policy.json

# Wait for IAM propagation
sleep 10
```

---

## Step 11 – Create IAM Role for CodeBuild

```bash
# Create trust policy for CodeBuild service
cat > codebuild-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "codebuild.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role for CodeBuild
aws iam create-role \
  --role-name CodeBuildServiceRole \
  --assume-role-policy-document file://codebuild-trust-policy.json

# Create permissions policy for CloudWatch Logs and S3 access
cat > codebuild-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::${ARTIFACT_BUCKET}",
        "arn:aws:s3:::${ARTIFACT_BUCKET}/*"
      ]
    }
  ]
}
EOF

# Attach policy to role
aws iam put-role-policy \
  --role-name CodeBuildServiceRole \
  --policy-name CodeBuildPermissions \
  --policy-document file://codebuild-permissions.json

# Wait for IAM propagation
sleep 10
```

---

## Step 12 – Create CodeBuild Project

```bash
# Create CodeBuild project configuration
cat > codebuild-project.json <<EOF
{
  "name": "flask-apprunner-build",
  "description": "Build Flask app from GitHub for App Runner",
  "source": {
    "type": "GITHUB",
    "location": "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}.git",
    "gitCloneDepth": 1,
    "buildspec": "${APP_FOLDER}/buildspec.yml"
  },
  "artifacts": {
    "type": "S3",
    "location": "${ARTIFACT_BUCKET}",
    "name": "flask-app.zip",
    "packaging": "NONE"
  },
  "environment": {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/standard:7.0",
    "computeType": "BUILD_GENERAL1_SMALL",
    "environmentVariables": [
      {"name": "AWS_DEFAULT_REGION", "value": "${REGION}"},
      {"name": "ARTIFACT_BUCKET", "value": "${ARTIFACT_BUCKET}"}
    ]
  },
  "serviceRole": "arn:aws:iam::${ACCOUNT_ID}:role/CodeBuildServiceRole"
}
EOF

# Create the CodeBuild project
aws codebuild create-project --cli-input-json file://codebuild-project.json --region "$REGION"
```

---

## Step 13 – Authorize GitHub Access

**Manual Step (AWS Console):**
1. Go to AWS Console → CodeBuild → Build Projects
2. Select `flask-apprunner-build`
3. Click Edit → Source
4. Click "Connect to GitHub" and authorize
5. Save changes

```bash
read -p "Press Enter after completing GitHub authorization..."
```

---

## Step 14 – Trigger Build

```bash
BUILD_ID=$(aws codebuild start-build \
  --project-name flask-apprunner-build \
  --source-version main \
  --region "$REGION" \
  --query 'build.id' \
  --output text)

echo "BUILD_ID=$BUILD_ID"
```

---

## Step 15 – Monitor Build

```bash
while true; do
    BUILD_STATUS=$(aws codebuild batch-get-builds \
      --ids "$BUILD_ID" \
      --region "$REGION" \
      --query 'builds[0].buildStatus' \
      --output text)
    
    echo "Build status: $BUILD_STATUS"
    
    [ "$BUILD_STATUS" = "SUCCEEDED" ] && echo "✅ Build succeeded!" && break
    [ "$BUILD_STATUS" = "FAILED" ] || [ "$BUILD_STATUS" = "STOPPED" ] && echo "❌ Build failed" && break
    
    sleep 15
done
```


---

## Step 16 – Create GitHub Connection for App Runner

```bash
# Create GitHub connection for App Runner
CONNECTION_ARN=$(aws apprunner create-connection \
  --connection-name github-connection \
  --provider-type GITHUB \
  --region "$REGION" \
  --query 'Connection.ConnectionArn' \
  --output text)

echo "CONNECTION_ARN=$CONNECTION_ARN"
```

**Manual Step (AWS Console):**
1. Go to AWS Console → App Runner → GitHub connections
2. Find `github-connection` and select it
3. Click **"Complete handshake"**
4. Authorize AWS to access your GitHub repository
5. Wait for status to become "AVAILABLE"

```bash
read -p "Press Enter after completing GitHub connection handshake..."
```

---

## Step 17 – Create App Runner Service

```bash
# Create App Runner service configuration with code-based deployment
cat > apprunner-service.json <<EOF
{
  "ServiceName": "${SERVICE_NAME}",
  "SourceConfiguration": {
    "CodeRepository": {
      "RepositoryUrl": "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}",
      "SourceCodeVersion": {
        "Type": "BRANCH",
        "Value": "main"
      },
      "SourceDirectory": "${APP_FOLDER}",
      "CodeConfiguration": {
        "ConfigurationSource": "API",
        "CodeConfigurationValues": {
          "Runtime": "PYTHON_3",
          "StartCommand": "gunicorn --bind :8000 app:app",
          "Port": "8000"
        }
      }
    },
    "AutoDeploymentsEnabled": false,
    "AuthenticationConfiguration": {
      "ConnectionArn": "${CONNECTION_ARN}"
    }
  },
  "InstanceConfiguration": {
    "Cpu": "1 vCPU",
    "Memory": "2 GB",
    "InstanceRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/AppRunnerInstanceRole"
  }
}
EOF

# Create the App Runner service
SERVICE_ARN=$(aws apprunner create-service \
  --cli-input-json file://apprunner-service.json \
  --region "$REGION" \
  --query 'Service.ServiceArn' \
  --output text)

echo "SERVICE_ARN=$SERVICE_ARN"
```

---

## Step 18 – Wait for Service to be Ready

```bash
# Wait for service deployment (1-2 minutes)
while true; do
  STATUS=$(aws apprunner describe-service --service-arn "$SERVICE_ARN" --region "$REGION" --query 'Service.Status' --output text)
  echo "Status: $STATUS"
  [ "$STATUS" = "RUNNING" ] && break
  [ "$STATUS" = "CREATE_FAILED" ] && echo "❌ Deployment failed" && break
  sleep 10
done

# Get service URL
SERVICE_URL=$(aws apprunner describe-service \
  --service-arn "$SERVICE_ARN" \
  --region "$REGION" \
  --query 'Service.ServiceUrl' \
  --output text)

echo "SERVICE_URL=$SERVICE_URL"
```

---

## Step 19 – Test Application

```bash
# Test all API endpoints
echo "Testing home endpoint:"
curl -s "https://$SERVICE_URL/" | jq .

echo -e "\nTesting joke endpoint:"
curl -s "https://$SERVICE_URL/joke" | jq .

echo -e "\nTesting health endpoint:"
curl -s "https://$SERVICE_URL/health" | jq .

# Open in browser
echo -e "\nApplication URL: https://$SERVICE_URL"
"$BROWSER" "https://$SERVICE_URL"
```

---

## Step 20 – Make Code Change

```bash
# Navigate to application directory
cd "$REPO_DIR/$APP_FOLDER"

# Add new joke to the application
sed -i '/"What.s a programmer.s favorite hangout place/a\    "Why do Python programmers prefer snake_case? Because camelCase is too humpy!",' app.py

# Commit and push changes
git add app.py
git commit -m "Add new Python joke"
git push origin main

echo "✅ Code changes pushed to GitHub"
echo "Manually trigger deployment: App Runner Console → Actions → Deploy"
```

---

## Step 21 – Cleanup

```bash
# Delete App Runner service
aws apprunner delete-service --service-arn "$SERVICE_ARN" --region "$REGION"

# Wait for service deletion to complete
while true; do
  STATUS=$(aws apprunner describe-service --service-arn "$SERVICE_ARN" --region "$REGION" --query 'Service.Status' --output text 2>/dev/null) || break
  echo "Status: $STATUS"
  [ "$STATUS" = "DELETED" ] && break
  sleep 10
done

# Delete GitHub connection
aws apprunner delete-connection --connection-arn "$CONNECTION_ARN" --region "$REGION"

# Delete CodeBuild project
aws codebuild delete-project --name flask-apprunner-build --region "$REGION"

# Empty and delete S3 bucket
aws s3 rm s3://"$ARTIFACT_BUCKET" --recursive
aws s3api delete-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION"

# Delete IAM roles and policies
aws iam delete-role-policy --role-name CodeBuildServiceRole --policy-name CodeBuildPermissions
aws iam delete-role --role-name CodeBuildServiceRole

aws iam delete-role-policy --role-name AppRunnerAccessRole --policy-name AppRunnerS3Access
aws iam delete-role --role-name AppRunnerAccessRole

aws iam delete-role --role-name AppRunnerInstanceRole

# Remove application directory from workspace
cd "$REPO_DIR"
rm -rf "$APP_FOLDER"

# Remove from git repository
git rm -r "$APP_FOLDER"
git commit -m "Cleanup: Remove Flask App Runner app"
git push origin main
```

---

## Summary

In this lab, you:
- Connected GitHub repository to AWS CodeBuild
- Created Flask application with buildspec.yml
- Configured CodeBuild for zip packaging
- Deployed to App Runner using **code-based** deployment (not containers)
- Tested deployed application endpoints
- Made code changes and triggered new builds
- Cleaned up all AWS resources

**Key Takeaways:**
- **AWS-Native CI/CD**: CodeBuild is AWS's managed build service
- **Code-Based Deployment**: App Runner deploys from source code (zip files)
- **No Docker Required**: Simple deployment without containers
- **buildspec.yml**: Defines build steps for packaging
- **Fully Managed**: AWS handles infrastructure, scaling, and deployments

**CI/CD Workflow:**
```
GitHub → CodeBuild (build zip) → S3 → App Runner (deploy code)
```

**Note**: Lab 10.C demonstrates the same App Runner target but using GitHub Actions + Docker containers instead of CodeBuild + source code.

---

## Best Practices

**CodeBuild:**
- Use specific image versions (standard:7.0)
- Enable build caching for faster builds
- Use environment variables for flexibility

**App Runner:**
- Enable auto-scaling for production workloads
- Use health checks for reliability
- Monitor metrics in CloudWatch
- Configure custom domains for production

**Security:**
- Use IAM roles (not access keys)
- Follow least-privilege principle
- Enable CloudTrail for audit logging

---

## Troubleshooting

**GitHub connection fails:**
- Complete OAuth authorization in AWS Console
- Verify repository name and owner are correct

**CodeBuild fails:**
- Check buildspec.yml path in project configuration
- Verify IAM role has S3 PutObject permissions
- Check CloudWatch Logs for error details

**App Runner deployment fails:**
- Verify app.py exists and port is 8000
- Check requirements.txt has all dependencies
- Review service logs in CloudWatch

**Application returns errors:**
- Check application listens on correct port (8000)
- Review CloudWatch Logs for application errors
- Verify runtime configuration in App Runner

---

## Additional Resources

- [AWS CodeBuild Documentation](https://docs.aws.amazon.com/codebuild/)
- [BuildSpec Reference](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html)
- [AWS App Runner Documentation](https://docs.aws.amazon.com/apprunner/)
- [GitHub Integration with CodeBuild](https://docs.aws.amazon.com/codebuild/latest/userguide/sample-github-pull-request.html)
