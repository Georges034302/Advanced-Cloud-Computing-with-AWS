# Lab 4.A: Provision and connect to an RDS MySQL database in a private subnet using Bastion host
<img width="1536" height="1024" alt="IMG" src="https://github.com/user-attachments/assets/97ac4aaa-bf9b-4876-90a4-38ad219041f5" />

## Overview
Provision an Amazon RDS for MySQL instance in private subnets, secure network access, store credentials in AWS Secrets Manager, and connect from a bastion host. Validate connectivity and perform basic SQL operations.

## Objectives
- Create an RDS subnet group using private subnets
- Create a security group that allows MySQL only from a bastion host
- Provision an RDS MySQL instance (private, not publicly accessible)
- Store DB credentials in Secrets Manager and enable rotation (optional)
- Connect securely via SSH tunnel and run SQL queries
- Snapshot/backup and cleanup resources

## Prerequisites
- AWS CLI v2 configured
- Permissions: RDS, EC2, IAM, Secrets Manager, VPC
- SSH client installed on your local machine
- MySQL client installed (for database connection testing)

---

## Variables (replace before running)

```bash
REGION=ap-southeast-2
VPC_CIDR=10.0.0.0/16
PUBLIC_SUBNET_CIDR=10.0.1.0/24
PRIVATE_SUBNET_1_CIDR=10.0.10.0/24
PRIVATE_SUBNET_2_CIDR=10.0.11.0/24
VPC_NAME=lab-rds-vpc
BASTION_SG_NAME=lab-bastion-sg
DB_SG_NAME=lab-rds-sg
DB_SUBNET_GROUP=lab-rds-subnet-group
DB_INSTANCE_ID=lab-mysql-01
DB_NAME=labdb
MASTER_USERNAME=labadmin
SECRET_NAME=lab/rds/mysql/master
DB_INSTANCE_CLASS=db.t3.micro
ALLOCATED_STORAGE=20
KEY_NAME=lab-rds-bastion-key
BASTION_INSTANCE_TYPE=t3.micro
```

---

## Steps (CLI)

### 1. Create VPC and Subnets

```bash
# Create VPC for RDS lab
VPC_ID=$(aws ec2 create-vpc \
  --cidr-block "$VPC_CIDR" \
  --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=$VPC_NAME}]" \
  --query 'Vpc.VpcId' \
  --output text \
  --region "$REGION")
echo "VPC created: $VPC_ID"

# Enable DNS hostnames for the VPC (required for RDS)
aws ec2 modify-vpc-attribute \
  --vpc-id "$VPC_ID" \
  --enable-dns-hostnames \
  --region "$REGION"
echo "DNS hostnames enabled"

# Get availability zones
AZ1=$(aws ec2 describe-availability-zones \
  --query 'AvailabilityZones[0].ZoneName' \
  --output text \
  --region "$REGION")
AZ2=$(aws ec2 describe-availability-zones \
  --query 'AvailabilityZones[1].ZoneName' \
  --output text \
  --region "$REGION")
echo "Using AZs: $AZ1, $AZ2"

# Create public subnet for bastion host
PUBLIC_SUBNET_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_ID" \
  --cidr-block "$PUBLIC_SUBNET_CIDR" \
  --availability-zone "$AZ1" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=lab-public-subnet}]" \
  --query 'Subnet.SubnetId' \
  --output text \
  --region "$REGION")
echo "Public subnet created: $PUBLIC_SUBNET_ID"

# Create first private subnet for RDS
PRIVATE_SUBNET_1_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_ID" \
  --cidr-block "$PRIVATE_SUBNET_1_CIDR" \
  --availability-zone "$AZ1" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=lab-private-subnet-1}]" \
  --query 'Subnet.SubnetId' \
  --output text \
  --region "$REGION")
echo "Private subnet 1 created: $PRIVATE_SUBNET_1_ID in $AZ1"

# Create second private subnet for RDS (multi-AZ requirement)
PRIVATE_SUBNET_2_ID=$(aws ec2 create-subnet \
  --vpc-id "$VPC_ID" \
  --cidr-block "$PRIVATE_SUBNET_2_CIDR" \
  --availability-zone "$AZ2" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=lab-private-subnet-2}]" \
  --query 'Subnet.SubnetId' \
  --output text \
  --region "$REGION")
echo "Private subnet 2 created: $PRIVATE_SUBNET_2_ID in $AZ2"

# Create and attach Internet Gateway
IGW_ID=$(aws ec2 create-internet-gateway \
  --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=lab-igw}]" \
  --query 'InternetGateway.InternetGatewayId' \
  --output text \
  --region "$REGION")
echo "Internet Gateway created: $IGW_ID"

# Attach Internet Gateway to VPC to enable internet connectivity
aws ec2 attach-internet-gateway \
  --vpc-id "$VPC_ID" \
  --internet-gateway-id "$IGW_ID" \
  --region "$REGION"
echo "Internet Gateway attached to VPC"

# Create route table for public subnet
PUBLIC_RT_ID=$(aws ec2 create-route-table \
  --vpc-id "$VPC_ID" \
  --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=lab-public-rt}]" \
  --query 'RouteTable.RouteTableId' \
  --output text \
  --region "$REGION")
echo "Public route table created: $PUBLIC_RT_ID"

# Add route to Internet Gateway
aws ec2 create-route \
  --route-table-id "$PUBLIC_RT_ID" \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id "$IGW_ID" \
  --region "$REGION"
echo "Route to Internet Gateway added"

# Associate public subnet with public route table
aws ec2 associate-route-table \
  --subnet-id "$PUBLIC_SUBNET_ID" \
  --route-table-id "$PUBLIC_RT_ID" \
  --region "$REGION"
echo "Public subnet associated with route table"

# Enable auto-assign public IP for public subnet
aws ec2 modify-subnet-attribute \
  --subnet-id "$PUBLIC_SUBNET_ID" \
  --map-public-ip-on-launch \
  --region "$REGION"
echo "Auto-assign public IP enabled for public subnet"
```

### 2. Create DB subnet group (private subnets)

```bash
# Create RDS subnet group to specify which private subnets can host DB instances
aws rds create-db-subnet-group \
  --db-subnet-group-name "$DB_SUBNET_GROUP" \
  --db-subnet-group-description "Subnet group for lab RDS" \
  --subnet-ids "$PRIVATE_SUBNET_1_ID" "$PRIVATE_SUBNET_2_ID" \
  --tags "Key=Name,Value=lab-rds-subnet-group" "Key=Purpose,Value=RDS private subnets" \
  --region "$REGION"
echo "DB Subnet Group created: $DB_SUBNET_GROUP"
```

### 3. Create Security Groups

> Create a security group for the bastion host and one for RDS allowing only bastion SG to access 3306.

```bash
# Get your current public IP for SSH access
MY_IP=$(curl -s checkip.amazonaws.com)/32
echo "Your public IP: $MY_IP"

# Create security group for bastion host
BASTION_SG_ID=$(aws ec2 create-security-group \
  --group-name "$BASTION_SG_NAME" \
  --description "Bastion SG" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' \
  --output text \
  --region "$REGION")
echo "Bastion Security Group ID: $BASTION_SG_ID"

# Tag bastion security group
aws ec2 create-tags \
  --resources "$BASTION_SG_ID" \
  --tags "Key=Name,Value=lab-bastion-sg" "Key=Purpose,Value=SSH access to bastion" \
  --region "$REGION"

# Allow SSH access from your IP to the bastion host
aws ec2 authorize-security-group-ingress \
  --group-id "$BASTION_SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr "$MY_IP" \
  --region "$REGION"
echo "SSH access authorized for $MY_IP"
```

> Create RDS SG and allow MySQL from bastion SG:

```bash
# Create security group for RDS MySQL instance
DB_SG_ID=$(aws ec2 create-security-group \
  --group-name "$DB_SG_NAME" \
  --description "RDS MySQL SG" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' \
  --output text \
  --region "$REGION")
echo "RDS Security Group ID: $DB_SG_ID"

# Tag RDS security group
aws ec2 create-tags \
  --resources "$DB_SG_ID" \
  --tags "Key=Name,Value=lab-rds-sg" "Key=Purpose,Value=MySQL access from bastion" \
  --region "$REGION"

# Allow MySQL (port 3306) access only from bastion security group
aws ec2 authorize-security-group-ingress \
  --group-id "$DB_SG_ID" \
  --protocol tcp \
  --port 3306 \
  --source-group "$BASTION_SG_ID" \
  --region "$REGION"
echo "MySQL access authorized from bastion SG: $BASTION_SG_ID"
```

### 4. Create Bastion Host

```bash
# Create SSH key pair for bastion host
aws ec2 create-key-pair \
  --key-name "$KEY_NAME" \
  --query 'KeyMaterial' \
  --output text \
  --region "$REGION" > "${KEY_NAME}.pem"
chmod 400 "${KEY_NAME}.pem"
echo "SSH key pair created: ${KEY_NAME}.pem"

# Get latest Amazon Linux 2023 AMI
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" "Name=state,Values=available" \
  --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
  --output text \
  --region "$REGION")
echo "Using AMI: $AMI_ID"

# Launch bastion host in public subnet
BASION_INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type "$BASTION_INSTANCE_TYPE" \
  --key-name "$KEY_NAME" \
  --subnet-id "$PUBLIC_SUBNET_ID" \
  --security-group-ids "$BASTION_SG_ID" \
  --associate-public-ip-address \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=lab-bastion-host}]" \
  --query 'Instances[0].InstanceId' \
  --output text \
  --region "$REGION")
echo "Bastion instance launched: $BASTION_INSTANCE_ID"

# Wait for instance to be running
echo "Waiting for bastion instance to be running..."
aws ec2 wait instance-running \
  --instance-ids "$BASTION_INSTANCE_ID" \
  --region "$REGION"
echo "Bastion instance is running"

# Get bastion public IP
BASTION_PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$BASTION_INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$REGION")
echo "Bastion public IP: $BASTION_PUBLIC_IP"
echo "SSH command: ssh -i ${KEY_NAME}.pem ec2-user@$BASTION_PUBLIC_IP"
```

### 5. Store DB master credentials in Secrets Manager (recommended)

```bash
# Generate a secure random password for RDS master user
MASTER_PASSWORD=$(openssl rand -base64 16)
echo "Master password generated (hidden for security)"

# Store credentials securely in AWS Secrets Manager
aws secretsmanager create-secret \
  --name "$SECRET_NAME" \
  --description "RDS MySQL master credentials for lab" \
  --secret-string "{\"username\":\"$MASTER_USERNAME\",\"password\":\"$MASTER_PASSWORD\"}" \
  --region "$REGION"
echo "Secret created: $SECRET_NAME"

# Retrieve the secret ARN for reference
SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id "$SECRET_NAME" \
  --query 'ARN' \
  --output text \
  --region "$REGION")
echo "Secret ARN: $SECRET_ARN"
```

### 6. Create the RDS MySQL instance (private)

```bash
# Create RDS MySQL instance in private subnets (not publicly accessible)
aws rds create-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --allocated-storage "$ALLOCATED_STORAGE" \
  --db-instance-class "$DB_INSTANCE_CLASS" \
  --engine mysql \
  --engine-version 8.4.3 \
  --db-name "$DB_NAME" \
  --master-username "$MASTER_USERNAME" \
  --master-user-password "$MASTER_PASSWORD" \
  --db-subnet-group-name "$DB_SUBNET_GROUP" \
  --vpc-security-group-ids "$DB_SG_ID" \
  --no-publicly-accessible \
  --backup-retention-period 7 \
  --no-multi-az \
  --tags "Key=Name,Value=lab-mysql-db" "Key=Environment,Value=lab" "Key=Purpose,Value=RDS MySQL lab" \
  --region "$REGION"
echo "RDS instance creation initiated: $DB_INSTANCE_ID"

# Wait for the RDS instance to become available (this may take 5-10 minutes)
echo "Waiting for RDS instance to be available..."
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$REGION"
echo "RDS instance is now available"

# Get the private endpoint address for database connections
ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text \
  --region "$REGION")
echo "DB endpoint (private): $ENDPOINT"
```

### 7. Connect to the private DB via bastion host

```bash
# Install MySQL client on bastion host
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@"$BASTION_PUBLIC_IP" "sudo dnf install -y mariadb105"

# Test connection to RDS from bastion
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@"$BASTION_PUBLIC_IP" "mysql -h $ENDPOINT -u $MASTER_USERNAME -p'$MASTER_PASSWORD' -e 'SHOW DATABASES;'"
```

### 8. Basic validation SQL

```bash
# Retrieve the master password from Secrets Manager
MASTER_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" \
  --query 'SecretString' \
  --output text \
  --region "$REGION" | jq -r '.password')
echo "Password retrieved from Secrets Manager"

# Run validation SQL from bastion host (create table and insert data)
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@"$BASTION_PUBLIC_IP" \
  "mysql -h $ENDPOINT -u $MASTER_USERNAME -p'$MASTER_PASSWORD' $DB_NAME -e \"
CREATE TABLE test_table(id INT PRIMARY KEY AUTO_INCREMENT, msg VARCHAR(255));
INSERT INTO test_table(msg) VALUES('hello lab');
\""

# Query the test table to verify data
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@"$BASTION_PUBLIC_IP" \
  "mysql -h $ENDPOINT -u $MASTER_USERNAME -p'$MASTER_PASSWORD' $DB_NAME -e 'SELECT * FROM test_table;'"
```

### 9. Backups and snapshots (Optional)

> Automated backups are enabled (backup-retention-period). Create on-demand snapshot:

```bash
# Create a manual snapshot of the RDS instance with timestamp
SNAPSHOT_ID="${DB_INSTANCE_ID}-snapshot-$(date -u +%Y%m%d)"

aws rds create-db-snapshot \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --db-snapshot-identifier "$SNAPSHOT_ID" \
  --tags "Key=Name,Value=$SNAPSHOT_ID" "Key=Type,Value=manual" "Key=Purpose,Value=lab backup" \
  --region "$REGION"
echo "Snapshot created: $SNAPSHOT_ID"
```

### 10. Cleanup

```bash
# Delete RDS instance (skip final snapshot - use with caution)
echo "Deleting RDS instance..."
aws rds delete-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --skip-final-snapshot \
  --delete-automated-backups \
  --region "$REGION"

# Wait for RDS instance to be fully deleted
echo "Waiting for RDS instance deletion..."
aws rds wait db-instance-deleted \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$REGION"
echo "RDS instance deleted"

# Delete RDS subnet group
aws rds delete-db-subnet-group \
  --db-subnet-group-name "$DB_SUBNET_GROUP" \
  --region "$REGION"
echo "DB subnet group deleted: $DB_SUBNET_GROUP"

# Terminate bastion host
echo "Terminating bastion instance..."
aws ec2 terminate-instances \
  --instance-ids "$BASTION_INSTANCE_ID" \
  --region "$REGION"

aws ec2 wait instance-terminated \
  --instance-ids "$BASTION_INSTANCE_ID" \
  --region "$REGION"
echo "Bastion instance terminated: $BASTION_INSTANCE_ID"

# Delete security groups
aws ec2 delete-security-group \
  --group-id "$DB_SG_ID" \
  --region "$REGION"
echo "RDS security group deleted: $DB_SG_ID"

aws ec2 delete-security-group \
  --group-id "$BASTION_SG_ID" \
  --region "$REGION"
echo "Bastion security group deleted: $BASTION_SG_ID"

# Delete key pair
aws ec2 delete-key-pair \
  --key-name "$KEY_NAME" \
  --region "$REGION"
rm -f "${KEY_NAME}.pem"
echo "Key pair deleted: $KEY_NAME"

# Detach and delete Internet Gateway
aws ec2 detach-internet-gateway \
  --internet-gateway-id "$IGW_ID" \
  --vpc-id "$VPC_ID" \
  --region "$REGION"
echo "Internet Gateway detached"

aws ec2 delete-internet-gateway \
  --internet-gateway-id "$IGW_ID" \
  --region "$REGION"
echo "Internet Gateway deleted: $IGW_ID"

# Delete subnets
aws ec2 delete-subnet \
  --subnet-id "$PUBLIC_SUBNET_ID" \
  --region "$REGION"
echo "Public subnet deleted: $PUBLIC_SUBNET_ID"

aws ec2 delete-subnet \
  --subnet-id "$PRIVATE_SUBNET_1_ID" \
  --region "$REGION"
echo "Private subnet 1 deleted: $PRIVATE_SUBNET_1_ID"

aws ec2 delete-subnet \
  --subnet-id "$PRIVATE_SUBNET_2_ID" \
  --region "$REGION"
echo "Private subnet 2 deleted: $PRIVATE_SUBNET_2_ID"

# Delete route table
aws ec2 delete-route-table \
  --route-table-id "$PUBLIC_RT_ID" \
  --region "$REGION"
echo "Route table deleted: $PUBLIC_RT_ID"

# Delete VPC
aws ec2 delete-vpc \
  --vpc-id "$VPC_ID" \
  --region "$REGION"
echo "VPC deleted: $VPC_ID"

# Delete secret from Secrets Manager (force delete without recovery)
aws secretsmanager delete-secret \
  --secret-id "$SECRET_NAME" \
  --force-delete-without-recovery \
  --region "$REGION"
echo "Secret deleted: $SECRET_NAME"

echo "All resources cleaned up successfully"
```

## Validation Checklist
- [ ] DB subnet group created with private subnets
- [ ] RDS instance launched with publicly-accessible=false
- [ ] Security group restricts port 3306 to management host/SSG only
- [ ] Able to connect via SSH tunnel 
- [ ] Can run basic SQL queries and create/verify a table
- [ ] Snapshot created (manual or automated)
- [ ] Resources cleaned up after lab

## Notes & Best Practices
- Never expose DB to the public Internet; use private subnets and strict SG rules.
- Use Secrets Manager + IAM for credentials and automatic rotation.
- Prefer IAM database authentication where supported.
- Enable Multi-AZ for production availability and use read replicas for scaling reads.
- Test backups and restores regularly.

## Summary
This lab provisions an RDS MySQL instance in private subnets, secures access via security groups and bastion host, demonstrates credential management with Secrets Manager, and validates connectivity and backups.
