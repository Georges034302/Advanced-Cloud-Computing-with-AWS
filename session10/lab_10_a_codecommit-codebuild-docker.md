# Lab 10.A: CodeCommit + CodeBuild - Automated Docker Image Build
<img width="1536" height="1024" alt="IMG10A" src="https://github.com/user-attachments/assets/7ca3374a-6590-4e8c-aa47-e9300501dee9" />

## Overview
This lab demonstrates AWS-native CI/CD by using CodeCommit for source control and CodeBuild to automatically build Docker images. You'll create a Git repository in AWS, commit a simple Python Flask application, and configure CodeBuild to build and push Docker images to Amazon ECR on every commit.

---

## Objectives
- Create AWS CodeCommit repository
- Clone repository and commit Python Flask application
- Create Amazon ECR repository for Docker images
- Configure CodeBuild project with buildspec.yml
- Automate Docker image build and push to ECR
- Trigger builds automatically on git push
- View build logs and artifacts

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Git installed (`git --version`)
- IAM permissions for CodeCommit, CodeBuild, ECR, IAM
- Region: ap-southeast-2

---

## Step 1 – Set Variables

```bash
# Set deployment region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Set repository names for CodeCommit and ECR
REPO_NAME="flask-joke-app"
ECR_REPO_NAME="flask-joke-app"

# Get AWS account ID for ECR URI
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "REGION=$REGION"
echo "REPO_NAME=$REPO_NAME"
echo "ECR_REPO_NAME=$ECR_REPO_NAME"
echo "ACCOUNT_ID=$ACCOUNT_ID"
```

---

## Step 2 – Create CodeCommit Repository

```bash
# Create CodeCommit repository for source control
aws codecommit create-repository \
  --repository-name "$REPO_NAME" \
  --repository-description "Flask joke API for CI/CD demo" \
  --region "$REGION"

# Get HTTP clone URL for repository
CLONE_URL=$(aws codecommit get-repository \
  --repository-name "$REPO_NAME" \
  --region "$REGION" \
  --query 'repositoryMetadata.cloneUrlHttp' \
  --output text)

echo "CLONE_URL=$CLONE_URL"
```

---

## Step 3 – Configure Git Credentials

```bash
# Install git-remote-codecommit credential helper for AWS authentication
pip install git-remote-codecommit --quiet

# Configure Git user information
git config --global user.name "AWS Student"
git config --global user.email "student@example.com"
```

---

## Step 4 – Clone Repository

```bash
# Get repository root directory
REPO_DIR=$(git rev-parse --show-toplevel)

# Create workspace directory in repo
WORKSPACE="$REPO_DIR/codecommit-lab"
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

# Clone CodeCommit repository using codecommit:// protocol
git clone codecommit://"$REGION"::"$REPO_NAME"
cd "$REPO_NAME"

echo "Workspace: $(pwd)"
```

---

## Step 5 – Create Flask Application

```bash
# Create Flask application with joke API endpoints
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
        "message": "Flask Joke API",
        "endpoints": {
            "/": "API info",
            "/joke": "Get random joke",
            "/health": "Health check"
        }
    })

@app.route('/joke')
def get_joke():
    return jsonify({
        "joke": random.choice(jokes)
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF
```

---

## Step 6 – Create Requirements File

```bash
# Create Python dependencies file
cat > requirements.txt <<'EOF'
Flask==3.0.0
gunicorn==21.2.0
EOF
```

---

## Step 7 – Create Dockerfile

```bash
# Create Dockerfile for containerizing Flask application
cat > Dockerfile <<'EOF'
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Expose port
EXPOSE 5000

# Run application with gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
EOF
```

---

## Step 8 – Create BuildSpec for CodeBuild

```bash
# Create buildspec.yml defining build phases for CodeBuild
cat > buildspec.yml <<EOF
version: 0.2

phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
      - REPOSITORY_URI=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO_NAME
      - COMMIT_HASH=\$(echo \$CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)
      - IMAGE_TAG=\${COMMIT_HASH:=latest}
      - echo Building image with tag \$IMAGE_TAG

  build:
    commands:
      - echo Build started on \$(date)
      - echo Building Docker image...
      - docker build -t \$REPOSITORY_URI:latest .
      - docker tag \$REPOSITORY_URI:latest \$REPOSITORY_URI:\$IMAGE_TAG

  post_build:
    commands:
      - echo Build completed on \$(date)
      - echo Pushing Docker images...
      - docker push \$REPOSITORY_URI:latest
      - docker push \$REPOSITORY_URI:\$IMAGE_TAG
      - echo Image pushed to \$REPOSITORY_URI:\$IMAGE_TAG

artifacts:
  files:
    - '**/*'
EOF
```

---

## Step 9 – Commit and Push to CodeCommit

```bash
# Stage all files for commit
git add .

# Commit files with descriptive message
git commit -m "Initial commit: Flask joke API with Docker"

# Push to CodeCommit main branch
git push origin main
```

---

## Step 10 – Create ECR Repository

```bash
# Create ECR repository with image scanning enabled
aws ecr create-repository \
  --repository-name "$ECR_REPO_NAME" \
  --region "$REGION" \
  --image-scanning-configuration scanOnPush=true

# Construct ECR repository URI
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo "ECR_URI=$ECR_URI"
```

---

## Step 11 – Create IAM Role for CodeBuild

```bash
# Create trust policy allowing CodeBuild service to assume role
cat > codebuild-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codebuild.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role for CodeBuild
aws iam create-role \
  --role-name CodeBuildServiceRole \
  --assume-role-policy-document file://codebuild-trust-policy.json \
  --region "$REGION"

# Create permissions policy for CloudWatch Logs, ECR, and CodeCommit
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
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "codecommit:GitPull"
      ],
      "Resource": "arn:aws:codecommit:${REGION}:${ACCOUNT_ID}:${REPO_NAME}"
    }
  ]
}
EOF

# Attach permissions policy to IAM role
aws iam put-role-policy \
  --role-name CodeBuildServiceRole \
  --policy-name CodeBuildPermissions \
  --policy-document file://codebuild-permissions.json

# Wait for IAM role to propagate globally
echo "Waiting for IAM role propagation..."
sleep 10
```

---

## Step 12 – Create CodeBuild Project

```bash
# Create CodeBuild project configuration JSON
cat > codebuild-project.json <<EOF
{
  "name": "flask-joke-app-build",
  "description": "Build Docker image for Flask joke API",
  "source": {
    "type": "CODECOMMIT",
    "location": "https://git-codecommit.${REGION}.amazonaws.com/v1/repos/${REPO_NAME}"
  },
  "artifacts": {
    "type": "NO_ARTIFACTS"
  },
  "environment": {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/standard:7.0",
    "computeType": "BUILD_GENERAL1_SMALL",
    "privilegedMode": true,
    "environmentVariables": [
      {
        "name": "AWS_DEFAULT_REGION",
        "value": "${REGION}",
        "type": "PLAINTEXT"
      },
      {
        "name": "AWS_ACCOUNT_ID",
        "value": "${ACCOUNT_ID}",
        "type": "PLAINTEXT"
      },
      {
        "name": "IMAGE_REPO_NAME",
        "value": "${ECR_REPO_NAME}",
        "type": "PLAINTEXT"
      }
    ]
  },
  "serviceRole": "arn:aws:iam::${ACCOUNT_ID}:role/CodeBuildServiceRole"
}
EOF

# Create CodeBuild project from JSON configuration
aws codebuild create-project \
  --cli-input-json file://codebuild-project.json \
  --region "$REGION"
```

---

## Step 13 – Trigger First Build

```bash
# Start CodeBuild project build and capture build ID
BUILD_ID=$(aws codebuild start-build \
  --project-name flask-joke-app-build \
  --region "$REGION" \
  --query 'build.id' \
  --output text)

echo "BUILD_ID=$BUILD_ID"
```

---

## Step 14 – Monitor Build Progress

```bash
# Poll build status every 15 seconds until completion
echo "Waiting for build to complete (3-5 minutes)..."

while true; do
    BUILD_STATUS=$(aws codebuild batch-get-builds \
      --ids "$BUILD_ID" \
      --region "$REGION" \
      --query 'builds[0].buildStatus' \
      --output text)
    
    echo "Build status: $BUILD_STATUS"
    
    if [ "$BUILD_STATUS" = "SUCCEEDED" ]; then
        echo "✅ Build succeeded!"
        break
    elif [ "$BUILD_STATUS" = "FAILED" ] || [ "$BUILD_STATUS" = "STOPPED" ]; then
        echo "❌ Build failed or was stopped"
        break
    fi
    
    sleep 15
done
```

---

## Step 15 – View Build Logs

```bash
# Get CloudWatch Logs information from build
LOG_INFO=$(aws codebuild batch-get-builds \
  --ids "$BUILD_ID" \
  --region "$REGION" \
  --query 'builds[0].logs.{group:groupName,stream:streamName}' \
  --output json)

# Extract log group and stream names
LOG_GROUP=$(echo "$LOG_INFO" | jq -r '.group')
LOG_STREAM=$(echo "$LOG_INFO" | jq -r '.stream')

echo "LOG_GROUP=$LOG_GROUP"
echo "LOG_STREAM=$LOG_STREAM"

# Retrieve last 20 log events from CloudWatch
aws logs get-log-events \
  --log-group-name "$LOG_GROUP" \
  --log-stream-name "$LOG_STREAM" \
  --region "$REGION" \
  --limit 20 \
  --query 'events[*].message' \
  --output text
```

---

## Step 16 – Verify Image in ECR

```bash
# List Docker images in ECR repository with tags and metadata
aws ecr describe-images \
  --repository-name "$ECR_REPO_NAME" \
  --region "$REGION" \
  --query 'imageDetails[*].{Tags:imageTags,Pushed:imagePushedAt,Size:imageSizeInBytes}' \
  --output table
```

---

## Step 17 – Make Code Change and Trigger Build

```bash
# Navigate to repository directory
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR/codecommit-lab/$REPO_NAME"

# Append new joke to existing jokes list
cat >> app.py <<'EOF'

# New joke added during CI/CD demo
jokes.append("Why do Python programmers prefer snake_case? Because camelCase is too humpy!")
EOF

# Commit and push code change
git add app.py
git commit -m "Add new Python joke"
git push origin main

echo "Note: CodeBuild webhook must be configured for automatic triggers"
```

---

## Step 18 – Monitor Automatic Build

```bash
# Wait for potential automatic build trigger
echo "Waiting for automatic build to trigger (30 seconds)..."
sleep 30

# Get most recent build ID for this project
LATEST_BUILD=$(aws codebuild list-builds-for-project \
  --project-name flask-joke-app-build \
  --region "$REGION" \
  --query 'ids[0]' \
  --output text)

echo "LATEST_BUILD=$LATEST_BUILD"

# Check if new build was automatically triggered
if [ "$LATEST_BUILD" != "$BUILD_ID" ]; then
    echo "✅ New build automatically triggered: $LATEST_BUILD"
else
    echo "⚠️ Automatic trigger not configured (webhook required)"
fi
```

---

## Step 19 – Cleanup

```bash
# Delete CodeBuild project
aws codebuild delete-project \
  --name flask-joke-app-build \
  --region "$REGION"

# Delete ECR repository and all images
aws ecr delete-repository \
  --repository-name "$ECR_REPO_NAME" \
  --region "$REGION" \
  --force

# Delete CodeCommit repository
aws codecommit delete-repository \
  --repository-name "$REPO_NAME" \
  --region "$REGION"

# Delete IAM role policy and role
aws iam delete-role-policy \
  --role-name CodeBuildServiceRole \
  --policy-name CodeBuildPermissions

aws iam delete-role \
  --role-name CodeBuildServiceRole

# Remove local workspace directory
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR"
rm -rf codecommit-lab

echo "✅ Cleanup complete"
```

---

## Summary

In this lab, you have:
- Created AWS CodeCommit repository for source control
- Committed Flask application with Dockerfile and buildspec.yml
- Created Amazon ECR repository for Docker images
- Configured IAM role with necessary permissions for CodeBuild
- Created CodeBuild project to build Docker images automatically
- Triggered manual build and monitored progress
- Verified Docker image pushed to ECR successfully
- Made code changes and tested CI/CD workflow
- Viewed build logs in CloudWatch Logs

**Key Takeaways:**
- **CodeCommit**: AWS-native Git repository (alternative to GitHub)
- **CodeBuild**: Managed build service (no build servers to manage)
- **buildspec.yml**: Defines build steps (pre_build, build, post_build)
- **ECR**: Container registry for Docker images
- **Automated Builds**: Trigger on every git push (CI/CD)

**CI/CD Workflow:**
```
Code Change → git push → CodeCommit → CodeBuild → Docker Build → Push to ECR
```

---

## Best Practices

**CodeCommit:**
- Use git-remote-codecommit for credential management
- Enable branch protection for main branch
- Use pull requests for code review
- Tag releases for version control

**CodeBuild:**
- Use specific image versions (standard:7.0, not :latest)
- Store secrets in AWS Secrets Manager (not in buildspec)
- Enable privileged mode only when needed (Docker builds)
- Use build cache to speed up builds

**buildspec.yml:**
- Organize commands into logical phases
- Use environment variables for flexibility
- Fail fast (exit on error)
- Generate artifacts for deployment

**ECR:**
- Enable image scanning for vulnerabilities
- Use lifecycle policies to clean old images
- Tag images with commit hash and latest
- Encrypt images at rest

**Security:**
- Use IAM roles (not access keys)
- Follow least-privilege principle
- Enable CloudTrail for audit logging
- Encrypt build artifacts

---

## Production Enhancements

1. **Automated Triggers**
   ```bash
   # Enable webhook for automatic builds
   aws codebuild create-webhook \
     --project-name flask-joke-app-build \
     --filter-groups '[[{"type":"EVENT","pattern":"PUSH"}]]'
   ```

2. **Build Notifications**
   ```yaml
   # Add to buildspec.yml post_build
   - aws sns publish \
       --topic-arn $SNS_TOPIC \
       --message "Build completed: $CODEBUILD_BUILD_ID"
   ```

3. **Multi-Stage Dockerfile**
   ```dockerfile
   # Builder stage
   FROM python:3.11-slim AS builder
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --user -r requirements.txt
   
   # Runtime stage
   FROM python:3.11-slim
   COPY --from=builder /root/.local /root/.local
   COPY app.py .
   CMD ["python", "app.py"]
   ```

4. **Build Cache**
   ```json
   {
     "cache": {
       "type": "S3",
       "location": "my-build-cache-bucket"
     }
   }
   ```

5. **Environment-Specific Builds**
   ```yaml
   # Use environment variables in buildspec
   - if [ "$ENV" = "prod" ]; then IMAGE_TAG=prod-$COMMIT_HASH; fi
   ```

---

## Troubleshooting

**CodeCommit clone fails:**
- Install git-remote-codecommit: `pip install git-remote-codecommit`
- Check IAM permissions for codecommit:GitPull
- Use codecommit:// protocol (not https://)

**CodeBuild fails with Docker error:**
- Ensure privilegedMode is set to true
- Check ECR permissions in IAM role
- Verify Docker image exists

**Build fails at ECR login:**
- Check IAM role has ecr:GetAuthorizationToken
- Verify ECR repository exists
- Check region matches in buildspec

**Image not pushed to ECR:**
- Check post_build phase completed
- Verify ECR URI is correct
- Check CloudWatch Logs for errors

---

## Additional Resources

- [AWS CodeCommit Documentation](https://docs.aws.amazon.com/codecommit/)
- [AWS CodeBuild Documentation](https://docs.aws.amazon.com/codebuild/)
- [BuildSpec Reference](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html)
- [Amazon ECR Documentation](https://docs.aws.amazon.com/ecr/)
- [Docker Build Best Practices](https://docs.docker.com/develop/dev-best-practices/)
