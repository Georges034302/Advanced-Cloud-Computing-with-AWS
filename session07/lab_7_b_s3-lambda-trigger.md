# Lab 7.B: Process CSV Files with S3 Trigger and Lambda

## Overview
This lab demonstrates event-driven data processing using S3, Lambda, and DynamoDB. You'll create an S3 bucket that triggers a Node.js Lambda function when CSV files are uploaded. The Lambda function parses student records (ID, NAME, MARK, GRADE) from the CSV and stores them in DynamoDB. This architecture is perfect for automated data ingestion pipelines.

---

## Objectives
- Create S3 bucket with event notifications
- Create DynamoDB table for student records
- Build Node.js Lambda function to parse CSV
- Configure S3 trigger to invoke Lambda
- Upload CSV file and verify data in DynamoDB
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Node.js 18+ installed locally
- IAM permissions for S3, Lambda, DynamoDB, and IAM
- Basic understanding of CSV parsing and event-driven architecture

---

## Architecture

```
CSV File Upload → S3 Bucket → Event Notification → Lambda (Node.js)
                                                      ↓
                                            Parse CSV → JSON
                                                      ↓
                                                  DynamoDB
```

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set region
REGION="ap-southeast-2"
echo "REGION=$REGION"

# Set resource names
BUCKET_NAME="student-csv-uploads-${ACCOUNT_ID}"
echo "BUCKET_NAME=$BUCKET_NAME"

TABLE_NAME="Students"
echo "TABLE_NAME=$TABLE_NAME"

FUNCTION_NAME="csv-to-dynamodb"
echo "FUNCTION_NAME=$FUNCTION_NAME"

ROLE_NAME="lambda-s3-dynamodb-role"
echo "ROLE_NAME=$ROLE_NAME"

# Verify Node.js
node --version || { echo "❌ Node.js not installed"; exit 1; }

echo ""
echo "✅ Prerequisites verified"
```

---

## Step 2 – Create S3 Bucket

```bash
# Create S3 bucket for CSV uploads
echo "Creating S3 bucket..."

aws s3api create-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

# Enable versioning (optional but recommended)
aws s3api put-bucket-versioning \
  --bucket "$BUCKET_NAME" \
  --versioning-configuration Status=Enabled

echo "✅ S3 bucket created: $BUCKET_NAME"
```

---

## Step 3 – Create DynamoDB Table

```bash
# Create DynamoDB table for student records
echo "Creating DynamoDB table..."

aws dynamodb create-table \
  --table-name "$TABLE_NAME" \
  --attribute-definitions \
    AttributeName=StudentID,AttributeType=S \
  --key-schema \
    AttributeName=StudentID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION"

# Wait for table to be active
echo "Waiting for table to become active..."
aws dynamodb wait table-exists \
  --table-name "$TABLE_NAME" \
  --region "$REGION"

echo "✅ DynamoDB table created: $TABLE_NAME"

# Describe table
aws dynamodb describe-table \
  --table-name "$TABLE_NAME" \
  --query 'Table.{Name:TableName,Status:TableStatus,ItemCount:ItemCount}' \
  --output table \
  --region "$REGION"
```

---

## Step 4 – Create Lambda Function Code

```bash
# Create project directory
mkdir -p csv-lambda
cd csv-lambda

# Create package.json
cat > package.json <<'EOF'
{
  "name": "csv-to-dynamodb",
  "version": "1.0.0",
  "description": "Parse CSV from S3 and store in DynamoDB",
  "main": "index.js",
  "dependencies": {
    "@aws-sdk/client-s3": "^3.600.0",
    "@aws-sdk/client-dynamodb": "^3.600.0",
    "@aws-sdk/lib-dynamodb": "^3.600.0"
  }
}
EOF

# Create Lambda function
cat > index.js <<'EOF'
const { S3Client, GetObjectCommand } = require('@aws-sdk/client-s3');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, PutCommand } = require('@aws-sdk/lib-dynamodb');

// Initialize AWS clients
const s3Client = new S3Client();
const dynamoClient = new DynamoDBClient();
const docClient = DynamoDBDocumentClient.from(dynamoClient);

// DynamoDB table name from environment variable
const TABLE_NAME = process.env.TABLE_NAME || 'Students';

/**
 * Lambda handler triggered by S3 upload
 * Parses CSV file and stores records in DynamoDB
 */
exports.handler = async (event) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        // Get S3 bucket and key from event
        const record = event.Records[0];
        const bucket = record.s3.bucket.name;
        const key = decodeURIComponent(record.s3.object.key.replace(/\+/g, ' '));
        
        console.log(`Processing file: s3://${bucket}/${key}`);
        
        // Only process CSV files
        if (!key.toLowerCase().endsWith('.csv')) {
            console.log('Skipping non-CSV file');
            return { statusCode: 200, body: 'Skipped non-CSV file' };
        }
        
        // Get CSV file from S3
        const s3Response = await s3Client.send(new GetObjectCommand({
            Bucket: bucket,
            Key: key
        }));
        
        // Read CSV content
        const csvContent = await streamToString(s3Response.Body);
        console.log('CSV content retrieved, length:', csvContent.length);
        
        // Parse CSV
        const students = parseCSV(csvContent);
        console.log(`Parsed ${students.length} student records`);
        
        // Store in DynamoDB
        let successCount = 0;
        let errorCount = 0;
        
        for (const student of students) {
            try {
                await docClient.send(new PutCommand({
                    TableName: TABLE_NAME,
                    Item: student
                }));
                successCount++;
                console.log(`Stored student: ${student.StudentID} - ${student.Name}`);
            } catch (error) {
                errorCount++;
                console.error(`Error storing student ${student.StudentID}:`, error);
            }
        }
        
        const result = {
            statusCode: 200,
            body: JSON.stringify({
                message: 'CSV processing completed',
                file: key,
                totalRecords: students.length,
                successCount,
                errorCount
            })
        };
        
        console.log('Processing complete:', result.body);
        return result;
        
    } catch (error) {
        console.error('Error processing CSV:', error);
        throw error;
    }
};

/**
 * Convert stream to string
 */
async function streamToString(stream) {
    const chunks = [];
    for await (const chunk of stream) {
        chunks.push(chunk);
    }
    return Buffer.concat(chunks).toString('utf-8');
}

/**
 * Parse CSV content to JSON array
 * Expected format: ID,NAME,MARK,GRADE
 */
function parseCSV(csvContent) {
    const lines = csvContent.trim().split('\n');
    const students = [];
    
    // Skip header row (first line)
    for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue; // Skip empty lines
        
        const [id, name, mark, grade] = line.split(',').map(field => field.trim());
        
        // Validate required fields
        if (!id || !name) {
            console.warn(`Skipping invalid row ${i}: ${line}`);
            continue;
        }
        
        // Create student object
        const student = {
            StudentID: id,
            Name: name,
            Mark: mark ? parseInt(mark) : 0,
            Grade: grade || 'N/A',
            ProcessedAt: new Date().toISOString()
        };
        
        students.push(student);
    }
    
    return students;
}
EOF

echo "✅ Lambda function code created"
```

---

## Step 5 – Install Dependencies and Package Lambda

```bash
# Install dependencies
echo "Installing Node.js dependencies..."
npm install

echo "✅ Dependencies installed"

# Create deployment package
echo "Creating deployment package..."
zip -r lambda-function.zip index.js package.json node_modules/

echo "✅ Deployment package created"

# Check package size
ls -lh lambda-function.zip
```

---

## Step 6 – Create IAM Role for Lambda

```bash
# Return to parent directory
cd ..

# Create trust policy
cat > lambda-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role
echo "Creating IAM role..."

aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document file://lambda-trust-policy.json \
  --description "Execution role for CSV processing Lambda"

# Create inline policy for S3 and DynamoDB access
cat > lambda-permissions-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion"
      ],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${TABLE_NAME}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/lambda/${FUNCTION_NAME}:*"
    }
  ]
}
EOF

# Attach inline policy
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "LambdaS3DynamoDBPolicy" \
  --policy-document file://lambda-permissions-policy.json

echo "✅ IAM role created with permissions"

# Get role ARN
ROLE_ARN=$(aws iam get-role \
  --role-name "$ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)
echo "ROLE_ARN=$ROLE_ARN"

# Wait for IAM role to propagate
echo "Waiting for IAM role to propagate..."
sleep 10
```

---

## Step 7 – Create Lambda Function

```bash
# Create Lambda function
echo "Creating Lambda function..."

aws lambda create-function \
  --function-name "$FUNCTION_NAME" \
  --runtime nodejs20.x \
  --role "$ROLE_ARN" \
  --handler index.handler \
  --zip-file fileb://csv-lambda/lambda-function.zip \
  --timeout 30 \
  --memory-size 256 \
  --environment "Variables={TABLE_NAME=$TABLE_NAME}" \
  --description "Process CSV files from S3 and store in DynamoDB" \
  --region "$REGION"

echo "✅ Lambda function created"

# Get function ARN
FUNCTION_ARN=$(aws lambda get-function \
  --function-name "$FUNCTION_NAME" \
  --query 'Configuration.FunctionArn' \
  --output text \
  --region "$REGION")
echo "FUNCTION_ARN=$FUNCTION_ARN"
```

---

## Step 8 – Grant S3 Permission to Invoke Lambda

```bash
# Allow S3 to invoke Lambda function
echo "Granting S3 permission to invoke Lambda..."

aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id "s3-invoke-permission" \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn "arn:aws:s3:::${BUCKET_NAME}" \
  --region "$REGION"

echo "✅ Permission granted"
```

---

## Step 9 – Configure S3 Event Notification

```bash
# Create S3 event notification configuration
cat > s3-notification.json <<EOF
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "csv-upload-trigger",
      "LambdaFunctionArn": "${FUNCTION_ARN}",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {
              "Name": "suffix",
              "Value": ".csv"
            }
          ]
        }
      }
    }
  ]
}
EOF

# Apply notification configuration
echo "Configuring S3 event notification..."

aws s3api put-bucket-notification-configuration \
  --bucket "$BUCKET_NAME" \
  --notification-configuration file://s3-notification.json

echo "✅ S3 event notification configured"

# Verify configuration
aws s3api get-bucket-notification-configuration \
  --bucket "$BUCKET_NAME" \
  --query 'LambdaFunctionConfigurations[*].{Id:Id,Events:Events,Function:LambdaFunctionArn}' \
  --output table
```

---

## Step 10 – Create Sample CSV File

```bash
# Create sample students.csv file
cat > students.csv <<'EOF'
ID,NAME,MARK,GRADE
S001,Alice Johnson,95,A
S002,Bob Smith,87,B
S003,Charlie Brown,76,C
S004,Diana Prince,92,A
S005,Ethan Hunt,68,D
S006,Fiona Apple,81,B
S007,George Lucas,73,C
S008,Hannah Montana,89,B
S009,Isaac Newton,98,A
S010,Julia Roberts,84,B
EOF

echo "✅ Sample CSV file created"

# Display contents
echo ""
echo "Sample CSV content:"
cat students.csv
```

---

## Step 11 – Upload CSV to S3 and Trigger Lambda

```bash
echo ""
echo "================================================"
echo "UPLOADING CSV FILE TO S3"
echo "================================================"
echo ""

# Upload CSV file to S3
aws s3 cp students.csv "s3://${BUCKET_NAME}/students.csv"

echo "✅ CSV file uploaded to S3"
echo ""
echo "Lambda function will be triggered automatically..."
echo "Waiting 5 seconds for processing..."
sleep 5
```

---

## Step 12 – Verify Lambda Execution

```bash
echo ""
echo "Checking Lambda logs..."

# Get latest log stream
LOG_STREAM=$(aws logs describe-log-streams \
  --log-group-name "/aws/lambda/$FUNCTION_NAME" \
  --order-by LastEventTime \
  --descending \
  --max-items 1 \
  --query 'logStreams[0].logStreamName' \
  --output text \
  --region "$REGION" \
  2>/dev/null || echo "")

if [ -n "$LOG_STREAM" ]; then
    echo "LOG_STREAM=$LOG_STREAM"
    echo ""
    echo "Recent Lambda execution logs:"
    aws logs get-log-events \
      --log-group-name "/aws/lambda/$FUNCTION_NAME" \
      --log-stream-name "$LOG_STREAM" \
      --limit 30 \
      --query 'events[*].message' \
      --output text \
      --region "$REGION"
else
    echo "No log streams found yet. Lambda may still be executing..."
fi
```

---

## Step 13 – Query DynamoDB Table

```bash
echo ""
echo "================================================"
echo "QUERYING DYNAMODB TABLE"
echo "================================================"
echo ""

# Scan DynamoDB table
aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --region "$REGION" \
  --query 'Items[*].{StudentID:StudentID.S,Name:Name.S,Mark:Mark.N,Grade:Grade.S}' \
  --output table

# Get item count
ITEM_COUNT=$(aws dynamodb describe-table \
  --table-name "$TABLE_NAME" \
  --query 'Table.ItemCount' \
  --output text \
  --region "$REGION")

echo ""
echo "Total records in DynamoDB: $ITEM_COUNT"
```

---

## Step 14 – Query Specific Student

```bash
echo ""
echo "Querying specific student (S001)..."

aws dynamodb get-item \
  --table-name "$TABLE_NAME" \
  --key '{"StudentID": {"S": "S001"}}' \
  --region "$REGION" \
  --query 'Item' \
  --output json | python3 -c "
import sys, json
item = json.load(sys.stdin)
if item:
    print('Student Details:')
    print(f\"  ID: {item.get('StudentID', {}).get('S', 'N/A')}\")
    print(f\"  Name: {item.get('Name', {}).get('S', 'N/A')}\")
    print(f\"  Mark: {item.get('Mark', {}).get('N', 'N/A')}\")
    print(f\"  Grade: {item.get('Grade', {}).get('S', 'N/A')}\")
    print(f\"  Processed: {item.get('ProcessedAt', {}).get('S', 'N/A')}\")
else:
    print('Student not found')
"
```

---

## Step 15 – Test with Another CSV File

```bash
echo ""
echo "Testing with another CSV file..."

# Create second CSV file
cat > students2.csv <<'EOF'
ID,NAME,MARK,GRADE
S011,Kevin Hart,78,C
S012,Laura Croft,94,A
S013,Michael Scott,82,B
EOF

# Upload second file
aws s3 cp students2.csv "s3://${BUCKET_NAME}/students2.csv"

echo "✅ Second CSV uploaded"
echo "Waiting 5 seconds for processing..."
sleep 5

# Query table again
echo ""
echo "Updated DynamoDB records:"
aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --region "$REGION" \
  --query 'Items[*].{StudentID:StudentID.S,Name:Name.S,Mark:Mark.N,Grade:Grade.S}' \
  --output table
```

---

## Step 16 – View S3 Bucket Contents

```bash
echo ""
echo "S3 Bucket contents:"
aws s3 ls "s3://${BUCKET_NAME}/" --human-readable

echo ""
echo "S3 Bucket details:"
aws s3api head-bucket \
  --bucket "$BUCKET_NAME" \
  2>&1 || echo "Bucket accessible"
```

---

## Step 17 – View Lambda Function Details

```bash
echo ""
echo "Lambda Function Configuration:"
aws lambda get-function-configuration \
  --function-name "$FUNCTION_NAME" \
  --query '{Name:FunctionName,Runtime:Runtime,Memory:MemorySize,Timeout:Timeout,Handler:Handler}' \
  --output table \
  --region "$REGION"

echo ""
echo "Lambda Environment Variables:"
aws lambda get-function-configuration \
  --function-name "$FUNCTION_NAME" \
  --query 'Environment.Variables' \
  --output json \
  --region "$REGION"
```

---

## Step 18 – Cleanup Resources

```bash
echo ""
echo "Cleaning up resources..."

# Remove S3 event notification
echo "Removing S3 event notification..."
aws s3api put-bucket-notification-configuration \
  --bucket "$BUCKET_NAME" \
  --notification-configuration '{}'

# Delete S3 objects
echo "Deleting S3 objects..."
aws s3 rm "s3://${BUCKET_NAME}/" --recursive

# Delete S3 bucket
echo "Deleting S3 bucket..."
aws s3api delete-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$REGION"

# Delete DynamoDB table
echo "Deleting DynamoDB table..."
aws dynamodb delete-table \
  --table-name "$TABLE_NAME" \
  --region "$REGION"

# Delete Lambda function
echo "Deleting Lambda function..."
aws lambda delete-function \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION"

# Delete IAM role policy and role
echo "Cleaning up IAM role..."
aws iam delete-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "LambdaS3DynamoDBPolicy"

aws iam delete-role \
  --role-name "$ROLE_NAME"

# Delete CloudWatch log group
echo "Deleting CloudWatch logs..."
aws logs delete-log-group \
  --log-group-name "/aws/lambda/$FUNCTION_NAME" \
  --region "$REGION" \
  2>/dev/null || true

# Delete local files
echo "Cleaning up local files..."
rm -rf csv-lambda
rm -f students.csv students2.csv
rm -f lambda-trust-policy.json lambda-permissions-policy.json s3-notification.json

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- S3 bucket and objects"
echo "- DynamoDB table"
echo "- Lambda function"
echo "- IAM role and policies"
echo "- CloudWatch log groups"
echo "- Local files"
```

---

## Summary

In this lab, you have:
- Created S3 bucket with event notifications for CSV files
- Created DynamoDB table with StudentID as partition key
- Built Node.js Lambda function to parse CSV and store data
- Configured S3 trigger to invoke Lambda automatically
- Uploaded CSV files and verified data in DynamoDB
- Queried DynamoDB for specific records
- Viewed Lambda logs in CloudWatch
- Cleaned up all resources

**Key Takeaways:**
- **Event-Driven Architecture**: S3 triggers Lambda automatically on file upload
- **Serverless Data Pipeline**: No servers to manage, scales automatically
- **CSV Parsing**: Simple Node.js parsing with split() and map()
- **DynamoDB**: NoSQL database with automatic scaling
- **IAM Permissions**: Lambda needs S3 read, DynamoDB write, and CloudWatch logs
- **Error Handling**: Try-catch blocks prevent partial failures

**Data Flow:**
```
1. CSV uploaded to S3
2. S3 triggers Lambda function
3. Lambda downloads CSV from S3
4. Lambda parses CSV to JSON
5. Lambda stores records in DynamoDB
6. Lambda logs execution to CloudWatch
```

**Lambda Event Structure:**
```json
{
  "Records": [
    {
      "s3": {
        "bucket": {"name": "bucket-name"},
        "object": {"key": "students.csv"}
      }
    }
  ]
}
```

**CSV Format:**
```csv
ID,NAME,MARK,GRADE
S001,Alice Johnson,95,A
S002,Bob Smith,87,B
```

**DynamoDB Item:**
```json
{
  "StudentID": "S001",
  "Name": "Alice Johnson",
  "Mark": 95,
  "Grade": "A",
  "ProcessedAt": "2025-11-13T10:30:00.000Z"
}
```

---

## Best Practices

**Error Handling:**
- Validate CSV format before processing
- Skip invalid rows instead of failing entire batch
- Log errors with student ID for debugging
- Use DLQ (Dead Letter Queue) for failed invocations

**Performance:**
- Use batch writes for large CSV files (DynamoDB BatchWriteItem)
- Increase Lambda memory for faster processing
- Enable S3 Transfer Acceleration for large uploads
- Use streams for large files instead of loading into memory

**Security:**
- Use least-privilege IAM policies
- Enable S3 bucket encryption (AES-256 or KMS)
- Validate and sanitize CSV input
- Enable CloudTrail for audit logging

**Cost Optimization:**
- Use S3 Standard-IA for infrequent access
- Set S3 lifecycle policies to delete old files
- Use DynamoDB on-demand pricing for variable workloads
- Monitor Lambda duration to optimize memory allocation

---

## Free Tier Notes
- **Lambda**: 1M requests/month + 400,000 GB-seconds compute
- **S3**: 5 GB storage + 20,000 GET + 2,000 PUT requests
- **DynamoDB**: 25 GB storage + 25 read/write capacity units
- **CloudWatch Logs**: 5 GB ingestion + 5 GB storage

This lab uses minimal resources, staying well within free tier limits.

---

## Production Enhancements

1. **Batch Processing**
   ```javascript
   // Use BatchWriteItem for better performance
   const { BatchWriteCommand } = require('@aws-sdk/lib-dynamodb');
   
   const batches = chunkArray(students, 25); // DynamoDB max 25 items
   for (const batch of batches) {
       await docClient.send(new BatchWriteCommand({
           RequestItems: {
               [TABLE_NAME]: batch.map(student => ({
                   PutRequest: { Item: student }
               }))
           }
       }));
   }
   ```

2. **Add Data Validation**
   ```javascript
   function validateStudent(student) {
       if (!student.StudentID || !student.Name) return false;
       if (student.Mark < 0 || student.Mark > 100) return false;
       if (!['A', 'B', 'C', 'D', 'F'].includes(student.Grade)) return false;
       return true;
   }
   ```

3. **Use SQS for Buffering**
   - S3 → SQS → Lambda for better retry control
   - Prevents Lambda throttling on large batches

4. **Add SNS Notification**
   - Send email when processing completes
   - Alert on errors or validation failures

5. **Use Step Functions**
   - Orchestrate complex workflows
   - Handle validation, processing, and notification steps

6. **Add Monitoring**
   ```bash
   # CloudWatch alarm for Lambda errors
   aws cloudwatch put-metric-alarm \
     --alarm-name csv-processing-errors \
     --alarm-description "Alert on Lambda errors" \
     --metric-name Errors \
     --namespace AWS/Lambda \
     --statistic Sum \
     --period 300 \
     --threshold 5 \
     --comparison-operator GreaterThanThreshold
   ```

7. **Implement Idempotency**
   ```javascript
   // Check if record exists before inserting
   const existing = await docClient.send(new GetCommand({
       TableName: TABLE_NAME,
       Key: { StudentID: student.StudentID }
   }));
   
   if (existing.Item) {
       console.log(`Student ${student.StudentID} already exists, skipping`);
       continue;
   }
   ```

---

## Troubleshooting

**Lambda not triggered:**
- Check S3 event notification configuration
- Verify Lambda permission for S3 invocation
- Check file suffix filter (.csv)

**DynamoDB write errors:**
- Verify IAM policy has PutItem permission
- Check table name in environment variable
- Verify table exists and is active

**CSV parsing errors:**
- Validate CSV format (comma-separated, no quotes)
- Check for empty lines or extra commas
- Verify header row is present

**Lambda timeout:**
- Increase timeout (default 30s)
- Process files in batches
- Use streams for large files
