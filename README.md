# Advanced Cloud Computing with AWS: Hands-On Lab Series

## 📚 Technical Introduction

This comprehensive lab series provides hands-on experience with Amazon Web Services (AWS), covering fundamental to advanced cloud computing concepts. Through 10 progressive sessions with 20 detailed labs, you'll gain practical skills in deploying, managing, and optimizing cloud infrastructure.

**What You'll Learn:**
- **Core Services**: Master EC2, S3, RDS, DynamoDB, Lambda, and more
- **Networking**: Design VPCs, configure load balancing, implement service discovery
- **Security**: Apply IAM best practices, encryption, and compliance controls
- **Automation**: Use CloudFormation, CI/CD pipelines, and Infrastructure as Code
- **Containers**: Deploy with ECS, Fargate, and orchestrate microservices
- **Serverless**: Build event-driven architectures with Lambda and Step Functions
- **Best Practices**: Apply the AWS Well-Architected Framework principles
- **Advanced Topics**: Explore ML with SageMaker, IoT Core, GraphQL APIs, and more

**Prerequisites:**
- Basic understanding of cloud computing concepts
- Familiarity with command line interfaces
- Programming knowledge (Python, Node.js, or similar)
- AWS account (Free Tier eligible for most labs)

**Technical Approach:**
This series emphasizes practical, production-ready implementations aligned with the AWS Well-Architected Framework. Each lab includes detailed steps, validation checkpoints, and cleanup procedures to manage costs. You'll work with both the AWS Console and CLI, building skills applicable to real-world cloud engineering scenarios.

---

## 🎯 Lab Sessions Overview

<details>
<summary><b>Session 1: AWS IAM and Identity Management</b></summary>

### 📖 Session 1: AWS IAM and Identity Management

Learn the fundamentals of AWS Identity and Access Management (IAM), the foundation of AWS security. Master user management, groups, roles, policies, and multi-factor authentication.

#### Lab 1.A: Introduction to AWS Console and IAM Basics
- Navigate the AWS Management Console
- Understand AWS global infrastructure
- Create IAM users with appropriate permissions
- Configure Multi-Factor Authentication (MFA)
- Apply the principle of least privilege
- [View Lab →](session1/lab_1_a.md)

#### Lab 1.B: IAM Groups, Roles, and Policy Management
- Create and manage IAM Groups
- Implement IAM Roles for AWS service access
- Understand policy types (managed vs. inline)
- Learn policy evaluation logic and permission boundaries
- Use the IAM Policy Simulator
- [View Lab →](session1/lab_1_b.md)

</details>

<details>
<summary><b>Session 2: Amazon EC2 and Compute Services</b></summary>

### 💻 Session 2: Amazon EC2 and Compute Services

Master Amazon EC2, AWS's primary compute service. Learn to launch instances, configure auto-scaling, implement load balancing, and build highly available architectures.

#### Lab 2.A: Launching and Managing EC2 Instances
- Launch EC2 instances using the AWS Console
- Configure security groups for network access
- Connect to instances using SSH/RDP
- Deploy applications with user data scripts
- Create AMIs for rapid deployment
- Monitor instance metrics with CloudWatch
- [View Lab →](session2/lab_2_a.md)

#### Lab 2.B: EC2 Auto Scaling and Load Balancing
- Create Application Load Balancers
- Set up target groups and health checks
- Configure Auto Scaling groups with scaling policies
- Implement self-healing architectures
- Test automatic scaling behavior
- Build highly available multi-AZ deployments
- [View Lab →](session2/lab_2_b.md)

</details>

<details>
<summary><b>Session 3: Amazon VPC and Networking</b></summary>

### 🌐 Session 3: Amazon VPC and Networking

Design and implement custom network architectures with Amazon VPC. Learn subnetting, routing, NAT Gateway, VPC Peering, and VPC Endpoints for secure, scalable networking.

#### Lab 3.A: VPC Fundamentals and Networking
- Create custom VPCs with CIDR block planning
- Configure public and private subnets across AZs
- Set up Internet Gateway and route tables
- Implement Network ACLs for subnet-level security
- Understand VPC routing and traffic control
- [View Lab →](session3/lab_3_a.md)

#### Lab 3.B: NAT Gateway, VPC Peering, and VPC Endpoints
- Configure NAT Gateway for private subnet internet access
- Implement VPC Peering between VPCs
- Create VPC Endpoints for AWS services
- Optimize costs with Gateway Endpoints
- Design secure multi-VPC architectures
- [View Lab →](session3/lab_3_b.md)

</details>

<details>
<summary><b>Session 4: Amazon S3 and Object Storage</b></summary>

### 🗄️ Session 4: Amazon S3 and Object Storage

Master Amazon S3 for scalable object storage. Learn bucket management, versioning, lifecycle policies, replication, encryption, and CloudFront integration for global content delivery.

#### Lab 4.A: Amazon S3 Fundamentals and Storage Management
- Create and configure S3 buckets
- Implement versioning and lifecycle policies
- Configure bucket and object permissions
- Host static websites on S3
- Use AWS CLI for S3 operations
- Optimize storage costs with storage classes
- [View Lab →](session4/lab_4_a.md)

#### Lab 4.B: S3 Advanced Features - Replication, Encryption, and CloudFront
- Configure Cross-Region Replication (CRR)
- Implement encryption with KMS
- Enable S3 Transfer Acceleration
- Integrate CloudFront for global distribution
- Use S3 Object Lock for compliance
- Analyze storage patterns with S3 Analytics
- [View Lab →](session4/lab_4_b.md)

</details>

<details>
<summary><b>Session 5: Amazon RDS and Relational Databases</b></summary>

### 🗃️ Session 5: Amazon RDS and Relational Databases

Deploy and manage relational databases with Amazon RDS. Learn about automated backups, Multi-AZ deployments, read replicas, and performance optimization with parameter groups.

#### Lab 5.A: Amazon RDS - Relational Database Setup and Management
- Launch RDS database instances
- Configure automated backups and snapshots
- Implement Multi-AZ for high availability
- Create read replicas for scalability
- Monitor database performance with CloudWatch
- Connect applications to RDS databases
- [View Lab →](session5/lab_5_a.md)

#### Lab 5.B: RDS Performance Optimization and Parameter Groups
- Create custom DB parameter groups
- Enable Performance Insights and Enhanced Monitoring
- Optimize query performance
- Implement connection pooling
- Configure database activity streams
- Test point-in-time recovery
- [View Lab →](session5/lab_5_b.md)

</details>

<details>
<summary><b>Session 6: Amazon DynamoDB and NoSQL</b></summary>

### 📊 Session 6: Amazon DynamoDB and NoSQL

Master Amazon DynamoDB, AWS's fully managed NoSQL database. Learn data modeling, secondary indexes, transactions, DynamoDB Streams, Global Tables, and DAX caching.

#### Lab 6.A: Amazon DynamoDB Fundamentals and Data Modeling
- Create DynamoDB tables with partition and sort keys
- Perform CRUD operations
- Implement Global Secondary Indexes (GSI)
- Use conditional writes and transactions
- Enable DynamoDB Streams
- Optimize with batch operations
- [View Lab →](session6/lab_6_a.md)

#### Lab 6.B: DynamoDB Advanced Features and Best Practices
- Configure Global Tables for multi-region replication
- Implement DynamoDB Accelerator (DAX) for caching
- Enable Point-in-Time Recovery (PITR)
- Use Time To Live (TTL) for data expiration
- Implement advanced data modeling patterns
- Optimize costs with capacity planning
- [View Lab →](session6/lab_6_b.md)

</details>

<details>
<summary><b>Session 7: AWS Lambda and Serverless Computing</b></summary>

### ⚡ Session 7: AWS Lambda and Serverless Computing

Build event-driven serverless applications with AWS Lambda. Learn function creation, event triggers, Step Functions orchestration, and SAM for infrastructure as code.

#### Lab 7.A: AWS Lambda Fundamentals and Serverless Computing
- Create and deploy Lambda functions
- Configure event triggers (S3, API Gateway, DynamoDB)
- Implement error handling and retries
- Use Lambda Layers for code reusability
- Monitor with CloudWatch Logs and metrics
- Schedule tasks with EventBridge
- [View Lab →](session7/lab_7_a.md)

#### Lab 7.B: Advanced Lambda Patterns and Serverless Applications
- Build serverless apps with SAM (Serverless Application Model)
- Orchestrate workflows with Step Functions
- Implement Lambda@Edge for CloudFront
- Configure provisioned concurrency
- Use Lambda Destinations
- Implement canary deployments
- [View Lab →](session7/lab_7_b.md)

</details>

<details>
<summary><b>Session 8: Amazon ECS and Container Orchestration</b></summary>

### 🐳 Session 8: Amazon ECS and Container Orchestration

Deploy containerized applications with Amazon ECS and Fargate. Learn Docker, ECR, service discovery, multi-container tasks, and microservices patterns.

#### Lab 8.A: Amazon ECS with Fargate - Container Basics
- Containerize applications with Docker
- Push images to Amazon ECR
- Create ECS clusters and task definitions
- Deploy services with load balancing
- Implement auto-scaling for containers
- Perform rolling updates with zero downtime
- [View Lab →](session8/lab_8_a.md)

#### Lab 8.B: ECS Service Discovery and Multi-Container Applications
- Configure AWS Cloud Map for service discovery
- Create multi-container task definitions
- Implement microservices communication
- Use ECS Exec for debugging
- Deploy sidecar patterns
- Monitor with X-Ray distributed tracing
- [View Lab →](session8/lab_8_b.md)

</details>

<details>
<summary><b>Session 9: AWS CloudFormation and Infrastructure as Code</b></summary>

### 🏗️ Session 9: AWS CloudFormation and Infrastructure as Code

Automate infrastructure deployment with AWS CloudFormation. Learn template creation, stack management, StackSets, and CI/CD integration for repeatable deployments.

#### Lab 9.A: AWS CloudFormation Fundamentals and Infrastructure as Code
- Create CloudFormation templates in YAML/JSON
- Use parameters, mappings, and outputs
- Deploy and manage stacks
- Implement cross-stack references
- Handle stack updates with change sets
- Detect and remediate stack drift
- [View Lab →](session9/lab_9_a.md)

#### Lab 9.B: Advanced CloudFormation and Infrastructure Automation
- Create Lambda-backed custom resources
- Implement CloudFormation macros
- Deploy across accounts with StackSets
- Integrate with CodePipeline for CI/CD
- Implement blue-green deployments
- Use CloudFormation Registry extensions
- [View Lab →](session9/lab_9_b.md)

</details>

<details>
<summary><b>Session 10: AWS Well-Architected Framework and Advanced Services</b></summary>

### 🎓 Session 10: AWS Well-Architected Framework and Advanced Services

Apply the AWS Well-Architected Framework and explore cutting-edge services. Learn SageMaker, IoT Core, App Runner, Amplify, EventBridge, and future cloud trends.

#### Lab 10.A: AWS Well-Architected Framework and Cloud Architecture Best Practices
- Understand the six pillars: Operational Excellence, Security, Reliability, Performance, Cost, Sustainability
- Conduct Well-Architected reviews
- Implement defense-in-depth security
- Build multi-AZ resilient architectures
- Optimize performance and costs
- Design sustainable cloud solutions
- [View Lab →](session10/lab_10_a.md)

#### Lab 10.B: Advanced AWS Services and Future-Ready Cloud Engineering
- Deploy ML models with Amazon SageMaker
- Build IoT applications with AWS IoT Core
- Use AWS App Runner for containers
- Create full-stack apps with AWS Amplify
- Implement event-driven architectures with EventBridge
- Build GraphQL APIs with AWS AppSync
- Explore emerging AWS technologies
- [View Lab →](session10/lab_10_b.md)

</details>

---

## 🚀 Getting Started

1. **Prerequisites**: Ensure you have an AWS account (Free Tier recommended)
2. **Setup**: Install AWS CLI and configure credentials
3. **Session Order**: Complete labs sequentially for best learning experience
4. **Practice**: Each lab includes hands-on exercises and validation steps
5. **Cleanup**: Always follow cleanup procedures to manage costs

## 💡 Best Practices

- **Cost Management**: Use AWS Free Tier and clean up resources after each lab
- **Security**: Never commit AWS credentials; use IAM roles when possible
- **Documentation**: Take notes and customize labs for your use cases
- **Experimentation**: Try variations beyond the lab instructions
- **Community**: Share learnings and collaborate with peers

## 📖 Additional Resources

- [AWS Documentation](https://docs.aws.amazon.com/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [AWS Free Tier](https://aws.amazon.com/free/)
- [AWS Training and Certification](https://aws.amazon.com/training/)
- [AWS Architecture Center](https://aws.amazon.com/architecture/)

## 🤝 Contributing

This lab series is designed for hands-on learning. Feel free to:
- Submit issues for clarifications or improvements
- Share your lab implementations and variations
- Contribute additional exercises or use cases

## ⚖️ License

This educational content is provided for learning purposes. AWS service usage is subject to AWS's terms and conditions.

---

**Ready to start your cloud engineering journey? Begin with [Session 1: AWS IAM and Identity Management](session1/lab_1_a.md)!**
