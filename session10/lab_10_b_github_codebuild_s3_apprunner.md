# Lab 10.B: GitHub → CodeBuild → ECR → App Runner (Multi-API Pipeline)

<img width="1200" height="634" alt="IMG" src="https://github.com/user-attachments/assets/9f2d9df8-99e8-45b2-a1a3-00d75ae6cd9d" />

## Overview
This lab demonstrates building a complete CI/CD pipeline for multiple microservices using AWS CodeBuild and App Runner. You'll create two Flask APIs (Student and Report), containerize them, and deploy to App Runner from ECR images. This showcases AWS-native containerized deployment with automated testing.

---

## Objectives
- Structure a multi-API GitHub repository with microservices
- Implement Flask REST APIs with pytest unit tests
- Configure CodeBuild to build, test, and push Docker images
- Deploy multiple App Runner services from ECR
- Understand container-based CI/CD workflows

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Git installed (`git --version`)
- GitHub account with repository access
- IAM permissions for CodeBuild, ECR, App Runner, S3, IAM
- Region: ap-southeast-2

---

## Architecture

```
GitHub → CodeBuild (test + build + push) → ECR → App Runner Services
                         ↓
                        S3 (artifacts)
```

**Pipeline Flow:**
1. GitHub hosts source code for both APIs
2. CodeBuild runs tests, builds Docker images, pushes to ECR
3. S3 stores build artifacts (imagedefinitions.json)
4. App Runner deploys two services from ECR images

---

## Step 1 – Set Variables

```bash
# Set AWS region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Dynamically get GitHub repository info
GITHUB_URL=$(git remote get-url origin)
GITHUB_OWNER=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/]([^/]+)/.*|\1|')
GITHUB_REPO=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/][^/]+/([^.]+)(\.git)?$|\1|')

# Application configuration
STUDENT_API_FOLDER="student_api"
REPORT_API_FOLDER="report_api"
STUDENT_REPO_NAME="student-api-repo"
REPORT_REPO_NAME="report-api-repo"
STUDENT_SERVICE_NAME="student-api-service"
REPORT_SERVICE_NAME="report-api-service"
CODEBUILD_PROJECT_NAME="multi-api-pipeline"

# Get AWS account ID and set bucket name
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
# Navigate to repository root
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR"

# Sync with remote
git checkout main
git pull origin main
```

---

## Step 3 – Create API Directories

```bash
# Create folder structure for both APIs
mkdir -p "$STUDENT_API_FOLDER" "$REPORT_API_FOLDER"
```

---

## Step 4 – Create Student API

```bash
# Create Student API application
cat > "${STUDENT_API_FOLDER}/app.py" <<'EOF'
from flask import Flask, jsonify

app = Flask(__name__)

STUDENTS = [
    {"id": 1, "name": "Alice", "mark": 85},
    {"id": 2, "name": "Bob", "mark": 67},
    {"id": 3, "name": "Charlie", "mark": 92},
    {"id": 4, "name": "Diana", "mark": 58},
]

@app.route('/')
def index():
    return jsonify({"service": "student-api", "status": "running"})

@app.route('/students')
def get_students():
    return jsonify(STUDENTS)

@app.route('/students/<int:student_id>')
def get_student(student_id):
    for s in STUDENTS:
        if s["id"] == student_id:
            return jsonify(s)
    return jsonify({"error": "Student not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
EOF

# Create Student API tests
cat > "${STUDENT_API_FOLDER}/test_student_api.py" <<'EOF'
from app import app

def test_health():
    client = app.test_client()
    resp = client.get('/')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["service"] == "student-api"

def test_get_all_students():
    client = app.test_client()
    resp = client.get('/students')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1

def test_get_single_student():
    client = app.test_client()
    resp = client.get('/students/1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == 1
EOF
```

---

## Step 5 – Create Report API

```bash
# Create Report API application
cat > "${REPORT_API_FOLDER}/app.py" <<'EOF'
from flask import Flask, jsonify

app = Flask(__name__)

STUDENTS = [
    {"id": 1, "name": "Alice", "mark": 85},
    {"id": 2, "name": "Bob", "mark": 67},
    {"id": 3, "name": "Charlie", "mark": 92},
    {"id": 4, "name": "Diana", "mark": 58},
]

def compute_grade(mark):
    if mark >= 85:
        return "HD"
    elif mark >= 75:
        return "D"
    elif mark >= 65:
        return "C"
    elif mark >= 50:
        return "P"
    else:
        return "F"

@app.route('/')
def index():
    return jsonify({"service": "report-api", "status": "running"})

@app.route('/reports')
def all_reports():
    reports = []
    for s in STUDENTS:
        reports.append({
            "id": s["id"],
            "name": s["name"],
            "mark": s["mark"],
            "grade": compute_grade(s["mark"])
        })
    return jsonify(reports)

@app.route('/report/<int:student_id>')
def report_for_student(student_id):
    for s in STUDENTS:
        if s["id"] == student_id:
            return jsonify({
                "id": s["id"],
                "name": s["name"],
                "mark": s["mark"],
                "grade": compute_grade(s["mark"])
            })
    return jsonify({"error": "Student not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
EOF

# Create Report API tests
cat > "${REPORT_API_FOLDER}/test_report_api.py" <<'EOF'
from app import app, compute_grade

def test_grade_mapping():
    assert compute_grade(90) == "HD"
    assert compute_grade(78) == "D"
    assert compute_grade(68) == "C"
    assert compute_grade(55) == "P"
    assert compute_grade(40) == "F"

def test_reports_endpoint():
    client = app.test_client()
    resp = client.get('/reports')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "grade" in data[0]

def test_single_report():
    client = app.test_client()
    resp = client.get('/report/1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == 1
    assert "grade" in data
EOF
```

---

## Step 6 – Create Requirements File

```bash
# Python dependencies for both APIs
cat > requirements.txt <<'EOF'
Flask==2.3.0
gunicorn==21.2.0
pytest==8.3.0
EOF
```

---

## Step 7 – Create Dockerfiles

```bash
# Dockerfile for Student API
cat > Dockerfile.student <<'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Student API code
COPY student_api/ ./student_api/

WORKDIR /app/student_api

# Run with gunicorn
ENV PORT=8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
EOF

# Dockerfile for Report API
cat > Dockerfile.report <<'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Report API code
COPY report_api/ ./report_api/

WORKDIR /app/report_api

# Run with gunicorn
ENV PORT=8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
EOF
```

---

## Step 8 – Create BuildSpec for CodeBuild

```bash
# CodeBuild build specification
cat > buildspec.yml <<EOF
version: 0.2

env:
  variables:
    AWS_DEFAULT_REGION: ${REGION}
    ECR_STUDENT_REPO: ${STUDENT_REPO_NAME}
    ECR_REPORT_REPO: ${REPORT_REPO_NAME}

phases:
  install:
    runtime-versions:
      python: 3.11
    commands:
      # Install Python dependencies
      - pip install --no-cache-dir -r requirements.txt

  pre_build:
    commands:
      # Get AWS account ID
      - ACCOUNT_ID=\$(aws sts get-caller-identity --query Account --output text)
      
      # Build ECR image URIs
      - STUDENT_URI=\${ACCOUNT_ID}.dkr.ecr.\${AWS_DEFAULT_REGION}.amazonaws.com/\${ECR_STUDENT_REPO}
      - REPORT_URI=\${ACCOUNT_ID}.dkr.ecr.\${AWS_DEFAULT_REGION}.amazonaws.com/\${ECR_REPORT_REPO}
      
      # Login to ECR
      - aws ecr get-login-password --region \$AWS_DEFAULT_REGION | docker login --username AWS --password-stdin \${ACCOUNT_ID}.dkr.ecr.\${AWS_DEFAULT_REGION}.amazonaws.com

  build:
    commands:
      # Run tests for both APIs
      - pytest -v
      
      # Build Docker image for Student API
      - docker build -t \${STUDENT_URI}:latest -f Dockerfile.student .
      
      # Build Docker image for Report API
      - docker build -t \${REPORT_URI}:latest -f Dockerfile.report .

  post_build:
    commands:
      # Push images to ECR
      - docker push \${STUDENT_URI}:latest
      - docker push \${REPORT_URI}:latest
      
      # Create image definitions artifact
      - printf '[{"name":"student-api","imageUri":"%s"},{"name":"report-api","imageUri":"%s"}]' \${STUDENT_URI}:latest \${REPORT_URI}:latest > imagedefinitions.json

artifacts:
  files:
    - imagedefinitions.json
  discard-paths: yes
EOF
```

---

## Step 9 – Commit and Push to GitHub

```bash
# Add all files to git
git add .

# Commit changes
git commit -m "Add Student and Report APIs with CI/CD pipeline"

# Push to GitHub
git push origin main
```

---

## Step 10 – Create S3 Bucket for Artifacts

```bash
# Create S3 bucket for CodeBuild artifacts
if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$ARTIFACT_BUCKET" \
      --region "$REGION"
else
    aws s3api create-bucket \
      --bucket "$ARTIFACT_BUCKET" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi

echo "ARTIFACT_BUCKET=$ARTIFACT_BUCKET"
```

---

## Step 11 – Create ECR Repositories

```bash
# Create ECR repository for Student API
aws ecr create-repository \
  --repository-name "$STUDENT_REPO_NAME" \
  --region "$REGION"

# Create ECR repository for Report API
aws ecr create-repository \
  --repository-name "$REPORT_REPO_NAME" \
  --region "$REGION"

# Get repository URIs
STUDENT_ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${STUDENT_REPO_NAME}"
REPORT_ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPORT_REPO_NAME}"

echo "STUDENT_ECR_URI=$STUDENT_ECR_URI"
echo "REPORT_ECR_URI=$REPORT_ECR_URI"
```

---

## Step 12 – Create IAM Role for CodeBuild

```bash
# Create trust policy for CodeBuild
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

# Create IAM role
aws iam create-role \
  --role-name CodeBuildMultiApiRole \
  --assume-role-policy-document file://codebuild-trust-policy.json

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
        "ecr:CompleteLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:InitiateLayerUpload",
        "ecr:PutImage",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${ARTIFACT_BUCKET}",
        "arn:aws:s3:::${ARTIFACT_BUCKET}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    }
  ]
}
EOF

# Attach permissions policy to role
aws iam put-role-policy \
  --role-name CodeBuildMultiApiRole \
  --policy-name CodeBuildMultiApiPermissions \
  --policy-document file://codebuild-permissions.json

# Wait for IAM propagation
sleep 10
```

---

## Step 13 – Create CodeBuild Project

```bash
# Create CodeBuild project configuration
cat > codebuild-project.json <<EOF
{
  "name": "${CODEBUILD_PROJECT_NAME}",
  "description": "Build and test Student + Report APIs, push to ECR",
  "source": {
    "type": "GITHUB",
    "location": "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}.git",
    "gitCloneDepth": 1,
    "buildspec": "buildspec.yml"
  },
  "artifacts": {
    "type": "S3",
    "location": "${ARTIFACT_BUCKET}",
    "packaging": "ZIP",
    "path": "builds"
  },
  "environment": {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/standard:7.0",
    "computeType": "BUILD_GENERAL1_SMALL",
    "privilegedMode": true,
    "environmentVariables": [
      {"name": "AWS_DEFAULT_REGION", "value": "${REGION}"},
      {"name": "ECR_STUDENT_REPO", "value": "${STUDENT_REPO_NAME}"},
      {"name": "ECR_REPORT_REPO", "value": "${REPORT_REPO_NAME}"}
    ]
  },
  "serviceRole": "arn:aws:iam::${ACCOUNT_ID}:role/CodeBuildMultiApiRole"
}
EOF

# Create the CodeBuild project
aws codebuild create-project \
  --cli-input-json file://codebuild-project.json \
  --region "$REGION"
```

---

## Step 14 – Authorize GitHub Access

**Manual Step (AWS Console):**
1. Go to AWS Console → CodeBuild → Build Projects
2. Select `multi-api-pipeline`
3. Click Edit → Source
4. Click "Connect to GitHub" and authorize
5. Save changes

```bash
read -p "Press Enter after completing GitHub authorization..."
```

---

## Step 15 – Trigger Build

```bash
# Start CodeBuild build
BUILD_ID=$(aws codebuild start-build \
  --project-name "$CODEBUILD_PROJECT_NAME" \
  --source-version main \
  --region "$REGION" \
  --query 'build.id' \
  --output text)

echo "BUILD_ID=$BUILD_ID"

# Monitor build status
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

## Step 16 – Create IAM Role for App Runner

```bash
# Create trust policy for App Runner
cat > apprunner-trust-policy.json <<'EOF'
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

# Create IAM role for App Runner ECR access
aws iam create-role \
  --role-name AppRunnerECRAccessRole \
  --assume-role-policy-document file://apprunner-trust-policy.json

# Attach AWS managed policy for ECR access
aws iam attach-role-policy \
  --role-name AppRunnerECRAccessRole \
  --policy-arn arn:aws:iam::aws:policy/AWSAppRunnerServicePolicyForECRAccess

# Wait for IAM propagation
sleep 10
```

---

## Step 17 – Create App Runner Services

```bash
# Create Student API service configuration
cat > apprunner-student.json <<EOF
{
  "ServiceName": "${STUDENT_SERVICE_NAME}",
  "SourceConfiguration": {
    "AuthenticationConfiguration": {
      "AccessRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/AppRunnerECRAccessRole"
    },
    "AutoDeploymentsEnabled": false,
    "ImageRepository": {
      "ImageIdentifier": "${STUDENT_ECR_URI}:latest",
      "ImageConfiguration": {
        "Port": "8000"
      },
      "ImageRepositoryType": "ECR"
    }
  },
  "InstanceConfiguration": {
    "Cpu": "1 vCPU",
    "Memory": "2 GB"
  }
}
EOF

# Create Student API service
STUDENT_SERVICE_ARN=$(aws apprunner create-service \
  --cli-input-json file://apprunner-student.json \
  --region "$REGION" \
  --query 'Service.ServiceArn' \
  --output text)

echo "STUDENT_SERVICE_ARN=$STUDENT_SERVICE_ARN"

# Create Report API service configuration
cat > apprunner-report.json <<EOF
{
  "ServiceName": "${REPORT_SERVICE_NAME}",
  "SourceConfiguration": {
    "AuthenticationConfiguration": {
      "AccessRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/AppRunnerECRAccessRole"
    },
    "AutoDeploymentsEnabled": false,
    "ImageRepository": {
      "ImageIdentifier": "${REPORT_ECR_URI}:latest",
      "ImageConfiguration": {
        "Port": "8000"
      },
      "ImageRepositoryType": "ECR"
    }
  },
  "InstanceConfiguration": {
    "Cpu": "1 vCPU",
    "Memory": "2 GB"
  }
}
EOF

# Create Report API service
REPORT_SERVICE_ARN=$(aws apprunner create-service \
  --cli-input-json file://apprunner-report.json \
  --region "$REGION" \
  --query 'Service.ServiceArn' \
  --output text)

echo "REPORT_SERVICE_ARN=$REPORT_SERVICE_ARN"
```

---

## Step 18 – Wait for Services to be Ready

```bash
# Wait for Student API service
echo "Waiting for Student API service..."
while true; do
  STUDENT_STATUS=$(aws apprunner describe-service \
    --service-arn "$STUDENT_SERVICE_ARN" \
    --region "$REGION" \
    --query 'Service.Status' \
    --output text)
  
  echo "Student API status: $STUDENT_STATUS"
  [ "$STUDENT_STATUS" = "RUNNING" ] && break
  [ "$STUDENT_STATUS" = "CREATE_FAILED" ] && echo "❌ Student API deployment failed" && break
  sleep 10
done

# Get Student API URL
STUDENT_URL=$(aws apprunner describe-service \
  --service-arn "$STUDENT_SERVICE_ARN" \
  --region "$REGION" \
  --query 'Service.ServiceUrl' \
  --output text)

echo "STUDENT_URL=$STUDENT_URL"

# Wait for Report API service
echo "Waiting for Report API service..."
while true; do
  REPORT_STATUS=$(aws apprunner describe-service \
    --service-arn "$REPORT_SERVICE_ARN" \
    --region "$REGION" \
    --query 'Service.Status' \
    --output text)
  
  echo "Report API status: $REPORT_STATUS"
  [ "$REPORT_STATUS" = "RUNNING" ] && break
  [ "$REPORT_STATUS" = "CREATE_FAILED" ] && echo "❌ Report API deployment failed" && break
  sleep 10
done

# Get Report API URL
REPORT_URL=$(aws apprunner describe-service \
  --service-arn "$REPORT_SERVICE_ARN" \
  --region "$REGION" \
  --query 'Service.ServiceUrl' \
  --output text)

echo "REPORT_URL=$REPORT_URL"
```

---

## Step 19 – Test Applications

```bash
# Test Student API
echo "Testing Student API:"
curl -s "https://$STUDENT_URL/" | jq .
curl -s "https://$STUDENT_URL/students" | jq .
curl -s "https://$STUDENT_URL/students/1" | jq .

# Test Report API
echo -e "\nTesting Report API:"
curl -s "https://$REPORT_URL/" | jq .
curl -s "https://$REPORT_URL/reports" | jq .
curl -s "https://$REPORT_URL/report/1" | jq .

# Display URLs for browser testing
echo -e "\n📱 Student API URLs:"
echo "https://$STUDENT_URL/"
echo "https://$STUDENT_URL/students"

echo -e "\n📱 Report API URLs:"
echo "https://$REPORT_URL/"
echo "https://$REPORT_URL/reports"
```

---

## Step 20 – Cleanup

```bash
# Delete App Runner services
aws apprunner delete-service \
  --service-arn "$STUDENT_SERVICE_ARN" \
  --region "$REGION"

aws apprunner delete-service \
  --service-arn "$REPORT_SERVICE_ARN" \
  --region "$REGION"

# Wait for services to delete
echo "Waiting for services to delete..."
sleep 30

# Delete ECR repositories (with all images)
aws ecr delete-repository \
  --repository-name "$STUDENT_REPO_NAME" \
  --force \
  --region "$REGION"

aws ecr delete-repository \
  --repository-name "$REPORT_REPO_NAME" \
  --force \
  --region "$REGION"

# Delete CodeBuild project
aws codebuild delete-project \
  --name "$CODEBUILD_PROJECT_NAME" \
  --region "$REGION"

# Delete IAM roles and policies
aws iam detach-role-policy \
  --role-name AppRunnerECRAccessRole \
  --policy-arn arn:aws:iam::aws:policy/AWSAppRunnerServicePolicyForECRAccess

aws iam delete-role --role-name AppRunnerECRAccessRole

aws iam delete-role-policy \
  --role-name CodeBuildMultiApiRole \
  --policy-name CodeBuildMultiApiPermissions

aws iam delete-role --role-name CodeBuildMultiApiRole

# Empty and delete S3 bucket
aws s3 rm "s3://$ARTIFACT_BUCKET" --recursive
aws s3api delete-bucket \
  --bucket "$ARTIFACT_BUCKET" \
  --region "$REGION"

# Remove application directories
cd "$REPO_DIR"
rm -rf "$STUDENT_API_FOLDER" "$REPORT_API_FOLDER"
git rm -r "$STUDENT_API_FOLDER" "$REPORT_API_FOLDER"

# Remove Docker and build files
rm -f Dockerfile.student Dockerfile.report buildspec.yml requirements.txt
rm -f codebuild-*.json apprunner-*.json
git add .
git commit -m "Cleanup: Remove multi-API pipeline"
git push origin main

echo "✅ Cleanup complete"
```

---

## Summary

In this lab, you:
- Created two Flask microservices (Student API and Report API)
- Implemented pytest unit tests for both APIs
- Built Docker images for each service
- Configured CodeBuild to test, build, and push to ECR
- Deployed two independent App Runner services
- Tested endpoints and verified the CI/CD pipeline

**Key Takeaways:**
- **Multi-Service Architecture**: Two independent APIs in one repository
- **Container-Based Deployment**: ECR → App Runner workflow
- **Automated Testing**: pytest runs before building images
- **Build Artifacts**: S3 stores imagedefinitions.json for deployment tracking
- **Fully Managed**: App Runner handles scaling and load balancing

**CI/CD Workflow:**
```
GitHub → CodeBuild (test + build) → ECR → App Runner
                ↓
              S3 (artifacts)
```

---

## Best Practices

**CodeBuild Configuration:**
- Use privileged mode for Docker builds
- Set specific runtime versions (python: 3.11)
- Store build artifacts in S3 for audit trail
- Use environment variables for flexibility

**Docker Images:**
- Use slim base images for smaller size
- Copy only necessary files to reduce image size
- Use gunicorn for production WSGI server
- Set explicit working directories

**App Runner:**
- Start with 1 vCPU / 2 GB for testing
- Monitor metrics and adjust resources
- Use ECR for private container images
- Enable auto-deployments for continuous delivery

**Testing:**
- Run tests before building images
- Use lightweight pytest for API testing
- Test all critical endpoints
- Fail builds on test failures

---

## Troubleshooting

**CodeBuild fails during Docker build:**
- Ensure privilegedMode is set to true
- Verify Dockerfiles are in repository root
- Check ECR permissions in IAM role

**ECR push fails:**
- Verify ECR repositories exist
- Check IAM role has ECR push permissions
- Ensure ECR login command succeeds

**App Runner deployment fails:**
- Verify image exists in ECR with :latest tag
- Check AccessRoleArn for ECR access
- Ensure port 8000 is exposed in Dockerfile
- Review CloudWatch logs for application errors

**Tests fail in CodeBuild:**
- Check requirements.txt includes pytest
- Verify test files are named test_*.py
- Review pytest output for specific failures
- Ensure Flask test_client is used correctly

---

## Additional Resources

- [AWS CodeBuild Documentation](https://docs.aws.amazon.com/codebuild/)
- [Amazon ECR Documentation](https://docs.aws.amazon.com/ecr/)
- [AWS App Runner Documentation](https://docs.aws.amazon.com/apprunner/)
- [Flask Testing Documentation](https://flask.palletsprojects.com/en/2.3.x/testing/)
- [pytest Documentation](https://docs.pytest.org/)
