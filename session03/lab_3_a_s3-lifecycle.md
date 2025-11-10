# Lab 3.B: NAT Gateway, VPC Peering, and VPC Endpoints

## Overview
This lab extends VPC networking concepts by implementing NAT Gateway for private subnet internet access, configuring VPC peering for inter-VPC communication, and using VPC endpoints for private AWS service access. These advanced networking patterns are essential for production environments requiring secure and efficient cloud connectivity.

## Objectives
- Configure NAT Gateway for private subnet internet access
- Implement VPC Peering between two VPCs
- Create VPC Endpoints for S3 and other AWS services
- Understand the difference between NAT Gateway and NAT Instance
- Configure route tables for advanced networking scenarios
- Optimize costs and security with VPC endpoints

## Requirements
- Completed Lab 3.A or equivalent VPC knowledge
- AWS account with VPC and EC2 permissions
- Understanding of routing and network address translation
- Basic knowledge of AWS service endpoints

## Steps

### Step 1: Allocate Elastic IP for NAT Gateway
1. Navigate to VPC → Elastic IPs
2. Click "Allocate Elastic IP address"
3. Configure:
   - Network Border Group: Select your region
   - Tags: Name = `nat-gateway-eip`
4. Allocate
5. Note the allocated Elastic IP address

### Step 2: Create NAT Gateway
1. Navigate to VPC → NAT Gateways
2. Click "Create NAT gateway"
3. Configure:
   - Name: `lab-nat-gateway`
   - Subnet: `public-subnet-1` (from Lab 3.A)
   - Connectivity type: Public
   - Elastic IP allocation ID: Select the EIP from Step 1
4. Create NAT gateway
5. Wait for status to change to "Available"

### Step 3: Update Private Route Table
1. Navigate to Route Tables
2. Select `private-rt` (from Lab 3.A)
3. Routes tab → Edit routes
4. Add route:
   - Destination: `0.0.0.0/0`
   - Target: NAT Gateway (`lab-nat-gateway`)
5. Save changes

### Step 4: Test Private Subnet Internet Access
1. Launch bastion host in public subnet (if not already):
   - Instance in `public-subnet-1`
   - Enable public IP
   - Security group: Allow SSH from My IP
2. Launch instance in private subnet:
   - Instance in `private-subnet-1`
   - No public IP
   - Security group: Allow SSH from public subnet CIDR
3. Connect to bastion host via SSH
4. From bastion, SSH to private instance:
   ```bash
   ssh -i keypair.pem ec2-user@<private-ip>
   ```
5. Test internet access from private instance:
   ```bash
   ping -c 4 google.com
   yum update -y
   curl http://checkip.amazonaws.com
   ```

### Step 5: Create Second VPC for Peering
1. Navigate to VPC → Create VPC
2. Configure:
   - Name: `lab-vpc-2`
   - IPv4 CIDR: `10.1.0.0/16` (different from lab-vpc)
   - Create VPC
3. Create subnet in new VPC:
   - Name: `vpc2-subnet-1`
   - CIDR: `10.1.1.0/24`
4. Create Internet Gateway:
   - Name: `lab-vpc-2-igw`
   - Attach to `lab-vpc-2`
5. Create and configure route table for internet access

### Step 6: Create VPC Peering Connection
1. Navigate to VPC → Peering Connections
2. Click "Create peering connection"
3. Configure:
   - Name: `lab-vpc-peering`
   - VPC (Requester): `lab-vpc` (10.0.0.0/16)
   - VPC (Accepter): `lab-vpc-2` (10.1.0.0/16)
4. Create peering connection
5. Select the peering connection → Actions → Accept request
6. Accept the peering connection

### Step 7: Update Route Tables for VPC Peering
1. **For lab-vpc route tables:**
   - Select `private-rt`
   - Add route: Destination `10.1.0.0/16`, Target: Peering connection
   - Select `public-rt`
   - Add route: Destination `10.1.0.0/16`, Target: Peering connection

2. **For lab-vpc-2 route table:**
   - Select the route table
   - Add route: Destination `10.0.0.0/16`, Target: Peering connection

### Step 8: Test VPC Peering
1. Launch instance in `lab-vpc-2`:
   - Subnet: `vpc2-subnet-1`
   - Security group: Allow ICMP and SSH from 10.0.0.0/16
2. From instance in `lab-vpc`, ping instance in `lab-vpc-2`:
   ```bash
   ping -c 4 <vpc2-instance-private-ip>
   ```
3. Establish SSH connection across VPCs
4. Verify connectivity works in both directions

### Step 9: Create S3 Gateway Endpoint
1. Navigate to VPC → Endpoints
2. Click "Create endpoint"
3. Configure:
   - Name: `s3-gateway-endpoint`
   - Service category: AWS services
   - Services: com.amazonaws.[region].s3 (Gateway type)
   - VPC: `lab-vpc`
   - Route tables: Select `private-rt`
4. Create endpoint
5. Verify route automatically added to private route table

### Step 10: Test S3 Gateway Endpoint
1. Connect to instance in private subnet
2. Create test file and upload to S3:
   ```bash
   echo "Test from private subnet" > test.txt
   aws s3 mb s3://my-vpc-endpoint-test-bucket-$(date +%s)
   aws s3 cp test.txt s3://my-vpc-endpoint-test-bucket-[timestamp]/
   aws s3 ls s3://my-vpc-endpoint-test-bucket-[timestamp]/
   ```
3. Monitor VPC Flow Logs to confirm traffic uses endpoint
4. Note: No NAT Gateway charges for S3 access!

### Step 11: Create Interface Endpoint (Optional)
1. Create endpoint for EC2:
   - Service: com.amazonaws.[region].ec2
   - Type: Interface
   - VPC: `lab-vpc`
   - Subnets: Select private subnets
   - Security group: Allow HTTPS (443) from VPC CIDR
2. Create endpoint
3. Test EC2 API access without internet:
   ```bash
   aws ec2 describe-instances --region [your-region]
   ```

### Step 12: Monitor and Optimize Costs
1. Navigate to Cost Explorer (if enabled)
2. Review NAT Gateway data processing charges
3. Identify S3 traffic using gateway endpoint (no charges)
4. Compare costs with and without VPC endpoints
5. Review VPC Flow Logs for traffic analysis

## Validation
- [ ] NAT Gateway created and operational
- [ ] Private subnet instances can access internet via NAT Gateway
- [ ] VPC Peering connection established and accepted
- [ ] Instances can communicate across peered VPCs
- [ ] S3 Gateway Endpoint created and route added
- [ ] S3 access from private subnet works without NAT Gateway
- [ ] Interface endpoint created (optional)
- [ ] Security groups properly configured for all scenarios

## Cleanup
1. Delete VPC Endpoints:
   - Select endpoints → Delete
2. Delete VPC Peering Connection:
   - Select peering → Actions → Delete
3. Terminate all EC2 instances in both VPCs
4. Delete NAT Gateway:
   - Select → Actions → Delete
   - Wait for deletion to complete
5. Release Elastic IP:
   - Select EIP → Actions → Release
6. Delete lab-vpc-2:
   - Delete subnets, IGW, route tables, VPC
7. Clean up lab-vpc if no longer needed
8. Verify all billable resources are removed

## Summary
In this lab, you implemented advanced VPC networking features including NAT Gateway for private subnet internet access, VPC Peering for multi-VPC communication, and VPC Endpoints for cost-efficient AWS service access. You learned how to design secure network architectures that balance connectivity requirements with cost optimization and security best practices.

**Key Takeaways:**
- NAT Gateway enables private subnet internet access with high availability
- NAT Gateway is managed by AWS and scales automatically
- VPC Peering allows direct network connectivity between VPCs
- Peering is non-transitive; connections must be explicit
- Gateway endpoints (S3, DynamoDB) have no additional charges
- Interface endpoints incur hourly and data processing charges
- VPC endpoints keep traffic within AWS network for security
- Always update security groups and route tables for connectivity
- Consider cost implications of NAT Gateway vs VPC endpoints
