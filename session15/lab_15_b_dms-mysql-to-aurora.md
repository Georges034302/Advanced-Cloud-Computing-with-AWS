# Lab 15.B: AWS Database Migration Service (DMS) – Migrate MySQL to Amazon Aurora

## Overview
This lab walks you through migrating a MySQL database to **Amazon Aurora MySQL-Compatible Edition** using **AWS Database Migration Service (DMS)**. You'll create a source RDS MySQL database with sample data, set up an Aurora MySQL cluster as the target, deploy a DMS replication instance, configure source and target endpoints, create and execute a migration task with full load plus CDC (Change Data Capture), validate the migration, test real-time replication, and perform comprehensive cleanup.

AWS DMS enables seamless database migrations with minimal downtime, supporting homogeneous (MySQL to Aurora MySQL) and heterogeneous migrations, continuous data replication, and automatic schema conversion.

---

## Objectives
- Set up environment variables and VPC security configuration
- Create source RDS MySQL database with sample schema and data
- Deploy Amazon Aurora MySQL-Compatible cluster as migration target
- Configure DMS replication instance for data transfer
- Set up source and target database endpoints in DMS
- Create and execute DMS migration task with full load and CDC
- Monitor migration progress and validate data integrity
- Test Change Data Capture with real-time replication
- Review CloudWatch metrics and DMS task logs
- Perform comprehensive resource cleanup

---

## Prerequisites
- AWS CLI configured with appropriate credentials
- IAM permissions for RDS, DMS, EC2, VPC, IAM, and CloudWatch
- MySQL client installed locally (`mysql` command-line tool)
- Region: **ap-southeast-2** (Sydney)
- `jq` installed for JSON parsing (optional but recommended)
- Basic understanding of relational databases and replication concepts

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│             AWS Database Migration Service (DMS)                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Source Database                                                    │
│  ┌─────────────────────────────┐                                   │
│  │   RDS MySQL 8.0             │                                   │
│  │   - DB: employees           │                                   │
│  │   - Table: staff            │                                   │
│  │   - Binary Logging: ON      │                                   │
│  │   - Multi-AZ: Optional      │                                   │
│  └─────────────────────────────┘                                   │
│              │                                                      │
│              │ Full Load + CDC (Change Data Capture)               │
│              ▼                                                      │
│  ┌─────────────────────────────────────────┐                       │
│  │     DMS Replication Instance            │                       │
│  │  - Instance: dms.t3.micro               │                       │
│  │  - Storage: 20 GB                       │                       │
│  │  - Networking: Private Subnet           │                       │
│  │  - Security Group: Port 3306            │                       │
│  │                                         │                       │
│  │  Migration Process:                     │                       │
│  │  1. Full Load (Initial Copy)            │                       │
│  │  2. CDC (Ongoing Replication)           │                       │
│  │  3. Data Validation                     │                       │
│  └─────────────────────────────────────────┘                       │
│              │                                                      │
│              ▼                                                      │
│  Target Database                                                    │
│  ┌─────────────────────────────┐                                   │
│  │   Aurora MySQL Cluster      │                                   │
│  │   - Writer Instance         │                                   │
│  │   - Reader Instance (opt)   │                                   │
│  │   - DB: employees           │                                   │
│  │   - Table: staff (replicated)│                                  │
│  │   - Automatic Backups       │                                   │
│  └─────────────────────────────┘                                   │
│              │                                                      │
│              ▼                                                      │
│  ┌─────────────────────────────┐                                   │
│  │   CloudWatch Monitoring     │                                   │
│  │  - Full Load Progress       │                                   │
│  │  - CDC Latency              │                                   │
│  │  - Task Errors              │                                   │
│  │  - Network Throughput       │                                   │
│  └─────────────────────────────┘                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

Migration Flow:
1. DMS reads source MySQL tables (full load)
2. Data transferred to Aurora target with transformation
3. CDC captures ongoing changes from MySQL binary logs
4. Changes applied to Aurora in near real-time
5. Validation ensures data consistency
```

---

## Cost Estimate
- **RDS MySQL (db.t3.micro)**: ~$0.017/hour (~$12/month)
- **Aurora MySQL (db.t3.medium)**: ~$0.082/hour (~$59/month)
- **DMS Replication Instance (dms.t3.micro)**: ~$0.036/hour (~$26/month)
- **Storage**: ~$0.10/GB-month (RDS) + $0.10/GB-month (Aurora)
- **Data Transfer**: Free within same AZ
- **Estimated Lab Cost**: ~$0.50 for 2-3 hours

---

# Step 1 – Set Environment Variables

```bash
# Set primary region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "✅ Region set to: $REGION"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "✅ AWS Account ID: $ACCOUNT_ID"

# Define database credentials (use strong passwords in production)
DB_USER="admin"
DB_PASS="MySecurePassword12345!"  # Change this to a secure password

# Define resource names
MYSQL_SRC="mysql-source-db"
AURORA_CLUSTER="aurora-target-cluster"
AURORA_INSTANCE="aurora-writer-instance"
DMS_REPLICA="dms-replication-instance"
DMS_SUBNET_GROUP="dms-subnet-group"

# Define database name and table
DB_NAME="employees"
TABLE_NAME="staff"

# Echo all variables for verification
echo ""
echo "=== Environment Configuration ==="
echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
echo "DB Username: $DB_USER"
echo "MySQL Source: $MYSQL_SRC"
echo "Aurora Cluster: $AURORA_CLUSTER"
echo "Aurora Instance: $AURORA_INSTANCE"
echo "DMS Instance: $DMS_REPLICA"
echo "Database Name: $DB_NAME"
echo "Table Name: $TABLE_NAME"
echo "================================="
echo ""
```

**Expected Output:**
```
✅ Region set to: ap-southeast-2
✅ AWS Account ID: 123456789012
=== Environment Configuration ===
Region: ap-southeast-2
Account ID: 123456789012
DB Username: admin
MySQL Source: mysql-source-db
Aurora Cluster: aurora-target-cluster
Aurora Instance: aurora-writer-instance
DMS Instance: dms-replication-instance
Database Name: employees
Table Name: staff
=================================
```

---

# Step 2 – Get Default VPC and Subnet Information

```bash
# Get default VPC ID
DEFAULT_VPC=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" \
  --output text)
echo "✅ Default VPC: $DEFAULT_VPC"

# Get default security group
DEFAULT_SG=$(aws ec2 describe-security-groups \
  --filters "Name=vpc-id,Values=$DEFAULT_VPC" "Name=group-name,Values=default" \
  --query "SecurityGroups[0].GroupId" \
  --output text)
echo "✅ Default Security Group: $DEFAULT_SG"

# Get all subnets in default VPC
SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$DEFAULT_VPC" \
  --query "Subnets[*].SubnetId" \
  --output text)
echo "✅ Available Subnets: $SUBNETS"

# Store subnet IDs as array for DMS subnet group
SUBNET_1=$(echo $SUBNETS | awk '{print $1}')
SUBNET_2=$(echo $SUBNETS | awk '{print $2}')

echo ""
echo "=== VPC Configuration ==="
echo "VPC ID: $DEFAULT_VPC"
echo "Security Group: $DEFAULT_SG"
echo "Subnet 1: $SUBNET_1"
echo "Subnet 2: $SUBNET_2"
echo "========================="
echo ""
```

**Expected Output:**
```
✅ Default VPC: vpc-0123456789abcdef0
✅ Default Security Group: sg-0123456789abcdef0
✅ Available Subnets: subnet-abc123 subnet-def456 subnet-ghi789

=== VPC Configuration ===
VPC ID: vpc-0123456789abcdef0
Security Group: sg-0123456789abcdef0
Subnet 1: subnet-abc123
Subnet 2: subnet-def456
=========================
```

---

# Step 3 – Ensure Security Group Allows MySQL Traffic

```bash
# Add inbound rule for MySQL (port 3306) if not exists
echo "Configuring security group for MySQL access..."

aws ec2 authorize-security-group-ingress \
  --group-id "$DEFAULT_SG" \
  --protocol tcp \
  --port 3306 \
  --cidr 0.0.0.0/0 \
  --region "$REGION" 2>/dev/null && echo "✅ MySQL port 3306 opened" || echo "ℹ️  Port 3306 rule already exists"

# Verify security group rules
echo ""
echo "=== Security Group Rules ==="
aws ec2 describe-security-groups \
  --group-ids "$DEFAULT_SG" \
  --query "SecurityGroups[0].IpPermissions[?ToPort==\`3306\`]" \
  --output table
echo "============================"
echo ""
```

**Expected Output:**
```
Configuring security group for MySQL access...
✅ MySQL port 3306 opened

=== Security Group Rules ===
-----------------------------------------------------------------
|                  DescribeSecurityGroups                        |
+----------------------------------------------------------------+
|  IpProtocol: tcp                                               |
|  FromPort: 3306                                                |
|  ToPort: 3306                                                  |
|  IpRanges: 0.0.0.0/0                                          |
+----------------------------------------------------------------+
============================
```

**Note:** In production, restrict CIDR to specific IP ranges for security.

---

# Step 4 – Create Source RDS MySQL Database

```bash
# Create RDS MySQL source database
echo "Creating source RDS MySQL database..."

aws rds create-db-instance \
  --db-instance-identifier "$MYSQL_SRC" \
  --engine mysql \
  --engine-version "8.0.35" \
  --db-instance-class db.t3.micro \
  --allocated-storage 20 \
  --storage-type gp2 \
  --publicly-accessible \
  --master-username "$DB_USER" \
  --master-user-password "$DB_PASS" \
  --backup-retention-period 1 \
  --vpc-security-group-ids "$DEFAULT_SG" \
  --db-name "$DB_NAME" \
  --region "$REGION" \
  --tags "Key=Purpose,Value=DMS-Source" "Key=Lab,Value=15B" \
  --output json > /dev/null

echo "✅ MySQL database creation initiated: $MYSQL_SRC"

# Wait for database to become available
echo ""
echo "⏳ Waiting for MySQL database to become available..."
echo "   This may take 5-10 minutes..."
echo ""

aws rds wait db-instance-available \
  --db-instance-identifier "$MYSQL_SRC" \
  --region "$REGION"

echo "✅ MySQL database is now available"

# Get MySQL endpoint
SRC_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$MYSQL_SRC" \
  --region "$REGION" \
  --query "DBInstances[0].Endpoint.Address" \
  --output text)

echo ""
echo "=== MySQL Source Database ==="
echo "Instance ID: $MYSQL_SRC"
echo "Endpoint: $SRC_ENDPOINT"
echo "Status: Available"
echo "============================="
echo ""
```

**Expected Output:**
```
Creating source RDS MySQL database...
✅ MySQL database creation initiated: mysql-source-db

⏳ Waiting for MySQL database to become available...
   This may take 5-10 minutes...

✅ MySQL database is now available

=== MySQL Source Database ===
Instance ID: mysql-source-db
Endpoint: mysql-source-db.c9a8b7d6e5f4.ap-southeast-2.rds.amazonaws.com
Status: Available
=============================
```

---

# Step 5 – Create Sample Schema and Data in Source MySQL

```bash
# Connect to MySQL and create sample data
echo "Creating sample database schema and data..."

# Create database, table, and insert sample records
mysql -h "$SRC_ENDPOINT" \
      -u "$DB_USER" \
      -p"$DB_PASS" \
      -e "
-- Verify database exists
USE $DB_NAME;

-- Create employees table
CREATE TABLE IF NOT EXISTS $TABLE_NAME (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  role VARCHAR(100) NOT NULL,
  salary INT NOT NULL,
  hire_date DATE,
  department VARCHAR(50),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Insert sample employee records
INSERT INTO $TABLE_NAME (name, role, salary, hire_date, department) VALUES
  ('Alice Johnson', 'Software Engineer', 95000, '2020-01-15', 'Engineering'),
  ('Bob Smith', 'Engineering Manager', 125000, '2019-03-20', 'Engineering'),
  ('Clara Davis', 'UX Designer', 88000, '2021-06-10', 'Design'),
  ('David Chen', 'DevOps Engineer', 98000, '2020-08-05', 'Engineering'),
  ('Emma Wilson', 'Product Manager', 115000, '2019-11-12', 'Product'),
  ('Frank Martinez', 'Data Analyst', 82000, '2022-02-18', 'Analytics'),
  ('Grace Lee', 'Senior Architect', 145000, '2018-05-30', 'Engineering'),
  ('Henry Taylor', 'QA Engineer', 78000, '2021-09-22', 'Quality'),
  ('Iris Brown', 'Marketing Manager', 105000, '2020-04-14', 'Marketing'),
  ('Jack Anderson', 'Sales Director', 135000, '2019-07-08', 'Sales');

-- Display inserted data
SELECT COUNT(*) AS 'Total Records' FROM $TABLE_NAME;
"

echo "✅ Sample schema and data created"

# Verify data in source
echo ""
echo "=== Source Database Content ==="
mysql -h "$SRC_ENDPOINT" \
      -u "$DB_USER" \
      -p"$DB_PASS" \
      -D "$DB_NAME" \
      -e "SELECT id, name, role, salary FROM $TABLE_NAME LIMIT 5;"

echo ""
echo "Total records in source:"
RECORD_COUNT=$(mysql -h "$SRC_ENDPOINT" \
                     -u "$DB_USER" \
                     -p"$DB_PASS" \
                     -D "$DB_NAME" \
                     -se "SELECT COUNT(*) FROM $TABLE_NAME;")
echo "  Records: $RECORD_COUNT"
echo "==============================="
echo ""
```

**Expected Output:**
```
Creating sample database schema and data...
✅ Sample schema and data created

=== Source Database Content ===
+----+------------------+--------------------+--------+
| id | name             | role               | salary |
+----+------------------+--------------------+--------+
|  1 | Alice Johnson    | Software Engineer  |  95000 |
|  2 | Bob Smith        | Engineering Manager| 125000 |
|  3 | Clara Davis      | UX Designer        |  88000 |
|  4 | David Chen       | DevOps Engineer    |  98000 |
|  5 | Emma Wilson      | Product Manager    | 115000 |
+----+------------------+--------------------+--------+

Total records in source:
  Records: 10
===============================
```

---

# Step 6 – Create DMS Subnet Group

```bash
# Create DMS subnet group for replication instance
echo "Creating DMS subnet group..."

aws dms create-replication-subnet-group \
  --replication-subnet-group-identifier "$DMS_SUBNET_GROUP" \
  --replication-subnet-group-description "Subnet group for DMS replication instance" \
  --subnet-ids $SUBNET_1 $SUBNET_2 \
  --tags "Key=Purpose,Value=DMS" "Key=Lab,Value=15B" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ DMS subnet group created: $DMS_SUBNET_GROUP"

# Verify subnet group
echo ""
echo "=== DMS Subnet Group ==="
aws dms describe-replication-subnet-groups \
  --filters "Name=replication-subnet-group-id,Values=$DMS_SUBNET_GROUP" \
  --query "ReplicationSubnetGroups[0].[ReplicationSubnetGroupIdentifier,VpcId]" \
  --output table
echo "========================"
echo ""
```

**Expected Output:**
```
Creating DMS subnet group...
✅ DMS subnet group created: dms-subnet-group

=== DMS Subnet Group ===
-----------------------------------------------------------------
|           DescribeReplicationSubnetGroups                      |
+--------------------------------+------------------------------+
|  dms-subnet-group              |  vpc-0123456789abcdef0      |
+--------------------------------+------------------------------+
========================
```

---

# Step 7 – Create DMS Replication Instance

```bash
# Create DMS replication instance for migration
echo "Creating DMS replication instance..."

aws dms create-replication-instance \
  --replication-instance-identifier "$DMS_REPLICA" \
  --replication-instance-class dms.t3.micro \
  --allocated-storage 20 \
  --vpc-security-group-ids "$DEFAULT_SG" \
  --replication-subnet-group-identifier "$DMS_SUBNET_GROUP" \
  --publicly-accessible \
  --multi-az false \
  --engine-version "3.5.2" \
  --tags "Key=Purpose,Value=Database-Migration" "Key=Lab,Value=15B" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ DMS replication instance creation initiated: $DMS_REPLICA"

# Wait for replication instance to become available
echo ""
echo "⏳ Waiting for DMS replication instance to become available..."
echo "   This may take 5-10 minutes..."
echo ""

# Poll for availability
while true; do
  STATUS=$(aws dms describe-replication-instances \
    --filters "Name=replication-instance-id,Values=$DMS_REPLICA" \
    --query "ReplicationInstances[0].ReplicationInstanceStatus" \
    --output text \
    --region "$REGION")
  
  echo "[$(date '+%H:%M:%S')] DMS Instance Status: $STATUS"
  
  if [[ "$STATUS" == "available" ]]; then
    echo ""
    echo "✅ DMS replication instance is now available"
    break
  elif [[ "$STATUS" == "failed" ]]; then
    echo ""
    echo "❌ DMS replication instance creation failed"
    exit 1
  fi
  
  sleep 30
done

# Get replication instance ARN
DMS_REPLICA_ARN=$(aws dms describe-replication-instances \
  --filters "Name=replication-instance-id,Values=$DMS_REPLICA" \
  --query "ReplicationInstances[0].ReplicationInstanceArn" \
  --output text \
  --region "$REGION")

echo ""
echo "=== DMS Replication Instance ==="
echo "Instance ID: $DMS_REPLICA"
echo "Instance ARN: $DMS_REPLICA_ARN"
echo "Status: Available"
echo "================================"
echo ""
```

**Expected Output:**
```
Creating DMS replication instance...
✅ DMS replication instance creation initiated: dms-replication-instance

⏳ Waiting for DMS replication instance to become available...
   This may take 5-10 minutes...

[10:20:30] DMS Instance Status: creating
[10:21:00] DMS Instance Status: creating
[10:21:30] DMS Instance Status: available

✅ DMS replication instance is now available

=== DMS Replication Instance ===
Instance ID: dms-replication-instance
Instance ARN: arn:aws:dms:ap-southeast-2:123456789012:rep:ABC123DEF456
Status: Available
================================
```

---

# Step 8 – Create Aurora MySQL Cluster (Target)

```bash
# Create Aurora MySQL cluster as migration target
echo "Creating Aurora MySQL cluster..."

aws rds create-db-cluster \
  --db-cluster-identifier "$AURORA_CLUSTER" \
  --engine aurora-mysql \
  --engine-version "8.0.mysql_aurora.3.05.2" \
  --master-username "$DB_USER" \
  --master-user-password "$DB_PASS" \
  --database-name "$DB_NAME" \
  --vpc-security-group-ids "$DEFAULT_SG" \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00" \
  --preferred-maintenance-window "mon:04:00-mon:05:00" \
  --tags "Key=Purpose,Value=DMS-Target" "Key=Lab,Value=15B" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Aurora cluster creation initiated: $AURORA_CLUSTER"

# Wait for cluster to become available
echo ""
echo "⏳ Waiting for Aurora cluster to become available..."

aws rds wait db-cluster-available \
  --db-cluster-identifier "$AURORA_CLUSTER" \
  --region "$REGION"

echo "✅ Aurora cluster is now available"

# Create Aurora writer instance
echo ""
echo "Creating Aurora writer instance..."

aws rds create-db-instance \
  --db-instance-identifier "$AURORA_INSTANCE" \
  --db-cluster-identifier "$AURORA_CLUSTER" \
  --engine aurora-mysql \
  --db-instance-class db.t3.medium \
  --publicly-accessible true \
  --tags "Key=Purpose,Value=DMS-Target-Writer" "Key=Lab,Value=15B" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Aurora writer instance creation initiated: $AURORA_INSTANCE"

# Wait for writer instance to become available
echo ""
echo "⏳ Waiting for Aurora writer instance to become available..."
echo "   This may take 5-10 minutes..."
echo ""

aws rds wait db-instance-available \
  --db-instance-identifier "$AURORA_INSTANCE" \
  --region "$REGION"

echo "✅ Aurora writer instance is now available"

# Get Aurora cluster endpoint
AURORA_ENDPOINT=$(aws rds describe-db-clusters \
  --db-cluster-identifier "$AURORA_CLUSTER" \
  --query "DBClusters[0].Endpoint" \
  --output text \
  --region "$REGION")

echo ""
echo "=== Aurora MySQL Cluster ==="
echo "Cluster ID: $AURORA_CLUSTER"
echo "Writer Instance: $AURORA_INSTANCE"
echo "Cluster Endpoint: $AURORA_ENDPOINT"
echo "Status: Available"
echo "============================"
echo ""
```

**Expected Output:**
```
Creating Aurora MySQL cluster...
✅ Aurora cluster creation initiated: aurora-target-cluster

⏳ Waiting for Aurora cluster to become available...
✅ Aurora cluster is now available

Creating Aurora writer instance...
✅ Aurora writer instance creation initiated: aurora-writer-instance

⏳ Waiting for Aurora writer instance to become available...
   This may take 5-10 minutes...

✅ Aurora writer instance is now available

=== Aurora MySQL Cluster ===
Cluster ID: aurora-target-cluster
Writer Instance: aurora-writer-instance
Cluster Endpoint: aurora-target-cluster.cluster-c9a8b7d6e5f4.ap-southeast-2.rds.amazonaws.com
Status: Available
============================
```

---

# Step 9 – Create DMS Source Endpoint (MySQL)

```bash
# Create DMS source endpoint for MySQL database
echo "Creating DMS source endpoint for MySQL..."

aws dms create-endpoint \
  --endpoint-identifier "mysql-source-endpoint" \
  --endpoint-type source \
  --engine-name mysql \
  --username "$DB_USER" \
  --password "$DB_PASS" \
  --server-name "$SRC_ENDPOINT" \
  --port 3306 \
  --database-name "$DB_NAME" \
  --tags "Key=Purpose,Value=DMS-Source-Endpoint" "Key=Lab,Value=15B" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ DMS source endpoint created: mysql-source-endpoint"

# Get source endpoint ARN
SRC_EP_ARN=$(aws dms describe-endpoints \
  --filters "Name=endpoint-id,Values=mysql-source-endpoint" \
  --query "Endpoints[0].EndpointArn" \
  --output text \
  --region "$REGION")

# Test source endpoint connection
echo ""
echo "Testing source endpoint connection..."

aws dms test-connection \
  --replication-instance-arn "$DMS_REPLICA_ARN" \
  --endpoint-arn "$SRC_EP_ARN" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Source endpoint connection test initiated"

# Wait for connection test to complete
sleep 10

TEST_STATUS=$(aws dms describe-connections \
  --filters "Name=endpoint-arn,Values=$SRC_EP_ARN" \
  --query "Connections[0].Status" \
  --output text \
  --region "$REGION")

echo "Connection Test Status: $TEST_STATUS"

echo ""
echo "=== DMS Source Endpoint ==="
echo "Endpoint ID: mysql-source-endpoint"
echo "Endpoint ARN: $SRC_EP_ARN"
echo "Server: $SRC_ENDPOINT"
echo "Database: $DB_NAME"
echo "==========================="
echo ""
```

**Expected Output:**
```
Creating DMS source endpoint for MySQL...
✅ DMS source endpoint created: mysql-source-endpoint

Testing source endpoint connection...
✅ Source endpoint connection test initiated
Connection Test Status: successful

=== DMS Source Endpoint ===
Endpoint ID: mysql-source-endpoint
Endpoint ARN: arn:aws:dms:ap-southeast-2:123456789012:endpoint:ABC123
Server: mysql-source-db.c9a8b7d6e5f4.ap-southeast-2.rds.amazonaws.com
Database: employees
===========================
```

---

# Step 10 – Create DMS Target Endpoint (Aurora MySQL)

```bash
# Create DMS target endpoint for Aurora MySQL
echo "Creating DMS target endpoint for Aurora..."

aws dms create-endpoint \
  --endpoint-identifier "aurora-target-endpoint" \
  --endpoint-type target \
  --engine-name aurora \
  --username "$DB_USER" \
  --password "$DB_PASS" \
  --server-name "$AURORA_ENDPOINT" \
  --port 3306 \
  --database-name "$DB_NAME" \
  --tags "Key=Purpose,Value=DMS-Target-Endpoint" "Key=Lab,Value=15B" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ DMS target endpoint created: aurora-target-endpoint"

# Get target endpoint ARN
DST_EP_ARN=$(aws dms describe-endpoints \
  --filters "Name=endpoint-id,Values=aurora-target-endpoint" \
  --query "Endpoints[0].EndpointArn" \
  --output text \
  --region "$REGION")

# Test target endpoint connection
echo ""
echo "Testing target endpoint connection..."

aws dms test-connection \
  --replication-instance-arn "$DMS_REPLICA_ARN" \
  --endpoint-arn "$DST_EP_ARN" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Target endpoint connection test initiated"

# Wait for connection test to complete
sleep 10

TEST_STATUS=$(aws dms describe-connections \
  --filters "Name=endpoint-arn,Values=$DST_EP_ARN" \
  --query "Connections[0].Status" \
  --output text \
  --region "$REGION")

echo "Connection Test Status: $TEST_STATUS"

echo ""
echo "=== DMS Target Endpoint ==="
echo "Endpoint ID: aurora-target-endpoint"
echo "Endpoint ARN: $DST_EP_ARN"
echo "Server: $AURORA_ENDPOINT"
echo "Database: $DB_NAME"
echo "==========================="
echo ""
```

**Expected Output:**
```
Creating DMS target endpoint for Aurora...
✅ DMS target endpoint created: aurora-target-endpoint

Testing target endpoint connection...
✅ Target endpoint connection test initiated
Connection Test Status: successful

=== DMS Target Endpoint ===
Endpoint ID: aurora-target-endpoint
Endpoint ARN: arn:aws:dms:ap-southeast-2:123456789012:endpoint:DEF456
Server: aurora-target-cluster.cluster-c9a8b7d6e5f4.ap-southeast-2.rds.amazonaws.com
Database: employees
===========================
```

---

# Step 11 – Create DMS Migration Task

```bash
# Create DMS replication task for full load + CDC
echo "Creating DMS migration task..."

# Define table mappings for migration
TABLE_MAPPINGS='{
  "rules": [
    {
      "rule-type": "selection",
      "rule-id": "1",
      "rule-name": "include-all-tables",
      "object-locator": {
        "schema-name": "'"$DB_NAME"'",
        "table-name": "%"
      },
      "rule-action": "include"
    }
  ]
}'

# Create migration task
TASK_ARN=$(aws dms create-replication-task \
  --replication-task-identifier "mysql-to-aurora-migration" \
  --source-endpoint-arn "$SRC_EP_ARN" \
  --target-endpoint-arn "$DST_EP_ARN" \
  --replication-instance-arn "$DMS_REPLICA_ARN" \
  --migration-type full-load-and-cdc \
  --table-mappings "$TABLE_MAPPINGS" \
  --replication-task-settings '{
    "TargetMetadata": {
      "SupportLobs": true,
      "FullLobMode": false,
      "LobChunkSize": 64,
      "LimitedSizeLobMode": true,
      "LobMaxSize": 32
    },
    "FullLoadSettings": {
      "TargetTablePrepMode": "DROP_AND_CREATE",
      "CreatePkAfterFullLoad": false,
      "StopTaskCachedChangesApplied": false,
      "StopTaskCachedChangesNotApplied": false,
      "MaxFullLoadSubTasks": 8,
      "TransactionConsistencyTimeout": 600
    },
    "Logging": {
      "EnableLogging": true,
      "LogComponents": [
        {
          "Id": "TRANSFORMATION",
          "Severity": "LOGGER_SEVERITY_DEFAULT"
        },
        {
          "Id": "SOURCE_UNLOAD",
          "Severity": "LOGGER_SEVERITY_DEFAULT"
        },
        {
          "Id": "TARGET_LOAD",
          "Severity": "LOGGER_SEVERITY_DEFAULT"
        }
      ]
    },
    "ChangeDataCaptureSettings": {
      "EnableDDL": true
    }
  }' \
  --tags "Key=Purpose,Value=Database-Migration" "Key=Lab,Value=15B" \
  --query "ReplicationTask.ReplicationTaskArn" \
  --output text \
  --region "$REGION")

echo "✅ DMS migration task created"

echo ""
echo "=== DMS Migration Task ==="
echo "Task ID: mysql-to-aurora-migration"
echo "Task ARN: $TASK_ARN"
echo "Migration Type: Full Load + CDC"
echo "Source: MySQL ($MYSQL_SRC)"
echo "Target: Aurora ($AURORA_CLUSTER)"
echo "=========================="
echo ""
```

**Expected Output:**
```
Creating DMS migration task...
✅ DMS migration task created

=== DMS Migration Task ===
Task ID: mysql-to-aurora-migration
Task ARN: arn:aws:dms:ap-southeast-2:123456789012:task:GHI789
Migration Type: Full Load + CDC
Source: MySQL (mysql-source-db)
Target: Aurora (aurora-target-cluster)
==========================
```

---

# Step 12 – Start DMS Migration Task

```bash
# Start the migration task
echo "Starting DMS migration task..."

aws dms start-replication-task \
  --replication-task-arn "$TASK_ARN" \
  --start-replication-task-type start-replication \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Migration task started"

# Monitor task progress
echo ""
echo "⏳ Monitoring migration progress..."
echo "   Phase 1: Full Load (copying existing data)"
echo "   Phase 2: CDC (capturing ongoing changes)"
echo ""

# Poll task status
while true; do
  TASK_INFO=$(aws dms describe-replication-tasks \
    --filters "Name=replication-task-arn,Values=$TASK_ARN" \
    --query "ReplicationTasks[0]" \
    --output json \
    --region "$REGION")
  
  STATUS=$(echo "$TASK_INFO" | jq -r '.Status')
  PERCENT=$(echo "$TASK_INFO" | jq -r '.ReplicationTaskStats.FullLoadProgressPercent // 0')
  
  echo "[$(date '+%H:%M:%S')] Status: $STATUS | Full Load: ${PERCENT}%"
  
  # Check if full load is complete and CDC has started
  if [[ "$STATUS" == "running" ]]; then
    # Check if we're in CDC phase
    CDC_STATUS=$(echo "$TASK_INFO" | jq -r '.ReplicationTaskStats.TablesLoaded // 0')
    if [[ "$CDC_STATUS" -gt 0 ]]; then
      echo ""
      echo "✅ Full load completed successfully!"
      echo "✅ CDC (Change Data Capture) is now active"
      break
    fi
  elif [[ "$STATUS" == "stopped" ]] || [[ "$STATUS" == "failed" ]]; then
    echo ""
    echo "❌ Migration task failed or stopped"
    echo "$TASK_INFO" | jq -r '.StopReason'
    exit 1
  fi
  
  sleep 15
done

# Display final statistics
echo ""
echo "=== Migration Statistics ==="
aws dms describe-replication-tasks \
  --filters "Name=replication-task-arn,Values=$TASK_ARN" \
  --query "ReplicationTasks[0].ReplicationTaskStats" \
  --output json \
  --region "$REGION" | jq '{
    TablesLoaded: .TablesLoaded,
    TablesLoading: .TablesLoading,
    FullLoadProgressPercent: .FullLoadProgressPercent,
    ElapsedTimeMillis: .ElapsedTimeMillis
  }'
echo "============================"
echo ""
```

**Expected Output:**
```
Starting DMS migration task...
✅ Migration task started

⏳ Monitoring migration progress...
   Phase 1: Full Load (copying existing data)
   Phase 2: CDC (capturing ongoing changes)

[10:30:15] Status: starting | Full Load: 0%
[10:30:30] Status: running | Full Load: 45%
[10:30:45] Status: running | Full Load: 100%

✅ Full load completed successfully!
✅ CDC (Change Data Capture) is now active

=== Migration Statistics ===
{
  "TablesLoaded": 1,
  "TablesLoading": 0,
  "FullLoadProgressPercent": 100,
  "ElapsedTimeMillis": 45230
}
============================
```

---

# Step 13 – Validate Data in Aurora Target

```bash
# Verify data was migrated successfully to Aurora
echo "Validating migrated data in Aurora target..."
echo ""

# Query Aurora to check migrated data
echo "=== Aurora Target Database Content ==="
mysql -h "$AURORA_ENDPOINT" \
      -u "$DB_USER" \
      -p"$DB_PASS" \
      -D "$DB_NAME" \
      -e "SELECT id, name, role, salary FROM $TABLE_NAME LIMIT 5;"

echo ""

# Count records in Aurora
AURORA_COUNT=$(mysql -h "$AURORA_ENDPOINT" \
                     -u "$DB_USER" \
                     -p"$DB_PASS" \
                     -D "$DB_NAME" \
                     -se "SELECT COUNT(*) FROM $TABLE_NAME;")

# Count records in source MySQL
MYSQL_COUNT=$(mysql -h "$SRC_ENDPOINT" \
                    -u "$DB_USER" \
                    -p"$DB_PASS" \
                    -D "$DB_NAME" \
                    -se "SELECT COUNT(*) FROM $TABLE_NAME;")

echo "=== Record Count Comparison ==="
echo "Source MySQL Records: $MYSQL_COUNT"
echo "Target Aurora Records: $AURORA_COUNT"

if [[ "$MYSQL_COUNT" -eq "$AURORA_COUNT" ]]; then
  echo "✅ Record counts match - Migration successful!"
else
  echo "⚠️  Record count mismatch detected"
fi

echo "==============================="
echo ""
```

**Expected Output:**
```
Validating migrated data in Aurora target...

=== Aurora Target Database Content ===
+----+------------------+--------------------+--------+
| id | name             | role               | salary |
+----+------------------+--------------------+--------+
|  1 | Alice Johnson    | Software Engineer  |  95000 |
|  2 | Bob Smith        | Engineering Manager| 125000 |
|  3 | Clara Davis      | UX Designer        |  88000 |
|  4 | David Chen       | DevOps Engineer    |  98000 |
|  5 | Emma Wilson      | Product Manager    | 115000 |
+----+------------------+--------------------+--------+

=== Record Count Comparison ===
Source MySQL Records: 10
Target Aurora Records: 10
✅ Record counts match - Migration successful!
===============================
```

---

# Step 14 – Test Change Data Capture (CDC)

```bash
# Test CDC by inserting new records in source and verifying in target
echo "Testing Change Data Capture (CDC)..."
echo ""

# Insert new records in source MySQL
echo "Inserting new records in source MySQL..."
mysql -h "$SRC_ENDPOINT" \
      -u "$DB_USER" \
      -p"$DB_PASS" \
      -D "$DB_NAME" \
      -e "
INSERT INTO $TABLE_NAME (name, role, salary, hire_date, department) VALUES
  ('Karen White', 'Security Engineer', 105000, '2023-01-10', 'Security'),
  ('Leo Garcia', 'Cloud Architect', 140000, '2022-11-15', 'Engineering'),
  ('Maria Lopez', 'Scrum Master', 92000, '2023-03-05', 'Product');

SELECT 'Inserted 3 new records' AS Status;
"

echo "✅ New records inserted in source"

# Wait for CDC replication
echo ""
echo "⏳ Waiting for CDC replication (30 seconds)..."
sleep 30

# Verify new records in Aurora target
echo ""
echo "=== Verifying CDC in Aurora Target ==="

AURORA_COUNT_AFTER=$(mysql -h "$AURORA_ENDPOINT" \
                           -u "$DB_USER" \
                           -p"$DB_PASS" \
                           -D "$DB_NAME" \
                           -se "SELECT COUNT(*) FROM $TABLE_NAME;")

MYSQL_COUNT_AFTER=$(mysql -h "$SRC_ENDPOINT" \
                          -u "$DB_USER" \
                          -p"$DB_PASS" \
                          -D "$DB_NAME" \
                          -se "SELECT COUNT(*) FROM $TABLE_NAME;")

echo "Source MySQL Records: $MYSQL_COUNT_AFTER"
echo "Target Aurora Records: $AURORA_COUNT_AFTER"

if [[ "$MYSQL_COUNT_AFTER" -eq "$AURORA_COUNT_AFTER" ]]; then
  echo "✅ CDC is working - Records synchronized!"
else
  echo "⚠️  CDC sync in progress or issue detected"
fi

# Display newly replicated records
echo ""
echo "Latest records in Aurora:"
mysql -h "$AURORA_ENDPOINT" \
      -u "$DB_USER" \
      -p"$DB_PASS" \
      -D "$DB_NAME" \
      -e "SELECT id, name, role, department FROM $TABLE_NAME ORDER BY id DESC LIMIT 3;"

echo ""
echo "====================================="
echo ""

# Test UPDATE operation
echo "Testing UPDATE operation via CDC..."
mysql -h "$SRC_ENDPOINT" \
      -u "$DB_USER" \
      -p"$DB_PASS" \
      -D "$DB_NAME" \
      -e "UPDATE $TABLE_NAME SET salary = 150000 WHERE name = 'Grace Lee';"

echo "✅ Updated Grace Lee's salary in source"
echo "⏳ Waiting for CDC replication..."
sleep 15

# Verify update in Aurora
GRACE_SALARY=$(mysql -h "$AURORA_ENDPOINT" \
                     -u "$DB_USER" \
                     -p"$DB_PASS" \
                     -D "$DB_NAME" \
                     -se "SELECT salary FROM $TABLE_NAME WHERE name = 'Grace Lee';")

echo "Grace Lee's salary in Aurora: \$${GRACE_SALARY}"

if [[ "$GRACE_SALARY" == "150000" ]]; then
  echo "✅ UPDATE replicated successfully via CDC!"
else
  echo "⚠️  Update not yet replicated"
fi

echo ""
```

**Expected Output:**
```
Testing Change Data Capture (CDC)...

Inserting new records in source MySQL...
✅ New records inserted in source

⏳ Waiting for CDC replication (30 seconds)...

=== Verifying CDC in Aurora Target ===
Source MySQL Records: 13
Target Aurora Records: 13
✅ CDC is working - Records synchronized!

Latest records in Aurora:
+----+--------------+--------------------+------------+
| id | name         | role               | department |
+----+--------------+--------------------+------------+
| 13 | Maria Lopez  | Scrum Master       | Product    |
| 12 | Leo Garcia   | Cloud Architect    | Engineering|
| 11 | Karen White  | Security Engineer  | Security   |
+----+--------------+--------------------+------------+

=====================================

Testing UPDATE operation via CDC...
✅ Updated Grace Lee's salary in source
⏳ Waiting for CDC replication...
Grace Lee's salary in Aurora: $150000
✅ UPDATE replicated successfully via CDC!
```

---

# Step 15 – Review CloudWatch Metrics and Task Logs

```bash
# Review CloudWatch metrics for DMS task
echo "Reviewing CloudWatch metrics for DMS task..."
echo ""

# Get task identifier for metrics
TASK_ID=$(echo "$TASK_ARN" | awk -F':' '{print $NF}')

# Query CloudWatch metrics
echo "=== DMS Task Metrics ==="
aws cloudwatch list-metrics \
  --namespace "AWS/DMS" \
  --dimensions "Name=ReplicationTaskIdentifier,Value=mysql-to-aurora-migration" \
  --query "Metrics[*].MetricName" \
  --output table \
  --region "$REGION" 2>/dev/null || echo "Metrics may take a few minutes to populate"

echo ""

# Get CDC latency metric (if available)
echo "Querying CDC latency..."
aws cloudwatch get-metric-statistics \
  --namespace "AWS/DMS" \
  --metric-name "CDCLatencySource" \
  --dimensions "Name=ReplicationTaskIdentifier,Value=mysql-to-aurora-migration" \
  --start-time "$(date -u -d '1 hour ago' '+%Y-%m-%dT%H:%M:%S')" \
  --end-time "$(date -u '+%Y-%m-%dT%H:%M:%S')" \
  --period 300 \
  --statistics Average \
  --query "Datapoints[*].[Timestamp,Average]" \
  --output table \
  --region "$REGION" 2>/dev/null || echo "  (CDC latency metrics not yet available)"

echo ""
echo "=== Key DMS Metrics ==="
echo "- CDCLatencySource: Time lag between source and DMS"
echo "- CDCLatencyTarget: Time lag between DMS and target"
echo "- FullLoadThroughputRowsSource: Full load throughput"
echo "- CDCIncomingChanges: Number of changes captured"
echo "========================"
echo ""

# Display task details
echo "=== Current Task Status ==="
aws dms describe-replication-tasks \
  --filters "Name=replication-task-arn,Values=$TASK_ARN" \
  --query "ReplicationTasks[0].[Status,ReplicationTaskIdentifier,MigrationType]" \
  --output table \
  --region "$REGION"
echo "==========================="
echo ""
```

**Expected Output:**
```
Reviewing CloudWatch metrics for DMS task...

=== DMS Task Metrics ===
-----------------------------------------------------------------
|                        ListMetrics                             |
+---------------------------------------------------------------+
|  CDCLatencySource                                              |
|  CDCLatencyTarget                                              |
|  CDCIncomingChanges                                            |
|  FullLoadThroughputRowsSource                                  |
+---------------------------------------------------------------+

Querying CDC latency...
-----------------------------------------------------------------
|                    GetMetricStatistics                         |
+--------------------------------+------------------------------+
|  2025-11-13T10:30:00Z          |  2.5                        |
|  2025-11-13T10:35:00Z          |  1.8                        |
+--------------------------------+------------------------------+

=== Key DMS Metrics ===
- CDCLatencySource: Time lag between source and DMS
- CDCLatencyTarget: Time lag between DMS and target
- FullLoadThroughputRowsSource: Full load throughput
- CDCIncomingChanges: Number of changes captured
========================

=== Current Task Status ===
-----------------------------------------------------------------
|              DescribeReplicationTasks                          |
+------------------------+----------------------+----------------+
|  running               | mysql-to-aurora-migration | full-load-and-cdc |
+------------------------+----------------------+----------------+
===========================
```

---

# Step 16 – Cleanup Resources

```bash
# Comprehensive cleanup of all DMS and database resources
echo "Starting cleanup process..."
echo ""

# Stop DMS replication task
echo "Stopping DMS replication task..."
aws dms stop-replication-task \
  --replication-task-arn "$TASK_ARN" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ DMS task stop initiated"

# Wait for task to stop
echo "⏳ Waiting for task to stop..."
sleep 30

# Delete DMS replication task
echo "Deleting DMS replication task..."
aws dms delete-replication-task \
  --replication-task-arn "$TASK_ARN" \
  --region "$REGION" \
  --output json > /dev/null
echo "✅ DMS task deleted"

sleep 10

# Delete DMS endpoints
echo "Deleting DMS endpoints..."
aws dms delete-endpoint \
  --endpoint-arn "$SRC_EP_ARN" \
  --region "$REGION" \
  --output json > /dev/null
echo "✅ Source endpoint deleted"

aws dms delete-endpoint \
  --endpoint-arn "$DST_EP_ARN" \
  --region "$REGION" \
  --output json > /dev/null
echo "✅ Target endpoint deleted"

sleep 10

# Delete DMS replication instance
echo "Deleting DMS replication instance..."
aws dms delete-replication-instance \
  --replication-instance-arn "$DMS_REPLICA_ARN" \
  --region "$REGION" \
  --output json > /dev/null
echo "✅ DMS replication instance deletion initiated"

# Wait for replication instance to be deleted
echo "⏳ Waiting for DMS replication instance to be deleted..."
sleep 60

# Delete DMS subnet group
echo "Deleting DMS subnet group..."
aws dms delete-replication-subnet-group \
  --replication-subnet-group-identifier "$DMS_SUBNET_GROUP" \
  --region "$REGION" 2>/dev/null && echo "✅ DMS subnet group deleted" || echo "ℹ️  Subnet group already deleted"

# Delete Aurora instances and cluster
echo ""
echo "Deleting Aurora resources..."

# Delete Aurora writer instance
aws rds delete-db-instance \
  --db-instance-identifier "$AURORA_INSTANCE" \
  --skip-final-snapshot \
  --region "$REGION" \
  --output json > /dev/null
echo "✅ Aurora writer instance deletion initiated"

# Wait for instance deletion
echo "⏳ Waiting for Aurora instance to be deleted..."
sleep 60

# Delete Aurora cluster
aws rds delete-db-cluster \
  --db-cluster-identifier "$AURORA_CLUSTER" \
  --skip-final-snapshot \
  --region "$REGION" \
  --output json > /dev/null
echo "✅ Aurora cluster deletion initiated"

# Delete source MySQL database
echo ""
echo "Deleting source MySQL database..."
aws rds delete-db-instance \
  --db-instance-identifier "$MYSQL_SRC" \
  --skip-final-snapshot \
  --region "$REGION" \
  --output json > /dev/null
echo "✅ MySQL source database deletion initiated"

echo ""
echo "========================================="
echo "✅ Cleanup completed successfully!"
echo "========================================="
echo ""
echo "All resources have been deleted or are being deleted:"
echo "  ✓ DMS replication task"
echo "  ✓ DMS source and target endpoints"
echo "  ✓ DMS replication instance"
echo "  ✓ DMS subnet group"
echo "  ✓ Aurora cluster and instances"
echo "  ✓ Source MySQL database"
echo ""
echo "Note: Database deletions may take 5-10 minutes to complete."
echo ""
```

**Expected Output:**
```
Starting cleanup process...

Stopping DMS replication task...
✅ DMS task stop initiated
⏳ Waiting for task to stop...
Deleting DMS replication task...
✅ DMS task deleted
Deleting DMS endpoints...
✅ Source endpoint deleted
✅ Target endpoint deleted
Deleting DMS replication instance...
✅ DMS replication instance deletion initiated
⏳ Waiting for DMS replication instance to be deleted...
Deleting DMS subnet group...
✅ DMS subnet group deleted

Deleting Aurora resources...
✅ Aurora writer instance deletion initiated
⏳ Waiting for Aurora instance to be deleted...
✅ Aurora cluster deletion initiated

Deleting source MySQL database...
✅ MySQL source database deletion initiated

=========================================
✅ Cleanup completed successfully!
=========================================

All resources have been deleted or are being deleted:
  ✓ DMS replication task
  ✓ DMS source and target endpoints
  ✓ DMS replication instance
  ✓ DMS subnet group
  ✓ Aurora cluster and instances
  ✓ Source MySQL database

Note: Database deletions may take 5-10 minutes to complete.
```

---

## Best Practices

### Migration Planning
- **Assessment**: Use AWS Schema Conversion Tool (SCT) for complex migrations
- **Testing**: Always perform test migrations before production cutover
- **Timing**: Schedule migrations during maintenance windows
- **Validation**: Implement comprehensive data validation procedures
- **Rollback Plan**: Maintain rollback strategy in case of issues

### Security
- **Encryption**: Enable encryption in transit and at rest for both source and target
- **IAM Roles**: Use IAM roles with least privilege for DMS
- **Network Isolation**: Deploy DMS in private subnets with VPC endpoints
- **Password Management**: Use AWS Secrets Manager for database credentials
- **SSL/TLS**: Enable SSL connections for database endpoints

### Performance
- **Instance Sizing**: Choose appropriate DMS instance size based on workload
- **Multi-AZ**: Enable Multi-AZ for production DMS instances
- **Parallel Load**: Use multiple tasks for large table migrations
- **LOB Handling**: Configure Limited LOB mode for better performance
- **Batch Apply**: Tune batch apply settings for optimal throughput

### Cost Optimization
- **Right-Sizing**: Start with smaller instances and scale as needed
- **Task Scheduling**: Stop tasks when not actively migrating
- **Storage**: Use General Purpose (gp2) storage for most workloads
- **Cleanup**: Delete resources immediately after migration completion
- **Monitoring**: Set up billing alarms to avoid unexpected costs

### Reliability
- **Monitoring**: Enable CloudWatch Logs and set up alarms
- **Validation**: Use DMS data validation to verify migration accuracy
- **CDC Testing**: Thoroughly test CDC before production cutover
- **Backup**: Maintain source database backups during migration
- **Documentation**: Document migration procedures and configurations

---

## Troubleshooting

### Issue: DMS Task Stuck in "Creating" Status
**Cause**: Missing subnet group or VPC endpoint configuration  
**Solution**:
```bash
# Verify DMS subnet group exists
aws dms describe-replication-subnet-groups \
  --filters "Name=replication-subnet-group-id,Values=$DMS_SUBNET_GROUP"

# Check VPC configuration
aws ec2 describe-vpcs --vpc-ids $DEFAULT_VPC

# Ensure IAM role exists
aws iam get-role --role-name dms-vpc-role
```

### Issue: CDC Not Replicating Changes
**Cause**: Binary logging not enabled on source MySQL  
**Solution**:
```bash
# Verify binary logging is enabled
mysql -h $SRC_ENDPOINT -u $DB_USER -p$DB_PASS \
  -e "SHOW VARIABLES LIKE 'log_bin';"

# Enable binary logging (requires parameter group modification)
aws rds modify-db-instance \
  --db-instance-identifier $MYSQL_SRC \
  --db-parameter-group-name custom-mysql-binlog-enabled \
  --apply-immediately
```

### Issue: Permission Denied Errors
**Cause**: Missing IAM role for DMS VPC management  
**Solution**:
```bash
# Create dms-vpc-role
aws iam create-role \
  --role-name dms-vpc-role \
  --assume-role-policy-document file://dms-trust-policy.json

# Attach required policy
aws iam attach-role-policy \
  --role-name dms-vpc-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonDMSVPCManagementRole
```

### Issue: Aurora Connection Failures
**Cause**: Security group not allowing inbound traffic on port 3306  
**Solution**:
```bash
# Add security group rule
aws ec2 authorize-security-group-ingress \
  --group-id $DEFAULT_SG \
  --protocol tcp \
  --port 3306 \
  --source-group $DMS_SG

# Verify connectivity
mysql -h $AURORA_ENDPOINT -u $DB_USER -p$DB_PASS -e "SELECT 1;"
```

### Issue: High CDC Latency
**Cause**: Insufficient DMS instance size or network throughput  
**Solution**:
```bash
# Modify DMS instance class
aws dms modify-replication-instance \
  --replication-instance-arn $DMS_REPLICA_ARN \
  --replication-instance-class dms.c5.large \
  --apply-immediately

# Monitor metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/DMS \
  --metric-name CDCLatencySource \
  --dimensions Name=ReplicationTaskIdentifier,Value=mysql-to-aurora-migration
```

### Issue: Table Mapping Errors
**Cause**: Incorrect schema or table names in mapping rules  
**Solution**:
```bash
# Verify table mappings
aws dms describe-replication-tasks \
  --filters "Name=replication-task-arn,Values=$TASK_ARN" \
  --query "ReplicationTasks[0].TableMappings"

# Test with wildcard pattern
# Use "%" to include all tables in schema
```

---

## Additional Resources

### AWS Documentation
- [AWS DMS User Guide](https://docs.aws.amazon.com/dms/)
- [DMS Best Practices](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_BestPractices.html)
- [Schema Conversion Tool](https://docs.aws.amazon.com/SchemaConversionTool/)
- [Aurora MySQL Migration](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Migrate.html)

### Migration Patterns
- **Homogeneous**: MySQL to Aurora MySQL (this lab)
- **Heterogeneous**: Oracle to PostgreSQL, SQL Server to Aurora
- **Continuous Replication**: CDC for minimal downtime migrations
- **Consolidation**: Multiple databases to single target

### Related Services
- **AWS Schema Conversion Tool (SCT)**: Convert database schemas
- **AWS Database Migration Service Fleet Advisor**: Discover source databases
- **AWS Application Discovery Service**: Assess on-premises workloads
- **Amazon Aurora Global Database**: Multi-region replication

### Use Cases
- **Cloud Migration**: Move on-premises databases to AWS
- **Database Modernization**: Upgrade to Aurora for better performance
- **Disaster Recovery**: Replicate databases across regions
- **Development/Test**: Create copies for non-production environments
- **Data Consolidation**: Merge multiple databases into one

---

## Key Takeaways

1. **DMS Simplifies Migrations**: Fully managed service with minimal downtime
2. **Full Load + CDC**: Initial data copy plus ongoing change replication
3. **Homogeneous Migration**: Direct MySQL to Aurora MySQL without schema conversion
4. **Automatic Schema Creation**: DMS creates tables in target database
5. **Real-Time Replication**: CDC captures changes with low latency
6. **Endpoint Testing**: Always test source and target connections before migration
7. **CloudWatch Integration**: Comprehensive monitoring and logging
8. **Aurora Benefits**: Better performance, scalability, and availability than RDS MySQL

---

## Summary

In this lab, you successfully:
- ✅ Created source RDS MySQL database with sample employee data
- ✅ Deployed Amazon Aurora MySQL cluster as migration target
- ✅ Configured DMS replication instance and subnet group
- ✅ Set up and tested source and target database endpoints
- ✅ Created DMS migration task with full load and CDC
- ✅ Executed migration and monitored progress to completion
- ✅ Validated data integrity with record count comparisons
- ✅ Tested Change Data Capture with INSERT and UPDATE operations
- ✅ Reviewed CloudWatch metrics for migration monitoring
- ✅ Performed comprehensive resource cleanup

AWS DMS provides a powerful, managed solution for database migrations with minimal downtime, supporting both homogeneous and heterogeneous migrations. Combined with Amazon Aurora's superior performance and availability, this creates an ideal path for modernizing database infrastructure.

---

## End of Lab 15.B

**Next Lab**: Lab 15.C - AWS Server Migration Service (SMS) - Migrate Virtual Machines

---
