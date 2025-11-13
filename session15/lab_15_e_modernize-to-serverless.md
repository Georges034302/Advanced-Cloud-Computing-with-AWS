# Lab 15.E: Application Modernization – Refactor Legacy to Serverless

## Overview
This lab demonstrates how to **modernize a legacy monolithic application** by refactoring it into a fully serverless architecture. You'll convert traditional application code into AWS Lambda functions, expose them via Amazon API Gateway, store data in Amazon DynamoDB, and validate the complete serverless solution.

This migration strategy eliminates server management, provides automatic scaling, reduces operational overhead, and offers a pay-per-use pricing model.

---

## Objectives
- Analyze and extract business logic from legacy applications
- Refactor monolithic code into serverless Lambda functions
- Create and configure Amazon DynamoDB NoSQL database
- Deploy Lambda functions with proper IAM roles
- Build REST API using Amazon API Gateway
- Integrate API Gateway with Lambda (proxy integration)
- Test serverless API endpoints with real requests
- Verify data persistence in DynamoDB
- Monitor Lambda execution with CloudWatch Logs
- Perform comprehensive resource cleanup

---

## Prerequisites
- AWS CLI configured with appropriate credentials
- IAM permissions for Lambda, DynamoDB, API Gateway, IAM, and CloudWatch
- Python 3.10+ installed locally
- Region: **ap-southeast-2** (Sydney)
- Basic understanding of REST APIs and serverless concepts
- `curl` and `jq` for testing (optional)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│          Serverless Modernization Architecture                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Legacy Application (Monolithic)                                    │
│  ┌─────────────────────────────┐                                   │
│  │  - Runs on servers 24/7     │                                   │
│  │  - Manual scaling           │                                   │
│  │  - Fixed costs              │                                   │
│  │  - Server maintenance       │                                   │
│  └─────────────────────────────┘                                   │
│              │                                                      │
│              │ Refactor & Modernize                                │
│              ▼                                                      │
│  Serverless Architecture (AWS)                                      │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Client / User                             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                           │                                        │
│                           │ HTTPS Request                          │
│                           ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │            Amazon API Gateway (REST API)                     │  │
│  │  - Fully managed API service                                 │  │
│  │  - Request validation & throttling                           │  │
│  │  - API keys & usage plans                                    │  │
│  │  - CORS support                                              │  │
│  │  Endpoint: /prod/modernized                                  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                           │                                        │
│                           │ Invoke (Proxy Integration)             │
│                           ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              AWS Lambda Function                             │  │
│  │  - Runtime: Python 3.10                                      │  │
│  │  - Memory: 128 MB                                            │  │
│  │  - Timeout: 10 seconds                                       │  │
│  │  - Auto-scaling & high availability                          │  │
│  │  - Pay per invocation                                        │  │
│  │  Function: legacy-modernized-fn                              │  │
│  │                                                              │  │
│  │  Business Logic:                                             │  │
│  │  1. Process incoming request                                 │  │
│  │  2. Execute business logic                                   │  │
│  │  3. Store data in DynamoDB                                   │  │
│  │  4. Return JSON response                                     │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                           │                                        │
│                           │ Read/Write                             │
│                           ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │            Amazon DynamoDB (NoSQL Database)                  │  │
│  │  - Fully managed NoSQL database                              │  │
│  │  - Automatic scaling                                         │  │
│  │  - Single-digit millisecond latency                          │  │
│  │  - Pay-per-request billing                                   │  │
│  │  Table: LegacyModernizedTable                                │  │
│  │  Primary Key: pk (String)                                    │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                           │                                        │
│                           ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │            Amazon CloudWatch Logs                            │  │
│  │  - Centralized logging                                       │  │
│  │  - Log retention & search                                    │  │
│  │  - Metrics & alarms                                          │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Benefits of Serverless Architecture:                               │
│  ✓ No server management or provisioning                            │
│  ✓ Automatic scaling (0 to thousands)                              │
│  ✓ Pay only for what you use                                       │
│  ✓ High availability built-in                                      │
│  ✓ Faster time to market                                           │
│  ✓ Reduced operational complexity                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

Request Flow:
1. Client sends HTTP GET request to API Gateway endpoint
2. API Gateway validates request and invokes Lambda function
3. Lambda processes request and executes business logic
4. Lambda writes data to DynamoDB table
5. Lambda returns JSON response to API Gateway
6. API Gateway returns response to client
7. CloudWatch logs capture all execution details
```

---

## Cost Estimate
- **Lambda**: First 1M requests free, then $0.20 per 1M requests
- **Lambda Compute**: $0.0000166667 per GB-second (first 400,000 GB-seconds free)
- **API Gateway**: First 1M requests free, then $3.50 per million
- **DynamoDB**: 25 GB storage free, pay-per-request $1.25 per million writes
- **CloudWatch Logs**: First 5 GB free, then $0.50 per GB
- **Estimated Lab Cost**: < $0.10 for testing

---

# Step 1 – Set Environment Variables

```bash
# Set primary region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "✅ Region set to: $REGION"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "✅ AWS Account ID: $ACCOUNT_ID"

# Define resource names
FUNCTION_NAME="legacy-modernized-fn"
TABLE_NAME="LegacyModernizedTable"
API_NAME="LegacyModernizedAPI"
ROLE_NAME="lambdaModernizationRole"
ZIP_NAME="lambda.zip"
WORK_DIR="/tmp/legacy-modernize"

# Echo all variables for verification
echo ""
echo "=== Environment Configuration ==="
echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
echo "Lambda Function: $FUNCTION_NAME"
echo "DynamoDB Table: $TABLE_NAME"
echo "API Gateway Name: $API_NAME"
echo "IAM Role: $ROLE_NAME"
echo "Deployment Package: $ZIP_NAME"
echo "Working Directory: $WORK_DIR"
echo "================================="
echo ""
```

**Expected Output:**
```
✅ Region set to: ap-southeast-2
✅ AWS Account ID: 123456789012

=== Environment Configuration ===
Region: ap-southeast-2
Account ID: 123456789012
Lambda Function: legacy-modernized-fn
DynamoDB Table: LegacyModernizedTable
API Gateway Name: LegacyModernizedAPI
IAM Role: lambdaModernizationRole
Deployment Package: lambda.zip
Working Directory: /tmp/legacy-modernize
=================================
```

---

# Step 2 – Create Legacy Application Code (Simulation)

```bash
# Create working directory for the project
echo "Creating project directory..."
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"
echo "✅ Working directory created: $WORK_DIR"

# Simulate legacy application business logic
echo ""
echo "Creating legacy application code..."

cat > legacy.py << 'EOF'
"""
Legacy Application Business Logic
This represents the core business logic from a monolithic application
that we're extracting and modernizing into a serverless function.
"""

def process_message(name):
    """
    Core business logic from legacy application.
    In real scenarios, this could be complex business rules,
    data transformations, or calculations.
    
    Args:
        name: User name or identifier
        
    Returns:
        Processed message string
    """
    # Simulate legacy business logic
    message = f"Hello {name}, your legacy application has been successfully modernized to serverless!"
    
    # In a real scenario, this might include:
    # - Complex calculations
    # - Business rule validations
    # - Data transformations
    # - Integration with other systems
    
    return message

def validate_input(name):
    """
    Input validation logic from legacy app.
    
    Args:
        name: Input to validate
        
    Returns:
        Boolean indicating if input is valid
    """
    if not name or len(name.strip()) == 0:
        return False
    if len(name) > 100:
        return False
    return True

def get_greeting_prefix(name):
    """
    Additional legacy business logic.
    
    Args:
        name: User name
        
    Returns:
        Appropriate greeting prefix
    """
    # Example: Time-based greetings or role-based prefixes
    if name.lower() in ['admin', 'administrator']:
        return "Welcome back, Administrator"
    return "Hello"
EOF

echo "✅ Legacy application code created: legacy.py"

# Display the legacy code
echo ""
echo "=== Legacy Application Code ==="
cat legacy.py
echo "==============================="
echo ""
```

**Expected Output:**
```
Creating project directory...
✅ Working directory created: /tmp/legacy-modernize

Creating legacy application code...
✅ Legacy application code created: legacy.py

=== Legacy Application Code ===
"""
Legacy Application Business Logic
...
"""
===============================
```

---

# Step 3 – Refactor Legacy Logic into Lambda Function

```bash
# Create Lambda handler that wraps legacy logic
echo "Creating serverless Lambda function..."

cat > lambda_function.py << 'EOF'
"""
AWS Lambda Function - Modernized Serverless Application
This Lambda function wraps the legacy business logic and provides
a serverless API interface using API Gateway proxy integration.
"""

import json
import boto3
import os
from datetime import datetime
from legacy import process_message, validate_input, get_greeting_prefix

# Initialize AWS SDK clients
TABLE_NAME = os.environ.get("TABLE_NAME", "LegacyModernizedTable")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    """
    Main Lambda handler function.
    
    Args:
        event: API Gateway proxy event containing request details
        context: Lambda execution context
        
    Returns:
        API Gateway proxy response with statusCode and body
    """
    try:
        # Log incoming request for debugging
        print(f"Received event: {json.dumps(event)}")
        
        # Extract query parameters from API Gateway event
        query_params = event.get("queryStringParameters", {})
        
        # Handle case when query_params is None
        if query_params is None:
            query_params = {}
        
        # Get name parameter with default
        name = query_params.get("name", "Guest")
        
        # Validate input using legacy validation logic
        if not validate_input(name):
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "error": "Invalid input",
                    "message": "Name must be between 1 and 100 characters"
                })
            }
        
        # Get greeting prefix from legacy logic
        prefix = get_greeting_prefix(name)
        
        # Process message using legacy business logic
        message = process_message(name)
        
        # Get current timestamp
        timestamp = datetime.utcnow().isoformat()
        
        # Store data in DynamoDB
        try:
            table.put_item(
                Item={
                    "pk": name,
                    "message": message,
                    "prefix": prefix,
                    "timestamp": timestamp,
                    "requestId": context.request_id
                }
            )
            print(f"Successfully stored data for: {name}")
        except Exception as db_error:
            print(f"DynamoDB error: {str(db_error)}")
            # Continue execution even if DynamoDB fails
        
        # Return successful response
        response = {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "success": True,
                "response": message,
                "greeting": prefix,
                "name": name,
                "timestamp": timestamp,
                "requestId": context.request_id
            })
        }
        
        return response
        
    except Exception as e:
        # Handle any unexpected errors
        print(f"Error processing request: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "error": "Internal server error",
                "message": str(e)
            })
        }
EOF

echo "✅ Lambda function created: lambda_function.py"

# Create requirements file (if needed for additional dependencies)
cat > requirements.txt << 'EOF'
# boto3 is included in Lambda runtime by default
# Add any additional dependencies here
EOF

echo "✅ Requirements file created: requirements.txt"

# Display created files
echo ""
echo "=== Created Lambda Files ==="
ls -lh "$WORK_DIR"
echo "============================"
echo ""
```

**Expected Output:**
```
Creating serverless Lambda function...
✅ Lambda function created: lambda_function.py
✅ Requirements file created: requirements.txt

=== Created Lambda Files ===
total 12K
-rw-r--r-- 1 user user 1.2K Nov 13 13:00 lambda_function.py
-rw-r--r-- 1 user user  850 Nov 13 13:00 legacy.py
-rw-r--r-- 1 user user   95 Nov 13 13:00 requirements.txt
============================
```

---

# Step 4 – Create DynamoDB Table

```bash
# Create DynamoDB table with pay-per-request billing
echo "Creating DynamoDB table..."

aws dynamodb create-table \
  --table-name "$TABLE_NAME" \
  --attribute-definitions \
    AttributeName=pk,AttributeType=S \
  --key-schema \
    AttributeName=pk,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --tags \
    Key=Purpose,Value=Serverless-Modernization \
    Key=Lab,Value=15E \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ DynamoDB table creation initiated: $TABLE_NAME"

# Wait for table to become active
echo ""
echo "⏳ Waiting for table to become ACTIVE..."

for i in {1..30}; do
  TABLE_STATUS=$(aws dynamodb describe-table \
    --table-name "$TABLE_NAME" \
    --region "$REGION" \
    --query "Table.TableStatus" \
    --output text 2>/dev/null)
  
  echo "[$(date '+%H:%M:%S')] Table status: $TABLE_STATUS"
  
  if [[ "$TABLE_STATUS" == "ACTIVE" ]]; then
    echo ""
    echo "✅ Table is ACTIVE and ready"
    break
  fi
  
  if [[ $i -eq 30 ]]; then
    echo "⚠️  Table creation taking longer than expected"
  fi
  
  sleep 2
done

# Display table details
echo ""
echo "=== DynamoDB Table Details ==="
aws dynamodb describe-table \
  --table-name "$TABLE_NAME" \
  --region "$REGION" \
  --query "Table.[TableName,TableStatus,BillingModeSummary.BillingMode,KeySchema[0].AttributeName]" \
  --output table

echo "=============================="
echo ""
```

**Expected Output:**
```
Creating DynamoDB table...
✅ DynamoDB table creation initiated: LegacyModernizedTable

⏳ Waiting for table to become ACTIVE...
[13:01:00] Table status: CREATING
[13:01:02] Table status: CREATING
[13:01:04] Table status: ACTIVE

✅ Table is ACTIVE and ready

=== DynamoDB Table Details ===
-----------------------------------------------------------
|                   DescribeTable                          |
+---------------------------------------------------------+
|  LegacyModernizedTable                                  |
|  ACTIVE                                                 |
|  PAY_PER_REQUEST                                        |
|  pk                                                     |
+---------------------------------------------------------+
==============================
```

---

# Step 5 – Package Lambda Deployment Package

```bash
# Create deployment package (ZIP file)
echo "Packaging Lambda function..."

# Change to working directory
cd "$WORK_DIR"

# Create ZIP file with all necessary files
zip -q "$ZIP_NAME" \
  lambda_function.py \
  legacy.py

echo "✅ Lambda deployment package created: $ZIP_NAME"

# Display package contents and size
echo ""
echo "=== Deployment Package Contents ==="
unzip -l "$ZIP_NAME"
echo ""
echo "Package size: $(ls -lh $ZIP_NAME | awk '{print $5}')"
echo "==================================="
echo ""
```

**Expected Output:**
```
Packaging Lambda function...
✅ Lambda deployment package created: lambda.zip

=== Deployment Package Contents ===
Archive:  lambda.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
     3245  2025-11-13 13:01   lambda_function.py
      850  2025-11-13 13:00   legacy.py
---------                     -------
     4095                     2 files

Package size: 1.5K
===================================
```

---

# Step 6 – Create IAM Role for Lambda Execution

```bash
# Create IAM role for Lambda function
echo "Creating IAM role for Lambda execution..."

# Create role with trust policy
aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document '{
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
  }' \
  --description "Role for modernized serverless Lambda function" \
  --tags \
    Key=Purpose,Value=Serverless-Modernization \
    Key=Lab,Value=15E \
  --output json > /dev/null

echo "✅ IAM role created: $ROLE_NAME"

# Attach AWS managed policy for Lambda basic execution (CloudWatch Logs)
echo ""
echo "Attaching policies to role..."

aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

echo "  ✓ Attached: AWSLambdaBasicExecutionRole (CloudWatch Logs)"

# Attach AWS managed policy for DynamoDB full access
aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"

echo "  ✓ Attached: AmazonDynamoDBFullAccess"

# Get role ARN for Lambda creation
ROLE_ARN=$(aws iam get-role \
  --role-name "$ROLE_NAME" \
  --query "Role.Arn" \
  --output text)

echo ""
echo "✅ Role ARN: $ROLE_ARN"

# Wait for role to propagate
echo ""
echo "⏳ Waiting for IAM role to propagate (10 seconds)..."
sleep 10
echo "✅ Role propagation complete"

echo ""
echo "=== IAM Role Configuration ==="
echo "Role Name: $ROLE_NAME"
echo "Role ARN: $ROLE_ARN"
echo "Policies:"
echo "  - AWSLambdaBasicExecutionRole"
echo "  - AmazonDynamoDBFullAccess"
echo "=============================="
echo ""
```

**Expected Output:**
```
Creating IAM role for Lambda execution...
✅ IAM role created: lambdaModernizationRole

Attaching policies to role...
  ✓ Attached: AWSLambdaBasicExecutionRole (CloudWatch Logs)
  ✓ Attached: AmazonDynamoDBFullAccess

✅ Role ARN: arn:aws:iam::123456789012:role/lambdaModernizationRole

⏳ Waiting for IAM role to propagate (10 seconds)...
✅ Role propagation complete

=== IAM Role Configuration ===
Role Name: lambdaModernizationRole
Role ARN: arn:aws:iam::123456789012:role/lambdaModernizationRole
Policies:
  - AWSLambdaBasicExecutionRole
  - AmazonDynamoDBFullAccess
==============================
```

---

# Step 7 – Create Lambda Function

```bash
# Create Lambda function from deployment package
echo "Creating Lambda function..."

aws lambda create-function \
  --function-name "$FUNCTION_NAME" \
  --runtime python3.10 \
  --handler lambda_function.lambda_handler \
  --zip-file "fileb://${WORK_DIR}/${ZIP_NAME}" \
  --role "$ROLE_ARN" \
  --environment "Variables={TABLE_NAME=${TABLE_NAME}}" \
  --timeout 10 \
  --memory-size 128 \
  --description "Modernized serverless application - Lab 15.E" \
  --tags \
    Purpose=Serverless-Modernization,Lab=15E \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Lambda function created: $FUNCTION_NAME"

# Wait for function to be active
echo ""
echo "⏳ Waiting for function to be ready..."
sleep 5

# Get function details
FUNCTION_ARN=$(aws lambda get-function \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION" \
  --query "Configuration.FunctionArn" \
  --output text)

echo "✅ Function is ready: $FUNCTION_ARN"

# Display function configuration
echo ""
echo "=== Lambda Function Configuration ==="
aws lambda get-function-configuration \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION" \
  --query "[FunctionName,Runtime,Handler,MemorySize,Timeout,State]" \
  --output table

echo "====================================="
echo ""
```

**Expected Output:**
```
Creating Lambda function...
✅ Lambda function created: legacy-modernized-fn

⏳ Waiting for function to be ready...
✅ Function is ready: arn:aws:lambda:ap-southeast-2:123456789012:function:legacy-modernized-fn

=== Lambda Function Configuration ===
-----------------------------------------------------------------------
|                  GetFunctionConfiguration                            |
+---------------------------------------------------------------------+
|  legacy-modernized-fn                                               |
|  python3.10                                                         |
|  lambda_function.lambda_handler                                     |
|  128                                                                |
|  10                                                                 |
|  Active                                                             |
+---------------------------------------------------------------------+
=====================================
```

---

# Step 8 – Test Lambda Function Directly

```bash
# Test Lambda function before API Gateway integration
echo "Testing Lambda function directly..."

# Create test event payload
cat > /tmp/test-event.json << EOF
{
  "queryStringParameters": {
    "name": "TestUser"
  }
}
EOF

echo "Test payload created"

# Invoke Lambda function
echo ""
echo "Invoking Lambda function..."

aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload file:///tmp/test-event.json \
  --region "$REGION" \
  --cli-binary-format raw-in-base64-out \
  /tmp/lambda-response.json > /dev/null

echo "✅ Lambda invocation successful"

# Display response
echo ""
echo "=== Lambda Response ==="
cat /tmp/lambda-response.json | jq .
echo "======================="

# Verify data was written to DynamoDB
echo ""
echo "Verifying DynamoDB entry..."

aws dynamodb get-item \
  --table-name "$TABLE_NAME" \
  --key '{"pk":{"S":"TestUser"}}' \
  --region "$REGION" \
  --query "Item" \
  --output json | jq .

echo ""
echo "✅ Lambda function test completed successfully"
echo ""
```

**Expected Output:**
```
Testing Lambda function directly...
Test payload created

Invoking Lambda function...
✅ Lambda invocation successful

=== Lambda Response ===
{
  "statusCode": 200,
  "headers": {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*"
  },
  "body": "{\"success\": true, \"response\": \"Hello TestUser, your legacy application has been successfully modernized to serverless!\", \"greeting\": \"Hello\", \"name\": \"TestUser\", \"timestamp\": \"2025-11-13T13:05:00.123456\", \"requestId\": \"abc-123-def\"}"
}
=======================

Verifying DynamoDB entry...
{
  "pk": {
    "S": "TestUser"
  },
  "message": {
    "S": "Hello TestUser, your legacy application has been successfully modernized to serverless!"
  },
  "timestamp": {
    "S": "2025-11-13T13:05:00.123456"
  }
}

✅ Lambda function test completed successfully
```

---

# Step 9 – Create API Gateway REST API

```bash
# Create REST API in API Gateway
echo "Creating API Gateway REST API..."

REST_API_ID=$(aws apigateway create-rest-api \
  --name "$API_NAME" \
  --description "API for modernized serverless application - Lab 15.E" \
  --endpoint-configuration types=REGIONAL \
  --region "$REGION" \
  --query "id" \
  --output text)

echo "✅ REST API created: $REST_API_ID"
echo "API Name: $API_NAME"

# Get root resource ID
echo ""
echo "Getting root resource..."

ROOT_ID=$(aws apigateway get-resources \
  --rest-api-id "$REST_API_ID" \
  --region "$REGION" \
  --query "items[?path=='/'].id" \
  --output text)

echo "✅ Root resource ID: $ROOT_ID"

echo ""
echo "=== API Gateway Configuration ==="
echo "REST API ID: $REST_API_ID"
echo "Root Resource ID: $ROOT_ID"
echo "================================="
echo ""
```

**Expected Output:**
```
Creating API Gateway REST API...
✅ REST API created: abc123xyz789
API Name: LegacyModernizedAPI

Getting root resource...
✅ Root resource ID: def456uvw012

=== API Gateway Configuration ===
REST API ID: abc123xyz789
Root Resource ID: def456uvw012
=================================
```

---

# Step 10 – Create API Resource and Method

```bash
# Create API resource path
echo "Creating API resource: /modernized"

RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id "$REST_API_ID" \
  --parent-id "$ROOT_ID" \
  --path-part "modernized" \
  --region "$REGION" \
  --query "id" \
  --output text)

echo "✅ Resource created: /modernized (ID: $RESOURCE_ID)"

# Create GET method on the resource
echo ""
echo "Creating GET method..."

aws apigateway put-method \
  --rest-api-id "$REST_API_ID" \
  --resource-id "$RESOURCE_ID" \
  --http-method GET \
  --authorization-type NONE \
  --request-parameters \
    "method.request.querystring.name=false" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ GET method created"

# Configure method response
echo ""
echo "Configuring method response..."

aws apigateway put-method-response \
  --rest-api-id "$REST_API_ID" \
  --resource-id "$RESOURCE_ID" \
  --http-method GET \
  --status-code 200 \
  --response-models '{"application/json":"Empty"}' \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Method response configured"

echo ""
echo "=== API Resource Configuration ==="
echo "Resource Path: /modernized"
echo "Resource ID: $RESOURCE_ID"
echo "HTTP Method: GET"
echo "Authorization: NONE"
echo "=================================="
echo ""
```

**Expected Output:**
```
Creating API resource: /modernized
✅ Resource created: /modernized (ID: ghi789jkl012)

Creating GET method...
✅ GET method created

Configuring method response...
✅ Method response configured

=== API Resource Configuration ===
Resource Path: /modernized
Resource ID: ghi789jkl012
HTTP Method: GET
Authorization: NONE
==================================
```

---

# Step 11 – Integrate API Gateway with Lambda

```bash
# Set up Lambda proxy integration
echo "Integrating API Gateway with Lambda..."

# Construct Lambda URI
LAMBDA_URI="arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}/invocations"

echo "Lambda URI: $LAMBDA_URI"

# Create integration
aws apigateway put-integration \
  --rest-api-id "$REST_API_ID" \
  --resource-id "$RESOURCE_ID" \
  --http-method GET \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "$LAMBDA_URI" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Lambda proxy integration created"

# Configure integration response
echo ""
echo "Configuring integration response..."

aws apigateway put-integration-response \
  --rest-api-id "$REST_API_ID" \
  --resource-id "$RESOURCE_ID" \
  --http-method GET \
  --status-code 200 \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Integration response configured"

# Add Lambda permission for API Gateway to invoke the function
echo ""
echo "Adding Lambda invoke permission for API Gateway..."

# Construct source ARN for permission
SOURCE_ARN="arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${REST_API_ID}/*/GET/modernized"

# Add permission
aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id "apigateway-invoke-${REST_API_ID}" \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "$SOURCE_ARN" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Lambda permission added"
echo "Source ARN: $SOURCE_ARN"

echo ""
echo "=== API-Lambda Integration ==="
echo "Integration Type: AWS_PROXY"
echo "Lambda Function: $FUNCTION_NAME"
echo "HTTP Method: GET"
echo "Permission: apigateway.amazonaws.com"
echo "=============================="
echo ""
```

**Expected Output:**
```
Integrating API Gateway with Lambda...
Lambda URI: arn:aws:apigateway:ap-southeast-2:lambda:path/2015-03-31/functions/arn:aws:lambda:ap-southeast-2:123456789012:function:legacy-modernized-fn/invocations
✅ Lambda proxy integration created

Configuring integration response...
✅ Integration response configured

Adding Lambda invoke permission for API Gateway...
✅ Lambda permission added
Source ARN: arn:aws:execute-api:ap-southeast-2:123456789012:abc123xyz789/*/GET/modernized

=== API-Lambda Integration ===
Integration Type: AWS_PROXY
Lambda Function: legacy-modernized-fn
HTTP Method: GET
Permission: apigateway.amazonaws.com
==============================
```

---

# Step 12 – Deploy API Gateway to Production Stage

```bash
# Deploy API to production stage
echo "Deploying API to production stage..."

aws apigateway create-deployment \
  --rest-api-id "$REST_API_ID" \
  --stage-name prod \
  --stage-description "Production stage for Lab 15.E" \
  --description "Initial deployment of modernized serverless API" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ API deployed to stage: prod"

# Construct API endpoint URL
API_ENDPOINT="https://${REST_API_ID}.execute-api.${REGION}.amazonaws.com/prod/modernized"

echo ""
echo "========================================="
echo "✅ API Gateway deployment successful!"
echo "========================================="
echo ""
echo "=== API Endpoint Information ==="
echo "Base URL: https://${REST_API_ID}.execute-api.${REGION}.amazonaws.com/prod"
echo "Endpoint: $API_ENDPOINT"
echo ""
echo "Test URLs:"
echo "  curl '$API_ENDPOINT?name=Alice'"
echo "  curl '$API_ENDPOINT?name=Bob'"
echo "  curl '$API_ENDPOINT?name=admin'"
echo "================================"
echo ""
```

**Expected Output:**
```
Deploying API to production stage...
✅ API deployed to stage: prod

=========================================
✅ API Gateway deployment successful!
=========================================

=== API Endpoint Information ===
Base URL: https://abc123xyz789.execute-api.ap-southeast-2.amazonaws.com/prod
Endpoint: https://abc123xyz789.execute-api.ap-southeast-2.amazonaws.com/prod/modernized

Test URLs:
  curl 'https://abc123xyz789.execute-api.ap-southeast-2.amazonaws.com/prod/modernized?name=Alice'
  curl 'https://abc123xyz789.execute-api.ap-southeast-2.amazonaws.com/prod/modernized?name=Bob'
  curl 'https://abc123xyz789.execute-api.ap-southeast-2.amazonaws.com/prod/modernized?name=admin'
================================
```

---

# Step 13 – Test Serverless API Endpoints

```bash
# Test the deployed serverless API
echo "Testing serverless API endpoints..."
echo ""

# Test 1: Basic request
echo "Test 1: Basic API request"
echo "Command: curl -s '$API_ENDPOINT?name=Georges'"
echo ""

RESPONSE_1=$(curl -s "${API_ENDPOINT}?name=Georges")
echo "Response:"
echo "$RESPONSE_1" | jq . 2>/dev/null || echo "$RESPONSE_1"

echo ""
echo "---"
echo ""

# Test 2: Different user
echo "Test 2: Request with different user"
echo "Command: curl -s '$API_ENDPOINT?name=Alice'"
echo ""

RESPONSE_2=$(curl -s "${API_ENDPOINT}?name=Alice")
echo "Response:"
echo "$RESPONSE_2" | jq . 2>/dev/null || echo "$RESPONSE_2"

echo ""
echo "---"
echo ""

# Test 3: Admin user (special greeting)
echo "Test 3: Admin user request"
echo "Command: curl -s '$API_ENDPOINT?name=admin'"
echo ""

RESPONSE_3=$(curl -s "${API_ENDPOINT}?name=admin")
echo "Response:"
echo "$RESPONSE_3" | jq . 2>/dev/null || echo "$RESPONSE_3"

echo ""
echo "---"
echo ""

# Test 4: No name parameter (default)
echo "Test 4: Request without name parameter"
echo "Command: curl -s '$API_ENDPOINT'"
echo ""

RESPONSE_4=$(curl -s "$API_ENDPOINT")
echo "Response:"
echo "$RESPONSE_4" | jq . 2>/dev/null || echo "$RESPONSE_4"

echo ""
echo "---"
echo ""

# Check HTTP status code
echo "Test 5: Verify HTTP status code"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${API_ENDPOINT}?name=StatusCheck")
echo "HTTP Status Code: $HTTP_STATUS"

if [[ "$HTTP_STATUS" == "200" ]]; then
  echo "✅ API returning successful status code"
else
  echo "⚠️  Unexpected status code: $HTTP_STATUS"
fi

echo ""
echo "========================================="
echo "✅ API testing completed successfully!"
echo "========================================="
echo ""
```

**Expected Output:**
```
Testing serverless API endpoints...

Test 1: Basic API request
Command: curl -s 'https://abc123xyz789.execute-api.ap-southeast-2.amazonaws.com/prod/modernized?name=Georges'

Response:
{
  "success": true,
  "response": "Hello Georges, your legacy application has been successfully modernized to serverless!",
  "greeting": "Hello",
  "name": "Georges",
  "timestamp": "2025-11-13T13:10:30.123456",
  "requestId": "abc-def-123"
}

---

Test 2: Request with different user
Command: curl -s 'https://abc123xyz789.execute-api.ap-southeast-2.amazonaws.com/prod/modernized?name=Alice'

Response:
{
  "success": true,
  "response": "Hello Alice, your legacy application has been successfully modernized to serverless!",
  "greeting": "Hello",
  "name": "Alice",
  "timestamp": "2025-11-13T13:10:32.234567",
  "requestId": "def-ghi-456"
}

---

Test 3: Admin user request
Command: curl -s 'https://abc123xyz789.execute-api.ap-southeast-2.amazonaws.com/prod/modernized?name=admin'

Response:
{
  "success": true,
  "response": "Hello admin, your legacy application has been successfully modernized to serverless!",
  "greeting": "Welcome back, Administrator",
  "name": "admin",
  "timestamp": "2025-11-13T13:10:34.345678",
  "requestId": "ghi-jkl-789"
}

---

Test 4: Request without name parameter
Command: curl -s 'https://abc123xyz789.execute-api.ap-southeast-2.amazonaws.com/prod/modernized'

Response:
{
  "success": true,
  "response": "Hello Guest, your legacy application has been successfully modernized to serverless!",
  "greeting": "Hello",
  "name": "Guest",
  "timestamp": "2025-11-13T13:10:36.456789",
  "requestId": "jkl-mno-012"
}

---

Test 5: Verify HTTP status code
HTTP Status Code: 200
✅ API returning successful status code

=========================================
✅ API testing completed successfully!
=========================================
```

---

# Step 14 – Verify DynamoDB Data Persistence

```bash
# Verify data was stored in DynamoDB
echo "Verifying data persistence in DynamoDB..."
echo ""

# Scan table to get all items
echo "=== All Items in DynamoDB Table ==="

aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --region "$REGION" \
  --query "Items" \
  --output json | jq .

echo "===================================="
echo ""

# Get specific item
echo "Retrieving specific item (Georges)..."

aws dynamodb get-item \
  --table-name "$TABLE_NAME" \
  --key '{"pk":{"S":"Georges"}}' \
  --region "$REGION" \
  --output json | jq .

echo ""
echo "✅ DynamoDB data verification complete"
echo ""

# Display item count
ITEM_COUNT=$(aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --region "$REGION" \
  --select COUNT \
  --query "Count" \
  --output text)

echo "Total items in table: $ITEM_COUNT"
echo ""
```

**Expected Output:**
```
Verifying data persistence in DynamoDB...

=== All Items in DynamoDB Table ===
[
  {
    "pk": {
      "S": "Georges"
    },
    "message": {
      "S": "Hello Georges, your legacy application has been successfully modernized to serverless!"
    },
    "prefix": {
      "S": "Hello"
    },
    "timestamp": {
      "S": "2025-11-13T13:10:30.123456"
    },
    "requestId": {
      "S": "abc-def-123"
    }
  },
  {
    "pk": {
      "S": "Alice"
    },
    "message": {
      "S": "Hello Alice, your legacy application has been successfully modernized to serverless!"
    },
    ...
  }
]
====================================

Retrieving specific item (Georges)...
{
  "Item": {
    "pk": {
      "S": "Georges"
    },
    "message": {
      "S": "Hello Georges, your legacy application has been successfully modernized to serverless!"
    },
    "prefix": {
      "S": "Hello"
    },
    "timestamp": {
      "S": "2025-11-13T13:10:30.123456"
    }
  }
}

✅ DynamoDB data verification complete

Total items in table: 5
```

---

# Step 15 – View Lambda Execution Logs

```bash
# View CloudWatch Logs for Lambda function
echo "Viewing Lambda execution logs..."
echo ""

# Get log group name
LOG_GROUP="/aws/lambda/${FUNCTION_NAME}"

echo "Log Group: $LOG_GROUP"
echo ""

# Get recent log streams
echo "=== Recent Log Streams ==="
aws logs describe-log-streams \
  --log-group-name "$LOG_GROUP" \
  --order-by LastEventTime \
  --descending \
  --max-items 3 \
  --region "$REGION" \
  --query "logStreams[*].[logStreamName,lastEventTime]" \
  --output table

echo "=========================="
echo ""

# Tail recent logs
echo "=== Recent Lambda Logs (last 20 lines) ==="
aws logs tail "$LOG_GROUP" \
  --since 10m \
  --format short \
  --region "$REGION" 2>/dev/null | tail -20 || \
  echo "Note: Install AWS CLI v2 for 'logs tail' command"

echo "==========================================="
echo ""

# Get Lambda metrics
echo "=== Lambda Function Metrics ==="
echo "Getting invocation count..."

INVOCATIONS=$(aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value="$FUNCTION_NAME" \
  --statistics Sum \
  --start-time "$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 600 \
  --region "$REGION" \
  --query "Datapoints[0].Sum" \
  --output text 2>/dev/null)

echo "Total invocations (last 10 min): ${INVOCATIONS:-N/A}"
echo "==============================="
echo ""
```

**Expected Output:**
```
Viewing Lambda execution logs...

Log Group: /aws/lambda/legacy-modernized-fn

=== Recent Log Streams ===
-----------------------------------------------------------------------------------
|                          DescribeLogStreams                                      |
+---------------------------------------------------------------------------------+
|  2025/11/13/[$LATEST]abc123def456  |  1731502230000                            |
|  2025/11/13/[$LATEST]def456ghi789  |  1731502150000                            |
+---------------------------------------------------------------------------------+
==========================

=== Recent Lambda Logs (last 20 lines) ===
2025-11-13T13:10:30.123Z START RequestId: abc-def-123 Version: $LATEST
2025-11-13T13:10:30.234Z Received event: {"queryStringParameters": {"name": "Georges"}}
2025-11-13T13:10:30.345Z Successfully stored data for: Georges
2025-11-13T13:10:30.456Z END RequestId: abc-def-123
2025-11-13T13:10:30.567Z REPORT RequestId: abc-def-123 Duration: 234.56 ms Billed Duration: 235 ms Memory Size: 128 MB Max Memory Used: 65 MB
===========================================

=== Lambda Function Metrics ===
Getting invocation count...
Total invocations (last 10 min): 6
===============================
```

---

# Step 16 – Cleanup Resources

```bash
# Comprehensive cleanup of all resources
echo "Starting cleanup process..."
echo ""

# Delete API Gateway
echo "Deleting API Gateway..."
aws apigateway delete-rest-api \
  --rest-api-id "$REST_API_ID" \
  --region "$REGION"

echo "✅ API Gateway deleted: $REST_API_ID"

# Delete Lambda function
echo ""
echo "Deleting Lambda function..."
aws lambda delete-function \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION"

echo "✅ Lambda function deleted: $FUNCTION_NAME"

# Delete DynamoDB table
echo ""
echo "Deleting DynamoDB table..."
aws dynamodb delete-table \
  --table-name "$TABLE_NAME" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ DynamoDB table deletion initiated: $TABLE_NAME"

# Wait briefly for table deletion to start
sleep 5

# Detach policies from IAM role
echo ""
echo "Detaching IAM policies..."

aws iam detach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

echo "  ✓ Detached: AWSLambdaBasicExecutionRole"

aws iam detach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"

echo "  ✓ Detached: AmazonDynamoDBFullAccess"

# Delete IAM role
echo ""
echo "Deleting IAM role..."
aws iam delete-role \
  --role-name "$ROLE_NAME"

echo "✅ IAM role deleted: $ROLE_NAME"

# Delete CloudWatch log group
echo ""
echo "Deleting CloudWatch log group..."
aws logs delete-log-group \
  --log-group-name "/aws/lambda/${FUNCTION_NAME}" \
  --region "$REGION" 2>/dev/null && \
  echo "✅ Log group deleted" || \
  echo "ℹ️  Log group not found or already deleted"

# Clean up local files
echo ""
echo "Cleaning up local files..."
rm -rf "$WORK_DIR"
rm -f /tmp/test-event.json /tmp/lambda-response.json
echo "✅ Local files deleted"

echo ""
echo "========================================="
echo "✅ Cleanup completed successfully!"
echo "========================================="
echo ""
echo "All resources have been deleted:"
echo "  ✓ API Gateway REST API"
echo "  ✓ Lambda function"
echo "  ✓ DynamoDB table"
echo "  ✓ IAM role and policies"
echo "  ✓ CloudWatch log group"
echo "  ✓ Local deployment files"
echo ""
```

**Expected Output:**
```
Starting cleanup process...

Deleting API Gateway...
✅ API Gateway deleted: abc123xyz789

Deleting Lambda function...
✅ Lambda function deleted: legacy-modernized-fn

Deleting DynamoDB table...
✅ DynamoDB table deletion initiated: LegacyModernizedTable

Detaching IAM policies...
  ✓ Detached: AWSLambdaBasicExecutionRole
  ✓ Detached: AmazonDynamoDBFullAccess

Deleting IAM role...
✅ IAM role deleted: lambdaModernizationRole

Deleting CloudWatch log group...
✅ Log group deleted

Cleaning up local files...
✅ Local files deleted

=========================================
✅ Cleanup completed successfully!
=========================================

All resources have been deleted:
  ✓ API Gateway REST API
  ✓ Lambda function
  ✓ DynamoDB table
  ✓ IAM role and policies
  ✓ CloudWatch log group
  ✓ Local deployment files
```

---

## Best Practices

### Serverless Application Design
- **Stateless functions**: Design Lambda functions to be stateless
- **Single responsibility**: Each function should have one clear purpose
- **Idempotency**: Functions should produce same result for same input
- **Error handling**: Implement comprehensive error handling and logging
- **Timeout management**: Set appropriate timeouts based on function complexity

### Lambda Optimization
- **Cold start reduction**: Use provisioned concurrency for latency-sensitive apps
- **Memory allocation**: Right-size memory (CPU scales with memory)
- **Package size**: Minimize deployment package size for faster cold starts
- **Lambda layers**: Use layers for shared dependencies
- **Environment variables**: Use for configuration, not secrets

### API Gateway Best Practices
- **Request validation**: Validate requests at API Gateway level
- **Throttling**: Set throttling limits to protect backend
- **Caching**: Enable caching for GET requests
- **Usage plans**: Implement usage plans and API keys for access control
- **CORS**: Configure CORS properly for web applications

### DynamoDB Optimization
- **Primary key design**: Choose partition keys that distribute data evenly
- **On-demand vs provisioned**: Use on-demand for unpredictable workloads
- **Indexes**: Create GSIs for alternative query patterns
- **Item size**: Keep items under 400 KB
- **Batch operations**: Use batch operations for better throughput

### Security Best Practices
- **Least privilege**: Grant minimal IAM permissions required
- **Secrets management**: Use AWS Secrets Manager or Parameter Store
- **API authentication**: Implement Cognito or custom authorizers
- **Encryption**: Enable encryption at rest and in transit
- **VPC integration**: Use VPC endpoints for private APIs

### Cost Optimization
- **Function duration**: Optimize code to reduce execution time
- **Memory allocation**: Find optimal memory for cost/performance balance
- **DynamoDB billing**: Use on-demand for variable workloads
- **API Gateway caching**: Reduce Lambda invocations with caching
- **CloudWatch logs**: Set log retention periods appropriately

### Monitoring & Debugging
- **CloudWatch metrics**: Monitor invocations, errors, duration, throttles
- **X-Ray tracing**: Enable AWS X-Ray for distributed tracing
- **CloudWatch Logs Insights**: Query logs for debugging
- **Alarms**: Set CloudWatch alarms for errors and throttling
- **Dead letter queues**: Configure DLQs for failed invocations

---

## Troubleshooting

### Issue: Lambda Returns 500 Error
**Cause**: Function code errors or timeout  
**Solution**:
```bash
# View Lambda logs
aws logs tail /aws/lambda/$FUNCTION_NAME --follow

# Check function configuration
aws lambda get-function-configuration --function-name $FUNCTION_NAME

# Test function directly
aws lambda invoke \
  --function-name $FUNCTION_NAME \
  --payload '{"queryStringParameters":{"name":"test"}}' \
  --cli-binary-format raw-in-base64-out \
  response.json
cat response.json
```

### Issue: API Gateway 403 Forbidden
**Cause**: Missing Lambda invoke permission  
**Solution**:
```bash
# Check Lambda permissions
aws lambda get-policy --function-name $FUNCTION_NAME

# Add permission
aws lambda add-permission \
  --function-name $FUNCTION_NAME \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$REGION:$ACCOUNT_ID:$REST_API_ID/*/GET/modernized"
```

### Issue: DynamoDB Item Not Written
**Cause**: IAM role missing DynamoDB permissions  
**Solution**:
```bash
# Check role policies
aws iam list-attached-role-policies --role-name $ROLE_NAME

# Verify table exists
aws dynamodb describe-table --table-name $TABLE_NAME

# Check Lambda environment variables
aws lambda get-function-configuration \
  --function-name $FUNCTION_NAME \
  --query 'Environment.Variables'
```

### Issue: Lambda Cold Start Latency
**Cause**: Function initialization delay  
**Solution**:
```bash
# Enable provisioned concurrency
aws lambda put-provisioned-concurrency-config \
  --function-name $FUNCTION_NAME \
  --provisioned-concurrent-executions 1 \
  --qualifier '$LATEST'

# Or optimize package size
pip install --target ./package package-name
cd package && zip -r ../function.zip . && cd ..
zip -g function.zip lambda_function.py
```

### Issue: API Gateway Timeout
**Cause**: Lambda execution exceeds 30 seconds (API Gateway limit)  
**Solution**:
```bash
# Check Lambda timeout setting
aws lambda get-function-configuration \
  --function-name $FUNCTION_NAME \
  --query 'Timeout'

# Note: API Gateway has hard limit of 30 seconds
# For longer processing, use asynchronous invocation or Step Functions
```

---

## Additional Resources

### AWS Documentation
- [AWS Lambda Developer Guide](https://docs.aws.amazon.com/lambda/)
- [Amazon API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
- [Amazon DynamoDB Developer Guide](https://docs.aws.amazon.com/dynamodb/)
- [Serverless Application Model (SAM)](https://docs.aws.amazon.com/serverless-application-model/)

### Modernization Strategies
- **Rehost**: Lift and shift to cloud (containers)
- **Replatform**: Optimize during migration (managed services)
- **Refactor**: Redesign for serverless (this lab)
- **Repurchase**: Move to SaaS
- **Retire**: Decommission unused applications
- **Retain**: Keep on-premises temporarily

### Related AWS Services
- **AWS Step Functions**: Orchestrate multiple Lambda functions
- **Amazon EventBridge**: Event-driven serverless applications
- **AWS AppSync**: GraphQL APIs with serverless backend
- **Amazon Cognito**: User authentication and authorization
- **AWS SAM/CDK**: Infrastructure as code for serverless apps

### Use Cases for Serverless
- **Web APIs**: RESTful APIs and microservices
- **Data processing**: ETL, real-time stream processing
- **Mobile backends**: Scalable mobile app backends
- **Chatbots**: Conversational interfaces
- **Scheduled tasks**: Cron jobs and batch processing
- **Event-driven workflows**: Respond to S3, DynamoDB events

---

## Key Takeaways

1. **Serverless Benefits**: No server management, automatic scaling, pay-per-use
2. **Lambda Best Practices**: Stateless, single-purpose, optimized functions
3. **API Gateway Integration**: Proxy integration simplifies request/response handling
4. **DynamoDB NoSQL**: Fast, flexible data storage for serverless applications
5. **IAM Security**: Least privilege access with managed policies
6. **Monitoring**: CloudWatch provides comprehensive observability
7. **Cost Efficiency**: Pay only for actual usage, not idle time
8. **Rapid Development**: Focus on code, not infrastructure management

---

## Summary

In this lab, you successfully:
- ✅ Analyzed and extracted business logic from legacy applications
- ✅ Refactored monolithic code into serverless Lambda functions
- ✅ Created DynamoDB table with pay-per-request billing
- ✅ Deployed Lambda functions with proper IAM configuration
- ✅ Built REST API using Amazon API Gateway
- ✅ Integrated API Gateway with Lambda using proxy integration
- ✅ Tested serverless API endpoints with multiple requests
- ✅ Verified data persistence in DynamoDB
- ✅ Monitored Lambda execution with CloudWatch Logs
- ✅ Performed comprehensive resource cleanup

**Modernizing to serverless architecture** provides significant operational benefits including elimination of server management, automatic scaling, improved availability, and cost optimization through pay-per-use pricing. This approach enables organizations to focus on business logic rather than infrastructure maintenance.

---

## End of Lab 15.E

**Congratulations!** You have completed Session 15 - Migration & Modernization

---
