# Lab 12.A: VPC Peering - Connect Multiple VPCs

## Overview
This lab demonstrates VPC Peering, a networking connection between two VPCs that enables routing traffic between them using private IPv4 or IPv6 addresses. You'll create two VPCs in the same region, establish a peering connection, configure routing, and verify cross-VPC communication between EC2 instances.

**💰 Cost**: FREE TIER (VPC peering is free, EC2 t2.micro included in free tier)

---

## Objectives
- Create two VPCs with non-overlapping CIDR blocks
- Launch EC2 instances in each VPC
- Establish VPC peering connection
- Configure route tables for cross-VPC routing
- Update security groups for inter-VPC communication
- Test connectivity between instances in different VPCs
- Understand VPC peering limitations and best practices

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for VPC, EC2
- Region: ap-southeast-2
- SSH key pair available

---

## Architecture

```
VPC-A (10.0.0.0/16)              VPC-B (10.1.0.0/16)
┌─────────────────────┐          ┌─────────────────────┐
│  Subnet 10.0.1.0/24 │          │  Subnet 10.1.1.0/24 │
│  ┌───────────────┐  │          │  ┌───────────────┐  │
│  │  EC2 Instance │  │◄────────►│  │  EC2 Instance │  │
│  │   10.0.1.10   │  │  Peering │  │   10.1.1.10   │  │
│  └───────────────┘  │          │  └───────────────┘  │
│         │           │          │         │           │
│    Internet GW      │          │    Internet GW      │
└─────────────────────┘          └─────────────────────┘
```

---

## Step 1 – Set Variables

```bash
# Set region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "REGION=$REGION"

# Set unique identifiers
TIMESTAMP=$(date +%s)
KEY_NAME="vpc-peering-key-${TIMESTAMP}"
echo "KEY_NAME=$KEY_NAME"
```

---

## Step 2 – Create SSH Key Pair

```bash
echo ""
echo "Creating SSH key pair..."

# Create key pair
aws ec2 create-key-pair \
  --key-name "$KEY_NAME" \
  --region "$REGION" \
  --query 'KeyMaterial' \
  --output text > "${KEY_NAME}.pem"

# Set permissions
chmod 400 "${KEY_NAME}.pem"

echo "✅ SSH key created: ${KEY_NAME}.pem"
```

---

## Step 3 – Create VPC-A

```bash
echo ""
echo "================================================"
echo "CREATING VPC-A (10.0.0.0/16)"
echo "================================================"
echo ""

# Create VPC-A
VPC_A_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --region "$REGION" \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=VPC-A}]' \
  --query 'Vpc.VpcId' \
  --output text)

echo "VPC_A_ID=$VPC_A_ID"

# Enable DNS hostnames
aws ec2 modify-vpc-attribute \
  --vpc-id "$VPC_A_ID" \
  --enable-dns-hostnames \
  --region "$REGION"

echo "✅ VPC-A created with DNS hostnames enabled"
```

---

## Step 4 – Create Subnet in VPC-A

```bash
echo ""
echo "Creating subnet in VPC-A..."

# Create subnet
SUBNET_A_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_A_ID" \
  --cidr-block 10.0.1.0/24 \
  --availability-zone "${REGION}a" \
  --region "$REGION" \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=Subnet-A}]' \
  --query 'Subnet.SubnetId' \
  --output text)

echo "SUBNET_A_ID=$SUBNET_A_ID"

# Enable auto-assign public IP
aws ec2 modify-subnet-attribute \
  --subnet-id "$SUBNET_A_ID" \
  --map-public-ip-on-launch \
  --region "$REGION"

echo "✅ Subnet-A created (10.0.1.0/24)"
```

---

## Step 5 – Create Internet Gateway for VPC-A

```bash
echo ""
echo "Creating Internet Gateway for VPC-A..."

# Create IGW
IGW_A_ID=$(aws ec2 create-internet-gateway \
  --region "$REGION" \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=IGW-A}]' \
  --query 'InternetGateway.InternetGatewayId' \
  --output text)

echo "IGW_A_ID=$IGW_A_ID"

# Attach to VPC-A
aws ec2 attach-internet-gateway \
  --internet-gateway-id "$IGW_A_ID" \
  --vpc-id "$VPC_A_ID" \
  --region "$REGION"

echo "✅ Internet Gateway attached to VPC-A"
```

---

## Step 6 – Configure Route Table for VPC-A

```bash
echo ""
echo "Configuring route table for VPC-A..."

# Get main route table
RTB_A_ID=$(aws ec2 describe-route-tables \
  --filters "Name=vpc-id,Values=$VPC_A_ID" "Name=association.main,Values=true" \
  --region "$REGION" \
  --query 'RouteTables[0].RouteTableId' \
  --output text)

echo "RTB_A_ID=$RTB_A_ID"

# Add route to Internet Gateway
aws ec2 create-route \
  --route-table-id "$RTB_A_ID" \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id "$IGW_A_ID" \
  --region "$REGION"

# Tag route table
aws ec2 create-tags \
  --resources "$RTB_A_ID" \
  --tags Key=Name,Value=RTB-A \
  --region "$REGION"

echo "✅ Route table configured with Internet access"
```

---

## Step 7 – Create Security Group for VPC-A

```bash
echo ""
echo "Creating security group for VPC-A..."

# Create security group
SG_A_ID=$(aws ec2 create-security-group \
  --group-name "VPC-A-SG" \
  --description "Security group for VPC-A instances" \
  --vpc-id "$VPC_A_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

echo "SG_A_ID=$SG_A_ID"

# Allow SSH from anywhere (for testing)
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_A_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

# Allow ICMP from VPC-B CIDR (for ping testing)
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_A_ID" \
  --protocol icmp \
  --port -1 \
  --cidr 10.1.0.0/16 \
  --region "$REGION"

# Allow SSH from VPC-B CIDR
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_A_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 10.1.0.0/16 \
  --region "$REGION"

echo "✅ Security group configured (SSH and ICMP allowed from VPC-B)"
```

---

## Step 8 – Create VPC-B

```bash
echo ""
echo "================================================"
echo "CREATING VPC-B (10.1.0.0/16)"
echo "================================================"
echo ""

# Create VPC-B
VPC_B_ID=$(aws ec2 create-vpc \
  --cidr-block 10.1.0.0/16 \
  --region "$REGION" \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=VPC-B}]' \
  --query 'Vpc.VpcId' \
  --output text)

echo "VPC_B_ID=$VPC_B_ID"

# Enable DNS hostnames
aws ec2 modify-vpc-attribute \
  --vpc-id "$VPC_B_ID" \
  --enable-dns-hostnames \
  --region "$REGION"

echo "✅ VPC-B created with DNS hostnames enabled"
```

---

## Step 9 – Create Subnet in VPC-B

```bash
echo ""
echo "Creating subnet in VPC-B..."

# Create subnet
SUBNET_B_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_B_ID" \
  --cidr-block 10.1.1.0/24 \
  --availability-zone "${REGION}a" \
  --region "$REGION" \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=Subnet-B}]' \
  --query 'Subnet.SubnetId' \
  --output text)

echo "SUBNET_B_ID=$SUBNET_B_ID"

# Enable auto-assign public IP
aws ec2 modify-subnet-attribute \
  --subnet-id "$SUBNET_B_ID" \
  --map-public-ip-on-launch \
  --region "$REGION"

echo "✅ Subnet-B created (10.1.1.0/24)"
```

---

## Step 10 – Create Internet Gateway for VPC-B

```bash
echo ""
echo "Creating Internet Gateway for VPC-B..."

# Create IGW
IGW_B_ID=$(aws ec2 create-internet-gateway \
  --region "$REGION" \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=IGW-B}]' \
  --query 'InternetGateway.InternetGatewayId' \
  --output text)

echo "IGW_B_ID=$IGW_B_ID"

# Attach to VPC-B
aws ec2 attach-internet-gateway \
  --internet-gateway-id "$IGW_B_ID" \
  --vpc-id "$VPC_B_ID" \
  --region "$REGION"

echo "✅ Internet Gateway attached to VPC-B"
```

---

## Step 11 – Configure Route Table for VPC-B

```bash
echo ""
echo "Configuring route table for VPC-B..."

# Get main route table
RTB_B_ID=$(aws ec2 describe-route-tables \
  --filters "Name=vpc-id,Values=$VPC_B_ID" "Name=association.main,Values=true" \
  --region "$REGION" \
  --query 'RouteTables[0].RouteTableId' \
  --output text)

echo "RTB_B_ID=$RTB_B_ID"

# Add route to Internet Gateway
aws ec2 create-route \
  --route-table-id "$RTB_B_ID" \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id "$IGW_B_ID" \
  --region "$REGION"

# Tag route table
aws ec2 create-tags \
  --resources "$RTB_B_ID" \
  --tags Key=Name,Value=RTB-B \
  --region "$REGION"

echo "✅ Route table configured with Internet access"
```

---

## Step 12 – Create Security Group for VPC-B

```bash
echo ""
echo "Creating security group for VPC-B..."

# Create security group
SG_B_ID=$(aws ec2 create-security-group \
  --group-name "VPC-B-SG" \
  --description "Security group for VPC-B instances" \
  --vpc-id "$VPC_B_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

echo "SG_B_ID=$SG_B_ID"

# Allow SSH from anywhere (for testing)
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_B_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

# Allow ICMP from VPC-A CIDR (for ping testing)
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_B_ID" \
  --protocol icmp \
  --port -1 \
  --cidr 10.0.0.0/16 \
  --region "$REGION"

# Allow SSH from VPC-A CIDR
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_B_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 10.0.0.0/16 \
  --region "$REGION"

echo "✅ Security group configured (SSH and ICMP allowed from VPC-A)"
```

---

## Step 13 – Launch EC2 Instance in VPC-A

```bash
echo ""
echo "================================================"
echo "LAUNCHING EC2 INSTANCES"
echo "================================================"
echo ""

# Get latest Amazon Linux 2 AMI
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" \
            "Name=state,Values=available" \
  --region "$REGION" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

echo "AMI_ID=$AMI_ID"
echo ""

# Launch instance in VPC-A
echo "Launching instance in VPC-A..."

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

echo "INSTANCE_A_ID=$INSTANCE_A_ID"
echo "Private IP: 10.0.1.10"
echo "✅ Instance-A launched in VPC-A"
```

---

## Step 14 – Launch EC2 Instance in VPC-B

```bash
echo ""
echo "Launching instance in VPC-B..."

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

echo "INSTANCE_B_ID=$INSTANCE_B_ID"
echo "Private IP: 10.1.1.10"
echo "✅ Instance-B launched in VPC-B"
echo ""
echo "Waiting for instances to be running..."

aws ec2 wait instance-running \
  --instance-ids "$INSTANCE_A_ID" "$INSTANCE_B_ID" \
  --region "$REGION"

echo "✅ Both instances are running"
```

---

## Step 15 – Get Instance Public IPs

```bash
echo ""
echo "Retrieving public IP addresses..."

INSTANCE_A_PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_A_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

INSTANCE_B_PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_B_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo ""
echo "Instance-A:"
echo "  Private IP: 10.0.1.10"
echo "  Public IP: $INSTANCE_A_PUBLIC_IP"
echo ""
echo "Instance-B:"
echo "  Private IP: 10.1.1.10"
echo "  Public IP: $INSTANCE_B_PUBLIC_IP"
echo ""
```

---

## Step 16 – Create VPC Peering Connection

```bash
echo ""
echo "================================================"
echo "CREATING VPC PEERING CONNECTION"
echo "================================================"
echo ""

# Create peering connection
PEERING_ID=$(aws ec2 create-vpc-peering-connection \
  --vpc-id "$VPC_A_ID" \
  --peer-vpc-id "$VPC_B_ID" \
  --region "$REGION" \
  --tag-specifications 'ResourceType=vpc-peering-connection,Tags=[{Key=Name,Value=VPC-A-to-VPC-B}]' \
  --query 'VpcPeeringConnection.VpcPeeringConnectionId' \
  --output text)

echo "PEERING_ID=$PEERING_ID"
echo ""

# Accept peering connection
echo "Accepting peering connection..."
aws ec2 accept-vpc-peering-connection \
  --vpc-peering-connection-id "$PEERING_ID" \
  --region "$REGION" \
  --query 'VpcPeeringConnection.Status.Code' \
  --output text

echo ""
echo "✅ VPC peering connection established and accepted"

# Wait for peering to be active
sleep 5

# Verify peering status
PEERING_STATUS=$(aws ec2 describe-vpc-peering-connections \
  --vpc-peering-connection-ids "$PEERING_ID" \
  --region "$REGION" \
  --query 'VpcPeeringConnections[0].Status.Code' \
  --output text)

echo "Peering status: $PEERING_STATUS"
```

---

## Step 17 – Add Peering Routes to VPC-A Route Table

```bash
echo ""
echo "================================================"
echo "UPDATING ROUTE TABLES"
echo "================================================"
echo ""

echo "Adding route to VPC-B in VPC-A route table..."

# Add route from VPC-A to VPC-B
aws ec2 create-route \
  --route-table-id "$RTB_A_ID" \
  --destination-cidr-block 10.1.0.0/16 \
  --vpc-peering-connection-id "$PEERING_ID" \
  --region "$REGION"

echo "✅ Route added: VPC-A → VPC-B (10.1.0.0/16) via peering"
```

---

## Step 18 – Add Peering Routes to VPC-B Route Table

```bash
echo ""
echo "Adding route to VPC-A in VPC-B route table..."

# Add route from VPC-B to VPC-A
aws ec2 create-route \
  --route-table-id "$RTB_B_ID" \
  --destination-cidr-block 10.0.0.0/16 \
  --vpc-peering-connection-id "$PEERING_ID" \
  --region "$REGION"

echo "✅ Route added: VPC-B → VPC-A (10.0.0.0/16) via peering"
echo ""
echo "Route tables updated on both sides!"
```

---

## Step 19 – Display Route Tables

```bash
echo ""
echo "================================================"
echo "ROUTE TABLE VERIFICATION"
echo "================================================"
echo ""

echo "VPC-A Route Table ($RTB_A_ID):"
aws ec2 describe-route-tables \
  --route-table-ids "$RTB_A_ID" \
  --region "$REGION" \
  --query 'RouteTables[0].Routes[*].[DestinationCidrBlock,GatewayId,VpcPeeringConnectionId]' \
  --output table

echo ""
echo "VPC-B Route Table ($RTB_B_ID):"
aws ec2 describe-route-tables \
  --route-table-ids "$RTB_B_ID" \
  --region "$REGION" \
  --query 'RouteTables[0].Routes[*].[DestinationCidrBlock,GatewayId,VpcPeeringConnectionId]' \
  --output table

echo ""
echo "✅ Both route tables show peering routes"
```

---

## Step 20 – Test Connectivity (Ping from VPC-A to VPC-B)

```bash
echo ""
echo "================================================"
echo "TESTING CROSS-VPC CONNECTIVITY"
echo "================================================"
echo ""

echo "Testing ping from Instance-A (VPC-A) to Instance-B (VPC-B)..."
echo ""
echo "SSH into Instance-A and run: ping -c 4 10.1.1.10"
echo ""

# Create test script
cat > test_connectivity.sh <<EOF
#!/bin/bash
echo "Connecting to Instance-A ($INSTANCE_A_PUBLIC_IP)..."
echo "Testing connectivity to Instance-B (10.1.1.10)..."
ssh -i ${KEY_NAME}.pem -o StrictHostKeyChecking=no ec2-user@${INSTANCE_A_PUBLIC_IP} "ping -c 4 10.1.1.10"
EOF

chmod +x test_connectivity.sh

# Wait a moment for SSH to be ready
echo "Waiting for SSH to be ready..."
sleep 30

# Run connectivity test
./test_connectivity.sh

echo ""
echo "✅ If ping successful, VPC peering is working!"
```

---

## Step 21 – Test Reverse Connectivity (Ping from VPC-B to VPC-A)

```bash
echo ""
echo "Testing ping from Instance-B (VPC-B) to Instance-A (VPC-A)..."
echo ""

# Create reverse test script
cat > test_reverse.sh <<EOF
#!/bin/bash
echo "Connecting to Instance-B ($INSTANCE_B_PUBLIC_IP)..."
echo "Testing connectivity to Instance-A (10.0.1.10)..."
ssh -i ${KEY_NAME}.pem -o StrictHostKeyChecking=no ec2-user@${INSTANCE_B_PUBLIC_IP} "ping -c 4 10.0.1.10"
EOF

chmod +x test_reverse.sh

# Run reverse connectivity test
./test_reverse.sh

echo ""
echo "✅ Bidirectional connectivity verified!"
```

---

## Step 22 – Display Peering Connection Details

```bash
echo ""
echo "================================================"
echo "PEERING CONNECTION DETAILS"
echo "================================================"
echo ""

aws ec2 describe-vpc-peering-connections \
  --vpc-peering-connection-ids "$PEERING_ID" \
  --region "$REGION" \
  --query 'VpcPeeringConnections[0].{
    PeeringID:VpcPeeringConnectionId,
    Status:Status.Code,
    RequesterVPC:RequesterVpcInfo.VpcId,
    RequesterCIDR:RequesterVpcInfo.CidrBlock,
    AccepterVPC:AccepterVpcInfo.VpcId,
    AccepterCIDR:AccepterVpcInfo.CidrBlock
  }' \
  --output table

echo ""
echo "✅ VPC peering connection details displayed"
```

---

## Step 23 – Cleanup

```bash
echo ""
echo "Cleaning up resources..."

# Terminate EC2 instances
echo "Terminating EC2 instances..."
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_A_ID" "$INSTANCE_B_ID" \
  --region "$REGION" > /dev/null

echo "Waiting for instances to terminate..."
aws ec2 wait instance-terminated \
  --instance-ids "$INSTANCE_A_ID" "$INSTANCE_B_ID" \
  --region "$REGION"

echo "✅ Instances terminated"

# Delete VPC peering connection
echo "Deleting VPC peering connection..."
aws ec2 delete-vpc-peering-connection \
  --vpc-peering-connection-id "$PEERING_ID" \
  --region "$REGION" > /dev/null

echo "✅ Peering connection deleted"

# Delete security groups
sleep 10
aws ec2 delete-security-group --group-id "$SG_A_ID" --region "$REGION" 2>/dev/null
aws ec2 delete-security-group --group-id "$SG_B_ID" --region "$REGION" 2>/dev/null

echo "✅ Security groups deleted"

# Detach and delete Internet Gateways
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

echo "✅ Internet Gateways deleted"

# Delete subnets
echo "Deleting subnets..."
aws ec2 delete-subnet --subnet-id "$SUBNET_A_ID" --region "$REGION"
aws ec2 delete-subnet --subnet-id "$SUBNET_B_ID" --region "$REGION"

echo "✅ Subnets deleted"

# Delete VPCs
echo "Deleting VPCs..."
aws ec2 delete-vpc --vpc-id "$VPC_A_ID" --region "$REGION"
aws ec2 delete-vpc --vpc-id "$VPC_B_ID" --region "$REGION"

echo "✅ VPCs deleted"

# Delete key pair
echo "Deleting key pair..."
aws ec2 delete-key-pair --key-name "$KEY_NAME" --region "$REGION"
rm -f "${KEY_NAME}.pem"

echo "✅ Key pair deleted"
echo ""
echo "All resources cleaned up!"
```

---

## Summary

In this lab, you have:
- Created two VPCs with non-overlapping CIDR blocks
- Configured subnets, Internet Gateways, and route tables
- Launched EC2 instances in each VPC
- Established VPC peering connection between VPCs
- Updated route tables to enable cross-VPC routing
- Configured security groups for inter-VPC communication
- Tested bidirectional connectivity between instances
- Properly cleaned up all resources

**Key Takeaways:**
- **VPC Peering**: Direct network connection between two VPCs
- **Same Region**: Both VPCs in same region (inter-region peering also supported)
- **Non-Overlapping CIDRs**: VPCs must have different IP ranges
- **No Transitive Routing**: Peering is not transitive (A↔B, B↔C doesn't mean A↔C)
- **Route Table Updates**: Required on both sides for bidirectional traffic
- **Security Groups**: Must allow traffic from peer VPC CIDR

**Common Use Cases:**
- **Shared Services**: Connect production VPC to shared services VPC
- **Multi-Tier Applications**: Separate application tiers into different VPCs
- **Environment Isolation**: Dev, test, prod VPCs with selective peering
- **Cross-Account Connections**: Peer VPCs across different AWS accounts
- **Disaster Recovery**: Connect primary and DR VPCs

---

## Best Practices

**Design:**
- Use non-overlapping CIDR blocks from the start
- Plan IP addressing strategy across all VPCs
- Document peering relationships in network diagrams
- Limit number of peering connections per VPC

**Routing:**
- Use specific CIDR ranges (not 0.0.0.0/0) in peering routes
- Keep route tables simple and well-documented
- Remember: no transitive routing through peering
- Use Transit Gateway for complex hub-and-spoke topologies

**Security:**
- Use security groups to control cross-VPC traffic
- Implement least privilege access between VPCs
- Use NACLs for additional subnet-level protection
- Enable VPC Flow Logs for traffic monitoring

**Cost Optimization:**
- Data transfer within same AZ is free
- Data transfer across AZs incurs charges
- Inter-region peering has data transfer costs
- Monitor data transfer with CloudWatch

**Management:**
- Tag all peering connections consistently
- Use descriptive names for easy identification
- Document which VPCs should communicate
- Regularly audit peering connections

---

## VPC Peering Limitations

**CIDR Restrictions:**
- Cannot have overlapping CIDR blocks
- Cannot modify CIDR after peering established
- Maximum 50 peering connections per VPC (soft limit)

**Routing Limitations:**
- No transitive peering (not a router)
- Cannot peer through another peering connection
- Must update route tables on both sides
- Routes must be more specific than local routes

**Network Limitations:**
- Edge-to-edge routing not supported (VPN, Internet Gateway)
- Cannot use peer's Internet Gateway or NAT Gateway
- IPv6 must be enabled on both VPCs for IPv6 peering
- Jumbo frames (MTU > 1500) not supported across peering

**DNS Limitations:**
- DNS resolution must be enabled for cross-VPC DNS
- Private hosted zones require additional configuration
- Public DNS names don't resolve to private IPs across peering

---

## Advanced Scenarios

**Cross-Account VPC Peering:**
```bash
# In Account A
aws ec2 create-vpc-peering-connection \
  --vpc-id vpc-aaaa \
  --peer-vpc-id vpc-bbbb \
  --peer-owner-id 123456789012

# In Account B
aws ec2 accept-vpc-peering-connection \
  --vpc-peering-connection-id pcx-xxxxx
```

**Inter-Region VPC Peering:**
```bash
# Create peering across regions
aws ec2 create-vpc-peering-connection \
  --vpc-id vpc-aaaa \
  --peer-vpc-id vpc-bbbb \
  --peer-region us-west-2
```

**DNS Resolution Across Peering:**
```bash
# Enable DNS resolution for peering
aws ec2 modify-vpc-peering-connection-options \
  --vpc-peering-connection-id pcx-xxxxx \
  --requester-peering-connection-options AllowDnsResolutionFromRemoteVpc=true \
  --accepter-peering-connection-options AllowDnsResolutionFromRemoteVpc=true
```

---

## Troubleshooting

**Ping fails between VPCs:**
- Verify peering connection status is "active"
- Check route tables have correct routes to peer CIDR
- Verify security groups allow ICMP from peer CIDR
- Check NACLs allow traffic (default allows all)
- Ensure instances have correct private IPs

**Route not appearing:**
- Verify peering connection is accepted
- Check CIDR blocks don't overlap
- Ensure route is more specific than existing routes
- Verify IAM permissions for route table modifications

**Cannot establish peering:**
- Check CIDR blocks for overlap
- Verify both VPCs exist and are active
- Ensure within VPC peering limits (50 per VPC)
- Check if requester/accepter are in allowed accounts

**DNS resolution not working:**
- Enable DNS hostnames on both VPCs
- Enable DNS resolution on peering connection
- Verify security groups allow DNS traffic (UDP 53)
- Check Route53 private hosted zone associations

---

## Additional Resources

- [VPC Peering Documentation](https://docs.aws.amazon.com/vpc/latest/peering/)
- [VPC Peering Scenarios](https://docs.aws.amazon.com/vpc/latest/peering/peering-configurations.html)
- [VPC Peering Limits](https://docs.aws.amazon.com/vpc/latest/peering/vpc-peering-basics.html#vpc-peering-limitations)
- [Transit Gateway vs VPC Peering](https://docs.aws.amazon.com/vpc/latest/tgw/tgw-vpc-peering.html)
- [VPC Peering Pricing](https://aws.amazon.com/vpc/pricing/)
