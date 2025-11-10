# Lab 1.A: Deploy a Linux EC2 instance in a custom VPC

## Overview
This lab walks through creating a custom VPC, subnets, internet gateway, route table, security group, key pair, and launching a Linux EC2 instance. You will verify networking and SSH access and deploy a simple web server.

## Objectives
- Create a custom VPC with public subnet
- Configure Internet Gateway and route table for public access
- Create a security group allowing SSH and HTTP
- Launch a Linux EC2 instance with an EC2 role (optional)
- Verify SSH connectivity and serve a simple web page
- Clean up resources

## Prerequisites
- AWS CLI configured (aws configure) or AWS Console access
- AWS account with permissions to create VPC, EC2, IAM resources
- Local SSH client

## Architecture (high level)
- VPC (CIDR): 10.0.0.0/16
- Public subnet (CIDR): 10.0.1.0/24
- Internet Gateway attached to VPC
- Route table with 0.0.0.0/0 -> IGW for public subnet
- EC2 instance in public subnet with public IPv4

---

## Steps (Console & CLI examples)

### 1. Create VPC and public subnet (CLI)
Replace placeholders where applicable.

```bash
# create VPC
VPC_ID=$(aws ec2 create-vpc --cidr-block 10.0.0.0/16 --query 'Vpc.VpcId' --output text)
aws ec2 create-tags --resources $VPC_ID --tags Key=Name,Value=lab-vpc

# create public subnet
SUBNET_ID=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.1.0/24 --availability-zone $(aws ec2 describe-availability-zones --query 'AvailabilityZones[0].ZoneName' --output text) --query 'Subnet.SubnetId' --output text)
aws ec2 modify-subnet-attribute --subnet-id $SUBNET_ID --map-public-ip-on-launch

# create internet gateway and attach
IGW_ID=$(aws ec2 create-internet-gateway --query 'InternetGateway.InternetGatewayId' --output text)
aws ec2 attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID

# create route table and route
RTB_ID=$(aws ec2 create-route-table --vpc-id $VPC_ID --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id $RTB_ID --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID
aws ec2 associate-route-table --route-table-id $RTB_ID --subnet-id $SUBNET_ID
```

Console alternative:
- VPC > Create VPC (10.0.0.0/16) > Create subnet (10.0.1.0/24) and enable "Auto-assign Public IPv4".
- Create Internet Gateway > Attach to VPC.
- Route Tables > create or edit route table for VPC, add route 0.0.0.0/0 -> IGW, associate with public subnet.

### 2. Create a key pair (CLI)
```bash
aws ec2 create-key-pair --key-name lab-key --query 'KeyMaterial' --output text > lab-key.pem
chmod 600 lab-key.pem
```
Or use Console: EC2 > Key Pairs > Create key pair and download PEM.

### 3. Create Security Group allowing SSH and HTTP
CLI:
```bash
SG_ID=$(aws ec2 create-security-group --group-name lab-sg --description "SSH+HTTP" --vpc-id $VPC_ID --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 22 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0
```
Console: EC2 > Security Groups > Create security group in your VPC, add inbound rules for SSH (22) and HTTP (80).

### 4. (Optional) Create an IAM role for EC2
If the instance needs AWS access (e.g., S3), create an instance profile role:
- Console: IAM > Roles > Create role > AWS service > EC2 > Attach policy (e.g., AmazonS3ReadOnlyAccess) > Name it lab-ec2-role
- Or use iam-create-role and instance-profile CLI flows.

### 5. Launch EC2 instance
Choose an Amazon Linux 2 AMI (or preferred distro). CLI example:

```bash
AMI_ID=$(aws ec2 describe-images --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" "Name=state,Values=available" --owners amazon --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' --output text)

INSTANCE_ID=$(aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type t3.micro \
  --key-name lab-key \
  --security-group-ids $SG_ID \
  --subnet-id $SUBNET_ID \
  --associate-public-ip-address \
  --count 1 \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=lab-ec2}]" \
  --query 'Instances[0].InstanceId' --output text)

# optional: attach instance profile
# aws ec2 associate-iam-instance-profile --instance-id $INSTANCE_ID --iam-instance-profile Name=lab-ec2-role
```

Wait until instance is running:
```bash
aws ec2 wait instance-running --instance-ids $INSTANCE_ID
PUBLIC_IP=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "Instance public IP: $PUBLIC_IP"
```

### 6. Bootstrap web server via user data (optional)
When launching, you can add user-data to install and start a web server:
```bash
USER_DATA='#!/bin/bash
yum update -y
yum install -y httpd
systemctl enable httpd
systemctl start httpd
echo "Hello from Lab 1.A - EC2 in VPC" > /var/www/html/index.html
'
# pass --user-data "$(echo "$USER_DATA" | base64 --wrap=0)" or use --user-data file://user-data.txt in run-instances
```

### 7. SSH and verify HTTP
SSH:
```bash
ssh -i lab-key.pem ec2-user@$PUBLIC_IP
# inside instance: curl http://localhost or exit to check from your machine:
curl http://$PUBLIC_IP
```
You should see the sample page content.

### 8. Validation Checklist
- [ ] VPC 10.0.0.0/16 created
- [ ] Public subnet 10.0.1.0/24 created and auto-assign public IP enabled
- [ ] Internet Gateway attached and route table has 0.0.0.0/0 -> IGW
- [ ] Security group allows SSH (22) and HTTP (80)
- [ ] EC2 instance launched and reachable via SSH
- [ ] Web server responding on HTTP

### 9. Cleanup
Remove resources to avoid charges.

```bash
# terminate instance
aws ec2 terminate-instances --instance-ids $INSTANCE_ID
aws ec2 wait instance-terminated --instance-ids $INSTANCE_ID

# delete key pair (local file and EC2 key metadata)
rm -f lab-key.pem
aws ec2 delete-key-pair --key-name lab-key

# delete security group
aws ec2 delete-security-group --group-id $SG_ID

# delete route table association (if needed), route table, and internet gateway
# Note: adjust association and IDs as necessary
RTB_ASSOC_IDS=$(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" --query 'RouteTables[].Associations[].RouteTableAssociationId' --output text)
for a in $RTB_ASSOC_IDS; do
  aws ec2 disassociate-route-table --association-id $a || true
done
aws ec2 delete-route-table --route-table-id $RTB_ID || true
aws ec2 detach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID || true
aws ec2 delete-internet-gateway --internet-gateway-id $IGW_ID || true

# delete subnet and VPC
aws ec2 delete-subnet --subnet-id $SUBNET_ID
aws ec2 delete-vpc --vpc-id $VPC_ID
```

Notes:
- Replace resource IDs and variables if you used different names.
- If you used Console, delete resources via the AWS Console for simplicity.
- Verify billing implications and ensure you terminate/delete all resources.

## Summary
This lab demonstrates how to create networking primitives and launch a publicly accessible EC2 Linux instance inside a custom VPC, including securing access via security groups and optionally bootstrapping a web server.
