# Advanced Cloud Computing with AWS: Hands-On Lab Series

## 📚 Technical Introduction

This comprehensive lab series provides hands-on experience with Amazon Web Services (AWS), covering fundamental to advanced cloud computing concepts. Through 16 progressive sessions, you'll gain practical skills in deploying, managing, and optimizing cloud infrastructure across compute, storage, databases, security, containers, serverless, DevOps, AI/ML, networking, and cost optimization.

---

**Prerequisites:**
- Basic understanding of cloud computing concepts
- Familiarity with command line interfaces (Bash, AWS CLI)
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
  - [lab_4_a_rds-mysql-bastion.md](session04/lab_4_a_rds-mysql-bastion.md):  
    *Provision and connect to an RDS MySQL database in a private subnet. Configure security groups, connect from EC2, create tables, and perform basic SQL operations.*
  - [lab_4_b_dynamodb-cli.md](session04/lab_4_b_dynamodb-cli.md):  
    *Build and query a DynamoDB table using AWS CLI and SDK. Work with partition keys, sort keys, queries, scans, and global secondary indexes (GSI).*
  - [lab_4_c_rds-multi-az-bastion.md](session04/lab_4_c_rds-multi-az-bastion.md):  
    *Deploy RDS MySQL with Multi-AZ synchronous replication for high availability. Access database securely through bastion host, test automatic failover between availability zones, and validate data persistence.*
  - [lab_4_d_elasticache-redis-sessions.md](session04/lab_4_d_elasticache-redis-sessions.md):  
    *Create ElastiCache Redis cluster for high-performance in-memory caching. Integrate with Flask application for session management and test basic Redis operations (SET, GET, EXPIRE).*

</details>

<details>
  <summary>Lab Session 05: Load Balancing and Auto Scaling </summary>

  Implement high availability and elasticity using Classic Load Balancers and Auto Scaling Groups with CloudWatch integration. Learn automatic scaling based on demand, scheduled scaling patterns, and global traffic distribution with Route 53.

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

  Master container deployment on AWS through multiple orchestration platforms. Build Docker images, push to ECR, and deploy using ECS with EC2, Elastic Beanstalk, ECS Fargate, and Amazon EKS.

  **Labs for this session:**
  - [lab_6_a_ecr-ecs-deployment.md](session06/lab_6_a_ecr-ecs-deployment.md):  
    *Build Python Flask joke API Docker image, push to ECR, and deploy to ECS using EC2 launch type with t2.micro instance. Complete container workflow from build to deployment. 
  - [lab_6_b_elastic-beanstalk-docker.md](session06/lab_6_b_elastic-beanstalk-docker.md):  
    *Deploy containerized Python Flask API to Elastic Beanstalk with Docker. Automatic infrastructure management, health monitoring, and rolling updates. 
  - [lab_6_c_ecs-fargate-deployment.md](session06/lab_6_c_ecs-fargate-deployment.md):  
    *Deploy containerized joke API to ECS using Fargate serverless containers. No infrastructure management, pay per vCPU/GB-hour. 
  - [lab_6_d_eks-microservices.md](session06/lab_6_d_eks-microservices.md):  
    *Deploy microservices (dad-jokes and tech-jokes) to Amazon EKS with Kubernetes. Create cluster, deploy pods, configure services, and test inter-service communication. 

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
  <summary>Lab Session 08: Monitoring, Logging, and Security Auditing</summary>

  Monitor AWS resources, audit API activity, analyze network traffic, and track access patterns using native logging and observability services. All labs are free tier compatible with CloudWatch, CloudTrail, VPC Flow Logs, and Athena.

  **Labs for this session:**
  - [lab_8_a_cloudwatch-dashboard-alarms.md](session08/lab_8_a_cloudwatch-dashboard-alarms.md):  
    *Monitor EC2 instances with CloudWatch dashboards showing CPU, network, and disk metrics. Create alarms for high CPU utilization with SNS email notifications. Test alarm triggers with stress testing. 
  - [lab_8_b_cloudtrail-auditing.md](session08/lab_8_b_cloudtrail-auditing.md):  
    *Enable CloudTrail for API activity logging to S3 and CloudWatch Logs. Query logs with Logs Insights (all calls, S3 operations, failed requests). Create metric filters and alarms for DeleteBucket operations. Security audit trail. 
  - [lab_8_c_vpc-flow-logs.md](session08/lab_8_c_vpc-flow-logs.md):  
    *Capture VPC network traffic with Flow Logs to CloudWatch. Analyze accepted and rejected connections with Logs Insights. Create alarms for suspicious activity (port scans, high rejected traffic). Network security monitoring. 
  - [lab_8_d_s3-access-logging-athena.md](session08/lab_8_d_s3-access-logging-athena.md):  
    *Enable S3 server access logging to track all bucket requests. Create Athena table to query logs with SQL (top IPs, status codes, bandwidth usage, errors). Identify unauthorized access attempts (403, 404). Compliance audit trails. 

</details>

<details>
  <summary>Lab Session 09: Infrastructure as Code – CloudFormation, CDK, and Terraform</summary>

  Master Infrastructure as Code (IaC) tools to define, deploy, and manage AWS resources using code. Learn CloudFormation advanced patterns, AWS CDK with Python, and Terraform multi-cloud basics. 

  **Labs for this session:**
  - [lab_9_a_cloudformation-vpc-2tier.md](session09/lab_9_a_cloudformation-vpc-2tier.md):  
    *Deploy two-tier VPC architecture with CloudFormation (7 steps, 400 lines). Web server in public subnet, Flask API in private subnet, Classic Load Balancer, security group isolation, and complete network infrastructure from single YAML template. 
  - [lab_9_b_cloudformation-nested-stacks.md](session09/lab_9_b_cloudformation-nested-stacks.md):  
    *Build modular infrastructure with CloudFormation nested stacks. Create parent stack orchestrating child stacks (network.yaml, compute.yaml), use cross-stack references with Exports/Imports, preview changes with Change Sets before applying, detect configuration drift from manual changes. 
  - [lab_9_c_cdk-python-serverless.md](session09/lab_9_c_cdk-python-serverless.md):  
    *Deploy serverless API using AWS CDK with Python. Define Lambda functions, DynamoDB table, and API Gateway using CDK constructs instead of YAML/JSON. Experience CDK workflow: synth (generate CloudFormation), diff (preview changes), deploy, and destroy. Compare CDK advantages over raw CloudFormation. 
  - [lab_9_d_terraform-vpc.md](session09/lab_9_d_terraform-vpc.md):  
    *Learn Terraform basics with VPC deployment in ap-southeast-2. Write HCL configuration (providers, resources, variables, outputs), configure remote state in S3 with DynamoDB locking, use terraform plan/apply/destroy workflow, and import existing resources. Alternative IaC tool for multi-cloud environments. 

</details>

<details>
  <summary>Lab Session 10: CI/CD Pipelines – App Runner, CodePipeline, GitHub Actions, and CodeDeploy</summary>

  Build complete CI/CD pipelines using AWS native DevOps tools and GitHub Actions. Learn different deployment approaches: direct GitHub integration, container deployments, AWS-native vs third-party CI/CD, and zero-downtime deployment strategies.

  **Labs for this session:**
  - [lab_10_a_github-apprunner.md](session10/lab_10_a_github-apprunner.md):  
    *Deploy Flask app with direct GitHub → App Runner integration. Connect repository to App Runner for code-based deployment with built-in build system. Python app auto-builds from requirements.txt and deploys with gunicorn. Simple PaaS deployment without separate CI/CD services. 
  - [lab_10_b_docker_ecr_apprunner.md](session10/lab_10_b_docker_ecr_apprunner.md):  
    *Build and deploy multi-API services with local Docker → ECR → App Runner. Create Student and Report microservices with pytest tests, build Docker images locally, push to ECR, deploy two independent App Runner services. Container-based deployment with local development workflow. 
  - [lab_10_c_github-actions-apprunner.md](session10/lab_10_c_github-actions-apprunner.md):  
    *Deploy containers with GitHub Actions → ECR → App Runner. Build Docker image with GitHub Actions, push to ECR, deploy to App Runner in image mode. Third-party CI/CD with container deployment. 
  - [lab_10_d_codedeploy-bluegreen.md](session10/lab_10_d_codedeploy-bluegreen.md):  
    *Implement blue/green deployment with CodeDeploy and Auto Scaling Groups. Deploy new version to "green" environment, shift traffic automatically, and rollback on failure. Zero-downtime VM deployment strategy. 
  - [lab_10_e_docker_ecr_eks_helm.md](session10/lab_10_e_docker_ecr_eks_helm.md):  
    *Deploy to Kubernetes with local Docker → ECR → Helm → EKS. Create Helm charts for Flask app, build Docker images locally, push to ECR, deploy to EKS with helm upgrade. Kubernetes deployment with rolling updates and LoadBalancer service. 
  - [lab_10_f_lambda_sam_github_actions.md](session10/lab_10_f_lambda_sam_github_actions.md):  
    *Build serverless pipeline with GitHub Actions → SAM → Lambda + API Gateway. Create SAM templates, configure GitHub Actions workflow, deploy with SAM CLI in CI/CD. Automated serverless deployments without CodePipeline or CodeBuild. 
  - [lab_10_g_terraform_cicd.md](session10/lab_10_g_terraform_cicd.md):  
    *Automate Terraform deployments with GitHub → CodePipeline → CodeBuild → VPC infrastructure. Configure S3 backend for remote state, DynamoDB for state locking, run terraform plan/apply in CodeBuild. GitOps workflow for infrastructure automation with multi-cloud IaC tool. 

</details>

<details>
  <summary>Lab Session 11: AI/ML Services – Rekognition, Comprehend, Translate, and SageMaker</summary>

  Leverage AWS AI/ML services for computer vision, natural language processing, translation, and machine learning model deployment. Build intelligent applications without ML expertise using pre-trained models and APIs. 

  **Labs for this session:**
  - [lab_11_a_rekognition-image-analysis.md](session11/lab_11_a_rekognition-image-analysis.md):  
    *Analyze images with Amazon Rekognition: detect objects, text (OCR), faces with attributes (age, gender, emotions), celebrities, and compare faces. Upload images to S3 and call Rekognition APIs for computer vision insights. 
  - [lab_11_b_comprehend-sentiment-analysis.md](session11/lab_11_b_comprehend-sentiment-analysis.md):  
    *Perform sentiment analysis and NLP with Amazon Comprehend. Analyze customer reviews to detect sentiment (positive/negative/neutral/mixed), extract key phrases, identify entities (people, organizations, locations), and determine dominant language automatically. 
  - [lab_11_c_translate-multi-language.md](session11/lab_11_c_translate-multi-language.md):  
    *Build multi-language translation pipeline with Amazon Translate. Translate text between 75+ languages, detect source language automatically, batch translate documents in S3, handle custom terminology, and integrate with web applications for real-time translation. 
  - [lab_11_d_sagemaker-model-deployment.md](session11/lab_11_d_sagemaker-model-deployment.md):  
    *Deploy machine learning model with SageMaker. Train XGBoost classifier on iris dataset, create model artifact, deploy to real-time inference endpoint, test predictions via API, and monitor invocations. Complete ML workflow from training to production. 

</details>

<details>
  <summary>Lab Session 12: Hybrid Cloud Networking – VPC Peering, Transit Gateway, VPN, and Direct Connect</summary>

  Connect VPCs, on-premises networks, and multi-region architectures using AWS hybrid networking services. Implement VPC peering, centralized routing with Transit Gateway, site-to-site VPN, and simulated Direct Connect. Build scalable hub-and-spoke network topologies.

  **Labs for this session:**
  - [lab_12_a_vpc-peering.md](session12/lab_12_a_vpc-peering.md):  
    *Connect two VPCs in same region with VPC Peering (free). Create peering connection, update route tables for bidirectional traffic, test connectivity between EC2 instances in different VPCs. Simple point-to-point VPC connectivity. 
  - [lab_12_b_transit-gateway.md](session12/lab_12_b_transit-gateway.md):  
    *Build hub-and-spoke network with AWS Transit Gateway (paid: $0.05/hour + data transfer). Connect three VPCs through central Transit Gateway, configure route propagation, test transitive routing between spoke VPCs, and visualize network topology. Scalable multi-VPC architecture. 
  - [lab_12_c_site-to-site-vpn.md](session12/lab_12_c_site-to-site-vpn.md):  
    *Create encrypted site-to-site VPN connection between on-premises network (simulated with VPC + EC2 as VPN client) and AWS VPC. Configure Virtual Private Gateway, Customer Gateway, VPN tunnels with BGP routing, test encrypted connectivity. Hybrid cloud foundation. 
  - [lab_12_d_direct-connect-gateway.md](session12/lab_12_d_direct-connect-gateway.md):  
    *Simulate AWS Direct Connect with VPC Peering and routing configuration (actual Direct Connect requires physical connection). Understand Direct Connect Gateway concepts for connecting on-premises to multiple VPCs across regions with private, dedicated network connection (1-100 Gbps). 

</details>

<details>
  <summary>Lab Session 13: Security and Compliance – AWS Config, GuardDuty, Security Hub, and KMS</summary>

  Implement comprehensive security monitoring, compliance auditing, threat detection, and encryption key management. Use AWS native security services to assess configuration compliance, detect malicious activity, centralize security findings, and manage encryption keys.

  **Labs for this session:**
  - [lab_13_a_aws-config.md](session13/lab_13_a_aws-config.md):  
    *Track resource configuration changes and compliance with AWS Config. Enable Config recorder, configure S3 delivery channel, create compliance rules (encrypted EBS, public S3 buckets, required tags), view configuration timeline, remediate non-compliant resources, and export compliance reports. 
  - [lab_13_b_guardduty.md](session13/lab_13_b_guardduty.md):  
    *Detect security threats with Amazon GuardDuty intelligent threat detection. Enable GuardDuty, generate sample findings (cryptocurrency mining, port scanning, unauthorized access), configure SNS notifications for critical findings, analyze threats with severity levels, and implement automated remediation. 
  - [lab_13_c_security-hub.md](session13/lab_13_c_security-hub.md):  
    *Centralize security findings with AWS Security Hub. Aggregate findings from GuardDuty, Config, IAM Access Analyzer, and other services. View security score, assess compliance with AWS Foundational Security Best Practices, CIS benchmarks, and export findings for remediation. 
  - [lab_13_d_kms-envelope-encryption.md](session13/lab_13_d_kms-envelope-encryption.md):  
    *Manage encryption keys with AWS KMS and implement envelope encryption. Create customer managed keys (CMK), configure key policies and grants, encrypt/decrypt data with KMS API, implement envelope encryption pattern (encrypt data keys), rotate keys automatically, and audit key usage with CloudTrail. 

</details>

<details>
  <summary>Lab Session 14: Disaster Recovery and Business Continuity – AWS Backup, Multi-Region, and Failover</summary>

  Implement disaster recovery strategies with automated backups, cross-region replication, and failover architectures. Learn backup policies, point-in-time recovery, multi-region high availability, and automated disaster recovery workflows. Build resilient applications that survive regional failures.

  **Labs for this session:**
  - [lab_14_a_aws-backup.md](session14/lab_14_a_aws-backup.md):  
    *Centralize backup management with AWS Backup service. Create backup vault with encryption, define backup plan with daily/weekly schedules and retention policies, protect EBS volumes and RDS databases, test restore procedures, configure cross-region backup copy, and implement lifecycle policies for cost optimization. 
  - [lab_14_b_rds-cross-region-replica.md](session14/lab_14_b_rds-cross-region-replica.md):  
    *Configure RDS cross-region read replica for disaster recovery. Create primary RDS MySQL in ap-southeast-2, set up asynchronous replica in us-east-1, test read operations from replica, simulate regional failure by promoting replica to standalone instance. Geographic redundancy for databases. 
  - [lab_14_c_s3-cross-region-replication.md](session14/lab_14_c_s3-cross-region-replication.md):  
    *Implement S3 Cross-Region Replication (CRR) for automatic object replication. Enable versioning on source and destination buckets, configure replication rule with IAM role, test automatic replication of new objects, verify replication status and metrics, replicate existing objects with S3 Batch Replication. Geographic data redundancy. 
  - [lab_14_d_route53-failover-routing.md](session14/lab_14_d_route53-failover-routing.md):  
    *Build active-passive disaster recovery with Route 53 failover routing. Deploy primary application in ap-southeast-2 and failover application in us-east-1, configure Route 53 health checks for automatic failure detection, create failover routing policy, simulate primary region failure and verify automatic traffic redirection to failover region. 

</details>

<details>
  <summary>Lab Session 15: Migration and Modernization – DataSync, DMS, MGN, Containers, and Serverless</summary>

  Migrate and modernize applications using AWS migration tools. Transfer large datasets with DataSync, migrate databases with DMS, migrate servers with Application Migration Service, containerize legacy applications with Docker/ECS, and refactor to serverless architectures with Lambda.

  **Labs for this session:**
  - [lab_15_a_datasync-migration.md](session15/lab_15_a_datasync-migration.md):  
    *Transfer large datasets with AWS DataSync for automated migration. Create DataSync agent, configure source location (simulated NFS on EC2) and destination (S3/EFS), create migration task with scheduling, monitor transfer progress, verify data integrity, and compare DataSync performance vs traditional file copy. 
  - [lab_15_b_dms-mysql-to-aurora.md](session15/lab_15_b_dms-mysql-to-aurora.md):  
    *Migrate database with AWS Database Migration Service (DMS). Set up source MySQL and target Aurora MySQL databases, create replication instance, configure source and target endpoints, create migration task with full load + CDC (change data capture), monitor replication, verify data consistency, and minimize downtime. 
  - [lab_15_c_server-migration-service.md](session15/lab_15_c_server-migration-service.md):  
    *Migrate servers to AWS with Application Migration Service (AWS MGN). Install replication agent on source server, configure replication settings, monitor continuous data replication, launch test instance in AWS, validate application functionality, perform cutover to migrate production workload. Lift-and-shift migration. 
  - [lab_15_d_containerize-legacy-app.md](session15/lab_15_d_containerize-legacy-app.md):  
    *Containerize legacy application with Docker and deploy to ECS Fargate. Create Flask application, write Dockerfile with best practices, build and test locally, push to ECR, deploy to ECS Fargate with task definitions, configure networking and security groups, validate container deployment. Application modernization. 
  - [lab_15_e_modernize-to-serverless.md](session15/lab_15_e_modernize-to-serverless.md):  
    *Refactor legacy application to serverless architecture. Extract business logic from monolithic app, convert to Lambda function, create DynamoDB table for data storage, expose via API Gateway REST API, test serverless endpoints, analyze cost benefits and operational improvements. Complete modernization. 

</details>

<details>
  <summary>Lab Session 16: Cost Management and Optimization – Cost Explorer, Trusted Advisor, Budgets, and Well-Architected</summary>

  Master AWS cost management and optimization tools. Analyze spending patterns, identify cost-saving opportunities, set budget alerts, review security and performance best practices, and implement Well-Architected Framework principles for optimized cloud operations.

  **Labs for this session:**
  - [lab_16_a_cost-explorer.md](session16/lab_16_a_cost-explorer.md):  
    *Analyze AWS spending with Cost Explorer API. Query daily and monthly costs, break down by service and region, identify top cost contributors, generate cost forecasts for budget planning, export data to JSON/CSV, calculate cost summaries and trends. Comprehensive cost visibility. 
  - [lab_16_b_trusted-advisor.md](session16/lab_16_b_trusted-advisor.md):  
    *Optimize AWS environment with Trusted Advisor best practice checks. List security, cost, performance, fault tolerance, and service limit checks, identify warnings and errors, filter by category, get detailed recommendations, refresh checks for latest status, export findings. Automated optimization recommendations. 
  - [lab_16_c_aws-budgets.md](session16/lab_16_c_aws-budgets.md):  
    *Set cost alerts with AWS Budgets. Create SNS topic for notifications, configure monthly cost budget with spending limit, add multiple alert thresholds (80%, 90%, 100%), subscribe email for alerts, verify notifications, track budget status. Proactive cost control. 
  - [lab_16_d_well-architected-review.md](session16/lab_16_d_well-architected-review.md):  
    *Review workloads with AWS Well-Architected Tool. Create workload definition, list available lenses (frameworks), review questions across six pillars (Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization, Sustainability), answer best practice questions, generate improvement recommendations, create milestone for progress tracking. 

</details>

---

#### 🧑‍🏫 Author: Georges Bou Ghantous
<sub><i>This repository delivers practical AWS training through 16 structured lab sessions covering compute, networking, storage, databases, IAM, containers, serverless, monitoring, IaC, CI/CD, AI/ML, hybrid networking, security, disaster recovery, migration, and cost optimization.</i></sub>

