# Lab 10.B: CodePipeline - Multi-Stage CI/CD Pipeline
<img width="1536" height="849" alt="IMG" src="https://github.com/user-attachments/assets/c1f01b86-8164-4ffa-8b63-cdd8ea69ef4e" />

## Overview
This lab builds a complete CI/CD pipeline using AWS CodePipeline to orchestrate source, build, and deploy stages. You'll automatically deploy a Flask Docker application from GitHub → CodeBuild (build Docker image) → ECS Fargate (deploy container) with automated deployment on every git push.

---

## Objectives
- Connect GitHub repository to CodePipeline
- Create multi-stage CodePipeline (Source → Build → Deploy)
- Configure automatic triggers on GitHub commits
- Build Docker images with CodeBuild
- Deploy containers to Amazon ECS Fargate
- Monitor pipeline execution
- Test end-to-end automation

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- GitHub account with repository (Georges034302/Advanced-Cloud-Computing-with-AWS)
- IAM permissions for CodePipeline, CodeBuild, ECS, ECR, S3
- Region: ap-southeast-2

---

## Step 1 – Set Variables

```bash
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Dynamically get GitHub repository info from git remote
GITHUB_URL=$(git remote get-url origin)
GITHUB_OWNER=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/]([^/]+)/.*|\1|')
GITHUB_REPO=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/][^/]+/([^.]+)(\.git)?$|\1|')
GITHUB_BRANCH="main"

APP_FOLDER="pipeline-flask-app"
ECR_REPO="pipeline-flask-app"
CLUSTER_NAME="pipeline-demo-cluster"
SERVICE_NAME="flask-service"
PIPELINE_NAME="flask-cicd-pipeline"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ARTIFACT_BUCKET="pipeline-artifacts-${ACCOUNT_ID}"

echo "REGION=$REGION"
echo "GITHUB_OWNER=$GITHUB_OWNER"
echo "GITHUB_REPO=$GITHUB_REPO"
echo "APP_FOLDER=$APP_FOLDER"
echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "ARTIFACT_BUCKET=$ARTIFACT_BUCKET"
```

---

## Step 2 – Verify GitHub Repository

```bash
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR"

git checkout main
git pull origin main

echo "Repository: $(pwd)"
```

---

## Step 3 – Create S3 Bucket for Pipeline Artifacts

```bash
if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION"
else
    aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi

echo "Created bucket: $ARTIFACT_BUCKET"
```

---

## Step 4 – Create Application Directory and Files

```bash
WORKSPACE="$REPO_DIR/$APP_FOLDER"
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

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

## Step 5 – Create BuildSpec and TaskDef Template

```bash
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

## Step 6 – Commit and Push to GitHub

```bash
git add "$APP_FOLDER/"
git commit -m "Add Flask app for CodePipeline demo"
git push origin main
```

---

## Step 7 – Create ECR Repository

```bash
aws ecr create-repository \
  --repository-name "$ECR_REPO" \
  --region "$REGION" \
  --image-scanning-configuration scanOnPush=true
```

---

## Step 8 – Create ECS Cluster

```bash
aws ecs create-cluster --cluster-name "$CLUSTER_NAME" --region "$REGION"
```

---

## Step 9 – Create CloudWatch Log Group

```bash
aws logs create-log-group --log-group-name "/ecs/flask-task" --region "$REGION"
```

---

## Step 10 – Create ECS Task Execution Role

```bash
if aws iam get-role --role-name ecsTaskExecutionRole 2>/dev/null; then
    echo "ecsTaskExecutionRole already exists"
else
    cat > ecs-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
      --role-name ecsTaskExecutionRole \
      --assume-role-policy-document file://ecs-trust-policy.json

    aws iam attach-role-policy \
      --role-name ecsTaskExecutionRole \
      --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

    sleep 10
fi
```

---

## Step 11 – Register ECS Task Definition

```bash
cd "$REPO_DIR/$APP_FOLDER"

aws ecs register-task-definition \
  --cli-input-json file://taskdef.json \
  --region "$REGION"
```

---

## Step 12 – Create Security Group for ECS

```bash
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --region "$REGION" \
  --query 'Vpcs[0].VpcId' \
  --output text)

echo "VPC_ID=$VPC_ID"

SG_ID=$(aws ec2 create-security-group \
  --group-name flask-ecs-sg \
  --description "Security group for Flask ECS tasks" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

echo "SG_ID=$SG_ID"

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 5000 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"
```

---

## Step 13 – Create ECS Service

```bash
SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --region "$REGION" \
  --query 'Subnets[0:2].SubnetId' \
  --output text | tr '\t' ',')

echo "SUBNETS=$SUBNETS"

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

## Step 14 – Create CodeBuild Project

```bash
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
      "Action": ["logs:*", "ecr:*", "s3:*"],
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

cat > codebuild-config.json <<EOF
{
  "name": "flask-pipeline-build",
  "source": {
    "type": "CODEPIPELINE",
    "buildspec": "$APP_FOLDER/buildspec.yml"
  },
  "artifacts": {"type": "CODEPIPELINE"},
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
```

---

## Step 15 – Create CodePipeline Service Role

```bash
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
  "Statement": [{
    "Effect": "Allow",
    "Action": ["codebuild:*", "ecs:*", "iam:PassRole", "s3:*", "codestar-connections:UseConnection"],
    "Resource": "*"
  }]
}
EOF

aws iam put-role-policy \
  --role-name CodePipelineServiceRole \
  --policy-name CodePipelinePolicy \
  --policy-document file://pipeline-policy.json

sleep 10
```

---

## Step 16 – Connect GitHub to AWS (One-Time Setup)

**Manual Step (AWS Console):**
1. Go to AWS Console → CodePipeline → Settings → Connections
2. Click "Create connection" → Select "GitHub"
3. Name it "github-connection" and authorize AWS
4. Copy the Connection ARN

```bash
read -p "Enter GitHub Connection ARN: " GITHUB_CONNECTION_ARN
echo "GITHUB_CONNECTION_ARN=$GITHUB_CONNECTION_ARN"
```

---

## Step 17 – Create CodePipeline with GitHub Source with GitHub Source

```bash
# Create CodePipeline configuration with GitHub Source, Build, and Deploy stages
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
            "provider": "CodeStarSourceConnection",
            "version": "1"
          },
          "outputArtifacts": [{"name": "SourceOutput"}],
          "configuration": {
            "ConnectionArn": "${GITHUB_CONNECTION_ARN}",
            "FullRepositoryId": "${GITHUB_OWNER}/${GITHUB_REPO}",
            "BranchName": "${GITHUB_BRANCH}",
            "OutputArtifactFormat": "CODE_ZIP",
            "DetectChanges": "true"
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

echo "Pipeline stages: Source (GitHub) → Build (CodeBuild) → Deploy (ECS)"
echo "Pipeline will automatically trigger on GitHub push"
```

---

## Step 18 – Monitor Pipeline Execution

```bash
sleep 10

aws codepipeline get-pipeline-state \
  --name "$PIPELINE_NAME" \
  --region "$REGION" \
  --query 'stageStates[*].{Stage:stageName,Status:latestExecution.status}' \
  --output table

echo "Pipeline is running! (5-7 minutes)"
```

---

## Step 19 – Wait for Deployment

```bash
aws ecs wait services-stable \
  --cluster "$CLUSTER_NAME" \
  --services "$SERVICE_NAME" \
  --region "$REGION"
```

---

## Step 20 – Get Application URL

```bash
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

echo "Application URL: http://${PUBLIC_IP}:5000"

sleep 10
curl -s "http://${PUBLIC_IP}:5000" | jq .
```

---

## Step 21 – Test Pipeline with Code Change

```bash
cd "$REPO_DIR/$APP_FOLDER"

sed -i "s/VERSION = os.getenv('APP_VERSION', '1.0')/VERSION = os.getenv('APP_VERSION', '2.0')/" app.py
sed -i 's/ENV APP_VERSION=1.0/ENV APP_VERSION=2.0/' Dockerfile

git add .
git commit -m "Update to version 2.0"
git push origin main

echo "Pipeline will automatically trigger on GitHub push"
```

---

## Step 22 – Cleanup

```bash
aws codepipeline delete-pipeline --name "$PIPELINE_NAME" --region "$REGION"

aws ecs update-service --cluster "$CLUSTER_NAME" --service "$SERVICE_NAME" --desired-count 0 --region "$REGION"
aws ecs delete-service --cluster "$CLUSTER_NAME" --service "$SERVICE_NAME" --region "$REGION" --force
aws ecs delete-cluster --cluster "$CLUSTER_NAME" --region "$REGION"

for REV in $(aws ecs list-task-definitions --family-prefix flask-task --region "$REGION" --query 'taskDefinitionArns[]' --output text); do
    aws ecs deregister-task-definition --task-definition "$REV" --region "$REGION"
done

aws codebuild delete-project --name flask-pipeline-build --region "$REGION"
aws ecr delete-repository --repository-name "$ECR_REPO" --region "$REGION" --force

aws s3 rm s3://"$ARTIFACT_BUCKET" --recursive
aws s3api delete-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION"

aws ec2 delete-security-group --group-id "$SG_ID" --region "$REGION"
aws logs delete-log-group --log-group-name "/ecs/flask-task" --region "$REGION"

aws iam delete-role-policy --role-name CodePipelineServiceRole --policy-name CodePipelinePolicy
aws iam delete-role --role-name CodePipelineServiceRole

aws iam delete-role-policy --role-name CodeBuildServiceRole --policy-name CodeBuildPolicy
aws iam delete-role --role-name CodeBuildServiceRole

cd "$REPO_DIR"
rm -rf "$APP_FOLDER"

git rm -r "$APP_FOLDER"
git commit -m "Cleanup: Remove pipeline Flask app"
git push origin main

echo "✅ Cleanup complete"
```

---

## Summary

**What You Built:**
- Multi-stage CodePipeline with GitHub integration
- Automated container build and deployment workflow
- ECS Fargate service running Dockerized Flask application

**Architecture:**
```
GitHub → CodePipeline → CodeBuild (Docker) → ECR → ECS Fargate
```

**Key Components:**
- **CodeStar Connection**: Secure GitHub integration (OAuth)
- **CodePipeline**: Three-stage orchestration (Source → Build → Deploy)
- **CodeBuild**: Docker image builder with privileged mode
- **ECR**: Private container registry
- **ECS Fargate**: Serverless container execution
- **S3**: Artifact storage between stages

**What You Learned:**
- Configure GitHub source integration with CodeStar
- Build multi-stage CI/CD pipelines
- Automate Docker image builds and deployments
- Deploy containers to ECS with zero infrastructure management
- Monitor and test automated pipelines

---

## Best Practices

**Pipeline Security:**
- Use CodeStar Connections for GitHub (secure OAuth flow)
- Apply least-privilege IAM policies to service roles
- Encrypt artifacts in S3 with KMS
- Enable ECR image vulnerability scanning
- Restrict pipeline execution to protected branches

**Production Deployment:**
- Add manual approval stage before production
- Use separate pipelines per environment (dev/staging/prod)
- Implement ECS blue/green deployments for zero downtime
- Configure automatic rollback on health check failures
- Monitor application metrics post-deployment

**Cost Optimization:**
- Clean up old ECR images with lifecycle policies
- Set S3 artifact retention policies (30-90 days)
- Use Fargate Spot for non-production workloads
- Right-size task CPU/memory based on actual usage

---

## Production Enhancements

**1. Multi-Environment Pipeline**
```json
{
  "name": "Approval",
  "actions": [{
    "name": "ManualApproval",
    "actionTypeId": {"category": "Approval", "owner": "AWS", "provider": "Manual", "version": "1"}
  }]
}
```

**2. Automated Testing**
```yaml
# Add to buildspec.yml
phases:
  post_build:
    commands:
      - pytest tests/
      - docker run $IMAGE_URI pytest
```

**3. ECR Image Scanning**
```bash
aws ecr put-image-scanning-configuration \
  --repository-name $ECR_REPO \
  --image-scanning-configuration scanOnPush=true
```

**4. Pipeline Notifications**
```bash
aws codestar-notifications create-notification-rule \
  --name pipeline-notifications \
  --resource "arn:aws:codepipeline:$REGION:$ACCOUNT_ID:$PIPELINE_NAME" \
  --targets targetType=SNS,targetAddress="arn:aws:sns:$REGION:$ACCOUNT_ID:pipeline-alerts"
```

---

## Troubleshooting

**GitHub connection fails:**
- Verify CodeStar Connection status is "Available"
- Check GitHub App permissions and repository access
- Ensure AWS Connector app is installed in GitHub

**Pipeline fails at Source stage:**
- Verify connection ARN and repository names are correct
- Check branch name matches exactly
- Ensure DetectChanges is set to true

**CodeBuild fails:**
- Review CloudWatch Logs: `/aws/codebuild/flask-pipeline-build`
- Verify buildspec.yml is in correct directory
- Ensure IAM role has ECR permissions
- Check privilegedMode is enabled for Docker builds

**ECS deployment fails:**
- Verify security group allows port 5000
- Check subnets have internet gateway for Fargate
- Ensure assignPublicIp is ENABLED
- Review ECS service events in console

**Application not accessible:**
- Verify task is RUNNING in ECS
- Check security group ingress rules
- Ensure public IP is assigned
- Test connectivity: `curl http://<public-ip>:5000`

---

## Additional Resources

- [AWS CodePipeline Documentation](https://docs.aws.amazon.com/codepipeline/)
- [GitHub Connections for CodePipeline](https://docs.aws.amazon.com/codepipeline/latest/userguide/connections-github.html)
- [AWS CodeBuild Documentation](https://docs.aws.amazon.com/codebuild/)
- [Amazon ECS on Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
- [Docker Multi-Stage Builds](https://docs.docker.com/develop/develop-images/multistage-build/)
