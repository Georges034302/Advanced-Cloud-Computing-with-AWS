# Advanced Cloud Computing with AWS: Hands-On Lab Series

## 📚 Technical Introduction

This comprehensive lab series provides hands-on experience with Amazon Web Services (AWS), covering fundamental to advanced cloud computing concepts. Through 10 progressive sessions with 20 detailed labs, you'll gain practical skills in deploying, managing, and optimizing cloud infrastructure.

---

**Prerequisites:**
- Basic understanding of cloud computing concepts
- Familiarity with command line interfaces
- Programming knowledge (Python, Node.js, or similar)
- AWS account (Free Tier eligible for most labs)

---

<details>
  <summary>Lab Session 01: Provisioning and Securing EC2 in a Custom VPC</summary>

  Learn how to create, secure, and manage EC2 instances inside a custom Virtual Private Cloud (VPC).

  **Labs for this session:**
  - [lab_1_a_ec2-vpc.md](session01/lab_1_a_ec2-vpc.md):  
    *Launch and configure a Linux EC2 instance in a custom VPC.*
  - [lab_1_b_dns-security.md](session01/lab_1_b_dns-security.md):  
    *Secure web access using Security Groups, NACLs, and Route 53 DNS.*

</details>

<details>
  <summary>Lab Session 02: Identity and Access Control with IAM</summary>

  Master AWS Identity and Access Management (IAM) by applying least-privilege security and MFA.

  **Labs for this session:**
  - [lab_2_a_iam-users-policies.md](session02/lab_2_a_iam-users-policies.md):  
    *Create IAM users, groups, and custom policies for least privilege.*
  - [lab_2_b_iam-roles-mfa.md](session02/lab_2_b_iam-roles-mfa.md):  
    *Configure IAM roles and MFA for secure access to AWS services.*

</details>

<details>
  <summary>Lab Session 03: Managing Object and Block Storage</summary>

  Explore storage management with Amazon S3 and EBS, including security and lifecycle automation.

  **Labs for this session:**
  - [lab_3_a_s3-lifecycle.md](session03/lab_3_a_s3-lifecycle.md):  
    *Manage S3 buckets with versioning, encryption, and lifecycle rules.*
  - [lab_3_b_ebs-snapshots.md](session03/lab_3_b_ebs-snapshots.md):  
    *Attach and manage EBS volumes and snapshots for EC2 instances.*

</details>

<details>
  <summary>Lab Session 04: Deploying and Connecting AWS Databases</summary>

  Learn to launch, connect, and manage relational and NoSQL databases in AWS.

  **Labs for this session:**
  - [lab_4_a_rds-mysql-private.md](session04/lab_4_a_rds-mysql-private.md):  
    *Provision and connect to an RDS MySQL database in a private subnet.*
  - [lab_4_b_dynamodb-cli.md](session04/lab_4_b_dynamodb-cli.md):  
    *Build and query a DynamoDB table using AWS CLI and SDK.*

</details>

<details>
  <summary>Lab Session 05: Application Load Balancing and Auto Scaling</summary>

  Implement high availability and elasticity using Load Balancers and Auto Scaling Groups.

  **Labs for this session:**
  - [lab_5_a_alb-deployment.md](session05/lab_5_a_alb-deployment.md):  
    *Deploy a web application behind an Application Load Balancer (ALB).*
  - [lab_5_b_autoscaling-cloudwatch.md](session05/lab_5_b_autoscaling-cloudwatch.md):  
    *Configure Auto Scaling policies and CloudWatch alarms for EC2.*

</details>

<details>
  <summary>Lab Session 06: Containerizing Applications with ECS (Fargate)</summary>

  Package and deploy containerized applications with Amazon ECS and ECR.

  **Labs for this session:**
  - [lab_6_a_ecr-docker-push.md](session06/lab_6_a_ecr-docker-push.md):  
    *Build and push Docker images to Amazon Elastic Container Registry (ECR).*
  - [lab_6_b_ecs-fargate-deploy.md](session06/lab_6_b_ecs-fargate-deploy.md):  
    *Deploy a containerized app on Amazon ECS using Fargate.*

</details>

<details>
  <summary>Lab Session 07: Serverless Application with Lambda and API Gateway</summary>

  Build and test serverless REST APIs and background processing flows.

  **Labs for this session:**
  - [lab_7_a_lambda-api-gateway.md](session07/lab_7_a_lambda-api-gateway.md):  
    *Build a REST API using API Gateway integrated with Lambda.*
  - [lab_7_b_s3-lambda-trigger.md](session07/lab_7_b_s3-lambda-trigger.md):  
    *Implement data processing pipelines triggered by S3 and Lambda.*

</details>

<details>
  <summary>Lab Session 08: Event-Driven Messaging with SQS, SNS, and EventBridge</summary>

  Integrate messaging and automation across AWS services for distributed workflows.

  **Labs for this session:**
  - [lab_8_a_sqs-lambda-integration.md](session08/lab_8_a_sqs-lambda-integration.md):  
    *Create an event-driven workflow using SQS and Lambda consumers.*
  - [lab_8_b_sns-eventbridge-alerts.md](session08/lab_8_b_sns-eventbridge-alerts.md):  
    *Send multi-channel notifications using SNS and EventBridge rules.*

</details>

<details>
  <summary>Lab Session 09: Monitoring and Logging Operations</summary>

  Monitor, audit, and analyze your AWS environment using native observability tools.

  **Labs for this session:**
  - [lab_9_a_cloudwatch-dashboard.md](session09/lab_9_a_cloudwatch-dashboard.md):  
    *Configure CloudWatch dashboards, metrics, and alarms.*
  - [lab_9_b_cloudtrail-logs.md](session09/lab_9_b_cloudtrail-logs.md):  
    *Track and audit API calls using CloudTrail and Log Insights.*

</details>

<details>
  <summary>Lab Session 10: Infrastructure as Code with CloudFormation and CDK</summary>

  Automate AWS resource creation and management with Infrastructure as Code (IaC).

  **Labs for this session:**
  - [lab_10_a_cloudformation-stack.md](session10/lab_10_a_cloudformation-stack.md):  
    *Deploy an automated EC2 and S3 stack using CloudFormation.*
  - [lab_10_b_cdk-python-deploy.md](session10/lab_10_b_cdk-python-deploy.md):  
    *Build and deploy infrastructure using AWS CDK (Python version).*

</details>

---

#### 🧑‍🏫 Author: Georges Bou Ghantous
<sub><i>This repository delivers practical AWS training through structured, end-to-end lab sessions that progressively build cloud expertise across compute, networking, storage, databases, containers, serverless, and automation.</i></sub>

