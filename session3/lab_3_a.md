# Lab 3.A: VPC Fundamentals and Networking

## Overview
This lab introduces Amazon Virtual Private Cloud (VPC), which allows you to provision a logically isolated section of AWS cloud. You'll learn how to design and implement custom network architectures, configure subnets across availability zones, and control traffic flow with routing tables and network ACLs.

## Objectives
- Create a custom VPC with CIDR block planning
- Configure public and private subnets across multiple AZs
- Set up Internet Gateway for public internet access
- Configure route tables for traffic control
- Implement Network ACLs for subnet-level security
- Understand the difference between security groups and NACLs

## Requirements
- AWS account with VPC permissions
- Understanding of IP addressing and CIDR notation
- Basic networking knowledge (subnets, routing, firewalls)
- Familiarity with EC2 instances

## Steps

### Step 1: Plan Your VPC Architecture
1. Design considerations:
   - VPC CIDR: 10.0.0.0/16 (65,536 IP addresses)
   - Public Subnet 1: 10.0.1.0/24 (AZ-1, 256 IPs)
   - Public Subnet 2: 10.0.2.0/24 (AZ-2, 256 IPs)
   - Private Subnet 1: 10.0.10.0/24 (AZ-1, 256 IPs)
   - Private Subnet 2: 10.0.11.0/24 (AZ-2, 256 IPs)

### Step 2: Create a VPC
1. Navigate to VPC Dashboard
2. Click "Create VPC"
3. Select "VPC only"
4. Configure:
   - Name tag: `lab-vpc`
   - IPv4 CIDR block: `10.0.0.0/16`
   - IPv6 CIDR block: No IPv6
   - Tenancy: Default
5. Create VPC
6. Enable DNS hostnames:
   - Select the VPC
   - Actions → Edit DNS hostnames → Enable

### Step 3: Create Subnets
1. Navigate to Subnets → Create subnet
2. Create Public Subnet 1:
   - VPC: `lab-vpc`
   - Subnet name: `public-subnet-1`
   - Availability Zone: Choose first AZ (e.g., us-east-1a)
   - IPv4 CIDR: `10.0.1.0/24`
3. Create Public Subnet 2:
   - Subnet name: `public-subnet-2`
   - Availability Zone: Choose second AZ (e.g., us-east-1b)
   - IPv4 CIDR: `10.0.2.0/24`
4. Create Private Subnet 1:
   - Subnet name: `private-subnet-1`
   - Availability Zone: Same as public-subnet-1
   - IPv4 CIDR: `10.0.10.0/24`
5. Create Private Subnet 2:
   - Subnet name: `private-subnet-2`
   - Availability Zone: Same as public-subnet-2
   - IPv4 CIDR: `10.0.11.0/24`

### Step 4: Create and Attach Internet Gateway
1. Navigate to Internet Gateways → Create internet gateway
2. Name: `lab-igw`
3. Create internet gateway
4. Attach to VPC:
   - Select the IGW
   - Actions → Attach to VPC
   - Select `lab-vpc`
   - Attach

### Step 5: Configure Route Tables
1. **Create Public Route Table:**
   - Navigate to Route Tables → Create route table
   - Name: `public-rt`
   - VPC: `lab-vpc`
   - Create
   
2. **Add Internet Gateway Route:**
   - Select `public-rt`
   - Routes tab → Edit routes
   - Add route: Destination `0.0.0.0/0`, Target: `lab-igw`
   - Save

3. **Associate Public Subnets:**
   - Subnet associations tab → Edit subnet associations
   - Select `public-subnet-1` and `public-subnet-2`
   - Save

4. **Create Private Route Table:**
   - Create route table
   - Name: `private-rt`
   - VPC: `lab-vpc`
   - Associate with `private-subnet-1` and `private-subnet-2`

### Step 6: Enable Auto-assign Public IP for Public Subnets
1. Select `public-subnet-1`
2. Actions → Edit subnet settings
3. Enable "Auto-assign public IPv4 address"
4. Save
5. Repeat for `public-subnet-2`

### Step 7: Configure Network ACLs
1. Navigate to Network ACLs
2. Find the default NACL for `lab-vpc`
3. Create custom NACL:
   - Name: `public-nacl`
   - VPC: `lab-vpc`
4. Configure inbound rules:
   - Rule 100: HTTP (80), Source: 0.0.0.0/0, Allow
   - Rule 110: HTTPS (443), Source: 0.0.0.0/0, Allow
   - Rule 120: SSH (22), Source: 0.0.0.0/0, Allow
   - Rule 130: Ephemeral ports (1024-65535), Source: 0.0.0.0/0, Allow
5. Configure outbound rules:
   - Rule 100: All traffic, Destination: 0.0.0.0/0, Allow
6. Associate with public subnets

### Step 8: Test the VPC Configuration
1. Launch EC2 instance in public subnet:
   - AMI: Amazon Linux 2023
   - Instance type: t2.micro
   - Network: `lab-vpc`
   - Subnet: `public-subnet-1`
   - Auto-assign public IP: Enable
   - Security group: Allow SSH from My IP
2. Connect via SSH and verify internet connectivity:
   ```bash
   ping -c 4 google.com
   curl http://checkip.amazonaws.com
   ```
3. Launch instance in private subnet:
   - Same configuration but subnet: `private-subnet-1`
   - No public IP assigned
4. Attempt connection (should fail without bastion host)

## Validation
- [ ] VPC created with correct CIDR block
- [ ] Four subnets created across two availability zones
- [ ] Internet Gateway attached to VPC
- [ ] Route tables configured correctly
- [ ] Public subnets can reach the internet
- [ ] Private subnets are isolated from direct internet access
- [ ] Network ACLs configured and associated
- [ ] EC2 instance in public subnet has internet connectivity

## Cleanup
1. Terminate all EC2 instances in the VPC
2. Delete NAT Gateways (if created in optional steps)
3. Release Elastic IPs (if allocated)
4. Delete custom Network ACLs
5. Delete route tables (except main)
6. Detach and delete Internet Gateway
7. Delete subnets
8. Delete VPC
9. Verify all resources removed in VPC Dashboard

## Summary
In this lab, you built a production-ready VPC architecture with public and private subnets across multiple availability zones. You configured routing tables to control traffic flow, attached an Internet Gateway for public internet access, and implemented network ACLs for subnet-level security. This foundation is essential for deploying secure, scalable applications on AWS.

**Key Takeaways:**
- VPCs provide network isolation and control in AWS
- Plan CIDR blocks carefully to avoid IP address conflicts
- Use multiple availability zones for high availability
- Public subnets have routes to Internet Gateway
- Private subnets should not have direct internet access
- Network ACLs are stateless, security groups are stateful
- Always follow the principle of least privilege in network design
- Route table associations determine subnet behavior
