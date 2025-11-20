# Lab 10.G: Lambda CI/CD with SAM - Serverless Pipeline


## Overview
This lab demonstrates building a complete CI/CD pipeline for serverless applications using AWS SAM (Serverless Application Model), CodePipeline, and CodeBuild. You'll create a Lambda function with API Gateway, deploy using SAM templates, and implement automated testing. This showcases production-grade serverless CI/CD workflows.

---

## Objectives
- Create Lambda function with SAM template
- Configure CodePipeline for serverless deployments
- Build and deploy with SAM CLI in CodeBuild
- Create API Gateway endpoints automatically
- Implement Lambda versioning and aliases
- Understand SAM template structure and deployment

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Git installed (`git --version`)
- GitHub account with repository access
- IAM permissions for CodePipeline, CodeBuild, Lambda, API Gateway, CloudFormation, S3, IAM
- Region: ap-southeast-2

---

## Architecture

```
GitHub → CodePipeline → CodeBuild:
                          → SAM Build
                          → SAM Deploy (CloudFormation)
                          ↓
                        Lambda + API Gateway
```

**Pipeline Flow:**
1. GitHub hosts Lambda code and SAM template
2. CodePipeline detects changes and triggers CodeBuild
3. CodeBuild runs SAM build (packages dependencies)
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

# Pipeline configuration
PIPELINE_NAME="lambda-sam-pipeline"
CODEBUILD_PROJECT="lambda-sam-deploy"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# S3 bucket for SAM artifacts and pipeline
SAM_BUCKET="sam-deployments-${ACCOUNT_ID}"
ARTIFACT_BUCKET="codepipeline-artifacts-lambda-${ACCOUNT_ID}"

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

## Step 6 – Create BuildSpec for SAM Deployment

```bash
# Create buildspec for CodeBuild
cat > buildspec.yml <<EOF
version: 0.2

phases:
  install:
    runtime-versions:
      python: 3.11
    commands:
      # Install SAM CLI
      - pip install aws-sam-cli

  pre_build:
    commands:
      # Validate SAM template
      - sam validate --template template.yaml

  build:
    commands:
      # Build SAM application
      - sam build --template template.yaml --use-container

  post_build:
    commands:
      # Deploy SAM application
      - |
        sam deploy \
          --template-file .aws-sam/build/template.yaml \
          --stack-name ${STACK_NAME} \
          --s3-bucket ${SAM_BUCKET} \
          --s3-prefix ${STACK_NAME} \
          --capabilities CAPABILITY_IAM \
          --region ${REGION} \
          --no-fail-on-empty-changeset \
          --no-confirm-changeset
      
      # Get API endpoint
      - |
        API_URL=\$(aws cloudformation describe-stacks \
          --stack-name ${STACK_NAME} \
          --region ${REGION} \
          --query 'Stacks[0].Outputs[?OutputKey==\`JokeApiUrl\`].OutputValue' \
          --output text)
        echo "API Endpoint: \$API_URL"

artifacts:
  files:
    - template.yaml
    - .aws-sam/**/*
  discard-paths: no
EOF
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

## Step 8 – Commit and Push to GitHub

```bash
# Add all files
cd "$REPO_DIR"
git add "$APP_FOLDER/"

# Commit changes
git commit -m "Add serverless SAM application with Lambda and API Gateway"

# Push to GitHub
git push origin main
```

---

## Step 9 – Create S3 Buckets

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

# Create S3 bucket for CodePipeline artifacts
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

echo "SAM_BUCKET=$SAM_BUCKET"
echo "ARTIFACT_BUCKET=$ARTIFACT_BUCKET"
```

---

## Step 10 – Create IAM Role for CodeBuild

```bash
# Create trust policy for CodeBuild
cat > codebuild-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codebuild.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role
aws iam create-role \
  --role-name CodeBuildLambdaSAMRole \
  --assume-role-policy-document file://codebuild-trust-policy.json

# Create permissions policy
cat > codebuild-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${SAM_BUCKET}",
        "arn:aws:s3:::${SAM_BUCKET}/*",
        "arn:aws:s3:::${ARTIFACT_BUCKET}",
        "arn:aws:s3:::${ARTIFACT_BUCKET}/*"
      ]
    },
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
        "lambda:UntagResource"
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
        "iam:GetRolePolicy"
      ],
      "Resource": "arn:aws:iam::${ACCOUNT_ID}:role/${STACK_NAME}-*"
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

# Attach permissions policy
aws iam put-role-policy \
  --role-name CodeBuildLambdaSAMRole \
  --policy-name CodeBuildLambdaSAMPermissions \
  --policy-document file://codebuild-permissions.json

# Wait for IAM propagation
sleep 10
```

---

## Step 11 – Create CodeBuild Project

```bash
# Create CodeBuild project configuration
cat > codebuild-project.json <<EOF
{
  "name": "${CODEBUILD_PROJECT}",
  "description": "Build and deploy Lambda function with SAM",
  "source": {
    "type": "CODEPIPELINE",
    "buildspec": "${APP_FOLDER}/buildspec.yml"
  },
  "artifacts": {
    "type": "CODEPIPELINE"
  },
  "environment": {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/standard:7.0",
    "computeType": "BUILD_GENERAL1_SMALL",
    "privilegedMode": true,
    "environmentVariables": [
      {"name": "AWS_DEFAULT_REGION", "value": "${REGION}"},
      {"name": "STACK_NAME", "value": "${STACK_NAME}"},
      {"name": "SAM_BUCKET", "value": "${SAM_BUCKET}"}
    ]
  },
  "serviceRole": "arn:aws:iam::${ACCOUNT_ID}:role/CodeBuildLambdaSAMRole"
}
EOF

# Create CodeBuild project
aws codebuild create-project \
  --cli-input-json file://codebuild-project.json \
  --region "$REGION"
```

---

## Step 12 – Create IAM Role for CodePipeline

```bash
# Create trust policy for CodePipeline
cat > codepipeline-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codepipeline.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role
aws iam create-role \
  --role-name CodePipelineLambdaRole \
  --assume-role-policy-document file://codepipeline-trust-policy.json

# Create permissions policy
cat > codepipeline-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:GetBucketLocation",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${ARTIFACT_BUCKET}",
        "arn:aws:s3:::${ARTIFACT_BUCKET}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "codebuild:BatchGetBuilds",
        "codebuild:StartBuild"
      ],
      "Resource": "arn:aws:codebuild:${REGION}:${ACCOUNT_ID}:project/${CODEBUILD_PROJECT}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "codestar-connections:UseConnection"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Attach permissions policy
aws iam put-role-policy \
  --role-name CodePipelineLambdaRole \
  --policy-name CodePipelineLambdaPermissions \
  --policy-document file://codepipeline-permissions.json

# Wait for IAM propagation
sleep 10
```

---

## Step 13 – Create GitHub Connection

```bash
# List existing CodeStar connections
CONNECTION_ARN=$(aws codestar-connections list-connections \
  --provider-type-filter GitHub \
  --region "$REGION" \
  --query 'Connections[0].ConnectionArn' \
  --output text)

echo "CONNECTION_ARN=$CONNECTION_ARN"
```

**If no connection exists:**
1. Go to AWS Console → Developer Tools → Connections
2. Click **Create connection**
3. Select **GitHub** and name it `github-connection`
4. Click **Connect to GitHub** and authorize AWS
5. Run the command above again to get the ARN

---

## Step 14 – Create CodePipeline

```bash
# Create CodePipeline configuration
cat > pipeline.json <<EOF
{
  "pipeline": {
    "name": "${PIPELINE_NAME}",
    "roleArn": "arn:aws:iam::${ACCOUNT_ID}:role/CodePipelineLambdaRole",
    "artifactStore": {
      "type": "S3",
      "location": "${ARTIFACT_BUCKET}"
    },
    "stages": [
      {
        "name": "Source",
        "actions": [
          {
            "name": "SourceAction",
            "actionTypeId": {
              "category": "Source",
              "owner": "AWS",
              "provider": "CodeStarSourceConnection",
              "version": "1"
            },
            "configuration": {
              "ConnectionArn": "${CONNECTION_ARN}",
              "FullRepositoryId": "${GITHUB_OWNER}/${GITHUB_REPO}",
              "BranchName": "main",
              "OutputArtifactFormat": "CODE_ZIP"
            },
            "outputArtifacts": [
              {
                "name": "SourceOutput"
              }
            ]
          }
        ]
      },
      {
        "name": "Build",
        "actions": [
          {
            "name": "BuildAction",
            "actionTypeId": {
              "category": "Build",
              "owner": "AWS",
              "provider": "CodeBuild",
              "version": "1"
            },
            "configuration": {
              "ProjectName": "${CODEBUILD_PROJECT}"
            },
            "inputArtifacts": [
              {
                "name": "SourceOutput"
              }
            ],
            "outputArtifacts": [
              {
                "name": "BuildOutput"
              }
            ]
          }
        ]
      }
    ]
  }
}
EOF

# Create CodePipeline
aws codepipeline create-pipeline \
  --cli-input-json file://pipeline.json \
  --region "$REGION"

echo "Pipeline created: ${PIPELINE_NAME}"
```

---

## Step 15 – Monitor Pipeline Execution

```bash
# Get pipeline execution status
aws codepipeline get-pipeline-state \
  --name "$PIPELINE_NAME" \
  --region "$REGION" \
  --query 'stageStates[*].{Stage:stageName,Status:latestExecution.status}' \
  --output table

# Wait for pipeline to complete
echo "Monitor pipeline: https://console.aws.amazon.com/codesuite/codepipeline/pipelines/${PIPELINE_NAME}/view"
```

---

## Step 16 – Get API Gateway URL

```bash
# Get CloudFormation stack outputs
API_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`JokeApiUrl`].OutputValue' \
  --output text)

echo "API_URL=$API_URL"
```

---

## Step 17 – Test Lambda Function

```bash
# Test all API endpoints
echo "Testing home endpoint:"
curl -s "$API_URL/" | jq .

echo -e "\nTesting joke endpoint:"
curl -s "$API_URL/joke" | jq .

echo -e "\nTesting health endpoint:"
curl -s "$API_URL/health" | jq .

# Display URLs for browser testing
echo -e "\n📱 Test in browser:"
echo "$API_URL/"
echo "$API_URL/joke"
echo "$API_URL/health"
```

---

## Step 18 – View Lambda Logs

```bash
# Get recent Lambda logs
aws logs tail "/aws/lambda/${FUNCTION_NAME}" \
  --region "$REGION" \
  --follow
```

---

## Step 19 – Make Code Changes and Redeploy

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
git commit -m "Add Lambda joke - trigger pipeline"
git push origin main

echo "✅ Code changes pushed - pipeline will auto-trigger and update Lambda"
```

---

## Step 20 – Cleanup

```bash
# Delete CloudFormation stack (removes Lambda, API Gateway, IAM roles)
aws cloudformation delete-stack \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

# Wait for stack deletion
aws cloudformation wait stack-delete-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

# Delete CodePipeline
aws codepipeline delete-pipeline \
  --name "$PIPELINE_NAME" \
  --region "$REGION"

# Delete CodeBuild project
aws codebuild delete-project \
  --name "$CODEBUILD_PROJECT" \
  --region "$REGION"

# Delete IAM roles
aws iam delete-role-policy \
  --role-name CodePipelineLambdaRole \
  --policy-name CodePipelineLambdaPermissions

aws iam delete-role --role-name CodePipelineLambdaRole

aws iam delete-role-policy \
  --role-name CodeBuildLambdaSAMRole \
  --policy-name CodeBuildLambdaSAMPermissions

aws iam delete-role --role-name CodeBuildLambdaSAMRole

# Empty and delete S3 buckets
aws s3 rm "s3://$SAM_BUCKET" --recursive
aws s3api delete-bucket \
  --bucket "$SAM_BUCKET" \
  --region "$REGION"

aws s3 rm "s3://$ARTIFACT_BUCKET" --recursive
aws s3api delete-bucket \
  --bucket "$ARTIFACT_BUCKET" \
  --region "$REGION"

# Remove application directory
cd "$REPO_DIR"
rm -rf "$APP_FOLDER"
git rm -r "$APP_FOLDER"
git commit -m "Cleanup: Remove SAM serverless app"
git push origin main

echo "✅ Cleanup complete"
```

---

## Summary

In this lab, you:
- Created serverless application with SAM template
- Configured CodePipeline for Lambda deployments
- Built and deployed with SAM CLI in CodeBuild
- Created API Gateway endpoints automatically via SAM
- Tested Lambda function through API Gateway
- Implemented automated serverless CI/CD pipeline

**Key Takeaways:**
- **SAM Templates**: Infrastructure as Code for serverless apps
- **CloudFormation**: SAM uses CloudFormation under the hood
- **API Gateway Integration**: Automatic API creation with Events in SAM
- **Zero Infrastructure**: No servers to manage, only code
- **Pipeline Automation**: CodePipeline triggers on every commit

**CI/CD Workflow:**
```
GitHub → CodePipeline → CodeBuild (SAM deploy) → CloudFormation → Lambda + API Gateway
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

**CodeBuild:**
- Use SAM build --use-container for consistency
- Validate templates before deployment
- Use --no-fail-on-empty-changeset to avoid errors
- Store artifacts in S3 for rollback capability

---

## Troubleshooting

**SAM build fails:**
- Verify Python version matches runtime
- Check requirements.txt exists (even if empty)
- Ensure template.yaml syntax is valid: `sam validate`

**CloudFormation deployment fails:**
- Check IAM permissions for CodeBuild role
- Verify S3 bucket exists and is accessible
- Review CloudFormation events for specific error
- Ensure stack name is unique

**API Gateway returns errors:**
- Check Lambda execution role has required permissions
- Review Lambda logs in CloudWatch
- Verify API Gateway integration is configured
- Test Lambda directly with test events

**Pipeline stuck or fails:**
- Check CodeBuild logs for detailed errors
- Verify GitHub connection is active
- Ensure all IAM roles have correct permissions
- Review pipeline execution history

---

## Additional Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [SAM CLI Reference](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-command-reference.html)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [API Gateway Integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/getting-started.html)
- [SAM Policy Templates](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-templates.html)
