# Lab 4.A: Provision and connect to an RDS MySQL database in a private subnet

## Overview
Provision an Amazon RDS for MySQL instance in private subnets, secure network access, store credentials in AWS Secrets Manager, and connect from a bastion or via AWS Systems Manager Session Manager port forwarding. Validate connectivity and perform basic SQL operations.

## Objectives
- Create an RDS subnet group using private subnets
- Create a security group that allows MySQL only from a management host (bastion/SSM)
- Provision an RDS MySQL instance (private, not publicly accessible)
- Store DB credentials in Secrets Manager and enable rotation (optional)
- Connect securely via SSH tunnel or SSM port forwarding and run SQL queries
- Snapshot/backup and cleanup resources

## Prerequisites
- AWS CLI v2 configured
- Permissions: RDS, EC2, IAM, Secrets Manager, VPC
- Existing VPC with private subnets (SUBNET_IDS) and at least one public subnet for a bastion host (optional)
- Optional: an EC2 bastion instance with SSH/SSM access, or an SSM-enabled instance for port forwarding

## Architecture (high level)
- Custom VPC
  - Public subnet(s): bastion/management host (optional)
  - Private subnet(s): RDS DB subnets (multi-AZ uses multiple private subnets)
- RDS MySQL instance in DB subnet group (private, no public IP)
- Security Group: allow MySQL (TCP/3306) only from bastion SG or management CIDR
- Secrets Manager: store master credentials

---

## Variables (replace before running)
- REGION=us-east-1
- VPC_ID=your-vpc-id
- PRIVATE_SUBNET_IDS="subnet-aaa subnet-bbb"    # space-separated
- PUBLIC_BASTION_SUBNET=subnet-ccc               # optional
- BASTION_SG_NAME=lab-bastion-sg
- DB_SG_NAME=lab-rds-sg
- DB_SUBNET_GROUP=lab-rds-subnet-group
- DB_INSTANCE_ID=lab-mysql-01
- DB_NAME=labdb
- MASTER_USERNAME=labadmin
- SECRET_NAME=lab/rds/mysql/master
- DB_INSTANCE_CLASS=db.t3.micro
- ALLOCATED_STORAGE=20

---

## Steps (CLI)

### 1. Create DB subnet group (private subnets)
```bash
aws rds create-db-subnet-group \
  --db-subnet-group-name $DB_SUBNET_GROUP \
  --db-subnet-group-description "Subnet group for lab RDS" \
  --subnet-ids $PRIVATE_SUBNET_IDS \
  --region $REGION
```

### 2. Create Security Groups

Create a security group for management (bastion/SSM) and one for RDS allowing only management SG to access 3306.

Create bastion/management SG (if you will SSH from your IP):
```bash
MY_IP=$(curl -s https://ifconfig.co)/32
BASTION_SG_ID=$(aws ec2 create-security-group --group-name $BASTION_SG_NAME --description "Bastion SG" --vpc-id $VPC_ID --query GroupId --output text --region $REGION)
aws ec2 authorize-security-group-ingress --group-id $BASTION_SG_ID --protocol tcp --port 22 --cidr $MY_IP --region $REGION
# allow SSM (no inbound needed) or other management ports as required
```

Create RDS SG and allow MySQL from bastion SG (or management CIDR/SG):
```bash
DB_SG_ID=$(aws ec2 create-security-group --group-name $DB_SG_NAME --description "RDS MySQL SG" --vpc-id $VPC_ID --query GroupId --output text --region $REGION)
# allow MySQL from bastion SG
aws ec2 authorize-security-group-ingress --group-id $DB_SG_ID --protocol tcp --port 3306 --source-group $BASTION_SG_ID --region $REGION
```

If using SSM port forwarding via an SSM-enabled instance, authorize the instance SG similarly.

### 3. Store DB master credentials in Secrets Manager (recommended)
```bash
MASTER_PASSWORD=$(openssl rand -base64 16)
aws secretsmanager create-secret --name $SECRET_NAME \
  --description "RDS MySQL master credentials for lab" \
  --secret-string "{\"username\":\"$MASTER_USERNAME\",\"password\":\"$MASTER_PASSWORD\"}" \
  --region $REGION
SECRET_ARN=$(aws secretsmanager describe-secret --secret-id $SECRET_NAME --query ARN --output text --region $REGION)
```

(Optionally configure automatic rotation with a Lambda; omitted for brevity.)

### 4. Create the RDS MySQL instance (private)
Use the stored password when creating the instance:
```bash
aws rds create-db-instance \
  --db-instance-identifier $DB_INSTANCE_ID \
  --allocated-storage $ALLOCATED_STORAGE \
  --db-instance-class $DB_INSTANCE_CLASS \
  --engine mysql \
  --engine-version 8.0.33 \
  --db-name $DB_NAME \
  --master-username $MASTER_USERNAME \
  --master-user-password "$MASTER_PASSWORD" \
  --db-subnet-group-name $DB_SUBNET_GROUP \
  --vpc-security-group-ids $DB_SG_ID \
  --publicly-accessible false \
  --backup-retention-period 7 \
  --no-multi-az \
  --region $REGION
```

Wait for the instance to be available:
```bash
aws rds wait db-instance-available --db-instance-identifier $DB_INSTANCE_ID --region $REGION
```

Get the endpoint (note: endpoint is private):
```bash
ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier $DB_INSTANCE_ID --query 'DBInstances[0].Endpoint.Address' --output text --region $REGION)
echo "DB endpoint (private): $ENDPOINT"
```

### 5. Connect to the private DB

Option A — SSH tunnel via bastion host:
1. Launch an EC2 bastion in the public subnet with BASTION_SG_ID attached and SSH access.
2. Tunnel:
```bash
ssh -i key.pem -L 3306:$ENDPOINT:3306 ec2-user@BASTION_PUBLIC_IP -N
# then on your machine:
mysql -h 127.0.0.1 -P 3306 -u $MASTER_USERNAME -p
```

Option B — SSM port forwarding (no bastion public IP required):
- Ensure an EC2 management instance is SSM-enabled and in private or public subnet with access to RDS (same SG as allowed).
- Start port forward:
```bash
aws ssm start-session --target i-ssm-managed-instance-id \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"host":["'"$ENDPOINT"'"],"portNumber":["3306"],"localPortNumber":["3306"]}'
# Then connect locally:
mysql -h 127.0.0.1 -P 3306 -u $MASTER_USERNAME -p
```

Use the password stored earlier or retrieve from Secrets Manager:
```bash
aws secretsmanager get-secret-value --secret-id $SECRET_NAME --query SecretString --output text --region $REGION
```

### 6. Basic validation SQL
```sql
CREATE TABLE test_table(id INT PRIMARY KEY AUTO_INCREMENT, msg VARCHAR(255));
INSERT INTO test_table(msg) VALUES('hello lab');
SELECT * FROM test_table;
```

### 7. Backups and snapshots
- Automated backups are enabled (backup-retention-period).
- Create on-demand snapshot:
```bash
aws rds create-db-snapshot --db-instance-identifier $DB_INSTANCE_ID --db-snapshot-identifier ${DB_INSTANCE_ID}-snapshot-$(date -u +%Y%m%d) --region $REGION
```

### 8. Monitoring
- Use CloudWatch metrics (CPU, freeable memory, connections, replica lag if any).
- Enable Enhanced Monitoring and Performance Insights as needed (console or CLI flags during create).

### 9. Cleanup
Be careful: deletion will remove data unless you keep final snapshot.

Delete DB (skip final snapshot example):
```bash
aws rds delete-db-instance --db-instance-identifier $DB_INSTANCE_ID --skip-final-snapshot --delete-automated-backups --region $REGION
aws rds wait db-instance-deleted --db-instance-identifier $DB_INSTANCE_ID --region $REGION
```

Remove subnet group and security groups:
```bash
aws rds delete-db-subnet-group --db-subnet-group-name $DB_SUBNET_GROUP --region $REGION
aws ec2 delete-security-group --group-id $DB_SG_ID --region $REGION
aws ec2 delete-security-group --group-id $BASTION_SG_ID --region $REGION
```

Delete secret:
```bash
aws secretsmanager delete-secret --secret-id $SECRET_NAME --force-delete-without-recovery --region $REGION
```

## Validation Checklist
- [ ] DB subnet group created with private subnets
- [ ] RDS instance launched with publicly-accessible=false
- [ ] Security group restricts port 3306 to management host/SSG only
- [ ] Able to connect via SSH tunnel or SSM port forwarding
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
This lab provisions an RDS MySQL instance in private subnets, secures access via security groups and bastion/SSM, demonstrates credential management with Secrets Manager, and validates connectivity and backups.
