# Lab 6.C: Deploy Container to ECS with Fargate

## Overview
This lab demonstrates how to deploy a containerized Python Flask API to Amazon ECS using AWS Fargate, a serverless compute engine for containers. Fargate eliminates the need to manage EC2 instances, allowing you to focus solely on your application. You'll build a Docker image, push it to ECR, and deploy it using Fargate with automatic networking and load balancing.

---

## Objectives
- Create simple Python Flask joke API
- Build Docker image and push to ECR
- Create ECS cluster for Fargate
- Create Fargate task definition
- Deploy ECS service with Fargate launch type
- Configure Application Load Balancer (optional)
- Test deployed API endpoints
- Clean up all resources to stop charges

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Docker installed and running
- IAM permissions for ECR, ECS, EC2, and ELB
- Default VPC with public subnets in multiple AZs
- Basic understanding of Docker and containers

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID and set region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="ap-southeast-2"

# Set resource names
REPO_NAME="joke-api-fargate"
IMAGE_TAG="latest"
CLUSTER_NAME="lab-fargate-cluster"
TASK_FAMILY="joke-api-fargate-task"
SERVICE_NAME="joke-api-fargate-service"
CONTAINER_NAME="joke-api"

echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "REGION=$REGION"

# Verify Docker is running
docker --version || { echo "❌ Docker not installed"; exit 1; }

```

---

## Step 2 – Create Flask Application

```bash
# Create project directory
mkdir -p joke-api-fargate
cd joke-api-fargate

# Create Flask application
cat > app.py <<'EOF'
from flask import Flask, jsonify
import random

app = Flask(__name__)

# Joke database
JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why do Java developers wear glasses? Because they don't C#!",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem!",
    "Why did the developer go broke? Because he used up all his cache!",
    "What's a programmer's favorite hangout place? Foo Bar!",
    "Why do programmers hate nature? It has too many bugs!",
    "What do you call a programmer from Finland? Nerdic!",
    "Why did the programmer quit his job? Because he didn't get arrays!",
    "What's the object-oriented way to become wealthy? Inheritance!",
    "Why do programmers always mix up Halloween and Christmas? Because Oct 31 == Dec 25!"
]

@app.route('/')
def welcome():
    return jsonify({
        "message": "Welcome to the Fargate Joke API!",
        "platform": "AWS ECS Fargate (Serverless Containers)",
        "endpoints": {
            "/": "This welcome message",
            "/joke": "Get a random joke",
            "/jokes": "Get all jokes"
        }
    })

@app.route('/joke')
def get_joke():
    return jsonify({
        "joke": random.choice(JOKES),
        "platform": "Fargate"
    })

@app.route('/jokes')
def get_all_jokes():
    return jsonify({
        "count": len(JOKES),
        "jokes": JOKES,
        "platform": "Fargate"
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
EOF

# Create requirements file
cat > requirements.txt <<'EOF'
flask==3.0.0
werkzeug==3.0.1
EOF
```

---

## Step 3 – Create Dockerfile

```bash
# Create Dockerfile
cat > Dockerfile <<'EOF'
# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Expose port 80
EXPOSE 80

# Run the application
CMD ["python", "app.py"]
EOF
```

---

## Step 4 – Build and Test Docker Image Locally

```bash
# Build Docker image
docker build --tag "${REPO_NAME}:${IMAGE_TAG}" --platform linux/amd64 .

# Test locally (optional)
CONTAINER_ID=$(docker run -d -p 8080:80 "${REPO_NAME}:${IMAGE_TAG}")
echo "CONTAINER_ID=$CONTAINER_ID"

sleep 3

curl -s http://localhost:8080/ | python3 -m json.tool

# Open in browser
"$BROWSER" "http://localhost:8080/"

# Stop and remove container
docker stop "$CONTAINER_ID"
docker rm "$CONTAINER_ID"
```

---

## Step 5 – Create ECR Repository and Push Image

```bash
# Return to parent directory
cd ..

# Create ECR repository
aws ecr create-repository \
  --repository-name "$REPO_NAME" \
  --region "$REGION" \
  --image-scanning-configuration scanOnPush=true

# Get repository URI
REPO_URI=$(aws ecr describe-repositories \
  --repository-names "$REPO_NAME" \
  --query 'repositories[0].repositoryUri' \
  --output text \
  --region "$REGION")
echo "REPO_URI=$REPO_URI"

# Authenticate Docker to ECR
aws ecr get-login-password --region "$REGION" | docker login \
  --username AWS \
  --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Tag and push image to ECR
docker tag "${REPO_NAME}:${IMAGE_TAG}" "${REPO_URI}:${IMAGE_TAG}"
docker push "${REPO_URI}:${IMAGE_TAG}"
```

---

## Step 6 – Create ECS Cluster

```bash
# Create ECS cluster (Fargate doesn't need EC2 instances)
aws ecs create-cluster --cluster-name "$CLUSTER_NAME" --region "$REGION"
```

---

## Step 7 – Create IAM Task Execution Role

```bash
# Create trust policy for ECS tasks
cat > fargate-task-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create ECS task execution role
TASK_ROLE_NAME="ecsTaskExecutionRole-fargate-lab"

aws iam create-role \
  --role-name "$TASK_ROLE_NAME" \
  --assume-role-policy-document file://fargate-task-trust-policy.json \
  2>/dev/null || echo "Role already exists"

# Attach AWS managed policy
aws iam attach-role-policy \
  --role-name "$TASK_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Get role ARN
TASK_ROLE_ARN=$(aws iam get-role \
  --role-name "$TASK_ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)
echo "TASK_ROLE_ARN=$TASK_ROLE_ARN"

# Wait for role propagation
sleep 10
```

---

## Step 8 – Create Security Group

```bash
# Get default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region "$REGION")
echo "VPC_ID=$VPC_ID"

# Create security group
SG_NAME="fargate-joke-api-sg"

SG_ID=$(aws ec2 create-security-group \
  --group-name "$SG_NAME" \
  --description "Security group for Fargate joke API" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)
echo "SG_ID=$SG_ID"

# Allow HTTP traffic from anywhere
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"
```

---

## Step 9 – Get Public Subnets

```bash
# Get public subnets in default VPC
SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[0:2].SubnetId' \
  --output text \
  --region "$REGION")

SUBNET1=$(echo "$SUBNETS" | awk '{print $1}')
SUBNET2=$(echo "$SUBNETS" | awk '{print $2}')

echo "SUBNET1=$SUBNET1"
echo "SUBNET2=$SUBNET2"
```

---

## Step 10 – Register Fargate Task Definition

```bash
# Create task definition JSON for Fargate
cat > fargate-task-definition.json <<EOF
{
  "family": "${TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "${TASK_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "${CONTAINER_NAME}",
      "image": "${REPO_URI}:${IMAGE_TAG}",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 80,
          "protocol": "tcp"
        }
      ],
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

# Register task definition
aws ecs register-task-definition \
  --cli-input-json file://fargate-task-definition.json \
  --region "$REGION"

```

---

## Step 11 – Create Fargate Service

```bash
# Create ECS service with Fargate launch type
aws ecs create-service \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --task-definition "$TASK_FAMILY" \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET1,$SUBNET2],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --region "$REGION"

echo ""  
echo "Waiting for task to start (this takes ~2 minutes)..."
sleep 120
```

---

## Step 12 – Get Task Public IP and Test API

```bash
# Get running task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --query 'taskArns[0]' \
  --output text \
  --region "$REGION")
echo "TASK_ARN=$TASK_ARN"

# Get task details
TASK_DETAILS=$(aws ecs describe-tasks \
  --cluster "$CLUSTER_NAME" \
  --tasks "$TASK_ARN" \
  --query 'tasks[0]' \
  --region "$REGION")

# Get ENI ID
ENI_ID=$(echo "$TASK_DETAILS" | python3 -c "import sys, json; print(json.load(sys.stdin)['attachments'][0]['details'][1]['value'])")
echo "ENI_ID=$ENI_ID"

# Get public IP from ENI
PUBLIC_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids "$ENI_ID" \
  --query 'NetworkInterfaces[0].Association.PublicIp' \
  --output text \
  --region "$REGION")
echo "PUBLIC_IP=$PUBLIC_IP"

echo ""
echo "API Base URL: http://${PUBLIC_IP}"
echo ""

# Wait for application to be ready
sleep 10

# Test welcome endpoint
echo "Testing / (welcome):"
curl -s "http://${PUBLIC_IP}/" | python3 -m json.tool
echo ""

# Test random joke endpoint
echo "Testing /joke (random joke):"
curl -s "http://${PUBLIC_IP}/joke" | python3 -m json.tool
echo ""

# Test all jokes endpoint
echo "Testing /jokes (all jokes):"
curl -s "http://${PUBLIC_IP}/jokes" | python3 -m json.tool
echo ""

# Open in browser
"$BROWSER" "http://${PUBLIC_IP}/"
"$BROWSER" "http://${PUBLIC_IP}/joke"
"$BROWSER" "http://${PUBLIC_IP}/jokes"

```

---

## Step 13 – View Fargate Service Status

```bash
# View cluster status
aws ecs describe-clusters \
  --clusters "$CLUSTER_NAME" \
  --query 'clusters[0].{Name:clusterName,RunningTasks:runningTasksCount,PendingTasks:pendingTasksCount}' \
  --output table \
  --region "$REGION"

# View service status
aws ecs describe-services \
  --cluster "$CLUSTER_NAME" \
  --services "$SERVICE_NAME" \
  --query 'services[0].{Name:serviceName,Status:status,DesiredCount:desiredCount,RunningCount:runningCount,LaunchType:launchType}' \
  --output table \
  --region "$REGION"

# View running tasks
aws ecs list-tasks \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --query 'taskArns' \
  --output table \
  --region "$REGION"
```

---

## Step 14 – Cleanup Resources (IMPORTANT!)

```bash
# Delete ECS service
aws ecs update-service \
  --cluster "$CLUSTER_NAME" \
  --service "$SERVICE_NAME" \
  --desired-count 0 \
  --region "$REGION"

aws ecs delete-service \
  --cluster "$CLUSTER_NAME" \
  --service "$SERVICE_NAME" \
  --force \
  --region "$REGION"

sleep 60

# Deregister task definition
TASK_DEF_ARN=$(aws ecs list-task-definitions \
  --family-prefix "$TASK_FAMILY" \
  --query 'taskDefinitionArns[0]' \
  --output text \
  --region "$REGION")

aws ecs deregister-task-definition \
  --task-definition "$TASK_DEF_ARN" \
  --region "$REGION"

# Delete ECS cluster
aws ecs delete-cluster --cluster "$CLUSTER_NAME" --region "$REGION"

# Delete security group
aws ec2 delete-security-group --group-id "$SG_ID" --region "$REGION"

# Delete ECR repository
aws ecr delete-repository --repository-name "$REPO_NAME" --force --region "$REGION"

# Delete IAM role
aws iam detach-role-policy \
  --role-name "$TASK_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

aws iam delete-role --role-name "$TASK_ROLE_NAME"

# Delete CloudWatch log group
aws logs delete-log-group --log-group-name "/ecs/${TASK_FAMILY}" --region "$REGION" 2>/dev/null || true

# Delete local files
cd ..
rm -rf joke-api-fargate
rm -f fargate-task-trust-policy.json fargate-task-definition.json

echo ""
echo "✅ Cleanup completed - all resources deleted"
```

---

## Summary

In this lab, you have:
- Created Python Flask joke API
- Built Docker image and pushed to ECR
- Created ECS cluster for Fargate
- Configured IAM roles for Fargate tasks
- Registered Fargate task definition (0.25 vCPU, 0.5 GB)
- Created Fargate service with public networking
- Tested all API endpoints
- Cleaned up all resources to stop charges

**Key Takeaways:**
- **Fargate**: Serverless container platform (no EC2 management)
- **awsvpc Network Mode**: Each task gets own ENI and IP
- **Cost Model**: Pay per vCPU/GB-hour (minimum 0.25 vCPU, 0.5 GB)
- **Automatic Scaling**: Can scale tasks without managing instances
- **Public IP**: Assign public IP for internet access

**Best Practices:**
- Use smallest CPU/memory needed (0.25 vCPU minimum)
- Enable CloudWatch logs for debugging
- Use task IAM roles for AWS service access
- Implement health checks for production
- Use Application Load Balancer for multiple tasks
- Tag resources for cost tracking
- **DELETE resources immediately after testing**

---

## Production Enhancements

For production Fargate deployments:

1. **Application Load Balancer**
   - Distribute traffic across multiple tasks
   - Health checks and auto-healing
   - SSL termination with ACM

2. **Auto Scaling**
   ```bash
   aws application-autoscaling register-scalable-target \
     --service-namespace ecs \
     --resource-id service/cluster/service \
     --scalable-dimension ecs:service:DesiredCount \
     --min-capacity 2 \
     --max-capacity 10
   ```

3. **Private Networking**
   - Run tasks in private subnets
   - Use NAT Gateway for outbound
   - ALB in public subnets

4. **Secrets Management**
   - Use AWS Secrets Manager
   - Reference in task definition

5. **CI/CD Pipeline**
   - Build → Push to ECR → Update ECS service
   - Blue/green deployments

6. **Monitoring**
   - CloudWatch Container Insights
   - Custom metrics and alarms
   - Distributed tracing with X-Ray
