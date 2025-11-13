# Lab 14.D: Disaster Recovery - Pilot Light Strategy

## Overview
This lab demonstrates the Pilot Light disaster recovery strategy, where minimal infrastructure runs in a DR region with a replicated database. During a disaster, you quickly scale up compute resources and promote the database replica. You'll create a primary environment, set up a pilot light DR environment with RDS read replica, simulate a disaster, perform failover, and verify recovery.

---

## Objectives
- Understand Pilot Light DR architecture
- Create primary RDS database and application server
- Set up DR region with read replica
- Configure minimal compute infrastructure in DR region
- Simulate disaster scenario
- Promote read replica to standalone database
- Scale up DR compute resources
- Test application failover
- Clean up multi-region resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for EC2, RDS, Systems Manager
- MySQL client installed
- Regions: ap-southeast-2 (primary), us-west-2 (DR)
- Understanding of DR strategies

---

## Architecture

```
Pilot Light DR Strategy:

Normal Operations:
  Primary Region (ap-southeast-2)
  ├─ EC2 Web Server (Running)
  ├─ RDS MySQL Primary (Running)
  └─ Full production workload
          ↓
    Async Replication
          ↓
  DR Region (us-west-2)
  ├─ EC2 Web Server (STOPPED - Pilot Light)
  ├─ RDS Read Replica (Running)
  └─ Minimal infrastructure (cost-efficient)

Disaster Event:
  1. Promote RDS replica to standalone
  2. Start EC2 instances in DR region
  3. Update DNS/Route 53 to DR region
  4. Scale up resources as needed
  
Recovery Time: 10-30 minutes
Recovery Point: Minutes (replication lag)
Cost: Low (only replica + stopped instances)
```

---

## Step 1 – Set Variables

```bash
# Set regions
PRIMARY_REGION="ap-southeast-2"
DR_REGION="us-west-2"

echo "PRIMARY_REGION=$PRIMARY_REGION"
echo "DR_REGION=$DR_REGION"

# Set database configuration
DB_INSTANCE_PRIMARY="pilotlight-primary-db"
DB_INSTANCE_DR="pilotlight-dr-replica"
DB_USERNAME="admin"
DB_PASSWORD="SecurePass123!"

echo "DB_INSTANCE_PRIMARY=$DB_INSTANCE_PRIMARY"
echo "DB_INSTANCE_DR=$DB_INSTANCE_DR"
echo "DB_USERNAME=$DB_USERNAME"

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)

echo "ACCOUNT_ID=$ACCOUNT_ID"
echo ""
echo "================================================"
echo "PILOT LIGHT DISASTER RECOVERY"
echo "================================================"
```

---

## Step 2 – Create Primary RDS Database

```bash
echo ""
echo "Creating primary RDS database in $PRIMARY_REGION..."

# Create RDS MySQL instance
aws rds create-db-instance \
  --db-instance-identifier "$DB_INSTANCE_PRIMARY" \
  --engine mysql \
  --engine-version "8.0.35" \
  --db-instance-class db.t3.micro \
  --allocated-storage 20 \
  --storage-type gp2 \
  --master-username "$DB_USERNAME" \
  --master-user-password "$DB_PASSWORD" \
  --backup-retention-period 7 \
  --publicly-accessible \
  --no-multi-az \
  --region "$PRIMARY_REGION" \
  --tags Key=Name,Value=PrimaryDatabase Key=Environment,Value=Production

echo "✅ Primary RDS instance creation initiated"
echo "   Instance: $DB_INSTANCE_PRIMARY"
echo "   Engine: MySQL 8.0.35"
echo ""
echo "Waiting for database to be available (5-10 minutes)..."

# Wait for instance to be available
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_INSTANCE_PRIMARY" \
  --region "$PRIMARY_REGION"

echo "✅ Primary database is ready"
```

---

## Step 3 – Get Primary Database Endpoint

```bash
echo ""
echo "Retrieving primary database endpoint..."

# Get endpoint
PRIMARY_DB_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_PRIMARY" \
  --region "$PRIMARY_REGION" \
  --query "DBInstances[0].Endpoint.Address" \
  --output text)

echo "PRIMARY_DB_ENDPOINT=$PRIMARY_DB_ENDPOINT"
echo ""
echo "✅ Primary database endpoint obtained"
```

---

## Step 4 – Create Sample Application Database

```bash
echo ""
echo "Creating application database and sample data..."

# Create database and populate with sample data
mysql -h "$PRIMARY_DB_ENDPOINT" \
  -u "$DB_USERNAME" \
  -p"$DB_PASSWORD" <<'EOF'

-- Create application database
CREATE DATABASE IF NOT EXISTS webapp;
USE webapp;

-- Create users table
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL,
  email VARCHAR(100) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  region VARCHAR(50)
);

-- Insert sample data
INSERT INTO users (username, email, region) VALUES
('john_doe', 'john@example.com', 'ap-southeast-2'),
('jane_smith', 'jane@example.com', 'ap-southeast-2'),
('bob_wilson', 'bob@example.com', 'ap-southeast-2'),
('alice_brown', 'alice@example.com', 'ap-southeast-2');

-- Create sessions table
CREATE TABLE IF NOT EXISTS sessions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT,
  session_token VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Show tables and data
SHOW TABLES;
SELECT COUNT(*) AS total_users FROM users;
SELECT * FROM users;

EOF

echo ""
echo "✅ Application database created with sample data"
echo "   Database: webapp"
echo "   Tables: users, sessions"
echo "   Sample users: 4"
```

---

## Step 5 – Launch Primary Application Server

```bash
echo ""
echo "================================================"
echo "CREATING PRIMARY INFRASTRUCTURE"
echo "================================================"
echo ""

# Get latest Amazon Linux 2 AMI
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" \
            "Name=state,Values=available" \
  --region "$PRIMARY_REGION" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

echo "AMI_ID=$AMI_ID"
echo ""

echo "Launching primary application server..."

# Launch EC2 instance
PRIMARY_INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --region "$PRIMARY_REGION" \
  --tag-specifications "ResourceType=instance,Tags=[
    {Key=Name,Value=PrimaryWebServer},
    {Key=Environment,Value=Production},
    {Key=Role,Value=WebServer}
  ]" \
  --user-data "#!/bin/bash
yum update -y
yum install -y httpd mysql
systemctl start httpd
systemctl enable httpd
echo '<h1>Primary Web Server - ap-southeast-2</h1>' > /var/www/html/index.html
" \
  --query "Instances[0].InstanceId" \
  --output text)

echo "PRIMARY_INSTANCE_ID=$PRIMARY_INSTANCE_ID"

# Wait for instance
echo "Waiting for instance to start..."
aws ec2 wait instance-running \
  --instance-ids "$PRIMARY_INSTANCE_ID" \
  --region "$PRIMARY_REGION"

echo "✅ Primary application server running"
```

---

## Step 6 – Create Cross-Region Read Replica (DR)

```bash
echo ""
echo "================================================"
echo "SETTING UP DR REGION (PILOT LIGHT)"
echo "================================================"
echo ""

echo "Creating cross-region read replica in $DR_REGION..."
echo "(This takes 10-20 minutes for cross-region replication)"
echo ""

# Create read replica in DR region
aws rds create-db-instance-read-replica \
  --db-instance-identifier "$DB_INSTANCE_DR" \
  --source-db-instance-identifier "$DB_INSTANCE_PRIMARY" \
  --db-instance-class db.t3.micro \
  --publicly-accessible \
  --source-region "$PRIMARY_REGION" \
  --region "$DR_REGION" \
  --tags Key=Name,Value=DRReplica Key=Environment,Value=DR

echo "✅ Read replica creation initiated"
echo "   Replica: $DB_INSTANCE_DR"
echo "   Region: $DR_REGION"
echo ""
echo "Waiting for replica to be available..."

# Wait for replica
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_INSTANCE_DR" \
  --region "$DR_REGION"

echo "✅ DR database replica is ready"
```

---

## Step 7 – Get DR Database Endpoint

```bash
echo ""
echo "Retrieving DR database endpoint..."

# Get DR endpoint
DR_DB_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_DR" \
  --region "$DR_REGION" \
  --query "DBInstances[0].Endpoint.Address" \
  --output text)

echo "DR_DB_ENDPOINT=$DR_DB_ENDPOINT"
echo ""
echo "✅ DR database endpoint obtained"
```

---

## Step 8 – Verify Data Replication

```bash
echo ""
echo "Verifying data replication to DR region..."

# Query DR replica
mysql -h "$DR_DB_ENDPOINT" \
  -u "$DB_USERNAME" \
  -p"$DB_PASSWORD" <<'EOF'

USE webapp;

-- Verify tables exist
SHOW TABLES;

-- Verify data replicated
SELECT COUNT(*) AS total_users FROM users;
SELECT * FROM users;

EOF

echo ""
echo "✅ Data successfully replicated to DR region"
echo "   DR database is read-only until promoted"
```

---

## Step 9 – Create Pilot Light EC2 Instance (STOPPED)

```bash
echo ""
echo "Creating pilot light EC2 instance in DR region..."

# Get AMI for DR region
DR_AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" \
            "Name=state,Values=available" \
  --region "$DR_REGION" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

echo "DR_AMI_ID=$DR_AMI_ID"
echo ""

# Launch instance in DR region
DR_INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$DR_AMI_ID" \
  --instance-type t2.micro \
  --region "$DR_REGION" \
  --tag-specifications "ResourceType=instance,Tags=[
    {Key=Name,Value=DR-PilotLight-WebServer},
    {Key=Environment,Value=DR},
    {Key=Role,Value=PilotLight}
  ]" \
  --user-data "#!/bin/bash
yum update -y
yum install -y httpd mysql
systemctl start httpd
systemctl enable httpd
echo '<h1>DR Web Server - us-west-2 (Pilot Light)</h1>' > /var/www/html/index.html
" \
  --query "Instances[0].InstanceId" \
  --output text)

echo "DR_INSTANCE_ID=$DR_INSTANCE_ID"

# Wait for instance to start
echo "Waiting for instance to start..."
aws ec2 wait instance-running \
  --instance-ids "$DR_INSTANCE_ID" \
  --region "$DR_REGION"

echo "✅ DR instance started"
echo ""

# Stop the instance (Pilot Light strategy)
echo "Stopping DR instance (Pilot Light - saves costs)..."
aws ec2 stop-instances \
  --instance-ids "$DR_INSTANCE_ID" \
  --region "$DR_REGION"

# Wait for instance to stop
aws ec2 wait instance-stopped \
  --instance-ids "$DR_INSTANCE_ID" \
  --region "$DR_REGION"

echo "✅ DR instance stopped (Pilot Light mode)"
echo "   Instance will be started only during disaster"
echo "   Cost: ~$0/hour (stopped), ~$0.012/hour (running)"
```

---

## Step 10 – Add More Data to Primary

```bash
echo ""
echo "Adding more data to primary database..."

# Add more data to test replication
mysql -h "$PRIMARY_DB_ENDPOINT" \
  -u "$DB_USERNAME" \
  -p"$DB_PASSWORD" <<'EOF'

USE webapp;

-- Add more users
INSERT INTO users (username, email, region) VALUES
('charlie_davis', 'charlie@example.com', 'ap-southeast-2'),
('diana_evans', 'diana@example.com', 'ap-southeast-2');

-- Show updated count
SELECT COUNT(*) AS total_users FROM users;

EOF

echo ""
echo "✅ New data added to primary"
echo ""
echo "Waiting 30 seconds for replication..."
sleep 30

# Verify replication
mysql -h "$DR_DB_ENDPOINT" \
  -u "$DB_USERNAME" \
  -p"$DB_PASSWORD" <<'EOF'

USE webapp;
SELECT COUNT(*) AS total_users FROM users;

EOF

echo ""
echo "✅ New data replicated to DR region"
```

---

## Step 11 – Simulate Disaster Event

```bash
echo ""
echo "================================================"
echo "DISASTER RECOVERY SCENARIO"
echo "================================================"
echo ""

echo "⚠️  SIMULATING DISASTER IN PRIMARY REGION"
echo ""
echo "Scenario: Primary region (ap-southeast-2) has failed"
echo "Action: Activating DR environment in us-west-2"
echo ""
echo "DR Activation Steps:"
echo "  1. Promote DR database replica to standalone"
echo "  2. Start pilot light EC2 instances"
echo "  3. Update application configuration"
echo "  4. Update DNS to point to DR region"
echo ""
read -p "Press Enter to begin DR activation..."
```

---

## Step 12 – Promote DR Database Replica

```bash
echo ""
echo "Step 1: Promoting DR database replica..."

# Promote read replica
aws rds promote-read-replica \
  --db-instance-identifier "$DB_INSTANCE_DR" \
  --backup-retention-period 7 \
  --region "$DR_REGION"

echo "✅ Promotion initiated"
echo ""
echo "Waiting for promotion to complete (2-5 minutes)..."

# Wait for promotion
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_INSTANCE_DR" \
  --region "$DR_REGION"

echo ""
echo "✅ DR database promoted to standalone instance"
echo "   Database is now READ-WRITE in DR region"
```

---

## Step 13 – Start Pilot Light EC2 Instances

```bash
echo ""
echo "Step 2: Starting pilot light EC2 instances..."

# Start DR instance
aws ec2 start-instances \
  --instance-ids "$DR_INSTANCE_ID" \
  --region "$DR_REGION"

echo "✅ Starting DR instance"
echo ""
echo "Waiting for instance to be running..."

# Wait for instance
aws ec2 wait instance-running \
  --instance-ids "$DR_INSTANCE_ID" \
  --region "$DR_REGION"

echo ""
echo "✅ DR web server is now running"

# Get instance public IP
DR_INSTANCE_IP=$(aws ec2 describe-instances \
  --instance-ids "$DR_INSTANCE_ID" \
  --region "$DR_REGION" \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text)

echo "DR_INSTANCE_IP=$DR_INSTANCE_IP"
```

---

## Step 14 – Test Write Operations on DR Database

```bash
echo ""
echo "Step 3: Testing write operations on promoted database..."

# Test writes to promoted database
mysql -h "$DR_DB_ENDPOINT" \
  -u "$DB_USERNAME" \
  -p"$DB_PASSWORD" <<'EOF'

USE webapp;

-- Now we can write (database is promoted)
INSERT INTO users (username, email, region) VALUES
('dr_test_user', 'drtest@example.com', 'us-west-2'),
('failover_success', 'success@example.com', 'us-west-2');

-- Display all users
SELECT * FROM users ORDER BY id DESC LIMIT 5;
SELECT COUNT(*) AS total_users FROM users;

-- Show users by region
SELECT region, COUNT(*) AS user_count FROM users GROUP BY region;

EOF

echo ""
echo "✅ Write operations successful on DR database"
echo "   Database is fully operational in DR region"
```

---

## Step 15 – Verify DR Environment Status

```bash
echo ""
echo "================================================"
echo "DR ENVIRONMENT STATUS"
echo "================================================"
echo ""

# Check database status
echo "Database Status:"
aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_DR" \
  --region "$DR_REGION" \
  --query "DBInstances[0].{
    Status:DBInstanceStatus,
    Endpoint:Endpoint.Address,
    MultiAZ:MultiAZ,
    ReadReplica:ReadReplicaSourceDBInstanceIdentifier
  }" \
  --output table

echo ""

# Check EC2 status
echo "Web Server Status:"
aws ec2 describe-instances \
  --instance-ids "$DR_INSTANCE_ID" \
  --region "$DR_REGION" \
  --query "Reservations[0].Instances[0].{
    State:State.Name,
    PublicIP:PublicIpAddress,
    PrivateIP:PrivateIpAddress,
    Type:InstanceType
  }" \
  --output table

echo ""
echo "✅ DR environment fully operational"
echo ""
echo "Recovery Summary:"
echo "  - Database: Promoted and accepting writes"
echo "  - Web Server: Running and ready for traffic"
echo "  - Total Users: 8 (6 from primary + 2 from DR)"
echo "  - Recovery Time: ~10-15 minutes"
echo "  - Data Loss: Minimal (last replication lag)"
```

---

## Step 16 – Cleanup

```bash
echo ""
echo "================================================"
echo "CLEANUP"
echo "================================================"
echo ""

echo "Cleaning up resources..."

# Terminate primary instance
echo "Terminating primary instance..."
aws ec2 terminate-instances \
  --instance-ids "$PRIMARY_INSTANCE_ID" \
  --region "$PRIMARY_REGION" > /dev/null

echo "✅ Primary instance terminated"

# Terminate DR instance
echo "Terminating DR instance..."
aws ec2 terminate-instances \
  --instance-ids "$DR_INSTANCE_ID" \
  --region "$DR_REGION" > /dev/null

echo "✅ DR instance terminated"

# Wait for termination
sleep 30

# Delete primary database
echo "Deleting primary database..."
aws rds delete-db-instance \
  --db-instance-identifier "$DB_INSTANCE_PRIMARY" \
  --skip-final-snapshot \
  --region "$PRIMARY_REGION"

echo "✅ Primary database deletion initiated"

# Delete DR database
echo "Deleting DR database..."
aws rds delete-db-instance \
  --db-instance-identifier "$DB_INSTANCE_DR" \
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
- Created primary RDS database with sample application data
- Launched primary application server in production region
- Established cross-region read replica in DR region
- Created pilot light EC2 instance (kept stopped to save costs)
- Verified data replication between regions
- Simulated disaster scenario
- Promoted DR database replica to standalone instance
- Started pilot light compute resources
- Tested write operations on promoted database
- Verified complete DR environment activation
- Cleaned up multi-region resources

**Key Takeaways:**
- **Cost Efficient**: Minimal running infrastructure in DR region
- **Quick Recovery**: 10-30 minute RTO with proper preparation
- **Automated Replication**: Continuous async replication to DR
- **Promotion Process**: One-way operation to make replica standalone
- **Pilot Light Concept**: Keep minimal resources ready, scale on demand

---

## Best Practices

**Architecture:**
- Use Route 53 health checks for automatic failover
- Implement monitoring and alerting for replication lag
- Keep DR environment configuration identical to primary
- Document and automate failover procedures
- Test failover quarterly

**Database:**
- Monitor replication lag constantly
- Enable automated backups on both databases
- Use Multi-AZ in production for high availability
- Consider Aurora Global Database for faster replication
- Test database promotion procedures regularly

**Compute:**
- Use AMIs to capture application configuration
- Store application configuration in Parameter Store
- Use Auto Scaling Groups for automatic scaling
- Keep EBS volumes for data persistence
- Tag resources for easy identification

**DNS and Traffic:**
- Use Route 53 with health checks
- Set low TTL values (60 seconds) for DNS records
- Implement weighted routing for gradual cutover
- Test DNS failover before disaster
- Document DNS update procedures

**Cost Management:**
- Stop non-essential instances in DR region
- Use reserved instances for always-running resources
- Monitor cross-region data transfer costs
- Right-size DR instances based on expected load
- Use lifecycle policies for old backups

---

## Troubleshooting

**Replica promotion fails:**
- Verify replica status is "available"
- Check for ongoing maintenance windows
- Ensure no pending modifications
- Wait for replication lag to be zero
- Review RDS events for specific errors

**Cannot start pilot light instances:**
- Check instance state (should be stopped, not terminated)
- Verify IAM permissions for EC2 operations
- Check for service limits in DR region
- Review EC2 console for error messages
- Ensure instance type available in AZ

**High replication lag:**
- Check primary database load
- Monitor network connectivity
- Review long-running transactions
- Consider read replica scaling
- Check CloudWatch ReplicaLag metric

**Application connection failures:**
- Verify security group rules updated
- Check database endpoint is correct
- Ensure network ACLs allow traffic
- Test database connectivity manually
- Review application logs

**Write operations fail after promotion:**
- Confirm promotion completed successfully
- Check database status is "available"
- Verify no read-only mode enabled
- Review database parameter groups
- Check user permissions

---

## Additional Resources

- [AWS Disaster Recovery](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html)
- [Pilot Light Strategy](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/pilot-light.html)
- [RDS Read Replicas](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html)
- [Route 53 Failover](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover.html)
- [DR Testing Best Practices](https://aws.amazon.com/blogs/publicsector/rapidly-recover-mission-critical-systems-in-a-disaster/)
- [AWS Elastic Disaster Recovery](https://aws.amazon.com/disaster-recovery/)
