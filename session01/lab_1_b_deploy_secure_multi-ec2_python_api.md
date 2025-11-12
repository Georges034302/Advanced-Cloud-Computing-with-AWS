# Lab 1.B: Deploy Secure Multi-EC2 Python Jokes API
<img width="1536" height="1024" alt="IMG" src="https://github.com/user-attachments/assets/958fa5ad-f9ff-4911-a9a9-03367dc2e1ea" />

---

## **Overview**
This lab extends your AWS networking foundation by deploying a **Python REST API** across **two EC2 instances** in separate subnets.  
Each instance hosts its own Flask application and serves a different endpoint:

- `/joke` → EC2 A (single random joke)  
- `/jokes` → EC2 B (list of jokes)  

Users will access each API endpoint directly via the EC2 public IP address.  
The environment uses **Network ACLs (NACLs)** and **Security Groups (SGs)** to enforce a secure network perimeter.

⚠ **Note:** The two EC2 instances are deployed across **two Availability Zones** (`ap-southeast-2a` and `ap-southeast-2b`) for redundancy and availability.

---

## **Objectives**
- Create a VPC with two public subnets  
- Configure Network ACLs (NACLs) and Security Groups (SGs)  
- Launch two EC2 instances with Flask-based Python APIs  
- Test API access using EC2 public IPs  
- Clean up all resources  

---

## **Prerequisites**
- AWS CLI configured (`aws configure`)  
- IAM permissions for EC2 and VPC resources  
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
echo "AZ1=$AZ1"
AZ2=$(aws ec2 describe-availability-zones --region ap-southeast-2 --query 'AvailabilityZones[1].ZoneName' --output text)
echo "AZ2=$AZ2"

# 3️⃣  Create two public subnets
SUBNET1_ID=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.1.0/24 --availability-zone $AZ1 --query 'Subnet.SubnetId' --output text)
echo "SUBNET1_ID=$SUBNET1_ID"
SUBNET2_ID=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.2.0/24 --availability-zone $AZ2 --query 'Subnet.SubnetId' --output text)
echo "SUBNET2_ID=$SUBNET2_ID"
aws ec2 modify-subnet-attribute --subnet-id $SUBNET1_ID --map-public-ip-on-launch
aws ec2 modify-subnet-attribute --subnet-id $SUBNET2_ID --map-public-ip-on-launch
aws ec2 create-tags --resources $SUBNET1_ID --tags Key=Name,Value=subnet-a
aws ec2 create-tags --resources $SUBNET2_ID --tags Key=Name,Value=subnet-b

# 4️⃣  Create and attach Internet Gateway
IGW_ID=$(aws ec2 create-internet-gateway --query 'InternetGateway.InternetGatewayId' --output text)
echo "IGW_ID=$IGW_ID"
# Attach Internet Gateway to VPC
aws ec2 attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID

# 5️⃣  Create Route Table and associate subnets
RTB_ID=$(aws ec2 create-route-table --vpc-id $VPC_ID --query 'RouteTable.RouteTableId' --output text)
echo "RTB_ID=$RTB_ID"
aws ec2 create-route --route-table-id $RTB_ID --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID
aws ec2 associate-route-table --route-table-id $RTB_ID --subnet-id $SUBNET1_ID
aws ec2 associate-route-table --route-table-id $RTB_ID --subnet-id $SUBNET2_ID
```

---

## **Step 2 – Create Security Groups**
```bash
# EC2 Security Group
EC2_SG=$(aws ec2 create-security-group --group-name ec2-sg --description "EC2 SG" --vpc-id $VPC_ID --query 'GroupId' --output text)
echo "EC2_SG=$EC2_SG"

# Allow inbound Flask API traffic on port 5000 from anywhere
aws ec2 authorize-security-group-ingress --group-id $EC2_SG --protocol tcp --port 5000 --cidr 0.0.0.0/0

# Get your public IP for SSH rule
MY_IP=$(curl -s ifconfig.me)
echo "MY_IP=$MY_IP"

# Allow SSH from your IP to EC2 SG
aws ec2 authorize-security-group-ingress --group-id $EC2_SG --protocol tcp --port 22 --cidr ${MY_IP}/32
```

---

## **Step 3 – Create Network ACL**
```bash
# Create Network ACL for the VPC
NACL_ID=$(aws ec2 create-network-acl --vpc-id $VPC_ID --query 'NetworkAcl.NetworkAclId' --output text)
echo "NACL_ID=$NACL_ID"

# Inbound Rules

# Allow inbound HTTP (port 80) from anywhere
aws ec2 create-network-acl-entry --cli-input-json '{"NetworkAclId":"'"$NACL_ID"'","RuleNumber":100,"Protocol":"6","RuleAction":"allow","Egress":false,"CidrBlock":"0.0.0.0/0","PortRange":{"From":80,"To":80}}'

# Allow inbound SSH (port 22) from anywhere
aws ec2 create-network-acl-entry --cli-input-json '{"NetworkAclId":"'"$NACL_ID"'","RuleNumber":110,"Protocol":"6","RuleAction":"allow","Egress":false,"CidrBlock":"0.0.0.0/0","PortRange":{"From":22,"To":22}}'

# Allow inbound ephemeral ports (1024-65535) for return traffic
aws ec2 create-network-acl-entry --cli-input-json '{"NetworkAclId":"'"$NACL_ID"'","RuleNumber":120,"Protocol":"6","RuleAction":"allow","Egress":false,"CidrBlock":"0.0.0.0/0","PortRange":{"From":1024,"To":65535}}'

# Deny all other inbound traffic
aws ec2 create-network-acl-entry --cli-input-json '{"NetworkAclId":"'"$NACL_ID"'","RuleNumber":32766,"Protocol":"-1","RuleAction":"deny","Egress":false,"CidrBlock":"0.0.0.0/0"}'


# Outbound Rules

# Allow outbound HTTP (port 80) to anywhere
aws ec2 create-network-acl-entry --cli-input-json '{"NetworkAclId":"'"$NACL_ID"'","RuleNumber":100,"Protocol":"6","RuleAction":"allow","Egress":true,"CidrBlock":"0.0.0.0/0","PortRange":{"From":80,"To":80}}'

# Allow outbound HTTPS (port 443) to anywhere
aws ec2 create-network-acl-entry --cli-input-json '{"NetworkAclId":"'"$NACL_ID"'","RuleNumber":110,"Protocol":"6","RuleAction":"allow","Egress":true,"CidrBlock":"0.0.0.0/0","PortRange":{"From":443,"To":443}}'

# Allow outbound ephemeral ports (1024-65535)
aws ec2 create-network-acl-entry --cli-input-json '{"NetworkAclId":"'"$NACL_ID"'","RuleNumber":120,"Protocol":"6","RuleAction":"allow","Egress":true,"CidrBlock":"0.0.0.0/0","PortRange":{"From":1024,"To":65535}}'

# Deny all other outbound traffic
aws ec2 create-network-acl-entry --cli-input-json '{"NetworkAclId":"'"$NACL_ID"'","RuleNumber":32766,"Protocol":"-1","RuleAction":"deny","Egress":true,"CidrBlock":"0.0.0.0/0"}'
```

---

## **Step 4 – Launch EC2 Instances**
```bash
# Latest Amazon Linux 2 AMI
AMI_ID=$(aws ec2 describe-images --owners amazon   --filters 'Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2'   --query 'Images | sort_by(@,&CreationDate) | [-1].ImageId' --output text)
echo "AMI_ID=$AMI_ID"

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
# Launch EC2 A and tag it
EC2A_ID=$(aws ec2 run-instances --image-id $AMI_ID --instance-type t3.micro --key-name lab-key   --security-group-ids $EC2_SG --subnet-id $SUBNET1_ID --associate-public-ip-address   --user-data file://user-data-a.sh --query 'Instances[0].InstanceId' --output text)
echo "EC2A_ID=$EC2A_ID"

# Launch EC2 B and tag it
EC2B_ID=$(aws ec2 run-instances --image-id $AMI_ID --instance-type t3.micro --key-name lab-key   --security-group-ids $EC2_SG --subnet-id $SUBNET2_ID --associate-public-ip-address   --user-data file://user-data-b.sh --query 'Instances[0].InstanceId' --output text)
echo "EC2B_ID=$EC2B_ID"

# Wait for both EC2 instances to be running
aws ec2 wait instance-running --instance-ids $EC2A_ID $EC2B_ID
```

---

## **Step 5 – Validation**
```bash
# Get EC2 public IPs
EC2A_PUBLIC_IP=$(aws ec2 describe-instances --instance-ids $EC2A_ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "EC2A_PUBLIC_IP=$EC2A_PUBLIC_IP"
EC2B_PUBLIC_IP=$(aws ec2 describe-instances --instance-ids $EC2B_ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "EC2B_PUBLIC_IP=$EC2B_IP"

# Test endpoints directly on EC2 instances
curl http://$EC2A_PUBLIC_IP:5000/joke
curl http://$EC2B_PUBLIC_IP:5000/jokes

# Test endpoints in the web-browser
"$BROWSER" "http://$EC2A_PUBLIC_IP:5000/joke"
"$BROWSER" "http://$EC2B_PUBLIC_IP:5000/jokes"
```
✅ Expected output: JSON responses from different EC2 hosts.

---

## **Step 6 – Cleanup**
```bash
# Terminate EC2 instances
aws ec2 terminate-instances --instance-ids $EC2A_ID $EC2B_ID
aws ec2 wait instance-terminated --instance-ids $EC2A_ID $EC2B_ID

# Delete security groups
aws ec2 delete-security-group --group-id $EC2_SG

# Delete network ACL
aws ec2 delete-network-acl --network-acl-id $NACL_ID

# Delete subnets
aws ec2 delete-subnet --subnet-id $SUBNET1_ID
aws ec2 delete-subnet --subnet-id $SUBNET2_ID

# Detach and delete internet gateway
aws ec2 detach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID
aws ec2 delete-internet-gateway --internet-gateway-id $IGW_ID

# Delete route table
aws ec2 delete-route-table --route-table-id $RTB_ID

# Delete VPC
aws ec2 delete-vpc --vpc-id $VPC_ID

# Delete key pair and remove local PEM file
aws ec2 delete-key-pair --key-name lab-key
rm -f lab-key.pem
```

---

## **Summary**
You have:
- Created a multi-AZ VPC environment  
- Launched two Flask-based Python APIs on separate EC2 instances  
- Secured the environment using Network ACLs (NACLs) and Security Groups (SGs)  
- Accessed each API endpoint directly using EC2 public IPs  
- Validated connectivity and cleaned up all deployed resources

