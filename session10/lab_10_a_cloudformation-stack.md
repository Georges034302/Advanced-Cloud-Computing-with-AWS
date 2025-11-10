# Lab 10.B: Advanced AWS Services and Future-Ready Cloud Engineering

## Overview
This final lab explores advanced AWS services and emerging technologies including Machine Learning with SageMaker, IoT Core, App Runner, Amplify, and modern application patterns. You'll gain exposure to cutting-edge AWS capabilities and learn how to architect future-ready cloud solutions.

## Objectives
- Deploy machine learning models with Amazon SageMaker
- Build IoT applications with AWS IoT Core
- Use AWS App Runner for simplified container deployment
- Create full-stack applications with AWS Amplify
- Implement event-driven architectures with EventBridge
- Use AWS AppSync for GraphQL APIs
- Explore quantum computing with Amazon Braket (overview)
- Understand emerging AWS services and trends

## Requirements
- AWS account with access to advanced services
- Completion of all previous labs
- Python and Node.js development skills
- Understanding of machine learning concepts (helpful)
- Docker knowledge

## Steps

### Step 1: Deploy ML Model with Amazon SageMaker
1. **Prepare training data:**
   ```python
   # prepare_data.py
   import pandas as pd
   import boto3
   from sklearn.model_selection import train_test_split
   
   # Load sample data
   data = pd.read_csv('customer_data.csv')
   
   # Split features and target
   X = data.drop('churn', axis=1)
   y = data['churn']
   
   # Train-test split
   X_train, X_test, y_train, y_test = train_test_split(
       X, y, test_size=0.2, random_state=42
   )
   
   # Upload to S3
   s3 = boto3.client('s3')
   train_data = pd.concat([y_train, X_train], axis=1)
   train_data.to_csv('/tmp/train.csv', index=False, header=False)
   
   s3.upload_file('/tmp/train.csv', 'sagemaker-bucket', 'data/train.csv')
   ```

2. **Create SageMaker training job:**
   ```python
   # train_model.py
   import sagemaker
   from sagemaker import get_execution_role
   from sagemaker.estimator import Estimator
   
   # Setup
   role = get_execution_role()
   session = sagemaker.Session()
   bucket = session.default_bucket()
   
   # Use built-in XGBoost algorithm
   container = sagemaker.image_uris.retrieve('xgboost', 
                                              boto3.Session().region_name, 
                                              '1.5-1')
   
   # Create estimator
   xgb = Estimator(
       container,
       role,
       instance_count=1,
       instance_type='ml.m5.xlarge',
       output_path=f's3://{bucket}/output',
       sagemaker_session=session
   )
   
   # Set hyperparameters
   xgb.set_hyperparameters(
       objective='binary:logistic',
       num_round=100,
       max_depth=5,
       eta=0.2
   )
   
   # Train
   xgb.fit({'train': f's3://{bucket}/data/train.csv'})
   ```

3. **Deploy model endpoint:**
   ```python
   # deploy_model.py
   predictor = xgb.deploy(
       initial_instance_count=1,
       instance_type='ml.t2.medium',
       endpoint_name='churn-prediction-endpoint'
   )
   
   # Make predictions
   import json
   
   test_data = [[35, 50000, 5, 1, 0]]  # Sample customer data
   result = predictor.predict(test_data)
   print(f"Churn probability: {result}")
   ```

### Step 2: Build IoT Application with AWS IoT Core
1. **Create IoT Thing:**
   ```bash
   # Create thing
   aws iot create-thing --thing-name smart-sensor-01
   
   # Create and attach certificate
   aws iot create-keys-and-certificate \
     --set-as-active \
     --certificate-pem-outfile cert.pem \
     --public-key-outfile public.key \
     --private-key-outfile private.key
   
   # Attach policy to certificate
   aws iot attach-policy \
     --policy-name IoTDevicePolicy \
     --target arn:aws:iot:region:account:cert/cert-id
   ```

2. **Create IoT device simulator:**
   ```python
   # iot_device_simulator.py
   import json
   import time
   import random
   from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
   
   # Setup MQTT client
   client = AWSIoTMQTTClient("smart-sensor-01")
   client.configureEndpoint("xxxxxx-ats.iot.us-east-1.amazonaws.com", 8883)
   client.configureCredentials("root-CA.crt", "private.key", "cert.pem")
   
   # Connect
   client.connect()
   
   # Publish sensor data
   while True:
       payload = {
           'device_id': 'smart-sensor-01',
           'timestamp': int(time.time()),
           'temperature': random.uniform(20.0, 30.0),
           'humidity': random.uniform(40.0, 60.0),
           'pressure': random.uniform(1000.0, 1020.0)
       }
       
       client.publish("sensors/data", json.dumps(payload), 1)
       print(f"Published: {payload}")
       time.sleep(5)
   ```

3. **Create IoT Rule to process data:**
   ```bash
   # Create IoT Rule to store in DynamoDB
   aws iot create-topic-rule \
     --rule-name ProcessSensorData \
     --topic-rule-payload '{
       "sql": "SELECT * FROM \"sensors/data\"",
       "actions": [{
         "dynamoDBv2": {
           "roleArn": "arn:aws:iam::account:role/IoTDynamoDBRole",
           "putItem": {
             "tableName": "SensorData"
           }
         }
       }],
       "ruleDisabled": false
     }'
   ```

### Step 3: Deploy Application with AWS App Runner
1. **Create Dockerfile:**
   ```dockerfile
   FROM python:3.12-slim
   
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   COPY app.py .
   
   EXPOSE 8000
   CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
   ```

2. **Deploy to App Runner:**
   ```bash
   # Create App Runner service
   aws apprunner create-service \
     --service-name my-web-app \
     --source-configuration '{
       "ImageRepository": {
         "ImageIdentifier": "account.dkr.ecr.region.amazonaws.com/my-app:latest",
         "ImageRepositoryType": "ECR",
         "ImageConfiguration": {
           "Port": "8000"
         }
       },
       "AutoDeploymentsEnabled": true
     }' \
     --instance-configuration '{
       "Cpu": "1 vCPU",
       "Memory": "2 GB"
     }'
   ```

3. **Access application:**
   - App Runner provides HTTPS URL automatically
   - Automatic scaling and load balancing
   - Zero infrastructure management

### Step 4: Build Full-Stack App with AWS Amplify
1. **Initialize Amplify project:**
   ```bash
   npm install -g @aws-amplify/cli
   amplify configure
   
   # Create React app
   npx create-react-app my-amplify-app
   cd my-amplify-app
   
   # Initialize Amplify
   amplify init
   ```

2. **Add authentication:**
   ```bash
   amplify add auth
   # Choose: Default configuration
   # Sign-in method: Username
   # Advanced settings: Default
   
   amplify push
   ```

3. **Add API (GraphQL):**
   ```bash
   amplify add api
   # Choose: GraphQL
   # Authorization: Amazon Cognito User Pool
   # Schema: Todo app
   
   amplify push
   ```

4. **Integrate in React app:**
   ```javascript
   // src/App.js
   import { Amplify } from 'aws-amplify';
   import { withAuthenticator } from '@aws-amplify/ui-react';
   import '@aws-amplify/ui-react/styles.css';
   import awsExports from './aws-exports';
   import { useState, useEffect } from 'react';
   import { API, graphqlOperation } from 'aws-amplify';
   import { listTodos } from './graphql/queries';
   import { createTodo } from './graphql/mutations';
   
   Amplify.configure(awsExports);
   
   function App({ signOut, user }) {
     const [todos, setTodos] = useState([]);
     const [input, setInput] = useState('');
   
     useEffect(() => {
       fetchTodos();
     }, []);
   
     async function fetchTodos() {
       const result = await API.graphql(graphqlOperation(listTodos));
       setTodos(result.data.listTodos.items);
     }
   
     async function addTodo() {
       const todo = { name: input, completed: false };
       await API.graphql(graphqlOperation(createTodo, { input: todo }));
       setInput('');
       fetchTodos();
     }
   
     return (
       <div>
         <h1>Hello {user.username}</h1>
         <button onClick={signOut}>Sign out</button>
         
         <h2>Todos</h2>
         <input value={input} onChange={e => setInput(e.target.value)} />
         <button onClick={addTodo}>Add Todo</button>
         
         <ul>
           {todos.map(todo => <li key={todo.id}>{todo.name}</li>)}
         </ul>
       </div>
     );
   }
   
   export default withAuthenticator(App);
   ```

5. **Deploy to Amplify Hosting:**
   ```bash
   amplify add hosting
   # Choose: Amplify Console
   amplify publish
   ```

### Step 5: Build Event-Driven Architecture with EventBridge
1. **Create custom event bus:**
   ```bash
   aws events create-event-bus --name application-events
   ```

2. **Create event patterns and rules:**
   ```bash
   # Rule for order processing
   aws events put-rule \
     --name ProcessNewOrders \
     --event-bus-name application-events \
     --event-pattern '{
       "source": ["ecommerce.orders"],
       "detail-type": ["Order Placed"]
     }'
   
   # Add Lambda target
   aws events put-targets \
     --rule ProcessNewOrders \
     --event-bus-name application-events \
     --targets '[{
       "Id": "1",
       "Arn": "arn:aws:lambda:region:account:function:ProcessOrder"
     }]'
   ```

3. **Publish events:**
   ```python
   # publish_event.py
   import boto3
   import json
   from datetime import datetime
   
   events = boto3.client('events')
   
   def publish_order_event(order_data):
       response = events.put_events(
           Entries=[{
               'Time': datetime.now(),
               'Source': 'ecommerce.orders',
               'DetailType': 'Order Placed',
               'Detail': json.dumps(order_data),
               'EventBusName': 'application-events'
           }]
       )
       return response
   
   # Example usage
   order = {
       'order_id': '12345',
       'customer_id': 'CUST001',
       'amount': 99.99,
       'items': [{'sku': 'PROD001', 'quantity': 2}]
   }
   
   publish_order_event(order)
   ```

### Step 6: Create GraphQL API with AWS AppSync
1. **Create AppSync API:**
   ```bash
   # Create API
   aws appsync create-graphql-api \
     --name ProductCatalogAPI \
     --authentication-type API_KEY
   ```

2. **Define GraphQL schema:**
   ```graphql
   # schema.graphql
   type Product {
     id: ID!
     name: String!
     description: String
     price: Float!
     category: String
     inStock: Boolean!
   }
   
   type Query {
     getProduct(id: ID!): Product
     listProducts(category: String): [Product]
   }
   
   type Mutation {
     createProduct(input: CreateProductInput!): Product
     updateProduct(input: UpdateProductInput!): Product
     deleteProduct(id: ID!): Product
   }
   
   input CreateProductInput {
     name: String!
     description: String
     price: Float!
     category: String
     inStock: Boolean!
   }
   
   input UpdateProductInput {
     id: ID!
     name: String
     price: Float
     inStock: Boolean
   }
   
   schema {
     query: Query
     mutation: Mutation
   }
   ```

3. **Configure data source (DynamoDB):**
   ```bash
   aws appsync create-data-source \
     --api-id <api-id> \
     --name ProductsTable \
     --type AMAZON_DYNAMODB \
     --dynamodb-config tableName=Products \
     --service-role-arn arn:aws:iam::account:role/AppSyncServiceRole
   ```

4. **Create resolvers:**
   ```javascript
   // Request mapping template
   {
     "version": "2017-02-28",
     "operation": "GetItem",
     "key": {
       "id": $util.dynamodb.toDynamoDBJson($ctx.args.id)
     }
   }
   
   // Response mapping template
   $util.toJson($ctx.result)
   ```

### Step 7: Implement Advanced Monitoring with X-Ray
1. **Enable X-Ray tracing:**
   ```python
   # app.py with X-Ray
   from aws_xray_sdk.core import xray_recorder
   from aws_xray_sdk.core import patch_all
   
   patch_all()
   
   @xray_recorder.capture('process_order')
   def process_order(order_id):
       # Add subsegments for detailed tracing
       subsegment = xray_recorder.begin_subsegment('validate_order')
       try:
           # Validation logic
           validate_order(order_id)
       finally:
           xray_recorder.end_subsegment()
       
       subsegment = xray_recorder.begin_subsegment('charge_payment')
       try:
           # Payment logic
           charge_payment(order_id)
       finally:
           xray_recorder.end_subsegment()
       
       return {'status': 'success'}
   ```

2. **Add custom annotations and metadata:**
   ```python
   xray_recorder.put_annotation('order_type', 'premium')
   xray_recorder.put_metadata('order_details', {
       'items': order_items,
       'total': order_total
   })
   ```

### Step 8: Use AWS Systems Manager for Operations
1. **Create SSM documents for runbooks:**
   ```yaml
   # runbook.yaml
   schemaVersion: '0.3'
   description: Automated instance patching
   parameters:
     InstanceId:
       type: String
   mainSteps:
     - name: StopInstance
       action: aws:executeAwsApi
       inputs:
         Service: ec2
         Api: StopInstances
         InstanceIds:
           - '{{ InstanceId }}'
     
     - name: WaitForStop
       action: aws:waitForAwsResourceProperty
       inputs:
         Service: ec2
         Api: DescribeInstanceStatus
         InstanceIds:
           - '{{ InstanceId }}'
         PropertySelector: '$.InstanceStatuses[0].InstanceState.Name'
         DesiredValues:
           - stopped
     
     - name: CreateAMI
       action: aws:createImage
       inputs:
         InstanceId: '{{ InstanceId }}'
         ImageName: 'Backup-{{ InstanceId }}-{{ global:DATE_TIME }}'
     
     - name: StartInstance
       action: aws:executeAwsApi
       inputs:
         Service: ec2
         Api: StartInstances
         InstanceIds:
           - '{{ InstanceId }}'
   ```

2. **Use Parameter Store for configuration:**
   ```bash
   # Store configuration
   aws ssm put-parameter \
     --name /app/database/connection-string \
     --value "postgresql://user:pass@host:5432/db" \
     --type SecureString
   
   # Retrieve in application
   aws ssm get-parameter \
     --name /app/database/connection-string \
     --with-decryption
   ```

### Step 9: Explore Quantum Computing with Amazon Braket (Overview)
1. **Understanding quantum computing on AWS:**
   - Amazon Braket provides access to quantum hardware
   - Supports gate-based and quantum annealing systems
   - Integrated with Jupyter notebooks

2. **Example quantum circuit (conceptual):**
   ```python
   # braket_example.py
   from braket.circuits import Circuit
   from braket.devices import LocalSimulator
   
   # Create quantum circuit
   circuit = Circuit().h(0).cnot(0, 1)
   
   # Run on simulator
   device = LocalSimulator()
   result = device.run(circuit, shots=1000).result()
   
   print(result.measurement_counts)
   ```

### Step 10: Future Trends and Best Practices
1. **Serverless-first architecture**
2. **Edge computing with Lambda@Edge and CloudFront Functions**
3. **AI/ML integration in applications**
4. **Multi-cloud strategies**
5. **Sustainability and green computing**
6. **Zero-trust security models**
7. **FinOps and cost optimization culture**
8. **GitOps for infrastructure management**
9. **Observability over monitoring**
10. **Platform engineering**

## Validation
- [ ] ML model deployed with SageMaker
- [ ] IoT device connected and sending data
- [ ] App Runner service deployed
- [ ] Amplify full-stack app created
- [ ] EventBridge event-driven architecture implemented
- [ ] AppSync GraphQL API created
- [ ] X-Ray tracing configured
- [ ] Systems Manager runbooks created
- [ ] Understanding of emerging AWS services
- [ ] Future-ready architecture patterns learned

## Cleanup
1. Delete SageMaker endpoints and models
2. Delete IoT things and certificates
3. Delete App Runner services
4. Delete Amplify app
5. Delete EventBridge rules and event buses
6. Delete AppSync API
7. Delete all test resources
8. Verify all resources removed

## Summary
In this final lab, you explored advanced AWS services including machine learning, IoT, serverless containers, full-stack development, event-driven architectures, and GraphQL APIs. You learned about emerging technologies and future trends in cloud computing. These skills position you to build innovative, next-generation cloud applications on AWS.

**Key Takeaways:**
- SageMaker simplifies ML model deployment
- IoT Core enables massive-scale IoT applications
- App Runner provides serverless container hosting
- Amplify accelerates full-stack development
- EventBridge enables loosely coupled architectures
- AppSync provides managed GraphQL APIs
- X-Ray enables distributed tracing
- Systems Manager automates operations
- Quantum computing is accessible via Braket
- Stay current with emerging AWS services

**Congratulations on completing all 10 sessions of the Advanced Cloud Computing with AWS lab series!**
