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
- Existing VPC and public subnet (VPC_ID, SUBNET_ID)
- A domain hosted in Route 53 (HOSTED_ZONE_ID and domain name) or permission to create a hosted zone
- Local public IP (run curl ifconfig.co) for SSH restrictions

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
# Create SG
SG_ID=$(aws ec2 create-security-group --group-name lab-web-sg --description "Allow web + SSH from my IP" --vpc-id $VPC_ID --query 'GroupId' --output text)

# Allow HTTP (80) from anywhere
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0

# (Optional) Allow HTTPS (443) from anywhere
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 443 --cidr 0.0.0.0/0

# Allow SSH only from your IP (replace YOUR_PUBLIC_IP/32)
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 22 --cidr YOUR_PUBLIC_IP/32

# Egress allow all (default)
```

Notes:
- Security Groups are stateful: return traffic is allowed automatically for established sessions.
- Keep SSH access restricted to your IP only.

### 2. Create a subnet-level NACL with explicit rules
```bash
# Create NACL
NACL_ID=$(aws ec2 create-network-acl --vpc-id $VPC_ID --query 'NetworkAcl.NetworkAclId' --output text)
# Tag
aws ec2 create-tags --resources $NACL_ID --tags Key=Name,Value=lab-public-nacl

# Allow inbound HTTP (80) and ephemeral ports, deny others (example)
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 100 --protocol tcp --port-range From=80,To=80 --egress false --rule-action allow --cidr-block 0.0.0.0/0
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 110 --protocol tcp --port-range From=443,To=443 --egress false --rule-action allow --cidr-block 0.0.0.0/0

# Allow ephemeral ports for return traffic (1024-65535)
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 120 --protocol tcp --port-range From=1024,To=65535 --egress false --rule-action allow --cidr-block 0.0.0.0/0

# Allow SSH from your IP
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 130 --protocol tcp --port-range From=22,To=22 --egress false --rule-action allow --cidr-block YOUR_PUBLIC_IP/32

# Deny everything else inbound (low priority number)
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 32766 --protocol -1 --egress false --rule-action deny --cidr-block 0.0.0.0/0

# For outbound (egress) allow HTTP/HTTPS and ephemeral ports
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 100 --protocol tcp --port-range From=80,To=80 --egress true --rule-action allow --cidr-block 0.0.0.0/0
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 110 --protocol tcp --port-range From=443,To=443 --egress true --rule-action allow --cidr-block 0.0.0.0/0
aws ec2 create-network-acl-entry --network-acl-id $NACL_ID --rule-number 120 --protocol tcp --port-range From=1024,To=65535 --egress true --rule-action allow --cidr-block 0.0.0.0/0

# Associate NACL with your public subnet
aws ec2 associate-network-acl --network-acl-id $NACL_ID --subnet-id $SUBNET_ID
```

Notes:
- NACLs are stateless: you must allow both inbound and outbound explicitly.
- Rule numbering matters (lower numbers are evaluated first).

### 3. Launch a simple EC2 web server
Use the security group created above. Example uses Amazon Linux 2 and user-data to install httpd.

```bash
AMI_ID=$(aws ec2 describe-images --owners amazon --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" "Name=state,Values=available" --query 'Images | sort_by(@,&CreationDate) | [-1].ImageId' --output text)

USER_DATA='#!/bin/bash
yum update -y
yum install -y httpd
systemctl enable httpd
systemctl start httpd
echo "Hello from Lab 1.B - secure web access" > /var/www/html/index.html
'

INSTANCE_ID=$(aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type t3.micro \
  --key-name lab-key \ # replace if you have a different key
  --security-group-ids $SG_ID \
  --subnet-id $SUBNET_ID \
  --associate-public-ip-address \
  --user-data "$USER_DATA" \
  --query 'Instances[0].InstanceId' --output text)

aws ec2 wait instance-running --instance-ids $INSTANCE_ID
PUBLIC_IP=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "Web server public IP: $PUBLIC_IP"
```

If you prefer a more production-like setup, create an Application Load Balancer in public subnets and register target(s) with the ALB, then point Route 53 to the ALB using an ALIAS record.

### 4. Create or update Route 53 DNS
If you already have a hosted zone for YOUR_DOMAIN, create an A record that maps the domain (or a subdomain) to the instance IP or ALB.

A. Create A record to point to instance public IP (not recommended for autoscaling):
```bash
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

aws route53 change-resource-record-sets --hosted-zone-id $HOSTED_ZONE_ID --change-batch file://record.json
```

B. Create ALIAS record for an ALB:
- In Console: Route 53 > Hosted zones > Select your zone > Create record > Choose ALIAS > Select ALB.
- Or with CLI use the ALIAS target configuration (requires ELB DNS name).

Note: DNS changes may take a short time to propagate.

### 5. Validate access
- From your workstation:
  - curl http://$PUBLIC_IP
  - curl http://lab.YOUR_DOMAIN (after DNS propagation)
- Verify SSH is allowed only from your IP:
  - Attempt SSH from another IP (should fail)
- Test NACL behavior:
  - Temporarily add a deny rule for port 80 in NACL and confirm HTTP fails; remove it afterward.

Useful checks:
```bash
# Check Security Group rules
aws ec2 describe-security-groups --group-ids $SG_ID

# Check NACL entries
aws ec2 describe-network-acls --network-acl-ids $NACL_ID

# DNS record check
dig +short lab.YOUR_DOMAIN @8.8.8.8
```

---

## Validation Checklist
- [ ] Security Group exists and allows only required ports (80/443 and SSH from your IP)
- [ ] NACL applied to public subnet with explicit allow/deny rules
- [ ] EC2 instance (or ALB) serving HTTP is reachable
- [ ] Route 53 record resolves to the web endpoint
- [ ] Cannot SSH from IPs other than the allowed CIDR
- [ ] Documented changes for cleanup

---

## Cleanup
Run these commands (replace IDs and names used above) or delete resources via the Console.

```bash
# Delete Route53 record (use reversed UPSERT with "DELETE" and same JSON)
aws route53 change-resource-record-sets --hosted-zone-id $HOSTED_ZONE_ID --change-batch file://record-delete.json || true

# Terminate instance
aws ec2 terminate-instances --instance-ids $INSTANCE_ID
aws ec2 wait instance-terminated --instance-ids $INSTANCE_ID

# Delete NACL (disassociate first if necessary)
# To find association id:
# aws ec2 describe-network-acls --network-acl-ids $NACL_ID --query 'NetworkAcls[0].Associations[].NetworkAclAssociationId' --output text
# aws ec2 disassociate-network-acl --association-id <assoc-id>
aws ec2 delete-network-acl --network-acl-id $NACL_ID || true

# Delete Security Group
aws ec2 delete-security-group --group-id $SG_ID || true
```

Notes:
- If you created an ALB, delete the ALB and its target group before removing subnets or SGs.
- Ensure Route 53 records are cleaned up to avoid stale DNS entries.

---

## Summary
This lab demonstrates layered network security in AWS: security groups (stateful, instance-level), NACLs (stateless, subnet-level), and DNS configuration using Route 53. Use restrictive rules, prefer ALB + Route 53 for production, and always restrict SSH to known admin IPs.
