# Lab 1.B: Deploy Secure Multi-EC2 Python Jokes API with ALB Path-Based Routing

<img width="1315" height="1024" alt="IMG" src="https://github.com/user-attachments/assets/b67f8928-9a7e-430b-8cd0-afab8d53128a" />

## Overview
This lab extends your previous AWS networking foundation (Lab 1.A) by deploying a **Python REST API** across **two EC2 instances**, fronted by an **Application Load Balancer (ALB)**. The ALB routes incoming requests based on the URL path:
- `/joke` → EC2 instance A (single random joke)
- `/jokes` → EC2 instance B (list of jokes)

The architecture also incorporates **enhanced security controls** using **Network ACLs (NACLs)** and **Security Groups (SGs)** to protect network traffic at multiple layers.

---

## Objectives
- Create a VPC and Public Subnet
- Configure NACLs and Security Groups for layered security
- Launch two EC2 instances running separate Flask APIs
- Deploy an Application Load Balancer (ALB) to route traffic by URL path
- Validate ALB path-based routing functionality
- Clean up resources to avoid ongoing charges

---

## Architecture Diagram (Conceptual)
```
Internet → ALB (Port 80)
      │
      ▼
+------------------------+
| AWS Cloud (VPC 10.0.0.0/16) |
|  ┌─────────────────────────────┐
|  │ Public Subnet 10.0.1.0/24   │
|  │   ┌─────────────────────┐   │
|  │   │   Network ACL       │   │
|  │   │  (Allow HTTP/SSH)   │   │
|  │   └─────────────────────┘   │
|  │      │             │        │
|  │   [EC2 A]       [EC2 B]     │
|  │  Flask /joke    Flask /jokes│
|  │  SG:5000 from ALB           │
|  │                             │
|  └─────────────────────────────┘
|     ▲                 ▲
|     │                 │
|   Target Group 1   Target Group 2
|     │                 │
|     └────── ALB Path Routing ───┘
+--------------------------------+
```

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Key Pair created (or use `lab-key.pem` from previous lab)
- IAM permissions to create EC2, ALB, and networking resources

---

## Step 1. Create VPC, Subnet, and Internet Gateway

```bash
# Create VPC and tag it
VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --query 'Vpc.VpcId' --output text)
aws ec2 create-tags --resources $VPC_ID --tags Key=Name,Value=lab-vpc
echo "VPC_ID=$VPC_ID"

# Get Availability Zone
AZ=$(aws ec2 describe-availability-zones \
  --query 'AvailabilityZones[0].ZoneName' --output text)
echo "AZ=$AZ"

# Create Subnet and tag it
SUBNET_ID=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.1.0/24 \
  --availability-zone $AZ \
  --query 'Subnet.SubnetId' --output text)
aws ec2 create-tags --resources $SUBNET_ID --tags Key=Name,Value=lab-public-subnet
echo "SUBNET_ID=$SUBNET_ID"

# Enable auto public IP assignment
aws ec2 modify-subnet-attribute --subnet-id $SUBNET_ID --map-public-ip-on-launch

# Create Internet Gateway and tag it, then attach
IGW_ID=$(aws ec2 create-internet-gateway --query 'InternetGateway.InternetGatewayId' --output text)
aws ec2 create-tags --resources $IGW_ID --tags Key=Name,Value=lab-igw
aws ec2 attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID
echo "IGW_ID=$IGW_ID"

# Create Route Table, tag it, and associate
RTB_ID=$(aws ec2 create-route-table --vpc-id $VPC_ID --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-tags --resources $RTB_ID --tags Key=Name,Value=lab-public-rtb
echo "RTB_ID=$RTB_ID"

aws ec2 create-route --route-table-id $RTB_ID --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID
aws ec2 associate-route-table --route-table-id $RTB_ID --subnet-id $SUBNET_ID
```

---

## Step 2. Create Security Groups

### ALB Security Group
```bash
# Create ALB Security Group and tag it
ALB_SG=$(aws ec2 create-security-group \
  --group-name alb-sg --description "ALB SG" --vpc-id $VPC_ID \
  --tag-specifications 'ResourceType=security-group,Tags=[{Key=Name,Value=alb-sg}]' \
  --query 'GroupId' --output text)
echo "ALB_SG=$ALB_SG"

# Allow inbound HTTP to ALB SG
aws ec2 authorize-security-group-ingress \
  --group-id $ALB_SG --protocol tcp --port 80 --cidr 0.0.0.0/0
```

### EC2 Security Group
```bash
# Create EC2 Security Group and tag it
EC2_SG=$(aws ec2 create-security-group \
  --group-name ec2-sg --description "EC2 SG" --vpc-id $VPC_ID \
  --tag-specifications 'ResourceType=security-group,Tags=[{Key=Name,Value=ec2-sg}]' \
  --query 'GroupId' --output text)
echo "EC2_SG=$EC2_SG"

# Allow inbound from ALB SG only
aws ec2 authorize-security-group-ingress \
  --group-id $EC2_SG --protocol tcp --port 5000 --source-group $ALB_SG

# Allow SSH from your IP
MY_IP=$(curl -s ifconfig.me)
echo "MY_IP=$MY_IP"
aws ec2 authorize-security-group-ingress \
  --group-id $EC2_SG --protocol tcp --port 22 --cidr ${MY_IP}/32
```

---

## Step 3. Create Network ACL

```bash
# Create NACL and tag it
NACL_ID=$(aws ec2 create-network-acl --vpc-id $VPC_ID --query 'NetworkAcl.NetworkAclId' --output text)
aws ec2 create-tags --resources $NACL_ID --tags Key=Name,Value=public-nacl
echo "NACL_ID=$NACL_ID"

# Inbound Rules
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 100 --protocol tcp --port-range From=80,To=80 --rule-action allow --cidr-block 0.0.0.0/0
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 110 --protocol tcp --port-range From=22,To=22 --rule-action allow --cidr-block ${MY_IP}/32
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 120 --protocol tcp --port-range From=1024,To=65535 --rule-action allow --cidr-block 0.0.0.0/0
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 32766 --protocol -1 --rule-action deny --cidr-block 0.0.0.0/0

# Outbound Rules
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 100 --protocol tcp --port-range From=80,To=80 --egress --rule-action allow --cidr-block 0.0.0.0/0
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 110 --protocol tcp --port-range From=443,To=443 --egress --rule-action allow --cidr-block 0.0.0.0/0
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 120 --protocol tcp --port-range From=1024,To=65535 --egress --rule-action allow --cidr-block 0.0.0.0/0

# Associate NACL with subnet
ASSOC_ID=$(aws ec2 describe-network-acls --filters Name=association.subnet-id,Values=$SUBNET_ID --query 'NetworkAcls[].Associations[].NetworkAclAssociationId' --output text)
echo "ASSOC_ID=$ASSOC_ID"
aws ec2 replace-network-acl-association --association-id $ASSOC_ID --network-acl-id $NACL_ID
```

---

## Step 4. Launch EC2 Instances (Flask APIs)

### User Data for EC2 A (/joke)
```bash
# Create user-data for EC2 A
cat > user-data-a.sh <<'EOF'
#!/bin/bash
yum update -y
yum install -y python3-pip
yum install -y git
pip3 install flask
cat > /home/ec2-user/app.py <<'APP'
from flask import Flask, jsonify
import socket
app = Flask(__name__)
@app.route('/joke')
def get_joke():
    return jsonify({
        'joke': 'Why do developers hate nature? It has too many bugs!',
        'host': socket.gethostname()
    })
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
APP
nohup python3 /home/ec2-user/app.py &
EOF
```

### User Data for EC2 B (/jokes)
```bash
# Create user-data for EC2 B
cat > user-data-b.sh <<'EOF'
#!/bin/bash
yum update -y
yum install -y python3-pip
yum install -y git
pip3 install flask
cat > /home/ec2-user/app.py <<'APP'
from flask import Flask, jsonify
import socket
app = Flask(__name__)
@app.route('/jokes')
def get_jokes():
    jokes = [
        'Why did the cloud break up with the server? It needed space.',
        'I told my computer I needed a break, and it said \'No problem, I’ll go to sleep.\'',
        'Why do Python programmers wear glasses? Because they can’t C #.'
    ]
    return jsonify({'jokes': jokes, 'host': socket.gethostname()})
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
APP
nohup python3 /home/ec2-user/app.py &
EOF
```

### Launch EC2 Instances
```bash
# Find latest Amazon Linux 2 AMI
AMI_ID=$(aws ec2 describe-images --owners amazon --filters 'Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2' 'Name=state,Values=available' --query 'Images | sort_by(@,&CreationDate) | [-1].ImageId' --output text)
echo "AMI_ID=$AMI_ID"

# Launch EC2 A and tag it
EC2A_ID=$(aws ec2 run-instances --image-id $AMI_ID --instance-type t3.micro --key-name lab-key --security-group-ids $EC2_SG --subnet-id $SUBNET_ID --associate-public-ip-address --user-data file://user-data-a.sh --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ec2-a}]' --query 'Instances[0].InstanceId' --output text)
echo "EC2A_ID=$EC2A_ID"

# Launch EC2 B and tag it
EC2B_ID=$(aws ec2 run-instances --image-id $AMI_ID --instance-type t3.micro --key-name lab-key --security-group-ids $EC2_SG --subnet-id $SUBNET_ID --associate-public-ip-address --user-data file://user-data-b.sh --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ec2-b}]' --query 'Instances[0].InstanceId' --output text)
echo "EC2B_ID=$EC2B_ID"

aws ec2 wait instance-running --instance-ids $EC2A_ID $EC2B_ID
```

---

## Step 5. Create ALB and Target Groups
```bash
# Create ALB and tag it
ALB_ARN=$(aws elbv2 create-load-balancer --name jokes-alb --subnets $SUBNET_ID --security-groups $ALB_SG --query 'LoadBalancers[0].LoadBalancerArn' --output text)
echo "ALB_ARN=$ALB_ARN"

# Create Target Groups and tag them
TG1_ARN=$(aws elbv2 create-target-group --name tg-joke --protocol HTTP --port 5000 --vpc-id $VPC_ID --target-type instance --query 'TargetGroups[0].TargetGroupArn' --output text)
echo "TG1_ARN=$TG1_ARN"
TG2_ARN=$(aws elbv2 create-target-group --name tg-jokes --protocol HTTP --port 5000 --vpc-id $VPC_ID --target-type instance --query 'TargetGroups[0].TargetGroupArn' --output text)
echo "TG2_ARN=$TG2_ARN"

aws elbv2 register-targets --target-group-arn $TG1_ARN --targets Id=$EC2A_ID
aws elbv2 register-targets --target-group-arn $TG2_ARN --targets Id=$EC2B_ID

# Create Listener and tag it
LISTENER_ARN=$(aws elbv2 create-listener --load-balancer-arn $ALB_ARN --protocol HTTP --port 80 --default-actions Type=forward,TargetGroupArn=$TG1_ARN --query 'Listeners[0].ListenerArn' --output text)
echo "LISTENER_ARN=$LISTENER_ARN"

# Add path-based rules
aws elbv2 create-rule --listener-arn $LISTENER_ARN --priority 1 --conditions Field=path-pattern,Values="/joke" --actions Type=forward,TargetGroupArn=$TG1_ARN
aws elbv2 create-rule --listener-arn $LISTENER_ARN --priority 2 --conditions Field=path-pattern,Values="/jokes" --actions Type=forward,TargetGroupArn=$TG2_ARN
```

---

## Step 6. Validation
```bash
# Retrieve the ALB DNS name
ALB_DNS=$(aws elbv2 describe-load-balancers --names jokes-alb --query 'LoadBalancers[0].DNSName' --output text)
echo "ALB URL: http://$ALB_DNS"

# Test endpoints
curl http://$ALB_DNS/joke
curl http://$ALB_DNS/jokes

# Open in browser (Ubuntu devcontainer)
"$BROWSER" "http://$ALB_DNS/joke"
"$BROWSER" "http://$ALB_DNS/jokes"
```
✅ You should see JSON responses from two different hosts (EC2 A and B).

---

## Step 7. Cleanup
```bash
# Terminate EC2 instances
aws ec2 terminate-instances --instance-ids $EC2A_ID $EC2B_ID
aws ec2 wait instance-terminated --instance-ids $EC2A_ID $EC2B_ID

# Delete ALB and target groups
aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN
aws elbv2 delete-target-group --target-group-arn $TG1_ARN
aws elbv2 delete-target-group --target-group-arn $TG2_ARN

# Delete security groups
aws ec2 delete-security-group --group-id $ALB_SG
aws ec2 delete-security-group --group-id $EC2_SG

# Delete NACL, subnet, IGW, route table, and VPC
aws ec2 delete-network-acl --network-acl-id $NACL_ID
aws ec2 delete-subnet --subnet-id $SUBNET_ID
aws ec2 detach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID
aws ec2 delete-internet-gateway --internet-gateway-id $IGW_ID
aws ec2 delete-route-table --route-table-id $RTB_ID
aws ec2 delete-vpc --vpc-id $VPC_ID
```

---

## Summary
This lab demonstrates:
- Deploying two independent Python Flask APIs on EC2
- Using Application Load Balancer path-based routing for multi-endpoint architecture
- Applying Network ACLs and Security Groups for layered defense
- Validating end-to-end routing from ALB to backend APIs securely

All resource creation commands now include tags, and each variable assignment is followed by an echo to display its value.

