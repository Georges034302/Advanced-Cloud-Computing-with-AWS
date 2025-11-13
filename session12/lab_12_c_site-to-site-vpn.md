# Lab 12.C: Site-to-Site VPN - Simulate On-Premises Connection

## Overview
This lab simulates a hybrid cloud scenario using AWS Site-to-Site VPN. You'll create two VPCs: one representing your AWS cloud environment and another simulating an on-premises data center. Then establish an encrypted VPN connection between them using Virtual Private Gateway and Customer Gateway.

---

## Objectives
- Create AWS cloud VPC and simulated on-premises VPC
- Configure Virtual Private Gateway (VGW)
- Configure Customer Gateway (CGW)
- Establish Site-to-Site VPN connection with redundant tunnels
- Configure routing between networks
- Test encrypted cross-network connectivity
- Understand VPN tunnel redundancy

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for VPC, VPN, EC2
- Region: ap-southeast-2
- SSH key pair available

---

## Architecture

```
AWS Cloud VPC (10.0.0.0/16)          On-Prem VPC (192.168.0.0/16)
┌──────────────────────┐            ┌──────────────────────┐
│   Virtual Private    │            │  Customer Gateway    │
│      Gateway (VGW)   │            │       (CGW)          │
│          │           │            │          │           │
│   ┌──────▼──────┐    │  VPN       │   ┌──────▼──────┐   │
│   │  EC2 Cloud  │    │◄═══════════►│   │ EC2 On-Prem │   │
│   │  10.0.1.10  │    │  Tunnel 1  │   │ 192.168.1.10│   │
│   └─────────────┘    │  Tunnel 2  │   └─────────────┘   │
│                      │  (IPSec)   │                      │
└──────────────────────┘            └──────────────────────┘
```

---

## Step 1 – Set Variables

```bash
# Set region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "REGION=$REGION"

# Create key pair name
KEY_NAME="vpn-demo-key-$(date +%s)"
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

## Step 3 – Create AWS Cloud VPC

```bash
echo ""
echo "================================================"
echo "CREATING AWS CLOUD VPC"
echo "================================================"
echo ""

# Create cloud VPC
CLOUD_VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --region "$REGION" \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=AWS-Cloud-VPC}]' \
  --query 'Vpc.VpcId' \
  --output text)

echo "CLOUD_VPC_ID=$CLOUD_VPC_ID (10.0.0.0/16)"

# Enable DNS hostnames
aws ec2 modify-vpc-attribute \
  --vpc-id "$CLOUD_VPC_ID" \
  --enable-dns-hostnames \
  --region "$REGION"

# Create subnet
CLOUD_SUBNET_ID=$(aws ec2 create-subnet \
  --vpc-id "$CLOUD_VPC_ID" \
  --cidr-block 10.0.1.0/24 \
  --availability-zone "${REGION}a" \
  --region "$REGION" \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=Cloud-Subnet}]' \
  --query 'Subnet.SubnetId' \
  --output text)

echo "CLOUD_SUBNET_ID=$CLOUD_SUBNET_ID (10.0.1.0/24)"

aws ec2 modify-subnet-attribute \
  --subnet-id "$CLOUD_SUBNET_ID" \
  --map-public-ip-on-launch \
  --region "$REGION"

echo "✅ AWS Cloud VPC created"
```

---

## Step 4 – Create Internet Gateway for Cloud VPC

```bash
echo ""
echo "Creating Internet Gateway for Cloud VPC..."

CLOUD_IGW_ID=$(aws ec2 create-internet-gateway \
  --region "$REGION" \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=Cloud-IGW}]' \
  --query 'InternetGateway.InternetGatewayId' \
  --output text)

aws ec2 attach-internet-gateway \
  --internet-gateway-id "$CLOUD_IGW_ID" \
  --vpc-id "$CLOUD_VPC_ID" \
  --region "$REGION"

echo "✅ Internet Gateway attached to Cloud VPC"

# Update route table
CLOUD_RTB_ID=$(aws ec2 describe-route-tables \
  --filters "Name=vpc-id,Values=$CLOUD_VPC_ID" "Name=association.main,Values=true" \
  --region "$REGION" \
  --query 'RouteTables[0].RouteTableId' \
  --output text)

aws ec2 create-route \
  --route-table-id "$CLOUD_RTB_ID" \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id "$CLOUD_IGW_ID" \
  --region "$REGION"

echo "✅ Route table updated for Internet access"
```

---

## Step 5 – Create On-Premises Simulated VPC

```bash
echo ""
echo "================================================"
echo "CREATING ON-PREMISES SIMULATED VPC"
echo "================================================"
echo ""

# Create on-prem VPC
ONPREM_VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 192.168.0.0/16 \
  --region "$REGION" \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=OnPrem-VPC}]' \
  --query 'Vpc.VpcId' \
  --output text)

echo "ONPREM_VPC_ID=$ONPREM_VPC_ID (192.168.0.0/16)"

# Enable DNS hostnames
aws ec2 modify-vpc-attribute \
  --vpc-id "$ONPREM_VPC_ID" \
  --enable-dns-hostnames \
  --region "$REGION"

# Create subnet
ONPREM_SUBNET_ID=$(aws ec2 create-subnet \
  --vpc-id "$ONPREM_VPC_ID" \
  --cidr-block 192.168.1.0/24 \
  --availability-zone "${REGION}a" \
  --region "$REGION" \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=OnPrem-Subnet}]' \
  --query 'Subnet.SubnetId' \
  --output text)

echo "ONPREM_SUBNET_ID=$ONPREM_SUBNET_ID (192.168.1.0/24)"

aws ec2 modify-subnet-attribute \
  --subnet-id "$ONPREM_SUBNET_ID" \
  --map-public-ip-on-launch \
  --region "$REGION"

echo "✅ On-Premises VPC created"
```

---

## Step 6 – Create Internet Gateway for On-Prem VPC

```bash
echo ""
echo "Creating Internet Gateway for On-Prem VPC..."

ONPREM_IGW_ID=$(aws ec2 create-internet-gateway \
  --region "$REGION" \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=OnPrem-IGW}]' \
  --query 'InternetGateway.InternetGatewayId' \
  --output text)

aws ec2 attach-internet-gateway \
  --internet-gateway-id "$ONPREM_IGW_ID" \
  --vpc-id "$ONPREM_VPC_ID" \
  --region "$REGION"

echo "✅ Internet Gateway attached to On-Prem VPC"

# Update route table
ONPREM_RTB_ID=$(aws ec2 describe-route-tables \
  --filters "Name=vpc-id,Values=$ONPREM_VPC_ID" "Name=association.main,Values=true" \
  --region "$REGION" \
  --query 'RouteTables[0].RouteTableId' \
  --output text)

aws ec2 create-route \
  --route-table-id "$ONPREM_RTB_ID" \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id "$ONPREM_IGW_ID" \
  --region "$REGION"

echo "✅ Route table updated for Internet access"
```

---

## Step 7 – Create Security Groups

```bash
echo ""
echo "Creating security groups..."

# Cloud VPC security group
CLOUD_SG_ID=$(aws ec2 create-security-group \
  --group-name "Cloud-SG" \
  --description "Security group for Cloud VPC" \
  --vpc-id "$CLOUD_VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

aws ec2 authorize-security-group-ingress \
  --group-id "$CLOUD_SG_ID" \
  --protocol tcp --port 22 --cidr 0.0.0.0/0 \
  --region "$REGION"

aws ec2 authorize-security-group-ingress \
  --group-id "$CLOUD_SG_ID" \
  --protocol icmp --port -1 --cidr 192.168.0.0/16 \
  --region "$REGION"

echo "✅ Cloud SG created (allow SSH and ICMP from On-Prem)"

# On-Prem VPC security group
ONPREM_SG_ID=$(aws ec2 create-security-group \
  --group-name "OnPrem-SG" \
  --description "Security group for On-Prem VPC" \
  --vpc-id "$ONPREM_VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

aws ec2 authorize-security-group-ingress \
  --group-id "$ONPREM_SG_ID" \
  --protocol tcp --port 22 --cidr 0.0.0.0/0 \
  --region "$REGION"

aws ec2 authorize-security-group-ingress \
  --group-id "$ONPREM_SG_ID" \
  --protocol icmp --port -1 --cidr 10.0.0.0/16 \
  --region "$REGION"

# Allow VPN protocols (UDP 500, 4500 for IPSec)
aws ec2 authorize-security-group-ingress \
  --group-id "$ONPREM_SG_ID" \
  --protocol udp --port 500 --cidr 0.0.0.0/0 \
  --region "$REGION"

aws ec2 authorize-security-group-ingress \
  --group-id "$ONPREM_SG_ID" \
  --protocol udp --port 4500 --cidr 0.0.0.0/0 \
  --region "$REGION"

echo "✅ On-Prem SG created (allow SSH, ICMP from Cloud, VPN protocols)"
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

# Launch Cloud instance
CLOUD_INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --key-name "$KEY_NAME" \
  --subnet-id "$CLOUD_SUBNET_ID" \
  --security-group-ids "$CLOUD_SG_ID" \
  --private-ip-address 10.0.1.10 \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Cloud-Instance}]' \
  --region "$REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Cloud-Instance: $CLOUD_INSTANCE_ID (10.0.1.10)"

# Launch On-Prem instance
ONPREM_INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --key-name "$KEY_NAME" \
  --subnet-id "$ONPREM_SUBNET_ID" \
  --security-group-ids "$ONPREM_SG_ID" \
  --private-ip-address 192.168.1.10 \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=OnPrem-Instance}]' \
  --region "$REGION" \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "OnPrem-Instance: $ONPREM_INSTANCE_ID (192.168.1.10)"
echo ""
echo "Waiting for instances to be running..."

aws ec2 wait instance-running \
  --instance-ids "$CLOUD_INSTANCE_ID" "$ONPREM_INSTANCE_ID" \
  --region "$REGION"

echo "✅ Both instances running"
```

---

## Step 9 – Get On-Prem Instance Public IP (for Customer Gateway)

```bash
echo ""
echo "Getting On-Prem instance public IP..."

ONPREM_PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$ONPREM_INSTANCE_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo "ONPREM_PUBLIC_IP=$ONPREM_PUBLIC_IP"
echo ""
echo "This will be used as the Customer Gateway public IP"
```

---

## Step 10 – Create Virtual Private Gateway

```bash
echo ""
echo "================================================"
echo "CREATING VIRTUAL PRIVATE GATEWAY"
echo "================================================"
echo ""

# Create VGW
VGW_ID=$(aws ec2 create-vpn-gateway \
  --type ipsec.1 \
  --tag-specifications 'ResourceType=vpn-gateway,Tags=[{Key=Name,Value=Cloud-VGW}]' \
  --region "$REGION" \
  --query 'VpnGateway.VpnGatewayId' \
  --output text)

echo "VGW_ID=$VGW_ID"

# Attach VGW to Cloud VPC
aws ec2 attach-vpn-gateway \
  --vpn-gateway-id "$VGW_ID" \
  --vpc-id "$CLOUD_VPC_ID" \
  --region "$REGION"

echo "✅ Virtual Private Gateway created and attached to Cloud VPC"
echo ""
echo "Waiting for VGW to be available..."
sleep 10
```

---

## Step 11 – Create Customer Gateway

```bash
echo ""
echo "================================================"
echo "CREATING CUSTOMER GATEWAY"
echo "================================================"
echo ""

# Create CGW pointing to On-Prem public IP
CGW_ID=$(aws ec2 create-customer-gateway \
  --type ipsec.1 \
  --public-ip "$ONPREM_PUBLIC_IP" \
  --bgp-asn 65000 \
  --tag-specifications 'ResourceType=customer-gateway,Tags=[{Key=Name,Value=OnPrem-CGW}]' \
  --region "$REGION" \
  --query 'CustomerGateway.CustomerGatewayId' \
  --output text)

echo "CGW_ID=$CGW_ID"
echo "Customer Gateway IP: $ONPREM_PUBLIC_IP"
echo ""
echo "✅ Customer Gateway created"
```

---

## Step 12 – Create Site-to-Site VPN Connection

```bash
echo ""
echo "================================================"
echo "CREATING SITE-TO-SITE VPN CONNECTION"
echo "================================================"
echo ""

# Create VPN connection
VPN_ID=$(aws ec2 create-vpn-connection \
  --type ipsec.1 \
  --customer-gateway-id "$CGW_ID" \
  --vpn-gateway-id "$VGW_ID" \
  --options "StaticRoutesOnly=true" \
  --tag-specifications 'ResourceType=vpn-connection,Tags=[{Key=Name,Value=Cloud-OnPrem-VPN}]' \
  --region "$REGION" \
  --query 'VpnConnection.VpnConnectionId' \
  --output text)

echo "VPN_ID=$VPN_ID"
echo ""
echo "VPN Connection created with 2 redundant tunnels!"
echo "Waiting for VPN to be available (this takes 1-2 minutes)..."

# Wait for VPN to be available
sleep 60

# Check VPN status
VPN_STATE=$(aws ec2 describe-vpn-connections \
  --vpn-connection-ids "$VPN_ID" \
  --region "$REGION" \
  --query 'VpnConnections[0].State' \
  --output text)

echo "VPN State: $VPN_STATE"
echo ""
echo "✅ Site-to-Site VPN Connection established"
```

---

## Step 13 – Add Static Route to VPN Connection

```bash
echo ""
echo "Adding static route for On-Prem network..."

# Add static route for on-prem CIDR
aws ec2 create-vpn-connection-route \
  --vpn-connection-id "$VPN_ID" \
  --destination-cidr-block 192.168.0.0/16 \
  --region "$REGION"

echo "✅ Static route added: 192.168.0.0/16 via VPN"
```

---

## Step 14 – Enable Route Propagation

```bash
echo ""
echo "Enabling VPN route propagation in Cloud VPC route table..."

# Enable route propagation
aws ec2 enable-vgw-route-propagation \
  --route-table-id "$CLOUD_RTB_ID" \
  --gateway-id "$VGW_ID" \
  --region "$REGION"

echo "✅ VPN routes will automatically propagate to Cloud VPC"
```

---

## Step 15 – Add Route to On-Prem Route Table

```bash
echo ""
echo "Adding route to On-Prem route table for Cloud VPC..."

# Add route to Cloud VPC via VPN Gateway
aws ec2 create-route \
  --route-table-id "$ONPREM_RTB_ID" \
  --destination-cidr-block 10.0.0.0/16 \
  --gateway-id "$VGW_ID" \
  --region "$REGION"

echo "✅ Route added: 10.0.0.0/16 via VGW"
```

---

## Step 16 – View VPN Connection Details

```bash
echo ""
echo "================================================"
echo "VPN CONNECTION DETAILS"
echo "================================================"
echo ""

aws ec2 describe-vpn-connections \
  --vpn-connection-ids "$VPN_ID" \
  --region "$REGION" \
  --query 'VpnConnections[0].{
    VpnId:VpnConnectionId,
    State:State,
    CustomerGatewayIP:CustomerGatewayConfiguration,
    Tunnel1Status:VgwTelemetry[0].Status,
    Tunnel2Status:VgwTelemetry[1].Status
  }' \
  --output table

echo ""
echo "VPN Tunnels:"
aws ec2 describe-vpn-connections \
  --vpn-connection-ids "$VPN_ID" \
  --region "$REGION" \
  --query 'VpnConnections[0].VgwTelemetry[*].[OutsideIpAddress,Status,StatusMessage]' \
  --output table

echo ""
echo "✅ VPN connection has 2 redundant tunnels for high availability"
```

---

## Step 17 – View Route Tables

```bash
echo ""
echo "================================================"
echo "ROUTE TABLE VERIFICATION"
echo "================================================"
echo ""

echo "Cloud VPC Route Table (with VPN propagation):"
aws ec2 describe-route-tables \
  --route-table-ids "$CLOUD_RTB_ID" \
  --region "$REGION" \
  --query 'RouteTables[0].Routes[*].[DestinationCidrBlock,GatewayId,VpcPeeringConnectionId,State]' \
  --output table

echo ""
echo "On-Prem VPC Route Table:"
aws ec2 describe-route-tables \
  --route-table-ids "$ONPREM_RTB_ID" \
  --region "$REGION" \
  --query 'RouteTables[0].Routes[*].[DestinationCidrBlock,GatewayId,State]' \
  --output table

echo ""
echo "✅ Routes configured for VPN traffic"
```

---

## Step 18 – Test Connectivity (Simulated)

```bash
echo ""
echo "================================================"
echo "CONNECTIVITY TEST (SIMULATED)"
echo "================================================"
echo ""

echo "NOTE: In a real scenario, you would:"
echo "1. SSH into Cloud-Instance (10.0.1.10)"
echo "2. Ping OnPrem-Instance (192.168.1.10) through VPN tunnel"
echo "3. Verify encrypted traffic flows through IPSec tunnel"
echo ""

# Get public IPs
CLOUD_PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$CLOUD_INSTANCE_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo "Cloud-Instance Public IP: $CLOUD_PUBLIC_IP"
echo "OnPrem-Instance Public IP: $ONPREM_PUBLIC_IP"
echo ""
echo "To test manually:"
echo "  ssh -i ${KEY_NAME}.pem ec2-user@${CLOUD_PUBLIC_IP}"
echo "  ping 192.168.1.10"
echo ""
echo "⚠️  Note: Actual VPN tunnel connectivity requires"
echo "   proper VPN configuration on the Customer Gateway side"
echo "   (software VPN or hardware appliance)"
```

---

## Step 19 – Display VPN Configuration

```bash
echo ""
echo "================================================"
echo "VPN CONFIGURATION DOWNLOAD"
echo "================================================"
echo ""

echo "Downloading VPN configuration file..."

# Download VPN configuration
aws ec2 describe-vpn-connections \
  --vpn-connection-ids "$VPN_ID" \
  --region "$REGION" \
  --query 'VpnConnections[0].CustomerGatewayConfiguration' \
  --output text > vpn-config.xml

echo "✅ VPN configuration saved to: vpn-config.xml"
echo ""
echo "This file contains:"
echo "  - Pre-shared keys for both tunnels"
echo "  - Tunnel endpoint IPs"
echo "  - IPSec configuration parameters"
echo "  - BGP configuration (if using dynamic routing)"
echo ""
echo "Use this to configure your on-premises VPN device"
```

---

## Step 20 – Cleanup

```bash
echo ""
echo "Cleaning up resources..."
echo ""

# Terminate instances
echo "Terminating EC2 instances..."
aws ec2 terminate-instances \
  --instance-ids "$CLOUD_INSTANCE_ID" "$ONPREM_INSTANCE_ID" \
  --region "$REGION" > /dev/null

aws ec2 wait instance-terminated \
  --instance-ids "$CLOUD_INSTANCE_ID" "$ONPREM_INSTANCE_ID" \
  --region "$REGION"

echo "✅ Instances terminated"

# Delete VPN connection
echo "Deleting VPN connection..."
aws ec2 delete-vpn-connection \
  --vpn-connection-id "$VPN_ID" \
  --region "$REGION"

echo "Waiting for VPN deletion (30 seconds)..."
sleep 30

echo "✅ VPN connection deleted"

# Detach and delete VGW
echo "Detaching and deleting Virtual Private Gateway..."
aws ec2 detach-vpn-gateway \
  --vpn-gateway-id "$VGW_ID" \
  --vpc-id "$CLOUD_VPC_ID" \
  --region "$REGION"

sleep 10

aws ec2 delete-vpn-gateway \
  --vpn-gateway-id "$VGW_ID" \
  --region "$REGION"

echo "✅ VGW deleted"

# Delete Customer Gateway
echo "Deleting Customer Gateway..."
aws ec2 delete-customer-gateway \
  --customer-gateway-id "$CGW_ID" \
  --region "$REGION"

echo "✅ CGW deleted"

# Delete security groups
sleep 10
aws ec2 delete-security-group --group-id "$CLOUD_SG_ID" --region "$REGION" 2>/dev/null
aws ec2 delete-security-group --group-id "$ONPREM_SG_ID" --region "$REGION" 2>/dev/null

echo "✅ Security groups deleted"

# Delete Internet Gateways
echo "Deleting Internet Gateways..."
aws ec2 detach-internet-gateway \
  --internet-gateway-id "$CLOUD_IGW_ID" \
  --vpc-id "$CLOUD_VPC_ID" \
  --region "$REGION"

aws ec2 delete-internet-gateway \
  --internet-gateway-id "$CLOUD_IGW_ID" \
  --region "$REGION"

aws ec2 detach-internet-gateway \
  --internet-gateway-id "$ONPREM_IGW_ID" \
  --vpc-id "$ONPREM_VPC_ID" \
  --region "$REGION"

aws ec2 delete-internet-gateway \
  --internet-gateway-id "$ONPREM_IGW_ID" \
  --region "$REGION"

echo "✅ Internet Gateways deleted"

# Delete subnets
echo "Deleting subnets..."
aws ec2 delete-subnet --subnet-id "$CLOUD_SUBNET_ID" --region "$REGION"
aws ec2 delete-subnet --subnet-id "$ONPREM_SUBNET_ID" --region "$REGION"

echo "✅ Subnets deleted"

# Delete VPCs
echo "Deleting VPCs..."
aws ec2 delete-vpc --vpc-id "$CLOUD_VPC_ID" --region "$REGION"
aws ec2 delete-vpc --vpc-id "$ONPREM_VPC_ID" --region "$REGION"

echo "✅ VPCs deleted"

# Delete key pair and config file
aws ec2 delete-key-pair --key-name "$KEY_NAME" --region "$REGION"
rm -f "${KEY_NAME}.pem" vpn-config.xml

echo "✅ Key pair deleted"
echo ""
echo "All resources cleaned up!"
```

---

## Summary

In this lab, you have:
- Created AWS cloud VPC and simulated on-premises VPC
- Configured Virtual Private Gateway on cloud side
- Configured Customer Gateway representing on-prem endpoint
- Established Site-to-Site VPN with redundant tunnels
- Configured static routing between networks
- Enabled route propagation for dynamic updates
- Downloaded VPN configuration for on-prem device setup
- Understood VPN tunnel redundancy and failover

**Key Takeaways:**
- **Encrypted Connection**: IPSec tunnels provide secure connectivity
- **Redundant Tunnels**: Two tunnels for high availability
- **Hybrid Cloud**: Extends on-prem network to AWS securely
- **Static or Dynamic**: Supports both static routes and BGP
- **Cost**: $0.05/hour per VPN connection + data transfer

**Site-to-Site VPN Components:**

| Component | Purpose |
|-----------|---------|
| Virtual Private Gateway (VGW) | AWS side VPN concentrator |
| Customer Gateway (CGW) | On-premises VPN device/endpoint |
| VPN Connection | Two IPSec tunnels |
| Route Propagation | Automatic route updates |

---

## Best Practices

**Design:**
- Use two tunnels for redundancy (automatic)
- Configure both tunnels on customer gateway
- Monitor tunnel health with CloudWatch
- Document VPN configuration

**Routing:**
- Use BGP for dynamic routing (preferred)
- Use static routes for simple setups
- Enable route propagation in VPC
- Avoid overlapping CIDR blocks

**Security:**
- Use strong pre-shared keys
- Rotate keys periodically
- Limit security group access
- Enable VPC Flow Logs
- Use AWS Certificate Manager for IKEv2

**Performance:**
- VPN bandwidth: up to 1.25 Gbps per tunnel
- Use AWS Transit Gateway for higher throughput
- Monitor latency and packet loss
- Consider Direct Connect for high bandwidth needs

---

## Real-World VPN Setup

**On-Premises VPN Devices:**
- Cisco ASA, ISR, Meraki
- Juniper SRX, SSG
- Palo Alto Networks
- pfSense, strongSwan (software)
- AWS provides device-specific config files

**Configuration Steps:**
1. Download VPN config from AWS
2. Apply config to on-prem device
3. Configure both tunnels
4. Test failover between tunnels
5. Monitor tunnel health

**Troubleshooting:**
- Check pre-shared keys match
- Verify security group rules
- Ensure NAT-T is enabled (UDP 4500)
- Check on-prem firewall rules
- Monitor VPN tunnel status in console

---

## Additional Resources

- [Site-to-Site VPN Documentation](https://docs.aws.amazon.com/vpn/latest/s2svpn/)
- [VPN Device Configuration](https://docs.aws.amazon.com/vpn/latest/s2svpn/your-cgw.html)
- [VPN CloudWatch Metrics](https://docs.aws.amazon.com/vpn/latest/s2svpn/monitoring-cloudwatch-vpn.html)
- [VPN Pricing](https://aws.amazon.com/vpn/pricing/)
- [Transit Gateway VPN](https://docs.aws.amazon.com/vpc/latest/tgw/tgw-vpn-attachments.html)
