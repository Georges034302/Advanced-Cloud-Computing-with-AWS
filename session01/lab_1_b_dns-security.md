# Lab 1.B: Secure web access using Security Groups, NACLs, and Route 53 DNS

## Overview
This lab shows how to secure HTTP access to a web server running on EC2 using Security Groups and Network ACLs (NACLs), and how to expose the service via Route 53 DNS. You'll create a hardened security group, a restrictive NACL for the public subnet, launch an EC2 web server, and add a DNS A record pointing to the instance (or to a load balancer).

## Objectives
- Create a Security Group that allows only required ingress (HTTP/HTTPS) and SSH from a limited IP
- Configure a subnet-level NACL with explicit allow/deny rules
- Launch an EC2 instance (or ALB) serving HTTP
- Create or update a Route 53 record to point to the web endpoint
- Validate access and verify that the firewall layers are effective
- Clean up to avoid charges

## Prerequisites

- AWS CLI configured or Console access
- Local public IP (run `curl ifconfig.co`) for SSH restrictions
- Create VPC and Public Subnet

    ```bash
    # Create VPC and capture VPC ID
    VPC_ID=$(
      aws ec2 create-vpc \
        --cidr-block 10.0.0.0/16 \
        --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=lab-vpc}]' \
        --query 'Vpc.VpcId' \
        --output text
    )
    echo "VPC_ID=$VPC_ID"

    # Query availability zones and pick first
    AZ=$(
      aws ec2 describe-availability-zones \
        --query 'AvailabilityZones[0].ZoneName' \
        --output text
    )
    echo "AZ=$AZ"

    # Create subnet in the VPC, tag it, and get subnet ID
    SUBNET_ID=$(
      aws ec2 create-subnet \
        --vpc-id "$VPC_ID" \
        --cidr-block 10.0.1.0/24 \
        --availability-zone "$AZ" \
        --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=lab-public-subnet}]' \
        --query 'Subnet.SubnetId' \
        --output text
    )
    echo "SUBNET_ID=$SUBNET_ID"
    ```

---

## Architecture (high level)
- Public subnet with NACL configured to be explicit about allowed/denied ports
- Security Group attached to EC2 (stateful) allowing only required ports
- Optional ALB in public subnets with SG allowing HTTP/HTTPS from internet
- Route 53 A/ALIAS record pointing to ALB or to instance public IP

---

## Steps (CLI examples)

Replace placeholders: VPC_ID, SUBNET_ID, HOSTED_ZONE_ID, YOUR_DOMAIN, YOUR_PUBLIC_IP (CIDR format e.g., 203.0.113.5/32).

### 1. Create a restrictive Security Group
```bash
# Create SG and tag it
SG_ID=$(
  aws ec2 create-security-group \
    --group-name lab-web-sg \
    --description "Allow web + SSH from my IP" \
    --vpc-id $VPC_ID \
    --tag-specifications 'ResourceType=security-group,Tags=[{Key=Name,Value=lab-web-sg}]' \
    --query 'GroupId' \
    --output text
)
echo "SG_ID=$SG_ID"

# Allow HTTP (80) from anywhere
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0

# (Optional) Allow HTTPS (443) from anywhere
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0

# Allow SSH only from your IP (replace YOUR_PUBLIC_IP/32)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 22 \
  --cidr YOUR_PUBLIC_IP/32
```

---

### 2. Create a subnet-level NACL with explicit rules
```bash
# Create NACL and tag it
NACL_ID=$(
  aws ec2 create-network-acl \
    --vpc-id $VPC_ID \
    --tag-specifications 'ResourceType=network-acl,Tags=[{Key=Name,Value=lab-public-nacl}]' \
    --query 'NetworkAcl.NetworkAclId' \
    --output text
)
echo "NACL_ID=$NACL_ID"

# Allow inbound HTTP (80)
aws ec2 create-network-acl-entry \
  --network-acl-id $NACL_ID \
  --rule-number 100 \
  --protocol tcp \
  --port-range From=80,To=80 \
  --egress false \
  --rule-action allow \
  --cidr-block 0.0.0.0/0

# Allow inbound HTTPS (443)
aws ec2 create-network-acl-entry \
  --network-acl-id $NACL_ID \
  --rule-number 110 \
  --protocol tcp \
  --port-range From=443,To=443 \
  --egress false \
  --rule-action allow \
  --cidr-block 0.0.0.0/0

# Allow inbound ephemeral ports for return traffic (1024-65535)
aws ec2 create-network-acl-entry \
  --network-acl-id $NACL_ID \
  --rule-number 120 \
  --protocol tcp \
  --port-range From=1024,To=65535 \
  --egress false \
  --rule-action allow \
  --cidr-block 0.0.0.0/0

# Allow SSH from your IP
aws ec2 create-network-acl-entry \
  --network-acl-id $NACL_ID \
  --rule-number 130 \
  --protocol tcp \
  --port-range From=22,To=22 \
  --egress false \
  --rule-action allow \
  --cidr-block YOUR_PUBLIC_IP/32

# Deny everything else inbound
aws ec2 create-network-acl-entry \
  --network-acl-id $NACL_ID \
  --rule-number 32766 \
  --protocol -1 \
  --egress false \
  --rule-action deny \
  --cidr-block 0.0.0.0/0

# Allow outbound HTTP (80)
aws ec2 create-network-acl-entry \
  --network-acl-id $NACL_ID \
  --rule-number 100 \
  --protocol tcp \
  --port-range From=80,To=80 \
  --egress true \
  --rule-action allow \
  --cidr-block 0.0.0.0/0

# Allow outbound HTTPS (443)
aws ec2 create-network-acl-entry \
  --network-acl-id $NACL_ID \
  --rule-number 110 \
  --protocol tcp \
  --port-range From=443,To=443 \
  --egress true \
  --rule-action allow \
  --cidr-block 0.0.0.0/0

# Allow outbound ephemeral ports
aws ec2 create-network-acl-entry \
  --network-acl-id $NACL_ID \
  --rule-number 120 \
  --protocol tcp \
  --port-range From=1024,To=65535 \
  --egress true \
  --rule-action allow \
  --cidr-block 0.0.0.0/0

# Associate NACL with your public subnet
aws ec2 associate-network-acl \
  --network-acl-id $NACL_ID \
  --subnet-id $SUBNET_ID
```

---

### 3. Launch a simple EC2 web server
```bash
# Find latest Amazon Linux 2 AMI
AMI_ID=$(
  aws ec2 describe-images \
    --owners amazon \
    --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" "Name=state,Values=available" \
    --query 'Images | sort_by(@,&CreationDate) | [-1].ImageId' \
    --output text
)
echo "AMI_ID=$AMI_ID"

# Create user-data script
USER_DATA='#!/bin/bash
yum update -y
yum install -y httpd
systemctl enable httpd
systemctl start httpd
echo "Hello from Lab 1.B - secure web access" > /var/www/html/index.html
'

# Launch EC2 instance and tag it
INSTANCE_ID=$(
  aws ec2 run-instances \
    --image-id $AMI_ID \
    --instance-type t3.micro \
    --key-name lab-key \
    --security-group-ids $SG_ID \
    --subnet-id $SUBNET_ID \
    --associate-public-ip-address \
    --user-data "$USER_DATA" \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=lab-web-ec2}]' \
    --query 'Instances[0].InstanceId' \
    --output text
)
echo "INSTANCE_ID=$INSTANCE_ID"

# Wait for instance to be running
aws ec2 wait instance-running \
  --instance-ids $INSTANCE_ID

# Get public IP
PUBLIC_IP=$(
  aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text
)
echo "PUBLIC_IP=$PUBLIC_IP"
```

---

### 4. Create or update Route 53 DNS
```bash
# Create A record to point to instance public IP
cat > record.json <<EOF
{
  "Comment": "Create A record for lab web",
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "lab.YOUR_DOMAIN.",
        "Type": "A",
        "TTL": 300,
        "ResourceRecords": [{ "Value": "$PUBLIC_IP" }]
      }
    }
  ]
}
EOF

aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch file://record.json
```

---

### 5. Validate access
```bash
# Test HTTP access
curl http://$PUBLIC_IP

# Test DNS access (after propagation)
curl http://lab.YOUR_DOMAIN

# Check Security Group rules
aws ec2 describe-security-groups \
  --group-ids $SG_ID

# Check NACL entries
aws ec2 describe-network-acls \
  --network-acl-ids $NACL_ID

# DNS record check
dig +short lab.YOUR_DOMAIN @8.8.8.8
```

---

### Cleanup
```bash
# Delete Route53 record (use reversed UPSERT with "DELETE" and same JSON)
aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch file://record-delete.json || true

# Terminate instance
aws ec2 terminate-instances \
  --instance-ids $INSTANCE_ID
aws ec2 wait instance-terminated \
  --instance-ids $INSTANCE_ID

# Delete NACL (disassociate first if necessary)
# To find association id:
# aws ec2 describe-network-acls --network-acl-ids $NACL_ID --query 'NetworkAcls[0].Associations[].NetworkAclAssociationId' --output text
# aws ec2 disassociate-network-acl --association-id <assoc-id>
aws ec2 delete-network-acl \
  --network-acl-id $NACL_ID || true

# Delete Security Group
aws ec2 delete-security-group \
  --group-id $SG_ID || true
```

## Summary
In this lab, you secured web access to an EC2 instance using AWS Security Groups and Network ACLs (NACLs), and exposed the service via Route 53 DNS.  
You created a restrictive security group, configured explicit NACL rules for your public subnet, launched a web server on EC2, and mapped a DNS record to the instance.  
You validated access and firewall effectiveness, and learned how to clean up resources to avoid charges.  
This approach demonstrates layered security and DNS integration for public cloud workloads.
