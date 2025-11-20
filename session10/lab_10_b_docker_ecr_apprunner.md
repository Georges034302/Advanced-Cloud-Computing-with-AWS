# Lab 10.B: GitHub → Docker → ECR → App Runner (Multi-API Deployment)

<img width="1536" height="834" alt="IMG" src="https://github.com/user-attachments/assets/ff010b78-bfff-4c52-b984-d7296a5664d1" />

## Overview
This lab demonstrates building and deploying multiple microservices to AWS App Runner. You'll create two Flask APIs (Student and Report), containerize them locally, push to ECR, and deploy to App Runner. This showcases containerized deployment with local development workflow.

---

## Objectives
- Structure a multi-API GitHub repository with microservices
- Implement Flask REST APIs with pytest unit tests
- Build and test Docker images locally
- Push container images to Amazon ECR
- Deploy multiple App Runner services from ECR
- Understand container-based deployment workflows

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Docker installed and running (`docker --version`)
- Git installed (`git --version`)
- GitHub account with repository access
- IAM permissions for ECR, App Runner, IAM
- Region: ap-southeast-2

---

## Architecture

```
GitHub (Source) → Local Docker Build → ECR → App Runner Services
                          ↓
                     pytest tests
```

**Deployment Flow:**
1. GitHub hosts source code for both APIs
2. Local environment builds and tests Docker images
3. Docker images pushed to Amazon ECR
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

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Build ECR repository URIs
STUDENT_ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${STUDENT_REPO_NAME}"
REPORT_ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPORT_REPO_NAME}"

# Display configuration
echo "REGION=$REGION"
echo "GITHUB_OWNER=$GITHUB_OWNER"
echo "GITHUB_REPO=$GITHUB_REPO"
echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "STUDENT_ECR_URI=$STUDENT_ECR_URI"
echo "REPORT_ECR_URI=$REPORT_ECR_URI"
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

## Step 8 – Commit and Push to GitHub

```bash
# Add all files to git
git add .

# Commit changes
git commit -m "Add Student and Report APIs with Docker configuration"

# Push to GitHub
git push origin main
```

---

## Step 9 – Create ECR Repositories

```bash
# Create ECR repository for Student API
aws ecr create-repository \
  --repository-name "$STUDENT_REPO_NAME" \
  --region "$REGION"

# Create ECR repository for Report API
aws ecr create-repository \
  --repository-name "$REPORT_REPO_NAME" \
  --region "$REGION"

# Display repository URIs (already set in Step 1)
echo "STUDENT_ECR_URI=$STUDENT_ECR_URI"
echo "REPORT_ECR_URI=$REPORT_ECR_URI"
```

---

## Step 10 – Run Local Tests

```bash
# Install Python dependencies locally
pip install -r requirements.txt

# Run tests for Student API
pytest -v student_api/test_student_api.py

# Run tests for Report API
pytest -v report_api/test_report_api.py

# ✅ Ensure all tests pass before building Docker images
```

---

## Step 11 – Build Docker Images Locally

```bash
# Build Docker image for Student API
# -t: Tag the image with ECR URI and 'latest' tag
# -f: Specify the Dockerfile to use
# .: Build context (current directory)
docker build -t "${STUDENT_ECR_URI}:latest" -f Dockerfile.student .

# Build Docker image for Report API
docker build -t "${REPORT_ECR_URI}:latest" -f Dockerfile.report .

# Verify images were built successfully
docker images | grep -E "student-api-repo|report-api-repo"
```

---

## Step 12 – Test Docker Images Locally (Optional)

```bash
# Test Student API container locally
# -d: Run in detached mode
# -p: Map container port 8000 to host port 8001
# --name: Give container a friendly name
docker run -d -p 8001:8000 --name student-api-test "${STUDENT_ECR_URI}:latest"

# Wait a few seconds for container to start
sleep 3

# Test Student API endpoints
curl http://localhost:8001/
curl http://localhost:8001/students
curl http://localhost:8001/students/1

# Stop and remove test container
docker stop student-api-test
docker rm student-api-test

# Test Report API container locally
docker run -d -p 8002:8000 --name report-api-test "${REPORT_ECR_URI}:latest"
sleep 3

# Test Report API endpoints
curl http://localhost:8002/
curl http://localhost:8002/reports
curl http://localhost:8002/report/1

# Stop and remove test container
docker stop report-api-test
docker rm report-api-test
```

---

## Step 13 – Login to Amazon ECR

```bash
# Get ECR login password and authenticate Docker client
# This command retrieves a temporary authentication token from ECR
# and pipes it to 'docker login' to authenticate with the ECR registry
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin \
  "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# ✅ You should see "Login Succeeded" message
```

---

## Step 14 – Push Docker Images to ECR

```bash
# Push Student API image to ECR
# This uploads all layers of the Docker image to ECR
docker push "${STUDENT_ECR_URI}:latest"

# Push Report API image to ECR
docker push "${REPORT_ECR_URI}:latest"

# Verify images in ECR
aws ecr describe-images \
  --repository-name "$STUDENT_REPO_NAME" \
  --region "$REGION"

aws ecr describe-images \
  --repository-name "$REPORT_REPO_NAME" \
  --region "$REGION"
```

---

## Step 15 – Create IAM Role for App Runner

```bash
# Create trust policy for App Runner
# This allows App Runner service to assume this role
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
# This policy allows App Runner to pull images from ECR
aws iam attach-role-policy \
  --role-name AppRunnerECRAccessRole \
  --policy-arn arn:aws:iam::aws:policy/AWSAppRunnerServicePolicyForECRAccess

# Wait for IAM role to propagate across AWS
sleep 10
```

---

## Step 16 – Create App Runner Services

```bash
# Create Student API service configuration
# ServiceName: Name of the App Runner service
# ImageIdentifier: ECR image URI with tag
# ImageConfiguration.Port: Container port to expose (must match Dockerfile)
# AutoDeploymentsEnabled: false = manual deployments only
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

## Step 17 – Wait for Services to be Ready

```bash
# Wait for Student API service to become RUNNING
# App Runner takes 2-4 minutes to deploy the container
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

# Wait for Report API service to become RUNNING
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

## Step 18 – Test Applications

```bash
# Test Student API endpoints
echo "Testing Student API:"
curl -s "https://$STUDENT_URL/" | jq .                # Health check
curl -s "https://$STUDENT_URL/students" | jq .        # Get all students
curl -s "https://$STUDENT_URL/students/1" | jq .      # Get student by ID

# Test Report API endpoints
echo -e "\nTesting Report API:"
curl -s "https://$REPORT_URL/" | jq .                 # Health check
curl -s "https://$REPORT_URL/reports" | jq .          # Get all reports with grades
curl -s "https://$REPORT_URL/report/1" | jq .         # Get report by ID

# Display URLs for browser testing
echo -e "\n📱 Student API URLs:"
echo "https://$STUDENT_URL/"
echo "https://$STUDENT_URL/students"

echo -e "\n📱 Report API URLs:"
echo "https://$REPORT_URL/"
echo "https://$REPORT_URL/reports"
```

---

## Step 19 – Cleanup

```bash
# Delete App Runner services
# This will take 2-3 minutes as App Runner gracefully shuts down
aws apprunner delete-service \
  --service-arn "$STUDENT_SERVICE_ARN" \
  --region "$REGION"

aws apprunner delete-service \
  --service-arn "$REPORT_SERVICE_ARN" \
  --region "$REGION"

# Wait for services to delete
echo "Waiting for services to delete..."
sleep 30

# Delete ECR repositories with all images
# --force flag deletes repository even if it contains images
aws ecr delete-repository \
  --repository-name "$STUDENT_REPO_NAME" \
  --force \
  --region "$REGION"

aws ecr delete-repository \
  --repository-name "$REPORT_REPO_NAME" \
  --force \
  --region "$REGION"

# Delete IAM role and detach policies
aws iam detach-role-policy \
  --role-name AppRunnerECRAccessRole \
  --policy-arn arn:aws:iam::aws:policy/AWSAppRunnerServicePolicyForECRAccess

aws iam delete-role --role-name AppRunnerECRAccessRole

# Remove application directories and files from Git
cd "$REPO_DIR"
rm -rf "$STUDENT_API_FOLDER" "$REPORT_API_FOLDER"

# Remove Docker and configuration files
rm -f Dockerfile.student Dockerfile.report requirements.txt
rm -f apprunner-*.json

# Commit cleanup to Git
git add .
git commit -m "Cleanup: Remove multi-API deployment"
git push origin main

echo "✅ Cleanup complete"
```

---

## Summary

In this lab, you:
- Created two Flask microservices (Student API and Report API)
- Implemented pytest unit tests for both APIs
- Built Docker images locally for each service
- Pushed Docker images to Amazon ECR
- Deployed two independent App Runner services from ECR images
- Tested endpoints and verified the deployment

**Key Takeaways:**
- **Multi-Service Architecture**: Two independent APIs in one repository
- **Local Development Workflow**: Build and test locally before deploying
- **Container-Based Deployment**: ECR → App Runner workflow
- **Automated Testing**: pytest validates code before building images
- **Fully Managed**: App Runner handles scaling and load balancing

**Deployment Workflow:**
```
Local Development → Docker Build → ECR → App Runner
       ↓
  pytest tests
```

---

## Best Practices

**Local Docker Development:**
- Test Docker images locally before pushing to ECR
- Use `docker run` to verify container behavior
- Check container logs with `docker logs` for debugging
- Tag images with ECR URI for seamless push

**Docker Images:**
- Use slim base images (python:3.11-slim) for smaller size
- Copy only necessary files to reduce image size
- Use gunicorn for production WSGI server
- Set explicit working directories and ports

**Amazon ECR:**
- One repository per microservice for independent versioning
- Use `:latest` tag for development, semantic versioning for production
- Authenticate Docker before pushing images
- Enable image scanning for security vulnerabilities

**App Runner:**
- Start with 1 vCPU / 2 GB for testing
- Monitor metrics and adjust resources as needed
- Use ECR for private container images
- Disable auto-deployments for manual control
- Enable auto-deployments for continuous delivery in production

**Testing:**
- Run pytest locally before building Docker images
- Test all critical endpoints before deployment
- Use lightweight pytest for API testing
- Verify responses with assertions

---

## Troubleshooting

**Docker build fails:**
- Ensure Docker daemon is running (`docker info`)
- Check Dockerfile syntax and paths
- Verify requirements.txt exists and is readable
- Use `docker build --no-cache` to force rebuild

**Docker push fails:**
- Verify ECR repositories exist
- Check AWS CLI authentication (`aws sts get-caller-identity`)
- Ensure ECR login succeeded (look for "Login Succeeded" message)
- Verify IAM permissions for ECR push operations

**App Runner deployment fails:**
- Verify image exists in ECR with `:latest` tag
- Check AccessRoleArn for ECR access role
- Ensure port 8000 is exposed in Dockerfile
- Review CloudWatch logs: App Runner → Services → Logs
- Verify application starts successfully (check CMD in Dockerfile)

**Local pytest fails:**
- Install dependencies: `pip install -r requirements.txt`
- Ensure test files are named `test_*.py`
- Run with `-v` flag for verbose output: `pytest -v`
- Check Flask test_client usage in test files

**Cannot access App Runner URL:**
- Wait for service status to be "RUNNING"
- App Runner takes 2-4 minutes to deploy
- Check if URL is HTTPS (App Runner only uses HTTPS)
- Verify application health endpoint returns 200

---

## Additional Resources

- [Amazon ECR Documentation](https://docs.aws.amazon.com/ecr/)
- [AWS App Runner Documentation](https://docs.aws.amazon.com/apprunner/)
- [Docker Documentation](https://docs.docker.com/)
- [Flask Testing Documentation](https://flask.palletsprojects.com/en/2.3.x/testing/)
- [pytest Documentation](https://docs.pytest.org/)

