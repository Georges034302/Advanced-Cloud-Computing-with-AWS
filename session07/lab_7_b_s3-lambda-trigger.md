# Lab 7.B: Implement data processing pipelines triggered by S3 and Lambda

## Overview
Build event-driven data pipelines that process objects uploaded to S3 using AWS Lambda. This lab covers configuring S3 event notifications, creating Lambda handlers for common processing patterns (image processing, metadata extraction, ETL), using SNS/SQS/DLQs for reliability, batching with S3 Batch or event mappings, and observing/operating the pipeline.

## Objectives
- Configure S3 event notifications to invoke Lambda (and use SQS/SNS where appropriate)
- Implement Lambda handlers to process S3 objects (image thumbnailing, metadata extraction, CSV ingestion)
- Use IAM least-privilege policies for Lambda and S3 access
- Add retry, DLQ, and idempotency considerations
- Test end-to-end, monitor with CloudWatch Logs and Metrics, and clean up resources

## Prerequisites
- AWS CLI v2 configured
- Python 3.12 (or Node.js) for Lambda code
- boto3 (for Python) if using SDK in functions
- Permissions to create Lambda, S3, IAM, SQS/SNS (optional)

---

## High-level patterns
- Direct S3 -> Lambda for lightweight, near-real-time processing (small files, per-object)
- S3 -> SQS -> Lambda for buffering, retry control, and batching
- S3 Batch + Lambda for bulk processing over many objects
- Use DLQ (SQS) for failed asynchronous invocations
- Store results/artefacts in S3, DynamoDB, or push to downstream services

---

## IAM: required permissions (example minimal policy for processors)
Example policy for Lambda to read objects, write results, and log:
```json
{
  "Version":"2012-10-17",
  "Statement":[
    {
      "Effect":"Allow",
      "Action":["s3:GetObject","s3:GetObjectAcl","s3:HeadObject"],
      "Resource":"arn:aws:s3:::YOUR_BUCKET_NAME/*"
    },
    {
      "Effect":"Allow",
      "Action":["s3:PutObject"],
      "Resource":"arn:aws:s3:::YOUR_OUTPUT_BUCKET/*"
    },
    {
      "Effect":"Allow",
      "Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],
      "Resource":"arn:aws:logs:*:*:*"
    }
  ]
}
```
