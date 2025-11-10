# Lab 6.B: DynamoDB Advanced Features and Best Practices

## Overview
This lab explores advanced DynamoDB features including Global Tables for multi-region replication, DynamoDB Accelerator (DAX) for caching, Point-in-Time Recovery, on-demand backups, and best practices for data modeling. You'll also learn cost optimization strategies and performance tuning techniques.

## Objectives
- Configure Global Tables for multi-region replication
- Implement DynamoDB Accelerator (DAX) for caching
- Enable Point-in-Time Recovery (PITR)
- Create and restore from backups
- Implement advanced data modeling patterns
- Optimize costs with capacity planning
- Use Time To Live (TTL) for automatic data expiration
- Implement best practices for partition key design

## Requirements
- Completed Lab 6.A or equivalent DynamoDB knowledge
- AWS account with access to multiple regions
- Understanding of caching concepts
- VPC with subnets for DAX cluster
- Advanced NoSQL data modeling knowledge

## Steps

### Step 1: Enable Point-in-Time Recovery (PITR)
1. Navigate to DynamoDB console
2. Create test table:
   - Name: `ProductCatalog`
   - Partition key: `productId` (String)
   - Capacity: On-demand
3. Select table → Backups tab
4. Point-in-time recovery section:
   - Click "Edit"
   - Enable point-in-time recovery
   - Save
5. Add sample data:
   ```bash
   aws dynamodb put-item \
     --table-name ProductCatalog \
     --item '{
       "productId": {"S": "PROD001"},
       "name": {"S": "Laptop"},
       "price": {"N": "999.99"},
       "category": {"S": "Electronics"}
     }'
   ```

### Step 2: Test Point-in-Time Recovery
1. Wait 5-10 minutes for recovery window
2. Make a change to test data:
   ```bash
   aws dynamodb delete-item \
     --table-name ProductCatalog \
     --key '{"productId": {"S": "PROD001"}}'
   ```
3. Restore to point in time:
   - Backups tab → Restore to point-in-time
   - Select time before deletion (last few minutes)
   - New table name: `ProductCatalog-Restored`
   - Restore
4. Verify data in restored table
5. Delete restored table after verification

### Step 3: Create On-Demand Backup
1. Select `ProductCatalog` table
2. Backups tab → Create backup
3. Configure:
   - Backup name: `ProductCatalog-Backup-Manual`
4. Create backup
5. Wait for backup to complete
6. Test restoration:
   - Select backup → Restore
   - Table name: `ProductCatalog-FromBackup`
   - Review settings → Restore
7. Verify and delete test restore

### Step 4: Configure Global Tables
1. **Create base table in primary region:**
   - Name: `GlobalProducts`
   - Partition key: `productId` (String)
   - DynamoDB Streams: Enabled (required for Global Tables)
   - Stream view type: New and old images

2. **Add replica regions:**
   - Select table → Global Tables tab
   - Click "Create replica"
   - Choose replica region (e.g., us-west-2 if primary is us-east-1)
   - Create replica
   - Wait for replica status to become "Active"

3. **Test global replication:**
   - Add item in primary region:
     ```bash
     aws dynamodb put-item \
       --table-name GlobalProducts \
       --item '{
         "productId": {"S": "GLOBAL001"},
         "name": {"S": "Global Product"},
         "region": {"S": "us-east-1"}
       }' \
       --region us-east-1
     ```
   
   - Verify in replica region:
     ```bash
     aws dynamodb get-item \
       --table-name GlobalProducts \
       --key '{"productId": {"S": "GLOBAL001"}}' \
       --region us-west-2
     ```

4. **Test bidirectional replication:**
   - Add item in replica region
   - Verify it appears in primary region

### Step 5: Create DAX Cluster for Caching
1. Navigate to DAX service
2. Click "Create cluster"
3. Configure:
   - Cluster name: `product-cache-cluster`
   - Node type: dax.t3.small (for testing)
   - Cluster size: 3 nodes (1 primary, 2 replicas)
   - Subnet group: Create new
     - Name: `dax-subnet-group`
     - VPC: Your VPC
     - Subnets: Select at least 2 in different AZs
   - IAM service role: Create new
   - Security groups: Create new allowing port 8111
4. Create cluster
5. Wait for cluster status to become "Available" (10-15 minutes)

### Step 6: Test DAX Performance
1. **Without DAX - Direct DynamoDB:**
   ```python
   # test_no_dax.py
   import boto3
   import time
   
   dynamodb = boto3.client('dynamodb', region_name='us-east-1')
   
   start = time.time()
   for i in range(100):
       response = dynamodb.get_item(
           TableName='ProductCatalog',
           Key={'productId': {'S': 'PROD001'}}
       )
   end = time.time()
   print(f"Without DAX: {end-start:.3f} seconds")
   ```

2. **With DAX:**
   ```python
   # test_with_dax.py
   import amazondax
   import time
   
   # DAX endpoint from console
   endpoint = "product-cache-cluster.xxxxxx.dax-clusters.us-east-1.amazonaws.com:8111"
   dax = amazondax.AmazonDaxClient(endpoint)
   
   start = time.time()
   for i in range(100):
       response = dax.get_item(
           TableName='ProductCatalog',
           Key={'productId': {'S': 'PROD001'}}
       )
   end = time.time()
   print(f"With DAX: {end-start:.3f} seconds")
   ```

3. Compare performance (DAX should be significantly faster)

### Step 7: Implement Time To Live (TTL)
1. Create table for session data:
   - Name: `UserSessions`
   - Partition key: `sessionId` (String)
   
2. Enable TTL:
   - Select table → Additional settings
   - Time to Live → Manage TTL
   - TTL attribute: `expirationTime`
   - Enable

3. Add items with TTL:
   ```bash
   # Calculate expiration (current time + 1 hour in epoch seconds)
   EXPIRATION=$(($(date +%s) + 3600))
   
   aws dynamodb put-item \
     --table-name UserSessions \
     --item "{
       \"sessionId\": {\"S\": \"sess123\"},
       \"userId\": {\"S\": \"user001\"},
       \"expirationTime\": {\"N\": \"$EXPIRATION\"}
     }"
   ```

4. Items will be automatically deleted after expiration time

### Step 8: Implement Advanced Data Modeling Patterns

**Pattern 1: Single Table Design**
Create a multi-entity table:
```bash
# Users
aws dynamodb put-item --table-name AppData --item '{
  "PK": {"S": "USER#user001"},
  "SK": {"S": "METADATA"},
  "username": {"S": "john_doe"},
  "email": {"S": "john@example.com"}
}'

# User's Orders
aws dynamodb put-item --table-name AppData --item '{
  "PK": {"S": "USER#user001"},
  "SK": {"S": "ORDER#2024-01-15"},
  "orderId": {"S": "ORD123"},
  "amount": {"N": "99.99"}
}'

# Products
aws dynamodb put-item --table-name AppData --item '{
  "PK": {"S": "PRODUCT#prod001"},
  "SK": {"S": "METADATA"},
  "name": {"S": "Laptop"},
  "price": {"N": "999.99"}
}'
```

**Pattern 2: Adjacency List Pattern**
Model hierarchical relationships:
```bash
# Organization
aws dynamodb put-item --table-name OrgStructure --item '{
  "PK": {"S": "ORG#org001"},
  "SK": {"S": "ORG#org001"},
  "name": {"S": "Acme Corp"}
}'

# Department (child of organization)
aws dynamodb put-item --table-name OrgStructure --item '{
  "PK": {"S": "ORG#org001"},
  "SK": {"S": "DEPT#dept001"},
  "name": {"S": "Engineering"}
}'

# Employee (child of department)
aws dynamodb put-item --table-name OrgStructure --item '{
  "PK": {"S": "DEPT#dept001"},
  "SK": {"S": "EMP#emp001"},
  "name": {"S": "John Doe"}
}'
```

### Step 9: Optimize Costs
1. **Analyze table usage:**
   - CloudWatch metrics → Table metrics
   - Review: ConsumedReadCapacityUnits, ConsumedWriteCapacityUnits
   
2. **Right-size capacity:**
   - For provisioned mode:
     - Set RCU/WCU based on actual usage
     - Enable auto-scaling
     - Set appropriate min/max values
   
3. **Use appropriate storage class:**
   - Standard: Frequent access
   - Standard-IA: Infrequent access (up to 60% cost savings)
   - Switch to IA if access patterns allow

4. **Implement caching with DAX:**
   - Reduces read capacity consumption
   - Lower DynamoDB costs for read-heavy workloads

5. **Archive old data:**
   - Use TTL to remove expired data
   - Export to S3 for long-term storage:
     - Exports tab → Export to S3
     - Cheaper than keeping in DynamoDB

### Step 10: Monitor and Set Alarms
1. Create CloudWatch alarms:
   - **High read throttles:**
     - Metric: ReadThrottleEvents
     - Threshold: Greater than 10
   
   - **High write throttles:**
     - Metric: WriteThrottleEvents
     - Threshold: Greater than 10
   
   - **High consumed capacity:**
     - Metric: ConsumedReadCapacityUnits
     - Threshold: 80% of provisioned
   
2. Enable AWS X-Ray for DynamoDB:
   - Application-level tracing
   - Identify slow queries
   - Optimize access patterns

3. Use DynamoDB Contributor Insights:
   - Identify most accessed items
   - Find hot partitions
   - Optimize partition key design

## Validation
- [ ] Point-in-Time Recovery enabled and tested
- [ ] On-demand backup created and restored
- [ ] Global Table created with replica region
- [ ] Bidirectional replication verified
- [ ] DAX cluster created and operational
- [ ] Performance improvement with DAX demonstrated
- [ ] TTL enabled and configured
- [ ] Advanced data modeling patterns implemented
- [ ] Cost optimization strategies applied
- [ ] CloudWatch alarms configured

## Cleanup
1. Delete DAX cluster:
   - Select cluster → Delete
   - Wait for deletion to complete
2. Delete Global Table replicas:
   - Remove replica regions first
   - Then delete primary table
3. Delete all test tables:
   - `ProductCatalog`
   - `UserSessions`
   - `AppData`
   - `OrgStructure`
4. Delete backups
5. Delete DAX subnet group
6. Delete security groups
7. Delete CloudWatch alarms
8. Verify all resources removed

## Summary
In this lab, you explored advanced DynamoDB features including Global Tables for multi-region replication, DAX for microsecond latency, Point-in-Time Recovery for data protection, and TTL for automatic data expiration. You also learned advanced data modeling patterns and cost optimization strategies essential for production DynamoDB deployments.

**Key Takeaways:**
- Global Tables provide multi-region, multi-master replication
- DAX provides microsecond read latency with caching
- PITR enables restoration to any point in last 35 days
- TTL automatically removes expired items at no cost
- Single table design reduces costs and improves performance
- Proper partition key design prevents hot partitions
- Standard-IA class saves costs for infrequent access
- Export to S3 for long-term data archival
- Monitor throttling events to optimize capacity
- Use Contributor Insights to identify access patterns
