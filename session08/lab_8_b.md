# Lab 8.B: ECS Service Discovery and Multi-Container Applications

## Overview
This lab explores advanced ECS features including AWS Cloud Map for service discovery, multi-container task definitions, ECS Exec for debugging, and deploying microservices architectures. You'll learn how to build interconnected containerized services that communicate seamlessly within your ECS environment.

## Objectives
- Configure AWS Cloud Map for service discovery
- Create multi-container task definitions
- Implement microservices communication patterns
- Use ECS Exec for container debugging
- Configure service mesh with App Mesh (overview)
- Implement secrets management with Secrets Manager
- Deploy sidecar patterns
- Monitor distributed container applications

## Requirements
- Completed Lab 8.A or equivalent ECS knowledge
- Understanding of microservices architecture
- Docker and containerization experience
- VPC and networking knowledge
- AWS CLI configured

## Steps

### Step 1: Create Cloud Map Namespace
1. Navigate to AWS Cloud Map console
2. Click "Create namespace"
3. Configure:
   - Namespace type: API calls and DNS queries in VPCs
   - Namespace name: `local`
   - VPC: Select your VPC
   - Description: "Service discovery for ECS"
4. Create namespace
5. Note the namespace ID

### Step 2: Create Backend API Service
1. Create backend application:
   ```python
   # backend/app.py
   from flask import Flask, jsonify
   import random
   
   app = Flask(__name__)
   
   @app.route('/api/data')
   def get_data():
       return jsonify({
           'data': random.randint(1, 100),
           'service': 'backend'
       })
   
   @app.route('/health')
   def health():
       return jsonify({'status': 'healthy'})
   
   if __name__ == '__main__':
       app.run(host='0.0.0.0', port=8080)
   ```

2. Create Dockerfile:
   ```dockerfile
   FROM python:3.12-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY app.py .
   EXPOSE 8080
   CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
   ```

3. Build and push to ECR:
   ```bash
   docker build -t backend-api:v1 backend/
   docker tag backend-api:v1 <account>.dkr.ecr.<region>.amazonaws.com/backend-api:v1
   docker push <account>.dkr.ecr.<region>.amazonaws.com/backend-api:v1
   ```

### Step 3: Create Frontend Service
1. Create frontend application:
   ```python
   # frontend/app.py
   from flask import Flask, jsonify
   import requests
   import os
   
   app = Flask(__name__)
   BACKEND_URL = os.environ.get('BACKEND_URL', 'http://backend.local:8080')
   
   @app.route('/')
   def home():
       try:
           # Call backend service via service discovery
           response = requests.get(f'{BACKEND_URL}/api/data', timeout=5)
           backend_data = response.json()
           
           return jsonify({
               'message': 'Frontend service',
               'backend_response': backend_data
           })
       except Exception as e:
           return jsonify({
               'message': 'Frontend service',
               'error': str(e)
           }), 500
   
   @app.route('/health')
   def health():
       return jsonify({'status': 'healthy'})
   
   if __name__ == '__main__':
       app.run(host='0.0.0.0', port=5000)
   ```

2. Add requests to requirements:
   ```text
   Flask==3.0.0
   gunicorn==21.2.0
   requests==2.31.0
   ```

3. Build and push to ECR

### Step 4: Create Backend Task Definition with Service Discovery
1. Create task definition for backend:
   - Family: `backend-api-task`
   - Launch type: Fargate
   - CPU: 0.25 vCPU
   - Memory: 0.5 GB
   - Container:
     - Name: `backend`
     - Image: Backend ECR image
     - Port: 8080
     - Health check: `/health`

2. Create backend service with Cloud Map:
   - Service name: `backend-service`
   - Task definition: `backend-api-task`
   - Desired count: 2
   - Service discovery:
     - Enable service discovery: Yes
     - Namespace: `local`
     - Service discovery name: `backend`
     - DNS record type: A
     - TTL: 60 seconds
   - Health check grace period: 60 seconds

3. Verify service discovery:
   ```bash
   # From within VPC (using EC2 instance)
   nslookup backend.local
   # Should resolve to task IP addresses
   ```

### Step 5: Create Frontend Service
1. Create frontend task definition:
   - Family: `frontend-task`
   - Container:
     - Name: `frontend`
     - Image: Frontend ECR image
     - Port: 5000
     - Environment variables:
       - `BACKEND_URL`: `http://backend.local:8080`

2. Create frontend service:
   - Task definition: `frontend-task`
   - Desired count: 2
   - Load balancer: Attach to ALB
   - Service discovery: Optional

3. Test microservices communication:
   ```bash
   curl http://<alb-dns-name>/
   # Should show frontend calling backend via service discovery
   ```

### Step 6: Create Multi-Container Task Definition
1. Create multi-container application:
   ```json
   {
     "family": "multi-container-task",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "512",
     "memory": "1024",
     "containerDefinitions": [
       {
         "name": "app",
         "image": "<account>.dkr.ecr.<region>.amazonaws.com/app:v1",
         "portMappings": [{
           "containerPort": 80,
           "protocol": "tcp"
         }],
         "dependsOn": [{
           "containerName": "init-container",
           "condition": "SUCCESS"
         }],
         "environment": [{
           "name": "LOG_LEVEL",
           "value": "info"
         }]
       },
       {
         "name": "init-container",
         "image": "busybox:latest",
         "essential": false,
         "command": [
           "sh", "-c",
           "echo 'Initialization complete' && sleep 5"
         ]
       },
       {
         "name": "log-router",
         "image": "amazon/aws-for-fluent-bit:latest",
         "essential": true,
         "firelensConfiguration": {
           "type": "fluentbit"
         },
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/firelens",
             "awslogs-region": "us-east-1",
             "awslogs-stream-prefix": "firelens"
           }
         }
       }
     ]
   }
   ```

2. Register task definition:
   ```bash
   aws ecs register-task-definition \
     --cli-input-json file://multi-container-task.json
   ```

### Step 7: Implement Secrets Management
1. Create secrets in AWS Secrets Manager:
   ```bash
   aws secretsmanager create-secret \
     --name db-password \
     --secret-string "MySecurePassword123!"
   
   aws secretsmanager create-secret \
     --name api-key \
     --secret-string "api-key-12345"
   ```

2. Update task definition to use secrets:
   ```json
   {
     "containerDefinitions": [{
       "name": "app",
       "secrets": [
         {
           "name": "DB_PASSWORD",
           "valueFrom": "arn:aws:secretsmanager:region:account:secret:db-password"
         },
         {
           "name": "API_KEY",
           "valueFrom": "arn:aws:secretsmanager:region:account:secret:api-key"
         }
       ]
     }]
   }
   ```

3. Update task execution role policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": [
         "secretsmanager:GetSecretValue"
       ],
       "Resource": [
         "arn:aws:secretsmanager:region:account:secret:db-password*",
         "arn:aws:secretsmanager:region:account:secret:api-key*"
       ]
     }]
   }
   ```

### Step 8: Enable and Use ECS Exec
1. Enable ECS Exec on service:
   ```bash
   aws ecs update-service \
     --cluster web-app-cluster \
     --service backend-service \
     --enable-execute-command
   ```

2. Update task role for ECS Exec:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": [
         "ssmmessages:CreateControlChannel",
         "ssmmessages:CreateDataChannel",
         "ssmmessages:OpenControlChannel",
         "ssmmessages:OpenDataChannel"
       ],
       "Resource": "*"
     }]
   }
   ```

3. Connect to running container:
   ```bash
   # List tasks
   aws ecs list-tasks \
     --cluster web-app-cluster \
     --service-name backend-service
   
   # Execute command in container
   aws ecs execute-command \
     --cluster web-app-cluster \
     --task <task-id> \
     --container backend \
     --interactive \
     --command "/bin/sh"
   ```

4. Debug within container:
   ```bash
   # Inside container
   ps aux
   netstat -tlnp
   env
   curl localhost:8080/health
   cat /proc/1/environ
   exit
   ```

### Step 9: Implement Sidecar Pattern
1. Create logging sidecar task definition:
   ```json
   {
     "containerDefinitions": [
       {
         "name": "application",
         "image": "app:v1",
         "portMappings": [{"containerPort": 80}],
         "logConfiguration": {
           "logDriver": "awsfirelens"
         }
       },
       {
         "name": "log-aggregator",
         "image": "fluent/fluent-bit:latest",
         "firelensConfiguration": {
           "type": "fluentbit",
           "options": {
             "config-file-type": "file",
             "config-file-value": "/fluent-bit/configs/parse-json.conf"
           }
         },
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/sidecar-logs",
             "awslogs-region": "us-east-1"
           }
         }
       }
     ]
   }
   ```

2. Create monitoring sidecar (Prometheus exporter):
   ```json
   {
     "name": "metrics-exporter",
     "image": "prom/node-exporter:latest",
     "portMappings": [{
       "containerPort": 9100
     }],
     "essential": false
   }
   ```

### Step 10: Monitor Microservices with X-Ray
1. Add X-Ray daemon sidecar:
   ```json
   {
     "containerDefinitions": [{
       "name": "xray-daemon",
       "image": "amazon/aws-xray-daemon:latest",
       "cpu": 32,
       "memoryReservation": 256,
       "portMappings": [{
         "containerPort": 2000,
         "protocol": "udp"
       }]
     }]
   }
   ```

2. Update application to use X-Ray:
   ```python
   # Add to app.py
   from aws_xray_sdk.core import xray_recorder
   from aws_xray_sdk.ext.flask.middleware import XRayMiddleware
   
   xray_recorder.configure(service='backend-api')
   XRayMiddleware(app, xray_recorder)
   
   @app.route('/api/data')
   @xray_recorder.capture('get_data')
   def get_data():
       # Existing code
   ```

3. View service map in X-Ray console:
   - Shows request flow between services
   - Latency analysis
   - Error tracking

### Step 11: Implement Circuit Breaker Pattern
1. Configure deployment circuit breaker:
   ```bash
   aws ecs update-service \
     --cluster web-app-cluster \
     --service backend-service \
     --deployment-configuration '{
       "deploymentCircuitBreaker": {
         "enable": true,
         "rollback": true
       },
       "maximumPercent": 200,
       "minimumHealthyPercent": 100
     }'
   ```

2. Test circuit breaker:
   - Deploy bad task definition
   - Circuit breaker detects failures
   - Automatic rollback to previous version

## Validation
- [ ] Cloud Map namespace created
- [ ] Backend service registered with service discovery
- [ ] Frontend successfully calls backend via DNS
- [ ] Multi-container task definition working
- [ ] Secrets Manager integration configured
- [ ] ECS Exec enabled and tested
- [ ] Sidecar containers deployed
- [ ] X-Ray tracing implemented
- [ ] Circuit breaker tested
- [ ] Microservices communicating properly

## Cleanup
1. Delete ECS services (frontend, backend)
2. Deregister all task definitions
3. Delete Cloud Map service and namespace
4. Delete ECR repositories
5. Delete Secrets Manager secrets
6. Delete CloudWatch log groups
7. Delete X-Ray service data
8. Delete load balancers and target groups
9. Verify all resources removed

## Summary
In this lab, you built a microservices architecture on ECS using service discovery, multi-container tasks, and advanced debugging tools. You learned how to implement sidecar patterns, manage secrets securely, and enable distributed tracing. These patterns are essential for building production-grade containerized applications on AWS.

**Key Takeaways:**
- Cloud Map enables DNS-based service discovery
- Multi-container tasks enable sidecar patterns
- ECS Exec provides debugging without SSH
- Secrets Manager securely stores sensitive data
- Service discovery simplifies microservices communication
- Sidecar containers handle cross-cutting concerns
- X-Ray provides distributed tracing
- Circuit breakers prevent cascading failures
- FireLens enables flexible log routing
- Container dependencies control startup order
