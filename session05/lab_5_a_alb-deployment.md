# Lab 5.A: Deploy a web application behind an Application Load Balancer (ALB)

## Overview
This lab walks through deploying a simple web application behind an Application Load Balancer (ALB). You will create an ALB with HTTP and HTTPS listeners, register EC2 targets (or an Auto Scaling Group), configure health checks, secure traffic with a TLS certificate from ACM, and validate routing and session stickiness.

## Objectives
- Create an ALB in public subnets and a Target Group in private subnets
- Configure security groups for ALB and application instances
- Request or import an ACM certificate and enable HTTPS listener
- Launch EC2 instances (or use an Auto Scaling Group) that run a sample web app
- Register targets and verify ALB health checks and routing
- Test HTTP/HTTPS access and validate TLS
- Clean up resources

## Prerequisites
- AWS CLI v2 configured
- IAM permissions for EC2, ELBv2, AutoScaling, ACM
- A VPC with at least two public subnets (for ALB) and private subnets for targets (optional)
- Domain name (optional) for TLS/Route53

## Architecture (high level)
- ALB in public subnets (internet-facing)
- Target Group with EC2 instances (private or public subnets)
- ALB security group allows inbound HTTP/HTTPS from internet
- Instance security group allows inbound from ALB SG only
- Optional: Route53 A/ALIAS pointing to ALB

---

## Variables (example)
- REGION=us-east-1
- VPC_ID=vpc-xxxx
- PUBLIC_SUBNETS="subnet-aaa subnet-bbb"
- PRIVATE_SUBNETS="subnet-ccc subnet-ddd"
- ALB_SG_NAME=lab-alb-sg
- APP_SG_NAME=lab-app-sg
- TARGET_GROUP_NAME=lab-app-tg
- ALB_NAME=lab-app-alb
- INSTANCE_TYPE=t3.micro
- AMI_ID=ami-0abcdef1234567890  # replace with a region-appropriate AMI
- KEY_NAME=lab-key
- CERT_ARN=arn:aws:acm:...
- DOMAIN=lab.example.com

---

## Steps (CLI examples)

### 1. Create security groups
Create ALB security group (allow HTTP/HTTPS from internet):
```bash
ALB_SG_ID=$(aws ec2 create-security-group --group-name $ALB_SG_NAME --description "ALB SG" --vpc-id $VPC_ID --query GroupId --output text --region $REGION)
aws ec2 authorize-security-group-ingress --group-id $ALB_SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0 --region $REGION
aws ec2 authorize-security-group-ingress --group-id $ALB_SG_ID --protocol tcp --port 443 --cidr 0.0.0.0/0 --region $REGION
```

Create application instance SG (allow only from ALB SG):
```bash
APP_SG_ID=$(aws ec2 create-security-group --group-name $APP_SG_NAME --description "App SG" --vpc-id $VPC_ID --query GroupId --output text --region $REGION)
aws ec2 authorize-security-group-ingress --group-id $APP_SG_ID --protocol tcp --port 80 --source-group $ALB_SG_ID --region $REGION
```

### 2. Create a Target Group
Create a target group for HTTP targets:
```bash
TARGET_ARN=$(aws elbv2 create-target-group --name $TARGET_GROUP_NAME --protocol HTTP --port 80 --vpc-id $VPC_ID --health-check-protocol HTTP --health-check-path / --matcher HttpCode=200 --region $REGION --query 'TargetGroups[0].TargetGroupArn' --output text)
```

### 3. Create the ALB
Create the ALB in two public subnets:
```bash
ALB_ARN=$(aws elbv2 create-load-balancer --name $ALB_NAME --subnets $PUBLIC_SUBNETS --security-groups $ALB_SG_ID --scheme internet-facing --type application --region $REGION --query 'LoadBalancers[0].LoadBalancerArn' --output text)
ALB_DNS=$(aws elbv2 describe-load-balancers --load-balancer-arns $ALB_ARN --query 'LoadBalancers[0].DNSName' --output text --region $REGION)
echo "ALB DNS: $ALB_DNS"
```

### 4. Create listeners
HTTP listener (redirect to HTTPS recommended):
```bash
aws elbv2 create-listener --load-balancer-arn $ALB_ARN --protocol HTTP --port 80 --default-actions Type=redirect,RedirectConfig='{"Protocol":"HTTPS","Port":"443","StatusCode":"HTTP_301"}' --region $REGION
```

HTTPS listener (uses ACM certificate):
```bash
aws elbv2 create-listener --load-balancer-arn $ALB_ARN --protocol HTTPS --port 443 --certificates CertificateArn=$CERT_ARN --default-actions Type=forward,TargetGroupArn=$TARGET_ARN --region $REGION
```

If you don't have a certificate, request one (DNS validation recommended):
```bash
aws acm request-certificate --domain-name $DOMAIN --validation-method DNS --region $REGION
# use "$BROWSER" to open the validation instructions if needed
```

### 5. Launch application instances (single or Auto Scaling)
Simple EC2 run-instances example with user-data to install a web app:
```bash
USER_DATA='#!/bin/bash
yum update -y
yum install -y httpd
systemctl enable httpd
systemctl start httpd
echo "Hello from ALB lab instance $(hostname)" > /var/www/html/index.html
'
INSTANCE_IDS=$(aws ec2 run-instances --image-id $AMI_ID --count 2 --instance-type $INSTANCE_TYPE --key-name $KEY_NAME --security-group-ids $APP_SG_ID --subnet-id $(echo $PRIVATE_SUBNETS | awk '{print $1}') --user-data "$USER_DATA" --query 'Instances[].InstanceId' --output text --region $REGION)
echo "Launched instances: $INSTANCE_IDS"
aws ec2 wait instance-running --instance-ids $INSTANCE_IDS --region $REGION
```

### 6. Register targets with Target Group
```bash
for id in $INSTANCE_IDS; do
  aws elbv2 register-targets --target-group-arn $TARGET_ARN --targets Id=$id --region $REGION
done

# wait for targets healthy
aws elbv2 wait target-in-service --target-group-arn $TARGET_ARN --targets Id=$(echo $INSTANCE_IDS | awk '{print $1}') --region $REGION || true
```

### 7. Validate
- Access ALB over HTTP: http://$ALB_DNS (redirects to HTTPS if configured)
- Access ALB over HTTPS: https://$ALB_DNS (certificate must be valid for domain)
- Verify content served and that multiple instances respond (round-robin)
- Check ALB target health in Console or:
```bash
aws elbv2 describe-target-health --target-group-arn $TARGET_ARN --region $REGION
```

### 8. Optional: Configure sticky sessions or path-based routing
Create listener rules for path-based routing:
```bash
aws elbv2 create-rule --listener-arn <HTTPS_LISTENER_ARN> --priority 10 --conditions Field=path-pattern,Values='/api/*' --actions Type=forward,TargetGroupArn=$API_TG_ARN --region $REGION
```
Enable sticky sessions on the target group:
```bash
aws elbv2 modify-target-group-attributes --target-group-arn $TARGET_ARN --attributes Key=stickiness.enabled,Value=true Key=stickiness.type,Value=lb_cookie Key=stickiness.lb_cookie.duration_seconds,Value=86400 --region $REGION
```

### 9. Logging and monitoring
- Enable access logs on ALB to S3 (Console or CLI):
```bash
aws elbv2 modify-load-balancer-attributes --load-balancer-arn $ALB_ARN --attributes Key=access_logs.s3.enabled,Value=true Key=access_logs.s3.bucket,Value=your-log-bucket --region $REGION
```
- Monitor CloudWatch metrics (RequestCount, HTTPCode_ELB_5XX, TargetResponseTime)
- Use AWS WAF to protect against common web attacks (optional)

### 10. Cleanup
Remove resources to avoid charges:
```bash
# deregister targets, terminate instances
for id in $INSTANCE_IDS; do
  aws ec2 terminate-instances --instance-ids $id --region $REGION
done

# delete listeners and ALB
LISTENER_ARN_HTTP=$(aws elbv2 describe-listeners --load-balancer-arn $ALB_ARN --query 'Listeners[?Port==`80`].ListenerArn' --output text --region $REGION)
LISTENER_ARN_HTTPS=$(aws elbv2 describe-listeners --load-balancer-arn $ALB_ARN --query 'Listeners[?Port==`443`].ListenerArn' --output text --region $REGION)
[ -n "$LISTENER_ARN_HTTP" ] && aws elbv2 delete-listener --listener-arn $LISTENER_ARN_HTTP --region $REGION
[ -n "$LISTENER_ARN_HTTPS" ] && aws elbv2 delete-listener --listener-arn $LISTENER_ARN_HTTPS --region $REGION

aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN --region $REGION
aws elbv2 delete-target-group --target-group-arn $TARGET_ARN --region $REGION

# delete security groups
aws ec2 delete-security-group --group-id $APP_SG_ID --region $REGION
aws ec2 delete-security-group --group-id $ALB_SG_ID --region $REGION
```

---

## Validation Checklist
- [ ] ALB created and reachable
- [ ] Target Group healthy with registered instances
- [ ] HTTP -> HTTPS redirect and TLS configured with ACM certificate
- [ ] Security groups restrict access (ALB open to internet, app only from ALB)
- [ ] Application served correct content via ALB
- [ ] Access logs and CloudWatch metrics enabled (optional)

## Best practices & notes
- Run ALB in at least two AZs for high availability.
- Use Auto Scaling Groups for target management in production.
- Terminate instances and ALB after the lab to avoid charges.
- Use ACM for TLS certificates and Route53 for DNS validation.
- Prefer ALB access logs and WAF for observability and protection.

## Summary
This lab covers end-to-end deployment of a web application behind an ALB, including security groups, TLS termination, target registration, health checks, routing, and cleanup. It prepares you to deploy scalable, highly-available web services on AWS.
