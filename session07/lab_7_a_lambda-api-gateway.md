# Lab 7.A: Build a REST API using API Gateway integrated with Lambda

## Overview
Build a simple REST API backed by AWS Lambda and API Gateway. This lab covers designing HTTP endpoints, creating Lambda functions, wiring API Gateway (HTTP API or REST API) integrations, enabling CORS, deploying stages, testing, and cleaning up. Examples use AWS CLI and AWS SAM for convenience.

## Objectives
- Design REST endpoints and methods
- Create Lambda functions and minimal IAM execution role
- Integrate Lambda with API Gateway (HTTP API and REST API examples)
- Configure CORS, request/response mapping, and stage deployment
- Test endpoints (local and deployed)
- Clean up resources

## Prerequisites
- AWS CLI v2 configured
- Python 3 or Node.js for Lambda code
- (Optional) AWS SAM CLI and Docker for local testing

---

## Minimal architecture
- Lambda function(s) implement handlers for API operations
- API Gateway routes HTTP methods/paths to Lambda
- IAM role for Lambda execution (logs + basic permissions)
- Stage (e.g., dev) provides a public invoke endpoint

---

## Quick design: Example endpoints
- GET /items         — list items
- GET /items/{id}    — get single item
- POST /items        — create item
- PUT /items/{id}    — update item
- DELETE /items/{id} — delete item

---

## Steps (CLI examples)

### 1. Create Lambda execution role (trust policy + basic policy)
```bash
cat > trust.json <<'EOF'
{
  "Version":"2012-10-17",
  "Statement":[
    { "Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole" }
  ]
}
EOF

aws iam create-role --role-name lab-lambda-exec --assume-role-policy-document file://trust.json
aws iam attach-role-policy --role-name lab-lambda-exec --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

### 2. Create a simple Lambda function (Python example)
```bash
mkdir -p session07/function
cat > session07/function/app.py <<'PY'
import json

def lambda_handler(event, context):
    path = event.get('rawPath') or event.get('path', '/')
    method = event.get('requestContext', {}).get('http', {}).get('method') or event.get('httpMethod')
    # simple router
    if method == "GET" and path == "/items":
        return {"statusCode":200,"body":json.dumps([{"id":"1","name":"item1"}])}
    return {"statusCode":404,"body":json.dumps({"message":"Not found"})}
PY

zip -j function.zip session07/function/app.py
aws lambda create-function --function-name lab-api-handler \
  --runtime python3.12 --handler app.lambda_handler --zip-file fileb://function.zip \
  --role arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/lab-lambda-exec
```

### 3. Create an API Gateway HTTP API and integrate with Lambda (simpler, lower latency)
```bash
API_ID=$(aws apigatewayv2 create-api --name lab-http-api --protocol-type HTTP --target arn:aws:lambda:$(aws configure get region):$(aws sts get-caller-identity --query Account --output text):function:lab-api-handler --query ApiId --output text)
# Grant invoke permission to API Gateway
aws lambda add-permission --function-name lab-api-handler --statement-id apigw-invoke --action lambda:InvokeFunction --principal apigateway.amazonaws.com --source-arn "arn:aws:execute-api:$(aws configure get region):$(aws sts get-caller-identity --query Account --output text):$API_ID/*/*/*"
# Create a route and integration (for path /items and method GET)
INTEGRATION_ARN=$(aws apigatewayv2 create-integration --api-id $API_ID --integration-type AWS_PROXY --integration-uri arn:aws:lambda:$(aws configure get region):$(aws sts get-caller-identity --query Account --output text):function:lab-api-handler --payload-format-version "2.0" --query IntegrationId --output text)
aws apigatewayv2 create-route --api-id $API_ID --route-key "GET /items" --target "integrations/$INTEGRATION_ARN"
aws apigatewayv2 create-deployment --api-id $API_ID --query DeploymentId --output text
aws apigatewayv2 create-stage --api-id $API_ID --stage-name dev
API_ENDPOINT=$(aws apigatewayv2 get-stage --api-id $API_ID --stage-name dev --query 'StageVariables' --output json; aws apigatewayv2 get-api --api-id $API_ID --query "ApiEndpoint" --output text)
echo "API endpoint: https://$API_ID.execute-api.$(aws configure get region).amazonaws.com/dev"
```

### 4. (Alternative) Create a REST API with method/request mapping (if you need advanced mapping)
- Use aws apigateway import-rest-api or console to define resources/methods, set Lambda integration URI, enable mapping templates for request/response.
- Deploy using create-deployment and create-stage.

### 5. Enable CORS (HTTP API)
```bash
# For HTTP API you can set CORS directly:
aws apigatewayv2 update-api --api-id $API_ID --cors-configuration AllowOrigins='["*"]' AllowMethods='["GET","POST","PUT","DELETE","OPTIONS"]' AllowHeaders='["Content-Type","Authorization"]'
```

### 6. Test the endpoint
```bash
curl -v "https://$API_ID.execute-api.$(aws configure get region).amazonaws.com/dev/items"
```

### 7. Use SAM for local development & deployment (optional)
- sam init -> add function, sam build, sam local start-api (test locally)
- sam deploy --guided to deploy stack (creates Lambda and API Gateway and outputs endpoint)

---

## Logging, monitoring & security
- Lambda logs: CloudWatch Logs (/aws/lambda/<function-name>)
- Capture request/response metrics with API Gateway access logs and CloudWatch
- Apply IAM authorizers or JWT (Cognito/OIDC) for auth
- Use WAF to protect against common web attacks (optional)

---

## Validation Checklist
- [ ] Lambda function created and running
- [ ] API Gateway route integrated to Lambda
- [ ] CORS configured for browser clients
- [ ] Endpoint responds to GET/POST as designed
- [ ] Logs available in CloudWatch for function and API
- [ ] Authentication/authorization applied if required

---

## Cleanup
```bash
aws lambda delete-function --function-name lab-api-handler || true
aws apigatewayv2 delete-api --api-id $API_ID || true
aws iam detach-role-policy --role-name lab-lambda-exec --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole || true
aws iam delete-role --role-name lab-lambda-exec || true
rm -f function.zip
```

## Summary
This lab provides a focused, hands-on walkthrough to build a REST API using API Gateway integrated with Lambda, covering function creation, API wiring, CORS, testing, and cleanup. Use SAM for faster local iteration and apply auth and observability for production readiness
