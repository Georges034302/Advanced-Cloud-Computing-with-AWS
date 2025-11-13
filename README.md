# Advanced Cloud Computing with AWS: Hands-On Lab Series

## 📚 Technical Introduction

This comprehensive lab series provides hands-on experience with Amazon Web Services (AWS), covering fundamental to advanced cloud computing concepts. Through 10 progressive sessions where you'll gain practical skills in deploying, managing, and optimizing cloud infrastructure.

---

**Prerequisites:**
- Basic understanding of cloud computing concepts
- Familiarity with command line interfaces
- Programming knowledge (Python, Node.js, or similar)
- AWS account (Free Tier eligible for most labs)

---

<details>
  <summary>
  Lab Session 01: AWS Compute Foundations – EC2, Networking, and Application Deployment 
  </summary>

  Gain hands-on experience across multiple AWS compute services by progressively building, securing, and deploying applications using EC2, Lightsail, and Elastic Beanstalk.

  **Labs for this session:**
  - [lab_1_a_ec2-on-custom-vpc.md](session01/lab_1_a_ec2-on-custom-vpc.md):  
    *Launch and configure a Linux EC2 instance in a custom VPC, including subnet, internet gateway, route table, and security group setup.*
  - [lab_1_b_deploy_secure_multi-ec2_python_api.md](session01/lab_1_b_deploy_secure_multi-ec2_python_api.md):  
    *Deploy multiple Python Flask APIs on EC2 instances across different subnets, secure them with Security Groups and Network ACLs, and access each API directly using public IP–based endpoints.*
  - [lab_1_c_host-static-website-lightsail.md](session01/lab_1_c_host-static-website-lightsail.md):  
    *Deploy and host a static website using AWS Lightsail.*
  - [lab_1_d_deploy-python-app-elastic-beanstalk.md](session01/Lab_1_s_deploy-python-app-elastic-beanstalk.md):  
    *Deploy a Python application using AWS Elastic Beanstalk for managed scaling and deployment.*

</details>

<details>
  <summary>Lab Session 02: Identity and Access Control with IAM</summary>

  Master AWS Identity and Access Management (IAM) by implementing least-privilege security, multi-factor authentication, and federated access patterns.

  **Labs for this session:**
  - [lab_2_a_iam-users-policies.md](session02/lab_2_a_iam-users-policies.md):  
    *Create IAM users, groups, and custom managed policies following least-privilege principles. Configure permission boundaries and test permissions using the policy simulator.*
  - [lab_2_b_iam-roles-mfa.md](session02/lab_2_b_iam-roles-mfa.md):  
    *Configure IAM roles with trust policies for EC2 and cross-account access. Enforce multi-factor authentication (MFA) for privileged operations using STS AssumeRole.*
  - [lab_2_c_cognito-federated-access.md](session02/lab_2_c_cognito-federated-access.md):  
    *Implement federated access using Amazon Cognito Identity Pools and external identity providers (Google OAuth). Obtain temporary AWS credentials without creating IAM users.*

</details>

<details>
  <summary>Lab Session 03: Cloud Storage Solutions – S3, EBS, and EFS</summary>

  Master AWS storage services by implementing object storage with S3, block storage with EBS, and shared file systems with EFS. Configure lifecycle policies, encryption, and multi-AZ architectures for high availability.

  **Labs for this session:**
  - [lab_3_a_s3-lifecycle.md](session03/lab_3_a_s3-lifecycle.md):  
    *Configure S3 buckets with versioning, encryption (SSE-S3, SSE-KMS), bucket policies, and lifecycle rules for storage class transitions (STANDARD_IA, GLACIER, DEEP_ARCHIVE).*
  - [lab_3_b_ebs-snapshots.md](session03/lab_3_b_ebs-snapshots.md):  
    *Create and manage EBS volumes, attach to EC2 instances, perform snapshots, restore volumes, and automate snapshot lifecycle with Data Lifecycle Manager (DLM).*
  - [lab_3_c_s3-static-website-cloudfront.md](session03/lab_3_c_s3-static-website-cloudfront.md):  
    *Deploy a static website on S3 with global distribution through CloudFront CDN. Configure Origin Access Identity (OAI), custom error pages, HTTPS delivery, cache behaviors, and invalidations.*
  - [lab_3_d_efs-shared-file-system.md](session03/lab_3_d_efs-shared-file-system.md):  
    *Create Amazon EFS file system with encryption and multi-AZ mount targets. Test concurrent access from multiple EC2 instances, implement lifecycle policies, configure access points, and perform performance testing.*

</details>

<details>
  <summary>Lab Session 04: Database Services – RDS, DynamoDB, and ElastiCache</summary>

  Master AWS database services by implementing relational databases with Multi-AZ high availability, NoSQL databases with DynamoDB, and in-memory caching with ElastiCache Redis for session management.

  **Labs for this session:**
  - [lab_4_a_rds-mysql-private.md](session04/lab_4_a_rds-mysql-private.md):  
    *Provision and connect to an RDS MySQL database in a private subnet. Configure security groups, connect from EC2, create tables, and perform basic SQL operations.*
  - [lab_4_b_dynamodb-cli.md](session04/lab_4_b_dynamodb-cli.md):  
    *Build and query a DynamoDB table using AWS CLI and SDK. Work with partition keys, sort keys, queries, scans, and global secondary indexes (GSI).*
  - [lab_4_c_rds-multi-az-bastion.md](session04/lab_4_c_rds-multi-az-bastion.md):  
    *Deploy RDS MySQL with Multi-AZ synchronous replication for high availability. Access database securely through bastion host, test automatic failover between availability zones, and validate data persistence.*
  - [lab_4_d_elasticache-redis-sessions.md](session04/lab_4_d_elasticache-redis-sessions.md):  
    *Create ElastiCache Redis cluster for high-performance in-memory caching. Integrate with Flask application for session management and test basic Redis operations (SET, GET, EXPIRE).*

</details>

<details>
  <summary>Lab Session 05: Load Balancing and Auto Scaling (Free Tier)</summary>

  Implement high availability and elasticity using free tier-eligible Classic Load Balancers and Auto Scaling Groups with CloudWatch integration. Learn automatic scaling based on demand, scheduled scaling patterns, and global traffic distribution with Route 53.

  **Labs for this session:**
  - [lab_5_a_clb-deployment.md](session05/lab_5_a_clb-deployment.md):  
    *Deploy web application behind Classic Load Balancer (CLB) with free tier eligibility (750 hours/month). Configure multi-AZ deployment, health checks, load distribution, and test automatic failover.*
  - [lab_5_b_autoscaling-cloudwatch.md](session05/lab_5_b_autoscaling-cloudwatch.md):  
    *Create Auto Scaling Group with Launch Template and configure target-tracking scaling policy (CPU-based) and scheduled scaling. Monitor scaling activities through CloudWatch metrics and test automatic capacity adjustment.*
  - [lab_5_c_clb-asg-integration.md](session05/lab_5_c_clb-asg-integration.md):  
    *Integrate Classic Load Balancer with Auto Scaling Group for automatic traffic distribution across scaling instances. Configure health checks at both CLB and ASG levels, test automatic instance replacement on failure, and monitor load distribution during scaling events.*
  - [lab_5_d_route53-multi-region.md](session05/lab_5_d_route53-multi-region.md):  
    *Implement global high availability with Route 53 latency-based routing across two regions (ap-southeast-2, us-east-1). Deploy identical applications in both regions, configure Route 53 health checks for automatic failover, and test traffic routing to nearest region.*

</details>

<details>
  <summary>Lab Session 06: Container Orchestration with ECS, Fargate, and EKS</summary>

  Master container deployment on AWS through multiple orchestration platforms. Build Docker images, push to ECR, and deploy using ECS with EC2 (free tier), Elastic Beanstalk (free tier), ECS Fargate (serverless, paid), and Amazon EKS (Kubernetes, paid).

  **Labs for this session:**
  - [lab_6_a_ecr-ecs-deployment.md](session06/lab_6_a_ecr-ecs-deployment.md):  
    *Build Python Flask joke API Docker image, push to ECR, and deploy to ECS using EC2 launch type with t2.micro instance. Complete container workflow from build to deployment. **FREE TIER** (750 hours/month).*
  - [lab_6_b_elastic-beanstalk-docker.md](session06/lab_6_b_elastic-beanstalk-docker.md):  
    *Deploy containerized Python Flask API to Elastic Beanstalk with Docker. Automatic infrastructure management, health monitoring, and rolling updates. **FREE TIER** (t2.micro, 750 hours/month).*
  - [lab_6_c_ecs-fargate-deployment.md](session06/lab_6_c_ecs-fargate-deployment.md):  
    *Deploy containerized joke API to ECS using Fargate serverless containers. No infrastructure management, pay per vCPU/GB-hour. **PAID** (~$0.04/hour minimum, delete immediately after lab).*
  - [lab_6_d_eks-microservices.md](session06/lab_6_d_eks-microservices.md):  
    *Deploy microservices (dad-jokes and tech-jokes) to Amazon EKS with Kubernetes. Create cluster, deploy pods, configure services, and test inter-service communication. **PAID** (EKS $0.10/hour + worker nodes, delete immediately after lab).*

</details>

<details>
  <summary>Lab Session 07: Serverless Computing with Lambda </summary>

  Build serverless applications using AWS Lambda with API Gateway, S3 triggers, SQS integration, and EventBridge automation. All labs are free tier compatible with 1M Lambda requests/month and no infrastructure management.

  **Labs for this session:**
  - [lab_7_a_lambda-api-gateway.md](session07/lab_7_a_lambda-api-gateway.md):  
    *Build serverless REST API with Python Lambda joke API (GET /joke, GET /jokes, POST /joke) exposed through API Gateway HTTP API. Deploy function, configure routes, enable CORS, and test all endpoints. 
  - [lab_7_b_s3-lambda-trigger.md](session07/lab_7_b_s3-lambda-trigger.md):  
    *Process CSV files with S3 trigger and Node.js Lambda. Upload student records (ID, NAME, MARK, GRADE) to S3, automatically trigger Lambda to parse CSV and store in DynamoDB. Event-driven data ingestion pipeline. 
  - [lab_7_c_sqs-lambda-integration.md](session07/lab_7_c_sqs-lambda-integration.md):  
    *Create event-driven order processing workflow using SQS and Python Lambda. Configure Dead Letter Queue (DLQ), event source mapping with batch processing, and test message handling with automatic retries. 
  - [lab_7_d_sns-eventbridge-alerts.md](session07/lab_7_d_sns-eventbridge-alerts.md):  
    *Monitor EC2 instances with SNS email alerts and EventBridge. Configure EventBridge rule to capture EC2 state changes (running, stopped, terminated), publish to SNS topic, and receive email notifications automatically. 
</details>

<details>
  <summary>Lab Session 08: Monitoring and Logging Operations</summary>

  Monitor, audit, and analyze your AWS environment using native observability tools.

  **Labs for this session:**
  - [lab_8_a_cloudwatch-dashboard.md](session08/lab_8_a_cloudwatch-dashboard.md):  
    *Configure CloudWatch dashboards, metrics, and alarms.*
  - [lab_8_b_cloudtrail-logs.md](session08/lab_8_b_cloudtrail-logs.md):  
    *Track and audit API calls using CloudTrail and Log Insights.*

</details>

<details>
  <summary>Lab Session 09: Infrastructure as Code with CloudFormation and CDK</summary>

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

