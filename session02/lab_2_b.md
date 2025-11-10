# Lab 2.B: EC2 Auto Scaling and Load Balancing

## Overview
This lab explores advanced EC2 features including Elastic Load Balancing (ELB) and Auto Scaling. You'll learn how to build highly available and scalable architectures that automatically adjust capacity based on demand. These are critical skills for production-grade AWS deployments.

## Objectives
- Create and configure an Application Load Balancer
- Set up target groups for load balancing
- Create launch templates for Auto Scaling
- Configure Auto Scaling groups with scaling policies
- Test automatic scaling behavior
- Implement health checks and self-healing

## Requirements
- Completed Lab 2.A or equivalent EC2 knowledge
- Understanding of load balancing concepts
- Familiarity with CloudWatch metrics
- VPC with multiple availability zones
- AWS account with EC2 and Auto Scaling permissions

## Steps

### Step 1: Create a Launch Template
1. Navigate to EC2 Dashboard → Launch Templates
2. Click "Create launch template"
3. Configure:
   - Name: `web-app-template`
   - Description: "Template for auto-scaled web servers"
   - AMI: Amazon Linux 2023 AMI
   - Instance type: t2.micro
   - Key pair: Create or select existing
4. Configure network settings:
   - Security group: Create new or use existing (allow HTTP, HTTPS, SSH)
5. Add user data:
   ```bash
   #!/bin/bash
   yum update -y
   yum install -y httpd
   systemctl start httpd
   systemctl enable httpd
   INSTANCE_ID=$(ec2-metadata --instance-id | cut -d " " -f 2)
   echo "<h1>Server: $INSTANCE_ID</h1>" > /var/www/html/index.html
   ```
6. Create launch template

### Step 2: Create Target Group
1. Navigate to EC2 Dashboard → Target Groups
2. Click "Create target group"
3. Configure:
   - Target type: Instances
   - Target group name: `web-app-tg`
   - Protocol: HTTP, Port: 80
   - VPC: Default VPC
4. Configure health checks:
   - Protocol: HTTP
   - Path: `/`
   - Healthy threshold: 2
   - Unhealthy threshold: 2
   - Timeout: 5 seconds
   - Interval: 30 seconds
5. Create target group (don't register targets yet)

### Step 3: Create Application Load Balancer
1. Navigate to Load Balancers → Create Load Balancer
2. Select "Application Load Balancer"
3. Configure:
   - Name: `web-app-alb`
   - Scheme: Internet-facing
   - IP address type: IPv4
4. Network mapping:
   - VPC: Default VPC
   - Select at least 2 availability zones
5. Security groups:
   - Create new security group allowing HTTP (80) and HTTPS (443) from anywhere
6. Listeners and routing:
   - Protocol: HTTP, Port: 80
   - Default action: Forward to `web-app-tg`
7. Create load balancer
8. Wait for load balancer state to become "Active"

### Step 4: Create Auto Scaling Group
1. Navigate to Auto Scaling Groups
2. Click "Create Auto Scaling group"
3. Step 1 - Choose launch template:
   - Name: `web-app-asg`
   - Launch template: `web-app-template`
4. Step 2 - Choose instance launch options:
   - VPC: Default VPC
   - Availability Zones: Select 2 or more AZs
5. Step 3 - Configure advanced options:
   - Load balancing: Attach to existing load balancer
   - Choose from load balancer target groups: `web-app-tg`
   - Health checks: Enable ELB health checks
   - Health check grace period: 300 seconds
6. Step 4 - Configure group size and scaling:
   - Desired capacity: 2
   - Minimum capacity: 1
   - Maximum capacity: 4
7. Step 5 - Add scaling policies:
   - Select "Target tracking scaling policy"
   - Metric type: Average CPU utilization
   - Target value: 50
   - Instances need: 300 seconds warm up
8. Add notifications (optional)
9. Add tags:
   - Key: `Environment`, Value: `Lab`
10. Review and create Auto Scaling group

### Step 5: Verify Auto Scaling Deployment
1. Wait for instances to launch (check Auto Scaling group "Activity" tab)
2. Verify instances are healthy in target group:
   - Navigate to Target Groups → `web-app-tg`
   - Check "Targets" tab
   - Status should show "healthy" for all instances
3. Copy the Load Balancer DNS name
4. Test in browser: `http://<load-balancer-dns>`
5. Refresh multiple times to see requests distributed across instances

### Step 6: Test Auto Scaling Behavior
1. **Test Scale-Out:**
   - Connect to one of the EC2 instances via SSH
   - Generate CPU load:
     ```bash
     sudo yum install -y stress
     sudo stress --cpu 4 --timeout 600
     ```
   - Monitor CloudWatch metrics for CPU utilization
   - Wait 5-10 minutes for scale-out to trigger
   - Verify new instances launching in Auto Scaling group

2. **Test Scale-In:**
   - Stop the stress test
   - Wait for CPU utilization to drop below 50%
   - Monitor Auto Scaling group for scale-in activity
   - Verify excess instances are terminated

### Step 7: Test Health Check and Self-Healing
1. Select one instance in the target group
2. Stop the instance manually:
   - EC2 → Instances → Select instance → Stop
3. Observe Auto Scaling behavior:
   - Health check should fail
   - Auto Scaling launches replacement instance
   - New instance registers with target group
4. Monitor the "Activity" tab in Auto Scaling group

### Step 8: Configure CloudWatch Alarms (Optional)
1. Navigate to CloudWatch → Alarms
2. Create alarm for high CPU:
   - Metric: EC2 → By Auto Scaling Group → CPUUtilization
   - Threshold: Greater than 75%
   - Actions: Send SNS notification
3. Create alarm for unhealthy targets:
   - Metric: ApplicationELB → UnHealthyHostCount
   - Threshold: Greater than 0

## Validation
- [ ] Launch template created with proper configuration
- [ ] Application Load Balancer is active and healthy
- [ ] Target group has healthy instances registered
- [ ] Auto Scaling group maintains desired capacity
- [ ] Load balancer distributes traffic across instances
- [ ] Auto Scaling responds to CPU load by scaling out
- [ ] Auto Scaling scales in when load decreases
- [ ] Self-healing replaces unhealthy instances automatically

## Cleanup
1. Delete Auto Scaling group:
   - Set desired, minimum, and maximum capacity to 0
   - Wait for instances to terminate
   - Delete the Auto Scaling group
2. Delete Load Balancer:
   - EC2 → Load Balancers → Select ALB → Delete
3. Delete Target Group:
   - EC2 → Target Groups → Select → Delete
4. Delete Launch Template:
   - EC2 → Launch Templates → Select → Delete
5. Delete security groups created for this lab
6. Verify all resources are removed

## Summary
In this lab, you built a highly available and scalable web application infrastructure using EC2 Auto Scaling and Application Load Balancer. You learned how to automatically distribute traffic across multiple instances, scale capacity based on demand, and implement self-healing architectures. These patterns are fundamental to building resilient, production-grade applications on AWS.

**Key Takeaways:**
- Load balancers distribute traffic across multiple instances for high availability
- Auto Scaling automatically adjusts capacity based on demand or schedule
- Target groups define health check criteria and routing rules
- Launch templates provide consistent instance configuration
- CloudWatch metrics trigger scaling policies
- Auto Scaling provides self-healing by replacing unhealthy instances
- Always use multiple availability zones for fault tolerance
- Proper health check configuration is critical for reliability
