# Lab 9.C: AWS CDK Python - Serverless API Deployment

## Overview
This lab introduces AWS Cloud Development Kit (CDK) using Python to deploy a serverless API. You'll define infrastructure as code using Python (instead of YAML/JSON), deploy a Lambda function with DynamoDB table and API Gateway HTTP API, and experience the CDK workflow: synth, diff, deploy, and destroy.

**💰 Cost**: FREE TIER (Lambda 1M requests/month, DynamoDB 25 GB)

---

## Objectives
- Install and configure AWS CDK CLI
- Initialize CDK Python project
- Define Lambda function, DynamoDB table, and API Gateway using CDK constructs
- Synthesize CloudFormation template from CDK code
- Preview changes with `cdk diff`
- Deploy infrastructure with `cdk deploy`
- Test serverless API endpoints
- Clean up with `cdk destroy`

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Python 3.8+ installed (`python3 --version`)
- Node.js 14+ installed for CDK CLI (`node --version`)
- IAM permissions for CloudFormation, Lambda, DynamoDB, API Gateway
- Region: ap-southeast-2

---

## Architecture

```
API Gateway HTTP API
  ├── GET  /items         → List all items (Lambda → DynamoDB Scan)
  └── POST /items         → Create item (Lambda → DynamoDB Put)

Lambda Function
  └── Python 3.11 runtime
  └── Environment: TABLE_NAME

DynamoDB Table
  └── items-table (id: String - primary key)
```

---

## Step 1 – Install AWS CDK CLI

```bash
echo ""
echo "Installing AWS CDK CLI globally..."

# Install CDK CLI (requires Node.js)
npm install -g aws-cdk

# Verify installation
cdk --version

echo "✅ AWS CDK CLI installed"
```

---

## Step 2 – Set Variables and Create Project Directory

```bash
# Set region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "REGION=$REGION"

# Create project directory
mkdir -p /tmp/cdk-serverless-api
cd /tmp/cdk-serverless-api

echo "✅ Project directory created: $(pwd)"
```

---

## Step 3 – Bootstrap CDK (One-Time Setup)

```bash
echo ""
echo "Bootstrapping CDK in $REGION (creates S3 bucket for assets)..."

# Bootstrap CDK environment (creates staging resources)
cdk bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/"$REGION"

echo ""
echo "✅ CDK bootstrapped"
echo "This creates: S3 bucket, IAM roles, ECR repos for CDK deployments"
```

---

## Step 4 – Initialize CDK Python App

```bash
echo ""
echo "Initializing CDK Python app..."

# Initialize CDK app with Python template
cdk init app --language python

echo ""
echo "✅ CDK Python app initialized"
echo ""
ls -la
```

---

## Step 5 – Install Python Dependencies

```bash
echo ""
echo "Installing Python dependencies..."

# Activate virtual environment
source .venv/bin/activate

# Install CDK libraries for Lambda, DynamoDB, API Gateway
pip install \
  aws-cdk-lib \
  constructs \
  aws-cdk.aws-lambda-python-alpha

echo ""
echo "✅ Dependencies installed"
```

---

## Step 6 – Create Lambda Function Code

```bash
echo ""
echo "Creating Lambda function code..."

# Create lambda directory
mkdir -p lambda

# Create Lambda handler (DynamoDB operations)
cat > lambda/handler.py <<'EOF'
import json
import os
import boto3
from decimal import Decimal

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table_name = os.environ['TABLE_NAME']
table = dynamodb.Table(table_name)

def decimal_default(obj):
    """Helper to serialize Decimal for JSON"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def handler(event, context):
    """
    API Handler:
    - GET  /items → List all items
    - POST /items → Create new item
    """
    print(f"Event: {json.dumps(event)}")
    
    http_method = event.get('requestContext', {}).get('http', {}).get('method')
    path = event.get('requestContext', {}).get('http', {}).get('path')
    
    try:
        # List all items (GET /items)
        if http_method == 'GET' and path == '/items':
            response = table.scan()
            items = response.get('Items', [])
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'items': items,
                    'count': len(items)
                }, default=decimal_default)
            }
        
        # Create item (POST /items)
        elif http_method == 'POST' and path == '/items':
            body = json.loads(event.get('body', '{}'))
            
            if 'id' not in body or 'name' not in body:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'id and name are required'})
                }
            
            # Put item in DynamoDB
            table.put_item(Item={
                'id': body['id'],
                'name': body['name'],
                'description': body.get('description', ''),
            })
            
            return {
                'statusCode': 201,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Item created', 'item': body})
            }
        
        # Unknown route
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Not found'})
            }
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)})
        }
EOF

echo "✅ Lambda function code created: lambda/handler.py"
```

---

## Step 7 – Define CDK Stack (Infrastructure as Code)

```bash
echo ""
echo "Defining CDK stack with Lambda, DynamoDB, API Gateway..."

# Get main stack file name
STACK_FILE=$(ls */*_stack.py | head -1)
echo "Stack file: $STACK_FILE"

# Create CDK stack (Lambda + DynamoDB + API Gateway)
cat > "$STACK_FILE" <<'EOF'
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct

class CdkServerlessApiStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB Table
        table = dynamodb.Table(
            self, "ItemsTable",
            table_name="cdk-items-table",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # Free tier
            removal_policy=RemovalPolicy.DESTROY,  # Auto-delete on stack destroy
        )

        # Lambda Function
        lambda_function = _lambda.Function(
            self, "ItemsHandler",
            function_name="cdk-items-handler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=_lambda.Code.from_asset("lambda"),
            environment={
                "TABLE_NAME": table.table_name,
            }
        )

        # Grant Lambda permissions to access DynamoDB
        table.grant_read_write_data(lambda_function)

        # HTTP API Gateway
        http_api = apigw.HttpApi(
            self, "ItemsApi",
            api_name="cdk-items-api",
            description="Serverless API built with CDK",
        )

        # Lambda integration
        integration = integrations.HttpLambdaIntegration(
            "ItemsIntegration",
            lambda_function,
        )

        # Add routes
        http_api.add_routes(
            path="/items",
            methods=[apigw.HttpMethod.GET, apigw.HttpMethod.POST],
            integration=integration,
        )

        # Outputs
        CfnOutput(
            self, "ApiUrl",
            value=http_api.url or "",
            description="API Gateway URL",
            export_name="CdkApiUrl"
        )

        CfnOutput(
            self, "TableName",
            value=table.table_name,
            description="DynamoDB Table Name",
            export_name="CdkTableName"
        )

        CfnOutput(
            self, "LambdaFunction",
            value=lambda_function.function_name,
            description="Lambda Function Name",
            export_name="CdkLambdaName"
        )
EOF

echo "✅ CDK stack defined with all resources"
```

---

## Step 8 – Synthesize CloudFormation Template

```bash
echo ""
echo "================================================"
echo "SYNTHESIZING CLOUDFORMATION TEMPLATE FROM CDK"
echo "================================================"
echo ""

# Synthesize CloudFormation template from CDK code
cdk synth

echo ""
echo "✅ CloudFormation template generated"
echo "Template location: cdk.out/*.template.json"
echo ""
echo "CDK code (Python) → CloudFormation template (JSON)"
```

---

## Step 9 – Preview Changes (CDK Diff)

```bash
echo ""
echo "Previewing changes (what will be deployed)..."

# Show differences between current stack and local code
cdk diff

echo ""
echo "✅ CDK diff shows all resources to be created"
```

---

## Step 10 – Deploy Stack

```bash
echo ""
echo "================================================"
echo "DEPLOYING CDK STACK"
echo "================================================"
echo ""

# Deploy stack (creates CloudFormation stack)
cdk deploy --require-approval never

echo ""
echo "✅ CDK stack deployed!"
```

---

## Step 11 – Get Stack Outputs

```bash
echo ""
echo "Getting stack outputs..."

# Get API URL from CloudFormation outputs
API_URL=$(aws cloudformation describe-stacks \
  --stack-name CdkServerlessApiStack \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text)

TABLE_NAME=$(aws cloudformation describe-stacks \
  --stack-name CdkServerlessApiStack \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`TableName`].OutputValue' \
  --output text)

echo ""
echo "API_URL=$API_URL"
echo "TABLE_NAME=$TABLE_NAME"
```

---

## Step 12 – Test API - Create Items (POST)

```bash
echo ""
echo "Testing API - Creating items..."

# Create item 1
curl -X POST "${API_URL}items" \
  -H "Content-Type: application/json" \
  -d '{"id": "item-1", "name": "Laptop", "description": "MacBook Pro 16-inch"}'

echo ""

# Create item 2
curl -X POST "${API_URL}items" \
  -H "Content-Type: application/json" \
  -d '{"id": "item-2", "name": "Mouse", "description": "Wireless ergonomic"}'

echo ""

# Create item 3
curl -X POST "${API_URL}items" \
  -H "Content-Type: application/json" \
  -d '{"id": "item-3", "name": "Keyboard", "description": "Mechanical RGB"}'

echo ""
echo "✅ 3 items created"
```

---

## Step 13 – Test API - List Items (GET)

```bash
echo ""
echo "Testing API - Listing all items..."

curl -s "${API_URL}items" | python3 -m json.tool

echo ""
echo "✅ Items retrieved from DynamoDB"
```

---

## Step 14 – Verify DynamoDB Table

```bash
echo ""
echo "Verifying DynamoDB table..."

# Scan table directly
aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --region "$REGION" \
  --query 'Items[*].{ID:id.S,Name:name.S,Description:description.S}' \
  --output table

echo ""
echo "✅ DynamoDB table contains 3 items"
```

---

## Step 15 – View CloudFormation Stack

```bash
echo ""
echo "Viewing CloudFormation stack created by CDK..."

aws cloudformation describe-stacks \
  --stack-name CdkServerlessApiStack \
  --region "$REGION" \
  --query 'Stacks[0].{Name:StackName,Status:StackStatus,Created:CreationTime}' \
  --output table

echo ""
echo "CDK creates and manages CloudFormation stack automatically"
```

---

## Step 16 – List CDK Stack Resources

```bash
echo ""
echo "Listing all resources in CDK stack..."

cdk ls

echo ""
aws cloudformation list-stack-resources \
  --stack-name CdkServerlessApiStack \
  --region "$REGION" \
  --query 'StackResourceSummaries[*].{Resource:LogicalResourceId,Type:ResourceType,Status:ResourceStatus}' \
  --output table

echo ""
echo "Stack includes: Lambda, DynamoDB, API Gateway, IAM roles"
```

---

## Step 17 – Cleanup

```bash
echo ""
echo "Cleaning up CDK stack..."

# Destroy CDK stack (deletes all resources)
cdk destroy --force

echo ""
echo "✅ CDK stack destroyed"
echo ""
echo "All resources cleaned up (Lambda, DynamoDB, API Gateway, IAM)"
```

---

## Summary

In this lab, you have:
- Installed AWS CDK CLI and initialized Python project
- Bootstrapped CDK environment (S3 bucket for assets)
- Created Lambda function with DynamoDB operations
- Defined infrastructure using CDK Python constructs
- Synthesized CloudFormation template from CDK code
- Previewed changes with `cdk diff`
- Deployed serverless API with `cdk deploy`
- Tested API endpoints (POST /items, GET /items)
- Verified DynamoDB table contents
- Destroyed stack with `cdk destroy`

**Key Takeaways:**
- **CDK = Infrastructure as Code in Real Programming Languages** (Python, TypeScript, Java, etc.)
- **Constructs**: High-level building blocks (Lambda, DynamoDB, API Gateway)
- **Type Safety**: Autocomplete, compile-time errors, refactoring
- **Abstraction**: CDK generates CloudFormation (you don't write YAML/JSON)
- **Workflow**: synth → diff → deploy → destroy

**CDK vs CloudFormation:**
| Feature | CloudFormation | CDK |
|---------|---------------|-----|
| Language | YAML/JSON | Python, TypeScript, Java, etc. |
| Abstraction | Low (define everything) | High (smart defaults) |
| Code Reuse | Limited (nested stacks) | Easy (functions, classes) |
| IDE Support | Basic | Full (autocomplete, linting) |
| Learning Curve | Template syntax | Programming language |

**CDK Advantages:**
- Write infrastructure code in familiar programming language
- Use loops, conditionals, functions for complex logic
- Share constructs as libraries (npm, pip packages)
- Strong typing prevents many errors at compile time
- Better IDE support (autocomplete, refactoring)

---

## Best Practices

**CDK Development:**
- Use virtual environments for Python projects
- Run `cdk synth` frequently to validate code
- Preview changes with `cdk diff` before deploy
- Use constructs from CDK library (don't reinvent)
- Organize stacks by environment (dev, staging, prod)

**Constructs:**
- Use L3 constructs for high-level abstractions
- L2 constructs for more control (what we used)
- L1 constructs for direct CloudFormation access
- Create custom constructs for reusable patterns

**Naming:**
- Use consistent construct IDs (affects resource names)
- Don't hardcode names (let CDK generate unique names)
- Override names only when required (e.g., cross-stack references)

**Testing:**
- Use CDK assertions for unit tests
- Test synthesized templates with snapshot tests
- Integration tests for deployed stacks

**CI/CD:**
- Run `cdk synth` in CI pipeline
- Store synthesized templates as artifacts
- Use `cdk deploy` with approval gates
- Automated tests before deployment

---

## Production Enhancements

1. **Environment Variables**
   ```python
   # Pass environment-specific values
   cdk deploy --context env=prod
   ```

2. **Multiple Environments**
   ```python
   # Create dev and prod stacks
   CdkServerlessApiStack(app, "DevStack", env=dev_env)
   CdkServerlessApiStack(app, "ProdStack", env=prod_env)
   ```

3. **Lambda Layers**
   ```python
   # Share dependencies across functions
   layer = _lambda.LayerVersion(
       self, "SharedLayer",
       code=_lambda.Code.from_asset("layers"),
       compatible_runtimes=[_lambda.Runtime.PYTHON_3_11]
   )
   lambda_function.add_layers(layer)
   ```

4. **Monitoring**
   ```python
   # Add CloudWatch alarms
   lambda_function.metric_errors().create_alarm(
       self, "ErrorAlarm",
       threshold=10,
       evaluation_periods=1
   )
   ```

5. **API Gateway Authentication**
   ```python
   # Add Cognito authorizer
   authorizer = apigw.HttpUserPoolAuthorizer(
       "Authorizer",
       user_pool
   )
   ```

---

## Troubleshooting

**CDK bootstrap fails:**
- Check AWS credentials and permissions
- Verify account/region are correct
- Re-run with `--force` flag if partial bootstrap

**Synth errors:**
- Check Python syntax in stack file
- Verify all imports are correct
- Ensure dependencies installed in virtual environment

**Deploy fails:**
- Check IAM permissions for CloudFormation
- Verify unique resource names (avoid conflicts)
- Review CloudFormation Events for specific errors

**API returns 403:**
- Check Lambda permissions to DynamoDB
- Verify IAM role has correct policies
- Check CloudWatch Logs for Lambda errors

**Cannot destroy stack:**
- Check for retain policies on resources
- Manually empty S3 buckets if any
- Remove termination protection if enabled

---

## CDK Commands Reference

```bash
# Initialize new CDK app
cdk init app --language python

# List all stacks
cdk ls

# Synthesize CloudFormation template
cdk synth

# Show differences
cdk diff

# Deploy stack
cdk deploy

# Deploy without approval prompts
cdk deploy --require-approval never

# Destroy stack
cdk destroy

# View CDK version
cdk --version

# View synthesized template location
cdk synth --output cdk.out
```

---

## Additional Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/v2/guide/home.html)
- [CDK Python Reference](https://docs.aws.amazon.com/cdk/api/v2/python/)
- [CDK Workshop](https://cdkworkshop.com/)
- [CDK Patterns](https://cdkpatterns.com/)
- [Construct Hub](https://constructs.dev/) - Browse reusable constructs
