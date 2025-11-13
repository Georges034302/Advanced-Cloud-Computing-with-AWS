# Lab 10.B: CodePipeline - Multi-Stage CI/CD Pipeline

## Overview
This lab builds a complete CI/CD pipeline using AWS CodePipeline to orchestrate source, build, and deploy stages. You'll automatically deploy a Flask application from CodeCommit → CodeBuild (build Docker image) → ECS (deploy container) with manual approval gates and automated testing.

**💰 Cost**: FREE TIER (CodePipeline 1 free pipeline/month, ECS 750 hrs/month)

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

## Architecture

```
CodeCommit (Source)
      ↓
CodeBuild (Build Docker Image)
      ↓
Manual Approval (Optional)
      ↓
ECS Deployment (Deploy Container)
```

---

## Step 1 – Set Variables

```bash
# Set region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "REGION=$REGION"

# Set names
REPO_NAME="pipeline-flask-app"
ECR_REPO="pipeline-flask-app"
CLUSTER_NAME="pipeline-demo-cluster"
SERVICE_NAME="flask-service"
PIPELINE_NAME="flask-cicd-pipeline"

echo "REPO_NAME=$REPO_NAME"
echo "CLUSTER_NAME=$CLUSTER_NAME"
echo "PIPELINE_NAME=$PIPELINE_NAME"

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
  --repository-description "Flask app for CodePipeline demo" \
  --region "$REGION"

echo "✅ CodeCommit repository created: $REPO_NAME"
```

---

## Step 3 – Clone and Create Application

```bash
echo ""
echo "Cloning repository and creating application..."

# Create workspace
mkdir -p /tmp/pipeline-lab
cd /tmp/pipeline-lab

# Clone repository
git clone codecommit://"$REGION"://"$REPO_NAME"
cd "$REPO_NAME"

# Create Flask app
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

echo "✅ Application files created"
```

---

## Step 4 – Create BuildSpec and TaskDef Template

```bash
echo ""
echo "Creating buildspec.yml and task definition template..."

# Create buildspec.yml
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

# Create ECS task definition
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

echo "✅ Build and deployment files created"
```

---

## Step 5 – Commit and Push Code

```bash
echo ""
echo "Committing code to CodeCommit..."

git add .
git commit -m "Initial commit: Flask app with CI/CD configuration"
git push origin main

echo "✅ Code pushed to CodeCommit"
```

---

## Step 6 – Create ECR Repository

```bash
echo ""
echo "Creating ECR repository..."

aws ecr create-repository \
  --repository-name "$ECR_REPO" \
  --region "$REGION" \
  --image-scanning-configuration scanOnPush=true

echo "✅ ECR repository created"
```

---

## Step 7 – Create ECS Cluster

```bash
echo ""
echo "Creating ECS Fargate cluster..."

aws ecs create-cluster \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION"

echo "✅ ECS cluster created: $CLUSTER_NAME"
```

---

## Step 8 – Create CloudWatch Log Group

```bash
echo ""
echo "Creating CloudWatch log group..."

aws logs create-log-group \
  --log-group-name "/ecs/flask-task" \
  --region "$REGION"

echo "✅ Log group created"
```

---

## Step 9 – Create ECS Task Execution Role

```bash
echo ""
echo "Creating ECS task execution role..."

# Check if role exists
if aws iam get-role --role-name ecsTaskExecutionRole 2>/dev/null; then
    echo "✅ ecsTaskExecutionRole already exists"
else
    # Create trust policy
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

    # Create role
    aws iam create-role \
      --role-name ecsTaskExecutionRole \
      --assume-role-policy-document file://ecs-trust-policy.json

    # Attach managed policy
    aws iam attach-role-policy \
      --role-name ecsTaskExecutionRole \
      --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

    echo "✅ ECS task execution role created"
    sleep 10
fi
```

---

## Step 10 – Register ECS Task Definition

```bash
echo ""
echo "Registering ECS task definition..."

cd /tmp/pipeline-lab/"$REPO_NAME"

aws ecs register-task-definition \
  --cli-input-json file://taskdef.json \
  --region "$REGION"

echo "✅ Task definition registered"
```

---

## Step 11 – Create Security Group for ECS

```bash
echo ""
echo "Creating security group for ECS tasks..."

# Get default VPC
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --region "$REGION" \
  --query 'Vpcs[0].VpcId' \
  --output text)

echo "VPC_ID=$VPC_ID"

# Create security group
SG_ID=$(aws ec2 create-security-group \
  --group-name flask-ecs-sg \
  --description "Security group for Flask ECS tasks" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

echo "SG_ID=$SG_ID"

# Allow inbound on port 5000
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 5000 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

echo "✅ Security group created: $SG_ID"
```

---

## Step 12 – Create ECS Service

```bash
echo ""
echo "Creating ECS service..."

# Get subnets
SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --region "$REGION" \
  --query 'Subnets[0:2].SubnetId' \
  --output text | tr '\t' ',')

echo "SUBNETS=$SUBNETS"

# Create service
aws ecs create-service \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --task-definition flask-task \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --region "$REGION"

echo "✅ ECS service created: $SERVICE_NAME"
```

---

## Step 13 – Create CodeBuild Project

```bash
echo ""
echo "Creating CodeBuild project..."

# Create IAM role for CodeBuild (if not exists)
if ! aws iam get-role --role-name CodeBuildServiceRole 2>/dev/null; then
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

    aws iam create-role \
      --role-name CodeBuildServiceRole \
      --assume-role-policy-document file://codebuild-trust.json

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

    aws iam put-role-policy \
      --role-name CodeBuildServiceRole \
      --policy-name CodeBuildPolicy \
      --policy-document file://codebuild-policy.json

    sleep 10
fi

# Create CodeBuild project
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

aws codebuild create-project \
  --cli-input-json file://codebuild-config.json \
  --region "$REGION"

echo "✅ CodeBuild project created"
```

---

## Step 14 – Create CodePipeline Service Role

```bash
echo ""
echo "Creating CodePipeline service role..."

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

aws iam create-role \
  --role-name CodePipelineServiceRole \
  --assume-role-policy-document file://pipeline-trust.json

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

aws iam put-role-policy \
  --role-name CodePipelineServiceRole \
  --policy-name CodePipelinePolicy \
  --policy-document file://pipeline-policy.json

echo "✅ CodePipeline role created"
sleep 10
```

---

## Step 15 – Create S3 Bucket for Artifacts

```bash
echo ""
echo "Creating S3 bucket for pipeline artifacts..."

ARTIFACT_BUCKET="pipeline-artifacts-${ACCOUNT_ID}"
echo "ARTIFACT_BUCKET=$ARTIFACT_BUCKET"

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

echo "✅ S3 bucket created"
```

---

## Step 16 – Create CodePipeline

```bash
echo ""
echo "================================================"
echo "CREATING CODEPIPELINE"
echo "================================================"
echo ""

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

aws codepipeline create-pipeline \
  --cli-input-json file://pipeline-config.json \
  --region "$REGION"

echo ""
echo "✅ CodePipeline created: $PIPELINE_NAME"
echo ""
echo "Pipeline stages: Source (CodeCommit) → Build (CodeBuild) → Deploy (ECS)"
```

---

## Step 17 – Monitor Pipeline Execution

```bash
echo ""
echo "Monitoring pipeline execution (first run)..."

sleep 10

# Get pipeline state
aws codepipeline get-pipeline-state \
  --name "$PIPELINE_NAME" \
  --region "$REGION" \
  --query 'stageStates[*].{Stage:stageName,Status:latestExecution.status}' \
  --output table

echo ""
echo "Pipeline is running! Full execution takes 5-7 minutes"
```

---

## Step 18 – Wait for Deployment

```bash
echo ""
echo "Waiting for ECS service to stabilize..."

aws ecs wait services-stable \
  --cluster "$CLUSTER_NAME" \
  --services "$SERVICE_NAME" \
  --region "$REGION"

echo "✅ ECS service is stable"
```

---

## Step 19 – Get Application URL

```bash
echo ""
echo "Getting application endpoint..."

# Get task public IP
TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --region "$REGION" \
  --query 'taskArns[0]' \
  --output text)

ENI_ID=$(aws ecs describe-tasks \
  --cluster "$CLUSTER_NAME" \
  --tasks "$TASK_ARN" \
  --region "$REGION" \
  --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
  --output text)

PUBLIC_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids "$ENI_ID" \
  --region "$REGION" \
  --query 'NetworkInterfaces[0].Association.PublicIp' \
  --output text)

echo ""
echo "Application URL: http://${PUBLIC_IP}:5000"
echo ""
echo "Testing application..."
sleep 10
curl -s "http://${PUBLIC_IP}:5000" | jq .
```

---

## Step 20 – Test Pipeline with Code Change

```bash
echo ""
echo "================================================"
echo "TESTING PIPELINE WITH CODE CHANGE"
echo "================================================"
echo ""

cd /tmp/pipeline-lab/"$REPO_NAME"

# Update version
sed -i "s/VERSION = os.getenv('APP_VERSION', '1.0')/VERSION = os.getenv('APP_VERSION', '2.0')/" app.py

# Update Dockerfile
sed -i 's/ENV APP_VERSION=1.0/ENV APP_VERSION=2.0/' Dockerfile

# Commit and push
git add .
git commit -m "Update to version 2.0"
git push origin main

echo ""
echo "✅ Code change pushed!"
echo "Pipeline will automatically trigger in ~1 minute"
echo ""
echo "Monitor pipeline: https://console.aws.amazon.com/codesuite/codepipeline/pipelines/${PIPELINE_NAME}/view"
```

---

## Step 21 – Cleanup

```bash
echo ""
echo "Cleaning up resources..."

# Delete pipeline
aws codepipeline delete-pipeline \
  --name "$PIPELINE_NAME" \
  --region "$REGION"

# Delete ECS service
aws ecs update-service \
  --cluster "$CLUSTER_NAME" \
  --service "$SERVICE_NAME" \
  --desired-count 0 \
  --region "$REGION"

aws ecs delete-service \
  --cluster "$CLUSTER_NAME" \
  --service "$SERVICE_NAME" \
  --region "$REGION" \
  --force

# Delete cluster
aws ecs delete-cluster \
  --cluster "$CLUSTER_NAME" \
  --region "$REGION"

# Delete CodeBuild project
aws codebuild delete-project \
  --name flask-pipeline-build \
  --region "$REGION"

# Delete ECR repository
aws ecr delete-repository \
  --repository-name "$ECR_REPO" \
  --region "$REGION" \
  --force

# Delete CodeCommit repository
aws codecommit delete-repository \
  --repository-name "$REPO_NAME" \
  --region "$REGION"

# Empty and delete S3 bucket
aws s3 rm s3://"$ARTIFACT_BUCKET" --recursive
aws s3api delete-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION"

# Delete security group
aws ec2 delete-security-group \
  --group-id "$SG_ID" \
  --region "$REGION"

# Delete log group
aws logs delete-log-group \
  --log-group-name "/ecs/flask-task" \
  --region "$REGION"

# Delete IAM roles
aws iam delete-role-policy \
  --role-name CodePipelineServiceRole \
  --policy-name CodePipelinePolicy

aws iam delete-role --role-name CodePipelineServiceRole

aws iam delete-role-policy \
  --role-name CodeBuildServiceRole \
  --policy-name CodeBuildPolicy

aws iam delete-role --role-name CodeBuildServiceRole

echo ""
echo "✅ All resources cleaned up!"
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
