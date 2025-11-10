# Lab 5.B: RDS Performance Optimization and Parameter Groups

## Overview
This lab focuses on optimizing RDS database performance through parameter groups, option groups, and performance tuning. You'll learn how to configure database parameters, enable Performance Insights, use Enhanced Monitoring, and implement best practices for production RDS deployments.

## Objectives
- Create and configure custom DB parameter groups
- Implement database performance tuning
- Enable and use RDS Performance Insights
- Configure Enhanced Monitoring
- Optimize storage and I/O performance
- Implement connection pooling strategies
- Use database activity streams for auditing
- Understand query performance optimization

## Requirements
- Completed Lab 5.A or equivalent RDS knowledge
- Running RDS MySQL or PostgreSQL instance
- Understanding of database performance concepts
- Access to EC2 instance for testing
- SQL query optimization knowledge (helpful)

## Steps

### Step 1: Create Custom DB Parameter Group
1. Navigate to RDS → Parameter groups
2. Click "Create parameter group"
3. Configure:
   - Parameter group family: mysql8.0 (match your engine)
   - Type: DB Parameter Group
   - Group name: `custom-mysql-params`
   - Description: "Custom parameters for performance tuning"
4. Create parameter group
5. Select the parameter group → Edit parameters

### Step 2: Configure Performance Parameters
1. Modify key parameters for performance:
   
   **Connection and Buffer Settings:**
   - `max_connections`: 150 (increase from default)
   - `innodb_buffer_pool_size`: {DBInstanceClassMemory*3/4}
   - `max_allowed_packet`: 67108864 (64MB)
   
   **Query Cache (MySQL 5.7 only):**
   - `query_cache_size`: 0 (disable, use application caching instead)
   - `query_cache_type`: 0
   
   **Logging:**
   - `slow_query_log`: 1 (enable)
   - `long_query_time`: 2 (log queries > 2 seconds)
   - `log_queries_not_using_indexes`: 1
   
   **Binary Logging:**
   - `binlog_format`: ROW (for replication)
   
2. Save changes
3. Apply parameter group to RDS instance:
   - Select RDS instance → Modify
   - DB parameter group: `custom-mysql-params`
   - Apply immediately (or during maintenance window)
   - Note: Some parameters require instance reboot

### Step 3: Enable Performance Insights
1. Select RDS instance → Modify
2. Find "Performance Insights" section
3. Enable Performance Insights:
   - Enable: Yes
   - Retention period: 7 days (free tier)
   - KMS key: Default
4. Apply changes immediately
5. Wait for modification to complete

### Step 4: Explore Performance Insights Dashboard
1. Navigate to RDS instance → Performance Insights
2. Review dashboard sections:
   - **Database load:** Active sessions over time
   - **Top SQL:** Most resource-intensive queries
   - **Top wait events:** What queries are waiting on
   - **Top hosts:** Which clients are most active
3. Adjust time range and filters to analyze patterns
4. Identify slow queries for optimization

### Step 5: Enable Enhanced Monitoring
1. Select RDS instance → Modify
2. Find "Monitoring" section
3. Enable Enhanced Monitoring:
   - Enable: Yes
   - Granularity: 60 seconds (or 1 second for detailed monitoring)
   - Monitoring role: Create new or use existing
4. Apply changes
5. View Enhanced Monitoring metrics:
   - Navigate to Monitoring tab
   - View OS-level metrics:
     - CPU utilization by process
     - Memory usage
     - Disk I/O
     - Network throughput
     - Process list

### Step 6: Optimize Storage Performance
1. **Evaluate current I/O performance:**
   - Review CloudWatch metrics: ReadIOPS, WriteIOPS
   - Check ReadLatency, WriteLatency
   
2. **Modify storage type if needed:**
   - Select instance → Modify
   - Storage type options:
     - General Purpose (gp3): 3,000-16,000 IOPS
     - Provisioned IOPS (io1/io2): Up to 64,000 IOPS
   - For high I/O workloads, select Provisioned IOPS:
     - Storage type: io1
     - IOPS: 10,000 (example)
   - Note: io1 is more expensive but provides consistent performance

3. **Enable storage autoscaling:**
   - Enable storage autoscaling: Yes
   - Maximum storage threshold: Set based on growth expectations

### Step 7: Implement and Test Connection Pooling
1. Connect to EC2 instance
2. Install Python and MySQL connector:
   ```bash
   sudo yum install python3 python3-pip -y
   pip3 install mysql-connector-python
   ```

3. Create connection pooling test script:
   ```python
   # connection_pool_test.py
   import mysql.connector
   from mysql.connector import pooling
   import time
   
   db_config = {
       "host": "lab-mysql-db.xxxxxx.region.rds.amazonaws.com",
       "user": "admin",
       "password": "your-password",
       "database": "labdb"
   }
   
   # Create connection pool
   connection_pool = pooling.MySQLConnectionPool(
       pool_name="mypool",
       pool_size=10,
       pool_reset_session=True,
       **db_config
   )
   
   def execute_query():
       conn = connection_pool.get_connection()
       cursor = conn.cursor()
       cursor.execute("SELECT * FROM users LIMIT 10")
       results = cursor.fetchall()
       cursor.close()
       conn.close()
       return results
   
   # Test pool performance
   start = time.time()
   for i in range(100):
       execute_query()
   end = time.time()
   print(f"100 queries completed in {end-start:.2f} seconds")
   ```

4. Run test and monitor connections in Performance Insights

### Step 8: Analyze and Optimize Slow Queries
1. Connect to RDS instance:
   ```bash
   mysql -h lab-mysql-db.xxxxxx.region.rds.amazonaws.com -u admin -p
   ```

2. Create test table with indexes:
   ```sql
   USE labdb;
   
   CREATE TABLE products (
     id INT AUTO_INCREMENT PRIMARY KEY,
     name VARCHAR(200),
     category VARCHAR(100),
     price DECIMAL(10,2),
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     INDEX idx_category (category),
     INDEX idx_price (price)
   );
   
   -- Insert sample data
   INSERT INTO products (name, category, price)
   SELECT 
     CONCAT('Product ', n),
     CONCAT('Category ', MOD(n, 10)),
     ROUND(RAND() * 1000, 2)
   FROM (
     SELECT @row := @row + 1 AS n
     FROM (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3) t1,
          (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3) t2,
          (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3) t3,
          (SELECT @row := 0) t4
   ) numbers
   LIMIT 10000;
   ```

3. Analyze query performance:
   ```sql
   -- Bad query (no index)
   EXPLAIN SELECT * FROM products WHERE name LIKE '%Product%';
   
   -- Good query (uses index)
   EXPLAIN SELECT * FROM products WHERE category = 'Category 5';
   
   -- Check query execution time
   SET profiling = 1;
   SELECT * FROM products WHERE category = 'Category 5';
   SHOW PROFILES;
   ```

4. Review slow query log:
   ```sql
   -- Enable slow query log (if not already enabled via parameter group)
   -- View recent slow queries in CloudWatch Logs
   ```

### Step 9: Configure Database Activity Streams (Aurora Only)
**Note:** This feature is available for Aurora MySQL/PostgreSQL. For standard RDS, use CloudWatch Logs.

1. For Aurora instances:
   - Select cluster → Actions → Start activity stream
   - KMS key: Select key for encryption
   - Mode: Async (or Sync for stricter compliance)
   - Apply

2. For standard RDS:
   - Enable general log and slow query log
   - Export to CloudWatch Logs
   - Create log groups and streams

### Step 10: Implement Backup and Recovery Best Practices
1. **Test Point-in-Time Recovery:**
   - Note current time
   - Make database change:
     ```sql
     DELETE FROM users WHERE id > 0;
     ```
   - Restore to point before deletion:
     - Actions → Restore to point in time
     - Select time before deletion
     - New instance identifier: `lab-mysql-restored`
     - Restore

2. **Verify restoration:**
   - Connect to restored instance
   - Verify data is present

3. **Create cross-region snapshot:**
   - Take snapshot
   - Copy snapshot to another region
   - Verify snapshot in destination region

## Validation
- [ ] Custom parameter group created and applied
- [ ] Performance Insights enabled and accessible
- [ ] Enhanced Monitoring providing OS-level metrics
- [ ] Slow query log enabled and configured
- [ ] Connection pooling implemented and tested
- [ ] Query performance analyzed with EXPLAIN
- [ ] Storage type optimized for workload
- [ ] Point-in-time recovery tested successfully
- [ ] Cross-region snapshot created

## Cleanup
1. Delete restored instance (`lab-mysql-restored`)
2. Delete cross-region snapshots
3. Disable Performance Insights (if desired)
4. Disable Enhanced Monitoring
5. Revert to default parameter group or delete custom group
6. Delete main RDS instance
7. Delete CloudWatch log groups
8. Verify all resources removed

## Summary
In this lab, you optimized RDS database performance through custom parameter groups, Performance Insights, and Enhanced Monitoring. You learned how to identify and optimize slow queries, implement connection pooling, and configure storage for optimal I/O performance. These skills are essential for maintaining production-grade RDS deployments that meet performance and reliability requirements.

**Key Takeaways:**
- Parameter groups allow database engine customization
- Performance Insights identifies problematic queries quickly
- Enhanced Monitoring provides OS-level visibility
- Slow query log is essential for performance tuning
- Connection pooling reduces connection overhead
- Proper indexing dramatically improves query performance
- Storage type impacts I/O performance and cost
- Regular performance monitoring prevents issues
- Test backup and recovery procedures regularly
- Some parameter changes require instance reboot
