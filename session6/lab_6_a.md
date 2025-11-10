# Lab 6.A: Amazon DynamoDB Fundamentals and Data Modeling

## Overview
This lab introduces Amazon DynamoDB, AWS's fully managed NoSQL database service. You'll learn how to create tables, design partition keys, perform CRUD operations, and understand DynamoDB's pricing model. DynamoDB provides single-digit millisecond performance at any scale, making it ideal for modern applications.

## Objectives
- Create and configure DynamoDB tables
- Design effective partition keys and sort keys
- Perform CRUD operations using the console and AWS CLI
- Implement secondary indexes (GSI and LSI)
- Understand read/write capacity modes
- Query and scan data efficiently
- Use DynamoDB Streams for change data capture
- Implement conditional writes and transactions

## Requirements
- AWS account with DynamoDB permissions
- AWS CLI installed and configured
- Understanding of NoSQL database concepts
- Basic JSON knowledge
- Python with boto3 (optional)

## Steps

### Step 1: Create Your First DynamoDB Table
1. Navigate to DynamoDB console
2. Click "Create table"
3. Configure:
   - Table name: `Users`
   - Partition key: `userId` (String)
   - Sort key: None (for now)
   - Table settings: Default settings
   - Read/write capacity: On-demand
4. Create table
5. Wait for table status to become "Active"

### Step 2: Add Items Using Console
1. Select `Users` table
2. Click "Explore table items"
3. Click "Create item"
4. Add attributes:
   ```json
   {
     "userId": "user001",
     "username": "john_doe",
     "email": "john@example.com",
     "age": 30,
     "city": "Seattle"
   }
   ```
5. Create item
6. Add more items with different attributes:
   ```json
   {
     "userId": "user002",
     "username": "jane_smith",
     "email": "jane@example.com",
     "age": 28,
     "country": "USA",
     "premium": true
   }
   ```

### Step 3: Query Items Using Console
1. In "Explore table items" view
2. Use "Scan/Query items" section:
   - Operation: Scan (returns all items)
   - Run
3. Filter results:
   - Add filter: `age` greater than `25`
   - Run filtered scan

### Step 4: Use AWS CLI for DynamoDB Operations
1. **Put Item:**
   ```bash
   aws dynamodb put-item \
     --table-name Users \
     --item '{
       "userId": {"S": "user003"},
       "username": {"S": "bob_wilson"},
       "email": {"S": "bob@example.com"},
       "age": {"N": "35"}
     }'
   ```

2. **Get Item:**
   ```bash
   aws dynamodb get-item \
     --table-name Users \
     --key '{"userId": {"S": "user001"}}'
   ```

3. **Update Item:**
   ```bash
   aws dynamodb update-item \
     --table-name Users \
     --key '{"userId": {"S": "user001"}}' \
     --update-expression "SET age = :newage" \
     --expression-attribute-values '{":newage": {"N": "31"}}'
   ```

4. **Delete Item:**
   ```bash
   aws dynamodb delete-item \
     --table-name Users \
     --key '{"userId": {"S": "user003"}}'
   ```

### Step 5: Create Table with Composite Key
1. Create new table:
   - Name: `Orders`
   - Partition key: `customerId` (String)
   - Sort key: `orderDate` (String)
   - Capacity: On-demand
2. Add sample orders:
   ```json
   {
     "customerId": "CUST001",
     "orderDate": "2024-01-15",
     "orderId": "ORD-12345",
     "amount": 99.99,
     "status": "completed"
   }
   ```
   ```json
   {
     "customerId": "CUST001",
     "orderDate": "2024-02-20",
     "orderId": "ORD-12346",
     "amount": 149.99,
     "status": "shipped"
   }
   ```

3. **Query orders for a customer:**
   ```bash
   aws dynamodb query \
     --table-name Orders \
     --key-condition-expression "customerId = :cid" \
     --expression-attribute-values '{":cid": {"S": "CUST001"}}'
   ```

4. **Query orders within date range:**
   ```bash
   aws dynamodb query \
     --table-name Orders \
     --key-condition-expression "customerId = :cid AND orderDate BETWEEN :start AND :end" \
     --expression-attribute-values '{
       ":cid": {"S": "CUST001"},
       ":start": {"S": "2024-01-01"},
       ":end": {"S": "2024-12-31"}
     }'
   ```

### Step 6: Create Global Secondary Index (GSI)
1. Select `Orders` table
2. Navigate to "Indexes" tab
3. Click "Create index"
4. Configure:
   - Partition key: `status` (String)
   - Sort key: `orderDate` (String)
   - Index name: `status-orderDate-index`
   - Attribute projections: All
5. Create index
6. Wait for index to become "Active"

7. **Query using GSI:**
   ```bash
   aws dynamodb query \
     --table-name Orders \
     --index-name status-orderDate-index \
     --key-condition-expression "status = :status" \
     --expression-attribute-values '{":status": {"S": "completed"}}'
   ```

### Step 7: Implement Conditional Writes
1. **Conditional put (only if item doesn't exist):**
   ```bash
   aws dynamodb put-item \
     --table-name Users \
     --item '{
       "userId": {"S": "user004"},
       "username": {"S": "alice_johnson"},
       "email": {"S": "alice@example.com"}
     }' \
     --condition-expression "attribute_not_exists(userId)"
   ```

2. **Conditional update (only if age is greater than 25):**
   ```bash
   aws dynamodb update-item \
     --table-name Users \
     --key '{"userId": {"S": "user001"}}' \
     --update-expression "SET premium = :val" \
     --condition-expression "age > :age" \
     --expression-attribute-values '{
       ":val": {"BOOL": true},
       ":age": {"N": "25"}
     }'
   ```

### Step 8: Use DynamoDB Transactions
1. **Transactional write (all or nothing):**
   ```bash
   aws dynamodb transact-write-items \
     --transact-items '[
       {
         "Put": {
           "TableName": "Users",
           "Item": {
             "userId": {"S": "user005"},
             "username": {"S": "trans_user"}
           }
         }
       },
       {
         "Update": {
           "TableName": "Orders",
           "Key": {"customerId": {"S": "CUST001"}, "orderDate": {"S": "2024-01-15"}},
           "UpdateExpression": "SET status = :status",
           "ExpressionAttributeValues": {":status": {"S": "cancelled"}}
         }
       }
     ]'
   ```

### Step 9: Enable DynamoDB Streams
1. Select `Users` table
2. Navigate to "Exports and streams" tab
3. Click "Turn on" for DynamoDB stream
4. Configure:
   - View type: New and old images
5. Enable stream
6. Note the Stream ARN (for Lambda integration in later labs)
7. View stream records:
   - Shows all changes to table items
   - Used for triggering Lambda functions
   - Enables change data capture

### Step 10: Understand Capacity Modes
1. **Review On-Demand mode:**
   - Pay per request
   - No capacity planning needed
   - Good for unpredictable workloads

2. **Switch to Provisioned mode (optional):**
   - Select table → Additional settings
   - Read/write capacity mode: Provisioned
   - Read capacity: 5 RCU
   - Write capacity: 5 WCU
   - Enable auto-scaling: Yes
   - Target utilization: 70%
   - Min: 1, Max: 10
   - Update

3. **Monitor capacity metrics:**
   - Navigate to "Metrics" tab
   - View consumed vs provisioned capacity
   - Review throttling events

### Step 11: Use Batch Operations
1. **BatchWriteItem (up to 25 items):**
   ```bash
   aws dynamodb batch-write-item \
     --request-items '{
       "Users": [
         {
           "PutRequest": {
             "Item": {
               "userId": {"S": "user010"},
               "username": {"S": "batch_user1"}
             }
           }
         },
         {
           "PutRequest": {
             "Item": {
               "userId": {"S": "user011"},
               "username": {"S": "batch_user2"}
             }
           }
         }
       ]
     }'
   ```

2. **BatchGetItem:**
   ```bash
   aws dynamodb batch-get-item \
     --request-items '{
       "Users": {
         "Keys": [
           {"userId": {"S": "user001"}},
           {"userId": {"S": "user002"}}
         ]
       }
     }'
   ```

## Validation
- [ ] DynamoDB tables created successfully
- [ ] Items added, queried, updated, and deleted
- [ ] Composite key table created and queried
- [ ] Global Secondary Index created and queried
- [ ] Conditional writes executed successfully
- [ ] Transactions completed successfully
- [ ] DynamoDB Streams enabled
- [ ] Batch operations completed
- [ ] Capacity modes understood and configured

## Cleanup
1. Disable DynamoDB Streams
2. Delete Global Secondary Indexes
3. Delete all tables:
   - `Users`
   - `Orders`
4. Verify tables are deleted in console
5. Check for any CloudWatch alarms and delete

## Summary
In this lab, you learned DynamoDB fundamentals including table creation, data modeling with partition and sort keys, CRUD operations, and secondary indexes. You explored conditional writes, transactions, and DynamoDB Streams for change data capture. Understanding these concepts is essential for building scalable, high-performance applications with DynamoDB.

**Key Takeaways:**
- DynamoDB is serverless and fully managed
- Partition key determines data distribution
- Sort key enables range queries
- GSI allows querying on different attributes
- On-demand mode is good for unpredictable workloads
- Provisioned mode with auto-scaling optimizes costs
- Conditional writes prevent race conditions
- Transactions ensure ACID properties across items
- DynamoDB Streams enable event-driven architectures
- Efficient key design is critical for performance
