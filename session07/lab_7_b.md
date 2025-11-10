# Lab 7.B: Advanced Lambda Patterns and Serverless Applications

## Overview
This lab explores advanced Lambda patterns including function orchestration with Step Functions, serverless applications with SAM, Lambda@Edge for CloudFront, and building complete serverless APIs. You'll learn production-ready patterns for building complex serverless architectures.

## Objectives
- Build serverless applications with SAM (Serverless Application Model)
- Orchestrate Lambda functions with AWS Step Functions
- Implement Lambda@Edge for CloudFront
- Create serverless REST APIs with Lambda and API Gateway
- Use Lambda Destinations for async invocation handling
- Implement function versioning and aliases
- Configure provisioned concurrency for consistent performance
- Build event-driven workflows

## Requirements
- Completed Lab 7.A or equivalent Lambda knowledge
- AWS SAM CLI installed
- Understanding of state machines and workflows
- Docker installed (for SAM local testing)
- Node.js or Python development environment

## Steps

### Step 1: Install and Configure AWS SAM CLI
1. Install SAM CLI:
   ```bash
   # macOS
   brew install aws-sam-cli
   
   # Linux
   pip install aws-sam-cli
   
   # Verify installation
   sam --version
   ```

2. Initialize SAM project:
   ```bash
   sam init
   # Choose: AWS Quick Start Templates
   # Runtime: Python 3.12
   # Project name: serverless-app
   # Template: Hello World Example
   ```

3. Explore project structure:
   ```bash
   cd serverless-app
   ls -la
   # template.yaml (SAM template)
   # hello_world/ (function code)
   # events/ (test events)
   ```

### Step 2: Build and Deploy SAM Application
1. Review `template.yaml`:
   ```yaml
   AWSTemplateFormatVersion: '2010-09-09'
   Transform: AWS::Serverless-2016-10-31
   
   Resources:
     HelloWorldFunction:
       Type: AWS::Serverless::Function
       Properties:
         CodeUri: hello_world/
         Handler: app.lambda_handler
         Runtime: python3.12
         Events:
           HelloWorld:
             Type: Api
             Properties:
               Path: /hello
               Method: get
   ```

2. Build the application:
   ```bash
   sam build
   ```

3. Test locally:
   ```bash
   sam local invoke HelloWorldFunction -e events/event.json
   
   # Start local API
   sam local start-api
   # Test: curl http://localhost:3000/hello
   ```

4. Deploy to AWS:
   ```bash
   sam deploy --guided
   # Stack name: serverless-app-stack
   # Region: your-region
   # Confirm changes: Y
   # Allow SAM CLI IAM role creation: Y
   # Save arguments to config: Y
   ```

5. Test deployed API:
   ```bash
   # Get API endpoint from outputs
   curl https://your-api-id.execute-api.region.amazonaws.com/Prod/hello
   ```

### Step 3: Create Multi-Function Serverless API
1. Add more functions to `template.yaml`:
   ```yaml
   Resources:
     UsersFunction:
       Type: AWS::Serverless::Function
       Properties:
         CodeUri: users/
         Handler: app.lambda_handler
         Runtime: python3.12
         Environment:
           Variables:
             TABLE_NAME: !Ref UsersTable
         Policies:
           - DynamoDBCrudPolicy:
               TableName: !Ref UsersTable
         Events:
           GetUsers:
             Type: Api
             Properties:
               Path: /users
               Method: get
           CreateUser:
             Type: Api
             Properties:
               Path: /users
               Method: post
           GetUser:
             Type: Api
             Properties:
               Path: /users/{id}
               Method: get
     
     UsersTable:
       Type: AWS::DynamoDB::Table
       Properties:
         AttributeDefinitions:
           - AttributeName: userId
             AttributeType: S
         KeySchema:
           - AttributeName: userId
             KeyType: HASH
         BillingMode: PAY_PER_REQUEST
   ```

2. Create users function:
   ```python
   # users/app.py
   import json
   import boto3
   import os
   from uuid import uuid4
   
   dynamodb = boto3.resource('dynamodb')
   table = dynamodb.Table(os.environ['TABLE_NAME'])
   
   def lambda_handler(event, context):
       http_method = event['httpMethod']
       
       if http_method == 'GET':
           if 'pathParameters' in event and event['pathParameters']:
               # Get single user
               user_id = event['pathParameters']['id']
               response = table.get_item(Key={'userId': user_id})
               item = response.get('Item', {})
               return {
                   'statusCode': 200 if item else 404,
                   'body': json.dumps(item)
               }
           else:
               # Get all users
               response = table.scan()
               return {
                   'statusCode': 200,
                   'body': json.dumps(response['Items'])
               }
       
       elif http_method == 'POST':
           # Create user
           body = json.loads(event['body'])
           user_id = str(uuid4())
           item = {
               'userId': user_id,
               'username': body['username'],
               'email': body['email']
           }
           table.put_item(Item=item)
           return {
               'statusCode': 201,
               'body': json.dumps(item)
           }
   ```

3. Deploy updated application:
   ```bash
   sam build && sam deploy
   ```

### Step 4: Create Step Functions State Machine
1. Add Step Functions to SAM template:
   ```yaml
   OrderProcessingStateMachine:
     Type: AWS::Serverless::StateMachine
     Properties:
       DefinitionUri: statemachine/order_processing.asl.json
       Role: !GetAtt StepFunctionsRole.Arn
       Events:
         ApiEvent:
           Type: Api
           Properties:
             Path: /orders
             Method: post
   
   ValidateOrderFunction:
     Type: AWS::Serverless::Function
     Properties:
       CodeUri: functions/validate_order/
       Handler: app.lambda_handler
       Runtime: python3.12
   
   ProcessPaymentFunction:
     Type: AWS::Serverless::Function
     Properties:
       CodeUri: functions/process_payment/
       Handler: app.lambda_handler
       Runtime: python3.12
   
   FulfillOrderFunction:
     Type: AWS::Serverless::Function
     Properties:
       CodeUri: functions/fulfill_order/
       Handler: app.lambda_handler
       Runtime: python3.12
   ```

2. Create state machine definition:
   ```json
   {
     "Comment": "Order Processing Workflow",
     "StartAt": "ValidateOrder",
     "States": {
       "ValidateOrder": {
         "Type": "Task",
         "Resource": "${ValidateOrderFunctionArn}",
         "Next": "ProcessPayment",
         "Catch": [{
           "ErrorEquals": ["ValidationError"],
           "Next": "OrderFailed"
         }]
       },
       "ProcessPayment": {
         "Type": "Task",
         "Resource": "${ProcessPaymentFunctionArn}",
         "Next": "FulfillOrder",
         "Retry": [{
           "ErrorEquals": ["PaymentError"],
           "IntervalSeconds": 2,
           "MaxAttempts": 3,
           "BackoffRate": 2
         }],
         "Catch": [{
           "ErrorEquals": ["States.ALL"],
           "Next": "PaymentFailed"
         }]
       },
       "FulfillOrder": {
         "Type": "Task",
         "Resource": "${FulfillOrderFunctionArn}",
         "End": true
       },
       "PaymentFailed": {
         "Type": "Fail",
         "Error": "PaymentFailed",
         "Cause": "Payment processing failed after retries"
       },
       "OrderFailed": {
         "Type": "Fail",
         "Error": "OrderValidationFailed",
         "Cause": "Order validation failed"
       }
     }
   }
   ```

3. Implement Lambda functions for each step
4. Deploy and test the workflow

### Step 5: Implement Function Versions and Aliases
1. Publish function version:
   ```bash
   aws lambda publish-version \
     --function-name HelloWorldFunction \
     --description "Production release v1.0"
   ```

2. Create alias for version:
   ```bash
   # Create 'prod' alias pointing to version 1
   aws lambda create-alias \
     --function-name HelloWorldFunction \
     --name prod \
     --function-version 1
   
   # Create 'dev' alias pointing to $LATEST
   aws lambda create-alias \
     --function-name HelloWorldFunction \
     --name dev \
     --function-version \$LATEST
   ```

3. Update alias to new version (deployment):
   ```bash
   # Publish new version
   aws lambda publish-version \
     --function-name HelloWorldFunction \
     --description "Production release v1.1"
   
   # Update prod alias to version 2
   aws lambda update-alias \
     --function-name HelloWorldFunction \
     --name prod \
     --function-version 2
   ```

4. Invoke specific alias:
   ```bash
   aws lambda invoke \
     --function-name HelloWorldFunction:prod \
     output.json
   ```

### Step 6: Configure Provisioned Concurrency
1. Set provisioned concurrency for alias:
   ```bash
   aws lambda put-provisioned-concurrency-config \
     --function-name HelloWorldFunction \
     --qualifier prod \
     --provisioned-concurrent-executions 5
   ```

2. Monitor provisioned concurrency metrics:
   - CloudWatch → Lambda → Metrics
   - ProvisionedConcurrencyInvocations
   - ProvisionedConcurrencyUtilization

3. Configure auto-scaling:
   ```bash
   aws application-autoscaling register-scalable-target \
     --service-namespace lambda \
     --resource-id function:HelloWorldFunction:prod \
     --scalable-dimension lambda:function:ProvisionedConcurrentExecutions \
     --min-capacity 1 \
     --max-capacity 10
   ```

### Step 7: Implement Lambda Destinations
1. Create Lambda function with destinations:
   ```python
   # async_processor.py
   import json
   import random
   
   def lambda_handler(event, context):
       # Simulate processing
       if random.random() < 0.3:
           raise Exception("Processing failed!")
       
       result = {
           'status': 'success',
           'data': event
       }
       return result
   ```

2. Configure destinations:
   ```bash
   # Create SNS topics for success/failure
   aws sns create-topic --name lambda-success
   aws sns create-topic --name lambda-failure
   
   # Configure destinations
   aws lambda put-function-event-invoke-config \
     --function-name async_processor \
     --destination-config '{
       "OnSuccess": {
         "Destination": "arn:aws:sns:region:account:lambda-success"
       },
       "OnFailure": {
         "Destination": "arn:aws:sns:region:account:lambda-failure"
       }
     }'
   ```

3. Test destinations:
   ```bash
   aws lambda invoke \
     --function-name async_processor \
     --invocation-type Event \
     --payload '{"test": "data"}' \
     response.json
   ```

### Step 8: Create Lambda@Edge Function
1. Create Lambda function for CloudFront:
   ```python
   # viewer_request.py
   def lambda_handler(event, context):
       request = event['Records'][0]['cf']['request']
       headers = request['headers']
       
       # Add security headers
       headers['strict-transport-security'] = [{
           'key': 'Strict-Transport-Security',
           'value': 'max-age=63072000; includeSubdomains; preload'
       }]
       
       # Redirect www to non-www
       host = headers.get('host', [{}])[0].get('value', '')
       if host.startswith('www.'):
           return {
               'status': '301',
               'statusDescription': 'Moved Permanently',
               'headers': {
                   'location': [{
                       'key': 'Location',
                       'value': f'https://{host[4:]}{request["uri"]}'
                   }]
               }
           }
       
       return request
   ```

2. Publish Lambda@Edge function (must be in us-east-1)
3. Associate with CloudFront distribution:
   - CloudFront → Distribution → Behaviors
   - Edit behavior
   - Lambda Function Associations
   - Event type: Viewer Request
   - Function ARN: Lambda@Edge function ARN

### Step 9: Implement Canary Deployments
1. Configure weighted alias routing:
   ```bash
   # 90% to version 1, 10% to version 2
   aws lambda update-alias \
     --function-name HelloWorldFunction \
     --name prod \
     --routing-config '{
       "AdditionalVersionWeights": {
         "2": 0.1
       }
     }'
   ```

2. Monitor canary metrics:
   - Compare error rates between versions
   - Gradually increase traffic to new version

3. Complete rollout:
   ```bash
   # Move 100% traffic to version 2
   aws lambda update-alias \
     --function-name HelloWorldFunction \
     --name prod \
     --function-version 2 \
     --routing-config '{}'
   ```

### Step 10: Monitor and Optimize Performance
1. **Enable X-Ray tracing:**
   - Function configuration → Monitoring tools
   - Enable active tracing
   - View service map and traces

2. **Analyze cold start duration:**
   - CloudWatch Logs Insights query:
     ```
     filter @type = "REPORT"
     | stats avg(@initDuration), max(@initDuration), count(@initDuration) by bin(5m)
     ```

3. **Optimize function package size:**
   - Remove unnecessary dependencies
   - Use Lambda layers for common libraries
   - Minimize deployment package

4. **Use Lambda Power Tuning:**
   - Deploy AWS Lambda Power Tuning tool
   - Run performance tests at different memory settings
   - Find optimal cost/performance ratio

## Validation
- [ ] SAM application built and deployed
- [ ] Multi-function API working correctly
- [ ] Step Functions workflow orchestrating Lambda
- [ ] Function versions and aliases configured
- [ ] Provisioned concurrency set up
- [ ] Lambda Destinations configured
- [ ] Lambda@Edge function deployed
- [ ] Canary deployment tested
- [ ] X-Ray tracing enabled
- [ ] Performance optimized

## Cleanup
1. Delete SAM stack:
   ```bash
   sam delete --stack-name serverless-app-stack
   ```
2. Delete Step Functions state machine
3. Delete Lambda@Edge functions
4. Delete CloudFront distributions
5. Delete SNS topics
6. Delete provisioned concurrency configs
7. Delete function versions and aliases
8. Verify all resources removed

## Summary
In this lab, you mastered advanced Lambda patterns including SAM for infrastructure as code, Step Functions for workflow orchestration, Lambda@Edge for edge computing, and production deployment strategies. These patterns enable building sophisticated, production-grade serverless applications that scale automatically and minimize operational overhead.

**Key Takeaways:**
- SAM simplifies serverless application development and deployment
- Step Functions orchestrate complex workflows with error handling
- Versions and aliases enable safe deployment strategies
- Provisioned concurrency eliminates cold starts for critical functions
- Lambda Destinations handle async success/failure scenarios
- Lambda@Edge runs code at CloudFront edge locations
- Canary deployments minimize risk during updates
- X-Ray provides distributed tracing for debugging
- Optimize memory settings for cost/performance balance
- Infrastructure as code enables repeatable deployments
