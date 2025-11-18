# Lab 10.C: GitHub Actions → ECR → App Runner
<img width="1536" height="1024" alt="IMG" src="https://github.com/user-attachments/assets/0923f59f-51b9-40b7-bc7f-82c31b4a5879" />

## Overview
This lab demonstrates third-party CI/CD using GitHub Actions to build Docker images and deploy to AWS App Runner. GitHub Actions builds and pushes containers to ECR, then App Runner automatically deploys the updated images using OpenID Connect (OIDC) for secure authentication without AWS access keys.

---

## Objectives
- Configure GitHub OIDC provider for secure AWS access
- Create GitHub Actions workflow for Docker builds
- Build and push container images to ECR
- Deploy containers to App Runner automatically
- Test automated deployments on code changes
- Monitor workflow executions

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- GitHub account and repository access
- Git installed and configured
- IAM permissions for ECR, App Runner, IAM
- Region: ap-southeast-2

---

## Step 1 – Set Variables

```bash
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

GITHUB_URL=$(git remote get-url origin)
GITHUB_OWNER=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/]([^/]+)/.*|\1|')
GITHUB_REPO=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/][^/]+/([^/\.]+).*|\1|')

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

APP_FOLDER="github-actions-apprunner"
ECR_REPO="github-actions-app"
APP_RUNNER_SERVICE="github-actions-service"

echo "REGION=$REGION"
echo "GITHUB_OWNER=$GITHUB_OWNER"
echo "GITHUB_REPO=$GITHUB_REPO"
echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "ECR_REPO=$ECR_REPO"
```

---

## Step 2 – Create GitHub OIDC Provider

```bash
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" 2>/dev/null || echo "OIDC provider already exists"
```

---

## Step 3 – Create IAM Role for GitHub Actions

```bash
cat > github-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {"token.actions.githubusercontent.com:aud": "sts.amazonaws.com"},
      "StringLike": {"token.actions.githubusercontent.com:sub": "repo:${GITHUB_OWNER}/${GITHUB_REPO}:*"}
    }
  }]
}
EOF

aws iam create-role \
  --role-name GitHubActionsAppRunnerRole \
  --assume-role-policy-document file://github-trust-policy.json

cat > github-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
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
        "apprunner:CreateService",
        "apprunner:UpdateService",
        "apprunner:DescribeService",
        "apprunner:StartDeployment"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["iam:PassRole"],
      "Resource": "*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name GitHubActionsAppRunnerRole \
  --policy-name GitHubActionsPermissions \
  --policy-document file://github-permissions.json

ROLE_ARN=$(aws iam get-role \
  --role-name GitHubActionsAppRunnerRole \
  --query 'Role.Arn' \
  --output text)

echo "$ROLE_ARN"
echo "⚠️  Save this ARN for GitHub Secrets (AWS_ROLE_ARN)"
```

---

## Step 4 – Create App Runner Instance Role

```bash
cat > apprunner-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "tasks.apprunner.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name AppRunnerInstanceRole \
  --assume-role-policy-document file://apprunner-trust-policy.json

APPRUNNER_ROLE_ARN=$(aws iam get-role \
  --role-name AppRunnerInstanceRole \
  --query 'Role.Arn' \
  --output text)

echo "$APPRUNNER_ROLE_ARN"
```

---

## Step 5 – Create ECR Repository

```bash
aws ecr create-repository \
  --repository-name "$ECR_REPO" \
  --region "$REGION" \
  --image-scanning-configuration scanOnPush=true 2>/dev/null || echo "ECR repository already exists"

ECR_URI=$(aws ecr describe-repositories \
  --repository-names "$ECR_REPO" \
  --region "$REGION" \
  --query 'repositories[0].repositoryUri' \
  --output text)

echo "$ECR_URI"
```

---

## Step 6 – Create Application Directory

```bash
REPO_DIR=$(git rev-parse --show-toplevel)
mkdir -p "$REPO_DIR/$APP_FOLDER"
cd "$REPO_DIR/$APP_FOLDER"

echo "$(pwd)"
```

---

## Step 7 – Create Flask Application

```bash
cat > app.py <<'EOF'
from flask import Flask, jsonify
import os
import socket

app = Flask(__name__)
VERSION = os.getenv('APP_VERSION', '1.0')

@app.route('/')
def home():
    return jsonify({
        'message': 'Hello from App Runner!',
        'version': VERSION,
        'deployed_by': 'GitHub Actions',
        'hostname': socket.gethostname(),
        'platform': 'AWS App Runner'
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
EOF

cat > requirements.txt <<'EOF'
Flask==3.0.0
Werkzeug==3.0.1
EOF
```

---

## Step 8 – Create Dockerfile

```bash
cat > Dockerfile <<'EOF'
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV APP_VERSION=1.0

EXPOSE 8000

CMD ["python", "app.py"]
EOF
```

---

## Step 9 – Create GitHub Actions Workflow

```bash
mkdir -p .github/workflows

cat > .github/workflows/deploy.yml <<EOF
name: Deploy to App Runner

on:
  push:
    branches: [main]
    paths:
      - '${APP_FOLDER}/**'

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: \${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${REGION}

      - name: Login to ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push Docker image
        env:
          ECR_REGISTRY: \${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: ${ECR_REPO}
          IMAGE_TAG: \${{ github.sha }}
        run: |
          cd ${APP_FOLDER}
          docker build -t \$ECR_REGISTRY/\$ECR_REPOSITORY:\$IMAGE_TAG .
          docker push \$ECR_REGISTRY/\$ECR_REPOSITORY:\$IMAGE_TAG
          docker tag \$ECR_REGISTRY/\$ECR_REPOSITORY:\$IMAGE_TAG \$ECR_REGISTRY/\$ECR_REPOSITORY:latest
          docker push \$ECR_REGISTRY/\$ECR_REPOSITORY:latest
          echo "IMAGE=\$ECR_REGISTRY/\$ECR_REPOSITORY:\$IMAGE_TAG" >> \$GITHUB_OUTPUT

      - name: Deploy to App Runner
        run: |
          if aws apprunner describe-service --service-arn arn:aws:apprunner:${REGION}:${ACCOUNT_ID}:service/${APP_RUNNER_SERVICE} 2>/dev/null; then
            echo "Triggering App Runner deployment..."
            aws apprunner start-deployment --service-arn arn:aws:apprunner:${REGION}:${ACCOUNT_ID}:service/${APP_RUNNER_SERVICE}
          else
            echo "App Runner service not found - create it manually first"
          fi
EOF
```

---

## Step 10 – Create App Runner Access Role

```bash
cat > apprunner-access-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "build.apprunner.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name AppRunnerECRAccessRole \
  --assume-role-policy-document file://apprunner-access-policy.json

aws iam attach-role-policy \
  --role-name AppRunnerECRAccessRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

APPRUNNER_ACCESS_ROLE_ARN=$(aws iam get-role \
  --role-name AppRunnerECRAccessRole \
  --query 'Role.Arn' \
  --output text)

echo "$APPRUNNER_ACCESS_ROLE_ARN"
```

---

## Step 11 – Commit Application to GitHub

```bash
git add .
git commit -m "Add GitHub Actions App Runner deployment"
git push origin main

echo "⚠️  Before pushing, configure GitHub Secret:"
echo "   Repository Settings → Secrets → Actions → New secret"
echo "   Name: AWS_ROLE_ARN"
echo "   Value: $ROLE_ARN"
```

---

## Step 12 – Create App Runner Service

```bash
sleep 15

aws apprunner create-service \
  --service-name "$APP_RUNNER_SERVICE" \
  --source-configuration "{
    \"ImageRepository\": {
      \"ImageIdentifier\": \"${ECR_URI}:latest\",
      \"ImageConfiguration\": {\"Port\": \"8000\"},
      \"ImageRepositoryType\": \"ECR\"
    },
    \"AutoDeploymentsEnabled\": false,
    \"AuthenticationConfiguration\": {
      \"AccessRoleArn\": \"${APPRUNNER_ACCESS_ROLE_ARN}\"
    }
  }" \
  --instance-configuration "Cpu=1 vCPU,Memory=2 GB" \
  --region "$REGION"

echo "App Runner service is being created..."
```

---

## Step 13 – Wait for Service Running

```bash
aws apprunner wait service-running \
  --service-arn "arn:aws:apprunner:${REGION}:${ACCOUNT_ID}:service/${APP_RUNNER_SERVICE}" \
  --region "$REGION"

SERVICE_URL=$(aws apprunner describe-service \
  --service-arn "arn:aws:apprunner:${REGION}:${ACCOUNT_ID}:service/${APP_RUNNER_SERVICE}" \
  --region "$REGION" \
  --query 'Service.ServiceUrl' \
  --output text)

echo "https://$SERVICE_URL"
```

---

## Step 14 – Test Application

```bash
curl -s "https://$SERVICE_URL" | jq .

curl -s "https://$SERVICE_URL/health" | jq .
```

---

## Step 15 – Test GitHub Actions CI/CD

```bash
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR/$APP_FOLDER"

sed -i "s/VERSION = os.getenv('APP_VERSION', '1.0')/VERSION = os.getenv('APP_VERSION', '2.0')/" app.py
sed -i 's/ENV APP_VERSION=1.0/ENV APP_VERSION=2.0/' Dockerfile

git add .
git commit -m "Update to version 2.0"
git push origin main

echo "GitHub Actions workflow will build and push to ECR"
echo "Then manually trigger App Runner deployment or enable auto-deploy"
```

---

## Step 16 – Cleanup

```bash
aws apprunner delete-service \
  --service-arn "arn:aws:apprunner:${REGION}:${ACCOUNT_ID}:service/${APP_RUNNER_SERVICE}" \
  --region "$REGION"

aws ecr delete-repository \
  --repository-name "$ECR_REPO" \
  --region "$REGION" \
  --force

aws iam delete-role-policy --role-name GitHubActionsAppRunnerRole --policy-name GitHubActionsPermissions
aws iam delete-role --role-name GitHubActionsAppRunnerRole

aws iam detach-role-policy --role-name AppRunnerECRAccessRole --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
aws iam delete-role --role-name AppRunnerECRAccessRole

aws iam delete-role --role-name AppRunnerInstanceRole

OIDC_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
aws iam delete-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_ARN" 2>/dev/null || true

REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR"
rm -rf "$APP_FOLDER"

git rm -r "$APP_FOLDER"
git commit -m "Cleanup: Remove GitHub Actions app"
git push origin main

echo "✅ Cleanup complete"
```

---

## Summary

**What You Built:**
- Third-party CI/CD pipeline using GitHub Actions
- Automated Docker image builds and ECR pushes
- Container deployment to AWS App Runner

**Architecture:**
```
GitHub Push → GitHub Actions → Docker Build → ECR Push → App Runner Deploy
```

**Key Components:**
- **GitHub Actions**: Third-party CI/CD platform (alternative to CodePipeline)
- **OIDC Authentication**: Secure AWS access without storing keys
- **ECR**: Private container registry
- **App Runner**: Managed container platform with auto-scaling
- **Docker**: Containerized Flask application

**What You Learned:**
- Configure GitHub OIDC for AWS authentication
- Build CI/CD workflows with GitHub Actions
- Automate Docker builds and ECR pushes
- Deploy containers to App Runner from ECR
- Use GitHub Secrets for secure configuration

---

## Best Practices

**GitHub Actions Security:**
- Use OIDC instead of long-lived AWS access keys
- Scope IAM roles to specific repositories
- Apply least-privilege permissions
- Use GitHub Secrets for sensitive values
- Never commit credentials to repository

**Workflow Design:**
- Use path filters to trigger relevant workflows
- Pin action versions for stability (@v4, not @latest)
- Use official GitHub and AWS actions
- Add status checks before deployments
- Cache Docker layers for faster builds

**Container Best Practices:**
- Use multi-stage Docker builds for smaller images
- Enable ECR image scanning for vulnerabilities
- Tag images with git SHA for traceability
- Keep base images updated
- Use .dockerignore to exclude unnecessary files

**Production Deployment:**
- Add manual approval for production
- Test in staging environment first
- Implement health checks in containers
- Monitor App Runner metrics
- Set up notifications for deployment failures

---

## Production Enhancements

**1. Enable Auto-Deploy in App Runner**
```bash
aws apprunner update-service \
  --service-arn "arn:aws:apprunner:$REGION:$ACCOUNT_ID:service/$APP_RUNNER_SERVICE" \
  --source-configuration "AutoDeploymentsEnabled=true"
```

**2. Add Testing to Workflow**
```yaml
- name: Run tests
  run: |
    cd ${APP_FOLDER}
    pip install -r requirements.txt pytest
    pytest tests/
```

**3. Multi-Environment Deployment**
```yaml
strategy:
  matrix:
    environment: [staging, production]
env:
  ENV: ${{ matrix.environment }}
```

**4. Docker Layer Caching**
```yaml
- name: Cache Docker layers
  uses: actions/cache@v3
  with:
    path: /tmp/.buildx-cache
    key: ${{ runner.os }}-buildx-${{ github.sha }}
```

---

## Troubleshooting

**OIDC authentication fails:**
- Verify OIDC provider thumbprint is correct
- Check IAM role trust policy includes repository path
- Ensure workflow has `id-token: write` permission

**Docker build fails:**
- Check Dockerfile syntax
- Verify base image is accessible
- Review build logs in GitHub Actions
- Ensure all dependencies are in requirements.txt

**ECR push fails:**
- Verify ECR repository exists
- Check IAM permissions for ECR actions
- Ensure ECR login step completed successfully
- Confirm region is correct

**App Runner service not deploying:**
- Check service exists before triggering deployment
- Verify App Runner access role has ECR permissions
- Ensure image exists in ECR with correct tag
- Review App Runner service logs

**Workflow doesn't trigger:**
- Check path filter matches changed files
- Verify branch name is correct (main)
- Review workflow YAML syntax
- Check repository secrets are configured

---

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [AWS Actions for GitHub](https://github.com/aws-actions)
- [GitHub OIDC with AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [AWS App Runner Documentation](https://docs.aws.amazon.com/apprunner/)
- [Amazon ECR User Guide](https://docs.aws.amazon.com/ecr/)
