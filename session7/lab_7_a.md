# Lab 7.A: AWS Lambda Fundamentals and Serverless Computing

## Overview
This lab introduces AWS Lambda, a serverless compute service that runs code in response to events. You'll learn how to create Lambda functions, configure triggers, manage environment variables, and understand Lambda's execution model. Lambda eliminates server management and scales automatically.

## Objectives
- Create and deploy Lambda functions
- Configure function triggers and event sources
- Manage environment variables and configuration
- Implement error handling and logging
- Understand Lambda execution context and lifecycle
- Configure function timeout and memory
- Use Lambda layers for code reusability
- Monitor function performance with CloudWatch

## Requirements
- AWS account with Lambda permissions
- Basic programming knowledge (Python, Node.js, or Java)
- Understanding of event-driven architecture
- Familiarity with IAM roles
- AWS CLI installed (optional)

## Steps

### Step 1: Create Your First Lambda Function
1. Navigate to Lambda console
2. Click "Create function"
3. Choose "Author from scratch"
4. Configure:
   - Function name: `HelloWorldFunction`
   - Runtime: Python 3.12 (or latest)
   - Architecture: x86_64
   - Permissions: Create new role with basic Lambda permissions
5. Create function

6. Replace the function code:
   ```python
   import json
   
   def lambda_handler(event, context):
       print(f"Event received: {json.dumps(event)}")
       
       name = event.get('name', 'World')
       message = f'Hello, {name}!'
       
       return {
           'statusCode': 200,
           'body': json.dumps({
               'message': message,
               'requestId': context.request_id
           })
       }
   ```

7. Click "Deploy"

### Step 2: Test the Lambda Function
1. Click "Test" button
2. Create test event:
   - Event name: `TestEvent1`
   - Event JSON:
     ```json
     {
       "name": "AWS Lambda"
     }
     ```
3. Save and Test
4. Review execution results:
   - Function logs
   - Execution duration
   - Memory used
   - Return value

### Step 3: Configure Function Settings
1. **Memory and Timeout:**
   - Configuration tab → General configuration
   - Edit:
     - Memory: 256 MB
     - Timeout: 30 seconds
     - Ephemeral storage: 512 MB (default)
   - Save

2. **Environment Variables:**
   - Configuration tab → Environment variables
   - Add:
     - Key: `GREETING_PREFIX`
     - Value: `Welcome`
   - Update function code:
     ```python
     import json
     import os
     
     def lambda_handler(event, context):
         prefix = os.environ.get('GREETING_PREFIX', 'Hello')
         name = event.get('name', 'World')
         message = f'{prefix}, {name}!'
         
         return {
             'statusCode': 200,
             'body': json.dumps({'message': message})
         }
     ```
   - Deploy and test

### Step 4: Create Lambda with S3 Trigger
1. Create new function:
   - Name: `S3ImageProcessor`
   - Runtime: Python 3.12
   - Create function

2. Add S3 trigger:
   - Click "Add trigger"
   - Source: S3
   - Bucket: Select or create new bucket
   - Event type: All object create events
   - Suffix: .jpg (optional, filters for image files)
   - Acknowledge recursive invocation warning
   - Add

3. Implement S3 event handler:
   ```python
   import json
   import boto3
   
   s3 = boto3.client('s3')
   
   def lambda_handler(event, context):
       print(f"Event: {json.dumps(event)}")
       
       # Get bucket and key from event
       for record in event['Records']:
           bucket = record['s3']['bucket']['name']
           key = record['s3']['object']['key']
           size = record['s3']['object']['size']
           
           print(f"File uploaded: {key} in bucket {bucket}, size: {size} bytes")
           
           # Example: Get object metadata
           try:
               response = s3.head_object(Bucket=bucket, Key=key)
               content_type = response.get('ContentType', 'unknown')
               print(f"Content-Type: {content_type}")
           except Exception as e:
               print(f"Error: {str(e)}")
       
       return {
           'statusCode': 200,
           'body': json.dumps('Processed successfully')
       }
   ```

4. Update IAM role permissions:
   - Configuration → Permissions
   - Click on role name
   - Add inline policy:
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Action": [
             "s3:GetObject",
             "s3:HeadObject"
           ],
           "Resource": "arn:aws:s3:::your-bucket-name/*"
         }
       ]
     }
     ```

5. Test by uploading image to S3 bucket
6. Check CloudWatch Logs for function execution

### Step 5: Create Lambda with API Gateway Trigger
1. Create new function:
   - Name: `RestAPIFunction`
   - Runtime: Python 3.12

2. Add API Gateway trigger:
   - Click "Add trigger"
   - Source: API Gateway
   - API type: REST API
   - Security: Open (for testing)
   - Create

3. Implement REST API handler:
   ```python
   import json
   
   def lambda_handler(event, context):
       http_method = event.get('httpMethod')
       path = event.get('path')
       body = event.get('body')
       
       if http_method == 'GET':
           response_body = {
               'message': 'GET request received',
               'path': path
           }
       elif http_method == 'POST':
           request_body = json.loads(body) if body else {}
           response_body = {
               'message': 'POST request received',
               'data': request_body
           }
       else:
           response_body = {
               'message': f'{http_method} not supported'
           }
       
       return {
           'statusCode': 200,
           'headers': {
               'Content-Type': 'application/json',
               'Access-Control-Allow-Origin': '*'
           },
           'body': json.dumps(response_body)
       }
   ```

4. Deploy and test:
   - Copy API Gateway endpoint URL
   - Test with curl or browser:
     ```bash
     curl https://your-api-id.execute-api.region.amazonaws.com/default/RestAPIFunction
     
     curl -X POST https://your-api-id.execute-api.region.amazonaws.com/default/RestAPIFunction \
       -H "Content-Type: application/json" \
       -d '{"name": "test"}'
     ```

### Step 6: Implement Error Handling and Retries
1. Create function with intentional error:
   ```python
   import json
   import random
   
   def lambda_handler(event, context):
       # Simulate random failure (20% chance)
       if random.random() < 0.2:
           raise Exception("Random error occurred!")
       
       return {
           'statusCode': 200,
           'body': json.dumps('Success!')
       }
   ```

2. Configure retry behavior:
   - Configuration → Asynchronous invocation
   - Retry attempts: 2
   - Maximum age of event: 6 hours
   - Configure DLQ (Dead Letter Queue):
     - Create SQS queue: `lambda-dlq`
     - Select DLQ in Lambda configuration

3. Test retry behavior by invoking multiple times

### Step 7: Create and Use Lambda Layer
1. **Create a layer with shared libraries:**
   - Create directory structure:
     ```bash
     mkdir -p python/lib/python3.12/site-packages
     cd python/lib/python3.12/site-packages
     pip install requests -t .
     cd ../../../..
     zip -r requests-layer.zip python
     ```

2. **Create layer in console:**
   - Lambda → Layers → Create layer
   - Name: `RequestsLayer`
   - Upload: `requests-layer.zip`
   - Compatible runtimes: Python 3.12
   - Create

3. **Attach layer to function:**
   - Select function → Configuration → Layers
   - Add layer → Custom layers
   - Select `RequestsLayer`
   - Add

4. **Use layer in function:**
   ```python
   import json
   import requests
   
   def lambda_handler(event, context):
       url = event.get('url', 'https://api.github.com')
       response = requests.get(url)
       
       return {
           'statusCode': 200,
           'body': json.dumps({
               'status': response.status_code,
               'headers': dict(response.headers)
           })
       }
   ```

### Step 8: Monitor with CloudWatch
1. **View CloudWatch Logs:**
   - Monitor tab → View logs in CloudWatch
   - Explore log streams
   - Search and filter logs

2. **Create CloudWatch dashboard:**
   - CloudWatch → Dashboards → Create
   - Add widgets:
     - Invocations
     - Duration
     - Error count
     - Throttles

3. **Set up alarms:**
   - Create alarm for errors:
     - Metric: Lambda → Errors
     - Threshold: Greater than 10
     - Period: 5 minutes
     - Action: SNS notification

### Step 9: Use Lambda with DynamoDB Streams
1. Create DynamoDB table with stream (from Lab 6.A)
2. Create Lambda function:
   - Name: `DynamoDBStreamProcessor`
   - Runtime: Python 3.12

3. Add DynamoDB trigger:
   - Add trigger → DynamoDB
   - Table: Select your table
   - Starting position: Latest
   - Add

4. Implement stream processor:
   ```python
   import json
   
   def lambda_handler(event, context):
       for record in event['Records']:
           event_name = record['eventName']
           
           if event_name == 'INSERT':
               new_image = record['dynamodb']['NewImage']
               print(f"New item: {json.dumps(new_image)}")
           elif event_name == 'MODIFY':
               old_image = record['dynamodb']['OldImage']
               new_image = record['dynamodb']['NewImage']
               print(f"Modified from {old_image} to {new_image}")
           elif event_name == 'REMOVE':
               old_image = record['dynamodb']['OldImage']
               print(f"Deleted item: {json.dumps(old_image)}")
       
       return {'statusCode': 200}
   ```

5. Test by adding/updating items in DynamoDB table

### Step 10: Use Lambda with EventBridge
1. Create Lambda function:
   - Name: `ScheduledTask`

2. Add EventBridge trigger:
   - Add trigger → EventBridge
   - Rule type: Schedule
   - Schedule expression: `rate(5 minutes)` or `cron(0 12 * * ? *)`
   - Create

3. Implement scheduled task:
   ```python
   import json
   from datetime import datetime
   
   def lambda_handler(event, context):
       current_time = datetime.now().isoformat()
       print(f"Scheduled task executed at {current_time}")
       
       # Perform scheduled operations
       # e.g., cleanup, data aggregation, reporting
       
       return {
           'statusCode': 200,
           'body': json.dumps(f'Task completed at {current_time}')
       }
   ```

## Validation
- [ ] Lambda function created and deployed
- [ ] Function tested with test events
- [ ] Environment variables configured and used
- [ ] S3 trigger configured and working
- [ ] API Gateway integrated successfully
- [ ] Error handling and retries implemented
- [ ] Lambda layer created and attached
- [ ] CloudWatch logs and metrics accessible
- [ ] DynamoDB stream trigger working
- [ ] EventBridge schedule configured

## Cleanup
1. Delete all Lambda functions
2. Delete API Gateway APIs
3. Delete S3 buckets (empty first)
4. Delete EventBridge rules
5. Delete CloudWatch log groups
6. Delete Lambda layers
7. Delete SQS queues (DLQ)
8. Delete IAM roles created for Lambda
9. Verify all resources removed

## Summary
In this lab, you learned AWS Lambda fundamentals including function creation, event triggers, error handling, and monitoring. You integrated Lambda with S3, API Gateway, DynamoDB Streams, and EventBridge to build event-driven architectures. Lambda's serverless model enables you to build scalable applications without managing infrastructure.

**Key Takeaways:**
- Lambda automatically scales based on incoming requests
- Pay only for compute time consumed
- Maximum execution time is 15 minutes
- Environment variables enable configuration without code changes
- Layers enable code and dependency reuse
- CloudWatch provides comprehensive logging and monitoring
- Dead Letter Queues capture failed event processing
- Multiple event sources can trigger Lambda functions
- IAM roles control Lambda's AWS service access
- Cold starts may add latency to first invocations
