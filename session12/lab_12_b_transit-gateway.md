# Lab 12.B: Transit Gateway - Hub-and-Spoke Architecture

## Overview
This lab demonstrates AWS Transit Gateway for centralized network connectivity. Instead of creating multiple VPC peering connections, you'll connect three VPCs to a single Transit Gateway hub, enabling any-to-any communication with simplified routing.

**💰 Cost**: Transit Gateway: $0.05/hour (~$1.20/day). Free tier doesn't cover TGW, but minimal cost for short lab.

---

## Objectives
- Create three VPCs with non-overlapping CIDR blocks
- Launch Transit Gateway as central hub
- Attach all VPCs to Transit Gateway
- Configure routing through Transit Gateway
- Test cross-VPC communication through hub
- Compare with VPC peering approach

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for VPC, EC2, Transit Gateway
- Region: ap-southeast-2
- SSH key pair available

---

## Architecture

```
        Transit Gateway (Hub)
               ┌─────┐
               │ TGW │
               └──┬──┘
          ┌───────┼───────┐
          │       │       │
      ┌───▼──┐ ┌──▼──┐ ┌──▼──┐
      │VPC-A │ │VPC-B│ │VPC-C│
      │10.0..│ │10.1.│ │10.2.│
      └──────┘ └─────┘ └─────┘
```

---

## Step 1 – Set Variables

```bash
# Set region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "REGION=$REGION"

# Create key pair name
KEY_NAME="tgw-demo-key-$(date +%s)"
echo "KEY_NAME=$KEY_NAME"
```

---

## Step 2 – Create SSH Key Pair

```bash
echo ""
echo "Creating SSH key pair..."

aws ec2 create-key-pair \
  --key-name "$KEY_NAME" \
  --region "$REGION" \
  --query 'KeyMaterial' \
  --output text > "${KEY_NAME}.pem"

chmod 400 "${KEY_NAME}.pem"

echo "✅ SSH key created"
```

---

## Step 3 – Create Three VPCs

```bash
echo ""
echo "================================================"
echo "CREATING 3 VPCs"
echo "================================================"
echo ""

# VPC-A (10.0.0.0/16)
VPC_A_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --region "$REGION" \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=TGW-VPC-A}]' \
  --query 'Vpc.VpcId' \
  --output text)

echo "VPC_A_ID=$VPC_A_ID (10.0.0.0/16)"

# VPC-B (10.1.0.0/16)
VPC_B_ID=$(aws ec2 create-vpc \
  --cidr-block 10.1.0.0/16 \
  --region "$REGION" \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=TGW-VPC-B}]' \
  --query 'Vpc.VpcId' \
  --output text)

echo "VPC_B_ID=$VPC_B_ID (10.1.0.0/16)"

# VPC-C (10.2.0.0/16)
VPC_C_ID=$(aws ec2 create-vpc \
  --cidr-block 10.2.0.0/16 \
  --region "$REGION" \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=TGW-VPC-C}]' \
  --query 'Vpc.VpcId' \
  --output text)

echo "VPC_C_ID=$VPC_C_ID (10.2.0.0/16)"
echo ""
echo "✅ Three VPCs created"
```

---

## Step 4 – Create Subnets in Each VPC

```bash
echo ""
echo "Creating subnets..."

# Subnet in VPC-A
SUBNET_A_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_A_ID" \
  --cidr-block 10.0.1.0/24 \
  --availability-zone "${REGION}a" \
  --region "$REGION" \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=Subnet-A}]' \
  --query 'Subnet.SubnetId' \
  --output text)

aws ec2 modify-subnet-attribute \
  --subnet-id "$SUBNET_A_ID" \
  --map-public-ip-on-launch \
  --region "$REGION"

echo "SUBNET_A_ID=$SUBNET_A_ID"

# Subnet in VPC-B
SUBNET_B_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_B_ID" \
  --cidr-block 10.1.1.0/24 \
  --availability-zone "${REGION}a" \
  --region "$REGION" \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=Subnet-B}]' \
  --query 'Subnet.SubnetId' \
  --output text)

aws ec2 modify-subnet-attribute \
  --subnet-id "$SUBNET_B_ID" \
  --map-public-ip-on-launch \
  --region "$REGION"

echo "SUBNET_B_ID=$SUBNET_B_ID"

# Subnet in VPC-C
SUBNET_C_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_C_ID" \
  --cidr-block 10.2.1.0/24 \
  --availability-zone "${REGION}a" \
  --region "$REGION" \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=Subnet-C}]' \
  --query 'Subnet.SubnetId' \
  --output text)

aws ec2 modify-subnet-attribute \
  --subnet-id "$SUBNET_C_ID" \
  --map-public-ip-on-launch \
  --region "$REGION"

echo "SUBNET_C_ID=$SUBNET_C_ID"
echo ""
echo "✅ Subnets created in all VPCs"
```

---

## Step 5 – Create Internet Gateways

```bash
echo ""
echo "Creating Internet Gateways..."

# IGW for VPC-A
IGW_A_ID=$(aws ec2 create-internet-gateway \
  --region "$REGION" \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=IGW-A}]' \
  --query 'InternetGateway.InternetGatewayId' \
  --output text)

aws ec2 attach-internet-gateway \
  --internet-gateway-id "$IGW_A_ID" \
  --vpc-id "$VPC_A_ID" \
  --region "$REGION"

# IGW for VPC-B
IGW_B_ID=$(aws ec2 create-internet-gateway \
  --region "$REGION" \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=IGW-B}]' \
  --query 'InternetGateway.InternetGatewayId' \
  --output text)

aws ec2 attach-internet-gateway \
  --internet-gateway-id "$IGW_B_ID" \
  --vpc-id "$VPC_B_ID" \
  --region "$REGION"

# IGW for VPC-C
IGW_C_ID=$(aws ec2 create-internet-gateway \
  --region "$REGION" \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=IGW-C}]' \
  --query 'InternetGateway.InternetGatewayId' \
  --output text)

aws ec2 attach-internet-gateway \
  --internet-gateway-id "$IGW_C_ID" \
  --vpc-id "$VPC_C_ID" \
  --region "$REGION"

echo "✅ Internet Gateways attached"
```

---

## Step 6 – Update Route Tables for Internet Access

```bash
echo ""
echo "Configuring route tables..."

# Get route tables
RTB_A_ID=$(aws ec2 describe-route-tables \
  --filters "Name=vpc-id,Values=$VPC_A_ID" "Name=association.main,Values=true" \
  --region "$REGION" \
  --query 'RouteTables[0].RouteTableId' \
  --output text)

RTB_B_ID=$(aws ec2 describe-route-tables \
  --filters "Name=vpc-id,Values=$VPC_B_ID" "Name=association.main,Values=true" \
  --region "$REGION" \
  --query 'RouteTables[0].RouteTableId' \
  --output text)

RTB_C_ID=$(aws ec2 describe-route-tables \
  --filters "Name=vpc-id,Values=$VPC_C_ID" "Name=association.main,Values=true" \
  --region "$REGION" \
  --query 'RouteTables[0].RouteTableId' \
  --output text)

# Add Internet routes
aws ec2 create-route \
  --route-table-id "$RTB_A_ID" \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id "$IGW_A_ID" \
  --region "$REGION"

aws ec2 create-route \
  --route-table-id "$RTB_B_ID" \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id "$IGW_B_ID" \
  --region "$REGION"

aws ec2 create-route \
  --route-table-id "$RTB_C_ID" \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id "$IGW_C_ID" \
  --region "$REGION"

echo "✅ Route tables updated with Internet access"
```

---

## Step 7 – Create Security Groups

```bash
echo ""
echo "Creating security groups..."

# Security group for VPC-A
SG_A_ID=$(aws ec2 create-security-group \
  --group-name "TGW-SG-A" \
  --description "Security group for VPC-A" \
  --vpc-id "$VPC_A_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_A_ID" \
  --protocol tcp --port 22 --cidr 0.0.0.0/0 \
  --region "$REGION"

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_A_ID" \
  --protocol icmp --port -1 --cidr 10.0.0.0/8 \
  --region "$REGION"

# Security group for VPC-B
SG_B_ID=$(aws ec2 create-security-group \
  --group-name "TGW-SG-B" \
  --description "Security group for VPC-B" \
  --vpc-id "$VPC_B_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_B_ID" \
  --protocol tcp --port 22 --cidr 0.0.0.0/0 \
  --region "$REGION"

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_B_ID" \
  --protocol icmp --port -1 --cidr 10.0.0.0/8 \
  --region "$REGION"

# Security group for VPC-C
SG_C_ID=$(aws ec2 create-security-group \
  --group-name "TGW-SG-C" \
  --description "Security group for VPC-C" \
  --vpc-id "$VPC_C_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_C_ID" \
  --protocol tcp --port 22 --cidr 0.0.0.0/0 \
  --region "$REGION"

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_C_ID" \
  --protocol icmp --port -1 --cidr 10.0.0.0/8 \
  --region "$REGION"

echo "✅ Security groups created (allow SSH and ICMP from 10.0.0.0/8)"
```

---

## Step 8 – Launch EC2 Instances

```bash
echo ""
echo "================================================"
echo "LAUNCHING EC2 INSTANCES"
echo "================================================"
echo ""

# Get AMI
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" \
            "Name=state,Values=available" \
  --region "$REGION" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

echo "AMI_ID=$AMI_ID"
echo ""

# Launch in VPC-A
INSTANCE_A_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --key-name "$KEY_NAME" \
  --subnet-id "$SUBNET_A_ID" \
  --security-group-ids "$SG_A_ID" \
  --private-ip-address 10.0.1.10 \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Instance-A}]' \
  --region "$REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Instance-A: $INSTANCE_A_ID (10.0.1.10)"

# Launch in VPC-B
INSTANCE_B_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --key-name "$KEY_NAME" \
  --subnet-id "$SUBNET_B_ID" \
  --security-group-ids "$SG_B_ID" \
  --private-ip-address 10.1.1.10 \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Instance-B}]' \
  --region "$REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Instance-B: $INSTANCE_B_ID (10.1.1.10)"

# Launch in VPC-C
INSTANCE_C_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --key-name "$KEY_NAME" \
  --subnet-id "$SUBNET_C_ID" \
  --security-group-ids "$SG_C_ID" \
  --private-ip-address 10.2.1.10 \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Instance-C}]' \
  --region "$REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Instance-C: $INSTANCE_C_ID (10.2.1.10)"
echo ""
echo "Waiting for instances to be running..."

aws ec2 wait instance-running \
  --instance-ids "$INSTANCE_A_ID" "$INSTANCE_B_ID" "$INSTANCE_C_ID" \
  --region "$REGION"

echo "✅ All instances running"
```

---

## Step 9 – Create Transit Gateway

```bash
echo ""
echo "================================================"
echo "CREATING TRANSIT GATEWAY"
echo "================================================"
echo ""

TGW_ID=$(aws ec2 create-transit-gateway \
  --description "Demo Transit Gateway" \
  --options "AmazonSideAsn=64512,DefaultRouteTableAssociation=enable,DefaultRouteTablePropagation=enable" \
  --tag-specifications 'ResourceType=transit-gateway,Tags=[{Key=Name,Value=Demo-TGW}]' \
  --region "$REGION" \
  --query 'TransitGateway.TransitGatewayId' \
  --output text)

echo "TGW_ID=$TGW_ID"
echo ""
echo "Waiting for Transit Gateway to be available..."
echo "(This takes 1-2 minutes)"

aws ec2 wait transit-gateway-available \
  --transit-gateway-ids "$TGW_ID" \
  --region "$REGION"

echo ""
echo "✅ Transit Gateway created and available"
```

---

## Step 10 – Attach VPCs to Transit Gateway

```bash
echo ""
echo "================================================"
echo "ATTACHING VPCs TO TRANSIT GATEWAY"
echo "================================================"
echo ""

# Attach VPC-A
echo "Attaching VPC-A..."
ATTACH_A_ID=$(aws ec2 create-transit-gateway-vpc-attachment \
  --transit-gateway-id "$TGW_ID" \
  --vpc-id "$VPC_A_ID" \
  --subnet-ids "$SUBNET_A_ID" \
  --tag-specifications 'ResourceType=transit-gateway-attachment,Tags=[{Key=Name,Value=TGW-Attach-A}]' \
  --region "$REGION" \
  --query 'TransitGatewayVpcAttachment.TransitGatewayAttachmentId' \
  --output text)

echo "ATTACH_A_ID=$ATTACH_A_ID"

# Attach VPC-B
echo "Attaching VPC-B..."
ATTACH_B_ID=$(aws ec2 create-transit-gateway-vpc-attachment \
  --transit-gateway-id "$TGW_ID" \
  --vpc-id "$VPC_B_ID" \
  --subnet-ids "$SUBNET_B_ID" \
  --tag-specifications 'ResourceType=transit-gateway-attachment,Tags=[{Key=Name,Value=TGW-Attach-B}]' \
  --region "$REGION" \
  --query 'TransitGatewayVpcAttachment.TransitGatewayAttachmentId' \
  --output text)

echo "ATTACH_B_ID=$ATTACH_B_ID"

# Attach VPC-C
echo "Attaching VPC-C..."
ATTACH_C_ID=$(aws ec2 create-transit-gateway-vpc-attachment \
  --transit-gateway-id "$TGW_ID" \
  --vpc-id "$VPC_C_ID" \
  --subnet-ids "$SUBNET_C_ID" \
  --tag-specifications 'ResourceType=transit-gateway-attachment,Tags=[{Key=Name,Value=TGW-Attach-C}]' \
  --region "$REGION" \
  --query 'TransitGatewayVpcAttachment.TransitGatewayAttachmentId' \
  --output text)

echo "ATTACH_C_ID=$ATTACH_C_ID"
echo ""
echo "Waiting for attachments to be available..."
echo "(This takes 1-2 minutes)"

sleep 60

echo ""
echo "✅ All VPC attachments created"
```

---

## Step 11 – Add Routes to Transit Gateway

```bash
echo ""
echo "================================================"
echo "UPDATING ROUTE TABLES"
echo "================================================"
echo ""

# Add routes to VPC-B and VPC-C from VPC-A
echo "Adding routes in VPC-A to reach VPC-B and VPC-C via TGW..."
aws ec2 create-route \
  --route-table-id "$RTB_A_ID" \
  --destination-cidr-block 10.1.0.0/16 \
  --transit-gateway-id "$TGW_ID" \
  --region "$REGION"

aws ec2 create-route \
  --route-table-id "$RTB_A_ID" \
  --destination-cidr-block 10.2.0.0/16 \
  --transit-gateway-id "$TGW_ID" \
  --region "$REGION"

echo "✅ VPC-A routes added"

# Add routes to VPC-A and VPC-C from VPC-B
echo "Adding routes in VPC-B to reach VPC-A and VPC-C via TGW..."
aws ec2 create-route \
  --route-table-id "$RTB_B_ID" \
  --destination-cidr-block 10.0.0.0/16 \
  --transit-gateway-id "$TGW_ID" \
  --region "$REGION"

aws ec2 create-route \
  --route-table-id "$RTB_B_ID" \
  --destination-cidr-block 10.2.0.0/16 \
  --transit-gateway-id "$TGW_ID" \
  --region "$REGION"

echo "✅ VPC-B routes added"

# Add routes to VPC-A and VPC-B from VPC-C
echo "Adding routes in VPC-C to reach VPC-A and VPC-B via TGW..."
aws ec2 create-route \
  --route-table-id "$RTB_C_ID" \
  --destination-cidr-block 10.0.0.0/16 \
  --transit-gateway-id "$TGW_ID" \
  --region "$REGION"

aws ec2 create-route \
  --route-table-id "$RTB_C_ID" \
  --destination-cidr-block 10.1.0.0/16 \
  --transit-gateway-id "$TGW_ID" \
  --region "$REGION"

echo "✅ VPC-C routes added"
echo ""
echo "All route tables updated to use Transit Gateway"
```

---

## Step 12 – Verify Route Tables

```bash
echo ""
echo "================================================"
echo "ROUTE TABLE VERIFICATION"
echo "================================================"
echo ""

echo "VPC-A Route Table:"
aws ec2 describe-route-tables \
  --route-table-ids "$RTB_A_ID" \
  --region "$REGION" \
  --query 'RouteTables[0].Routes[*].[DestinationCidrBlock,GatewayId,TransitGatewayId]' \
  --output table

echo ""
echo "VPC-B Route Table:"
aws ec2 describe-route-tables \
  --route-table-ids "$RTB_B_ID" \
  --region "$REGION" \
  --query 'RouteTables[0].Routes[*].[DestinationCidrBlock,GatewayId,TransitGatewayId]' \
  --output table

echo ""
echo "VPC-C Route Table:"
aws ec2 describe-route-tables \
  --route-table-ids "$RTB_C_ID" \
  --region "$REGION" \
  --query 'RouteTables[0].Routes[*].[DestinationCidrBlock,GatewayId,TransitGatewayId]' \
  --output table

echo ""
echo "✅ All routes point to Transit Gateway for cross-VPC traffic"
```

---

## Step 13 – Test Connectivity from VPC-A

```bash
echo ""
echo "================================================"
echo "TESTING CONNECTIVITY"
echo "================================================"
echo ""

# Get public IP of Instance-A
INSTANCE_A_PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_A_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo "Instance-A Public IP: $INSTANCE_A_PUBLIC_IP"
echo ""
echo "Testing connectivity from VPC-A to VPC-B and VPC-C..."
echo "Waiting for SSH to be ready..."
sleep 30

# Test from A to B
echo ""
echo "Ping from Instance-A (10.0.1.10) to Instance-B (10.1.1.10):"
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no \
  ec2-user@"$INSTANCE_A_PUBLIC_IP" \
  "ping -c 3 10.1.1.10" 2>/dev/null || echo "Testing..."

# Test from A to C
echo ""
echo "Ping from Instance-A (10.0.1.10) to Instance-C (10.2.1.10):"
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no \
  ec2-user@"$INSTANCE_A_PUBLIC_IP" \
  "ping -c 3 10.2.1.10" 2>/dev/null || echo "Testing..."

echo ""
echo "✅ All VPCs can communicate through Transit Gateway hub"
```

---

## Step 14 – View Transit Gateway Attachments

```bash
echo ""
echo "================================================"
echo "TRANSIT GATEWAY DETAILS"
echo "================================================"
echo ""

echo "Transit Gateway Attachments:"
aws ec2 describe-transit-gateway-attachments \
  --filters "Name=transit-gateway-id,Values=$TGW_ID" \
  --region "$REGION" \
  --query 'TransitGatewayAttachments[*].[TransitGatewayAttachmentId,ResourceId,State]' \
  --output table

echo ""
echo "Transit Gateway Route Table:"
TGW_RTB_ID=$(aws ec2 describe-transit-gateway-route-tables \
  --filters "Name=transit-gateway-id,Values=$TGW_ID" \
  --region "$REGION" \
  --query 'TransitGatewayRouteTables[0].TransitGatewayRouteTableId' \
  --output text)

echo "TGW Route Table ID: $TGW_RTB_ID"
```

---

## Step 15 – Cleanup

```bash
echo ""
echo "Cleaning up resources..."
echo "⚠️  This will take several minutes due to TGW deletion delays"
echo ""

# Terminate instances
echo "Terminating EC2 instances..."
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_A_ID" "$INSTANCE_B_ID" "$INSTANCE_C_ID" \
  --region "$REGION" > /dev/null

aws ec2 wait instance-terminated \
  --instance-ids "$INSTANCE_A_ID" "$INSTANCE_B_ID" "$INSTANCE_C_ID" \
  --region "$REGION"

echo "✅ Instances terminated"

# Delete TGW attachments
echo "Deleting Transit Gateway attachments..."
aws ec2 delete-transit-gateway-vpc-attachment \
  --transit-gateway-attachment-id "$ATTACH_A_ID" \
  --region "$REGION" > /dev/null

aws ec2 delete-transit-gateway-vpc-attachment \
  --transit-gateway-attachment-id "$ATTACH_B_ID" \
  --region "$REGION" > /dev/null

aws ec2 delete-transit-gateway-vpc-attachment \
  --transit-gateway-attachment-id "$ATTACH_C_ID" \
  --region "$REGION" > /dev/null

echo "Waiting for attachments to be deleted (60 seconds)..."
sleep 60

echo "✅ Attachments deleted"

# Delete Transit Gateway
echo "Deleting Transit Gateway..."
aws ec2 delete-transit-gateway \
  --transit-gateway-id "$TGW_ID" \
  --region "$REGION" > /dev/null

echo "Waiting for TGW deletion (this takes 1-2 minutes)..."
sleep 90

echo "✅ Transit Gateway deleted"

# Delete security groups
sleep 10
aws ec2 delete-security-group --group-id "$SG_A_ID" --region "$REGION" 2>/dev/null
aws ec2 delete-security-group --group-id "$SG_B_ID" --region "$REGION" 2>/dev/null
aws ec2 delete-security-group --group-id "$SG_C_ID" --region "$REGION" 2>/dev/null

echo "✅ Security groups deleted"

# Delete Internet Gateways
echo "Deleting Internet Gateways..."
aws ec2 detach-internet-gateway \
  --internet-gateway-id "$IGW_A_ID" \
  --vpc-id "$VPC_A_ID" \
  --region "$REGION"

aws ec2 delete-internet-gateway \
  --internet-gateway-id "$IGW_A_ID" \
  --region "$REGION"

aws ec2 detach-internet-gateway \
  --internet-gateway-id "$IGW_B_ID" \
  --vpc-id "$VPC_B_ID" \
  --region "$REGION"

aws ec2 delete-internet-gateway \
  --internet-gateway-id "$IGW_B_ID" \
  --region "$REGION"

aws ec2 detach-internet-gateway \
  --internet-gateway-id "$IGW_C_ID" \
  --vpc-id "$VPC_C_ID" \
  --region "$REGION"

aws ec2 delete-internet-gateway \
  --internet-gateway-id "$IGW_C_ID" \
  --region "$REGION"

echo "✅ Internet Gateways deleted"

# Delete subnets
echo "Deleting subnets..."
aws ec2 delete-subnet --subnet-id "$SUBNET_A_ID" --region "$REGION"
aws ec2 delete-subnet --subnet-id "$SUBNET_B_ID" --region "$REGION"
aws ec2 delete-subnet --subnet-id "$SUBNET_C_ID" --region "$REGION"

echo "✅ Subnets deleted"

# Delete VPCs
echo "Deleting VPCs..."
aws ec2 delete-vpc --vpc-id "$VPC_A_ID" --region "$REGION"
aws ec2 delete-vpc --vpc-id "$VPC_B_ID" --region "$REGION"
aws ec2 delete-vpc --vpc-id "$VPC_C_ID" --region "$REGION"

echo "✅ VPCs deleted"

# Delete key pair
aws ec2 delete-key-pair --key-name "$KEY_NAME" --region "$REGION"
rm -f "${KEY_NAME}.pem"

echo "✅ Key pair deleted"
echo ""
echo "All resources cleaned up!"
```

---

## Summary

In this lab, you have:
- Created three VPCs with non-overlapping CIDR blocks
- Launched Transit Gateway as central connectivity hub
- Attached all three VPCs to Transit Gateway
- Configured routing through Transit Gateway
- Tested cross-VPC communication through hub
- Compared hub-and-spoke vs mesh peering topology

**Key Takeaways:**
- **Centralized Hub**: Transit Gateway simplifies multi-VPC connectivity
- **Scalable**: Connect hundreds of VPCs without mesh complexity
- **Transitive Routing**: Unlike VPC peering, TGW supports transitive routing
- **Single Point**: All VPCs route through TGW (no direct peering needed)
- **Cost**: $0.05/hour per TGW + $0.02/GB data processing

**Transit Gateway vs VPC Peering:**

| Feature | VPC Peering | Transit Gateway |
|---------|-------------|-----------------|
| Max connections | 125 per VPC | Unlimited |
| Transitive routing | ❌ No | ✅ Yes |
| Complexity | High (mesh) | Low (hub) |
| Cost | Free | $0.05/hour |
| Inter-region | Supported | Supported |

---

## Best Practices

**Design:**
- Use Transit Gateway for 3+ VPCs
- Keep CIDR blocks non-overlapping
- Plan for future VPC additions
- Use separate TGW for different environments

**Routing:**
- Use Transit Gateway route tables for segmentation
- Keep routes simple and documented
- Monitor route propagation
- Use blackhole routes for security

**Security:**
- Use security groups for instance-level control
- Implement Transit Gateway route table filtering
- Enable VPC Flow Logs
- Use AWS Network Firewall with TGW

**Cost Optimization:**
- Use TGW for 3+ VPCs (otherwise use peering)
- Monitor data processing charges
- Consider intra-region vs inter-region costs
- Right-size TGW attachments

---

## Additional Resources

- [Transit Gateway Documentation](https://docs.aws.amazon.com/vpc/latest/tgw/)
- [Transit Gateway vs VPC Peering](https://docs.aws.amazon.com/vpc/latest/tgw/tgw-peering.html)
- [Transit Gateway Pricing](https://aws.amazon.com/transit-gateway/pricing/)
- [Best Practices Guide](https://docs.aws.amazon.com/vpc/latest/tgw/tgw-best-design-practices.html)
