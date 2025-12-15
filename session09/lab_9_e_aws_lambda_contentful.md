# Lab 9.E: AWS Lambda + Contentful (API-Only CMS Integration)

## Objective
Build a secure **Pattern 2** integration where AWS owns the API boundary and Contentful is used strictly as an **API-only CMS**.

You will deploy:
- AWS Lambda (Python)
- API Gateway (HTTP API)
- AWS Secrets Manager for Contentful tokens
- Contentful GraphQL (READ)
- Contentful REST Delivery (READ)
- Contentful REST Management (WRITE)

All AWS resources are deployed using **AWS SAM**.

---

## Architecture

```
Client  
→ API Gateway (HTTP API)  
→ Lambda (Python)  
→ Secrets Manager (IAM-secured)  
→ Contentful APIs
```

---

## Prerequisites
- AWS CLI configured
- AWS SAM CLI installed (`pip install aws-sam-cli`)
- Python 3.11+
- Contentful account (free tier)
- IAM permissions for Lambda, API Gateway, Secrets Manager, CloudFormation

---

## Step 1: Contentful Setup (UI Only)

**Create Contentful Account and Space:**

1. Go to https://www.contentful.com/sign-up/
2. Create a free account
3. Create a new Space (name: `lambda-demo`)
4. Use environment: `master`

**Create Content Type:**

5. Navigate to **Content model** > **Add content type**
6. Create content type named `blogPost` with the following fields:
   - **title** (Short text, required)
   - **slug** (Short text, required)
   - **body** (Long text / Rich text)
7. Save the content type

**Generate API Tokens:**

8. Go to **Settings** > **API keys** > **Add API key**
9. Generate and save the following tokens:
   - **Content Delivery API token** (read-only access)
   - **Content Management API token** (admin access)
10. Copy your **Space ID** from Settings > General settings

---

## Step 2: Set Up Project Variables

```bash
# Define AWS region
REGION="ap-southeast-2"

# Define project naming convention
PROJECT_NAME="lab-9e-contentful"
STACK_NAME="$PROJECT_NAME"

# Define secret paths in AWS Secrets Manager
SECRET_DELIVERY_NAME="contentful/delivery-token"
SECRET_MANAGEMENT_NAME="contentful/management-token"

# Display configuration
echo "=" | head -c 50 && echo
echo "Project Configuration"
echo "=" | head -c 50 && echo
echo "Region: $REGION"
echo "Stack Name: $STACK_NAME"
echo "Delivery Secret: $SECRET_DELIVERY_NAME"
echo "Management Secret: $SECRET_MANAGEMENT_NAME"
echo "=" | head -c 50 && echo
```

---

## Step 3: Store Contentful Secrets in AWS Secrets Manager

```bash
# Prompt for Contentful Space ID (not a secret, used as CloudFormation parameter)
read -p "Enter Contentful Space ID: " CONTENTFUL_SPACE_ID

# Prompt for Delivery API token and immediately store in AWS Secrets Manager
read -s -p "Enter Content Delivery API token: " CONTENTFUL_DELIVERY_TOKEN
echo

# Store or update Delivery token (idempotent - safe to rerun)
aws secretsmanager create-secret \
  --region "$REGION" \
  --name "$SECRET_DELIVERY_NAME" \
  --secret-string "$CONTENTFUL_DELIVERY_TOKEN" \
  --description "Contentful Delivery API token (read-only)" \
  --tags Key=Project,Value="$PROJECT_NAME" Key=Environment,Value=Lab \
  2>/dev/null || \
aws secretsmanager put-secret-value \
  --region "$REGION" \
  --secret-id "$SECRET_DELIVERY_NAME" \
  --secret-string "$CONTENTFUL_DELIVERY_TOKEN"

echo "✅ Delivery token stored in Secrets Manager"

# Clear the token from bash history immediately
unset CONTENTFUL_DELIVERY_TOKEN

# Prompt for Management API token and immediately store in AWS Secrets Manager
read -s -p "Enter Content Management API token: " CONTENTFUL_MANAGEMENT_TOKEN
echo

# Store or update Management token (idempotent - safe to rerun)
aws secretsmanager create-secret \
  --region "$REGION" \
  --name "$SECRET_MANAGEMENT_NAME" \
  --secret-string "$CONTENTFUL_MANAGEMENT_TOKEN" \
  --description "Contentful Management API token (admin)" \
  --tags Key=Project,Value="$PROJECT_NAME" Key=Environment,Value=Lab \
  2>/dev/null || \
aws secretsmanager put-secret-value \
  --region "$REGION" \
  --secret-id "$SECRET_MANAGEMENT_NAME" \
  --secret-string "$CONTENTFUL_MANAGEMENT_TOKEN"

echo "✅ Management token stored in Secrets Manager"

# Clear the token from bash history immediately
unset CONTENTFUL_MANAGEMENT_TOKEN

echo ""
echo "Verifying secrets in Secrets Manager:"
aws secretsmanager list-secrets \
  --region "$REGION" \
  --query "SecretList[?contains(Name, 'contentful')].{Name:Name,Description:Description}" \
  --output table
```

> **Security Best Practice:** Secrets are never stored in environment variables or bash history. They're collected via `read -s` (silent input) and immediately stored in AWS Secrets Manager, then unset. Secrets Manager encrypts them at rest using AWS KMS.

---

## Step 4: Create Project Structure

```bash
# Create project directory structure
mkdir -p lab_9_e_contentful/src
cd lab_9_e_contentful

echo "✅ Project structure created: $(pwd)"
```

---

## Step 5: Create AWS SAM Template

```bash
# Create SAM template with Infrastructure as Code
# This template defines all AWS resources: Lambda, API Gateway, IAM policies
cat > template.yaml <<'EOF'
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Lab 9-E Contentful Integration - API-Only CMS Pattern

Parameters:
  ContentfulSpaceId:
    Type: String
    Description: Contentful Space ID
    NoEcho: false

Globals:
  Function:
    Runtime: python3.11
    Timeout: 15
    MemorySize: 256
    Environment:
      Variables:
        # AWS region is set automatically by Lambda
        AWS_REGION: !Ref AWS::Region

Resources:

  # HTTP API Gateway - Entry point for all client requests
  ContentfulApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      CorsConfiguration:
        AllowOrigins: ['*']  # WARNING: Restrict in production
        AllowMethods: ['GET', 'POST']
        AllowHeaders: ['Content-Type', 'Authorization']
      Description: API Gateway for Contentful Lambda integration

  # Lambda Function - Handles requests and interacts with Contentful
  ContentfulFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: lambda_function.lambda_handler
      Description: Lambda function for Contentful CMS integration
      Environment:
        Variables:
          # Contentful configuration - NO SECRETS HERE
          CONTENTFUL_SPACE_ID: !Ref ContentfulSpaceId
          CONTENTFUL_ENV: master
          CONTENTFUL_LOCALE: en-US
          # Secret names only (not values)
          SECRET_DELIVERY_NAME: contentful/delivery-token
          SECRET_MANAGEMENT_NAME: contentful/management-token
      Policies:
        # Grant Lambda permission to read secrets from Secrets Manager
        - AWSSecretsManagerGetSecretValuePolicy:
            SecretArn: !Sub 'arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:contentful/*'
        # CloudWatch Logs permission (implicit via AWS::Serverless::Function)
      Events:
        # Route: GET /posts - Fetch posts using GraphQL
        GetPostsGraphQL:
          Type: HttpApi
          Properties:
            ApiId: !Ref ContentfulApi
            Path: /posts
            Method: GET
        # Route: GET /posts-rest - Fetch posts using REST API
        GetPostsRest:
          Type: HttpApi
          Properties:
            ApiId: !Ref ContentfulApi
            Path: /posts-rest
            Method: GET
        # Route: POST /posts - Create new post
        CreatePost:
          Type: HttpApi
          Properties:
            ApiId: !Ref ContentfulApi
            Path: /posts
            Method: POST

Outputs:
  ApiEndpoint:
    Description: "HTTP API endpoint URL"
    Value: !GetAtt ContentfulApi.ApiEndpoint
    Export:
      Name: !Sub "${AWS::StackName}-ApiEndpoint"
  FunctionName:
    Description: "Lambda Function Name"
    Value: !Ref ContentfulFunction
    Export:
      Name: !Sub "${AWS::StackName}-FunctionName"
  FunctionArn:
    Description: "Lambda Function ARN"
    Value: !GetAtt ContentfulFunction.Arn
    Export:
      Name: !Sub "${AWS::StackName}-FunctionArn"
EOF

echo "✅ SAM template created: template.yaml"
```

---

## Step 6: Validate SAM Template

```bash
# Validate SAM template for syntax errors and CloudFormation compatibility
echo "Validating SAM template..."
sam validate

if [ $? -eq 0 ]; then
    echo "✅ Template validation passed"
else
    echo "❌ Template validation failed - check syntax and retry"
    exit 1
fi
```

---

## Step 7: Create Lambda Function Code

```bash
cat > src/lambda_function.py <<'EOF'
import json
import os
import boto3
import requests

# Environment variables
AWS_REGION = os.environ["AWS_REGION"]
SPACE_ID = os.environ["CONTENTFUL_SPACE_ID"]
ENV_ID = os.environ["CONTENTFUL_ENV"]
LOCALE = os.environ["CONTENTFUL_LOCALE"]

DELIVERY_SECRET = os.environ["SECRET_DELIVERY_NAME"]
MANAGEMENT_SECRET = os.environ["SECRET_MANAGEMENT_NAME"]

# Contentful API endpoints
DELIVERY_REST = f"https://cdn.contentful.com/spaces/{SPACE_ID}/environments/{ENV_ID}"
MANAGEMENT_REST = f"https://api.contentful.com/spaces/{SPACE_ID}/environments/{ENV_ID}"
GRAPHQL_ENDPOINT = f"https://graphql.contentful.com/content/v1/spaces/{SPACE_ID}/environments/{ENV_ID}"

# Secrets Manager client
secrets = boto3.client("secretsmanager", region_name=AWS_REGION)
_cache = {}

def get_secret(name):
    """Retrieve secret from AWS Secrets Manager with caching"""
    if name not in _cache:
        response = secrets.get_secret_value(SecretId=name)
        _cache[name] = response["SecretString"]
    return _cache[name]

def respond(code, body):
    """Create HTTP response"""
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }

def graphql_get_posts():
    """Fetch blog posts using Contentful GraphQL API"""
    token = get_secret(DELIVERY_SECRET)
    
    query = """query {
      blogPostCollection(limit: 10, order: sys_publishedAt_DESC) {
        items {
          sys {
            id
            publishedAt
          }
          title
          slug
          body
        }
      }
    }"""
    
    response = requests.post(
        GRAPHQL_ENDPOINT,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={"query": query},
        timeout=10
    )
    response.raise_for_status()
    return response.json()

def rest_get_posts():
    """Fetch blog posts using Contentful REST Delivery API"""
    token = get_secret(DELIVERY_SECRET)
    
    response = requests.get(
        f"{DELIVERY_REST}/entries",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "content_type": "blogPost",
            "order": "-sys.createdAt"
        },
        timeout=10
    )
    response.raise_for_status()
    return response.json()

def rest_create_post(data):
    """Create blog post using Contentful REST Management API"""
    token = get_secret(MANAGEMENT_SECRET)
    
    payload = {
        "fields": {
            "title": {LOCALE: data["title"]},
            "slug": {LOCALE: data["slug"]},
            "body": {LOCALE: data.get("body", "")}
        }
    }
    
    response = requests.post(
        f"{MANAGEMENT_REST}/entries",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/vnd.contentful.management.v1+json",
            "X-Contentful-Content-Type": "blogPost"
        },
        json=payload,
        timeout=10
    )
    response.raise_for_status()
    
    entry_data = response.json()
    entry_id = entry_data["sys"]["id"]
    
    # Publish the entry
    version = entry_data["sys"]["version"]
    publish_response = requests.put(
        f"{MANAGEMENT_REST}/entries/{entry_id}/published",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Contentful-Version": str(version)
        },
        timeout=10
    )
    publish_response.raise_for_status()
    
    return publish_response.json()

def lambda_handler(event, context):
    """Main Lambda handler"""
    try:
        method = event["requestContext"]["http"]["method"]
        path = event["requestContext"]["http"]["path"]
        print(f"{method} {path}")
        
        # Route: GET /posts - Fetch posts using GraphQL
        if method == "GET" and path == "/posts":
            data = graphql_get_posts()
            return respond(200, data)
        
        # Route: GET /posts-rest - Fetch posts using REST API
        if method == "GET" and path == "/posts-rest":
            data = rest_get_posts()
            return respond(200, data)
        
        # Route: POST /posts - Create new post
        if method == "POST" and path == "/posts":
            body = json.loads(event.get("body", "{}"))
            
            if "title" not in body or "slug" not in body:
                return respond(400, {
                    "message": "title and slug are required",
                    "example": {
                        "title": "My First Post",
                        "slug": "my-first-post",
                        "body": "Optional post content"
                    }
                })
            
            data = rest_create_post(body)
            return respond(201, data)
        
        # Route not found
        return respond(404, {
            "message": "Not found",
            "availableRoutes": {
                "GET /posts": "Fetch posts using GraphQL",
                "GET /posts-rest": "Fetch posts using REST API",
                "POST /posts": "Create new post"
            }
        })
        
    except requests.exceptions.RequestException as e:
        print(f"Contentful API error: {str(e)}")
        return respond(502, {
            "message": "Error communicating with Contentful API",
            "error": str(e)
        })
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return respond(500, {
            "message": "Internal server error",
            "error": str(e)
        })
EOF

echo "✅ Lambda function code created"
```

---

## Step 8: Create Requirements File

```bash
cat > src/requirements.txt <<'EOF'
requests==2.31.0
EOF

echo "✅ requirements.txt created"
```

---

## Step 9: Build SAM Application

```bash
# Build SAM application (downloads Python dependencies from requirements.txt)
echo "Building SAM application..."
sam build

if [ $? -eq 0 ]; then
    echo "✅ Build complete - Lambda package ready"
else
    echo "❌ Build failed - check Python code and requirements.txt"
    exit 1
fi
```

---

## Step 10: Deploy SAM Application

```bash
# Deploy SAM application to AWS (creates CloudFormation stack)
echo "Deploying to AWS..."
echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo ""

# Deploy with Space ID as parameter (secrets retrieved from Secrets Manager at runtime)
sam deploy \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides ContentfulSpaceId="$CONTENTFUL_SPACE_ID" \
  --resolve-s3 \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset

if [ $? -eq 0 ]; then
    echo "✅ Deployment successful"
else
    echo "❌ Deployment failed - check CloudFormation console for details"
    exit 1
fi
```

---

## Step 11: Retrieve Stack Outputs

```bash
# Retrieve stack outputs
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text)

FUNCTION_NAME=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='FunctionName'].OutputValue" \
  --output text)

# Display deployment information
echo ""
echo "=" | head -c 60 && echo
echo "API Endpoint: $API_ENDPOINT"
echo "Lambda Function: $FUNCTION_NAME"
echo "=" | head -c 60 && echo
echo ""
echo "Available Endpoints:"
echo "  GET  $API_ENDPOINT/posts"
echo "  GET  $API_ENDPOINT/posts-rest"
echo "  POST $API_ENDPOINT/posts"
echo ""
```

---

## Step 12: Create Sample Content via Lambda

```bash
echo "Creating sample blog post..."

# Lambda retrieves Management token from Secrets Manager to create content
curl -X POST "$API_ENDPOINT/posts" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Hello from AWS Lambda",
    "slug": "hello-lambda",
    "body": "This post was created via AWS Lambda using Contentful Management API"
  }' 2>/dev/null | python3 -m json.tool

echo ""
echo "✅ Post created and published"
```

---

## Step 13: Test GraphQL Endpoint

```bash
echo "Fetching posts via GraphQL..."

# Lambda retrieves Delivery token from Secrets Manager to query Contentful
curl -s "$API_ENDPOINT/posts" 2>/dev/null | python3 -m json.tool

echo ""
echo "✅ GraphQL query successful"
```

---

## Step 14: Test REST Delivery Endpoint

```bash
echo "Fetching posts via REST Delivery API..."

# Compare GraphQL vs REST API response structure
curl -s "$API_ENDPOINT/posts-rest" 2>/dev/null | python3 -m json.tool

echo ""
echo "✅ REST query successful"
```

---

## Step 15: Create Additional Posts

```bash
echo "Creating additional posts..."

curl -X POST "$API_ENDPOINT/posts" \
  -H "Content-Type: application/json" \
  -d '{"title":"Serverless Architecture","slug":"serverless","body":"AWS Lambda benefits"}' \
  2>/dev/null | python3 -m json.tool

curl -X POST "$API_ENDPOINT/posts" \
  -H "Content-Type: application/json" \
  -d '{"title":"Headless CMS","slug":"headless-cms","body":"API-first content management"}' \
  2>/dev/null | python3 -m json.tool

echo "✅ Additional posts created"
echo ""
echo "Fetching all posts:"
curl -s "$API_ENDPOINT/posts" 2>/dev/null | python3 -m json.tool
```

---

## Step 16: View Lambda Logs

```bash
echo "Viewing Lambda logs (Ctrl+C to stop):"
echo ""

# Stream Lambda execution logs (shows Secrets Manager retrievals and Contentful API calls)
aws logs tail "/aws/lambda/$FUNCTION_NAME" \
  --region "$REGION" \
  --follow \
  --format short
```

---

## Step 17: Test Error Handling

```bash
echo "Testing error handling..."
echo ""

# Test missing required field
echo "1. Missing slug field:"
curl -X POST "$API_ENDPOINT/posts" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test"}' 2>/dev/null | python3 -m json.tool

echo ""
echo "2. Invalid route:"
curl -s "$API_ENDPOINT/invalid" 2>/dev/null | python3 -m json.tool

echo ""
echo "✅ Error handling verified"
```

---

## Step 18: View Stack Resources

```bash
echo "CloudFormation stack resources:"

# List all resources (Lambda, API Gateway, IAM roles, log groups)
aws cloudformation describe-stack-resources \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "StackResources[*].{Type:ResourceType,Status:ResourceStatus}" \
  --output table
```

---

## Step 19: Monitor Lambda Metrics

```bash
echo "Lambda metrics (last hour):"

# Get invocation count from CloudWatch
INVOCATIONS=$(aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value="$FUNCTION_NAME" \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum \
  --region "$REGION" \
  --query 'Datapoints[0].Sum' \
  --output text)

echo "Invocations: ${INVOCATIONS:-0}"
```

---

## Step 20: Cleanup Resources

```bash
echo "=" | head -c 50 && echo
echo "CLEANUP"
echo "=" | head -c 50 && echo

# Delete CloudFormation stack (removes Lambda, API Gateway, IAM roles, logs)
aws cloudformation delete-stack \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo "Waiting for stack deletion..."
aws cloudformation wait stack-delete-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION" 2>/dev/null

echo "✅ Stack deleted"

echo ""
echo "⚠️  WARNING: The following deletes secrets PERMANENTLY (no recovery possible)"
read -p "Press Enter to continue or Ctrl+C to abort..."

# Delete Secrets Manager secrets (IRREVERSIBLE - no recovery period)
aws secretsmanager delete-secret \
  --secret-id "$SECRET_DELIVERY_NAME" \
  --region "$REGION" \
  --force-delete-without-recovery 2>/dev/null

aws secretsmanager delete-secret \
  --secret-id "$SECRET_MANAGEMENT_NAME" \
  --region "$REGION" \
  --force-delete-without-recovery 2>/dev/null

echo "✅ Secrets permanently deleted"

# Delete local files
cd ..
rm -rf lab_9_e_contentful

echo "✅ Local files deleted"
echo ""
echo "AWS cleanup complete!"
echo ""
echo "⚠️  Contentful cleanup (optional):"
echo "  - Delete blog posts"
echo "  - Delete Space 'lambda-demo'"
echo "  - Revoke API tokens"
```

---

## Summary

In this lab, you have:
- Deployed serverless Contentful integration using **AWS SAM**
- Stored sensitive credentials in **AWS Secrets Manager**
- Created Lambda function with **GraphQL** and **REST API** access
- Implemented content **READ** operations (Delivery API)
- Implemented content **WRITE** operations (Management API)
- Secured API access with IAM policies
- Tested all endpoints and error handling
- Cleaned up all AWS resources

**Key Takeaways:**
- **Pattern 2 Architecture**: AWS owns the API boundary
- **API-Only CMS**: Contentful is accessed only via APIs
- **Security**: Secrets managed by AWS, not in code
- **GraphQL**: Efficient queries for specific data
- **REST Management API**: Full CRUD operations
- **Infrastructure as Code**: SAM template ensures reproducibility

**Use Cases:**
- **Headless CMS**: Content API for web/mobile apps
- **Content Syndication**: Distribute content to multiple channels
- **JAMstack**: Static site generation with dynamic content
- **Multi-Channel Publishing**: Web, mobile, IoT devices
- **Content as a Service**: Expose content via API

---

## Best Practices

**Security:**
- ✅ Use Secrets Manager for API tokens
- ✅ Implement least-privilege IAM policies
- ✅ Enable CORS only for trusted origins
- ✅ Validate input data
- ✅ Use environment variables for configuration

**Performance:**
- ✅ Cache secrets in Lambda execution context
- ✅ Use GraphQL for efficient data fetching
- ✅ Implement proper error handling
- ✅ Set appropriate Lambda timeout and memory
- ✅ Use CloudFront for content delivery

**Reliability:**
- ✅ Implement retry logic for API calls
- ✅ Use proper exception handling
- ✅ Monitor Lambda metrics and logs
- ✅ Set up CloudWatch alarms
- ✅ Use dead letter queues for failures

**Cost Optimization:**
- ✅ Use HTTP API (cheaper than REST API)
- ✅ Optimize Lambda memory and timeout
- ✅ Cache frequently accessed content
- ✅ Use Contentful's CDN
- ✅ Monitor API usage quotas

---

## Production Enhancements

1. **Add Caching Layer**
   ```yaml
   # Add ElastiCache Redis for content caching
   CacheCluster:
     Type: AWS::ElastiCache::CacheCluster
     Properties:
       Engine: redis
   ```

2. **Implement Authentication**
   ```yaml
   # Add Cognito authorizer
   ContentfulApi:
     Type: AWS::Serverless::HttpApi
     Properties:
       Auth:
         Authorizers:
           CognitoAuthorizer:
             IdentitySource: $request.header.Authorization
   ```

3. **Add Rate Limiting**
   ```yaml
   # Add usage plan for API throttling
   ApiUsagePlan:
     Type: AWS::ApiGateway::UsagePlan
     Properties:
       Throttle:
         RateLimit: 100
         BurstLimit: 200
   ```

4. **Implement Content Webhooks**
   ```python
   # Handle Contentful webhooks for real-time updates
   def handle_webhook(event):
       topic = event["headers"]["x-contentful-topic"]
       # Invalidate cache, trigger rebuild, etc.
   ```

5. **Add Observability**
   ```yaml
   # Enable X-Ray tracing
   Globals:
     Function:
       Tracing: Active
   ```

---

## Additional Resources

- [Contentful API Documentation](https://www.contentful.com/developers/docs/references/)
- [Contentful GraphQL API](https://www.contentful.com/developers/docs/references/graphql/)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [AWS Secrets Manager Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- [Headless CMS Architecture Patterns](https://www.contentful.com/developers/docs/concepts/apis/)
