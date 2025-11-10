# Lab 2.A: Launching and Managing EC2 Instances

## Overview
This lab introduces Amazon Elastic Compute Cloud (EC2), AWS's primary compute service. You'll learn how to launch, configure, and manage virtual servers in the cloud. This hands-on experience covers instance types, storage options, security groups, and basic instance management operations.

## Objectives
- Launch EC2 instances using the AWS Console
- Select appropriate instance types and AMIs
- Configure security groups for network access
- Connect to instances using SSH/RDP
- Monitor instance metrics and logs
- Understand EC2 pricing models

## Requirements
- AWS account with EC2 permissions
- SSH client (Terminal for Mac/Linux, PuTTY for Windows)
- Basic understanding of Linux command line
- Completed IAM labs or equivalent knowledge
- Key pair for SSH access

## Steps

### Step 1: Create a Key Pair
1. Navigate to EC2 Dashboard
2. Click on "Key Pairs" under "Network & Security"
3. Click "Create key pair"
4. Configure:
   - Name: `my-lab-keypair`
   - Key pair type: RSA
   - Private key file format: .pem (for Mac/Linux) or .ppk (for Windows/PuTTY)
5. Download and save the key pair securely
6. Set appropriate permissions (Mac/Linux):
   ```bash
   chmod 400 my-lab-keypair.pem
   ```

### Step 2: Create a Security Group
1. In EC2 Dashboard, click "Security Groups"
2. Click "Create security group"
3. Configure:
   - Name: `web-server-sg`
   - Description: "Security group for web server lab"
   - VPC: Default VPC
4. Add inbound rules:
   - Type: SSH, Port: 22, Source: My IP
   - Type: HTTP, Port: 80, Source: Anywhere (0.0.0.0/0)
   - Type: HTTPS, Port: 443, Source: Anywhere (0.0.0.0/0)
5. Keep default outbound rules (allow all)
6. Create security group

### Step 3: Launch an EC2 Instance
1. Click "Launch instance" on EC2 Dashboard
2. Configure instance:
   - Name: `web-server-lab`
   - AMI: Amazon Linux 2023 AMI (Free tier eligible)
   - Instance type: t2.micro (Free tier eligible)
   - Key pair: Select `my-lab-keypair`
   - Network settings: Select `web-server-sg` security group
   - Configure storage: 8 GB gp3 (default)
3. Expand "Advanced details" and add user data:
   ```bash
   #!/bin/bash
   yum update -y
   yum install -y httpd
   systemctl start httpd
   systemctl enable httpd
   echo "<h1>Hello from AWS EC2!</h1>" > /var/www/html/index.html
   ```
4. Review and launch the instance

### Step 4: Connect to Your Instance
1. Wait for instance state to show "Running"
2. Select the instance and click "Connect"
3. Choose connection method:

**For SSH (Linux/Mac):**
```bash
ssh -i "my-lab-keypair.pem" ec2-user@<public-ip-address>
```

**For Session Manager (browser-based):**
- Ensure IAM role is attached (may require modification)
- Click "Connect" using Session Manager

4. Once connected, verify the web server:
   ```bash
   sudo systemctl status httpd
   curl localhost
   ```

### Step 5: Test the Web Server
1. Copy the public IP address from instance details
2. Open a browser and navigate to: `http://<public-ip-address>`
3. You should see "Hello from AWS EC2!"
4. Verify security group rules are working correctly

### Step 6: Monitor Instance Metrics
1. Select your instance in EC2 console
2. Click on "Monitoring" tab
3. Review CloudWatch metrics:
   - CPU Utilization
   - Network In/Out
   - Disk Read/Write
4. Enable detailed monitoring (note: additional charges apply)

### Step 7: Create an AMI
1. Select your instance
2. Click "Actions" → "Image and templates" → "Create image"
3. Configure:
   - Name: `web-server-image`
   - Description: "Custom AMI with Apache installed"
4. Create image
5. Monitor AMI creation status under "AMIs" in left navigation

### Step 8: Instance Management Operations
1. **Stop the instance:**
   - Actions → Instance state → Stop instance
   - Wait for state to change to "Stopped"
   - Note: Public IP may change when restarted

2. **Start the instance:**
   - Actions → Instance state → Start instance
   - Verify new public IP address

3. **Reboot the instance:**
   - Actions → Instance state → Reboot instance

## Validation
- [ ] EC2 instance launched successfully
- [ ] Security group configured with correct rules
- [ ] Successfully connected to instance via SSH
- [ ] Web server accessible from browser
- [ ] CloudWatch metrics visible in console
- [ ] AMI created from running instance
- [ ] Instance stop/start operations completed

## Cleanup
1. Terminate the EC2 instance:
   - Select instance
   - Actions → Instance state → Terminate instance
   - Confirm termination
2. Delete the security group `web-server-sg`
3. Deregister the AMI:
   - Navigate to AMIs
   - Select `web-server-image`
   - Actions → Deregister AMI
4. Delete associated snapshot:
   - Navigate to Snapshots
   - Find and delete the snapshot
5. Delete key pair `my-lab-keypair`
6. Verify all resources are removed

## Summary
In this lab, you gained hands-on experience with Amazon EC2, launching and managing virtual servers in the cloud. You configured security groups for network access control, connected to instances using SSH, and deployed a simple web server using user data scripts. You also learned about instance monitoring, AMI creation, and basic instance lifecycle management.

**Key Takeaways:**
- EC2 provides resizable compute capacity in the cloud
- Security groups act as virtual firewalls for instances
- User data allows automated instance configuration at launch
- AMIs enable rapid deployment of pre-configured instances
- Always terminate instances when not in use to avoid charges
- Instance states affect billing (running = charged, stopped = storage only)
- Public IPs may change unless using Elastic IPs
