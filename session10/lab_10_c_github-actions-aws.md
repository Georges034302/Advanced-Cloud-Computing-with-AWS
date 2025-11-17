# Lab 10.C: GitHub Actions + AWS - Serverless CI/CD
<img width="1536" height="1024" alt="IMG" src="https://github.com/user-attachments/assets/0923f59f-51b9-40b7-bc7f-82c31b4a5879" />

## Overview
This lab demonstrates CI/CD using GitHub Actions to deploy serverless applications to AWS. You'll create a GitHub repository, configure GitHub Actions workflows to automatically deploy a Lambda function and static website to S3 on every git push, using OpenID Connect (OIDC) for secure authentication.

---

## Objectives
- Create GitHub repository with AWS deployment workflows
- Configure GitHub OIDC provider in AWS IAM
- Create GitHub Actions workflow for Lambda deployment
- Create GitHub Actions workflow for S3 static site deployment
- Automate deployments on git push
- Use GitHub Secrets for AWS credentials
- Test automated deployments

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- GitHub account (free)
- Git installed (`git --version`)
- IAM permissions for Lambda, S3, IAM, CloudFormation
- Region: ap-southeast-2

---

## Architecture

```
GitHub Repository
      ↓
  git push (trigger)
      ↓
GitHub Actions Workflow
      ↓
AWS OIDC Authentication
      ↓
Deploy Lambda Function / S3 Website
```

---

## Step 1 – Set Variables

```bash
# Set deployment region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Set resource names for GitHub Actions deployment
GITHUB_REPO_NAME="aws-serverless-cicd"  # You'll create this on GitHub
LAMBDA_FUNCTION="github-actions-lambda"

# Get AWS account ID and create unique S3 bucket name
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
S3_BUCKET_NAME="github-actions-site-${ACCOUNT_ID}"

echo "REGION=$REGION"
echo "LAMBDA_FUNCTION=$LAMBDA_FUNCTION"
echo "S3_BUCKET_NAME=$S3_BUCKET_NAME"
echo "ACCOUNT_ID=$ACCOUNT_ID"
```

---

## Step 2 – Create GitHub OIDC Provider in AWS

```bash
# Create OIDC provider for GitHub Actions authentication (enables secure access without AWS keys)
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1"
```

---

## Step 3 – Create IAM Role for GitHub Actions

```bash
# Prompt for GitHub username to scope IAM role trust policy
read -p "Enter your GitHub username:" GITHUB_USERNAME
echo "GITHUB_USERNAME=$GITHUB_USERNAME"

# Create trust policy allowing GitHub Actions from specific repository to assume role
cat > github-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_USERNAME}/${GITHUB_REPO_NAME}:*"
        }
      }
    }
  ]
}
EOF

# Create IAM role for GitHub Actions
aws iam create-role \
  --role-name GitHubActionsRole \
  --assume-role-policy-document file://github-trust-policy.json

# Create permissions policy for Lambda, S3, IAM, and CloudWatch Logs
cat > github-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:GetFunction",
        "lambda:AddPermission",
        "lambda:RemovePermission"
      ],
      "Resource": "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::${S3_BUCKET_NAME}",
        "arn:aws:s3:::${S3_BUCKET_NAME}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:PassRole",
        "iam:GetRole"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Attach permissions policy to GitHub Actions role
aws iam put-role-policy \
  --role-name GitHubActionsRole \
  --policy-name GitHubActionsPermissions \
  --policy-document file://github-permissions.json

# Get role ARN for GitHub Secrets configuration
ROLE_ARN=$(aws iam get-role \
  --role-name GitHubActionsRole \
  --query 'Role.Arn' \
  --output text)

echo "Role ARN: $ROLE_ARN"
echo "⚠️  Save this ARN - you'll need it for GitHub Secrets"
```

---

## Step 4 – Create Lambda Execution Role

```bash
# Check if Lambda execution role already exists
if ! aws iam get-role --role-name GitHubActionsLambdaRole 2>/dev/null; then
    # Create trust policy allowing Lambda service to assume role
    cat > lambda-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create IAM role for Lambda function execution
    aws iam create-role \
      --role-name GitHubActionsLambdaRole \
      --assume-role-policy-document file://lambda-trust-policy.json

    # Attach AWS managed policy for basic Lambda execution (CloudWatch Logs)
    aws iam attach-role-policy \
      --role-name GitHubActionsLambdaRole \
      --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

    # Wait for IAM role to propagate globally
    sleep 10
else
    echo "Lambda execution role already exists"
fi

# Get Lambda role ARN for use in GitHub Actions workflow
LAMBDA_ROLE_ARN=$(aws iam get-role \
  --role-name GitHubActionsLambdaRole \
  --query 'Role.Arn' \
  --output text)

echo "LAMBDA_ROLE_ARN=$LAMBDA_ROLE_ARN"
```

---

## Step 5 – Create S3 Bucket for Static Website

```bash
# Create S3 bucket with region-specific configuration
if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$S3_BUCKET_NAME" \
      --region "$REGION"
else
    aws s3api create-bucket \
      --bucket "$S3_BUCKET_NAME" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi

# Configure bucket for static website hosting with index and error pages
aws s3 website s3://"$S3_BUCKET_NAME"/ \
  --index-document index.html \
  --error-document error.html

# Disable public access block to allow bucket policy for public reads
aws s3api put-public-access-block \
  --bucket "$S3_BUCKET_NAME" \
  --public-access-block-configuration \
    "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

# Create bucket policy allowing public read access to all objects
cat > bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::${S3_BUCKET_NAME}/*"
    }
  ]
}
EOF

# Apply bucket policy to enable public access
aws s3api put-bucket-policy \
  --bucket "$S3_BUCKET_NAME" \
  --policy file://bucket-policy.json

echo "Website URL: http://${S3_BUCKET_NAME}.s3-website-${REGION}.amazonaws.com"
```

---

## Step 6 – Create Local Project Directory

```bash
# Get repository root and create workspace for GitHub Actions lab
REPO_DIR=$(git rev-parse --show-toplevel)
WORKSPACE="$REPO_DIR/github-actions-lab"
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

echo "Project directory: $(pwd)"
```

---

## Step 7 – Create Lambda Function Code

```bash
# Create Lambda function directory and handler code
mkdir -p lambda
cat > lambda/handler.py <<'EOF'
import json

def lambda_handler(event, context):
    """
    Simple Lambda function deployed via GitHub Actions
    """
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'message': 'Hello from Lambda deployed via GitHub Actions!',
            'version': '1.0',
            'deployed_by': 'GitHub Actions',
            'event': event
        })
    }
EOF
```

---

## Step 8 – Create Static Website Files

```bash
# Create website directory and HTML files
mkdir -p website

# Create index.html with responsive design
cat > website/index.html <<'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub Actions + AWS</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 10px;
            max-width: 600px;
            margin: 0 auto;
        }
        h1 { font-size: 2.5em; margin-bottom: 20px; }
        p { font-size: 1.2em; margin: 15px 0; }
        .badge { 
            background: rgba(255,255,255,0.2);
            padding: 10px 20px;
            border-radius: 20px;
            display: inline-block;
            margin: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 GitHub Actions + AWS</h1>
        <p>This static website was automatically deployed to S3 using GitHub Actions!</p>
        <div>
            <span class="badge">GitHub Actions</span>
            <span class="badge">AWS S3</span>
            <span class="badge">CI/CD</span>
        </div>
        <p style="margin-top: 30px;">
            <strong>Deployment:</strong> Automated on every git push
        </p>
        <p>
            <strong>Version:</strong> 1.0
        </p>
    </div>
</body>
</html>
EOF

# Create error.html
cat > website/error.html <<'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Error</title>
</head>
<body>
    <h1>404 - Page Not Found</h1>
    <p>The requested page could not be found.</p>
</body>
</html>
EOF
```

---

## Step 9 – Create GitHub Actions Workflow for Lambda

```bash
# Create GitHub Actions workflows directory
mkdir -p .github/workflows

# Create workflow for automated Lambda deployment on code changes
name: Deploy Lambda Function

on:
  push:
    branches:
      - main
    paths:
      - 'lambda/**'

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: \${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${REGION}

      - name: Package Lambda function
        run: |
          cd lambda
          zip -r ../function.zip .
          cd ..

      - name: Deploy to Lambda
        run: |
          # Check if function exists
          if aws lambda get-function --function-name ${LAMBDA_FUNCTION} 2>/dev/null; then
            echo "Updating existing Lambda function..."
            aws lambda update-function-code \
              --function-name ${LAMBDA_FUNCTION} \
              --zip-file fileb://function.zip
          else
            echo "Creating new Lambda function..."
            aws lambda create-function \
              --function-name ${LAMBDA_FUNCTION} \
              --runtime python3.11 \
              --role ${LAMBDA_ROLE_ARN} \
              --handler handler.lambda_handler \
              --zip-file fileb://function.zip \
              --timeout 30 \
              --memory-size 128
          fi

      - name: Create Function URL
        run: |
          # Create function URL if it doesn't exist
          aws lambda create-function-url-config \
            --function-name ${LAMBDA_FUNCTION} \
            --auth-type NONE \
            --cors 'AllowOrigins=*,AllowMethods=GET,POST' 2>/dev/null || true
          
          # Add public invoke permission
          aws lambda add-permission \
            --function-name ${LAMBDA_FUNCTION} \
            --statement-id FunctionURLAllowPublicAccess \
            --action lambda:InvokeFunctionUrl \
            --principal '*' \
            --function-url-auth-type NONE 2>/dev/null || true

      - name: Get Function URL
        run: |
          FUNCTION_URL=\$(aws lambda get-function-url-config \
            --function-name ${LAMBDA_FUNCTION} \
            --query 'FunctionUrl' \
            --output text)
          echo "Lambda Function URL: \$FUNCTION_URL"
EOF
```

---

## Step 10 – Create GitHub Actions Workflow for S3

```bash
# Create workflow for automated S3 website deployment on content changes
cat > .github/workflows/deploy-s3.yml <<EOF
name: Deploy Static Website to S3

on:
  push:
    branches:
      - main
    paths:
      - 'website/**'

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: \${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${REGION}

      - name: Sync website to S3
        run: |
          aws s3 sync website/ s3://${S3_BUCKET_NAME}/ \
            --delete \
            --cache-control "max-age=3600"

      - name: Get Website URL
        run: |
          echo "Website URL: http://${S3_BUCKET_NAME}.s3-website-${REGION}.amazonaws.com"
EOF
```

---

## Step 11 – Create README with Setup Instructions

```bash
# Create README with deployment instructions and architecture overview
cat > README.md <<EOF
# AWS Serverless CI/CD with GitHub Actions

This repository demonstrates automated deployment to AWS using GitHub Actions.

## Architecture

- **Lambda Function**: Deployed automatically when \`lambda/\` changes
- **Static Website**: Deployed to S3 when \`website/\` changes
- **Authentication**: GitHub OIDC (no AWS keys stored)

## Setup Instructions

### 1. Configure GitHub Secrets

Go to repository Settings → Secrets and variables → Actions, and add:

- **AWS_ROLE_ARN**: \`${ROLE_ARN}\`

### 2. Push to GitHub

The workflows will automatically trigger on push to main branch.

### 3. Access Deployed Resources

- **Lambda Function**: Check workflow output for Function URL
- **Static Website**: http://${S3_BUCKET_NAME}.s3-website-${REGION}.amazonaws.com

## Workflows

- \`.github/workflows/deploy-lambda.yml\` - Deploys Lambda function
- \`.github/workflows/deploy-s3.yml\` - Deploys static website

## Local Testing

\`\`\`bash
# Test Lambda function locally
python lambda/handler.py

# View website locally
cd website && python -m http.server 8000
\`\`\`
EOF
```

---

## Step 12 – Initialize Git Repository

```bash
# Navigate to workspace directory
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR/github-actions-lab"

# Initialize Git repository and commit all files
git init
git add .
git commit -m "Initial commit: GitHub Actions CI/CD setup"
```

---

## Step 13 – Verify Lambda Deployment

```bash
# Check if Lambda function has been deployed by GitHub Actions
if aws lambda get-function --function-name "$LAMBDA_FUNCTION" --region "$REGION" 2>/dev/null; then
    echo "Lambda function deployed"
    
    # Get function URL if configured
    FUNCTION_URL=$(aws lambda get-function-url-config \
      --function-name "$LAMBDA_FUNCTION" \
      --region "$REGION" \
      --query 'FunctionUrl' \
      --output text 2>/dev/null || echo "Not configured yet")
    
    if [ "$FUNCTION_URL" != "Not configured yet" ]; then
        echo "Lambda Function URL: $FUNCTION_URL"
        echo "Testing Lambda function..."
        curl -s "$FUNCTION_URL" | jq .
    else
        echo "Function URL will be created by GitHub Actions workflow"
    fi
else
    echo "⚠️  Lambda function not deployed yet"
    echo "It will be created when you push to GitHub"
fi
```

---

## Step 14 – Verify S3 Website Deployment

```bash
# Check if website files have been uploaded by GitHub Actions
OBJECT_COUNT=$(aws s3 ls s3://"$S3_BUCKET_NAME"/ --region "$REGION" 2>/dev/null | wc -l)

if [ "$OBJECT_COUNT" -gt 0 ]; then
    echo "Website files deployed to S3"
    echo "Website URL: http://${S3_BUCKET_NAME}.s3-website-${REGION}.amazonaws.com"
    echo "Testing website..."
    curl -s "http://${S3_BUCKET_NAME}.s3-website-${REGION}.amazonaws.com" | head -20
else
    echo "⚠️  Website not deployed yet"
    echo "Files will be uploaded when you push to GitHub"
fi
```

---

## Step 15 – Test CI/CD with Code Change

```bash
# Navigate to workspace directory
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR/github-actions-lab"

# Update Lambda function to version 2.0 with timestamp tracking
cat > lambda/handler.py <<'EOF'
import json
from datetime import datetime

def lambda_handler(event, context):
    """
    Updated Lambda function - Version 2.0
    """
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'message': 'Hello from Lambda - Version 2.0!',
            'version': '2.0',
            'deployed_by': 'GitHub Actions',
            'timestamp': datetime.utcnow().isoformat(),
            'updates': 'Added timestamp and version tracking'
        })
    }
EOF

# Update website version and content
sed -i 's/Version: 1.0/Version: 2.0/' website/index.html
sed -i 's/This static website/This UPDATED static website/' website/index.html

echo "Now commit and push changes:"
echo ""
echo "cd \$REPO_DIR/github-actions-lab"
echo "git add ."
echo "git commit -m 'Update to version 2.0'"
echo "git push origin main"
echo ""
echo "GitHub Actions will automatically deploy the changes!"
```

---

## Step 16 – Cleanup

```bash
# Delete Lambda function
aws lambda delete-function \
  --function-name "$LAMBDA_FUNCTION" \
  --region "$REGION" 2>/dev/null || true

# Empty and delete S3 bucket
aws s3 rm s3://"$S3_BUCKET_NAME" --recursive --region "$REGION" 2>/dev/null || true
aws s3api delete-bucket \
  --bucket "$S3_BUCKET_NAME" \
  --region "$REGION" 2>/dev/null || true

# Delete GitHub Actions IAM role and policy
aws iam delete-role-policy \
  --role-name GitHubActionsRole \
  --policy-name GitHubActionsPermissions 2>/dev/null || true

aws iam delete-role \
  --role-name GitHubActionsRole 2>/dev/null || true

# Delete Lambda execution role and policy
aws iam detach-role-policy \
  --role-name GitHubActionsLambdaRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true

aws iam delete-role \
  --role-name GitHubActionsLambdaRole 2>/dev/null || true

# Delete OIDC provider
OIDC_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
aws iam delete-open-id-connect-provider \
  --open-id-connect-provider-arn "$OIDC_ARN" 2>/dev/null || true

# Remove local workspace directory
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR"
rm -rf github-actions-lab

echo "✅ Cleanup complete"
echo "⚠️  Remember to delete the GitHub repository manually if desired"
```

---

## Summary

In this lab, you have:
- Created GitHub OIDC provider in AWS for secure authentication
- Configured IAM roles with permissions for GitHub Actions
- Created Lambda function with automated deployment workflow
- Created static website with automated S3 deployment workflow
- Set up GitHub Actions workflows for CI/CD
- Tested automated deployments on code changes
- Used GitHub Secrets for secure credential management

**Key Takeaways:**
- **GitHub Actions**: Free CI/CD platform integrated with GitHub
- **OIDC Authentication**: Secure, no AWS keys stored in GitHub
- **Workflow Triggers**: Automatic on push to specific paths
- **Multi-Environment**: Separate workflows for different services
- **Zero Infrastructure**: Serverless deployment (Lambda + S3)

**CI/CD Flow:**
```
git push → GitHub Actions → AWS OIDC Auth → Deploy Lambda/S3 → Live Application
```

---

## Best Practices

**Security:**
- Use OIDC instead of long-lived AWS keys
- Restrict IAM role to specific GitHub repository
- Use least-privilege permissions
- Never commit secrets to repository

**Workflows:**
- Separate workflows for different services
- Use path filters to trigger only relevant workflows
- Add manual approval for production deployments
- Run tests before deployment

**GitHub Actions:**
- Use official actions (actions/checkout, aws-actions/*)
- Pin action versions for stability
- Cache dependencies to speed up builds
- Use matrix builds for multiple environments

**Deployment:**
- Use tags for versioning
- Implement rollback strategies
- Monitor deployments with notifications
- Test in staging before production

---

## Production Enhancements

1. **Add Testing Stage**
   ```yaml
   - name: Run tests
     run: |
       pytest lambda/tests/
   ```

2. **Manual Approval**
   ```yaml
   - name: Manual approval
     uses: trstringer/manual-approval@v1
     with:
       approvers: username
   ```

3. **Notifications**
   ```yaml
   - name: Notify deployment
     uses: 8398a7/action-slack@v3
     with:
       status: ${{ job.status }}
   ```

4. **Environment Variables**
   ```yaml
   - name: Deploy with environment
     env:
       ENV: production
       DEBUG: false
   ```

---

## Troubleshooting

**OIDC authentication fails:**
- Verify OIDC provider thumbprint is correct
- Check IAM role trust policy includes correct repo
- Ensure GitHub Actions has id-token: write permission

**Workflow doesn't trigger:**
- Check path filters match changed files
- Verify branch name is correct (main vs master)
- Check workflow syntax with GitHub's validator

**Deployment fails:**
- Check IAM role has necessary permissions
- Verify AWS resources exist (S3 bucket, Lambda role)
- Review workflow logs in GitHub Actions tab

**Lambda function not accessible:**
- Check function URL is created
- Verify public invoke permission is added
- Check CORS configuration

---

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [AWS Actions for GitHub](https://github.com/aws-actions)
- [OIDC with GitHub Actions](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [Workflow Syntax Reference](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
