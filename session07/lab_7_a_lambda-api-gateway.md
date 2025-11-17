# Lab 7.A: Build Serverless REST API with Lambda and API Gateway

## Overview
This lab demonstrates how to build a serverless REST API using AWS Lambda and API Gateway. You'll create a simple Python joke API with Lambda functions, expose it through API Gateway HTTP API (publicly accessible), and test all endpoints. This serverless architecture requires zero infrastructure management and scales automatically.

---

## Objectives
- Create Python Lambda function for joke API
- Package and deploy Lambda function
- Create API Gateway HTTP API
- Configure routes and Lambda integrations
- Enable CORS for browser access
- Test all API endpoints
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Python 3.12 installed locally
- IAM permissions for Lambda, API Gateway, and IAM
- Basic understanding of REST APIs and Lambda

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID and set variables
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="ap-southeast-2"
FUNCTION_NAME="joke-api"
ROLE_NAME="lambda-joke-api-role"
API_NAME="joke-api"

echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "REGION=$REGION"

```

---

## Step 2 – Create Lambda Function Code

```bash
# Create project directory
mkdir -p joke-api-lambda
cd joke-api-lambda

# Create Lambda function with joke API
cat > lambda_function.py <<'EOF'
import json
import random

# In-memory joke storage (for simplicity)
JOKES = [
    {"id": 1, "joke": "Why do programmers prefer dark mode? Because light attracts bugs!"},
    {"id": 2, "joke": "Why do Java developers wear glasses? Because they don't C#!"},
    {"id": 3, "joke": "How many programmers does it take to change a light bulb? None, that's a hardware problem!"},
    {"id": 4, "joke": "Why did the developer go broke? Because he used up all his cache!"},
    {"id": 5, "joke": "What's a programmer's favorite hangout place? Foo Bar!"}
]

def lambda_handler(event, context):
    """
    Handle API requests:
    - GET /joke - Get random joke
    - GET /jokes - Get all jokes
    - POST /joke - Add new joke
    """
    
    # Parse request
    http_method = event.get('requestContext', {}).get('http', {}).get('method')
    path = event.get('rawPath', '/')
    
    print(f"Method: {http_method}, Path: {path}")
    
    # Route requests
    if http_method == 'GET' and path == '/joke':
        return get_random_joke()
    
    elif http_method == 'GET' and path == '/jokes':
        return get_all_jokes()
    
    elif http_method == 'POST' and path == '/joke':
        return add_joke(event)
    
    elif path == '/':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Welcome to Joke API!',
                'endpoints': {
                    'GET /joke': 'Get a random joke',
                    'GET /jokes': 'Get all jokes',
                    'POST /joke': 'Add a new joke (body: {"joke": "text"})'
                }
            })
        }
    
    # 404 for unknown routes
    return {
        'statusCode': 404,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': 'Not found'})
    }

def get_random_joke():
    """Return a random joke"""
    joke = random.choice(JOKES)
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(joke)
    }

def get_all_jokes():
    """Return all jokes"""
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'count': len(JOKES),
            'jokes': JOKES
        })
    }

def add_joke(event):
    """Add a new joke"""
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        new_joke_text = body.get('joke')
        
        if not new_joke_text:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing joke text'})
            }
        
        # Add new joke
        new_id = max([j['id'] for j in JOKES]) + 1
        new_joke = {'id': new_id, 'joke': new_joke_text}
        JOKES.append(new_joke)
        
        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Joke added successfully',
                'joke': new_joke
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }
EOF
```

---

## Step 3 – Package Lambda Function

```bash
# Create deployment package
zip -r lambda-function.zip lambda_function.py

# Verify package contents
unzip -l lambda-function.zip
```

---

## Step 4 – Create IAM Role for Lambda

```bash
# Create trust policy for Lambda
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

# Create IAM role
aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document file://lambda-trust-policy.json \
  --description "Execution role for joke API Lambda function"

# Attach basic Lambda execution policy (for CloudWatch Logs)
aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Get role ARN
ROLE_ARN=$(aws iam get-role \
  --role-name "$ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)
echo "ROLE_ARN=$ROLE_ARN"

# Wait for IAM role to propagate
sleep 10
```

---

## Step 5 – Create Lambda Function

```bash
# Create Lambda function
aws lambda create-function \
  --function-name "$FUNCTION_NAME" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda-function.zip \
  --timeout 10 \
  --memory-size 128 \
  --description "Serverless joke API" \
  --region "$REGION"

# Get function ARN
FUNCTION_ARN=$(aws lambda get-function \
  --function-name "$FUNCTION_NAME" \
  --query 'Configuration.FunctionArn' \
  --output text \
  --region "$REGION")
echo "FUNCTION_ARN=$FUNCTION_ARN"
```

---

## Step 6 – Test Lambda Function Locally

```bash
# Create test event for GET /joke
cat > test-event-get-joke.json <<'EOF'
{
  "requestContext": {
    "http": {
      "method": "GET"
    }
  },
  "rawPath": "/joke"
}
EOF

# Invoke Lambda function
aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload file://test-event-get-joke.json \
  --region "$REGION" \
  response.json

# Display response
cat response.json | python3 -m json.tool
```

---

## Step 7 – Create API Gateway HTTP API

```bash
# Create HTTP API with Lambda integration
API_ID=$(aws apigatewayv2 create-api \
  --name "$API_NAME" \
  --protocol-type HTTP \
  --description "Serverless joke API with Lambda backend" \
  --region "$REGION" \
  --query 'ApiId' \
  --output text)
echo "API_ID=$API_ID"
```

---

## Step 8 – Create Lambda Integration

```bash
# Create integration with Lambda function
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
  --api-id "$API_ID" \
  --integration-type AWS_PROXY \
  --integration-uri "$FUNCTION_ARN" \
  --payload-format-version "2.0" \
  --region "$REGION" \
  --query 'IntegrationId' \
  --output text)
echo "INTEGRATION_ID=$INTEGRATION_ID"
```

---

## Step 9 – Create API Routes

```bash
# Create route for GET /joke
aws apigatewayv2 create-route \
  --api-id "$API_ID" \
  --route-key "GET /joke" \
  --target "integrations/$INTEGRATION_ID" \
  --region "$REGION"

# Create route for GET /jokes
aws apigatewayv2 create-route \
  --api-id "$API_ID" \
  --route-key "GET /jokes" \
  --target "integrations/$INTEGRATION_ID" \
  --region "$REGION"

# Create route for POST /joke
aws apigatewayv2 create-route \
  --api-id "$API_ID" \
  --route-key "POST /joke" \
  --target "integrations/$INTEGRATION_ID" \
  --region "$REGION"

# Create default route for /
aws apigatewayv2 create-route \
  --api-id "$API_ID" \
  --route-key "GET /" \
  --target "integrations/$INTEGRATION_ID" \
  --region "$REGION"
```

---

## Step 10 – Grant API Gateway Permission to Invoke Lambda

```bash
# Grant API Gateway permission to invoke Lambda function
aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id "apigateway-invoke-$API_ID" \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/*" \
  --region "$REGION"
```

---

## Step 11 – Create and Deploy Stage

```bash
# Create $default stage with auto-deploy
aws apigatewayv2 create-stage \
  --api-id "$API_ID" \
  --stage-name '$default' \
  --auto-deploy \
  --region "$REGION"

# Get API endpoint URL
API_ENDPOINT=$(aws apigatewayv2 get-api \
  --api-id "$API_ID" \
  --query 'ApiEndpoint' \
  --output text \
  --region "$REGION")
echo "API_ENDPOINT=$API_ENDPOINT"
```

---

## Step 12 – Enable CORS

```bash
# Enable CORS for browser-based API access
aws apigatewayv2 update-api \
  --api-id "$API_ID" \
  --cors-configuration \
    AllowOrigins='["*"]',\
AllowMethods='["GET","POST","OPTIONS"]',\
AllowHeaders='["Content-Type"]' \
  --region "$REGION"
```

---

## Step 13 – Test API Endpoints

```bash
echo "API_ENDPOINT=$API_ENDPOINT"

# Wait for deployment to complete
sleep 5

# Test welcome endpoint (GET /)
echo "\n1. Testing GET / (welcome):"
curl -s "${API_ENDPOINT}/" | python3 -m json.tool  # Test via curl
"$BROWSER" "${API_ENDPOINT}/"  # Open in browser

# Test random joke endpoint (GET /joke)
echo "\n2. Testing GET /joke (random joke):"
curl -s "${API_ENDPOINT}/joke" | python3 -m json.tool  # Get random joke via curl
"$BROWSER" "${API_ENDPOINT}/joke"  # Open in browser

# Test all jokes endpoint (GET /jokes)
echo "\n3. Testing GET /jokes (all jokes):"
curl -s "${API_ENDPOINT}/jokes" | python3 -m json.tool  # Get all jokes via curl
"$BROWSER" "${API_ENDPOINT}/jokes"  # Open in browser

# Test POST endpoint to add new joke
echo "\n4. Testing POST /joke (add new joke):"
curl -s -X POST "${API_ENDPOINT}/joke" \
  -H "Content-Type: application/json" \
  -d '{"joke":"Why do programmers always mix up Halloween and Christmas? Because Oct 31 == Dec 25!"}' | python3 -m json.tool  # Add new joke via POST request

# Verify new joke was added (GET /jokes again)
echo "\n5. Testing GET /jokes again (verify new joke added):"
curl -s "${API_ENDPOINT}/jokes" | python3 -m json.tool  # Verify joke list includes new joke
"$BROWSER" "${API_ENDPOINT}/jokes"  # Open in browser to see updated list

```

---

## Step 14 – View Lambda Logs

```bash
# Get latest log stream
LOG_STREAM=$(aws logs describe-log-streams \
  --log-group-name "/aws/lambda/$FUNCTION_NAME" \
  --order-by LastEventTime \
  --descending \
  --max-items 1 \
  --query 'logStreams[0].logStreamName' \
  --output text \
  --region "$REGION")
echo "LOG_STREAM=$LOG_STREAM"

# Get recent log events
echo "\nRecent Lambda invocations:"
aws logs get-log-events \
  --log-group-name "/aws/lambda/$FUNCTION_NAME" \
  --log-stream-name "$LOG_STREAM" \
  --limit 20 \
  --query 'events[*].message' \
  --output text \
  --region "$REGION"
```

---

## Step 15 – View API Gateway Details

```bash
# View API configuration
echo "\nAPI Gateway Configuration:"
aws apigatewayv2 get-api \
  --api-id "$API_ID" \
  --query '{Name:Name,Endpoint:ApiEndpoint,Protocol:ProtocolType,CreatedDate:CreatedDate}' \
  --output table \
  --region "$REGION"

# View routes
echo "\nAPI Routes:"
aws apigatewayv2 get-routes \
  --api-id "$API_ID" \
  --query 'Items[*].{RouteKey:RouteKey,Target:Target}' \
  --output table \
  --region "$REGION"

# View integrations
echo "\nAPI Integrations:"
aws apigatewayv2 get-integrations \
  --api-id "$API_ID" \
  --query 'Items[*].{IntegrationId:IntegrationId,IntegrationType:IntegrationType,IntegrationUri:IntegrationUri}' \
  --output table \
  --region "$REGION"
```

---

## Step 16 – Cleanup Resources

```bash
# Delete API Gateway HTTP API
aws apigatewayv2 delete-api \
  --api-id "$API_ID" \
  --region "$REGION"

# Delete Lambda function
aws lambda delete-function \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION"

# Detach policy and delete IAM role
aws iam detach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam delete-role \
  --role-name "$ROLE_NAME"

# Delete CloudWatch log group
aws logs delete-log-group \
  --log-group-name "/aws/lambda/$FUNCTION_NAME" \
  --region "$REGION" \
  2>/dev/null || true

# Delete local files
rm -f lambda_function.py lambda-function.zip lambda-trust-policy.json
rm -f test-event-get-joke.json response.json
```

---

## Summary

In this lab, you have:
- Created Python Lambda function with joke API (GET /joke, GET /jokes, POST /joke)
- Packaged and deployed Lambda function
- Created API Gateway HTTP API
- Configured Lambda integration with API Gateway
- Created routes for all endpoints
- Enabled CORS for browser access
- Tested all API endpoints
- Viewed Lambda logs in CloudWatch
- Cleaned up all resources

**Key Takeaways:**
- **Serverless**: No infrastructure to manage, automatic scaling
- **Lambda**: Event-driven compute, pay per invocation
- **API Gateway HTTP API**: Low-latency, cost-effective REST APIs
- **AWS_PROXY Integration**: Lambda handles full request/response
- **Payload Format 2.0**: Simplified event format for HTTP APIs
- **CORS**: Required for browser-based API calls

**Lambda Event Structure (Payload 2.0):**
```json
{
  "requestContext": {
    "http": {
      "method": "GET"
    }
  },
  "rawPath": "/joke",
  "body": "{...}"
}
```

**API Architecture:**
```
Client → API Gateway → Lambda → Response
         (Routes)     (Handler)
```

**Best Practices:**
- Use payload format 2.0 for HTTP APIs (simpler)
- Enable CloudWatch Logs for debugging
- Set appropriate Lambda timeout (10s default)
- Use minimal IAM permissions
- Enable CORS for browser access
- Use environment variables for configuration
- Implement proper error handling
- Add request validation for POST endpoints

**HTTP API vs REST API:**
| Feature | HTTP API | REST API |
|---------|----------|----------|
| **Cost** | ~$1/million | ~$3.50/million |
| **Latency** | Lower | Higher |
| **Features** | Basic | Advanced (caching, models) |
| **Best For** | Simple APIs | Complex APIs |

---

## Production Enhancements

For production deployment:

1. **Add Authentication**
   ```bash
   # Use Lambda authorizer or JWT authorizer
   aws apigatewayv2 create-authorizer \
     --api-id $API_ID \
     --authorizer-type JWT \
     --identity-source '$request.header.Authorization'
   ```

2. **Use DynamoDB for Persistence**
   - Replace in-memory JOKES list with DynamoDB table
   - Add IAM policy for Lambda to access DynamoDB

3. **Add API Throttling**
   ```bash
   # Set throttle limits per route
   aws apigatewayv2 update-route \
     --api-id $API_ID \
     --route-id $ROUTE_ID \
     --throttle-settings RateLimit=100,BurstLimit=200
   ```

4. **Custom Domain**
   ```bash
   # Create custom domain with ACM certificate
   aws apigatewayv2 create-domain-name \
     --domain-name api.example.com \
     --domain-name-configurations CertificateArn=$CERT_ARN
   ```

5. **Monitoring and Alarms**
   - CloudWatch alarms for Lambda errors
   - API Gateway access logging
   - X-Ray tracing for distributed tracing

6. **Input Validation**
   - Add request validation schemas
   - Validate POST body structure
   - Sanitize user input

7. **CI/CD Pipeline**
   - Use AWS SAM or Serverless Framework
   - Automated testing and deployment
   - Multiple stages (dev, staging, prod)
