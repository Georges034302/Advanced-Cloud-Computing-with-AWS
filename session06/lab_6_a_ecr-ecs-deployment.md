# Lab 6.A: Build, Push to ECR, and Deploy to ECS with EC2

## Overview
This lab demonstrates the complete container workflow: building a Docker image for a simple Python Flask API, pushing it to Amazon Elastic Container Registry (ECR), and deploying it to Amazon Elastic Container Service (ECS) using the EC2 launch type with a single t2.micro instance (free tier eligible).

---

## Objectives
- Create simple Python Flask joke API
- Build Docker image locally
- Create ECR repository and push image
- Create ECS cluster with EC2 launch type
- Deploy containerized application to ECS
- Test the deployed API endpoints
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Docker installed and running locally
- IAM permissions for ECR, ECS, EC2, and IAM
- Default VPC with public subnet
- Basic understanding of Docker and containers

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set region and resource names
REGION="ap-southeast-2"
REPO_NAME="joke-api"
IMAGE_TAG="latest"
CLUSTER_NAME="lab-ecs-cluster"
TASK_FAMILY="joke-api-task"
SERVICE_NAME="joke-api-service"
CONTAINER_NAME="joke-api"
INSTANCE_TYPE="t2.micro"

# Verify Docker is running
docker --version || { echo "❌ Docker not installed"; exit 1; }
```

---

## Step 2 – Create Flask Application

```bash
# Create project directory
mkdir -p joke-api
cd joke-api

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
    "Why did the programmer quit his job? Because he didn't get arrays!"
]

@app.route('/')
def welcome():
    return jsonify({
        "message": "Welcome to the Joke API!",
        "endpoints": {
            "/": "This welcome message",
            "/joke": "Get a random joke",
            "/jokes": "Get all jokes"
        }
    })

@app.route('/joke')
def get_joke():
    return jsonify({
        "joke": random.choice(JOKES)
    })

@app.route('/jokes')
def get_all_jokes():
    return jsonify({
        "count": len(JOKES),
        "jokes": JOKES
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

## Step 4 – Build Docker Image Locally

```bash
# Build Docker image for linux/amd64 platform
docker build --tag "${REPO_NAME}:${IMAGE_TAG}" --platform linux/amd64 .

# Verify image created
docker images | grep "$REPO_NAME"
```

---

## Step 5 – Create ECR Repository

```bash
# Return to parent directory
cd ..

# Create ECR repository with image scanning enabled
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
```

---

## Step 6 – Push Image to ECR

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Tag image for ECR
docker tag "${REPO_NAME}:${IMAGE_TAG}" "${REPO_URI}:${IMAGE_TAG}"

# Push image to ECR
docker push "${REPO_URI}:${IMAGE_TAG}"

# Verify image in ECR
aws ecr describe-images \
  --repository-name "$REPO_NAME" \
  --query 'imageDetails[*].{Tags:imageTags,Pushed:imagePushedAt,Size:imageSizeInBytes}' \
  --output table \
  --region "$REGION"
```

---

## Step 7 – Create ECS Cluster

```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name "$CLUSTER_NAME" --region "$REGION"
```

---

## Step 8 – Create IAM Roles

```bash
# Create ECS task execution role trust policy
cat > ecs-task-trust-policy.json <<'EOF'
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
TASK_ROLE_NAME="ecsTaskExecutionRole-lab"

aws iam create-role \
  --role-name "$TASK_ROLE_NAME" \
  --assume-role-policy-document file://ecs-task-trust-policy.json \
  2>/dev/null || true

# Attach AWS managed policy
aws iam attach-role-policy \
  --role-name "$TASK_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Create ECS instance role trust policy
cat > ecs-instance-trust-policy.json <<'EOF'
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

# Create ECS instance role
INSTANCE_ROLE_NAME="ecsInstanceRole-lab"

aws iam create-role \
  --role-name "$INSTANCE_ROLE_NAME" \
  --assume-role-policy-document file://ecs-instance-trust-policy.json \
  2>/dev/null || true

# Attach AWS managed policy for ECS instances
aws iam attach-role-policy \
  --role-name "$INSTANCE_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role

# Create instance profile and add role
INSTANCE_PROFILE_NAME="ecsInstanceProfile-lab"

aws iam create-instance-profile \
  --instance-profile-name "$INSTANCE_PROFILE_NAME" \
  2>/dev/null || true

aws iam add-role-to-instance-profile \
  --instance-profile-name "$INSTANCE_PROFILE_NAME" \
  --role-name "$INSTANCE_ROLE_NAME" \
  2>/dev/null || true

# Wait for IAM role propagation
sleep 10
```

---

## Step 9 – Create Security Group

```bash
# Get default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region "$REGION")
echo "VPC_ID=$VPC_ID"

# Create security group
SG_NAME="ecs-joke-api-sg"
SG_ID=$(aws ec2 create-security-group \
  --group-name "$SG_NAME" \
  --description "Security group for ECS joke API" \
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

# Allow SSH traffic (optional, for debugging)
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION" \
  2>/dev/null || true
```

---

## Step 10 – Launch ECS EC2 Instance

```bash
# Get ECS-optimized AMI ID for Amazon Linux 2
ECS_AMI=$(aws ssm get-parameter \
  --name /aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id \
  --query 'Parameter.Value' \
  --output text \
  --region "$REGION")

# Get first available subnet
SUBNET_ID=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[0].SubnetId' \
  --output text \
  --region "$REGION")

# Create user data to register instance with ECS cluster
cat > ecs-user-data.sh <<EOF
#!/bin/bash
echo ECS_CLUSTER=${CLUSTER_NAME} >> /etc/ecs/ecs.config
EOF

# Launch EC2 instance for ECS
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$ECS_AMI" \
  --instance-type "$INSTANCE_TYPE" \
  --iam-instance-profile "Name=$INSTANCE_PROFILE_NAME" \
  --security-group-ids "$SG_ID" \
  --subnet-id "$SUBNET_ID" \
  --user-data file://ecs-user-data.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=ECS-Instance}]" \
  --region "$REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)
echo "INSTANCE_ID=$INSTANCE_ID"

# Wait for instance to join cluster (~2 minutes)
sleep 120
```

---

## Step 11 – Register Task Definition

```bash
# Get task execution role ARN
TASK_ROLE_ARN=$(aws iam get-role \
  --role-name "$TASK_ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)

# Create task definition JSON
cat > task-definition.json <<EOF
{
  "family": "${TASK_FAMILY}",
  "taskRoleArn": "${TASK_ROLE_ARN}",
  "executionRoleArn": "${TASK_ROLE_ARN}",
  "networkMode": "bridge",
  "containerDefinitions": [
    {
      "name": "${CONTAINER_NAME}",
      "image": "${REPO_URI}:${IMAGE_TAG}",
      "memory": 256,
      "cpu": 256,
      "essential": true,
      "portMappings": [
        {
          "containerPort": 80,
          "hostPort": 80,
          "protocol": "tcp"
        }
      ]
    }
  ],
  "requiresCompatibilities": ["EC2"]
}
EOF

# Register task definition
aws ecs register-task-definition \
  --cli-input-json file://task-definition.json \
  --region "$REGION"
```

---

## Step 12 – Create ECS Service

```bash
# Create ECS service with 1 task
aws ecs create-service \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --task-definition "$TASK_FAMILY" \
  --desired-count 1 \
  --launch-type EC2 \
  --region "$REGION"

# Wait for service to stabilize (~2 minutes)
sleep 120
```

---

## Step 13 – Get Public IP and Test API

```bash
# Get public IP of EC2 instance
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$REGION")
echo "PUBLIC_IP=$PUBLIC_IP"

echo ""
echo "API Base URL: http://${PUBLIC_IP}"
echo ""

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

# Open API in browser
"$BROWSER" "http://${PUBLIC_IP}/"
"$BROWSER" "http://${PUBLIC_IP}/joke"
"$BROWSER" "http://${PUBLIC_IP}/jokes"
```

---

## Step 14 – View ECS Service Status

```bash
# View ECS cluster status
aws ecs describe-clusters \
  --clusters "$CLUSTER_NAME" \
  --query 'clusters[0].{Name:clusterName,RegisteredInstances:registeredContainerInstancesCount,RunningTasks:runningTasksCount}' \
  --output table \
  --region "$REGION"

# View ECS service status
aws ecs describe-services \
  --cluster "$CLUSTER_NAME" \
  --services "$SERVICE_NAME" \
  --query 'services[0].{Name:serviceName,Status:status,DesiredCount:desiredCount,RunningCount:runningCount}' \
  --output table \
  --region "$REGION"

# List running tasks
aws ecs list-tasks \
  --cluster "$CLUSTER_NAME" \
  --query 'taskArns' \
  --output table \
  --region "$REGION"
```

---

## Step 15 – Cleanup Resources

```bash
# Scale down and delete ECS service
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

sleep 30

# Deregister task definition
TASK_DEF_ARN=$(aws ecs list-task-definitions \
  --family-prefix "$TASK_FAMILY" \
  --query 'taskDefinitionArns[0]' \
  --output text \
  --region "$REGION")

aws ecs deregister-task-definition \
  --task-definition "$TASK_DEF_ARN" \
  --region "$REGION"

# Terminate EC2 instance
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "$REGION"
sleep 30

# Delete ECS cluster
aws ecs delete-cluster --cluster "$CLUSTER_NAME" --region "$REGION"

# Delete security group
aws ec2 delete-security-group --group-id "$SG_ID" --region "$REGION"

# Delete ECR repository (force delete with all images)
aws ecr delete-repository --repository-name "$REPO_NAME" --force --region "$REGION"

# Remove instance profile and role association
aws iam remove-role-from-instance-profile \
  --instance-profile-name "$INSTANCE_PROFILE_NAME" \
  --role-name "$INSTANCE_ROLE_NAME" \
  2>/dev/null || true

aws iam delete-instance-profile \
  --instance-profile-name "$INSTANCE_PROFILE_NAME" \
  2>/dev/null || true

# Detach and delete IAM roles
aws iam detach-role-policy \
  --role-name "$TASK_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
  2>/dev/null || true

aws iam detach-role-policy \
  --role-name "$INSTANCE_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role \
  2>/dev/null || true

aws iam delete-role --role-name "$TASK_ROLE_NAME" 2>/dev/null || true
aws iam delete-role --role-name "$INSTANCE_ROLE_NAME" 2>/dev/null || true

# Delete local files
rm -rf joke-api
rm -f ecs-task-trust-policy.json ecs-instance-trust-policy.json
rm -f ecs-user-data.sh task-definition.json
```

---

## Summary

In this lab, you have:
- Created a simple Python Flask joke API with three endpoints
- Built Docker image locally and tested it
- Created ECR repository and pushed Docker image
- Created ECS cluster with EC2 launch type
- Configured IAM roles for ECS tasks and instances
- Launched ECS-optimized EC2 instance (t2.micro)
- Registered task definition with container configuration
- Created ECS service to run the containerized application
- Tested all API endpoints (/, /joke, /jokes)
- Cleaned up all resources

**Key Takeaways:**
- **ECR**: Private Docker registry in AWS
- **ECS EC2 Launch Type**: Run containers on managed EC2 instances
- **Task Definition**: Blueprint for running containers
- **ECS Service**: Maintains desired number of running tasks
- **Free Tier Compatible**: Uses single t2.micro instance (750 hours/month)

**Container Workflow:**
```
Build Image → Push to ECR → Define Task → Launch Instance → Run Service
```

**Best Practices:**
- Use ECS-optimized AMI for container instances
- Configure appropriate IAM roles for tasks and instances
- Use security groups to restrict network access
- Tag resources for cost tracking
- Clean up resources after testing
- Use health checks for production deployments

---