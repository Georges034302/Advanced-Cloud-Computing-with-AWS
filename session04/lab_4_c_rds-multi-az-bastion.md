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
SECRET_NAME=lab/rds/multiaz/master
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

## Step 3: Store Credentials in Secrets Manager

```bash
# Generate secure password for RDS master user
MASTER_PASSWORD=$(openssl rand -base64 16)
echo "Master password generated (hidden for security)"

# Store credentials in AWS Secrets Manager
aws secretsmanager create-secret \
  --name "$SECRET_NAME" \
  --description "RDS MySQL Multi-AZ master credentials" \
  --secret-string "{\"username\":\"$MASTER_USERNAME\",\"password\":\"$MASTER_PASSWORD\"}" \
  --region "$REGION"
echo "Secret created: $SECRET_NAME"
```

---

## Step 4: Create DB Subnet Group and RDS Instance

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

## Step 5: Launch Bastion Host

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

## Step 6: Connect and Initialize Database

```bash
# Retrieve password from Secrets Manager
MASTER_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" \
  --query 'SecretString' \
  --output text \
  --region "$REGION" | jq -r '.password')
echo "Password retrieved from Secrets Manager"

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

## Step 7: Test Multi-AZ Failover

```bash
# Record current primary and standby AZs before failover
CURRENT_PRIMARY=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].AvailabilityZone' \
  --output text \
  --region "$REGION")
echo "Current primary AZ: $CURRENT_PRIMARY"

CURRENT_STANDBY=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].SecondaryAvailabilityZone' \
  --output text \
  --region "$REGION")
echo "Current standby AZ: $CURRENT_STANDBY"

# Initiate failover (forces standby to become primary)
echo "Initiating failover..."
aws rds reboot-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --force-failover \
  --region "$REGION"

# Wait for instance to be available after failover (30-60 seconds)
echo "Waiting for failover to complete..."
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$REGION"
echo "Failover completed"

# Get new primary and standby AZs after failover
NEW_PRIMARY=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].AvailabilityZone' \
  --output text \
  --region "$REGION")
echo "New primary AZ: $NEW_PRIMARY (was standby)"

NEW_STANDBY=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].SecondaryAvailabilityZone' \
  --output text \
  --region "$REGION")
echo "New standby AZ: $NEW_STANDBY (was primary)"

# Verify endpoint remains the same after failover
CURRENT_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text \
  --region "$REGION")
echo "Endpoint (unchanged): $CURRENT_ENDPOINT"
```

---

## Step 8: Validate Data Persistence After Failover

```bash
# Retrieve password from Secrets Manager again for validation
MASTER_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" \
  --query 'SecretString' \
  --output text \
  --region "$REGION" | jq -r '.password')

# Query database to verify all data persisted through failover
echo "Verifying data persistence after failover..."
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@"$BASTION_PUBLIC_IP" \
  "mysql -h $DB_ENDPOINT -u $MASTER_USERNAME -p'$MASTER_PASSWORD' $DB_NAME -e \"
SELECT * FROM messages;
INSERT INTO messages (msg) VALUES ('Post-failover record');
SELECT * FROM messages;
\""
echo "Data persistence verified - all records intact"
```

---

## Step 9: Cleanup

```bash
# Terminate bastion host
echo "Terminating bastion..."
aws ec2 terminate-instances \
  --instance-ids "$BASTION_INSTANCE_ID" \
  --region "$REGION"

# Wait for instance termination
aws ec2 wait instance-terminated \
  --instance-ids "$BASTION_INSTANCE_ID" \
  --region "$REGION"
echo "Bastion terminated"

# Delete RDS instance (skip final snapshot)
echo "Deleting RDS instance..."
aws rds delete-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --skip-final-snapshot \
  --delete-automated-backups \
  --region "$REGION"

# Wait for RDS deletion
echo "Waiting for RDS deletion..."
aws rds wait db-instance-deleted \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$REGION"
echo "RDS instance deleted"

# Delete DB subnet group
aws rds delete-db-subnet-group \
  --db-subnet-group-name "$DB_SUBNET_GROUP" \
  --region "$REGION"
echo "DB subnet group deleted"

# Delete Secrets Manager secret
aws secretsmanager delete-secret \
  --secret-id "$SECRET_NAME" \
  --force-delete-without-recovery \
  --region "$REGION"
echo "Secret deleted"

# Delete security groups
aws ec2 delete-security-group \
  --group-id "$DB_SG_ID" \
  --region "$REGION"
echo "RDS security group deleted"

aws ec2 delete-security-group \
  --group-id "$BASTION_SG_ID" \
  --region "$REGION"
echo "Bastion security group deleted"

# Delete key pair
aws ec2 delete-key-pair \
  --key-name "$KEY_NAME" \
  --region "$REGION"
rm -f "${KEY_NAME}.pem"
echo "Key pair deleted"

# Detach and delete Internet Gateway
aws ec2 detach-internet-gateway \
  --internet-gateway-id "$IGW_ID" \
  --vpc-id "$VPC_ID" \
  --region "$REGION"
echo "Internet Gateway detached"

aws ec2 delete-internet-gateway \
  --internet-gateway-id "$IGW_ID" \
  --region "$REGION"
echo "Internet Gateway deleted"

# Delete subnets
aws ec2 delete-subnet \
  --subnet-id "$PUBLIC_SUBNET_ID" \
  --region "$REGION"
echo "Public subnet deleted"

aws ec2 delete-subnet \
  --subnet-id "$PRIVATE_SUBNET_1_ID" \
  --region "$REGION"
echo "Private subnet 1 deleted"

aws ec2 delete-subnet \
  --subnet-id "$PRIVATE_SUBNET_2_ID" \
  --region "$REGION"
echo "Private subnet 2 deleted"

# Delete route table
aws ec2 delete-route-table \
  --route-table-id "$PUBLIC_RT_ID" \
  --region "$REGION"
echo "Route table deleted"

# Delete VPC
aws ec2 delete-vpc \
  --vpc-id "$VPC_ID" \
  --region "$REGION"
echo "VPC deleted"

echo "Cleanup complete"
```

---

## Summary

This lab demonstrated:
- **Multi-AZ RDS deployment** with automatic synchronous replication
- **Primary and standby** in different availability zones
- **Automatic failover** (30-60 seconds downtime)
- **Data persistence** through failover (no data loss)
- **Endpoint stability** (DNS remains unchanged)
- **Bastion host access** to private RDS instance

### Key Concepts

**Multi-AZ Benefits:**
- High availability (99.95% uptime)
- Automatic failover on failure
- Synchronous replication (zero data loss)
- No manual intervention required

**Failover Triggers:**
- Infrastructure failure (AZ outage)
- Network issues
- Compute/storage failure  
- Maintenance operations
- Manual failover testing

**Best Practices:**
- Use Multi-AZ for production databases
- Place RDS in private subnets
- Use bastion hosts for administrative access
- Enable automated backups
- Test failover regularly
- Monitor with CloudWatch

---
