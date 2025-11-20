# Lab 10.F: Lambda CI/CD with SAM and GitHub Actions
<img width="1536" height="1024" alt="IMG" src="https://github.com/user-attachments/assets/5d36742b-d707-4119-a2a1-97003a7fa5b3" />


## Overview
This lab demonstrates building a complete CI/CD pipeline for serverless applications using AWS SAM (Serverless Application Model) and GitHub Actions. You'll create a Lambda function with API Gateway, deploy using SAM templates, and implement automated testing. This showcases production-grade serverless CI/CD workflows.

---

## Objectives
- Create Lambda function with SAM template
- Configure GitHub Actions for serverless deployments
- Build and deploy with SAM CLI in GitHub Actions
- Create API Gateway endpoints automatically
- Implement automated CI/CD on every push
- Understand SAM template structure and deployment

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Git installed (`git --version`)
- GitHub account with repository access
- IAM permissions for Lambda, API Gateway, CloudFormation, S3, IAM
- Region: ap-southeast-2

---

## Architecture

```
GitHub Push → GitHub Actions:
                → SAM Build
                → SAM Deploy (CloudFormation)
                ↓
              Lambda + API Gateway
```

**Pipeline Flow:**
1. GitHub hosts Lambda code and SAM template
2. Push to main branch triggers GitHub Actions workflow
3. GitHub Actions runs SAM build (packages dependencies)
4. SAM deploy creates/updates CloudFormation stack
5. CloudFormation provisions Lambda, API Gateway, IAM roles

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
APP_FOLDER="serverless-sam-app"
FUNCTION_NAME="JokeApiFunction"
STACK_NAME="joke-api-sam-stack"
API_NAME="JokeAPI"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# S3 bucket for SAM artifacts
SAM_BUCKET="sam-deployments-${ACCOUNT_ID}"

echo "REGION=$REGION"
echo "GITHUB_OWNER=$GITHUB_OWNER"
echo "GITHUB_REPO=$GITHUB_REPO"
echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "STACK_NAME=$STACK_NAME"
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

## Step 3 – Create Application Directory

```bash
# Create and navigate to application directory
mkdir -p "$APP_FOLDER"
cd "$APP_FOLDER"
```

---

## Step 4 – Create Lambda Function

```bash
# Create Lambda function directory
mkdir -p joke_api

# Create Lambda function handler
cat > joke_api/app.py <<'EOF'
import json
import random

jokes = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why do Java developers wear glasses? Because they don't C#.",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
    "Why did the developer go broke? Because he used up all his cache.",
    "What's a programmer's favorite hangout place? The Foo Bar.",
    "Why do serverless developers sleep well? Because they have no servers to worry about!",
]

def lambda_handler(event, context):
    """
    Lambda function handler for Joke API
    """
    # Get HTTP method and path
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    
    # Route requests
    if path == '/' and http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'service': 'joke-api',
                'version': '1.0.0',
                'endpoints': {
                    '/': 'API info',
                    '/joke': 'Get random joke',
                    '/health': 'Health check'
                }
            })
        }
    
    elif path == '/joke' and http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'joke': random.choice(jokes)
            })
        }
    
    elif path == '/health' and http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'healthy'
            })
        }
    
    else:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Not Found'
            })
        }
EOF

# Create requirements.txt (empty for this simple function)
touch joke_api/requirements.txt
```

---

## Step 5 – Create SAM Template

```bash
# Create SAM template
cat > template.yaml <<EOF
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Joke API - Serverless REST API with Lambda and API Gateway

Globals:
  Function:
    Timeout: 10
    MemorySize: 128
    Runtime: python3.11

Resources:
  # Lambda Function
  JokeApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: ${FUNCTION_NAME}
      CodeUri: joke_api/
      Handler: app.lambda_handler
      Description: Returns programming jokes via REST API
      Events:
        RootApi:
          Type: Api
          Properties:
            Path: /
            Method: GET
            RestApiId: !Ref JokeApi
        JokeApi:
          Type: Api
          Properties:
            Path: /joke
            Method: GET
            RestApiId: !Ref JokeApi
        HealthApi:
          Type: Api
          Properties:
            Path: /health
            Method: GET
            RestApiId: !Ref JokeApi
      Tags:
        Application: JokeAPI
        Environment: Production

  # API Gateway
  JokeApi:
    Type: AWS::Serverless::Api
    Properties:
      Name: ${API_NAME}
      StageName: prod
      Description: Joke API Gateway
      Cors:
        AllowOrigin: "'*'"
        AllowHeaders: "'Content-Type,X-Amz-Date,Authorization,X-Api-Key'"
        AllowMethods: "'GET,OPTIONS'"

  # CloudWatch Log Group
  JokeApiFunctionLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub '/aws/lambda/\${JokeApiFunction}'
      RetentionInDays: 7

Outputs:
  JokeApiUrl:
    Description: API Gateway endpoint URL
    Value: !Sub 'https://\${JokeApi}.execute-api.\${AWS::Region}.amazonaws.com/prod'
    Export:
      Name: !Sub '\${AWS::StackName}-ApiUrl'
  
  JokeApiFunctionArn:
    Description: Lambda Function ARN
    Value: !GetAtt JokeApiFunction.Arn
    Export:
      Name: !Sub '\${AWS::StackName}-FunctionArn'
  
  JokeApiId:
    Description: API Gateway ID
    Value: !Ref JokeApi
    Export:
      Name: !Sub '\${AWS::StackName}-ApiId'
EOF
```

---

## Step 6 – Create GitHub Actions Workflow

```bash
# Create GitHub Actions directory
mkdir -p .github/workflows

# Create deployment workflow
cat > .github/workflows/deploy-sam.yml <<'EOF'
name: Deploy SAM Application

on:
  push:
    branches:
      - main
    paths:
      - 'serverless-sam-app/**'
      - '.github/workflows/deploy-sam.yml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-southeast-2
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install SAM CLI
        run: |
          pip install aws-sam-cli
          sam --version
      
      - name: Validate SAM template
        run: |
          cd serverless-sam-app
          sam validate --template template.yaml
      
      - name: Build SAM application
        run: |
          cd serverless-sam-app
          sam build --template template.yaml
      
      - name: Deploy SAM application
        run: |
          cd serverless-sam-app
          sam deploy \
            --template-file .aws-sam/build/template.yaml \
            --stack-name joke-api-sam-stack \
            --s3-bucket sam-deployments-${{ secrets.AWS_ACCOUNT_ID }} \
            --s3-prefix joke-api-sam-stack \
            --capabilities CAPABILITY_IAM \
            --region ap-southeast-2 \
            --no-fail-on-empty-changeset \
            --no-confirm-changeset
      
      - name: Get API Gateway URL
        run: |
          API_URL=$(aws cloudformation describe-stacks \
            --stack-name joke-api-sam-stack \
            --region ap-southeast-2 \
            --query 'Stacks[0].Outputs[?OutputKey==`JokeApiUrl`].OutputValue' \
            --output text)
          echo "🚀 API Endpoint: $API_URL"
          echo "📱 Test endpoints:"
          echo "   - $API_URL/"
          echo "   - $API_URL/joke"
          echo "   - $API_URL/health"
EOF

echo "✅ GitHub Actions workflow created"
```

---

## Step 7 – Create Lambda Tests (Optional)

```bash
# Create test events directory
mkdir -p events

# Create test event for root endpoint
cat > events/root-event.json <<'EOF'
{
  "httpMethod": "GET",
  "path": "/",
  "headers": {
    "Content-Type": "application/json"
  }
}
EOF

# Create test event for joke endpoint
cat > events/joke-event.json <<'EOF'
{
  "httpMethod": "GET",
  "path": "/joke",
  "headers": {
    "Content-Type": "application/json"
  }
}
EOF
```

---

## Step 8 – Create AWS Credentials for GitHub Actions

```bash
# Create IAM user for GitHub Actions
aws iam create-user --user-name github-actions-sam-deploy

# Create access policy for SAM deployments
cat > github-actions-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:DescribeChangeSet",
        "cloudformation:CreateChangeSet",
        "cloudformation:DeleteChangeSet",
        "cloudformation:ExecuteChangeSet",
        "cloudformation:GetTemplateSummary"
      ],
      "Resource": "arn:aws:cloudformation:${REGION}:${ACCOUNT_ID}:stack/${STACK_NAME}/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:GetFunction",
        "lambda:DeleteFunction",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:TagResource",
        "lambda:UntagResource",
        "lambda:ListTags"
      ],
      "Resource": "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "apigateway:*"
      ],
      "Resource": "arn:aws:apigateway:${REGION}::/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:PassRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:GetRolePolicy",
        "iam:TagRole"
      ],
      "Resource": "arn:aws:iam::${ACCOUNT_ID}:role/${STACK_NAME}-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::${SAM_BUCKET}",
        "arn:aws:s3:::${SAM_BUCKET}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:DeleteLogGroup",
        "logs:DescribeLogGroups",
        "logs:PutRetentionPolicy"
      ],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/lambda/*"
    },
    {
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    }
  ]
}
EOF

# Attach policy to user
aws iam put-user-policy \
  --user-name github-actions-sam-deploy \
  --policy-name SAMDeployPolicy \
  --policy-document file://github-actions-policy.json

# Create access keys
ACCESS_KEYS=$(aws iam create-access-key \
  --user-name github-actions-sam-deploy \
  --output json)

AWS_ACCESS_KEY_ID=$(echo "$ACCESS_KEYS" | jq -r '.AccessKey.AccessKeyId')
AWS_SECRET_ACCESS_KEY=$(echo "$ACCESS_KEYS" | jq -r '.AccessKey.SecretAccessKey')

echo "✅ IAM user created with access keys"
echo ""
echo "⚠️  SAVE THESE CREDENTIALS - They will not be shown again:"
echo "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID"
echo "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY"
echo "AWS_ACCOUNT_ID=$ACCOUNT_ID"
```

---

## Step 9 – Configure GitHub Secrets

```bash
echo "Configure GitHub repository secrets:"
echo ""
echo "1. Go to: https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/settings/secrets/actions"
echo "2. Click 'New repository secret'"
echo "3. Add these three secrets:"
echo ""
echo "   Name: AWS_ACCESS_KEY_ID"
echo "   Value: $AWS_ACCESS_KEY_ID"
echo ""
echo "   Name: AWS_SECRET_ACCESS_KEY"
echo "   Value: $AWS_SECRET_ACCESS_KEY"
echo ""
echo "   Name: AWS_ACCOUNT_ID"
echo "   Value: $ACCOUNT_ID"
echo ""
echo "Press Enter when secrets are configured..."
read
```

---

## Step 10 – Create S3 Bucket for SAM

```bash
# Create S3 bucket for SAM deployments
if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$SAM_BUCKET" \
      --region "$REGION"
else
    aws s3api create-bucket \
      --bucket "$SAM_BUCKET" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi

echo "SAM_BUCKET=$SAM_BUCKET"
```

---

## Step 11 – Commit and Push to GitHub

```bash
# Navigate to repository root
cd "$REPO_DIR"

# Add all files
git add "$APP_FOLDER/" .github/

# Commit changes
git commit -m "Add serverless SAM application with GitHub Actions CI/CD"

# Push to GitHub (triggers workflow)
git push origin main

echo "✅ Code pushed - GitHub Actions workflow will start automatically"
echo "📊 Monitor workflow: https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions"
```

---

## Step 12 – Monitor GitHub Actions Workflow

```bash
# Open workflow in browser
echo "📊 Monitor deployment:"
echo "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions"
echo ""
echo "Or use GitHub CLI:"
gh run list --limit 5
gh run watch
```

---

## Step 13 – Get API Gateway URL

```bash
# Wait for workflow to complete (2-3 minutes)
echo "Waiting for deployment to complete..."
sleep 120

# Get CloudFormation stack outputs
API_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`JokeApiUrl`].OutputValue' \
  --output text)

echo "API_URL=$API_URL"
```

---

## Step 14 – Test Lambda Function

```bash
# Test all API endpoints
echo "Testing home endpoint:"
curl -s "$API_URL/" | jq .

echo -e "\nTesting joke endpoint:"
curl -s "$API_URL/joke" | jq .

echo -e "\nTesting health endpoint:"
curl -s "$API_URL/health" | jq .

# Open in browser
echo -e "\n📱 Open in browser:"
echo "$API_URL/"
echo "$API_URL/joke"
echo "$API_URL/health"
```

---

## Step 15 – View Lambda Logs

```bash
# Get recent Lambda logs
aws logs tail "/aws/lambda/${FUNCTION_NAME}" \
  --region "$REGION" \
  --follow
```

---

## Step 16 – Make Code Changes and Redeploy

```bash
# Navigate to app directory
cd "$REPO_DIR/$APP_FOLDER/joke_api"

# Add new joke
cat > app.py <<'EOF'
import json
import random

jokes = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why do Java developers wear glasses? Because they don't C#.",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
    "Why did the developer go broke? Because he used up all his cache.",
    "What's a programmer's favorite hangout place? The Foo Bar.",
    "Why do serverless developers sleep well? Because they have no servers to worry about!",
    "What do you call a Lambda function that never returns? A timeout waiting to happen!",
]

def lambda_handler(event, context):
    """
    Lambda function handler for Joke API - Version 2.0
    """
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    
    if path == '/' and http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'service': 'joke-api',
                'version': '2.0.0',
                'endpoints': {
                    '/': 'API info',
                    '/joke': 'Get random joke',
                    '/health': 'Health check'
                }
            })
        }
    
    elif path == '/joke' and http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'joke': random.choice(jokes)
            })
        }
    
    elif path == '/health' and http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'healthy'
            })
        }
    
    else:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Not Found'
            })
        }
EOF

# Commit and push
cd "$REPO_DIR"
git add "$APP_FOLDER/joke_api/app.py"
git commit -m "Add Lambda joke - trigger GitHub Actions"
git push origin main

echo "✅ Code changes pushed - GitHub Actions workflow will trigger automatically"
echo "📊 Monitor: https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions"
```

---

## Step 17 – Cleanup

```bash
# Delete CloudFormation stack (removes Lambda, API Gateway, IAM roles)
aws cloudformation delete-stack \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

# Wait for stack deletion
aws cloudformation wait stack-delete-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

# Delete IAM user and access keys
aws iam list-access-keys \
  --user-name github-actions-sam-deploy \
  --query 'AccessKeyMetadata[*].AccessKeyId' \
  --output text | while read key; do
    aws iam delete-access-key \
      --user-name github-actions-sam-deploy \
      --access-key-id "$key"
done

aws iam delete-user-policy \
  --user-name github-actions-sam-deploy \
  --policy-name SAMDeployPolicy

aws iam delete-user --user-name github-actions-sam-deploy

# Empty and delete S3 bucket
aws s3 rm "s3://$SAM_BUCKET" --recursive
aws s3api delete-bucket \
  --bucket "$SAM_BUCKET" \
  --region "$REGION"

# Remove application and workflow directories
cd "$REPO_DIR"
rm -rf "$APP_FOLDER" .github/workflows/deploy-sam.yml
git add -A
git commit -m "Cleanup: Remove SAM serverless app and GitHub Actions workflow"
git push origin main

# Remove GitHub secrets manually
echo ""
echo "⚠️  Manually remove GitHub secrets:"
echo "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/settings/secrets/actions"
echo "Delete: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_ACCOUNT_ID"

echo ""
echo "✅ Cleanup complete"
```

---

## Summary

In this lab, you:
- Created serverless application with SAM template
- Configured GitHub Actions for Lambda deployments
- Built and deployed with SAM CLI in GitHub Actions
- Created API Gateway endpoints automatically via SAM
- Tested Lambda function through API Gateway
- Implemented automated serverless CI/CD pipeline

**Key Takeaways:**
- **SAM Templates**: Infrastructure as Code for serverless apps
- **CloudFormation**: SAM uses CloudFormation under the hood
- **API Gateway Integration**: Automatic API creation with Events in SAM
- **Zero Infrastructure**: No servers to manage, only code
- **GitHub Actions**: Native CI/CD without CodePipeline/CodeBuild

**CI/CD Workflow:**
```
GitHub Push → GitHub Actions (SAM build/deploy) → CloudFormation → Lambda + API Gateway
```

---

## Best Practices

**SAM Templates:**
- Use Globals section for common function properties
- Define all resources in template.yaml
- Use Outputs for important ARNs and URLs
- Version your API stages (dev, staging, prod)

**Lambda Functions:**
- Keep functions small and focused
- Set appropriate timeout and memory
- Use environment variables for configuration
- Implement proper error handling

**API Gateway:**
- Enable CORS if needed for web clients
- Use stages for different environments
- Implement throttling and caching
- Monitor with CloudWatch metrics

**GitHub Actions:**
- Store AWS credentials as GitHub Secrets (never commit them)
- Use official AWS actions (configure-aws-credentials)
- Use path filters to trigger only on relevant changes
- Use SAM validate before deploying
- Set --no-fail-on-empty-changeset to avoid errors on no changes

---

## Troubleshooting

**SAM build fails:**
- Verify Python version matches runtime
- Check requirements.txt exists (even if empty)
- Ensure template.yaml syntax is valid: `sam validate`

**CloudFormation deployment fails:**
- Check IAM permissions for GitHub Actions user
- Verify S3 bucket exists and is accessible
- Review CloudFormation events for specific error
- Ensure stack name is unique

**API Gateway returns errors:**
- Check Lambda execution role has required permissions
- Review Lambda logs in CloudWatch
- Verify API Gateway integration is configured
- Test Lambda directly with test events

**GitHub Actions workflow fails:**
- Check workflow logs for detailed errors
- Verify GitHub Secrets are configured correctly
- Ensure AWS credentials have required permissions
- Check SAM CLI installation step succeeded
- Verify S3 bucket name matches AWS_ACCOUNT_ID secret

---

## Additional Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [SAM CLI Reference](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-command-reference.html)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [API Gateway Integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/getting-started.html)
- [SAM Policy Templates](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-templates.html)
