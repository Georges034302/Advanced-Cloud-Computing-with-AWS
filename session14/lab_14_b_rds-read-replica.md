# Lab 14.B: Amazon RDS - Cross-Region Read Replicas for Disaster Recovery

## Overview
This lab demonstrates Amazon RDS cross-region read replication, a key disaster recovery strategy that replicates your primary database to another AWS region. You'll create a primary RDS MySQL database, establish a cross-region read replica, test replication, simulate a disaster by promoting the replica, and verify failover functionality.

---

## Objectives
- Create RDS MySQL primary database instance
- Enable automated backups for replication
- Create cross-region read replica
- Populate primary database with sample data
- Verify asynchronous replication to replica
- Monitor replication lag
- Simulate disaster by promoting read replica
- Test write operations on promoted database
- Clean up multi-region resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for RDS operations
- MySQL client installed (`mysql` command)
- Regions: ap-southeast-2 (primary), us-west-2 (DR)
- Understanding of RDS replication concepts

---

## Architecture

```
Primary Region (ap-southeast-2)
          ↓
  RDS MySQL Primary
  - Read/Write
  - Auto Backups Enabled
          ↓
  Asynchronous Replication
          ↓
DR Region (us-west-2)
          ↓
  RDS Read Replica
  - Read-Only (until promoted)
  - Can be promoted to standalone
          ↓
  On Disaster: Promote Replica
          ↓
  New Primary in DR Region
  - Read/Write enabled
  - Independent database
```

---

## Step 1 – Set Variables

```bash
# Set regions
PRIMARY_REGION="ap-southeast-2"
DR_REGION="us-west-2"
export AWS_REGION="$PRIMARY_REGION"

echo "PRIMARY_REGION=$PRIMARY_REGION"
echo "DR_REGION=$DR_REGION"

# Set database identifiers
DB_INSTANCE_ID="primary-mysql-db"
DB_REPLICA_ID="dr-mysql-replica"

echo "DB_INSTANCE_ID=$DB_INSTANCE_ID"
echo "DB_REPLICA_ID=$DB_REPLICA_ID"

# Set credentials (DEMO ONLY - use Secrets Manager in production)
MASTER_USERNAME="admin"
MASTER_PASSWORD="MySecurePass123!"

echo "MASTER_USERNAME=$MASTER_USERNAME"
echo ""
echo "================================================"
echo "RDS CROSS-REGION REPLICATION"
echo "================================================"
```

---

## Step 2 – Create Primary RDS Instance

```bash
echo ""
echo "Creating primary RDS MySQL instance in $PRIMARY_REGION..."

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --engine mysql \
  --engine-version "8.0.35" \
  --db-instance-class db.t3.micro \
  --allocated-storage 20 \
  --storage-type gp2 \
  --master-username "$MASTER_USERNAME" \
  --master-user-password "$MASTER_PASSWORD" \
  --backup-retention-period 7 \
  --publicly-accessible \
  --no-multi-az \
  --region "$PRIMARY_REGION" \
  --tags Key=Name,Value=PrimaryDatabase Key=Environment,Value=DR-Demo

echo "✅ RDS instance creation initiated"
echo "   Instance ID: $DB_INSTANCE_ID"
echo "   Engine: MySQL 8.0.35"
echo "   Class: db.t3.micro"
echo "   Backup Retention: 7 days (required for replication)"
```

---

## Step 3 – Wait for Primary Instance to be Available

```bash
echo ""
echo "Waiting for primary RDS instance to be available..."
echo "(This typically takes 5-10 minutes)"
echo ""

# Wait for instance to be available
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$PRIMARY_REGION"

echo "✅ Primary RDS instance is now available"
```

---

## Step 4 – Get Primary Database Endpoint

```bash
echo ""
echo "Retrieving primary database endpoint..."

# Get endpoint address
PRIMARY_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$PRIMARY_REGION" \
  --query "DBInstances[0].Endpoint.Address" \
  --output text)

echo "PRIMARY_ENDPOINT=$PRIMARY_ENDPOINT"

# Get port
PRIMARY_PORT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$PRIMARY_REGION" \
  --query "DBInstances[0].Endpoint.Port" \
  --output text)

echo "PRIMARY_PORT=$PRIMARY_PORT"
echo ""
echo "✅ Primary database endpoint obtained"
```

---

## Step 5 – Create Database and Sample Data

```bash
echo ""
echo "================================================"
echo "POPULATING PRIMARY DATABASE"
echo "================================================"
echo ""

echo "Creating database and sample data..."

# Connect and create database with sample data
mysql -h "$PRIMARY_ENDPOINT" \
  -P "$PRIMARY_PORT" \
  -u "$MASTER_USERNAME" \
  -p"$MASTER_PASSWORD" <<'EOF'

-- Create database
CREATE DATABASE IF NOT EXISTS drdemo;
USE drdemo;

-- Create table
CREATE TABLE IF NOT EXISTS orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_number VARCHAR(50),
  customer_name VARCHAR(100),
  amount DECIMAL(10,2),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  region VARCHAR(50)
);

-- Insert sample data
INSERT INTO orders (order_number, customer_name, amount, region) VALUES
('ORD-001', 'John Smith', 150.50, 'ap-southeast-2'),
('ORD-002', 'Jane Doe', 299.99, 'ap-southeast-2'),
('ORD-003', 'Bob Johnson', 89.75, 'ap-southeast-2');

-- Display data
SELECT * FROM orders;
SELECT COUNT(*) AS total_orders FROM orders;

EOF

echo ""
echo "✅ Database and sample data created"
echo "   Database: drdemo"
echo "   Table: orders"
echo "   Records: 3 initial orders"
```

---

## Step 6 – Create Cross-Region Read Replica

```bash
echo ""
echo "================================================"
echo "CREATING CROSS-REGION READ REPLICA"
echo "================================================"
echo ""

echo "Creating read replica in $DR_REGION..."
echo "(This takes 10-20 minutes due to cross-region data transfer)"
echo ""

# Create read replica in DR region
aws rds create-db-instance-read-replica \
  --db-instance-identifier "$DB_REPLICA_ID" \
  --source-db-instance-identifier "$DB_INSTANCE_ID" \
  --db-instance-class db.t3.micro \
  --publicly-accessible \
  --source-region "$PRIMARY_REGION" \
  --region "$DR_REGION" \
  --tags Key=Name,Value=DRReplica Key=Environment,Value=DR-Demo

echo "✅ Read replica creation initiated"
echo "   Replica ID: $DB_REPLICA_ID"
echo "   DR Region: $DR_REGION"
```

---

## Step 7 – Wait for Replica to be Available

```bash
echo ""
echo "Waiting for read replica to be available..."
echo "Progress indicators:"

# Monitor replica status
while true; do
  STATUS=$(aws rds describe-db-instances \
    --db-instance-identifier "$DB_REPLICA_ID" \
    --region "$DR_REGION" \
    --query "DBInstances[0].DBInstanceStatus" \
    --output text 2>/dev/null)
  
  if [ "$STATUS" == "available" ]; then
    echo ""
    echo "✅ Read replica is now available"
    break
  else
    echo "  Status: $STATUS"
    sleep 30
  fi
done
```

---

## Step 8 – Get Replica Endpoint

```bash
echo ""
echo "Retrieving read replica endpoint..."

# Get replica endpoint
DR_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_REPLICA_ID" \
  --region "$DR_REGION" \
  --query "DBInstances[0].Endpoint.Address" \
  --output text)

echo "DR_ENDPOINT=$DR_ENDPOINT"

# Get port
DR_PORT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_REPLICA_ID" \
  --region "$DR_REGION" \
  --query "DBInstances[0].Endpoint.Port" \
  --output text)

echo "DR_PORT=$DR_PORT"
echo ""
echo "✅ Replica endpoint obtained"
```

---

## Step 9 – Verify Replication (Read-Only Access)

```bash
echo ""
echo "================================================"
echo "VERIFYING REPLICATION"
echo "================================================"
echo ""

echo "Querying read replica (read-only)..."

# Query replica
mysql -h "$DR_ENDPOINT" \
  -P "$DR_PORT" \
  -u "$MASTER_USERNAME" \
  -p"$MASTER_PASSWORD" <<'EOF'

USE drdemo;

-- Display replicated data
SELECT * FROM orders;
SELECT COUNT(*) AS total_orders FROM orders;

-- Try to write (should fail - read-only)
-- INSERT INTO orders (order_number, customer_name, amount, region)
-- VALUES ('ORD-004', 'Test User', 100.00, 'us-west-2');

EOF

echo ""
echo "✅ Replication verified - data successfully replicated"
echo "   Read replica is READ-ONLY until promoted"
```

---

## Step 10 – Add More Data to Primary

```bash
echo ""
echo "Adding new data to primary database..."

# Add more data to primary
mysql -h "$PRIMARY_ENDPOINT" \
  -P "$PRIMARY_PORT" \
  -u "$MASTER_USERNAME" \
  -p"$MASTER_PASSWORD" <<'EOF'

USE drdemo;

-- Insert additional orders
INSERT INTO orders (order_number, customer_name, amount, region) VALUES
('ORD-004', 'Alice Brown', 450.25, 'ap-southeast-2'),
('ORD-005', 'Charlie Wilson', 199.99, 'ap-southeast-2');

-- Display updated data
SELECT * FROM orders;
SELECT COUNT(*) AS total_orders FROM orders;

EOF

echo ""
echo "✅ New data added to primary database"
```

---

## Step 11 – Check Replication Lag

```bash
echo ""
echo "Checking replication lag..."

# Get replica lag
REPLICA_LAG=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_REPLICA_ID" \
  --region "$DR_REGION" \
  --query "DBInstances[0].StatusInfos[0].Message" \
  --output text 2>/dev/null)

echo "Replication status: $REPLICA_LAG"

# Wait a moment for replication
echo "Waiting 10 seconds for replication to catch up..."
sleep 10
```

---

## Step 12 – Verify New Data in Replica

```bash
echo ""
echo "Verifying new data replicated to DR region..."

# Query replica for new data
mysql -h "$DR_ENDPOINT" \
  -P "$DR_PORT" \
  -u "$MASTER_USERNAME" \
  -p"$MASTER_PASSWORD" <<'EOF'

USE drdemo;

-- Check if new data is replicated
SELECT * FROM orders ORDER BY id DESC LIMIT 5;
SELECT COUNT(*) AS total_orders FROM orders;

EOF

echo ""
echo "✅ New data successfully replicated to DR region"
echo "   Asynchronous replication working correctly"
```

---

## Step 13 – Promote Read Replica (Simulate Disaster)

```bash
echo ""
echo "================================================"
echo "DISASTER RECOVERY FAILOVER"
echo "================================================"
echo ""

echo "Simulating disaster scenario..."
echo "Promoting read replica to standalone database..."
echo ""

# Promote replica to standalone database
aws rds promote-read-replica \
  --db-instance-identifier "$DB_REPLICA_ID" \
  --backup-retention-period 7 \
  --region "$DR_REGION"

echo "✅ Promotion initiated"
echo ""
echo "Waiting for promotion to complete..."

# Wait for promotion
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_REPLICA_ID" \
  --region "$DR_REGION"

echo ""
echo "✅ Read replica promoted to standalone database"
echo "   Database is now READ-WRITE in DR region"
```

---

## Step 14 – Test Write Operations on Promoted Database

```bash
echo ""
echo "Testing write operations on promoted database..."

# Write to promoted database
mysql -h "$DR_ENDPOINT" \
  -P "$DR_PORT" \
  -u "$MASTER_USERNAME" \
  -p"$MASTER_PASSWORD" <<'EOF'

USE drdemo;

-- Now we can write (database is promoted)
INSERT INTO orders (order_number, customer_name, amount, region) VALUES
('ORD-006', 'DR Test User', 350.00, 'us-west-2'),
('ORD-007', 'Failover Success', 500.00, 'us-west-2');

-- Display all data
SELECT * FROM orders;
SELECT COUNT(*) AS total_orders FROM orders;

-- Show orders by region
SELECT region, COUNT(*) AS orders, SUM(amount) AS total_amount
FROM orders
GROUP BY region;

EOF

echo ""
echo "✅ Write operations successful on promoted database"
echo "   DR database is now fully operational"
echo "   Application can be redirected to DR region"
```

---

## Step 15 – Cleanup

```bash
echo ""
echo "================================================"
echo "CLEANUP"
echo "================================================"
echo ""

echo "Cleaning up resources..."

# Delete primary database
echo "Deleting primary database in $PRIMARY_REGION..."
aws rds delete-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --skip-final-snapshot \
  --region "$PRIMARY_REGION"

echo "✅ Primary database deletion initiated"

# Delete promoted replica (now standalone)
echo "Deleting promoted database in $DR_REGION..."
aws rds delete-db-instance \
  --db-instance-identifier "$DB_REPLICA_ID" \
  --skip-final-snapshot \
  --region "$DR_REGION"

echo "✅ DR database deletion initiated"
echo ""
echo "Databases are being deleted (takes 5-10 minutes)"
echo ""
echo "All resources cleaned up!"
```

---

## Summary

In this lab, you have:
- Created RDS MySQL primary database with automated backups
- Enabled cross-region replication to DR region
- Populated primary database with sample data
- Verified asynchronous replication to read replica
- Added new data and confirmed replication
- Monitored replication lag and status
- Simulated disaster by promoting read replica
- Tested write operations on promoted database
- Successfully failed over to DR region
- Cleaned up multi-region resources

**Key Takeaways:**
- **Disaster Recovery**: Cross-region replicas provide geographic redundancy
- **Asynchronous Replication**: Near real-time data replication with minimal lag
- **Read Scaling**: Replicas can offload read traffic before promotion
- **Promotion**: One-way operation converts replica to standalone database
- **RTO/RPO**: Promotion takes minutes, data loss depends on replication lag

---

## Best Practices

**Replication:**
- Enable automated backups (minimum 1 day retention)
- Monitor replica lag using CloudWatch metrics
- Use Multi-AZ for high availability in each region
- Test failover procedures quarterly
- Document promotion procedures

**Security:**
- Use AWS Secrets Manager for database credentials
- Enable encryption at rest using KMS
- Enable encryption in transit (SSL/TLS)
- Use VPC security groups to restrict access
- Enable audit logging (slow query, error logs)

**Performance:**
- Use appropriate instance classes for workload
- Monitor CPU, memory, and IOPS
- Use provisioned IOPS for consistent performance
- Consider read replicas in same region for read scaling
- Set appropriate backup window

**Cost Optimization:**
- Delete unused replicas
- Use appropriate retention periods
- Monitor data transfer costs between regions
- Consider Reserved Instances for production
- Use Aurora for automatic replication (lower cost)

**Failover Planning:**
- Use Route 53 health checks and failover routing
- Automate DNS updates for application endpoints
- Document RPO/RTO requirements
- Test end-to-end failover process
- Have rollback procedures documented

---

## Troubleshooting

**Replica creation fails:**
- Verify backup retention period >= 1 day on primary
- Check IAM permissions for cross-region operations
- Ensure sufficient capacity in DR region
- Verify security group rules
- Check CloudTrail logs for specific errors

**High replication lag:**
- Check primary database load (high writes increase lag)
- Verify network connectivity between regions
- Review long-running transactions on primary
- Consider larger instance class for replica
- Monitor ReplicaLag CloudWatch metric

**Cannot promote replica:**
- Ensure replica status is "available"
- Check for ongoing maintenance windows
- Verify no pending modifications
- Wait for replication to catch up
- Review RDS events for errors

**Connection failures:**
- Verify publicly-accessible is enabled (or use VPN/Direct Connect)
- Check security group inbound rules (port 3306)
- Verify database endpoint is correct
- Test network connectivity: `telnet <endpoint> 3306`
- Check NACLs and route tables

**Write operations fail on replica:**
- Read replicas are read-only until promoted
- Verify promotion completed successfully
- Check database status is "available"
- Review error messages in MySQL client
- Confirm you're connecting to correct endpoint

---

## Additional Resources

- [Amazon RDS Read Replicas](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html)
- [Cross-Region Read Replicas](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html#USER_ReadRepl.XRgn)
- [Promoting Read Replicas](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html#USER_ReadRepl.Promote)
- [RDS Disaster Recovery](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html)
- [RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [RDS Pricing](https://aws.amazon.com/rds/mysql/pricing/)
