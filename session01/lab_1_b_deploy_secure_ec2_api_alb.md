# Lab 1.B: Deploy Secure Multi-EC2 Python Jokes API with ALB Path-Based Routing

<img width="1315" height="1024" alt="IMG" src="https://github.com/user-attachments/assets/b67f8928-9a7e-430b-8cd0-afab8d53128a" />
---

## **Overview**
This lab extends your AWS networking foundation by deploying a **Python REST API** across **two EC2 instances**, fronted by an **Application Load Balancer (ALB)**.  
The ALB routes requests based on the path:
- `/joke` → EC2 A (single random joke)  
- `/jokes` → EC2 B (list of jokes)  

It uses **Network ACLs (NACLs)** and **Security Groups (SGs)** for layered defense.

⚠ **Note:** ALBs require **two subnets in different Availability Zones**. This lab deploys them in `ap-southeast-2a` and `ap-southeast-2b`.

---

## **Objectives**
- Create a VPC and two public subnets  
- Configure NACLs and Security Groups  
- Launch two EC2 instances with Flask APIs  
- Deploy an ALB with path-based routing  
- Validate endpoints and clean up  

---

## **Architecture**
```
Internet → ALB (Port 80)
          │
   ┌──────┴───────────────┐
   │ AWS VPC (10.0.0.0/16)│
   │ ┌──────────┐ ┌──────────┐
   │ │Subnet A  │ │Subnet B  │
   │ │EC2 A     │ │EC2 B     │
   │ │/joke     │ │/jokes    │
   │ └──────────┘ └──────────┘
   │  ▲  ▲           ▲  ▲
   │  │  └─ Target Group 1
   │  └──── Target Group 2
   └────────────────────────┘
```

---

## **Prerequisites**
- AWS CLI configured (`aws configure`)
- IAM permissions for EC2, VPC, ALB resources
- No pre-existing infrastructure required  

---

## **Step 1 – Create VPC, Subnets & Internet Gateway**
```bash
# 1️⃣  Create VPC
VPC_ID=$(aws ec2 create-vpc --cidr-block 10.0.0.0/16 --query 'Vpc.VpcId' --output text)
aws ec2 create-tags --resources $VPC_ID --tags Key=Name,Value=lab-vpc
echo "VPC_ID=$VPC_ID"

# 2️⃣  Get first two AZs in Sydney
AZ1=$(aws ec2 describe-availability-zones --region ap-southeast-2 --query 'AvailabilityZones[0].ZoneName' --output text)
AZ2=$(aws ec2 describe-availability-zones --region ap-southeast-2 --query 'AvailabilityZones[1].ZoneName' --output text)
echo "AZ1=$AZ1 | AZ2=$AZ2"

# 3️⃣  Create two public subnets
SUBNET1_ID=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.1.0/24 --availability-zone $AZ1 --query 'Subnet.SubnetId' --output text)
SUBNET2_ID=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.2.0/24 --availability-zone $AZ2 --query 'Subnet.SubnetId' --output text)
aws ec2 modify-subnet-attribute --subnet-id $SUBNET1_ID --map-public-ip-on-launch
aws ec2 modify-subnet-attribute --subnet-id $SUBNET2_ID --map-public-ip-on-launch
aws ec2 create-tags --resources $SUBNET1_ID --tags Key=Name,Value=subnet-a
aws ec2 create-tags --resources $SUBNET2_ID --tags Key=Name,Value=subnet-b

# 4️⃣  Create and attach Internet Gateway
IGW_ID=$(aws ec2 create-internet-gateway --query 'InternetGateway.InternetGatewayId' --output text)
aws ec2 attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID

# 5️⃣  Create Route Table and associate subnets
RTB_ID=$(aws ec2 create-route-table --vpc-id $VPC_ID --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id $RTB_ID --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID
aws ec2 associate-route-table --route-table-id $RTB_ID --subnet-id $SUBNET1_ID
aws ec2 associate-route-table --route-table-id $RTB_ID --subnet-id $SUBNET2_ID
```

---

## **Step 2 – Create Security Groups**
```bash
# ALB Security Group
ALB_SG=$(aws ec2 create-security-group --group-name alb-sg --description "ALB SG" --vpc-id $VPC_ID --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id $ALB_SG --protocol tcp --port 80 --cidr 0.0.0.0/0

# EC2 Security Group
EC2_SG=$(aws ec2 create-security-group --group-name ec2-sg --description "EC2 SG" --vpc-id $VPC_ID --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id $EC2_SG --protocol tcp --port 5000 --source-group $ALB_SG
MY_IP=$(curl -s ifconfig.me)
aws ec2 authorize-security-group-ingress --group-id $EC2_SG --protocol tcp --port 22 --cidr ${MY_IP}/32
```

---

## **Step 3 – Create Network ACL**
```bash
NACL_ID=$(aws ec2 create-network-acl --vpc-id $VPC_ID --query 'NetworkAcl.NetworkAclId' --output text)

# Inbound
aws ec2 create-network-acl-entry --cli-input-json '{"NetworkAclId":"'"$NACL_ID"'","RuleNumber":100,"Protocol":"6","RuleAction":"allow","Egress":false,"CidrBlock":"0.0.0.0/0","PortRange":{"From":80,"To":80}}'
aws ec2 create-network-acl-entry --cli-input-json '{"NetworkAclId":"'"$NACL_ID"'","RuleNumber":110,"Protocol":"6","RuleAction":"allow","Egress":false,"CidrBlock":"0.0.0.0/0","PortRange":{"From":22,"To":22}}'

# Outbound
aws ec2 create-network-acl-entry --cli-input-json '{"NetworkAclId":"'"$NACL_ID"'","RuleNumber":100,"Protocol":"6","RuleAction":"allow","Egress":true,"CidrBlock":"0.0.0.0/0","PortRange":{"From":80,"To":80}}'
aws ec2 create-network-acl-entry --cli-input-json '{"NetworkAclId":"'"$NACL_ID"'","RuleNumber":110,"Protocol":"6","RuleAction":"allow","Egress":true,"CidrBlock":"0.0.0.0/0","PortRange":{"From":443,"To":443}}'
```

---

## **Step 4 – Launch EC2 Instances**
```bash
# Latest Amazon Linux 2 AMI
AMI_ID=$(aws ec2 describe-images --owners amazon   --filters 'Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2'   --query 'Images | sort_by(@,&CreationDate) | [-1].ImageId' --output text)

# Create Key Pair
aws ec2 create-key-pair --key-name lab-key --query 'KeyMaterial' --output text > lab-key.pem
chmod 600 lab-key.pem

# User Data A
cat > user-data-a.sh <<'EOF'
#!/bin/bash
yum update -y
yum install -y python3-pip
pip3 install flask
cat > /home/ec2-user/app.py <<'APP'
from flask import Flask, jsonify; import socket
app = Flask(__name__)
@app.route('/joke')
def joke(): return jsonify({'joke':'Why do developers hate nature? It has too many bugs!','host':socket.gethostname()})
app.run(host='0.0.0.0', port=5000)
APP
nohup python3 /home/ec2-user/app.py &
EOF

# User Data B
cat > user-data-b.sh <<'EOF'
#!/bin/bash
yum update -y
yum install -y python3-pip
pip3 install flask
cat > /home/ec2-user/app.py <<'APP'
from flask import Flask, jsonify; import socket
app = Flask(__name__)
@app.route('/jokes')
def jokes():
    data=['Why did the cloud break up with the server? It needed space.',
          'I told my computer I needed a break, and it said “No problem, I’ll go to sleep.”',
          'Why do Python programmers wear glasses? Because they can’t C#.']
    return jsonify({'jokes':data,'host':socket.gethostname()})
app.run(host='0.0.0.0', port=5000)
APP
nohup python3 /home/ec2-user/app.py &
EOF

# Launch EC2 Instances
EC2A_ID=$(aws ec2 run-instances --image-id $AMI_ID --instance-type t3.micro --key-name lab-key   --security-group-ids $EC2_SG --subnet-id $SUBNET1_ID --associate-public-ip-address   --user-data file://user-data-a.sh --query 'Instances[0].InstanceId' --output text)

EC2B_ID=$(aws ec2 run-instances --image-id $AMI_ID --instance-type t3.micro --key-name lab-key   --security-group-ids $EC2_SG --subnet-id $SUBNET2_ID --associate-public-ip-address   --user-data file://user-data-b.sh --query 'Instances[0].InstanceId' --output text)

aws ec2 wait instance-running --instance-ids $EC2A_ID $EC2B_ID
```

---

## **Step 5 – Create ALB and Target Groups**
```bash
# Create ALB (Across Two Subnets)
ALB_ARN=$(aws elbv2 create-load-balancer --name jokes-alb   --subnets $SUBNET1_ID $SUBNET2_ID --security-groups $ALB_SG   --query 'LoadBalancers[0].LoadBalancerArn' --output text)

# Target Groups
TG1_ARN=$(aws elbv2 create-target-group --name tg-joke --protocol HTTP --port 5000   --vpc-id $VPC_ID --target-type instance --query 'TargetGroups[0].TargetGroupArn' --output text)
TG2_ARN=$(aws elbv2 create-target-group --name tg-jokes --protocol HTTP --port 5000   --vpc-id $VPC_ID --target-type instance --query 'TargetGroups[0].TargetGroupArn' --output text)

# Register Instances
aws elbv2 register-targets --target-group-arn $TG1_ARN --targets Id=$EC2A_ID
aws elbv2 register-targets --target-group-arn $TG2_ARN --targets Id=$EC2B_ID

# Listener & Path Routing
LISTENER_ARN=$(aws elbv2 create-listener --load-balancer-arn $ALB_ARN   --protocol HTTP --port 80 --default-actions Type=forward,TargetGroupArn=$TG1_ARN   --query 'Listeners[0].ListenerArn' --output text)

aws elbv2 create-rule --listener-arn $LISTENER_ARN --priority 1   --conditions Field=path-pattern,Values="/joke"   --actions Type=forward,TargetGroupArn=$TG1_ARN

aws elbv2 create-rule --listener-arn $LISTENER_ARN --priority 2   --conditions Field=path-pattern,Values="/jokes"   --actions Type=forward,TargetGroupArn=$TG2_ARN
```

---

## **Step 6 – Validation**
```bash
ALB_DNS=$(aws elbv2 describe-load-balancers --names jokes-alb --query 'LoadBalancers[0].DNSName' --output text)
echo "ALB URL: http://$ALB_DNS"

curl http://$ALB_DNS/joke
curl http://$ALB_DNS/jokes
```
✅ Expected output: JSON responses from different EC2 hosts.

---

## **Step 7 – Cleanup**
```bash
aws ec2 terminate-instances --instance-ids $EC2A_ID $EC2B_ID
aws ec2 wait instance-terminated --instance-ids $EC2A_ID $EC2B_ID
aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN
aws elbv2 delete-target-group --target-group-arn $TG1_ARN
aws elbv2 delete-target-group --target-group-arn $TG2_ARN
aws ec2 delete-security-group --group-id $ALB_SG
aws ec2 delete-security-group --group-id $EC2_SG
aws ec2 delete-network-acl --network-acl-id $NACL_ID
aws ec2 delete-subnet --subnet-id $SUBNET1_ID
aws ec2 delete-subnet --subnet-id $SUBNET2_ID
aws ec2 detach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID
aws ec2 delete-internet-gateway --internet-gateway-id $IGW_ID
aws ec2 delete-route-table --route-table-id $RTB_ID
aws ec2 delete-vpc --vpc-id $VPC_ID
```

---

## **Summary**
You have:
- Created a multi-AZ VPC environment  
- Launched two Flask APIs on EC2  
- Configured path-based routing via ALB  
- Applied NACL + SG security layers  
- Validated and cleaned up resources  