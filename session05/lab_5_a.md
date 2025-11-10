# Lab 5.A: Amazon RDS - Relational Database Setup and Management

## Overview
This lab introduces Amazon Relational Database Service (RDS), a managed database service that simplifies database administration. You'll learn how to launch RDS instances, configure security, perform backups, and implement high availability with Multi-AZ deployments. RDS supports multiple database engines including MySQL, PostgreSQL, Oracle, and SQL Server.

## Objectives
- Launch and configure RDS database instances
- Implement security best practices for database access
- Configure automated backups and snapshots
- Set up Multi-AZ deployments for high availability
- Monitor database performance with CloudWatch
- Connect to RDS from EC2 instances
- Understand RDS pricing and cost optimization

## Requirements
- AWS account with RDS and EC2 permissions
- Completed VPC labs (Lab 3.A recommended)
- Basic SQL knowledge
- MySQL or PostgreSQL client software
- Understanding of relational database concepts

## Steps

### Step 1: Create DB Subnet Group
1. Navigate to RDS console
2. Click "Subnet groups" → Create DB subnet group
3. Configure:
   - Name: `lab-db-subnet-group`
   - Description: "Subnet group for RDS lab"
   - VPC: Select your VPC (or default)
   - Add subnets: Select at least 2 subnets in different AZs
4. Create subnet group

### Step 2: Create Security Group for RDS
1. Navigate to EC2 → Security Groups
2. Create security group:
   - Name: `rds-mysql-sg`
   - Description: "Security group for MySQL RDS"
   - VPC: Same as DB subnet group
3. Inbound rules:
   - Type: MySQL/Aurora (3306)
   - Source: Security group of EC2 instances (or VPC CIDR)
4. Create security group

### Step 3: Launch RDS MySQL Instance
1. Navigate to RDS → Databases
2. Click "Create database"
3. Choose database creation method: Standard create
4. Engine options:
   - Engine type: MySQL
   - Version: Latest MySQL 8.0
5. Templates: Free tier (for learning)
6. Settings:
   - DB instance identifier: `lab-mysql-db`
   - Master username: `admin`
   - Master password: Create strong password (save securely)
7. DB instance class: db.t3.micro (Free tier)
8. Storage:
   - Storage type: General Purpose SSD (gp3)
   - Allocated storage: 20 GB
   - Enable storage autoscaling: Yes
   - Maximum storage threshold: 100 GB
9. Connectivity:
   - VPC: Your VPC
   - DB subnet group: `lab-db-subnet-group`
   - Public access: No
   - VPC security group: `rds-mysql-sg`
   - Availability Zone: No preference
10. Database authentication: Password authentication
11. Additional configuration:
    - Initial database name: `labdb`
    - Backup retention: 7 days
    - Enable automatic backups
    - Backup window: Choose time
    - Enable encryption: Yes (default KMS key)
    - Enable Enhanced Monitoring: Optional
12. Create database
13. Wait for status to show "Available" (5-10 minutes)

### Step 4: Launch EC2 Instance for Database Access
1. Launch EC2 instance:
   - AMI: Amazon Linux 2023
   - Instance type: t2.micro
   - Network: Same VPC as RDS
   - Subnet: Public subnet
   - Auto-assign public IP: Enable
   - Security group: Allow SSH from My IP
2. Connect to instance via SSH

### Step 5: Install MySQL Client and Connect
1. Install MySQL client on EC2:
   ```bash
   sudo yum update -y
   sudo yum install mysql -y
   ```

2. Get RDS endpoint from console:
   - Navigate to RDS → Databases → `lab-mysql-db`
   - Copy endpoint address (e.g., `lab-mysql-db.xxxxxx.region.rds.amazonaws.com`)

3. Connect to RDS instance:
   ```bash
   mysql -h lab-mysql-db.xxxxxx.region.rds.amazonaws.com \
         -u admin -p
   ```
   - Enter master password when prompted

4. Verify connection and explore:
   ```sql
   SHOW DATABASES;
   USE labdb;
   CREATE TABLE users (
     id INT AUTO_INCREMENT PRIMARY KEY,
     username VARCHAR(50),
     email VARCHAR(100),
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   INSERT INTO users (username, email) VALUES ('testuser', 'test@example.com');
   SELECT * FROM users;
   ```

### Step 6: Configure Automated Backups
1. Navigate to RDS instance → Maintenance & backups
2. Review automated backup settings:
   - Backup retention period: 7 days
   - Backup window: Configured during creation
3. Modify backup retention if needed:
   - Select instance → Modify
   - Change backup retention period
   - Apply immediately or during maintenance window

### Step 7: Create Manual Snapshot
1. Select RDS instance
2. Actions → Take snapshot
3. Configure:
   - Snapshot name: `lab-mysql-snapshot-manual`
4. Create snapshot
5. Monitor snapshot progress in Snapshots section
6. Once available, practice restoring:
   - Select snapshot → Actions → Restore snapshot
   - Review settings (don't actually restore unless needed)
   - Cancel to avoid creating duplicate instance

### Step 8: Enable Multi-AZ Deployment
1. Select RDS instance → Modify
2. Find "Availability & durability" section
3. Change to Multi-AZ deployment:
   - Create a standby instance: Yes
4. Continue through modification wizard
5. Apply: During next maintenance window (or immediately for testing)
6. Wait for modification to complete
7. Verify Multi-AZ status in instance details

### Step 9: Monitor Database Performance
1. Navigate to RDS instance → Monitoring tab
2. Review CloudWatch metrics:
   - CPU Utilization
   - Database Connections
   - Read/Write IOPS
   - Free Storage Space
   - Read/Write Latency
3. Create CloudWatch alarm:
   - Navigate to CloudWatch → Alarms
   - Create alarm for high CPU:
     - Metric: RDS → Per-Database Metrics → CPUUtilization
     - Threshold: Greater than 80%
     - Actions: SNS notification (optional)

### Step 10: Test Database Performance
1. From EC2 instance, run load test:
   ```bash
   mysql -h lab-mysql-db.xxxxxx.region.rds.amazonaws.com -u admin -p
   ```

2. Create test data:
   ```sql
   USE labdb;
   CREATE TABLE load_test (
     id INT AUTO_INCREMENT PRIMARY KEY,
     data VARCHAR(1000)
   );
   
   DELIMITER $$
   CREATE PROCEDURE insert_test_data()
   BEGIN
     DECLARE i INT DEFAULT 0;
     WHILE i < 10000 DO
       INSERT INTO load_test (data) VALUES (MD5(RAND()));
       SET i = i + 1;
     END WHILE;
   END$$
   DELIMITER ;
   
   CALL insert_test_data();
   ```

3. Monitor metrics in RDS console

### Step 11: Configure Read Replica (Optional)
1. Select RDS instance
2. Actions → Create read replica
3. Configure:
   - DB instance identifier: `lab-mysql-read-replica`
   - Region: Same region or different
   - Instance class: Can be smaller than primary
4. Create read replica
5. Test read operations from replica endpoint

## Validation
- [ ] RDS MySQL instance created and running
- [ ] DB subnet group configured across multiple AZs
- [ ] Security group properly configured
- [ ] Successfully connected to database from EC2
- [ ] Created database tables and inserted data
- [ ] Automated backups configured
- [ ] Manual snapshot created successfully
- [ ] Multi-AZ deployment enabled
- [ ] CloudWatch metrics visible and monitoring
- [ ] Read replica created (optional)

## Cleanup
1. Delete read replica (if created):
   - Select replica → Actions → Delete
   - Skip final snapshot for lab
2. Delete RDS instance:
   - Select `lab-mysql-db` → Actions → Delete
   - Uncheck "Create final snapshot" (lab only)
   - Acknowledge deletion
   - Type "delete me" to confirm
3. Delete manual snapshots:
   - Navigate to Snapshots
   - Select and delete
4. Delete automated backups:
   - May be deleted automatically after retention period
5. Terminate EC2 instance
6. Delete security groups and DB subnet group
7. Verify all resources removed

## Summary
In this lab, you learned how to deploy and manage relational databases using Amazon RDS. You configured automated backups, implemented Multi-AZ deployments for high availability, monitored performance metrics, and connected applications to your database. RDS eliminates the operational burden of database management while providing enterprise-grade reliability and performance.

**Key Takeaways:**
- RDS automates backups, patching, and maintenance
- Multi-AZ provides automatic failover for high availability
- Never expose RDS publicly; use private subnets
- Security groups control database network access
- Automated backups enable point-in-time recovery
- Read replicas improve read scalability
- Always encrypt databases for sensitive data
- Monitor performance metrics to optimize costs
- Choose appropriate instance class based on workload
