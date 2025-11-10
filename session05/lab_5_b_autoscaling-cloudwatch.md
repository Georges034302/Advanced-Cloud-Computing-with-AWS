# Lab 5.B: Configure Auto Scaling policies and CloudWatch alarms for EC2

## Overview
This lab teaches how to create an Auto Scaling Group (ASG) for EC2, configure scaling policies (target-tracking, step, scheduled), and create CloudWatch alarms and metrics to drive scaling decisions. You will validate autoscaling behavior and observe CloudWatch metrics and alarms.

## Objectives
- Create a Launch Template or Launch Configuration
- Create an Auto Scaling Group across multiple AZs
- Configure scaling policies: target-tracking, step-scaling, and scheduled scaling
- Create CloudWatch alarms and custom metrics to trigger policies
- Test scale-out and scale-in behavior and observe cooldown/health checks
- Cleanup resources

## Prerequisites
- AWS CLI v2 configured
- IAM permissions: ec2, autoscaling, cloudwatch
- VPC with subnets across ≥2 AZs
- AMI with a simple web service or user-data to bootstrap

---

## Variables (replace before running)
- REGION=us-east-1
- VPC_ID=vpc-xxxx
- SUBNETS="subnet-aaa subnet-bbb subnet-ccc"
- KEY_NAME=lab-key
- SECURITY_GROUP_ID=sg-xxxx
- LAUNCH_TEMPLATE_NAME=lab-launch-template
- ASG_NAME=lab-asg
- TARGET_GROUP_ARN=<optional-target-group-arn>
- AMI_ID=ami-xxxxxxxx
- INSTANCE_TYPE=t3.micro
- MIN_SIZE=1
- MAX_SIZE=4
- DESIRED_CAPACITY=1

---

## Steps (CLI examples)

### 1. Create a Launch Template (user-data bootstraps web service)
```bash
cat > user-data.sh <<'EOF'
#!/bin/bash
yum update -y
yum install -y httpd
systemctl enable --now httpd
echo "ASG instance $(hostname) $(date)" > /var/www/html/index.html
EOF

aws ec2 create-launch-template \
  --launch-template-name $LAUNCH_TEMPLATE_NAME \
  --version-description "v1" \
  --launch-template-data "{
    \"ImageId\":\"$AMI_ID\",
    \"InstanceType\":\"$INSTANCE_TYPE\",
    \"KeyName\":\"$KEY_NAME\",
    \"SecurityGroupIds\":[\"$SECURITY_GROUP_ID\"],
    \"UserData\":\"$(base64 -w0 user-data.sh)\"
  }" --region $REGION
```

### 2. Create the Auto Scaling Group
```bash
aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name $ASG_NAME \
  --launch-template LaunchTemplateName=$LAUNCH_TEMPLATE_NAME,Version=1 \
  --min-size $MIN_SIZE --max-size $MAX_SIZE --desired-capacity $DESIRED_CAPACITY \
  --vpc-zone-identifier "$SUBNETS" \
  --target-group-arns $TARGET_GROUP_ARN \
  --region $REGION
```

### 3. Target-tracking scaling policy (e.g., keep average CPU at 40%)
```bash
aws autoscaling put-scaling-policy \
  --auto-scaling-group-name $ASG_NAME \
  --policy-name cpu-target-tracking \
  --policy-type TargetTrackingScaling \
  --target-tracking-configuration '{"PredefinedMetricSpecification":{"PredefinedMetricType":"ASGAverageCPUUtilization"},"TargetValue":40.0}' \
  --region $REGION
```

### 4. Step-scaling policy (scale more aggressively on spikes)
Create CloudWatch alarm that triggers a step-scaling action:
```bash
# create alarm (high CPU)
aws cloudwatch put-metric-alarm \
  --alarm-name ${ASG_NAME}-HighCPU \
  --metric-name CPUUtilization --namespace AWS/EC2 --statistic Average \
  --period 60 --evaluation-periods 2 --threshold 70 --comparison-operator GreaterThanThreshold \
  --dimensions Name=AutoScalingGroupName,Value=$ASG_NAME \
  --alarm-actions <step-scaling-policy-arn> \
  --region $REGION
```
Define step-scaling policy with adjustments for thresholds via autoscaling put-scaling-policy (StepScaling type).

### 5. Scheduled scaling (increase capacity during predictable load)
```bash
aws autoscaling put-scheduled-update-group-action \
  --auto-scaling-group-name $ASG_NAME \
  --scheduled-action-name scale-up-morning \
  --start-time "2025-11-11T08:00:00Z" \
  --min-size 2 --desired-capacity 2 --max-size $MAX_SIZE \
  --region $REGION
```

### 6. Configure lifecycle hooks and health checks
Lifecycle hook example:
```bash
aws autoscaling put-lifecycle-hook \
  --lifecycle-hook-name pause-before-terminate \
  --auto-scaling-group-name $ASG_NAME \
  --lifecycle-transition autoscaling:EC2_INSTANCE_TERMINATING \
  --heartbeat-timeout 300 \
  --default-result CONTINUE \
  --region $REGION
```
Set ASG health check type & grace period:
```bash
aws autoscaling update-auto-scaling-group --auto-scaling-group-name $ASG_NAME --health-check-type ELB --health-check-grace-period 60 --region $REGION
```

### 7. Custom metrics and CloudWatch
Publish a custom metric from an instance (example using AWS CLI or CloudWatch agent). Example (push from local CLI for testing):
```bash
aws cloudwatch put-metric-data --metric-name RequestsPerMinute --namespace Lab/ASG --value 120 --dimensions AutoScalingGroupName=$ASG_NAME --region $REGION
```
Create CloudWatch alarm on custom metric and attach to scaling policy.

### 8. Test scaling behavior
- Generate load (e.g., curl loop against ALB or instance IP) to raise CPU or custom metric.
- Observe CloudWatch metrics and alarms.
- Verify ASG scales out/in per configured policies and respects cooldowns and health checks.
- Check instance lifecycle events (launch/terminate) in ASG and EC2 console.

### 9. Monitor and verify
Useful commands:
```bash
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names $ASG_NAME --region $REGION
aws cloudwatch describe-alarms --alarm-name-prefix ${ASG_NAME} --region $REGION
aws autoscaling describe-scaling-activities --auto-scaling-group-name $ASG_NAME --region $REGION
```

---

## Validation Checklist
- [ ] Launch Template created with user-data
- [ ] ASG spans multiple AZs and correct subnets
- [ ] Target-tracking policy active and maintaining target metric
- [ ] Step-scaling or alarm-backed scaling configured
- [ ] Scheduled scaling action created
- [ ] CloudWatch alarms firing as expected under load
- [ ] Lifecycle hooks and health checks configured and tested
- [ ] Instances launch, register with target group (if used), and terminate cleanly

## Cleanup
```bash
# delete scheduled actions
aws autoscaling delete-scheduled-action --auto-scaling-group-name $ASG_NAME --scheduled-action-name scale-up-morning --region $REGION || true

# delete scaling policies (use policy ARNs)
aws autoscaling delete-policy --auto-scaling-group-name $ASG_NAME --policy-name cpu-target-tracking --region $REGION || true

# remove lifecycle hooks
aws autoscaling delete-lifecycle-hook --lifecycle-hook-name pause-before-terminate --auto-scaling-group-name $ASG_NAME --region $REGION || true

# delete ASG (set desired capacity to 0 first)
aws autoscaling update-auto-scaling-group --auto-scaling-group-name $ASG_NAME --min-size 0 --desired-capacity 0 --region $REGION
aws autoscaling delete-auto-scaling-group --auto-scaling-group-name $ASG_NAME --force-delete --region $REGION

# delete launch template
aws ec2 delete-launch-template --launch-template-name $LAUNCH_TEMPLATE_NAME --region $REGION
```

## Best practices
- Use target-tracking for common metrics (CPU, ALB request count).
- Use warm-up and grace periods to avoid flapping.
- Prefer application-level or ALB request-based metrics for more stable autoscaling.
- Test policies under controlled load before production.
- Use CloudWatch Logs/Events for auditing scaling activities.

## Summary
This lab configures ASG scaling policies driven by CloudWatch alarms and metrics, covering target-tracking, step, and scheduled scaling, lifecycle hooks, and validation steps to ensure reliable autoscaling behavior.
