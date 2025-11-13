# Lab 15.D: Container Migration – Dockerize a Legacy Application

## Overview
This lab teaches you how to containerize a **legacy monolithic application** using Docker. You'll create a simple Python Flask application, write a Dockerfile, build and test the container locally, push it to Amazon Elastic Container Registry (ECR), deploy it on AWS ECS Fargate, and validate the containerized application.

Containerization enables legacy applications to run in modern cloud environments with improved portability, scalability, and resource efficiency.

---

## Objectives
- Create a simple legacy application for containerization
- Write a production-ready Dockerfile with best practices
- Build and test Docker images locally
- Create and configure Amazon ECR repository
- Authenticate Docker with ECR
- Push container images to ECR
- Create ECS cluster and task definitions
- Deploy containerized application to ECS Fargate
- Validate application accessibility and functionality
- Perform comprehensive resource cleanup

---

## Prerequisites
- Docker installed and running locally
- AWS CLI configured with appropriate credentials
- IAM permissions for ECR, ECS, IAM, and EC2
- Region: **ap-southeast-2** (Sydney)
- Basic understanding of Docker and containers
- `jq` installed for JSON parsing (optional)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              Container Migration Workflow                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Local Development Environment                                      │
│  ┌─────────────────────────────┐                                   │
│  │   Legacy Application        │                                   │
│  │   - Python Flask App        │                                   │
│  │   - app.py                  │                                   │
│  │   - requirements.txt        │                                   │
│  └─────────────────────────────┘                                   │
│              │                                                      │
│              │ Docker Build                                         │
│              ▼                                                      │
│  ┌─────────────────────────────┐                                   │
│  │   Docker Image              │                                   │
│  │   - Base: python:3.11-slim  │                                   │
│  │   - App Code + Dependencies │                                   │
│  │   - Exposed Port: 8080      │                                   │
│  └─────────────────────────────┘                                   │
│              │                                                      │
│              │ Docker Push                                          │
│              ▼                                                      │
│  AWS Cloud Environment                                              │
│  ┌─────────────────────────────┐                                   │
│  │   Amazon ECR Repository     │                                   │
│  │   - Private Registry        │                                   │
│  │   - Image Versioning        │                                   │
│  │   - Lifecycle Policies      │                                   │
│  └─────────────────────────────┘                                   │
│              │                                                      │
│              │ ECS Pull                                             │
│              ▼                                                      │
│  ┌─────────────────────────────┐                                   │
│  │   ECS Fargate Service       │                                   │
│  │   - Serverless Containers   │                                   │
│  │   - Auto-scaling            │                                   │
│  │   - Load Balancing          │                                   │
│  │   - Public Access           │                                   │
│  └─────────────────────────────┘                                   │
│              │                                                      │
│              ▼                                                      │
│  ┌─────────────────────────────┐                                   │
│  │   Users / Applications      │                                   │
│  │   HTTP Access on Port 8080  │                                   │
│  └─────────────────────────────┘                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

Key Components:
- Legacy App: Simple Python Flask web application
- Dockerfile: Multi-stage build with optimization
- ECR: Private container registry in AWS
- ECS Fargate: Serverless container orchestration
- Task Definition: Container configuration
- Security Group: Network access control
```

---

## Cost Estimate
- **ECR Storage**: $0.10 per GB-month (first 500 MB free)
- **ECS Fargate**: ~$0.04048 per vCPU-hour + $0.004445 per GB-hour
- **Data Transfer**: Free within same region
- **Estimated Lab Cost**: < $0.25 for 2-3 hours

---

# Step 1 – Set Environment Variables

```bash
# Set primary region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "✅ Region set to: $REGION"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "✅ AWS Account ID: $ACCOUNT_ID"

# Define resource names
ECR_REPO="legacy-app-repo"
APP_DIR="/tmp/legacy-app"
IMAGE_TAG="v1.0"
CLUSTER_NAME="legacy-app-cluster"
TASK_FAMILY="legacy-app-task"
SERVICE_NAME="legacy-app-service"

# Echo all variables for verification
echo ""
echo "=== Environment Configuration ==="
echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
echo "ECR Repository: $ECR_REPO"
echo "Application Directory: $APP_DIR"
echo "Image Tag: $IMAGE_TAG"
echo "Cluster Name: $CLUSTER_NAME"
echo "Task Family: $TASK_FAMILY"
echo "Service Name: $SERVICE_NAME"
echo "================================="
echo ""
```

**Expected Output:**
```
✅ Region set to: ap-southeast-2
✅ AWS Account ID: 123456789012
=== Environment Configuration ===
Region: ap-southeast-2
Account ID: 123456789012
ECR Repository: legacy-app-repo
Application Directory: /tmp/legacy-app
Image Tag: v1.0
Cluster Name: legacy-app-cluster
Task Family: legacy-app-task
Service Name: legacy-app-service
=================================
```

---

# Step 2 – Verify Docker Installation

```bash
# Check if Docker is installed and running
echo "Verifying Docker installation..."

# Check Docker version
DOCKER_VERSION=$(docker --version 2>/dev/null)
if [[ $? -eq 0 ]]; then
  echo "✅ Docker installed: $DOCKER_VERSION"
else
  echo "❌ Docker not found. Please install Docker first."
  exit 1
fi

# Check if Docker daemon is running
docker info > /dev/null 2>&1
if [[ $? -eq 0 ]]; then
  echo "✅ Docker daemon is running"
else
  echo "❌ Docker daemon not running. Please start Docker."
  exit 1
fi

# Display Docker info
echo ""
echo "=== Docker Configuration ==="
echo "Docker Version: $(docker version --format '{{.Server.Version}}')"
echo "Docker Root: $(docker info --format '{{.DockerRootDir}}')"
echo "============================"
echo ""
```

**Expected Output:**
```
Verifying Docker installation...
✅ Docker installed: Docker version 24.0.7, build afdd53b
✅ Docker daemon is running

=== Docker Configuration ===
Docker Version: 24.0.7
Docker Root: /var/lib/docker
============================
```

---

# Step 3 – Create Legacy Application Code

```bash
# Create application directory
echo "Creating legacy application directory..."
mkdir -p "$APP_DIR"
cd "$APP_DIR"
echo "✅ Directory created: $APP_DIR"

# Create Python Flask application
echo ""
echo "Creating Flask application..."

cat > app.py << 'EOF'
#!/usr/bin/env python3
"""
Legacy Application - Containerized with Docker
A simple Flask web application demonstrating containerization
"""

from flask import Flask, jsonify, request
import os
import socket
import datetime

app = Flask(__name__)

@app.route("/")
def home():
    """Home endpoint - returns HTML welcome page"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Legacy App - Containerized</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f0f0f0;
            }
            .container {
                background-color: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 { color: #FF9900; }
            .info { margin: 10px 0; padding: 10px; background-color: #f9f9f9; }
            .success { color: green; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🐳 Legacy Application Successfully Containerized!</h1>
            <p class="success">This legacy monolithic application has been migrated to containers.</p>
            
            <div class="info">
                <strong>Hostname:</strong> """ + socket.gethostname() + """<br>
                <strong>Container IP:</strong> """ + request.host + """<br>
                <strong>Timestamp:</strong> """ + str(datetime.datetime.now()) + """<br>
                <strong>Python Version:</strong> """ + os.sys.version.split()[0] + """
            </div>
            
            <h2>Migration Benefits:</h2>
            <ul>
                <li>✅ Improved portability across environments</li>
                <li>✅ Consistent deployment and scaling</li>
                <li>✅ Reduced infrastructure overhead</li>
                <li>✅ Better resource utilization</li>
                <li>✅ Simplified CI/CD integration</li>
            </ul>
            
            <h2>API Endpoints:</h2>
            <ul>
                <li><a href="/">/</a> - Home page (this page)</li>
                <li><a href="/health">/health</a> - Health check endpoint</li>
                <li><a href="/info">/info</a> - System information (JSON)</li>
            </ul>
        </div>
    </body>
    </html>
    """
    return html_content

@app.route("/health")
def health():
    """Health check endpoint for ECS"""
    return jsonify({
        "status": "healthy",
        "timestamp": str(datetime.datetime.now())
    }), 200

@app.route("/info")
def info():
    """System information endpoint"""
    return jsonify({
        "hostname": socket.gethostname(),
        "host": request.host,
        "python_version": os.sys.version,
        "timestamp": str(datetime.datetime.now()),
        "environment": os.environ.get("ENVIRONMENT", "production")
    })

if __name__ == "__main__":
    # Run Flask application
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
EOF

echo "✅ Flask application created: app.py"

# Create requirements file for Python dependencies
echo ""
echo "Creating requirements.txt..."

cat > requirements.txt << 'EOF'
# Python dependencies for legacy Flask application
flask==3.0.0
werkzeug==3.0.1
EOF

echo "✅ Requirements file created: requirements.txt"

# Display created files
echo ""
echo "=== Application Files ==="
ls -lh "$APP_DIR"
echo "========================="
echo ""
```

**Expected Output:**
```
Creating legacy application directory...
✅ Directory created: /tmp/legacy-app

Creating Flask application...
✅ Flask application created: app.py

Creating requirements.txt...
✅ Requirements file created: requirements.txt

=== Application Files ===
total 8.0K
-rw-r--r-- 1 user user 2.5K Nov 13 12:00 app.py
-rw-r--r-- 1 user user   85 Nov 13 12:00 requirements.txt
=========================
```

---

# Step 4 – Create Dockerfile with Best Practices

```bash
# Create optimized Dockerfile
echo "Creating Dockerfile..."

cat > Dockerfile << 'EOF'
# Use official Python slim image for smaller size
FROM python:3.11-slim

# Set metadata labels
LABEL maintainer="AWS Lab 15.D"
LABEL description="Containerized legacy Flask application"
LABEL version="1.0"

# Set working directory
WORKDIR /app

# Copy requirements first (for better layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose application port
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run the application
CMD ["python", "app.py"]
EOF

echo "✅ Dockerfile created with best practices"

# Create .dockerignore file to exclude unnecessary files
echo ""
echo "Creating .dockerignore..."

cat > .dockerignore << 'EOF'
# Git files
.git
.gitignore

# Python cache
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.so

# Virtual environments
venv/
env/
ENV/

# IDE files
.vscode/
.idea/
*.swp
*.swo

# Documentation
README.md
*.md

# Tests
tests/
test/
EOF

echo "✅ .dockerignore created"

# Display Dockerfile
echo ""
echo "=== Dockerfile Content ==="
cat Dockerfile
echo "=========================="
echo ""
```

**Expected Output:**
```
Creating Dockerfile...
✅ Dockerfile created with best practices

Creating .dockerignore...
✅ .dockerignore created

=== Dockerfile Content ===
FROM python:3.11-slim
LABEL maintainer="AWS Lab 15.D"
...
CMD ["python", "app.py"]
==========================
```

---

# Step 5 – Build Docker Image Locally

```bash
# Build Docker image
echo "Building Docker image..."
echo ""

# Build with tag
docker build \
  --tag "legacy-app:${IMAGE_TAG}" \
  --tag "legacy-app:latest" \
  --file Dockerfile \
  --progress=plain \
  "$APP_DIR"

echo ""
echo "✅ Docker image built successfully"

# Verify image was created
echo ""
echo "=== Docker Images ==="
docker images legacy-app
echo "====================="
echo ""

# Display image details
IMAGE_SIZE=$(docker images legacy-app:${IMAGE_TAG} --format "{{.Size}}")
echo "Image: legacy-app:${IMAGE_TAG}"
echo "Size: $IMAGE_SIZE"
echo ""
```

**Expected Output:**
```
Building Docker image...

#1 [internal] load build definition from Dockerfile
#1 transferring dockerfile: 123B done
...
#8 exporting to image
#8 exporting layers done
#8 writing image sha256:abc123... done

✅ Docker image built successfully

=== Docker Images ===
REPOSITORY    TAG       IMAGE ID       CREATED          SIZE
legacy-app    v1.0      abc123def456   10 seconds ago   145MB
legacy-app    latest    abc123def456   10 seconds ago   145MB
=====================

Image: legacy-app:v1.0
Size: 145MB
```

---

# Step 6 – Test Docker Container Locally

```bash
# Run container locally for testing
echo "Starting Docker container locally..."

# Run container in detached mode
CONTAINER_ID=$(docker run \
  --detach \
  --name legacy-app-test \
  --publish 8080:8080 \
  --env ENVIRONMENT=testing \
  legacy-app:${IMAGE_TAG})

echo "✅ Container started: $CONTAINER_ID"

# Wait for container to be ready
echo ""
echo "⏳ Waiting for container to be ready (10 seconds)..."
sleep 10

# Check container status
CONTAINER_STATUS=$(docker ps --filter "name=legacy-app-test" --format "{{.Status}}")
echo "Container Status: $CONTAINER_STATUS"

# Test health endpoint
echo ""
echo "Testing application endpoints..."

# Test root endpoint
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>/dev/null)
if [[ "$HTTP_CODE" == "200" ]]; then
  echo "✅ Root endpoint (/) responding: HTTP $HTTP_CODE"
else
  echo "⚠️  Root endpoint issue: HTTP $HTTP_CODE"
fi

# Test health endpoint
HEALTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health 2>/dev/null)
if [[ "$HEALTH_CODE" == "200" ]]; then
  echo "✅ Health endpoint (/health) responding: HTTP $HEALTH_CODE"
  
  # Display health response
  echo ""
  echo "=== Health Check Response ==="
  curl -s http://localhost:8080/health | jq . 2>/dev/null || curl -s http://localhost:8080/health
  echo "============================="
else
  echo "⚠️  Health endpoint issue: HTTP $HEALTH_CODE"
fi

# Test info endpoint
echo ""
echo "=== System Info Response ==="
curl -s http://localhost:8080/info | jq . 2>/dev/null || curl -s http://localhost:8080/info
echo "============================"

# Display container logs
echo ""
echo "=== Container Logs (last 10 lines) ==="
docker logs --tail 10 legacy-app-test
echo "======================================="
echo ""

echo "✅ Local testing successful"
echo ""
echo "Access application at: http://localhost:8080"
echo ""
```

**Expected Output:**
```
Starting Docker container locally...
✅ Container started: abc123def456789

⏳ Waiting for container to be ready (10 seconds)...
Container Status: Up 10 seconds

Testing application endpoints...
✅ Root endpoint (/) responding: HTTP 200
✅ Health endpoint (/health) responding: HTTP 200

=== Health Check Response ===
{
  "status": "healthy",
  "timestamp": "2025-11-13 12:05:30.123456"
}
=============================

=== System Info Response ===
{
  "hostname": "abc123def456",
  "host": "localhost:8080",
  "python_version": "3.11.6",
  "timestamp": "2025-11-13 12:05:30.234567",
  "environment": "testing"
}
============================

=== Container Logs (last 10 lines) ===
 * Serving Flask app 'app'
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:8080
 * Running on http://172.17.0.2:8080
=======================================

✅ Local testing successful

Access application at: http://localhost:8080
```

---

# Step 7 – Stop Local Test Container

```bash
# Stop and remove test container
echo "Stopping local test container..."

docker stop legacy-app-test
docker rm legacy-app-test

echo "✅ Test container stopped and removed"
echo ""
```

**Expected Output:**
```
Stopping local test container...
legacy-app-test
legacy-app-test
✅ Test container stopped and removed
```

---

# Step 8 – Create Amazon ECR Repository

```bash
# Create ECR repository for container images
echo "Creating Amazon ECR repository..."

# Create repository with image scanning enabled
aws ecr create-repository \
  --repository-name "$ECR_REPO" \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256 \
  --tags "Key=Purpose,Value=Container-Migration" "Key=Lab,Value=15D" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ ECR repository created: $ECR_REPO"

# Get repository URI
REPO_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}"

echo ""
echo "=== ECR Repository Details ==="
echo "Repository Name: $ECR_REPO"
echo "Repository URI: $REPO_URI"
echo "Region: $REGION"
echo "=============================="
echo ""

# Verify repository exists
aws ecr describe-repositories \
  --repository-names "$ECR_REPO" \
  --region "$REGION" \
  --query "repositories[0].[repositoryName,repositoryUri,createdAt]" \
  --output table

echo ""
```

**Expected Output:**
```
Creating Amazon ECR repository...
✅ ECR repository created: legacy-app-repo

=== ECR Repository Details ===
Repository Name: legacy-app-repo
Repository URI: 123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/legacy-app-repo
Region: ap-southeast-2
==============================

----------------------------------------------------------------------------------
|                        DescribeRepositories                                     |
+---------------------------------------------------------------------------------+
|  legacy-app-repo                                                               |
|  123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/legacy-app-repo            |
|  2025-11-13T12:06:00+00:00                                                     |
+---------------------------------------------------------------------------------+
```

---

# Step 9 – Authenticate Docker to Amazon ECR

```bash
# Authenticate Docker client to ECR
echo "Authenticating Docker to Amazon ECR..."

# Get ECR login password and pipe to docker login
aws ecr get-login-password \
  --region "$REGION" | \
docker login \
  --username AWS \
  --password-stdin \
  "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "✅ Docker authenticated to ECR"
echo ""
```

**Expected Output:**
```
Authenticating Docker to Amazon ECR...
WARNING! Your password will be stored unencrypted in /home/user/.docker/config.json.
Configure a credential helper to remove this warning. See
https://docs.docker.com/engine/reference/commandline/login/#credentials-store

Login Succeeded
✅ Docker authenticated to ECR
```

---

# Step 10 – Tag and Push Image to ECR

```bash
# Tag image for ECR
echo "Tagging image for ECR..."

# Tag with both version and latest
docker tag \
  "legacy-app:${IMAGE_TAG}" \
  "${REPO_URI}:${IMAGE_TAG}"

docker tag \
  "legacy-app:${IMAGE_TAG}" \
  "${REPO_URI}:latest"

echo "✅ Image tagged for ECR"

# Display tagged images
echo ""
echo "=== Tagged Images ==="
docker images | grep -E "(REPOSITORY|legacy-app|${ECR_REPO})"
echo "====================="
echo ""

# Push image to ECR
echo "Pushing image to ECR..."
echo "This may take a few minutes depending on image size..."
echo ""

# Push versioned tag
docker push "${REPO_URI}:${IMAGE_TAG}"

echo ""
echo "✅ Image pushed with tag: ${IMAGE_TAG}"

# Push latest tag
docker push "${REPO_URI}:latest"

echo "✅ Image pushed with tag: latest"

# Verify images in ECR
echo ""
echo "=== Images in ECR Repository ==="
aws ecr list-images \
  --repository-name "$ECR_REPO" \
  --region "$REGION" \
  --query 'imageIds[*].[imageTag]' \
  --output table

echo "================================"
echo ""
```

**Expected Output:**
```
Tagging image for ECR...
✅ Image tagged for ECR

=== Tagged Images ===
REPOSITORY                                                    TAG       IMAGE ID       CREATED          SIZE
legacy-app                                                    v1.0      abc123def456   5 minutes ago    145MB
legacy-app                                                    latest    abc123def456   5 minutes ago    145MB
123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/legacy-app  v1.0      abc123def456   5 minutes ago    145MB
123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/legacy-app  latest    abc123def456   5 minutes ago    145MB
=====================

Pushing image to ECR...
This may take a few minutes depending on image size...

The push refers to repository [123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/legacy-app]
...
v1.0: digest: sha256:abc123... size: 1234

✅ Image pushed with tag: v1.0
✅ Image pushed with tag: latest

=== Images in ECR Repository ===
--------------------------
|      ListImages        |
+------------------------+
|  v1.0                  |
|  latest                |
+------------------------+
================================
```

---

# Step 11 – Get VPC and Subnet Information

```bash
# Get default VPC and subnet for ECS deployment
echo "Getting VPC and subnet information..."

# Get default VPC
DEFAULT_VPC=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" \
  --output text \
  --region "$REGION")
echo "✅ Default VPC: $DEFAULT_VPC"

# Get subnets in default VPC
SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$DEFAULT_VPC" \
  --query "Subnets[*].SubnetId" \
  --output text \
  --region "$REGION")
SUBNET_1=$(echo $SUBNETS | awk '{print $1}')
SUBNET_2=$(echo $SUBNETS | awk '{print $2}')

echo "✅ Subnets found: $SUBNET_1, $SUBNET_2"

# Create security group for ECS tasks
echo ""
echo "Creating security group for ECS tasks..."

SG_ID=$(aws ec2 create-security-group \
  --group-name "ecs-legacy-app-sg" \
  --description "Security group for containerized legacy app" \
  --vpc-id "$DEFAULT_VPC" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

echo "✅ Security group created: $SG_ID"

# Add inbound rule for application port
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 8080 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

echo "✅ Inbound rule added: TCP port 8080"

echo ""
echo "=== Network Configuration ==="
echo "VPC: $DEFAULT_VPC"
echo "Subnet 1: $SUBNET_1"
echo "Subnet 2: $SUBNET_2"
echo "Security Group: $SG_ID"
echo "============================="
echo ""
```

**Expected Output:**
```
Getting VPC and subnet information...
✅ Default VPC: vpc-0123456789abcdef0
✅ Subnets found: subnet-abc123, subnet-def456

Creating security group for ECS tasks...
✅ Security group created: sg-0123456789abcdef0
✅ Inbound rule added: TCP port 8080

=== Network Configuration ===
VPC: vpc-0123456789abcdef0
Subnet 1: subnet-abc123
Subnet 2: subnet-def456
Security Group: sg-0123456789abcdef0
=============================
```

---

# Step 12 – Create ECS Cluster

```bash
# Create ECS cluster for Fargate
echo "Creating ECS cluster..."

aws ecs create-cluster \
  --cluster-name "$CLUSTER_NAME" \
  --capacity-providers FARGATE FARGATE_SPOT \
  --default-capacity-provider-strategy "capacityProvider=FARGATE,weight=1" \
  --tags "key=Purpose,value=Container-Migration" "key=Lab,value=15D" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ ECS cluster created: $CLUSTER_NAME"

# Wait for cluster to be active
sleep 5

# Verify cluster
echo ""
echo "=== ECS Cluster Details ==="
aws ecs describe-clusters \
  --clusters "$CLUSTER_NAME" \
  --region "$REGION" \
  --query "clusters[0].[clusterName,status,capacityProviders[]]" \
  --output table

echo "==========================="
echo ""
```

**Expected Output:**
```
Creating ECS cluster...
✅ ECS cluster created: legacy-app-cluster

=== ECS Cluster Details ===
-----------------------------------------------------------------
|                     DescribeClusters                           |
+---------------------------------------------------------------+
|  legacy-app-cluster                                           |
|  ACTIVE                                                       |
|  FARGATE                                                      |
|  FARGATE_SPOT                                                 |
+---------------------------------------------------------------+
===========================
```

---

# Step 13 – Create IAM Role for ECS Task Execution

```bash
# Create IAM role for ECS task execution
echo "Creating IAM role for ECS task execution..."

# Check if role already exists
ROLE_EXISTS=$(aws iam get-role \
  --role-name ecsTaskExecutionRole \
  --query 'Role.RoleName' \
  --output text 2>/dev/null)

if [[ "$ROLE_EXISTS" == "ecsTaskExecutionRole" ]]; then
  echo "ℹ️  Role ecsTaskExecutionRole already exists"
  TASK_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole"
else
  # Create role
  aws iam create-role \
    --role-name ecsTaskExecutionRole \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": {
          "Service": "ecs-tasks.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
      }]
    }' \
    --description "Role for ECS task execution" \
    --output json > /dev/null

  echo "✅ IAM role created: ecsTaskExecutionRole"

  # Attach required policy
  aws iam attach-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"

  echo "✅ Policy attached: AmazonECSTaskExecutionRolePolicy"

  # Wait for role to propagate
  sleep 10

  TASK_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole"
fi

echo ""
echo "=== IAM Role Information ==="
echo "Role Name: ecsTaskExecutionRole"
echo "Role ARN: $TASK_ROLE_ARN"
echo "============================"
echo ""
```

**Expected Output:**
```
Creating IAM role for ECS task execution...
✅ IAM role created: ecsTaskExecutionRole
✅ Policy attached: AmazonECSTaskExecutionRolePolicy

=== IAM Role Information ===
Role Name: ecsTaskExecutionRole
Role ARN: arn:aws:iam::123456789012:role/ecsTaskExecutionRole
============================
```

---

# Step 14 – Create ECS Task Definition

```bash
# Create ECS task definition
echo "Creating ECS task definition..."

# Create task definition JSON
cat > /tmp/task-definition.json << EOF
{
  "family": "${TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "${TASK_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "legacy-app-container",
      "image": "${REPO_URI}:${IMAGE_TAG}",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp",
          "hostPort": 8080
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        },
        {
          "name": "PORT",
          "value": "8080"
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${TASK_FAMILY}",
          "awslogs-region": "${REGION}",
          "awslogs-stream-prefix": "ecs",
          "awslogs-create-group": "true"
        }
      }
    }
  ]
}
EOF

echo "✅ Task definition file created"

# Register task definition
TASK_DEF_ARN=$(aws ecs register-task-definition \
  --cli-input-json file:///tmp/task-definition.json \
  --region "$REGION" \
  --query 'taskDefinition.taskDefinitionArn' \
  --output text)

echo "✅ Task definition registered: $TASK_DEF_ARN"

# Display task definition details
echo ""
echo "=== Task Definition Details ==="
aws ecs describe-task-definition \
  --task-definition "$TASK_FAMILY" \
  --region "$REGION" \
  --query 'taskDefinition.[family,revision,cpu,memory,networkMode]' \
  --output table

echo "==============================="
echo ""
```

**Expected Output:**
```
Creating ECS task definition...
✅ Task definition file created
✅ Task definition registered: arn:aws:ecs:ap-southeast-2:123456789012:task-definition/legacy-app-task:1

=== Task Definition Details ===
-----------------------------------------------------------------
|                  DescribeTaskDefinition                        |
+---------------------------------------------------------------+
|  legacy-app-task                                              |
|  1                                                            |
|  256                                                          |
|  512                                                          |
|  awsvpc                                                       |
+---------------------------------------------------------------+
===============================
```

---

# Step 15 – Create ECS Fargate Service

```bash
# Create ECS Fargate service
echo "Creating ECS Fargate service..."

# Create service
aws ecs create-service \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --task-definition "$TASK_FAMILY" \
  --desired-count 1 \
  --launch-type FARGATE \
  --platform-version LATEST \
  --network-configuration "awsvpcConfiguration={
    subnets=[$SUBNET_1,$SUBNET_2],
    securityGroups=[$SG_ID],
    assignPublicIp=ENABLED
  }" \
  --tags "key=Purpose,value=Container-Migration" "key=Lab,value=15D" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ ECS service created: $SERVICE_NAME"

# Wait for service to stabilize
echo ""
echo "⏳ Waiting for service to start (this may take 2-3 minutes)..."
echo ""

# Monitor service deployment
for i in {1..12}; do
  SERVICE_STATUS=$(aws ecs describe-services \
    --cluster "$CLUSTER_NAME" \
    --services "$SERVICE_NAME" \
    --region "$REGION" \
    --query 'services[0].[runningCount,desiredCount]' \
    --output text)
  
  RUNNING=$(echo $SERVICE_STATUS | awk '{print $1}')
  DESIRED=$(echo $SERVICE_STATUS | awk '{print $2}')
  
  echo "[$(date '+%H:%M:%S')] Running: $RUNNING / Desired: $DESIRED"
  
  if [[ "$RUNNING" -eq "$DESIRED" ]] && [[ "$RUNNING" -gt 0 ]]; then
    echo ""
    echo "✅ Service is running and stable"
    break
  fi
  
  if [[ $i -eq 12 ]]; then
    echo ""
    echo "⚠️  Service taking longer than expected to start"
  fi
  
  sleep 15
done

echo ""
```

**Expected Output:**
```
Creating ECS Fargate service...
✅ ECS service created: legacy-app-service

⏳ Waiting for service to start (this may take 2-3 minutes)...

[12:15:00] Running: 0 / Desired: 1
[12:15:15] Running: 0 / Desired: 1
[12:15:30] Running: 1 / Desired: 1

✅ Service is running and stable
```

---

# Step 16 – Get Task Public IP and Validate Application

```bash
# Get task ARN
echo "Getting task information..."

TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --region "$REGION" \
  --query 'taskArns[0]' \
  --output text)

echo "✅ Task ARN: $TASK_ARN"

# Get task details
TASK_DETAILS=$(aws ecs describe-tasks \
  --cluster "$CLUSTER_NAME" \
  --tasks "$TASK_ARN" \
  --region "$REGION" \
  --output json)

# Extract ENI ID
ENI_ID=$(echo "$TASK_DETAILS" | \
  jq -r '.tasks[0].attachments[0].details[] | select(.name=="networkInterfaceId") | .value')

echo "✅ Network Interface: $ENI_ID"

# Get public IP from ENI
PUBLIC_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids "$ENI_ID" \
  --region "$REGION" \
  --query 'NetworkInterfaces[0].Association.PublicIp' \
  --output text)

echo "✅ Public IP: $PUBLIC_IP"

# Wait for application to be ready
echo ""
echo "⏳ Waiting for application to be ready (30 seconds)..."
sleep 30

# Test application endpoints
echo ""
echo "=== Testing Containerized Application ==="
echo ""

# Test root endpoint
echo "Testing root endpoint..."
ROOT_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://${PUBLIC_IP}:8080/" 2>/dev/null)

if [[ "$ROOT_CODE" == "200" ]]; then
  echo "✅ Root endpoint responding: HTTP $ROOT_CODE"
else
  echo "⚠️  Root endpoint issue: HTTP $ROOT_CODE"
fi

# Test health endpoint
echo ""
echo "Testing health endpoint..."
HEALTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://${PUBLIC_IP}:8080/health" 2>/dev/null)

if [[ "$HEALTH_CODE" == "200" ]]; then
  echo "✅ Health endpoint responding: HTTP $HEALTH_CODE"
  
  echo ""
  echo "Health Response:"
  curl -s "http://${PUBLIC_IP}:8080/health" | jq . 2>/dev/null || curl -s "http://${PUBLIC_IP}:8080/health"
else
  echo "⚠️  Health endpoint issue: HTTP $HEALTH_CODE"
fi

# Test info endpoint
echo ""
echo "System Info Response:"
curl -s "http://${PUBLIC_IP}:8080/info" | jq . 2>/dev/null || curl -s "http://${PUBLIC_IP}:8080/info"

echo ""
echo "=========================================="
echo ""
echo "✅ Application successfully deployed and validated!"
echo ""
echo "=== Access Information ==="
echo "Application URL: http://${PUBLIC_IP}:8080"
echo "Health Check: http://${PUBLIC_IP}:8080/health"
echo "System Info: http://${PUBLIC_IP}:8080/info"
echo "=========================="
echo ""
```

**Expected Output:**
```
Getting task information...
✅ Task ARN: arn:aws:ecs:ap-southeast-2:123456789012:task/legacy-app-cluster/abc123...
✅ Network Interface: eni-0123456789abcdef0
✅ Public IP: 13.239.123.45

⏳ Waiting for application to be ready (30 seconds)...

=== Testing Containerized Application ===

Testing root endpoint...
✅ Root endpoint responding: HTTP 200

Testing health endpoint...
✅ Health endpoint responding: HTTP 200

Health Response:
{
  "status": "healthy",
  "timestamp": "2025-11-13 12:20:30.123456"
}

System Info Response:
{
  "hostname": "ip-10-0-1-25",
  "host": "13.239.123.45:8080",
  "python_version": "3.11.6",
  "timestamp": "2025-11-13 12:20:30.234567",
  "environment": "production"
}

==========================================

✅ Application successfully deployed and validated!

=== Access Information ===
Application URL: http://13.239.123.45:8080
Health Check: http://13.239.123.45:8080/health
System Info: http://13.239.123.45:8080/info
==========================
```

---

# Step 17 – Cleanup Resources

```bash
# Comprehensive cleanup of all resources
echo "Starting cleanup process..."
echo ""

# Update service to desired count 0
echo "Stopping ECS service..."
aws ecs update-service \
  --cluster "$CLUSTER_NAME" \
  --service "$SERVICE_NAME" \
  --desired-count 0 \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Service scaled down to 0 tasks"
sleep 20

# Delete ECS service
echo ""
echo "Deleting ECS service..."
aws ecs delete-service \
  --cluster "$CLUSTER_NAME" \
  --service "$SERVICE_NAME" \
  --force \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ ECS service deleted: $SERVICE_NAME"

# Wait for service deletion
sleep 10

# Delete ECS cluster
echo ""
echo "Deleting ECS cluster..."
aws ecs delete-cluster \
  --cluster "$CLUSTER_NAME" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ ECS cluster deleted: $CLUSTER_NAME"

# Deregister task definition (mark as inactive)
echo ""
echo "Deregistering task definition..."
TASK_DEF_REVISIONS=$(aws ecs list-task-definitions \
  --family-prefix "$TASK_FAMILY" \
  --region "$REGION" \
  --query 'taskDefinitionArns[]' \
  --output text)

for TASK_DEF in $TASK_DEF_REVISIONS; do
  aws ecs deregister-task-definition \
    --task-definition "$TASK_DEF" \
    --region "$REGION" \
    --output json > /dev/null
  echo "  ✓ Deregistered: $(basename $TASK_DEF)"
done

# Delete CloudWatch log group
echo ""
echo "Deleting CloudWatch log group..."
aws logs delete-log-group \
  --log-group-name "/ecs/${TASK_FAMILY}" \
  --region "$REGION" 2>/dev/null && \
  echo "✅ Log group deleted" || \
  echo "ℹ️  Log group not found or already deleted"

# Delete ECR images
echo ""
echo "Deleting images from ECR..."
aws ecr batch-delete-image \
  --repository-name "$ECR_REPO" \
  --image-ids imageTag="${IMAGE_TAG}" imageTag=latest \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Images deleted from ECR"

# Delete ECR repository
echo ""
echo "Deleting ECR repository..."
aws ecr delete-repository \
  --repository-name "$ECR_REPO" \
  --force \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ ECR repository deleted: $ECR_REPO"

# Delete security group
echo ""
echo "Deleting security group..."
sleep 10  # Wait for ENI cleanup
aws ec2 delete-security-group \
  --group-id "$SG_ID" \
  --region "$REGION" 2>/dev/null && \
  echo "✅ Security group deleted" || \
  echo "⚠️  Security group deletion pending (network interfaces still detaching)"

# Clean up local Docker images
echo ""
echo "Cleaning up local Docker images..."
docker rmi "legacy-app:${IMAGE_TAG}" "legacy-app:latest" 2>/dev/null || true
docker rmi "${REPO_URI}:${IMAGE_TAG}" "${REPO_URI}:latest" 2>/dev/null || true
echo "✅ Local Docker images removed"

# Remove application directory
echo ""
echo "Removing application directory..."
rm -rf "$APP_DIR"
rm -f /tmp/task-definition.json
echo "✅ Application files deleted"

echo ""
echo "========================================="
echo "✅ Cleanup completed successfully!"
echo "========================================="
echo ""
echo "All resources have been deleted:"
echo "  ✓ ECS service stopped and deleted"
echo "  ✓ ECS cluster deleted"
echo "  ✓ Task definitions deregistered"
echo "  ✓ CloudWatch log group deleted"
echo "  ✓ ECR images deleted"
echo "  ✓ ECR repository deleted"
echo "  ✓ Security group deleted"
echo "  ✓ Local Docker images removed"
echo "  ✓ Application files removed"
echo ""
echo "Note: IAM role 'ecsTaskExecutionRole' was not deleted"
echo "      (may be used by other ECS tasks)"
echo ""
```

**Expected Output:**
```
Starting cleanup process...

Stopping ECS service...
✅ Service scaled down to 0 tasks

Deleting ECS service...
✅ ECS service deleted: legacy-app-service

Deleting ECS cluster...
✅ ECS cluster deleted: legacy-app-cluster

Deregistering task definition...
  ✓ Deregistered: legacy-app-task:1

Deleting CloudWatch log group...
✅ Log group deleted

Deleting images from ECR...
✅ Images deleted from ECR

Deleting ECR repository...
✅ ECR repository deleted: legacy-app-repo

Deleting security group...
✅ Security group deleted

Cleaning up local Docker images...
✅ Local Docker images removed

Removing application directory...
✅ Application files deleted

=========================================
✅ Cleanup completed successfully!
=========================================

All resources have been deleted:
  ✓ ECS service stopped and deleted
  ✓ ECS cluster deleted
  ✓ Task definitions deregistered
  ✓ CloudWatch log group deleted
  ✓ ECR images deleted
  ✓ ECR repository deleted
  ✓ Security group deleted
  ✓ Local Docker images removed
  ✓ Application files removed

Note: IAM role 'ecsTaskExecutionRole' was not deleted
      (may be used by other ECS tasks)
```

---

## Best Practices

### Dockerfile Optimization
- **Multi-stage builds**: Separate build and runtime stages
- **Layer caching**: Order commands from least to most frequently changed
- **Minimal base images**: Use slim or alpine variants
- **Non-root user**: Run containers as non-root for security
- **.dockerignore**: Exclude unnecessary files from build context

### Container Security
- **Image scanning**: Enable ECR image scanning for vulnerabilities
- **Secrets management**: Use AWS Secrets Manager, not environment variables
- **Read-only filesystem**: Mount volumes as read-only when possible
- **Security groups**: Restrict network access to necessary ports only
- **Regular updates**: Keep base images and dependencies updated

### ECS Best Practices
- **Health checks**: Define health checks in task definitions
- **Resource limits**: Set appropriate CPU and memory limits
- **Auto scaling**: Configure service auto scaling based on metrics
- **Load balancing**: Use ALB/NLB for production workloads
- **Logging**: Centralize logs with CloudWatch Logs

### Cost Optimization
- **Fargate Spot**: Use Fargate Spot for fault-tolerant workloads
- **Right-sizing**: Choose appropriate CPU/memory for tasks
- **Image size**: Minimize image size to reduce storage and transfer costs
- **Lifecycle policies**: Clean up old ECR images automatically
- **Task scheduling**: Use scheduled scaling for predictable workloads

### Operational Excellence
- **CI/CD integration**: Automate builds and deployments
- **Monitoring**: Set up CloudWatch alarms for failures
- **Tagging**: Tag all resources for cost allocation
- **Documentation**: Document application dependencies and configs
- **Blue/green deployments**: Use ECS deployment strategies

---

## Troubleshooting

### Issue: Docker Build Fails
**Cause**: Missing dependencies or Dockerfile errors  
**Solution**:
```bash
# Check Dockerfile syntax
docker build --no-cache -t test-image .

# View build logs
docker build --progress=plain -t test-image .

# Verify base image exists
docker pull python:3.11-slim
```

### Issue: Cannot Push to ECR
**Cause**: Authentication expired or permissions missing  
**Solution**:
```bash
# Re-authenticate to ECR
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin $REPO_URI

# Check ECR permissions
aws ecr get-repository-policy --repository-name $ECR_REPO

# Verify IAM permissions for ECR
aws iam get-user --query 'User.Arn'
```

### Issue: ECS Task Fails to Start
**Cause**: Invalid task definition or insufficient permissions  
**Solution**:
```bash
# Check task stopped reason
aws ecs describe-tasks \
  --cluster $CLUSTER_NAME \
  --tasks $TASK_ARN \
  --query 'tasks[0].stoppedReason'

# View task events
aws ecs describe-tasks \
  --cluster $CLUSTER_NAME \
  --tasks $TASK_ARN \
  --query 'tasks[0].containers[0].reason'

# Check CloudWatch logs
aws logs tail /ecs/$TASK_FAMILY --follow
```

### Issue: Cannot Access Application
**Cause**: Security group or network configuration  
**Solution**:
```bash
# Verify security group allows port 8080
aws ec2 describe-security-groups --group-ids $SG_ID

# Check if public IP is assigned
aws ecs describe-tasks \
  --cluster $CLUSTER_NAME \
  --tasks $TASK_ARN \
  --query 'tasks[0].attachments[0].details'

# Test from within VPC
aws ec2 run-instances --image-id ami-xxx --user-data "curl http://$PRIVATE_IP:8080"
```

### Issue: High ECR Storage Costs
**Cause**: Too many old images retained  
**Solution**:
```bash
# Create lifecycle policy to delete old images
aws ecr put-lifecycle-policy \
  --repository-name $ECR_REPO \
  --lifecycle-policy-text '{
    "rules": [{
      "rulePriority": 1,
      "description": "Keep last 5 images",
      "selection": {
        "tagStatus": "any",
        "countType": "imageCountMoreThan",
        "countNumber": 5
      },
      "action": {
        "type": "expire"
      }
    }]
  }'
```

---

## Additional Resources

### AWS Documentation
- [Amazon ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [AWS Fargate Documentation](https://docs.aws.amazon.com/fargate/)
- [Amazon ECR Documentation](https://docs.aws.amazon.com/ecr/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

### Container Migration Strategies
- **Lift and Shift**: Containerize as-is (this lab)
- **Replatform**: Optimize for containers during migration
- **Refactor**: Redesign as microservices
- **Rebuild**: Rewrite for cloud-native architecture

### Related Services
- **Amazon EKS**: Managed Kubernetes for complex orchestration
- **AWS App Runner**: Simplified container deployment
- **AWS Copilot**: CLI for containerized applications
- **AWS App2Container**: Automated legacy app containerization

### Use Cases
- **Legacy Modernization**: Containerize monolithic applications
- **Microservices**: Break down applications into services
- **CI/CD**: Automated testing and deployment
- **Multi-cloud**: Portable containers across clouds
- **Development**: Consistent dev/test/prod environments

---

## Key Takeaways

1. **Containerization Benefits**: Portability, consistency, and efficiency
2. **Docker Best Practices**: Use slim images, non-root users, and health checks
3. **ECR Integration**: Private, secure container registry with scanning
4. **Fargate Advantages**: Serverless containers without managing infrastructure
5. **Local Testing**: Always test containers locally before deploying
6. **Security First**: Implement security at every layer (image, network, access)
7. **Monitoring**: Use CloudWatch for logs and metrics
8. **Cost Management**: Right-size resources and clean up old images

---

## Summary

In this lab, you successfully:
- ✅ Created a legacy Python Flask application for containerization
- ✅ Wrote production-ready Dockerfile with best practices
- ✅ Built and tested Docker images locally
- ✅ Created Amazon ECR repository with security features
- ✅ Authenticated Docker to ECR and pushed images
- ✅ Configured VPC, subnets, and security groups
- ✅ Created ECS cluster with Fargate capacity
- ✅ Set up IAM roles for ECS task execution
- ✅ Created and registered ECS task definitions
- ✅ Deployed containerized application to ECS Fargate
- ✅ Validated application accessibility and functionality
- ✅ Performed comprehensive resource cleanup

Containerization with Docker and AWS ECS Fargate provides a powerful platform for modernizing legacy applications, enabling scalability, portability, and operational efficiency without the overhead of managing infrastructure.

---

## End of Lab 15.D

**Next Lab**: Lab 15.E - Modernize to Serverless Architecture

---
