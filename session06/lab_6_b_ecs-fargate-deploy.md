# Lab 6.B: Deploy a containerized app on Amazon ECS using Fargate

## Overview
Deploy a containerized web application to Amazon ECS using the Fargate launch type (serverless containers). The lab covers building and pushing an image to ECR, creating an ECS cluster, task definition, service, optional Application Load Balancer integration, IAM roles, networking, and cleanup.

## Objectives
- Build and push a Docker image to ECR
- Create an ECS cluster supporting Fargate
- Define and register a Fargate task definition
- Create an ECS service (with optional ALB) and verify traffic
- Configure required IAM roles and security groups
- Scale, update, and clean up the deployment

## Prerequisites
- AWS CLI v2 configured
- Docker installed and authenticated to ECR
- IAM permissions for ECR, ECS, IAM, ELBv2, EC2 networking
- VPC with at least two subnets in different AZs (for ALB/high availability)

## Architecture (high level)
- ECR repo stores Docker image
- ECS cluster (Fargate) runs tasks in private subnets
- Optional ALB in public subnets fronts the ECS service with target group
- Task execution role grants ECR pull and CloudWatch logs access
- Security groups restrict access: ALB from internet, tasks only from ALB

## Variables (example)
- REGION=us-east-1
- ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
- REPO_NAME=lab-ecs-app
- IMAGE_TAG=latest
- CLUSTER_NAME=lab-fargate-cluster
- TASK_DEF_NAME=lab-fargate-task
- SERVICE_NAME=lab-fargate-service
- CONTAINER_NAME=lab-app
- CONTAINER_PORT=80
- SUBNETS="subnet-aaa subnet-bbb"
- VPC_ID=vpc-xxxx
- ALB_PUBLIC_SUBNETS="subnet-111 subnet-222"
- KEY_NAME=lab-key   # only if launching bastion for debugging

---

## Steps (CLI examples)

### 1. Build and push image to ECR
```bash
aws ecr create-repository --repository-name $REPO_NAME --region $REGION || true
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
docker build -t ${REPO_NAME}:${IMAGE_TAG} .
docker tag ${REPO_NAME}:${IMAGE_TAG} ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}
docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}
```

### 2. Create IAM role for Fargate task execution
```bash
cat > trust.json <<'EOF'
{
  "Version":"2012-10-17",
  "Statement":[
    { "Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole" }
  ]
}
EOF

aws iam create-role --role-name ecsTaskExecutionRole --assume-role-policy-document file://trust.json --region $REGION || true
aws iam attach-role-policy --role-name ecsTaskExecutionRole --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy --region $REGION
```

### 3. Create ECS cluster
```bash
aws ecs create-cluster --cluster-name $CLUSTER_NAME --capacity-providers FARGATE FARGATE_SPOT --region $REGION || true
```

### 4. Register a Fargate task definition
Sample task definition (minimal) — replace image ARN:
```bash
cat > task-def.json <<'EOF'
{
  "family": "lab-fargate-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "${CONTAINER_NAME}",
      "image": "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}",
      "portMappings": [ { "containerPort": ${CONTAINER_PORT}, "protocol": "tcp" } ],
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${SERVICE_NAME}",
          "awslogs-region": "${REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF

aws ecs register-task-definition --cli-input-json file://task-def.json --region $REGION
```

### 5. (Optional) Create an ALB and target group for the service
```bash
ALB_SG_ID=$(aws ec2 create-security-group --group-name lab-alb-sg --description "ALB SG" --vpc-id $VPC_ID --query GroupId --output text --region $REGION)
aws ec2 authorize-security-group-ingress --group-id $ALB_SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0 --region $REGION

TG_ARN=$(aws elbv2 create-target-group --name lab-ecs-tg --protocol HTTP --port $CONTAINER_PORT --vpc-id $VPC_ID --target-type ip --region $REGION --query 'TargetGroups[0].TargetGroupArn' --output text)
ALB_ARN=$(aws elbv2 create-load-balancer --name lab-ecs-alb --subnets $ALB_PUBLIC_SUBNETS --security-groups $ALB_SG_ID --scheme internet-facing --region $REGION --query 'LoadBalancers[0].LoadBalancerArn' --output text)
LISTENER_ARN=$(aws elbv2 create-listener --load-balancer-arn $ALB_ARN --protocol HTTP --port 80 --default-actions Type=forward,TargetGroupArn=$TG_ARN --region $REGION --query 'Listeners[0].ListenerArn' --output text)
ALB_DNS=$(aws elbv2 describe-load-balancers --load-balancer-arns $ALB_ARN --region $REGION --query 'LoadBalancers[0].DNSName' --output text)
```

### 6. Create the ECS service (with awsvpc networking)
Create SG for tasks that only allows traffic from ALB SG (or open as required):
```bash
TASK_SG_ID=$(aws ec2 create-security-group --group-name lab-task-sg --description "Task SG" --vpc-id $VPC_ID --query GroupId --output text --region $REGION)
# allow traffic from ALB SG to container port
aws ec2 authorize-security-group-ingress --group-id $TASK_SG_ID --protocol tcp --port $CONTAINER_PORT --source-group $ALB_SG_ID --region $REGION
```

Create service:
```bash
aws ecs create-service \
  --cluster $CLUSTER_NAME \
  --service-name $SERVICE_NAME \
  --task-definition $TASK_DEF_NAME \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$TASK_SG_ID],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=$TG_ARN,containerName=${CONTAINER_NAME},containerPort=${CONTAINER_PORT}" \
  --region $REGION
```

If not using an ALB, omit load-balancers and expose via NAT/bastion/SSM port forwarding for debug.

### 7. Verify deployment
- Check service and task status:
```bash
aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION
aws ecs list-tasks --cluster $CLUSTER_NAME --service-name $SERVICE_NAME --region $REGION
aws ecs describe-tasks --cluster $CLUSTER_NAME --tasks $(aws ecs list-tasks --cluster $CLUSTER_NAME --service-name $SERVICE_NAME --region $REGION --query 'taskArns[]' --output text) --region $REGION
```
- If ALB configured, access: http://$ALB_DNS

### 8. Update / Scale
- Update task definition image and register new revision, then update service:
```bash
aws ecs update-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --task-definition lab-fargate-task:2 --desired-count 3 --region $REGION
```

### 9. Cleanup
```bash
aws ecs update-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --desired-count 0 --region $REGION
aws ecs delete-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --force --region $REGION
aws ecs deregister-task-definition --task-definition lab-fargate-task --region $REGION || true
aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN --region $REGION || true
aws elbv2 delete-target-group --target-group-arn $TG_ARN --region $REGION || true
aws ec2 delete-security-group --group-id $TASK_SG_ID --region $REGION || true
aws ec2 delete-security-group --group-id $ALB_SG_ID --region $REGION || true
aws ecs delete-cluster --cluster $CLUSTER_NAME --region $REGION || true
aws ecr delete-repository --repository-name $REPO_NAME --force --region $REGION || true
aws iam detach-role-policy --role-name ecsTaskExecutionRole --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy --region $REGION || true
aws iam delete-role --role-name ecsTaskExecutionRole --region $REGION || true
```

## Validation checklist
- [ ] Image pushed to ECR
- [ ] ECS cluster created
- [ ] Fargate task definition registered and running
- [ ] ECS service running desired tasks
- [ ] ALB (if used) routes traffic to healthy tasks
- [ ] Logs available in CloudWatch Logs
- [ ] Service scales and updates correctly
- [ ] Resources cleaned up after lab

## Notes & best practices
- Use task execution role for ECR pulls and CloudWatch logs.
- Run tasks in private subnets and expose via ALB for production.
- Use health checks and appropriate resource sizes for tasks.
- Use immutable tags (image digests) for deployments and CI/CD for automated rollouts
