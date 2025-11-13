# Lab 10.A: CodeCommit + CodeBuild - Automated Docker Image Build

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

## Architecture

```
Developer → git push → CodeCommit Repository
                            ↓
                      CodeBuild Project
                       (buildspec.yml)
                            ↓
                     Build Docker Image
                            ↓
                  Push to Amazon ECR
```

---

## Step 1 – Set Variables

```bash
# Set region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "REGION=$REGION"

# Set repository names
REPO_NAME="flask-joke-app"
ECR_REPO_NAME="flask-joke-app"

echo "REPO_NAME=$REPO_NAME"
echo "ECR_REPO_NAME=$ECR_REPO_NAME"

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"
```

---

## Step 2 – Create CodeCommit Repository

```bash
echo ""
echo "Creating CodeCommit repository..."

# Create repository
aws codecommit create-repository \
  --repository-name "$REPO_NAME" \
  --repository-description "Flask joke API for CI/CD demo" \
  --region "$REGION"

echo ""
echo "✅ CodeCommit repository created: $REPO_NAME"

# Get clone URL
CLONE_URL=$(aws codecommit get-repository \
  --repository-name "$REPO_NAME" \
  --region "$REGION" \
  --query 'repositoryMetadata.cloneUrlHttp' \
  --output text)

echo "Clone URL: $CLONE_URL"
```

---

## Step 3 – Configure Git Credentials

```bash
echo ""
echo "Configuring Git credentials for CodeCommit..."

# Install git-remote-codecommit (credential helper)
pip install git-remote-codecommit --quiet

# Configure Git user
git config --global user.name "AWS Student"
git config --global user.email "student@example.com"

echo "✅ Git configured for CodeCommit"
```

---

## Step 4 – Clone Repository and Create Application

```bash
echo ""
echo "Cloning repository..."

# Create workspace
mkdir -p /tmp/codecommit-lab
cd /tmp/codecommit-lab

# Clone repository (using codecommit:// protocol)
git clone codecommit://"$REGION"://"$REPO_NAME"

# Navigate to repo
cd "$REPO_NAME"

echo "✅ Repository cloned: $(pwd)"
```

---

## Step 5 – Create Flask Application

```bash
echo ""
echo "Creating Flask application..."

# Create app.py (simple joke API)
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

echo "✅ Flask application created: app.py"
```

---

## Step 6 – Create Requirements File

```bash
echo ""
echo "Creating requirements.txt..."

cat > requirements.txt <<'EOF'
Flask==3.0.0
gunicorn==21.2.0
EOF

echo "✅ Requirements file created"
```

---

## Step 7 – Create Dockerfile

```bash
echo ""
echo "Creating Dockerfile..."

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

echo "✅ Dockerfile created"
```

---

## Step 8 – Create BuildSpec for CodeBuild

```bash
echo ""
echo "Creating buildspec.yml for CodeBuild..."

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

echo "✅ buildspec.yml created"
```

---

## Step 9 – Commit and Push to CodeCommit

```bash
echo ""
echo "Committing files to CodeCommit..."

# Add all files
git add .

# Commit
git commit -m "Initial commit: Flask joke API with Docker"

# Push to CodeCommit
git push origin main

echo ""
echo "✅ Code pushed to CodeCommit"
```

---

## Step 10 – Create ECR Repository

```bash
echo ""
echo "Creating Amazon ECR repository..."

# Create ECR repository
aws ecr create-repository \
  --repository-name "$ECR_REPO_NAME" \
  --region "$REGION" \
  --image-scanning-configuration scanOnPush=true

echo ""
echo "✅ ECR repository created: $ECR_REPO_NAME"

# Get ECR URI
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}"
echo "ECR URI: $ECR_URI"
```

---

## Step 11 – Create IAM Role for CodeBuild

```bash
echo ""
echo "Creating IAM role for CodeBuild..."

# Create trust policy
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

# Create role
aws iam create-role \
  --role-name CodeBuildServiceRole \
  --assume-role-policy-document file://codebuild-trust-policy.json \
  --region "$REGION"

echo "✅ IAM role created: CodeBuildServiceRole"

# Create permissions policy
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

# Attach policy
aws iam put-role-policy \
  --role-name CodeBuildServiceRole \
  --policy-name CodeBuildPermissions \
  --policy-document file://codebuild-permissions.json

echo "✅ Permissions attached to role"

# Wait for role to propagate
echo "Waiting for IAM role to propagate..."
sleep 10
```

---

## Step 12 – Create CodeBuild Project

```bash
echo ""
echo "================================================"
echo "CREATING CODEBUILD PROJECT"
echo "================================================"
echo ""

# Create CodeBuild project configuration
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

# Create CodeBuild project
aws codebuild create-project \
  --cli-input-json file://codebuild-project.json \
  --region "$REGION"

echo ""
echo "✅ CodeBuild project created: flask-joke-app-build"
```

---

## Step 13 – Trigger First Build

```bash
echo ""
echo "Triggering first build..."

# Start build
BUILD_ID=$(aws codebuild start-build \
  --project-name flask-joke-app-build \
  --region "$REGION" \
  --query 'build.id' \
  --output text)

echo "BUILD_ID=$BUILD_ID"
echo ""
echo "Build started! Monitoring build progress..."
```

---

## Step 14 – Monitor Build Progress

```bash
echo ""
echo "Waiting for build to complete (3-5 minutes)..."

# Poll build status
while true; do
    BUILD_STATUS=$(aws codebuild batch-get-builds \
      --ids "$BUILD_ID" \
      --region "$REGION" \
      --query 'builds[0].buildStatus' \
      --output text)
    
    echo "Build status: $BUILD_STATUS"
    
    if [ "$BUILD_STATUS" = "SUCCEEDED" ]; then
        echo ""
        echo "✅ Build succeeded!"
        break
    elif [ "$BUILD_STATUS" = "FAILED" ] || [ "$BUILD_STATUS" = "STOPPED" ]; then
        echo ""
        echo "❌ Build failed or was stopped"
        break
    fi
    
    sleep 15
done
```

---

## Step 15 – View Build Logs

```bash
echo ""
echo "Viewing build logs..."

# Get log group and stream
LOG_INFO=$(aws codebuild batch-get-builds \
  --ids "$BUILD_ID" \
  --region "$REGION" \
  --query 'builds[0].logs.{group:groupName,stream:streamName}' \
  --output json)

LOG_GROUP=$(echo "$LOG_INFO" | jq -r '.group')
LOG_STREAM=$(echo "$LOG_INFO" | jq -r '.stream')

echo "Log Group: $LOG_GROUP"
echo "Log Stream: $LOG_STREAM"
echo ""

# Get last 20 log events
aws logs get-log-events \
  --log-group-name "$LOG_GROUP" \
  --log-stream-name "$LOG_STREAM" \
  --region "$REGION" \
  --limit 20 \
  --query 'events[*].message' \
  --output text

echo ""
echo "Full logs available in CloudWatch: /aws/codebuild/flask-joke-app-build"
```

---

## Step 16 – Verify Image in ECR

```bash
echo ""
echo "Verifying Docker image in ECR..."

# List images in ECR
aws ecr describe-images \
  --repository-name "$ECR_REPO_NAME" \
  --region "$REGION" \
  --query 'imageDetails[*].{Tags:imageTags,Pushed:imagePushedAt,Size:imageSizeInBytes}' \
  --output table

echo ""
echo "✅ Docker image successfully built and pushed to ECR"
```

---

## Step 17 – Make Code Change and Trigger Build

```bash
echo ""
echo "================================================"
echo "TESTING AUTOMATED BUILD ON CODE CHANGE"
echo "================================================"
echo ""

# Add new joke to app.py
cd /tmp/codecommit-lab/"$REPO_NAME"

# Update app.py with new joke
cat >> app.py <<'EOF'

# New joke added during CI/CD demo
jokes.append("Why do Python programmers prefer snake_case? Because camelCase is too humpy!")
EOF

# Commit and push
git add app.py
git commit -m "Add new Python joke"
git push origin main

echo ""
echo "✅ Code change pushed to CodeCommit"
echo "CodeBuild will automatically trigger a new build"
```

---

## Step 18 – Monitor Automatic Build

```bash
echo ""
echo "Waiting for automatic build to trigger (30 seconds)..."
sleep 30

# Get latest build
LATEST_BUILD=$(aws codebuild list-builds-for-project \
  --project-name flask-joke-app-build \
  --region "$REGION" \
  --query 'ids[0]' \
  --output text)

echo "Latest Build ID: $LATEST_BUILD"

# Check if new build was triggered
if [ "$LATEST_BUILD" != "$BUILD_ID" ]; then
    echo "✅ New build automatically triggered!"
    echo "Build ID: $LATEST_BUILD"
else
    echo "⚠️  Automatic trigger not configured (manual builds only)"
    echo "To enable: Configure webhook in CodeBuild project settings"
fi
```

---

## Step 19 – Cleanup

```bash
echo ""
echo "Cleaning up resources..."

# Delete CodeBuild project
aws codebuild delete-project \
  --name flask-joke-app-build \
  --region "$REGION"

echo "✅ CodeBuild project deleted"

# Delete ECR repository
aws ecr delete-repository \
  --repository-name "$ECR_REPO_NAME" \
  --region "$REGION" \
  --force

echo "✅ ECR repository deleted"

# Delete CodeCommit repository
aws codecommit delete-repository \
  --repository-name "$REPO_NAME" \
  --region "$REGION"

echo "✅ CodeCommit repository deleted"

# Delete IAM role and policy
aws iam delete-role-policy \
  --role-name CodeBuildServiceRole \
  --policy-name CodeBuildPermissions

aws iam delete-role \
  --role-name CodeBuildServiceRole

echo "✅ IAM role deleted"
echo ""
echo "All resources cleaned up!"
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
