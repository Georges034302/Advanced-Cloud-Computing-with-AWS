# Lab 4.C: RDS Multi-AZ High Availability with Bastion Host

## Overview
Deploy an RDS MySQL instance with Multi-AZ for high availability, access it via bastion host, test automatic failover, and validate data persistence.

## Objectives
- Create VPC with public and private subnets in two availability zones
- Deploy RDS MySQL with Multi-AZ (primary + standby in different AZs)
- Launch bastion host for secure database access
- Test automatic failover between availability zones
- Validate data persistence after failover

## Prerequisites
- AWS CLI v2 configured
- Permissions: RDS, EC2, VPC
- Basic understanding of MySQL and networking

---

## Variables

```bash
REGION=ap-southeast-2
VPC_CIDR=10.0.0.0/16
PUBLIC_SUBNET_CIDR=10.0.1.0/24
PRIVATE_SUBNET_1_CIDR=10.0.10.0/24
PRIVATE_SUBNET_2_CIDR=10.0.20.0/24
DB_INSTANCE_ID=lab-mysql-multiaz
DB_NAME=labdb
MASTER_USERNAME=labadmin
DB_INSTANCE_CLASS=db.t3.micro
ALLOCATED_STORAGE=20
DB_SUBNET_GROUP=lab-db-subnet-group
KEY_NAME=lab-multiaz-bastion-key

# Generate secure password for RDS master user
MASTER_PASSWORD=$(openssl rand -base64 16)
echo "Master password: $MASTER_PASSWORD (save this!)"
```

---

## Step 1: Create VPC and Subnets

```bash
# Create VPC for Multi-AZ RDS deployment
VPC_ID=$(aws ec2 create-vpc \
  --cidr-block "$VPC_CIDR" \
  --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=lab-multiaz-vpc}]" \
  --query 'Vpc.VpcId' \
  --output text \
  --region "$REGION")
echo "VPC created: $VPC_ID"

# Enable DNS hostnames (required for RDS endpoint resolution)
aws ec2 modify-vpc-attribute \
  --vpc-id "$VPC_ID" \
  --enable-dns-hostnames \
  --region "$REGION"
echo "DNS hostnames enabled"

# Get two availability zones for Multi-AZ deployment
AZ1=$(aws ec2 describe-availability-zones \
  --query 'AvailabilityZones[0].ZoneName' \
  --output text \
  --region "$REGION")
AZ2=$(aws ec2 describe-availability-zones \
  --query 'AvailabilityZones[1].ZoneName' \
  --output text \
  --region "$REGION")
echo "Using availability zones: $AZ1, $AZ2"

# Create public subnet in AZ1 for bastion host
PUBLIC_SUBNET_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_ID" \
  --cidr-block "$PUBLIC_SUBNET_CIDR" \
  --availability-zone "$AZ1" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=lab-public-subnet}]" \
  --query 'Subnet.SubnetId' \
  --output text \
  --region "$REGION")
echo "Public subnet created: $PUBLIC_SUBNET_ID in $AZ1"

# Create first private subnet in AZ1 for RDS primary
PRIVATE_SUBNET_1_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_ID" \
  --cidr-block "$PRIVATE_SUBNET_1_CIDR" \
  --availability-zone "$AZ1" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=lab-private-subnet-1}]" \
  --query 'Subnet.SubnetId' \
  --output text \
  --region "$REGION")
echo "Private subnet 1 created: $PRIVATE_SUBNET_1_ID in $AZ1"

# Create second private subnet in AZ2 for RDS standby
PRIVATE_SUBNET_2_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_ID" \
  --cidr-block "$PRIVATE_SUBNET_2_CIDR" \
  --availability-zone "$AZ2" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=lab-private-subnet-2}]" \
  --query 'Subnet.SubnetId' \
  --output text \
  --region "$REGION")
echo "Private subnet 2 created: $PRIVATE_SUBNET_2_ID in $AZ2"

# Create and attach Internet Gateway for public subnet connectivity
IGW_ID=$(aws ec2 create-internet-gateway \
  --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=lab-igw}]" \
  --query 'InternetGateway.InternetGatewayId' \
  --output text \
  --region "$REGION")
echo "Internet Gateway created: $IGW_ID"

# Attach Internet Gateway to VPC
aws ec2 attach-internet-gateway \
  --internet-gateway-id "$IGW_ID" \
  --vpc-id "$VPC_ID" \
  --region "$REGION"
echo "Internet Gateway attached"

# Create route table for public subnet
PUBLIC_RT_ID=$(aws ec2 create-route-table \
  --vpc-id "$VPC_ID" \
  --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=lab-public-rt}]" \
  --query 'RouteTable.RouteTableId' \
  --output text \
  --region "$REGION")
echo "Route table created: $PUBLIC_RT_ID"

# Add route to Internet Gateway (enables internet access for public subnet)
aws ec2 create-route \
  --route-table-id "$PUBLIC_RT_ID" \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id "$IGW_ID" \
  --region "$REGION"
echo "Route to Internet Gateway added"

# Associate public subnet with route table
aws ec2 associate-route-table \
  --route-table-id "$PUBLIC_RT_ID" \
  --subnet-id "$PUBLIC_SUBNET_ID" \
  --region "$REGION"
echo "Public subnet associated with route table"

# Enable auto-assign public IP for instances in public subnet
aws ec2 modify-subnet-attribute \
  --subnet-id "$PUBLIC_SUBNET_ID" \
  --map-public-ip-on-launch \
  --region "$REGION"
echo "Auto-assign public IP enabled"
```

## Step 3 – Create Subnets Across Two Availability Zones

```bash
# Get availability zones in the region
AVAILABILITY_ZONES=$(aws ec2 describe-availability-zones \
  --region "$REGION" \
  --query 'AvailabilityZones[?State==`available`].ZoneName' \
  --output text)
echo "AVAILABILITY_ZONES=$AVAILABILITY_ZONES"

# Get first availability zone
AZ_1=$(echo "$AVAILABILITY_ZONES" | awk '{print $1}')
echo "AZ_1=$AZ_1"

# Get first two availability zones
AZ_2=$(echo "$AVAILABILITY_ZONES" | awk '{print $2}')
echo "AZ_2=$AZ_2"

# Create public subnet in AZ1 for bastion host
PUBLIC_SUBNET_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_ID" \
  --cidr-block "$PUBLIC_SUBNET_CIDR" \
  --availability-zone "$AZ_1" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=lab-public-subnet},{Key=Lab,Value=4C}]" \
  --region "$REGION" \
  --query 'Subnet.SubnetId' \
  --output text)
echo "PUBLIC_SUBNET_ID=$PUBLIC_SUBNET_ID"

# Create first private subnet in AZ1 for RDS primary
PRIVATE_SUBNET_1_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_ID" \
  --cidr-block "$PRIVATE_SUBNET_1_CIDR" \
  --availability-zone "$AZ_1" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=lab-private-subnet-1},{Key=Lab,Value=4C}]" \
  --region "$REGION" \
  --query 'Subnet.SubnetId' \
  --output text)
echo "PRIVATE_SUBNET_1_ID=$PRIVATE_SUBNET_1_ID"

# Create second private subnet in AZ2 for RDS standby
PRIVATE_SUBNET_2_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_ID" \
  --cidr-block "$PRIVATE_SUBNET_2_CIDR" \
  --availability-zone "$AZ_2" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=lab-private-subnet-2},{Key=Lab,Value=4C}]" \
  --region "$REGION" \
  --query 'Subnet.SubnetId' \
  --output text)
echo "PRIVATE_SUBNET_2_ID=$PRIVATE_SUBNET_2_ID"

echo ""
echo "Subnets created:"
echo "  Public subnet (AZ1): $PUBLIC_SUBNET_ID"
echo "  Private subnet 1 (AZ1): $PRIVATE_SUBNET_1_ID"
echo "  Private subnet 2 (AZ2): $PRIVATE_SUBNET_2_ID"

# Enable auto-assign public IP for public subnet
aws ec2 modify-subnet-attribute \
  --subnet-id "$PUBLIC_SUBNET_ID" \
  --map-public-ip-on-launch \
  --region "$REGION"

echo "Auto-assign public IP enabled for public subnet"
```

---

## Step 4 – Create and Attach Internet Gateway

```bash
# Create Internet Gateway
IGW_ID=$(aws ec2 create-internet-gateway \
  --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=lab-igw},{Key=Lab,Value=4C}]" \
  --region "$REGION" \
  --query 'InternetGateway.InternetGatewayId' \
  --output text)
echo "IGW_ID=$IGW_ID"

# Attach Internet Gateway to VPC
aws ec2 attach-internet-gateway \
  --internet-gateway-id "$IGW_ID" \
  --vpc-id "$VPC_ID" \
  --region "$REGION"

echo "Internet Gateway attached to VPC"

# Verify attachment
aws ec2 describe-internet-gateways \
  --internet-gateway-ids "$IGW_ID" \
  --query 'InternetGateways[0].{InternetGatewayId:InternetGatewayId,State:Attachments[0].State,VpcId:Attachments[0].VpcId}' \
  --output table \
  --region "$REGION"
```

---

## Step 5 – Create Route Tables

```bash
# Create public route table
PUBLIC_RT_ID=$(aws ec2 create-route-table \
  --vpc-id "$VPC_ID" \
  --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=lab-public-rt},{Key=Lab,Value=4C}]" \
  --region "$REGION" \
  --query 'RouteTable.RouteTableId' \
  --output text)
echo "PUBLIC_RT_ID=$PUBLIC_RT_ID"

# Add route to Internet Gateway in public route table
aws ec2 create-route \
  --route-table-id "$PUBLIC_RT_ID" \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id "$IGW_ID" \
  --region "$REGION"

echo "Route to Internet Gateway added to public route table"

# Associate public subnet with public route table
aws ec2 associate-route-table \
  --route-table-id "$PUBLIC_RT_ID" \
  --subnet-id "$PUBLIC_SUBNET_ID" \
  --region "$REGION"

echo "Public subnet associated with public route table"

# Private subnets will use the default route table (no internet access)
echo ""
echo "Network routing configured:"
echo "  Public subnet → Internet Gateway"
echo "  Private subnets → No internet access (isolated)"
```

---

---

## Step 2: Create Security Groups

```bash
# Create security group for bastion host (allows SSH access)
BASTION_SG_ID=$(aws ec2 create-security-group \
  --group-name "lab-bastion-sg" \
  --description "SSH access to bastion host" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' \
  --output text \
  --region "$REGION")
echo "Bastion security group created: $BASTION_SG_ID"

# Allow SSH from anywhere (restrict to your IP in production)
aws ec2 authorize-security-group-ingress \
  --group-id "$BASTION_SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"
echo "SSH access authorized"

# Create security group for RDS (allows MySQL only from bastion)
DB_SG_ID=$(aws ec2 create-security-group \
  --group-name "lab-rds-sg" \
  --description "MySQL access from bastion only" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' \
  --output text \
  --region "$REGION")
echo "RDS security group created: $DB_SG_ID"

# Allow MySQL access only from bastion security group
aws ec2 authorize-security-group-ingress \
  --group-id "$DB_SG_ID" \
  --protocol tcp \
  --port 3306 \
  --source-group "$BASTION_SG_ID" \
  --region "$REGION"
echo "MySQL access authorized from bastion"
```

---

## Step 3: Create DB Subnet Group and RDS Instance

```bash
# Create DB subnet group with both private subnets (required for Multi-AZ)
aws rds create-db-subnet-group \
  --db-subnet-group-name "$DB_SUBNET_GROUP" \
  --db-subnet-group-description "Subnet group for Multi-AZ RDS" \
  --subnet-ids "$PRIVATE_SUBNET_1_ID" "$PRIVATE_SUBNET_2_ID" \
  --tags "Key=Name,Value=lab-db-subnet-group" \
  --region "$REGION"
echo "DB subnet group created: $DB_SUBNET_GROUP"

# Create RDS MySQL instance with Multi-AZ enabled
aws rds create-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --db-instance-class "$DB_INSTANCE_CLASS" \
  --engine mysql \
  --engine-version 8.4.3 \
  --master-username "$MASTER_USERNAME" \
  --master-user-password "$MASTER_PASSWORD" \
  --allocated-storage "$ALLOCATED_STORAGE" \
  --db-name "$DB_NAME" \
  --vpc-security-group-ids "$DB_SG_ID" \
  --db-subnet-group-name "$DB_SUBNET_GROUP" \
  --backup-retention-period 7 \
  --multi-az \
  --no-publicly-accessible \
  --tags "Key=Name,Value=lab-multiaz-db" \
  --region "$REGION"
echo "RDS instance creation initiated (Multi-AZ enabled)"

# Wait for RDS instance to become available (10-15 minutes)
echo "Waiting for RDS instance to be available..."
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$REGION"
echo "RDS instance is available"

# Get database endpoint and availability zone information
DB_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text \
  --region "$REGION")
echo "DB endpoint: $DB_ENDPOINT"

PRIMARY_AZ=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].AvailabilityZone' \
  --output text \
  --region "$REGION")
echo "Primary AZ: $PRIMARY_AZ"

SECONDARY_AZ=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].SecondaryAvailabilityZone' \
  --output text \
  --region "$REGION")
echo "Standby AZ: $SECONDARY_AZ"
```

---

## Step 4: Launch Bastion Host

```bash
# Create SSH key pair for bastion access
aws ec2 create-key-pair \
  --key-name "$KEY_NAME" \
  --query 'KeyMaterial' \
  --output text \
  --region "$REGION" > "${KEY_NAME}.pem"
chmod 400 "${KEY_NAME}.pem"
echo "SSH key created: ${KEY_NAME}.pem"

# Get latest Amazon Linux 2023 AMI
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text \
  --region "$REGION")
echo "Using AMI: $AMI_ID"

# Launch bastion host in public subnet
BASTION_INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --key-name "$KEY_NAME" \
  --subnet-id "$PUBLIC_SUBNET_ID" \
  --security-group-ids "$BASTION_SG_ID" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=lab-bastion-host}]" \
  --query 'Instances[0].InstanceId' \
  --output text \
  --region "$REGION")
echo "Bastion instance launched: $BASTION_INSTANCE_ID"

# Wait for instance to be running
echo "Waiting for bastion to be running..."
aws ec2 wait instance-running \
  --instance-ids "$BASTION_INSTANCE_ID" \
  --region "$REGION"
echo "Bastion is running"

# Get bastion public IP address
BASTION_PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$BASTION_INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$REGION")
echo "Bastion public IP: $BASTION_PUBLIC_IP"
```

---

## Step 5: Connect and Initialize Database

```bash
# Install MySQL client on bastion host
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@"$BASTION_PUBLIC_IP" \
  "sudo dnf install -y mariadb105"
echo "MySQL client installed on bastion"

# Test database connection from bastion
echo "Testing database connection..."
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@"$BASTION_PUBLIC_IP" \
  "mysql -h $DB_ENDPOINT -u $MASTER_USERNAME -p'$MASTER_PASSWORD' -e 'SHOW DATABASES;'"

# Create sample table and insert data
echo "Creating sample table and data..."
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@"$BASTION_PUBLIC_IP" \
  "mysql -h $DB_ENDPOINT -u $MASTER_USERNAME -p'$MASTER_PASSWORD' $DB_NAME -e \"
CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    msg VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO messages (msg) VALUES 
('Message from $PRIMARY_AZ'),
('Multi-AZ test data'),
('Pre-failover record');
SELECT * FROM messages;
\""
echo "Database initialized"
```

---

## Step 12 – Test Automatic Failover

```bash
# Record current primary availability zone
CURRENT_PRIMARY_AZ=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].AvailabilityZone' \
  --output text \
  --region "$REGION")
echo "CURRENT_PRIMARY_AZ=$CURRENT_PRIMARY_AZ"

CURRENT_SECONDARY_AZ=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].SecondaryAvailabilityZone' \
  --output text \
  --region "$REGION")
echo "CURRENT_SECONDARY_AZ=$CURRENT_SECONDARY_AZ"

echo ""
echo "================================================"
echo "INITIATING MULTI-AZ FAILOVER TEST"
echo "================================================"
echo ""
echo "Current configuration:"
echo "  Primary AZ: $CURRENT_PRIMARY_AZ"
echo "  Standby AZ: $CURRENT_SECONDARY_AZ"
echo ""
echo "Initiating reboot with failover..."
echo "This will cause:"
echo "  1. Brief connection interruption (30-60 seconds)"
echo "  2. Standby becomes new primary"
echo "  3. Previous primary becomes new standby"
echo "  4. DNS endpoint remains the same"
echo "  5. No data loss (synchronous replication)"
echo ""

# Initiate failover
aws rds reboot-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --force-failover \
  --region "$REGION"

echo "Failover initiated. Monitoring status..."

# Wait for instance to be available again
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$REGION"

echo ""
echo "✅ Failover completed!"

# Get new availability zones
NEW_PRIMARY_AZ=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].AvailabilityZone' \
  --output text \
  --region "$REGION")
echo "NEW_PRIMARY_AZ=$NEW_PRIMARY_AZ"

NEW_SECONDARY_AZ=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].SecondaryAvailabilityZone' \
  --output text \
  --region "$REGION")
echo "NEW_SECONDARY_AZ=$NEW_SECONDARY_AZ"

# Get endpoint (should be the same)
NEW_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text \
  --region "$REGION")
echo "NEW_ENDPOINT=$NEW_ENDPOINT"

echo ""
echo "================================================"
echo "FAILOVER RESULTS"
echo "================================================"
echo ""
echo "Before failover:"
echo "  Primary AZ: $CURRENT_PRIMARY_AZ"
echo "  Standby AZ: $CURRENT_SECONDARY_AZ"
echo ""
echo "After failover:"
echo "  Primary AZ: $NEW_PRIMARY_AZ (was standby)"
echo "  Standby AZ: $NEW_SECONDARY_AZ (was primary)"
echo ""
echo "Endpoint (unchanged): $NEW_ENDPOINT"
echo ""
echo "================================================"
echo ""
echo "Next: Connect via bastion and verify data persistence"
echo "  mysql -h $NEW_ENDPOINT -P $DB_PORT -u $MASTER_USERNAME -p"
echo "  SELECT @@hostname;"
echo "  USE $DB_NAME;"
echo "  SELECT * FROM messages;  -- Data should still be intact"
```

---

## Step 13 – Validate Data Persistence After Failover

```bash
# Create validation SQL script
cat > validate-failover.sql <<EOF
-- Show current database host
SELECT @@hostname AS current_host;

-- Show current timestamp
SELECT NOW() AS current_time;

-- Verify database exists
SHOW DATABASES;

-- Use the lab database
USE $DB_NAME;

-- Show tables
SHOW TABLES;

-- Count records in messages table
SELECT COUNT(*) AS total_messages FROM messages;

-- Display all messages to verify data integrity
SELECT * FROM messages ORDER BY id;

-- Insert a new record post-failover
INSERT INTO messages (msg) 
VALUES ('Post-failover message - data persisted successfully');

-- Verify the new record
SELECT * FROM messages WHERE msg LIKE 'Post-failover%';

-- Summary
SELECT 
    'Data persistence verified after failover' AS status,
    COUNT(*) AS total_records 
FROM messages;
EOF

echo ""
echo "Failover validation script created: validate-failover.sql"
echo ""
echo "To validate data persistence:"
echo "1. Connect to bastion host"
echo "2. Run: mysql -h $DB_ENDPOINT -P $DB_PORT -u $MASTER_USERNAME -p$MASTER_PASSWORD < validate-failover.sql"
echo ""
echo "Expected results:"
echo "  ✅ All original data intact"
echo "  ✅ Can insert new data"
echo "  ✅ No data loss during failover"
echo "  ✅ Connection automatically redirected to new primary"
```

---

## Step 14 – Monitor RDS Performance Metrics

```bash
# Get CPU utilization
echo "Retrieving RDS CPU utilization metrics..."

aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBInstanceIdentifier,Value="$DB_INSTANCE_ID" \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Average,Maximum \
  --region "$REGION" \
  --query 'Datapoints[*].{Timestamp:Timestamp,Average:Average,Maximum:Maximum}' \
  --output table

# Get database connections
echo ""
echo "Retrieving database connection metrics..."

aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBInstanceIdentifier,Value="$DB_INSTANCE_ID" \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Average,Maximum \
  --region "$REGION" \
  --query 'Datapoints[*].{Timestamp:Timestamp,Average:Average,Maximum:Maximum}' \
  --output table

# Get freeable memory
echo ""
echo "Retrieving freeable memory metrics..."

aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name FreeableMemory \
  --dimensions Name=DBInstanceIdentifier,Value="$DB_INSTANCE_ID" \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Average \
  --region "$REGION" \
  --query 'Datapoints[*].{Timestamp:Timestamp,FreeMemoryBytes:Average}' \
  --output table

# List all available RDS metrics
echo ""
echo "Available CloudWatch metrics for RDS:"
aws cloudwatch list-metrics \
  --namespace AWS/RDS \
  --dimensions Name=DBInstanceIdentifier,Value="$DB_INSTANCE_ID" \
  --region "$REGION" \
  --query 'Metrics[*].MetricName' \
  --output text | tr '\t' '\n' | sort -u
```

---

## Step 15 – Cleanup Resources

```bash
# Terminate bastion host
echo "Terminating bastion host..."
aws ec2 terminate-instances \
  --instance-ids "$BASTION_INSTANCE_ID" \
  --region "$REGION"

# Wait for instance to terminate
echo "Waiting for bastion to terminate..."
aws ec2 wait instance-terminated \
  --instance-ids "$BASTION_INSTANCE_ID" \
  --region "$REGION"

echo "Bastion host terminated"

# Disable deletion protection on RDS instance
echo "Disabling deletion protection..."
aws rds modify-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --no-deletion-protection \
  --apply-immediately \
  --region "$REGION"

# Wait for modification
echo "Waiting for modification to complete..."
sleep 10

# Delete RDS instance
echo "Deleting RDS instance..."
aws rds delete-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --skip-final-snapshot \
  --delete-automated-backups \
  --region "$REGION"

# Wait for instance to be deleted
echo "Waiting for RDS instance to be deleted..."
echo "This may take several minutes..."
aws rds wait db-instance-deleted \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$REGION" || echo "RDS instance deleted"

# Delete DB subnet group
echo "Deleting DB subnet group..."
aws rds delete-db-subnet-group \
  --db-subnet-group-name "lab-db-subnet-group" \
  --region "$REGION"

# Delete security groups
echo "Deleting security groups..."
sleep 10

aws ec2 delete-security-group \
  --group-id "$DB_SG_ID" \
  --region "$REGION"

aws ec2 delete-security-group \
  --group-id "$BASTION_SG_ID" \
  --region "$REGION"

# Disassociate and delete route table
echo "Cleaning up route tables..."
aws ec2 delete-route-table \
  --route-table-id "$PUBLIC_RT_ID" \
  --region "$REGION" || echo "Route table may have associations"

# Delete subnets
echo "Deleting subnets..."
sleep 5

aws ec2 delete-subnet \
  --subnet-id "$PUBLIC_SUBNET_ID" \
  --region "$REGION"

aws ec2 delete-subnet \
  --subnet-id "$PRIVATE_SUBNET_1_ID" \
  --region "$REGION"

aws ec2 delete-subnet \
  --subnet-id "$PRIVATE_SUBNET_2_ID" \
  --region "$REGION"

# Detach and delete Internet Gateway
echo "Detaching and deleting Internet Gateway..."
aws ec2 detach-internet-gateway \
  --internet-gateway-id "$IGW_ID" \
  --vpc-id "$VPC_ID" \
  --region "$REGION"

aws ec2 delete-internet-gateway \
  --internet-gateway-id "$IGW_ID" \
  --region "$REGION"

# Delete VPC
echo "Deleting VPC..."
aws ec2 delete-vpc \
  --vpc-id "$VPC_ID" \
  --region "$REGION"

# Delete local files
echo "Cleaning up local files..."
rm -f bastion-userdata.sh \
  init-database.sql \
  validate-failover.sql

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- RDS MySQL Multi-AZ instance"
echo "- Bastion host EC2 instance"
echo "- DB subnet group"
echo "- Security groups (2)"
echo "- Subnets (3)"
echo "- Route tables"
echo "- Internet Gateway"
echo "- VPC"
echo "- Local SQL scripts"
```

---

## Summary

In this lab, you have:
- Created custom VPC with public and private subnets across two availability zones
- Deployed bastion host in public subnet for secure database access
- Created RDS MySQL instance with Multi-AZ deployment in private subnets
- Configured security groups for layered network security (bastion → database)
- Connected to private RDS instance via bastion host
- Created and populated database with sample data
- Tested automatic failover between availability zones
- Validated data persistence and connection recovery after failover
- Monitored RDS performance with CloudWatch metrics
- Verified endpoint stability during failover

**Key Takeaways:**
- **Multi-AZ (Single Region)**: High availability within one region across multiple AZs
- **Synchronous Replication**: Primary and standby synchronized in real-time (no data loss)
- **Automatic Failover**: 30-60 seconds downtime, fully automated
- **Endpoint Stability**: DNS endpoint remains unchanged during failover
- **Private Deployment**: Databases in private subnets, accessed via bastion host
- **Security Layers**: Bastion SG allows SSH, DB SG allows MySQL only from bastion
- **Data Persistence**: All data intact after failover (synchronous replication)

**Multi-AZ vs Single-AZ:**
| Feature | Single-AZ | Multi-AZ |
|---------|-----------|----------|
| **Availability** | ~99.5% | ~99.95% |
| **Automatic Failover** | No | Yes (30-60s) |
| **Standby Instance** | No | Yes (different AZ) |
| **Replication** | N/A | Synchronous |
| **Cost** | Standard | ~2x single AZ |
| **Use Case** | Dev/Test | Production |
| **Data Loss Risk** | Higher | None (sync) |

**Multi-AZ Failover Scenarios:**
1. **Infrastructure Failure**: AZ outage, hardware failure
2. **Maintenance**: Patching, scaling operations
3. **Manual**: Force failover for testing
4. **Network Issues**: Loss of connectivity to primary

**Failover Process:**
1. Health check detects primary failure
2. DNS automatically redirected to standby
3. Standby promoted to primary
4. Previous primary becomes new standby (when recovered)
5. Applications reconnect automatically
6. Total downtime: 30-60 seconds

**Best Practices:**
- Always use Multi-AZ for production databases
- Place databases in private subnets (no public access)
- Use bastion hosts or SSM for administrative access
- Enable automated backups (7-35 days retention)
- Enable Enhanced Monitoring for detailed metrics
- Test failover regularly in non-production environments
- Use appropriate instance classes for workload
- Enable encryption at rest and in transit
- Monitor CloudWatch metrics for performance
- Set up CloudWatch alarms for critical metrics

**Real-World Use Cases:**
- **Production Databases**: E-commerce, banking, healthcare applications
- **Mission-Critical Apps**: Zero data loss tolerance
- **Compliance Requirements**: High availability mandates
- **24/7 Operations**: Minimal downtime requirements
- **Disaster Recovery**: AZ-level fault tolerance

---

## Additional Resources
- [Amazon RDS Multi-AZ Deployments](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html)
- [RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [Working with Backups](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html)
- [Monitoring RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/monitoring-cloudwatch.html)
- [VPC Security for RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.html)

---
