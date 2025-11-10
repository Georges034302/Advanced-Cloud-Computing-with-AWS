# Lab 8.A: Amazon ECS with Fargate - Container Basics

## Overview
This lab introduces Amazon Elastic Container Service (ECS) with AWS Fargate, a serverless compute engine for containers. You'll learn how to containerize applications, create ECS clusters, define task definitions, and deploy containerized applications without managing servers.

## Objectives
- Understand container concepts and Docker basics
- Build and push Docker images to Amazon ECR
- Create ECS clusters with Fargate
- Define ECS task definitions and services
- Configure load balancing for containerized applications
- Implement auto-scaling for ECS services
- Monitor container performance
- Understand ECS vs EKS use cases

## Requirements
- AWS account with ECS and ECR permissions
- Docker installed locally
- Basic understanding of containers
- Familiarity with application development
- AWS CLI configured

## Steps

### Step 1: Install and Verify Docker
1. Install Docker:
   ```bash
   # Verify installation
   docker --version
   docker run hello-world
   ```

2. Test Docker locally:
   ```bash
   # Run nginx container
   docker run -d -p 8080:80 nginx
   # Test: curl http://localhost:8080
   docker ps
   docker stop <container-id>
   ```

### Step 2: Create a Simple Web Application
1. Create application directory:
   ```bash
   mkdir simple-web-app && cd simple-web-app
   ```

2. Create application file:
   ```python
   # app.py
   from flask import Flask, jsonify
   import os
   import socket
   
   app = Flask(__name__)
   
   @app.route('/')
   def home():
       return jsonify({
           'message': 'Hello from ECS!',
           'hostname': socket.gethostname(),
           'version': os.environ.get('APP_VERSION', '1.0')
       })
   
   @app.route('/health')
   def health():
       return jsonify({'status': 'healthy'})
   
   if __name__ == '__main__':
       app.run(host='0.0.0.0', port=5000)
   ```

3. Create requirements file:
   ```text
   # requirements.txt
   Flask==3.0.0
   gunicorn==21.2.0
   ```

4. Create Dockerfile:
   ```dockerfile
   FROM python:3.12-slim
   
   WORKDIR /app
   
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   COPY app.py .
   
   ENV APP_VERSION=1.0
   
   EXPOSE 5000
   
   CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
   ```

5. Build and test locally:
   ```bash
   docker build -t simple-web-app:v1 .
   docker run -d -p 5000:5000 --name web-app simple-web-app:v1
   curl http://localhost:5000
   docker logs web-app
   docker stop web-app && docker rm web-app
   ```

### Step 3: Create Amazon ECR Repository
1. Navigate to ECR console
2. Click "Create repository"
3. Configure:
   - Visibility: Private
   - Repository name: `simple-web-app`
   - Tag immutability: Disabled
   - Scan on push: Enabled
4. Create repository

5. Get login credentials:
   ```bash
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin \
     <account-id>.dkr.ecr.us-east-1.amazonaws.com
   ```

6. Tag and push image:
   ```bash
   docker tag simple-web-app:v1 \
     <account-id>.dkr.ecr.us-east-1.amazonaws.com/simple-web-app:v1
   
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/simple-web-app:v1
   ```

7. Verify image in ECR console

### Step 4: Create ECS Cluster
1. Navigate to ECS console
2. Click "Create Cluster"
3. Configure:
   - Cluster name: `web-app-cluster`
   - Infrastructure: AWS Fargate (serverless)
   - Monitoring: Enable Container Insights (optional)
4. Create cluster

### Step 5: Create Task Definition
1. Navigate to Task Definitions → Create new task definition
2. Configure task definition:
   - Task definition family: `simple-web-app-task`
   - Launch type: Fargate
   - Operating system: Linux
   - Task size:
     - CPU: 0.5 vCPU
     - Memory: 1 GB
   - Task role: Create new role (for AWS service access)
   - Task execution role: Create new role (ecsTaskExecutionRole)

3. Container definitions:
   - Container name: `web-app`
   - Image URI: `<account-id>.dkr.ecr.us-east-1.amazonaws.com/simple-web-app:v1`
   - Port mappings:
     - Container port: 5000
     - Protocol: TCP
     - App protocol: HTTP
   - Environment variables:
     - APP_VERSION: v1
   - Health check:
     - Command: `CMD-SHELL, curl -f http://localhost:5000/health || exit 1`
     - Interval: 30 seconds
     - Timeout: 5 seconds
     - Retries: 3
   - Log configuration:
     - Log driver: awslogs
     - Log group: Create new `/ecs/simple-web-app`
     - Stream prefix: `ecs`

4. Create task definition

### Step 6: Create Application Load Balancer
1. Navigate to EC2 → Load Balancers
2. Create Application Load Balancer:
   - Name: `ecs-web-app-alb`
   - Scheme: Internet-facing
   - VPC: Default VPC
   - Subnets: Select 2+ availability zones
   - Security group: Allow HTTP (80) from anywhere

3. Create target group:
   - Target type: IP addresses
   - Protocol: HTTP
   - Port: 5000
   - VPC: Default VPC
   - Health check path: `/health`
   - Name: `ecs-web-app-tg`

4. Complete load balancer creation

### Step 7: Create ECS Service
1. Navigate to cluster → Services → Create
2. Configure service:
   - Launch type: Fargate
   - Task definition: `simple-web-app-task:1`
   - Service name: `web-app-service`
   - Desired tasks: 2
   - Deployment type: Rolling update
   - Minimum healthy percent: 100
   - Maximum percent: 200

3. Networking:
   - VPC: Default VPC
   - Subnets: Select multiple AZs
   - Security group: Allow port 5000 from ALB security group
   - Public IP: Enabled

4. Load balancing:
   - Load balancer type: Application Load Balancer
   - Select: `ecs-web-app-alb`
   - Container: `web-app:5000:5000`
   - Target group: `ecs-web-app-tg`
   - Health check grace period: 60 seconds

5. Auto Scaling:
   - Service auto scaling: Yes
   - Minimum tasks: 2
   - Maximum tasks: 6
   - Policy:
     - Type: Target tracking
     - Metric: ECS Service Average CPU Utilization
     - Target value: 70%

6. Create service

### Step 8: Verify Deployment
1. Wait for service status: "Active"
2. Check tasks are running:
   - Tasks tab → All tasks should be "RUNNING"
3. Check target group health:
   - EC2 → Target Groups → `ecs-web-app-tg`
   - Targets should show "healthy"
4. Test application:
   - Get ALB DNS name
   - `curl http://<alb-dns-name>`
   - Refresh multiple times to see different hostnames (task IPs)

### Step 9: Update Service with New Version
1. Update application code:
   ```python
   # Modify app.py
   'message': 'Hello from ECS v2!',
   ```

2. Build and push new version:
   ```bash
   docker build -t simple-web-app:v2 .
   docker tag simple-web-app:v2 \
     <account-id>.dkr.ecr.us-east-1.amazonaws.com/simple-web-app:v2
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/simple-web-app:v2
   ```

3. Create new task definition revision:
   - Select task definition → Create new revision
   - Update image tag to `:v2`
   - Update APP_VERSION to `v2`
   - Create

4. Update service:
   - Service → Update
   - Select new task definition revision
   - Force new deployment: Yes
   - Update service

5. Monitor rolling update:
   - Deployments tab → Watch rolling update
   - Old tasks drained, new tasks started
   - Zero downtime deployment

### Step 10: Monitor ECS Service
1. **CloudWatch Metrics:**
   - ECS → Cluster → Metrics
   - View: CPUUtilization, MemoryUtilization
   - Service-level and task-level metrics

2. **Container Insights:**
   - CloudWatch → Container Insights
   - View cluster, service, and task performance

3. **CloudWatch Logs:**
   - CloudWatch → Log Groups → `/ecs/simple-web-app`
   - View application logs from all tasks

4. **Create CloudWatch Alarms:**
   - High CPU:
     - Metric: Service CPUUtilization
     - Threshold: > 80%
   - Service unhealthy:
     - Metric: TargetHealth (from ALB)
     - Threshold: < 1

### Step 11: Test Auto Scaling
1. Generate load to trigger scaling:
   ```bash
   # Install Apache Bench
   ab -n 10000 -c 100 http://<alb-dns-name>/
   ```

2. Monitor auto-scaling:
   - Service → Deployments → Auto Scaling events
   - Watch task count increase
   - View CloudWatch alarms

3. Stop load and watch scale-in:
   - Task count should decrease after cooldown period

## Validation
- [ ] Docker installed and working locally
- [ ] Application containerized successfully
- [ ] ECR repository created and image pushed
- [ ] ECS cluster created with Fargate
- [ ] Task definition configured properly
- [ ] Service running with desired task count
- [ ] Load balancer distributing traffic
- [ ] Health checks passing
- [ ] Rolling deployment completed successfully
- [ ] Auto-scaling configured and tested
- [ ] CloudWatch metrics and logs accessible

## Cleanup
1. Update service desired count to 0
2. Delete ECS service
3. Deregister task definitions
4. Delete ECS cluster
5. Delete Application Load Balancer
6. Delete target group
7. Delete ECR repository (and images)
8. Delete CloudWatch log groups
9. Delete security groups
10. Verify all resources removed

## Summary
In this lab, you learned how to containerize applications and deploy them on Amazon ECS with Fargate. You created Docker images, pushed them to ECR, defined ECS tasks, and deployed scalable services with load balancing. Fargate's serverless model eliminates the need to manage EC2 instances while providing full container orchestration capabilities.

**Key Takeaways:**
- Fargate eliminates infrastructure management for containers
- ECR provides secure, managed Docker registry
- Task definitions specify container configuration
- Services maintain desired task count with auto-scaling
- Rolling deployments enable zero-downtime updates
- Load balancers distribute traffic across tasks
- Container Insights provides detailed performance metrics
- Health checks ensure only healthy tasks receive traffic
- Auto-scaling adjusts capacity based on metrics
- Pay only for vCPU and memory resources used
