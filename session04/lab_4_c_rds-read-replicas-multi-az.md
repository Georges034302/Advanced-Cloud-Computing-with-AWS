# Lab 4.C: RDS Read Replicas and Multi-AZ High Availability

## Overview
This lab demonstrates high availability and scalability features of Amazon RDS by implementing Multi-AZ deployments for automatic failover and read replicas for horizontal scaling. You will deploy an RDS MySQL instance, enable Multi-AZ, create read replicas, test failover scenarios, and implement read/write splitting patterns.

---

## Objectives
- Create RDS MySQL instance with Multi-AZ deployment
- Configure automated backups and maintenance windows
- Create read replicas in same and different regions
- Test automatic failover with Multi-AZ
- Implement read/write traffic splitting
- Monitor replication lag and performance metrics
- Promote read replica to standalone instance
- Perform cross-region disaster recovery
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Default VPC with subnets in multiple availability zones
- IAM permissions to manage RDS, EC2, and VPC resources
- MySQL client installed locally or on EC2 instance
- Basic understanding of SQL and replication concepts

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID dynamically
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set primary region
PRIMARY_REGION="ap-southeast-2"
echo "PRIMARY_REGION=$PRIMARY_REGION"

# Set secondary region for cross-region replica
SECONDARY_REGION="ap-southeast-1"
echo "SECONDARY_REGION=$SECONDARY_REGION"

# Set database identifiers
DB_INSTANCE_ID="lab-mysql-primary"
echo "DB_INSTANCE_ID=$DB_INSTANCE_ID"

READ_REPLICA_ID="lab-mysql-replica"
echo "READ_REPLICA_ID=$READ_REPLICA_ID"

CROSS_REGION_REPLICA_ID="lab-mysql-replica-cross-region"
echo "CROSS_REGION_REPLICA_ID=$CROSS_REGION_REPLICA_ID"

# Set database configuration
DB_NAME="labdb"
echo "DB_NAME=$DB_NAME"

MASTER_USERNAME="labadmin"
echo "MASTER_USERNAME=$MASTER_USERNAME"

# Generate secure password
MASTER_PASSWORD=$(openssl rand -base64 16 | tr -d "=+/" | cut -c1-16)
echo "MASTER_PASSWORD=$MASTER_PASSWORD"
echo "Save this password for later use!"

# Set instance class (free tier eligible)
DB_INSTANCE_CLASS="db.t3.micro"
echo "DB_INSTANCE_CLASS=$DB_INSTANCE_CLASS"

# Set allocated storage
ALLOCATED_STORAGE=20
echo "ALLOCATED_STORAGE=$ALLOCATED_STORAGE"

# Get default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region "$PRIMARY_REGION")
echo "VPC_ID=$VPC_ID"

# Verify AWS CLI is configured
aws sts get-caller-identity
```

---

## Step 2 – Create Security Group for RDS

```bash
# Create security group for RDS instances
DB_SG_ID=$(aws ec2 create-security-group \
  --group-name "rds-mysql-sg" \
  --description "Security group for RDS MySQL with Multi-AZ and replicas" \
  --vpc-id "$VPC_ID" \
  --region "$PRIMARY_REGION" \
  --query 'GroupId' \
  --output text)
echo "DB_SG_ID=$DB_SG_ID"

# Get VPC CIDR for internal access
VPC_CIDR=$(aws ec2 describe-vpcs \
  --vpc-ids "$VPC_ID" \
  --query 'Vpcs[0].CidrBlock' \
  --output text \
  --region "$PRIMARY_REGION")
echo "VPC_CIDR=$VPC_CIDR"

# Allow MySQL access from VPC CIDR (internal access)
aws ec2 authorize-security-group-ingress \
  --group-id "$DB_SG_ID" \
  --protocol tcp \
  --port 3306 \
  --cidr "$VPC_CIDR" \
  --region "$PRIMARY_REGION"

echo "Security group created with MySQL access from VPC"

# Describe security group
aws ec2 describe-security-groups \
  --group-ids "$DB_SG_ID" \
  --query 'SecurityGroups[0].{GroupId:GroupId,GroupName:GroupName,IpPermissions:IpPermissions}' \
  --output json \
  --region "$PRIMARY_REGION" | jq '.'
```

---

## Step 3 – Create DB Subnet Group

```bash
# Get all subnet IDs in default VPC across availability zones
SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[*].SubnetId' \
  --output text \
  --region "$PRIMARY_REGION")
echo "SUBNET_IDS=$SUBNET_IDS"

# Create DB subnet group for Multi-AZ deployment
aws rds create-db-subnet-group \
  --db-subnet-group-name "lab-db-subnet-group" \
  --db-subnet-group-description "Subnet group for RDS Multi-AZ lab" \
  --subnet-ids $SUBNET_IDS \
  --region "$PRIMARY_REGION"

echo "DB subnet group created across multiple availability zones"

# Describe DB subnet group
aws rds describe-db-subnet-groups \
  --db-subnet-group-name "lab-db-subnet-group" \
  --query 'DBSubnetGroups[0].{Name:DBSubnetGroupName,VpcId:VpcId,Subnets:Subnets[*].SubnetIdentifier}' \
  --output json \
  --region "$PRIMARY_REGION" | jq '.'
```

---

## Step 4 – Create RDS MySQL Instance with Multi-AZ

```bash
# Create RDS MySQL instance with Multi-AZ enabled
echo "Creating RDS MySQL instance with Multi-AZ deployment..."

aws rds create-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --db-instance-class "$DB_INSTANCE_CLASS" \
  --engine mysql \
  --engine-version "8.0.35" \
  --master-username "$MASTER_USERNAME" \
  --master-user-password "$MASTER_PASSWORD" \
  --allocated-storage "$ALLOCATED_STORAGE" \
  --db-name "$DB_NAME" \
  --vpc-security-group-ids "$DB_SG_ID" \
  --db-subnet-group-name "lab-db-subnet-group" \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00" \
  --preferred-maintenance-window "sun:04:00-sun:05:00" \
  --multi-az \
  --publicly-accessible \
  --storage-type gp3 \
  --storage-encrypted \
  --enable-cloudwatch-logs-exports '["error","general","slowquery"]' \
  --deletion-protection \
  --region "$PRIMARY_REGION"

echo ""
echo "RDS instance creation initiated with Multi-AZ enabled"
echo "This will take 10-15 minutes..."

# Wait for instance to be available
echo "Waiting for RDS instance to become available..."
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$PRIMARY_REGION"

echo "RDS instance is now available!"

# Get instance details
aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].{Endpoint:Endpoint.Address,Port:Endpoint.Port,MultiAZ:MultiAZ,Status:DBInstanceStatus,AZ:AvailabilityZone,SecondaryAZ:SecondaryAvailabilityZone}' \
  --output table \
  --region "$PRIMARY_REGION"
```

---

## Step 5 – Get Database Endpoint and Connection Details

```bash
# Get primary instance endpoint
DB_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text \
  --region "$PRIMARY_REGION")
echo "DB_ENDPOINT=$DB_ENDPOINT"

# Get port
DB_PORT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].Endpoint.Port' \
  --output text \
  --region "$PRIMARY_REGION")
echo "DB_PORT=$DB_PORT"

# Get availability zones
PRIMARY_AZ=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].AvailabilityZone' \
  --output text \
  --region "$PRIMARY_REGION")
echo "PRIMARY_AZ=$PRIMARY_AZ"

SECONDARY_AZ=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].SecondaryAvailabilityZone' \
  --output text \
  --region "$PRIMARY_REGION")
echo "SECONDARY_AZ=$SECONDARY_AZ"

echo ""
echo "Connection command:"
echo "mysql -h $DB_ENDPOINT -P $DB_PORT -u $MASTER_USERNAME -p"
echo ""
echo "Multi-AZ Configuration:"
echo "Primary AZ: $PRIMARY_AZ"
echo "Secondary AZ: $SECONDARY_AZ"
```

---

## Step 6 – Connect and Create Sample Database

```bash
# Create SQL script for initial data
cat > init-database.sql <<EOF
-- Create sample table
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Insert sample data
INSERT INTO products (name, description, price, stock) VALUES
('Laptop', 'High-performance laptop', 1299.99, 50),
('Mouse', 'Wireless mouse', 29.99, 200),
('Keyboard', 'Mechanical keyboard', 89.99, 150),
('Monitor', '27-inch 4K monitor', 399.99, 75),
('Headphones', 'Noise-cancelling headphones', 199.99, 100);

-- Create read-only test query
SELECT 'Database initialized successfully' AS status;
SELECT COUNT(*) AS product_count FROM products;
EOF

# Display SQL script
cat init-database.sql

echo ""
echo "Connect to database and run the SQL script:"
echo "mysql -h $DB_ENDPOINT -P $DB_PORT -u $MASTER_USERNAME -p$MASTER_PASSWORD < init-database.sql"
echo ""
echo "Or connect interactively:"
echo "mysql -h $DB_ENDPOINT -P $DB_PORT -u $MASTER_USERNAME -p$MASTER_PASSWORD $DB_NAME"
```

---

## Step 7 – Create Read Replica in Same Region

```bash
# Create read replica in same region
echo "Creating read replica in same region..."

aws rds create-db-instance-read-replica \
  --db-instance-identifier "$READ_REPLICA_ID" \
  --source-db-instance-identifier "$DB_INSTANCE_ID" \
  --db-instance-class "$DB_INSTANCE_CLASS" \
  --publicly-accessible \
  --region "$PRIMARY_REGION"

echo "Read replica creation initiated..."

# Wait for replica to be available
echo "Waiting for read replica to become available..."
aws rds wait db-instance-available \
  --db-instance-identifier "$READ_REPLICA_ID" \
  --region "$PRIMARY_REGION"

echo "Read replica is now available!"

# Get replica endpoint
REPLICA_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$READ_REPLICA_ID" \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text \
  --region "$PRIMARY_REGION")
echo "REPLICA_ENDPOINT=$REPLICA_ENDPOINT"

# Get replica details
aws rds describe-db-instances \
  --db-instance-identifier "$READ_REPLICA_ID" \
  --query 'DBInstances[0].{Endpoint:Endpoint.Address,Status:DBInstanceStatus,AZ:AvailabilityZone,SourceDB:ReadReplicaSourceDBInstanceIdentifier}' \
  --output table \
  --region "$PRIMARY_REGION"
```

---

## Step 8 – Monitor Replication Lag

```bash
# Check replication lag for read replica
echo "Monitoring replication lag..."

# Get replica lag metric
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name ReplicaLag \
  --dimensions Name=DBInstanceIdentifier,Value="$READ_REPLICA_ID" \
  --start-time "$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Average \
  --region "$PRIMARY_REGION" \
  --query 'Datapoints[*].{Timestamp:Timestamp,ReplicaLag:Average}' \
  --output table

# Describe read replica status
aws rds describe-db-instances \
  --db-instance-identifier "$READ_REPLICA_ID" \
  --query 'DBInstances[0].{StatusInfos:StatusInfos,ReplicationSourceIdentifier:ReadReplicaSourceDBInstanceIdentifier}' \
  --output json \
  --region "$PRIMARY_REGION" | jq '.'

echo ""
echo "Check replication status with SQL:"
echo "mysql -h $REPLICA_ENDPOINT -P $DB_PORT -u $MASTER_USERNAME -p$MASTER_PASSWORD -e 'SHOW REPLICA STATUS\G'"
```

---

## Step 9 – Create Cross-Region Read Replica

```bash
# Create security group in secondary region
SECONDARY_SG_ID=$(aws ec2 create-security-group \
  --group-name "rds-mysql-replica-sg" \
  --description "Security group for cross-region RDS read replica" \
  --region "$SECONDARY_REGION" \
  --query 'GroupId' \
  --output text)
echo "SECONDARY_SG_ID=$SECONDARY_SG_ID"

# Allow MySQL access from anywhere (or restrict to specific IP)
aws ec2 authorize-security-group-ingress \
  --group-id "$SECONDARY_SG_ID" \
  --protocol tcp \
  --port 3306 \
  --cidr 0.0.0.0/0 \
  --region "$SECONDARY_REGION"

# Create cross-region read replica
echo "Creating cross-region read replica in $SECONDARY_REGION..."

aws rds create-db-instance-read-replica \
  --db-instance-identifier "$CROSS_REGION_REPLICA_ID" \
  --source-db-instance-identifier "arn:aws:rds:${PRIMARY_REGION}:${ACCOUNT_ID}:db:${DB_INSTANCE_ID}" \
  --db-instance-class "$DB_INSTANCE_CLASS" \
  --publicly-accessible \
  --vpc-security-group-ids "$SECONDARY_SG_ID" \
  --region "$SECONDARY_REGION"

echo "Cross-region replica creation initiated..."
echo "This will take 15-20 minutes..."

# Wait for cross-region replica
echo "Waiting for cross-region replica to become available..."
aws rds wait db-instance-available \
  --db-instance-identifier "$CROSS_REGION_REPLICA_ID" \
  --region "$SECONDARY_REGION"

echo "Cross-region replica is now available!"

# Get cross-region replica endpoint
CROSS_REGION_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$CROSS_REGION_REPLICA_ID" \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text \
  --region "$SECONDARY_REGION")
echo "CROSS_REGION_ENDPOINT=$CROSS_REGION_ENDPOINT"

# Display replica details
aws rds describe-db-instances \
  --db-instance-identifier "$CROSS_REGION_REPLICA_ID" \
  --query 'DBInstances[0].{Endpoint:Endpoint.Address,Status:DBInstanceStatus,Region:AvailabilityZone,SourceDB:ReadReplicaSourceDBInstanceIdentifier}' \
  --output table \
  --region "$SECONDARY_REGION"
```

---

## Step 10 – Test Read/Write Splitting

```bash
# Create Python script to demonstrate read/write splitting
cat > test-read-write-split.py <<'SCRIPT'
#!/usr/bin/env python3
import pymysql
import sys
import time

# Connection details (replace with your values)
PRIMARY_HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
REPLICA_HOST = sys.argv[2] if len(sys.argv) > 2 else "localhost"
USERNAME = sys.argv[3] if len(sys.argv) > 3 else "labadmin"
PASSWORD = sys.argv[4] if len(sys.argv) > 4 else "password"
DATABASE = "labdb"

def get_connection(host):
    """Create database connection"""
    return pymysql.connect(
        host=host,
        user=USERNAME,
        password=PASSWORD,
        database=DATABASE,
        cursorclass=pymysql.cursors.DictCursor
    )

def write_operation(conn):
    """Perform write operation on primary"""
    with conn.cursor() as cursor:
        sql = "INSERT INTO products (name, description, price, stock) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, ('New Product', 'Test product', 99.99, 10))
        conn.commit()
        print(f"✅ Write completed - Inserted new product (ID: {cursor.lastrowid})")
        return cursor.lastrowid

def read_operation(conn, product_id=None):
    """Perform read operation on replica"""
    with conn.cursor() as cursor:
        if product_id:
            sql = "SELECT * FROM products WHERE id = %s"
            cursor.execute(sql, (product_id,))
        else:
            sql = "SELECT * FROM products ORDER BY id DESC LIMIT 5"
            cursor.execute(sql)
        results = cursor.fetchall()
        print(f"✅ Read completed - Found {len(results)} products")
        return results

def main():
    print("=" * 60)
    print("RDS Read/Write Splitting Test")
    print("=" * 60)
    
    # Write to primary
    print(f"\n1. Writing to PRIMARY: {PRIMARY_HOST}")
    primary_conn = get_connection(PRIMARY_HOST)
    new_id = write_operation(primary_conn)
    primary_conn.close()
    
    # Wait for replication
    print("\n2. Waiting 2 seconds for replication...")
    time.sleep(2)
    
    # Read from replica
    print(f"\n3. Reading from REPLICA: {REPLICA_HOST}")
    replica_conn = get_connection(REPLICA_HOST)
    products = read_operation(replica_conn, new_id)
    
    if products:
        print(f"\n✅ Replication successful! Product found on replica:")
        for product in products:
            print(f"   - {product['name']}: ${product['price']}")
    else:
        print(f"\n⚠️  Product not yet replicated (may need more time)")
    
    replica_conn.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
SCRIPT

# Make script executable
chmod +x test-read-write-split.py

echo ""
echo "Python test script created: test-read-write-split.py"
echo ""
echo "Install PyMySQL if needed:"
echo "  pip install pymysql"
echo ""
echo "Run the test:"
echo "  python3 test-read-write-split.py $DB_ENDPOINT $REPLICA_ENDPOINT $MASTER_USERNAME $MASTER_PASSWORD"
```

---

## Step 11 – Test Multi-AZ Failover

```bash
# Initiate failover to test Multi-AZ automatic failover
echo "Testing Multi-AZ automatic failover..."

# Record current availability zone
CURRENT_AZ=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].AvailabilityZone' \
  --output text \
  --region "$PRIMARY_REGION")
echo "CURRENT_AZ=$CURRENT_AZ"

# Initiate reboot with failover
echo "Initiating reboot with failover..."
aws rds reboot-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --force-failover \
  --region "$PRIMARY_REGION"

echo "Failover initiated. Monitoring status..."

# Wait for instance to be available again
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$PRIMARY_REGION"

# Check new availability zone after failover
NEW_AZ=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBInstances[0].AvailabilityZone' \
  --output text \
  --region "$PRIMARY_REGION")
echo "NEW_AZ=$NEW_AZ"

echo ""
echo "Failover completed!"
echo "Previous AZ: $CURRENT_AZ"
echo "Current AZ:  $NEW_AZ"
echo ""
echo "Note: Endpoint remains the same: $DB_ENDPOINT"
echo "Application connections are automatically redirected"
```

---

## Step 12 – Promote Read Replica to Standalone Instance

```bash
# Promote read replica to standalone instance
echo "Promoting read replica to standalone instance..."

# Note: This will break replication and create an independent database
aws rds promote-read-replica \
  --db-instance-identifier "$READ_REPLICA_ID" \
  --backup-retention-period 7 \
  --region "$PRIMARY_REGION"

echo "Replica promotion initiated..."

# Wait for promotion to complete
echo "Waiting for promotion to complete..."
aws rds wait db-instance-available \
  --db-instance-identifier "$READ_REPLICA_ID" \
  --region "$PRIMARY_REGION"

echo "Promotion completed!"

# Verify replica is now standalone
aws rds describe-db-instances \
  --db-instance-identifier "$READ_REPLICA_ID" \
  --query 'DBInstances[0].{Endpoint:Endpoint.Address,Status:DBInstanceStatus,ReadReplicaSource:ReadReplicaSourceDBInstanceIdentifier,ReadReplicas:ReadReplicaDBInstanceIdentifiers}' \
  --output table \
  --region "$PRIMARY_REGION"

echo ""
echo "The replica is now a standalone RDS instance with read/write capability"
echo "It is no longer synchronized with the primary instance"
```

---

## Step 13 – Monitor Performance Metrics

```bash
# Get CPU utilization for primary instance
echo "Retrieving CPU utilization metrics..."

aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBInstanceIdentifier,Value="$DB_INSTANCE_ID" \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Average,Maximum \
  --region "$PRIMARY_REGION" \
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
  --region "$PRIMARY_REGION" \
  --query 'Datapoints[*].{Timestamp:Timestamp,Average:Average,Maximum:Maximum}' \
  --output table

# List available metrics
echo ""
echo "Available CloudWatch metrics for RDS:"
aws cloudwatch list-metrics \
  --namespace AWS/RDS \
  --dimensions Name=DBInstanceIdentifier,Value="$DB_INSTANCE_ID" \
  --region "$PRIMARY_REGION" \
  --query 'Metrics[*].MetricName' \
  --output text | tr '\t' '\n' | sort -u
```

---

## Step 14 – Create Manual Snapshot

```bash
# Create manual snapshot of primary instance
SNAPSHOT_ID="${DB_INSTANCE_ID}-snapshot-$(date +%Y%m%d-%H%M%S)"
echo "SNAPSHOT_ID=$SNAPSHOT_ID"

# Create snapshot
echo "Creating manual snapshot..."
aws rds create-db-snapshot \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --db-snapshot-identifier "$SNAPSHOT_ID" \
  --region "$PRIMARY_REGION"

# Wait for snapshot to complete
echo "Waiting for snapshot to complete..."
aws rds wait db-snapshot-completed \
  --db-snapshot-identifier "$SNAPSHOT_ID" \
  --region "$PRIMARY_REGION"

echo "Snapshot created successfully!"

# Describe snapshot
aws rds describe-db-snapshots \
  --db-snapshot-identifier "$SNAPSHOT_ID" \
  --query 'DBSnapshots[0].{SnapshotId:DBSnapshotIdentifier,Status:Status,Size:AllocatedStorage,CreateTime:SnapshotCreateTime,Encrypted:Encrypted}' \
  --output table \
  --region "$PRIMARY_REGION"

# List all snapshots for this instance
echo ""
echo "All snapshots for $DB_INSTANCE_ID:"
aws rds describe-db-snapshots \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query 'DBSnapshots[*].{SnapshotId:DBSnapshotIdentifier,Type:SnapshotType,Status:Status,CreateTime:SnapshotCreateTime}' \
  --output table \
  --region "$PRIMARY_REGION"
```

---

## Step 15 – Cleanup Resources

```bash
# Disable deletion protection on primary instance
echo "Disabling deletion protection..."
aws rds modify-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --no-deletion-protection \
  --apply-immediately \
  --region "$PRIMARY_REGION"

# Wait for modification to complete
echo "Waiting for modification to complete..."
sleep 10

# Delete cross-region read replica first
echo "Deleting cross-region read replica..."
aws rds delete-db-instance \
  --db-instance-identifier "$CROSS_REGION_REPLICA_ID" \
  --skip-final-snapshot \
  --delete-automated-backups \
  --region "$SECONDARY_REGION"

# Delete promoted replica (now standalone instance)
echo "Deleting promoted replica instance..."
aws rds delete-db-instance \
  --db-instance-identifier "$READ_REPLICA_ID" \
  --skip-final-snapshot \
  --delete-automated-backups \
  --region "$PRIMARY_REGION"

# Delete primary instance
echo "Deleting primary RDS instance..."
aws rds delete-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --skip-final-snapshot \
  --delete-automated-backups \
  --region "$PRIMARY_REGION"

# Wait for instances to be deleted
echo "Waiting for instances to be deleted..."
echo "This may take several minutes..."

aws rds wait db-instance-deleted \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$PRIMARY_REGION" || echo "Primary instance deleted"

aws rds wait db-instance-deleted \
  --db-instance-identifier "$READ_REPLICA_ID" \
  --region "$PRIMARY_REGION" || echo "Replica instance deleted"

aws rds wait db-instance-deleted \
  --db-instance-identifier "$CROSS_REGION_REPLICA_ID" \
  --region "$SECONDARY_REGION" || echo "Cross-region replica deleted"

# Delete manual snapshot
echo "Deleting manual snapshot..."
aws rds delete-db-snapshot \
  --db-snapshot-identifier "$SNAPSHOT_ID" \
  --region "$PRIMARY_REGION"

# Delete DB subnet group
echo "Deleting DB subnet group..."
aws rds delete-db-subnet-group \
  --db-subnet-group-name "lab-db-subnet-group" \
  --region "$PRIMARY_REGION"

# Delete security groups
echo "Deleting security groups..."
sleep 10

aws ec2 delete-security-group \
  --group-id "$DB_SG_ID" \
  --region "$PRIMARY_REGION"

aws ec2 delete-security-group \
  --group-id "$SECONDARY_SG_ID" \
  --region "$SECONDARY_REGION"

# Delete local files
echo "Cleaning up local files..."
rm -f init-database.sql test-read-write-split.py

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- Primary RDS instance (Multi-AZ)"
echo "- Read replica (promoted)"
echo "- Cross-region read replica"
echo "- Manual snapshot"
echo "- DB subnet group"
echo "- Security groups (2)"
echo "- Local test files"
```

---

## Summary

In this lab, you have:
- Created RDS MySQL instance with Multi-AZ deployment for high availability
- Configured automated backups and maintenance windows
- Created read replica in same region for horizontal read scaling
- Created cross-region read replica for disaster recovery
- Monitored replication lag using CloudWatch metrics
- Tested automatic failover with Multi-AZ configuration
- Implemented read/write splitting pattern with Python
- Promoted read replica to standalone instance
- Created manual snapshots for point-in-time recovery
- Monitored performance metrics across all instances

**Key Takeaways:**
- **Multi-AZ**: Provides automatic failover (1-2 minutes) for high availability
- **Read Replicas**: Horizontal scaling for read-heavy workloads (up to 5 per primary)
- **Cross-Region**: Disaster recovery and geographic distribution
- **Synchronous vs Asynchronous**: Multi-AZ uses synchronous replication, read replicas use asynchronous
- **Endpoint Stability**: Multi-AZ endpoint remains unchanged during failover
- **Promotion**: Read replicas can become standalone databases
- **No Downtime**: Read replicas can be created without downtime to primary

**Multi-AZ vs Read Replicas:**
| Feature | Multi-AZ | Read Replicas |
|---------|----------|---------------|
| **Purpose** | High availability | Horizontal scaling |
| **Replication** | Synchronous | Asynchronous |
| **Availability** | Same region, different AZ | Same or different region |
| **Automatic Failover** | Yes (1-2 minutes) | No (manual promotion) |
| **Read Traffic** | No (standby not accessible) | Yes (readable) |
| **Write Traffic** | Primary only | Primary only |
| **Cost** | ~2x single AZ | Additional instance cost |

**Use Cases:**
- **Multi-AZ**: Production databases requiring 99.95% availability
- **Read Replicas**: Analytics, reporting, read-heavy applications
- **Cross-Region Replicas**: Global applications, disaster recovery, compliance
- **Read/Write Splitting**: Separate read and write workloads for optimization

**Performance Optimization:**
- Use read replicas for SELECT queries
- Keep writes on primary instance
- Monitor replication lag (should be < 1 second)
- Use appropriate instance classes for workload
- Enable Enhanced Monitoring for detailed metrics
- Configure connection pooling in applications

**Cost Optimization:**
- Start with single-AZ for dev/test
- Enable Multi-AZ only for production
- Use read replicas instead of larger primary instance
- Delete unused snapshots and replicas
- Consider Reserved Instances for long-term workloads

**Real-World Architectures:**
- **E-commerce**: Primary for orders, replicas for product catalog queries
- **Analytics**: Replicas for business intelligence without impacting production
- **Global Apps**: Cross-region replicas for low latency worldwide
- **Disaster Recovery**: Cross-region replica as warm standby

---

## Additional Resources
- [Amazon RDS Multi-AZ Deployments](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html)
- [Working with Read Replicas](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html)
- [RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [Monitoring RDS Metrics](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/monitoring-cloudwatch.html)
- [RDS Backup and Restore](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_CommonTasks.BackupRestore.html)

---
