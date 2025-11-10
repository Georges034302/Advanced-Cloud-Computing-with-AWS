# Lab 4.B: Build and query a DynamoDB table using AWS CLI and SDK

## Overview
Hands-on lab to design, create, populate, and query an Amazon DynamoDB table using the AWS CLI and SDK (boto3). You will practice schema design (partition & sort keys), efficient queries, secondary indexes, pagination, TTL, backups, and basic IAM permissions.

## Objectives
- Design a DynamoDB table schema for read/write patterns
- Create a table with CLI and SDK
- Insert items (PutItem, BatchWriteItem)
- Query and scan efficiently, use pagination
- Add a Global Secondary Index (GSI) and query it
- Use TTL, on-demand backups, and point-in-time recovery (PITR)
- Clean up resources

## Prerequisites
- AWS CLI v2 configured (aws configure)
- Python 3 with boto3 installed (pip install boto3) for SDK examples
- IAM permissions for dynamodb:* for lab account (or scoped as shown below)

---

## Table design notes
- Choose a partition key (hash) for even distribution; add a sort key for query filtering.
- Reserve GSIs for alternate access patterns.
- Keep item size small and avoid hot keys under high write traffic.

Example model for a simple event store:
- Table name: LabEvents
- Partition key: pk (string) — e.g., USER#123
- Sort key: sk (string) — e.g., EVENT#2025-11-10T12:00:00Z
- GSI: GSI1 with partition gsi1pk and sort gsi1sk for querying by event type or status

---

## CLI: Create table (on-demand or provisioned capacity)
Replace REGION, ACCOUNT, TABLE_NAME as needed.

On-demand (simpler for labs):
```bash
aws dynamodb create-table \
  --table-name LabEvents \
  --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S AttributeName=gsi1pk,AttributeType=S \
  --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --global-secondary-indexes '[{"IndexName":"GSI1","KeySchema":[{"AttributeName":"gsi1pk","KeyType":"HASH"},{"AttributeName":"gsi1sk","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}]' \
  --region us-east-1
```

Wait for table:
```bash
aws dynamodb wait table-exists --table-name LabEvents --region us-east-1
```

## CLI: Insert items
Single item:
```bash
aws dynamodb put-item --table-name LabEvents --item '{"pk":{"S":"USER#123"},"sk":{"S":"EVENT#2025-11-10T12:00:00Z"},"type":{"S":"login"},"payload":{"S":"{\"ip\":\"1.2.3.4\"}"}}' --region us-east-1
```

Batch write (up to 25 items per request):
```bash
aws dynamodb batch-write-item --request-items file://batch-items.json --region us-east-1
```

## CLI: Query and Scan
Query by pk and range on sk:
```bash
aws dynamodb query --table-name LabEvents --key-condition-expression "pk = :p and begins_with(sk, :s)" --expression-attribute-values '{":p":{"S":"USER#123"},":s":{"S":"EVENT#2025-11"}}' --region us-east-1
```

Query GSI:
```bash
aws dynamodb query --table-name LabEvents --index-name GSI1 --key-condition-expression "gsi1pk = :g" --expression-attribute-values '{":g":{"S":"EVENTTYPE#login"}}' --region us-east-1
```

Scan with pagination (use sparingly):
```bash
aws dynamodb scan --table-name LabEvents --max-items 100 --region us-east-1
```

## TTL, Backups, and PITR
Enable TTL on attribute "expiresAt" (epoch seconds):
```bash
aws dynamodb update-time-to-live --table-name LabEvents --time-to-live-specification "Enabled=true,AttributeName=expiresAt" --region us-east-1
```

Create on-demand backup:
```bash
aws dynamodb create-backup --table-name LabEvents --backup-name LabEvents-backup-$(date -u +%Y%m%d) --region us-east-1
```

Enable PITR:
```bash
aws dynamodb update-continuous-backups --table-name LabEvents --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true --region us-east-1
```

## SDK examples (Python / boto3)

Create table (boto3):
```python
# filepath: examples/dynamodb_create_table.py
import boto3

dynamodb = boto3.client('dynamodb', region_name='us-east-1')
dynamodb.create_table(
    TableName='LabEvents',
    AttributeDefinitions=[
        {'AttributeName': 'pk', 'AttributeType': 'S'},
        {'AttributeName': 'sk', 'AttributeType': 'S'},
        {'AttributeName': 'gsi1pk', 'AttributeType': 'S'}
    ],
    KeySchema=[
        {'AttributeName': 'pk', 'KeyType': 'HASH'},
        {'AttributeName': 'sk', 'KeyType': 'RANGE'}
    ],
    BillingMode='PAY_PER_REQUEST',
    GlobalSecondaryIndexes=[{
        'IndexName':'GSI1',
        'KeySchema':[{'AttributeName':'gsi1pk','KeyType':'HASH'}],
        'Projection':{'ProjectionType':'ALL'}
    }]
)
```

Put item and query (boto3):
```python
# filepath: examples/dynamodb_put_query.py
import boto3
from boto3.dynamodb.conditions import Key

d = boto3.resource('dynamodb', region_name='us-east-1')
t = d.Table('LabEvents')

t.put_item(Item={'pk':'USER#123','sk':'EVENT#2025-11-10T12:00:00Z','type':'login','payload':'{"ip":"1.2.3.4"}'})

resp = t.query(KeyConditionExpression=Key('pk').eq('USER#123') & Key('sk').begins_with('EVENT#2025'))
print(resp.get('Items', []))
```

## IAM policy example (scoped)
Grant minimal privileges for the lab (replace resource ARNs):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DescribeTable",
        "dynamodb:PutItem",
        "dynamodb:BatchWriteItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:UpdateTable",
        "dynamodb:DeleteTable",
        "dynamodb:CreateBackup",
        "dynamodb:UpdateContinuousBackups",
        "dynamodb:UpdateTimeToLive"
      ],
      "Resource": "arn:aws:dynamodb:REGION:ACCOUNT_ID:table/LabEvents"
    }
  ]
}
```

## Validation checklist
- [ ] Table created and active
- [ ] Items inserted via CLI and SDK
- [ ] Query by PK+SK returns expected items
- [ ] GSI created and queried successfully
- [ ] Pagination handled for large results
- [ ] TTL and backups configured (on-demand backup + PITR)
- [ ] IAM permissions scoped and working

## Cleanup
Delete table when done:
```bash
aws dynamodb delete-table --table-name LabEvents --region us-east-1
aws dynamodb wait table-not-exists --table-name LabEvents --region us-east-1
```
Remove example backup(s) and any on-demand snapshots if created.

## Notes & best practices
- Prefer queries over scans; design keys for access patterns.
- Use on-demand billing for unpredictable workloads during labs.
- Monitor for hot keys and uneven traffic distribution.
- Use GSIs sparingly and evaluate capacity/cost.
- Use encryption at rest (default) and IAM roles for SDK access.

## Summary
This lab covers practical DynamoDB operations using CLI and SDK, focusing on schema design, efficient querying, indexes, TTL, backups, and cleanup — all essential for scalable serverless data stores.
