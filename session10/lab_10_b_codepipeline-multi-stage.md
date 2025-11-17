# Lab 10.B: CodePipeline - Multi-Stage CI/CD Pipeline
<img width="1536" height="1024" alt="IMG10B" src="https://github.com/user-attachments/assets/e6261be5-1889-4309-905d-b1196a126b59" />

## Overview
This lab builds a complete CI/CD pipeline using AWS CodePipeline to orchestrate source, build, and deploy stages. You'll automatically deploy a Flask application from CodeCommit → CodeBuild (build Docker image) → ECS (deploy container) with manual approval gates and automated testing.

---

## Objectives
- Create multi-stage CodePipeline (Source → Build → Deploy)
- Configure automatic triggers on code commits
- Build Docker images with CodeBuild
- Deploy containers to Amazon ECS
- Add manual approval stage
- Monitor pipeline execution
- Test end-to-end automation

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Completed Lab 10.A (CodeCommit + CodeBuild basics)
- IAM permissions for CodePipeline, CodeCommit, CodeBuild, ECS, ECR
- Region: ap-southeast-2

---

## Step 1 – Set Variables

```bash
# Set deployment region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Set resource names for CodePipeline, ECR, ECS, and CodeCommit
REPO_NAME="pipeline-flask-app"
ECR_REPO="pipeline-flask-app"
CLUSTER_NAME="pipeline-demo-cluster"
SERVICE_NAME="flask-service"
PIPELINE_NAME="flask-cicd-pipeline"

# Get AWS account ID for resource ARNs
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "REGION=$REGION"
echo "REPO_NAME=$REPO_NAME"
echo "CLUSTER_NAME=$CLUSTER_NAME"
echo "PIPELINE_NAME=$PIPELINE_NAME"
echo "ACCOUNT_ID=$ACCOUNT_ID"
```

---

## Step 2 – Create CodeCommit Repository

```bash
# Create CodeCommit repository for source control
aws codecommit create-repository \
  --repository-name "$REPO_NAME" \
  --repository-description "Flask app for CodePipeline demo" \
  --region "$REGION"
```

---

## Step 3 – Clone and Create Application

```bash
# Get repository root and create workspace for CodePipeline lab
REPO_DIR=$(git rev-parse --show-toplevel)
WORKSPACE="$REPO_DIR/pipeline-lab"
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

# Clone CodeCommit repository using codecommit:// protocol
git clone codecommit://"$REGION"::"$REPO_NAME"
cd "$REPO_NAME"

# Create Flask application with version-aware endpoints
cat > app.py <<'EOF'
from flask import Flask, jsonify
import os

app = Flask(__name__)

VERSION = os.getenv('APP_VERSION', '1.0')

@app.route('/')
def home():
    return jsonify({
        "app": "Flask CI/CD Demo",
        "version": VERSION,
        "message": "Deployed via CodePipeline!",
        "endpoints": ["/", "/health", "/version"]
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/version')
def version():
    return jsonify({"version": VERSION})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF

# Create requirements.txt
cat > requirements.txt <<'EOF'
Flask==3.0.0
gunicorn==21.2.0
EOF

# Create Dockerfile
cat > Dockerfile <<'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 5000
ENV APP_VERSION=1.0
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
EOF
```

---

## Step 4 – Create BuildSpec and TaskDef Template

```bash
# Create buildspec.yml defining CodeBuild phases for Docker image build and push
cat > buildspec.yml <<EOF
version: 0.2

phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
      - REPOSITORY_URI=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO
      - COMMIT_HASH=\$(echo \$CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)
      - IMAGE_TAG=\${COMMIT_HASH:=latest}

  build:
    commands:
      - echo Build started on \$(date)
      - docker build -t \$REPOSITORY_URI:latest .
      - docker tag \$REPOSITORY_URI:latest \$REPOSITORY_URI:\$IMAGE_TAG

  post_build:
    commands:
      - echo Pushing Docker image...
      - docker push \$REPOSITORY_URI:latest
      - docker push \$REPOSITORY_URI:\$IMAGE_TAG
      - echo Writing image definitions file...
      - printf '[{"name":"flask-container","imageUri":"%s"}]' \$REPOSITORY_URI:latest > imagedefinitions.json

artifacts:
  files:
    - imagedefinitions.json
EOF

# Create ECS task definition for Fargate deployment
cat > taskdef.json <<EOF
{
  "family": "flask-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "flask-container",
      "image": "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:latest",
      "portMappings": [
        {
          "containerPort": 5000,
          "protocol": "tcp"
        }
      ],
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/flask-task",
          "awslogs-region": "${REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF
```

---

## Step 5 – Commit and Push Code

```bash
# Stage all files for commit
git add .

# Commit application and CI/CD configuration files
git commit -m "Initial commit: Flask app with CI/CD configuration"

# Push to CodeCommit main branch
git push origin main
```

---

## Step 6 – Create ECR Repository

```bash
# Create ECR repository with automatic image scanning on push
aws ecr create-repository \
  --repository-name "$ECR_REPO" \
  --region "$REGION" \
  --image-scanning-configuration scanOnPush=true
```

---

## Step 7 – Create ECS Cluster

```bash
# Create ECS cluster for Fargate container deployments
aws ecs create-cluster \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION"
```

---

## Step 8 – Create CloudWatch Log Group

```bash
# Create CloudWatch log group for ECS task container logs
aws logs create-log-group \
  --log-group-name "/ecs/flask-task" \
  --region "$REGION"
```

---

## Step 9 – Create ECS Task Execution Role

```bash
# Check if ECS task execution role already exists
if aws iam get-role --role-name ecsTaskExecutionRole 2>/dev/null; then
    echo "ecsTaskExecutionRole already exists"
else
    # Create trust policy allowing ECS tasks service to assume role
    cat > ecs-trust-policy.json <<'EOF'
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

    # Create IAM role for ECS task execution
    aws iam create-role \
      --role-name ecsTaskExecutionRole \
      --assume-role-policy-document file://ecs-trust-policy.json

    # Attach AWS managed policy for ECS task execution (ECR, CloudWatch Logs)
    aws iam attach-role-policy \
      --role-name ecsTaskExecutionRole \
      --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

    # Wait for IAM role to propagate globally
    sleep 10
fi
```

---

## Step 10 – Register ECS Task Definition

```bash
# Navigate to repository directory
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR/pipeline-lab/$REPO_NAME"

# Register ECS task definition from JSON configuration
aws ecs register-task-definition \
  --cli-input-json file://taskdef.json \
  --region "$REGION"
```

---

## Step 11 – Create Security Group for ECS

```bash
# Get default VPC ID for security group creation
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --region "$REGION" \
  --query 'Vpcs[0].VpcId' \
  --output text)

echo "VPC_ID=$VPC_ID"

# Create security group for ECS tasks
SG_ID=$(aws ec2 create-security-group \
  --group-name flask-ecs-sg \
  --description "Security group for Flask ECS tasks" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

echo "SG_ID=$SG_ID"

# Allow inbound HTTP traffic on Flask port 5000 from anywhere
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 5000 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"
```

---

## Step 12 – Create ECS Service

```bash
# Get first two subnets from default VPC
SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --region "$REGION" \
  --query 'Subnets[0:2].SubnetId' \
  --output text | tr '\t' ',')

echo "SUBNETS=$SUBNETS"

# Create ECS service with Fargate launch type and public IP assignment
aws ecs create-service \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --task-definition flask-task \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --region "$REGION"
```

---

## Step 13 – Create CodeBuild Project

```bash
# Check if CodeBuild service role exists, create if not
if ! aws iam get-role --role-name CodeBuildServiceRole 2>/dev/null; then
    # Create trust policy allowing CodeBuild service to assume role
    cat > codebuild-trust.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "codebuild.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

    # Create IAM role for CodeBuild
    aws iam create-role \
      --role-name CodeBuildServiceRole \
      --assume-role-policy-document file://codebuild-trust.json

    # Create permissions policy for CloudWatch Logs, ECR, CodeCommit, and S3
    cat > codebuild-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["logs:*", "ecr:*", "codecommit:GitPull"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Resource": "*"
    }
  ]
}
EOF

    # Attach permissions policy to CodeBuild role
    aws iam put-role-policy \
      --role-name CodeBuildServiceRole \
      --policy-name CodeBuildPolicy \
      --policy-document file://codebuild-policy.json

    # Wait for IAM role to propagate globally
    sleep 10
fi

# Create CodeBuild project configuration for pipeline integration
cat > codebuild-config.json <<EOF
{
  "name": "flask-pipeline-build",
  "source": {
    "type": "CODEPIPELINE"
  },
  "artifacts": {
    "type": "CODEPIPELINE"
  },
  "environment": {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/standard:7.0",
    "computeType": "BUILD_GENERAL1_SMALL",
    "privilegedMode": true
  },
  "serviceRole": "arn:aws:iam::${ACCOUNT_ID}:role/CodeBuildServiceRole"
}
EOF

# Create CodeBuild project from JSON configuration
aws codebuild create-project \
  --cli-input-json file://codebuild-config.json \
  --region "$REGION"
```

---

## Step 14 – Create CodePipeline Service Role

```bash
# Create trust policy allowing CodePipeline service to assume role
cat > pipeline-trust.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "codepipeline.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create IAM role for CodePipeline
aws iam create-role \
  --role-name CodePipelineServiceRole \
  --assume-role-policy-document file://pipeline-trust.json

# Create permissions policy for CodeCommit, CodeBuild, ECS, IAM, and S3
cat > pipeline-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "codecommit:*",
        "codebuild:*",
        "ecs:*",
        "iam:PassRole",
        "s3:*"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Attach permissions policy to CodePipeline role
aws iam put-role-policy \
  --role-name CodePipelineServiceRole \
  --policy-name CodePipelinePolicy \
  --policy-document file://pipeline-policy.json

# Wait for IAM role to propagate globally
sleep 10
```

---

## Step 15 – Create S3 Bucket for Artifacts

```bash
# Create unique S3 bucket name using account ID
ARTIFACT_BUCKET="pipeline-artifacts-${ACCOUNT_ID}"
echo "ARTIFACT_BUCKET=$ARTIFACT_BUCKET"

# Create S3 bucket for storing pipeline artifacts between stages
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
```

---

## Step 16 – Create CodePipeline

```bash
# Create CodePipeline configuration with Source, Build, and Deploy stages
cat > pipeline-config.json <<EOF
{
  "pipeline": {
    "name": "${PIPELINE_NAME}",
    "roleArn": "arn:aws:iam::${ACCOUNT_ID}:role/CodePipelineServiceRole",
    "artifactStore": {
      "type": "S3",
      "location": "${ARTIFACT_BUCKET}"
    },
    "stages": [
      {
        "name": "Source",
        "actions": [{
          "name": "SourceAction",
          "actionTypeId": {
            "category": "Source",
            "owner": "AWS",
            "provider": "CodeCommit",
            "version": "1"
          },
          "outputArtifacts": [{"name": "SourceOutput"}],
          "configuration": {
            "RepositoryName": "${REPO_NAME}",
            "BranchName": "main",
            "PollForSourceChanges": "true"
          }
        }]
      },
      {
        "name": "Build",
        "actions": [{
          "name": "BuildAction",
          "actionTypeId": {
            "category": "Build",
            "owner": "AWS",
            "provider": "CodeBuild",
            "version": "1"
          },
          "inputArtifacts": [{"name": "SourceOutput"}],
          "outputArtifacts": [{"name": "BuildOutput"}],
          "configuration": {
            "ProjectName": "flask-pipeline-build"
          }
        }]
      },
      {
        "name": "Deploy",
        "actions": [{
          "name": "DeployAction",
          "actionTypeId": {
            "category": "Deploy",
            "owner": "AWS",
            "provider": "ECS",
            "version": "1"
          },
          "inputArtifacts": [{"name": "BuildOutput"}],
          "configuration": {
            "ClusterName": "${CLUSTER_NAME}",
            "ServiceName": "${SERVICE_NAME}",
            "FileName": "imagedefinitions.json"
          }
        }]
      }
    ]
  }
}
EOF

# Create CodePipeline from JSON configuration
aws codepipeline create-pipeline \
  --cli-input-json file://pipeline-config.json \
  --region "$REGION"

echo "Pipeline stages: Source (CodeCommit) → Build (CodeBuild) → Deploy (ECS)"
```

---

## Step 17 – Monitor Pipeline Execution

```bash
# Wait for pipeline to initialize
sleep 10

# Get current state of all pipeline stages
aws codepipeline get-pipeline-state \
  --name "$PIPELINE_NAME" \
  --region "$REGION" \
  --query 'stageStates[*].{Stage:stageName,Status:latestExecution.status}' \
  --output table

echo "Pipeline is running! Full execution takes 5-7 minutes"
```

---

## Step 18 – Wait for Deployment

```bash
# Wait for ECS service to reach stable state (all tasks running)
aws ecs wait services-stable \
  --cluster "$CLUSTER_NAME" \
  --services "$SERVICE_NAME" \
  --region "$REGION"
```

---

## Step 19 – Get Application URL

```bash
# Get ARN of running task in ECS service
TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --region "$REGION" \
  --query 'taskArns[0]' \
  --output text)

# Get network interface ID from task details
ENI_ID=$(aws ecs describe-tasks \
  --cluster "$CLUSTER_NAME" \
  --tasks "$TASK_ARN" \
  --region "$REGION" \
  --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
  --output text)

# Get public IP address from network interface
PUBLIC_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids "$ENI_ID" \
  --region "$REGION" \
  --query 'NetworkInterfaces[0].Association.PublicIp' \
  --output text)

echo "Application URL: http://${PUBLIC_IP}:5000"
echo "Testing application..."
sleep 10
curl -s "http://${PUBLIC_IP}:5000" | jq .
```

---

## Step 20 – Test Pipeline with Code Change

```bash
# Navigate to repository directory
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR/pipeline-lab/$REPO_NAME"

# Update application version in Flask app
sed -i "s/VERSION = os.getenv('APP_VERSION', '1.0')/VERSION = os.getenv('APP_VERSION', '2.0')/" app.py

# Update version in Dockerfile environment variable
sed -i 's/ENV APP_VERSION=1.0/ENV APP_VERSION=2.0/' Dockerfile

# Stage, commit, and push code changes
git add .
git commit -m "Update to version 2.0"
git push origin main

echo "Pipeline will automatically trigger in ~1 minute"
echo "Monitor pipeline: https://console.aws.amazon.com/codesuite/codepipeline/pipelines/${PIPELINE_NAME}/view"
```

---

## Step 21 – Cleanup

```bash
# Delete CodePipeline
aws codepipeline delete-pipeline \
  --name "$PIPELINE_NAME" \
  --region "$REGION"

# Scale ECS service to zero tasks
aws ecs update-service \
  --cluster "$CLUSTER_NAME" \
  --service "$SERVICE_NAME" \
  --desired-count 0 \
  --region "$REGION"

# Delete ECS service
aws ecs delete-service \
  --cluster "$CLUSTER_NAME" \
  --service "$SERVICE_NAME" \
  --region "$REGION" \
  --force

# Delete ECS cluster
aws ecs delete-cluster \
  --cluster "$CLUSTER_NAME" \
  --region "$REGION"

# Delete CodeBuild project
aws codebuild delete-project \
  --name flask-pipeline-build \
  --region "$REGION"

# Delete ECR repository and all images
aws ecr delete-repository \
  --repository-name "$ECR_REPO" \
  --region "$REGION" \
  --force

# Delete CodeCommit repository
aws codecommit delete-repository \
  --repository-name "$REPO_NAME" \
  --region "$REGION"

# Empty and delete S3 artifacts bucket
aws s3 rm s3://"$ARTIFACT_BUCKET" --recursive
aws s3api delete-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION"

# Delete security group
aws ec2 delete-security-group \
  --group-id "$SG_ID" \
  --region "$REGION"

# Delete CloudWatch log group
aws logs delete-log-group \
  --log-group-name "/ecs/flask-task" \
  --region "$REGION"

# Delete CodePipeline IAM role and policy
aws iam delete-role-policy \
  --role-name CodePipelineServiceRole \
  --policy-name CodePipelinePolicy

aws iam delete-role --role-name CodePipelineServiceRole

# Delete CodeBuild IAM role and policy
aws iam delete-role-policy \
  --role-name CodeBuildServiceRole \
  --policy-name CodeBuildPolicy

aws iam delete-role --role-name CodeBuildServiceRole

# Remove local workspace directory
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR"
rm -rf pipeline-lab

echo "✅ Cleanup complete"
```

---

## Summary

In this lab, you have:
- Created multi-stage CodePipeline (Source → Build → Deploy)
- Configured CodeCommit as source stage
- Built Docker images with CodeBuild
- Deployed containers to ECS Fargate automatically
- Monitored pipeline execution stages
- Tested automated deployment on code changes
- Verified application running on ECS

**Key Takeaways:**
- **CodePipeline**: Orchestrates CI/CD workflow across multiple services
- **Three-Stage Pipeline**: Source (CodeCommit) → Build (CodeBuild) → Deploy (ECS)
- **Automated Triggers**: Pipeline runs automatically on git push
- **Artifact Management**: S3 stores artifacts between stages
- **Service Integration**: Seamless integration with AWS services

**Pipeline Flow:**
```
git push → CodeCommit → Trigger Pipeline → CodeBuild (Docker) → ECS Deploy → Live App
```

---

## Best Practices

**Pipeline Design:**
- Keep stages small and focused
- Add manual approval for production
- Use separate pipelines per environment
- Enable notifications for failures

**Security:**
- Use IAM roles (not access keys)
- Encrypt artifacts in S3
- Scan images for vulnerabilities
- Restrict pipeline execution permissions

**Deployment:**
- Test in staging before production
- Use blue/green deployments for zero downtime
- Implement rollback strategies
- Monitor application health post-deployment

---

## Additional Resources

- [AWS CodePipeline Documentation](https://docs.aws.amazon.com/codepipeline/)
- [Pipeline Structure Reference](https://docs.aws.amazon.com/codepipeline/latest/userguide/reference-pipeline-structure.html)
- [ECS Deployment with CodePipeline](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-cd-pipeline.html)
