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

```bash
echo "================================================"
echo "CONTENTFUL SETUP INSTRUCTIONS"
echo "================================================"
echo ""
echo "1. Go to https://www.contentful.com/sign-up/"
echo "2. Create a free account"
echo "3. Create a new Space (name: 'lambda-demo')"
echo "4. Use environment: 'master'"
echo ""
echo "5. Create content type 'blogPost' with fields:"
echo "   - title (Short text, required)"
echo "   - slug (Short text, required)"
echo "   - body (Long text / Rich text)"
echo ""
echo "6. Generate API tokens from Settings > API keys:"
echo "   - Content Delivery API token (read-only)"
echo "   - Content Management API token (admin)"
echo ""
read -p "Press Enter when you have completed Contentful setup..."
echo ""
read -p "Enter Contentful Space ID: " CONTENTFUL_SPACE_ID
read -p "Enter Content Delivery API token: " CONTENTFUL_DELIVERY_TOKEN
read -p "Enter Content Management API token: " CONTENTFUL_MANAGEMENT_TOKEN
echo ""
echo "✅ Contentful credentials collected"
```

---

## Step 2: Store Secrets in AWS Secrets Manager

```bash
# Set region
REGION="ap-southeast-2"

# Create secret for Delivery API token
aws secretsmanager create-secret \
  --region "$REGION" \
  --name contentful/delivery-token \
  --secret-string "$CONTENTFUL_DELIVERY_TOKEN" \
  --description "Contentful Content Delivery API token (read-only)"

# Create secret for Management API token
aws secretsmanager create-secret \
  --region "$REGION" \
  --name contentful/management-token \
  --secret-string "$CONTENTFUL_MANAGEMENT_TOKEN" \
  --description "Contentful Content Management API token (admin)"

echo "✅ Secrets stored in AWS Secrets Manager"

# Verify secrets
aws secretsmanager list-secrets \
  --region "$REGION" \
  --query "SecretList[?contains(Name, 'contentful')].{Name:Name,Created:CreatedDate}" \
  --output table
```

---

## Step 3: Create Project Structure

```bash
# Create project directory
mkdir -p lab_9_e_contentful
cd lab_9_e_contentful

# Create source directory
mkdir -p src

echo "✅ Project structure created"
```

---

## Step 4: Create AWS SAM Template

```bash
cat > template.yaml <<'EOF'
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Lab 9-E Contentful Integration

Globals:
  Function:
    Runtime: python3.11
    Timeout: 15
    MemorySize: 256

Resources:

  ContentfulApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      CorsConfiguration:
        AllowOrigins: ['*']
        AllowMethods: ['GET', 'POST']
        AllowHeaders: ['Content-Type', 'Authorization']

  ContentfulFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: lambda_function.lambda_handler
      Environment:
        Variables:
          AWS_REGION: ap-southeast-2
          CONTENTFUL_SPACE_ID: REPLACE_WITH_YOUR_SPACE_ID
          CONTENTFUL_ENV: master
          CONTENTFUL_LOCALE: en-US
          SECRET_DELIVERY_NAME: contentful/delivery-token
          SECRET_MANAGEMENT_NAME: contentful/management-token
      Policies:
        - AWSSecretsManagerGetSecretValuePolicy:
            SecretArn: !Sub 'arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:contentful/*'
      Events:
        GetPostsGraphQL:
          Type: HttpApi
          Properties:
            ApiId: !Ref ContentfulApi
            Path: /posts
            Method: GET
        GetPostsRest:
          Type: HttpApi
          Properties:
            ApiId: !Ref ContentfulApi
            Path: /posts-rest
            Method: GET
        CreatePost:
          Type: HttpApi
          Properties:
            ApiId: !Ref ContentfulApi
            Path: /posts
            Method: POST

Outputs:
  ApiEndpoint:
    Description: "HTTP API endpoint URL"
    Value: !Sub "https://${ContentfulApi}.execute-api.${AWS::Region}.amazonaws.com"
  FunctionName:
    Description: "Lambda Function Name"
    Value: !Ref ContentfulFunction
EOF

echo "✅ SAM template created"
```

---

## Step 5: Update SAM Template with Your Space ID

```bash
# Replace placeholder with actual Space ID
sed -i "s/REPLACE_WITH_YOUR_SPACE_ID/$CONTENTFUL_SPACE_ID/" template.yaml

echo "✅ Template updated with Space ID: $CONTENTFUL_SPACE_ID"
```

---

## Step 6: Create Lambda Function Code

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
    print(f"Event: {json.dumps(event)}")
    
    try:
        method = event["requestContext"]["http"]["method"]
        path = event["requestContext"]["http"]["path"]
        
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

## Step 7: Create Requirements File

```bash
cat > src/requirements.txt <<'EOF'
requests==2.31.0
EOF

echo "✅ requirements.txt created"
```

---

## Step 8: Build SAM Application

```bash
# Build the application
sam build

echo ""
echo "✅ SAM build complete"
```

---

## Step 9: Deploy SAM Application

```bash
# Deploy with guided prompts
sam deploy \
  --guided \
  --stack-name lab-9e-contentful \
  --region "$REGION" \
  --capabilities CAPABILITY_IAM

echo ""
echo "✅ Deployment initiated"
echo ""
echo "Answer the prompts:"
echo "  - Stack Name: lab-9e-contentful"
echo "  - AWS Region: ap-southeast-2"
echo "  - Confirm changes: y"
echo "  - Allow SAM CLI IAM role creation: y"
echo "  - ContentfulFunction has no authentication: y"
echo "  - Save arguments to config file: y"
```

---

## Step 10: Get API Endpoint

```bash
# Get the API endpoint from stack outputs
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name lab-9e-contentful \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text)

FUNCTION_NAME=$(aws cloudformation describe-stacks \
  --stack-name lab-9e-contentful \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='FunctionName'].OutputValue" \
  --output text)

echo ""
echo "================================================"
echo "DEPLOYMENT COMPLETE"
echo "================================================"
echo ""
echo "API Endpoint: $API_ENDPOINT"
echo "Function Name: $FUNCTION_NAME"
echo ""
echo "Test URLs:"
echo "  ${API_ENDPOINT}/posts"
echo "  ${API_ENDPOINT}/posts-rest"
```

---

## Step 11: Create Sample Content in Contentful

```bash
echo ""
echo "Creating sample blog post via API..."

curl -X POST "${API_ENDPOINT}/posts" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Hello from AWS Lambda",
    "slug": "hello-lambda",
    "body": "This post was created via AWS Lambda and Contentful Management API!"
  }' | python3 -m json.tool

echo ""
echo "✅ Sample post created"
```

---

## Step 12: Test GraphQL Endpoint

```bash
echo ""
echo "Testing GraphQL endpoint..."
echo ""

curl -s "${API_ENDPOINT}/posts" | python3 -m json.tool

echo ""
echo "✅ GraphQL test complete"
```

---

## Step 13: Test REST Delivery Endpoint

```bash
echo ""
echo "Testing REST Delivery endpoint..."
echo ""

curl -s "${API_ENDPOINT}/posts-rest" | python3 -m json.tool

echo ""
echo "✅ REST Delivery test complete"
```

---

## Step 14: Create Additional Posts

```bash
echo ""
echo "Creating more sample posts..."

# Post 2
curl -X POST "${API_ENDPOINT}/posts" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Serverless Architecture",
    "slug": "serverless-architecture",
    "body": "Exploring the benefits of serverless computing with AWS Lambda and API Gateway."
  }'

# Post 3
curl -X POST "${API_ENDPOINT}/posts" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Headless CMS Benefits",
    "slug": "headless-cms",
    "body": "Why headless CMS like Contentful is the future of content management."
  }'

echo ""
echo "✅ Additional posts created"

# Fetch all posts
echo ""
echo "Fetching all posts via GraphQL..."
curl -s "${API_ENDPOINT}/posts" | python3 -m json.tool
```

---

## Step 15: View Lambda Logs

```bash
echo ""
echo "Recent Lambda logs:"
echo ""

aws logs tail "/aws/lambda/$FUNCTION_NAME" \
  --region "$REGION" \
  --follow \
  --format short
```

---

## Step 16: Test Error Handling

```bash
echo ""
echo "Testing error handling (missing required fields)..."

curl -X POST "${API_ENDPOINT}/posts" \
  -H "Content-Type: application/json" \
  -d '{"title": "Incomplete Post"}' | python3 -m json.tool

echo ""
echo "✅ Error handling test complete"
```

---

## Step 17: View Stack Resources

```bash
echo ""
echo "CloudFormation stack resources:"
echo ""

aws cloudformation describe-stack-resources \
  --stack-name lab-9e-contentful \
  --region "$REGION" \
  --query "StackResources[*].{Type:ResourceType,LogicalId:LogicalResourceId,Status:ResourceStatus}" \
  --output table
```

---

## Step 18: Monitor Lambda Metrics

```bash
echo ""
echo "Lambda metrics (last hour):"

aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value="$FUNCTION_NAME" \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum \
  --region "$REGION" \
  --query 'Datapoints[0].Sum' \
  --output text

echo " invocations in the last hour"
```

---

## Step 19: Cleanup Resources

```bash
echo ""
echo "================================================"
echo "CLEANUP"
echo "================================================"
echo ""

# Delete CloudFormation stack
aws cloudformation delete-stack \
  --stack-name lab-9e-contentful \
  --region "$REGION"

echo "⏳ Deleting CloudFormation stack..."

# Wait for stack deletion
aws cloudformation wait stack-delete-complete \
  --stack-name lab-9e-contentful \
  --region "$REGION"

echo "✅ CloudFormation stack deleted"

# Delete secrets
aws secretsmanager delete-secret \
  --secret-id contentful/delivery-token \
  --region "$REGION" \
  --force-delete-without-recovery

aws secretsmanager delete-secret \
  --secret-id contentful/management-token \
  --region "$REGION" \
  --force-delete-without-recovery

echo "✅ Secrets deleted"

# Delete local files
cd ..
rm -rf lab_9_e_contentful

echo "✅ Local files deleted"
echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Optional: Delete content and space in Contentful dashboard"
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
