# Lab 1.A: Deploy a Linux EC2 Instance in a Custom VPC

## Overview
This lab walks you through creating a custom VPC, subnet, internet gateway, route table, security group, key pair, and launching a Linux EC2 instance using the AWS CLI. You will verify networking, connect via SSH, and deploy a simple web server automatically using EC2 user data.

## Objectives
- Create a custom VPC with a public subnet  
- Configure Internet Gateway and route table for public access  
- Create a security group allowing SSH and HTTP  
- Launch a Linux EC2 instance bootstrapped with a web server  
- Update the default web page with a custom website directory  
- Clean up resources  

## Prerequisites
- AWS CLI configured (`aws configure`) or AWS Console access  
- AWS account with permissions to create VPC, EC2, and IAM resources  
- Local SSH client and SCP tool installed  

## Architecture (High Level)
- VPC (CIDR): `10.0.0.0/16`  
- Public Subnet (CIDR): `10.0.1.0/24`  
- Internet Gateway attached to VPC  
- Route table with `0.0.0.0/0 → IGW` for public subnet  
- EC2 instance in public subnet with public IPv4 and HTTP access  

---

## Steps (CLI + Console Examples)

### 1. Create VPC and Public Subnet

```bash
# Create VPC and capture VPC ID
VPC_ID=$(
  aws ec2 create-vpc \
    --cidr-block 10.0.0.0/16 \
    --query 'Vpc.VpcId' \
    --output text
)

# Tag the VPC with a name
aws ec2 create-tags \
  --resources "$VPC_ID" \
  --tags Key=Name,Value=lab-vpc

# Query availability zones and pick first
AZ=$(
  aws ec2 describe-availability-zones \
    --query 'AvailabilityZones[0].ZoneName' \
    --output text
)

# Create subnet in the VPC and get subnet ID
SUBNET_ID=$(
  aws ec2 create-subnet \
    --vpc-id "$VPC_ID" \
    --cidr-block 10.0.1.0/24 \
    --availability-zone "$AZ" \
    --query 'Subnet.SubnetId' \
    --output text
)

# Enable auto-assign public IPv4 on subnet
aws ec2 modify-subnet-attribute \
  --subnet-id "$SUBNET_ID" \
  --map-public-ip-on-launch

# Create Internet Gateway and get Gateway ID
IGW_ID=$(
  aws ec2 create-internet-gateway \
    --query 'InternetGateway.InternetGatewayId' \
    --output text
)

# Attach Internet Gateway to VPC
aws ec2 attach-internet-gateway \
  --internet-gateway-id "$IGW_ID" \
  --vpc-id "$VPC_ID"

# Create a route table for the VPC and get table ID
RTB_ID=$(
  aws ec2 create-route-table \
    --vpc-id "$VPC_ID" \
    --query 'RouteTable.RouteTableId' \
    --output text
)

# Create route to Internet Gateway
aws ec2 create-route \
  --route-table-id "$RTB_ID" \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id "$IGW_ID"

# Associate route table with subnet
aws ec2 associate-route-table \
  --route-table-id "$RTB_ID" \
  --subnet-id "$SUBNET_ID"
```

**Console alternative:**  
VPC → Create VPC (10.0.0.0/16) → Subnet (10.0.1.0/24, Enable Auto-assign IPv4) → Create IGW → Attach → Route Table 0.0.0.0/0 → IGW.

---

### 2. Create a Key Pair

```bash
# Create an EC2 key pair and save PEM locally
aws ec2 create-key-pair \
  --key-name lab-key \
  --query 'KeyMaterial' \
  --output text > lab-key.pem

# Set file permissions for the private key
chmod 600 lab-key.pem
```

**Console alternative:** EC2 → Key Pairs → Create key pair → Download PEM.

---

### 3. Create Security Group Allowing SSH and HTTP

```bash
# Create security group in the VPC and capture ID
SG_ID=$(
  aws ec2 create-security-group \
    --group-name lab-sg \
    --description "SSH+HTTP" \
    --vpc-id "$VPC_ID" \
    --query 'GroupId' \
    --output text
)

# Allow SSH from your IP (replace <your-ip>/32)
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr <your-ip>/32

# Allow HTTP from anywhere
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0
```

> 💡 *For better security, restrict SSH to your public IP using `--cidr <your-ip>/32`.*

---

### 4. Launch EC2 Instance and Bootstrap Web Server (via User Data File)

```bash
# Create user-data script to bootstrap Apache HTTP server
cat > user-data.txt <<'EOF'
#!/bin/bash
yum update -y
yum install -y httpd
systemctl enable httpd
systemctl start httpd
echo "Hello from Lab 1.A - EC2 in VPC" > /var/www/html/index.html
EOF
```

```bash
# Find latest Amazon Linux 2 AMI
AMI_ID=$(
  aws ec2 describe-images \
    --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" "Name=state,Values=available" \
    --owners amazon \
    --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
    --output text
)
```

```bash
# Run EC2 instance (do not capture instance id here)
aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t3.micro \
  --key-name lab-key \
  --security-group-ids "$SG_ID" \
  --subnet-id "$SUBNET_ID" \
  --associate-public-ip-address \
  --user-data file://user-data.txt \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=lab-ec2}]' \
  --output json
```

```bash
# Retrieve instance id by filtering for Name=lab-ec2 and running/pending states
INSTANCE_ID=$(
  aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=lab-ec2" "Name=instance-state-name,Values=pending,running" \
    --query 'Reservations[].Instances[].InstanceId' \
    --output text | awk '{print $1}'
)
```

```bash
# Wait until the instance is in running state
aws ec2 wait instance-running \
  --instance-ids "$INSTANCE_ID"
```

```bash
# Get the public IP address of the instance
PUBLIC_IP=$(
  aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text
)

# Print the web server URL
echo "Web server ready at: http://$PUBLIC_IP"
```

---

### 5. Upload a Custom Website and Replace Default Page

1. **Verify SSH access**

```bash
# SSH to the EC2 instance as ec2-user
ssh -i lab-key.pem ec2-user@"$PUBLIC_IP"
```

Inside the instance:

```bash
# Check local web server via localhost
curl http://localhost
```

You should see: `Hello from Lab 1.A – EC2 in VPC`

2. **On your local machine**, create website files:

```bash
# Create local website directory and index page
mkdir -p website
cat > website/index.html <<'HTML'
<html>
  <h1>Welcome to My Custom Website</h1>
  <p>Deployed via SCP in Lab 1.A</p>
</html>
HTML
```

3. **Copy the directory to EC2 using SCP:**

```bash
# Copy website directory to /tmp on EC2
scp -i lab-key.pem -r website ec2-user@"$PUBLIC_IP":/tmp/
```

4. **SSH into the instance and replace the web root:**

```bash
# Connect and replace web root with uploaded site
ssh -i lab-key.pem ec2-user@"$PUBLIC_IP"
sudo rm -rf /var/www/html/*
sudo cp -r /tmp/website/* /var/www/html/
sudo systemctl restart httpd
exit
```

5. **Open the site in the workspace host's default browser:**

```bash
# Open public IP in host browser
"$BROWSER" "http://$PUBLIC_IP"
```

---

### 6. Validation Checklist

- [ ] VPC `10.0.0.0/16` created  
- [ ] Public subnet `10.0.1.0/24` with public IP enabled  
- [ ] Internet Gateway attached and route table configured  
- [ ] Security group allows SSH (22) and HTTP (80)  
- [ ] EC2 instance reachable via SSH  
- [ ] Default web server page visible  
- [ ] Custom website successfully deployed and served  

---

### 7. Cleanup (Avoid Charges)

```bash
# Terminate the EC2 instance
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_ID"

# Wait for termination
aws ec2 wait instance-terminated \
  --instance-ids "$INSTANCE_ID"

# Remove local key file and delete key pair in AWS
rm -f lab-key.pem
aws ec2 delete-key-pair \
  --key-name lab-key

# Delete the security group
aws ec2 delete-security-group \
  --group-id "$SG_ID"
```

```bash
# Disassociate and delete route table associations, then delete route table
RTB_ASSOC_IDS=$(
  aws ec2 describe-route-tables \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query 'RouteTables[].Associations[].RouteTableAssociationId' \
    --output text
)
for a in $RTB_ASSOC_IDS; do
  # disassociate each association if present
  aws ec2 disassociate-route-table \
    --association-id "$a" || true
done

# Delete route table (ignore failure)
aws ec2 delete-route-table \
  --route-table-id "$RTB_ID" || true
```

```bash
# Detach and delete internet gateway
aws ec2 detach-internet-gateway \
  --internet-gateway-id "$IGW_ID" \
  --vpc-id "$VPC_ID" || true

aws ec2 delete-internet-gateway \
  --internet-gateway-id "$IGW_ID" || true
```

```bash
# Delete subnet and VPC
aws ec2 delete-subnet \
  --subnet-id "$SUBNET_ID"

aws ec2 delete-vpc \
  --vpc-id "$VPC_ID"
```

> ⚠️ Prompt before cleanup:
```bash
read -p "Proceed with cleanup (y/n)? " confirm && [[ $confirm == [yY] ]] || exit 1
```

## Summary
This lab demonstrates how to build a custom VPC from scratch, launch a Linux EC2 instance, and use user data to bootstrap a web server automatically.  
You also learned how to upload and serve a custom website via `scp`, reinforcing networking, security, and automation concepts in AWS EC2 and VPC environments.
