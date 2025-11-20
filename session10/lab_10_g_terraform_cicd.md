# Lab 10.G: Terraform CI/CD with CodePipeline - Infrastructure Automation
<img width="1486" height="662" alt="IMG10H" src="https://github.com/user-attachments/assets/f93ba940-654b-43bb-8980-86a9b55034ca" />


## Overview
This lab demonstrates building a CI/CD pipeline for Terraform infrastructure deployments using CodePipeline and CodeBuild. You'll create Terraform configurations for VPC infrastructure, automate terraform plan/apply with CodeBuild, implement remote state in S3, and enable GitOps workflows. This showcases production-grade infrastructure automation with multi-cloud IaC tools.

---

## Objectives
- Create Terraform configuration for VPC infrastructure
- Configure CodePipeline for Terraform deployments
- Automate terraform init/plan/apply in CodeBuild
- Implement S3 backend for remote state management
- Configure DynamoDB for state locking
- Enable GitOps workflow (Git push → Auto deploy)
- Compare Terraform vs CloudFormation/SAM CI/CD

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Git installed (`git --version`)
- GitHub account with repository access
- IAM permissions for CodePipeline, CodeBuild, VPC, EC2, S3, DynamoDB, IAM
- Region: ap-southeast-2

---

## Architecture

```
GitHub → CodePipeline → CodeBuild:
                          → terraform init (S3 backend)
                          → terraform plan
                          → terraform apply
                          ↓
                        VPC + Subnets + EC2
                        
Remote State:
  ├── S3 Bucket (terraform.tfstate)
  └── DynamoDB Table (state locking)
```

**Pipeline Flow:**
1. GitHub hosts Terraform configuration (.tf files)
2. CodePipeline detects changes and triggers CodeBuild
3. CodeBuild installs Terraform CLI
4. Runs terraform init (connects to S3 backend)
5. Executes terraform plan (preview changes)
6. Applies terraform apply (provisions infrastructure)
7. State saved to S3 with DynamoDB locking

---

## Step 1 – Set Variables

```bash
# Set AWS region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Dynamically get GitHub repository info
GITHUB_URL=$(git remote get-url origin)
GITHUB_OWNER=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/]([^/]+)/.*|\1|')
GITHUB_REPO=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/][^/]+/([^.]+)(\.git)?$|\1|')

# Application configuration
APP_FOLDER="terraform-vpc-app"
PROJECT_NAME="terraform-vpc-cicd"

# Pipeline configuration
PIPELINE_NAME="terraform-vpc-pipeline"
CODEBUILD_PROJECT="terraform-vpc-deploy"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# S3 buckets
TF_STATE_BUCKET="terraform-state-${ACCOUNT_ID}"
ARTIFACT_BUCKET="codepipeline-artifacts-terraform-${ACCOUNT_ID}"

# DynamoDB table for state locking
TF_LOCK_TABLE="terraform-state-lock"

echo "REGION=$REGION"
echo "GITHUB_OWNER=$GITHUB_OWNER"
echo "GITHUB_REPO=$GITHUB_REPO"
echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "TF_STATE_BUCKET=$TF_STATE_BUCKET"
```

---

## Step 2 – Verify GitHub Repository

```bash
# Navigate to repository root
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR"

# Sync with remote
git checkout main
git pull origin main
```

---

## Step 3 – Create Application Directory

```bash
# Create application folder
mkdir -p "$APP_FOLDER"
cd "$APP_FOLDER"

echo "Created application directory: $APP_FOLDER"
```

---

## Step 4 – Create Terraform Backend Configuration

Create `backend.tf`:

```bash
cat > backend.tf << 'EOF'
# Terraform backend configuration for remote state
terraform {
  backend "s3" {
    # Bucket name will be provided via backend-config during terraform init
    # bucket         = "terraform-state-ACCOUNT_ID"
    key            = "terraform-vpc/terraform.tfstate"
    region         = "ap-southeast-2"
    # DynamoDB table for state locking
    # dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
EOF

echo "Created backend.tf"
```

---

## Step 5 – Create Terraform Provider Configuration

Create `providers.tf`:

```bash
cat > providers.tf << 'EOF'
# AWS Provider configuration
terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "TerraformVPCCICD"
      ManagedBy   = "Terraform"
      Environment = var.environment
    }
  }
}
EOF

echo "Created providers.tf"
```

---

## Step 6 – Create Terraform Variables

Create `variables.tf`:

```bash
cat > variables.tf << 'EOF'
# Input variables for Terraform configuration

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "ap-southeast-2"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.10.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR block for public subnet"
  type        = string
  default     = "10.10.1.0/24"
}

variable "private_subnet_cidr" {
  description = "CIDR block for private subnet"
  type        = string
  default     = "10.10.2.0/24"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t2.micro"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "terraform-vpc-cicd"
}
EOF

echo "Created variables.tf"
```

---

## Step 7 – Create Terraform Main Configuration

Create `main.tf`:

```bash
cat > main.tf << 'EOF'
# VPC Configuration
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

# Public Subnet
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-subnet"
  }
}

# Private Subnet
resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidr
  availability_zone = data.aws_availability_zones.available.names[0]

  tags = {
    Name = "${var.project_name}-private-subnet"
  }
}

# Route Table for Public Subnet
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

# Route Table Association
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Security Group for Web Server
resource "aws_security_group" "web" {
  name        = "${var.project_name}-web-sg"
  description = "Security group for web server"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH from anywhere"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-web-sg"
  }
}

# Data source for latest Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# EC2 Instance in Public Subnet
resource "aws_instance" "web" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.web.id]

  user_data = <<-EOF
              #!/bin/bash
              yum update -y
              yum install -y httpd
              systemctl start httpd
              systemctl enable httpd
              echo "<h1>Hello from Terraform CI/CD</h1>" > /var/www/html/index.html
              echo "<p>Instance ID: $(ec2-metadata --instance-id | cut -d ' ' -f 2)</p>" >> /var/www/html/index.html
              echo "<p>Availability Zone: $(ec2-metadata --availability-zone | cut -d ' ' -f 2)</p>" >> /var/www/html/index.html
              EOF

  tags = {
    Name = "${var.project_name}-web-server"
  }
}
EOF

echo "Created main.tf"
```

---

## Step 8 – Create Terraform Outputs

Create `outputs.tf`:

```bash
cat > outputs.tf << 'EOF'
# Output values for created resources

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_id" {
  description = "Public subnet ID"
  value       = aws_subnet.public.id
}

output "private_subnet_id" {
  description = "Private subnet ID"
  value       = aws_subnet.private.id
}

output "web_server_id" {
  description = "Web server instance ID"
  value       = aws_instance.web.id
}

output "web_server_public_ip" {
  description = "Web server public IP address"
  value       = aws_instance.web.public_ip
}

output "web_server_url" {
  description = "Web server URL"
  value       = "http://${aws_instance.web.public_ip}"
}

output "security_group_id" {
  description = "Security group ID"
  value       = aws_security_group.web.id
}
EOF

echo "Created outputs.tf"
```

---

## Step 9 – Create BuildSpec for CodeBuild

Create `buildspec.yml`:

```bash
cat > buildspec.yml << 'EOF'
version: 0.2

phases:
  install:
    commands:
      # Install Terraform CLI
      - echo "Installing Terraform..."
      - wget -q https://releases.hashicorp.com/terraform/1.6.6/terraform_1.6.6_linux_amd64.zip
      - unzip -q terraform_1.6.6_linux_amd64.zip
      - mv terraform /usr/local/bin/
      - terraform --version

  pre_build:
    commands:
      # Initialize Terraform with S3 backend
      - echo "Initializing Terraform..."
      - cd terraform-vpc-app
      - |
        terraform init \
          -backend-config="bucket=${TF_STATE_BUCKET}" \
          -backend-config="dynamodb_table=${TF_LOCK_TABLE}"

  build:
    commands:
      # Validate Terraform configuration
      - echo "Validating Terraform configuration..."
      - terraform validate
      
      # Format check
      - echo "Checking Terraform formatting..."
      - terraform fmt -check || true
      
      # Plan infrastructure changes
      - echo "Planning Terraform changes..."
      - terraform plan -out=tfplan
      
      # Apply infrastructure changes
      - echo "Applying Terraform changes..."
      - terraform apply -auto-approve tfplan

  post_build:
    commands:
      # Show outputs
      - echo "Terraform deployment completed!"
      - terraform output -json > terraform-outputs.json
      - cat terraform-outputs.json

artifacts:
  files:
    - terraform-vpc-app/terraform-outputs.json
  name: TerraformOutputs
EOF

echo "Created buildspec.yml"
```

---

## Step 10 – Create README

Create `README.md`:

```bash
cat > README.md << 'EOF'
# Terraform VPC CI/CD

This application demonstrates automated Terraform deployments using CodePipeline and CodeBuild.

## Infrastructure

- VPC (10.10.0.0/16)
- Public Subnet (10.10.1.0/24)
- Private Subnet (10.10.2.0/24)
- Internet Gateway
- Route Tables
- Security Group (HTTP + SSH)
- EC2 Instance (Apache web server)

## Terraform Files

- `backend.tf` - S3 backend configuration for remote state
- `providers.tf` - AWS provider and version constraints
- `variables.tf` - Input variables
- `main.tf` - VPC, subnets, EC2 resources
- `outputs.tf` - Output values

## CI/CD Pipeline

GitHub → CodePipeline → CodeBuild → Terraform Apply → AWS Resources

## Remote State

- S3 Bucket: Stores terraform.tfstate
- DynamoDB Table: Provides state locking for concurrent operations
EOF

echo "Created README.md"
```

---

## Step 11 – Commit and Push to GitHub

```bash
# Navigate to repository root
cd "$REPO_DIR"

# Add all files
git add "$APP_FOLDER/"

# Commit changes
git commit -m "Add Terraform VPC CI/CD application"

# Push to GitHub
git push origin main

echo "Pushed application code to GitHub"
```

---

## Step 12 – Create S3 Buckets

```bash
# Create S3 bucket for Terraform state
aws s3api create-bucket \
  --bucket "$TF_STATE_BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

# Enable versioning for state bucket
aws s3api put-bucket-versioning \
  --bucket "$TF_STATE_BUCKET" \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket "$TF_STATE_BUCKET" \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Create S3 bucket for CodePipeline artifacts
aws s3api create-bucket \
  --bucket "$ARTIFACT_BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

echo "Created S3 buckets: $TF_STATE_BUCKET, $ARTIFACT_BUCKET"
```

---

## Step 13 – Create DynamoDB Table for State Locking

```bash
# Create DynamoDB table for Terraform state locking
aws dynamodb create-table \
  --table-name "$TF_LOCK_TABLE" \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION"

# Wait for table to be active
aws dynamodb wait table-exists \
  --table-name "$TF_LOCK_TABLE" \
  --region "$REGION"

echo "Created DynamoDB table: $TF_LOCK_TABLE"
```

---

## Step 14 – Create IAM Role for CodeBuild

```bash
# Create trust policy for CodeBuild
cat > codebuild-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codebuild.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role
aws iam create-role \
  --role-name CodeBuildTerraformRole \
  --assume-role-policy-document file://codebuild-trust-policy.json

# Create permissions policy for Terraform operations
cat > codebuild-terraform-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${ARTIFACT_BUCKET}/*",
        "arn:aws:s3:::${ARTIFACT_BUCKET}",
        "arn:aws:s3:::${TF_STATE_BUCKET}/*",
        "arn:aws:s3:::${TF_STATE_BUCKET}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${TF_LOCK_TABLE}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ec2:*",
        "vpc:*"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Attach policy to role
aws iam put-role-policy \
  --role-name CodeBuildTerraformRole \
  --policy-name CodeBuildTerraformPolicy \
  --policy-document file://codebuild-terraform-policy.json

echo "Created IAM role: CodeBuildTerraformRole"
```

---

## Step 15 – Create CodeBuild Project

```bash
# Create CodeBuild project configuration
cat > codebuild-project.json << EOF
{
  "name": "$CODEBUILD_PROJECT",
  "source": {
    "type": "CODEPIPELINE",
    "buildspec": "terraform-vpc-app/buildspec.yml"
  },
  "artifacts": {
    "type": "CODEPIPELINE"
  },
  "environment": {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/standard:7.0",
    "computeType": "BUILD_GENERAL1_SMALL",
    "environmentVariables": [
      {
        "name": "TF_STATE_BUCKET",
        "value": "$TF_STATE_BUCKET",
        "type": "PLAINTEXT"
      },
      {
        "name": "TF_LOCK_TABLE",
        "value": "$TF_LOCK_TABLE",
        "type": "PLAINTEXT"
      },
      {
        "name": "AWS_DEFAULT_REGION",
        "value": "$REGION",
        "type": "PLAINTEXT"
      }
    ]
  },
  "serviceRole": "arn:aws:iam::${ACCOUNT_ID}:role/CodeBuildTerraformRole"
}
EOF

# Create CodeBuild project
aws codebuild create-project \
  --cli-input-json file://codebuild-project.json \
  --region "$REGION"

echo "Created CodeBuild project: $CODEBUILD_PROJECT"
```

---

## Step 16 – Create IAM Role for CodePipeline

```bash
# Create trust policy for CodePipeline
cat > codepipeline-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codepipeline.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role
aws iam create-role \
  --role-name CodePipelineTerraformRole \
  --assume-role-policy-document file://codepipeline-trust-policy.json

# Attach managed policy
aws iam attach-role-policy \
  --role-name CodePipelineTerraformRole \
  --policy-arn arn:aws:iam::aws:policy/AWSCodePipeline_FullAccess

# Create additional permissions policy
cat > codepipeline-terraform-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::${ARTIFACT_BUCKET}/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "codebuild:BatchGetBuilds",
        "codebuild:StartBuild"
      ],
      "Resource": "arn:aws:codebuild:${REGION}:${ACCOUNT_ID}:project/${CODEBUILD_PROJECT}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "codestar-connections:UseConnection"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Attach policy to role
aws iam put-role-policy \
  --role-name CodePipelineTerraformRole \
  --policy-name CodePipelineTerraformPolicy \
  --policy-document file://codepipeline-terraform-policy.json

echo "Created IAM role: CodePipelineTerraformRole"
```

---

## Step 17 – Create CodeStar Connection

```bash
# Create CodeStar connection to GitHub
CONNECTION_ARN=$(aws codestar-connections create-connection \
  --provider-type GitHub \
  --connection-name terraform-github-connection \
  --region "$REGION" \
  --query 'ConnectionArn' \
  --output text)

echo "CONNECTION_ARN=$CONNECTION_ARN"
echo ""
echo "⚠️  IMPORTANT: Complete the connection in AWS Console:"
echo "1. Go to: https://${REGION}.console.aws.amazon.com/codesuite/settings/connections"
echo "2. Find 'terraform-github-connection' with status 'PENDING'"
echo "3. Click 'Update pending connection'"
echo "4. Click 'Install a new app' or select existing GitHub App"
echo "5. Authorize AWS Connector for GitHub"
echo "6. Click 'Connect'"
echo ""
read -p "Press Enter after completing the connection in AWS Console..."
```

---

## Step 18 – Create CodePipeline

```bash
# Create CodePipeline configuration
cat > codepipeline-config.json << EOF
{
  "pipeline": {
    "name": "$PIPELINE_NAME",
    "roleArn": "arn:aws:iam::${ACCOUNT_ID}:role/CodePipelineTerraformRole",
    "artifactStore": {
      "type": "S3",
      "location": "$ARTIFACT_BUCKET"
    },
    "stages": [
      {
        "name": "Source",
        "actions": [
          {
            "name": "SourceAction",
            "actionTypeId": {
              "category": "Source",
              "owner": "AWS",
              "provider": "CodeStarSourceConnection",
              "version": "1"
            },
            "configuration": {
              "ConnectionArn": "$CONNECTION_ARN",
              "FullRepositoryId": "${GITHUB_OWNER}/${GITHUB_REPO}",
              "BranchName": "main",
              "OutputArtifactFormat": "CODE_ZIP"
            },
            "outputArtifacts": [
              {
                "name": "SourceOutput"
              }
            ]
          }
        ]
      },
      {
        "name": "Deploy",
        "actions": [
          {
            "name": "TerraformDeploy",
            "actionTypeId": {
              "category": "Build",
              "owner": "AWS",
              "provider": "CodeBuild",
              "version": "1"
            },
            "configuration": {
              "ProjectName": "$CODEBUILD_PROJECT"
            },
            "inputArtifacts": [
              {
                "name": "SourceOutput"
              }
            ],
            "outputArtifacts": [
              {
                "name": "TerraformOutputs"
              }
            ]
          }
        ]
      }
    ]
  }
}
EOF

# Create CodePipeline
aws codepipeline create-pipeline \
  --cli-input-json file://codepipeline-config.json \
  --region "$REGION"

echo "Created CodePipeline: $PIPELINE_NAME"
```

---

## Step 19 – Monitor Pipeline Execution

```bash
# Get pipeline execution status
aws codepipeline get-pipeline-state \
  --name "$PIPELINE_NAME" \
  --region "$REGION" \
  --query 'stageStates[*].[stageName,latestExecution.status]' \
  --output table

echo ""
echo "Pipeline Console:"
echo "https://${REGION}.console.aws.amazon.com/codesuite/codepipeline/pipelines/${PIPELINE_NAME}/view"
```

**Wait for pipeline to complete** (approximately 5-8 minutes):
- Source stage: Pull code from GitHub
- Deploy stage: Run Terraform in CodeBuild

---

## Step 20 – Verify Terraform Outputs

```bash
# Wait for pipeline to complete
echo "Waiting for pipeline to complete..."
aws codepipeline get-pipeline-state \
  --name "$PIPELINE_NAME" \
  --region "$REGION" \
  --query 'stageStates[*].[stageName,latestExecution.status]' \
  --output table

# Get CodeBuild build ID
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name "$CODEBUILD_PROJECT" \
  --region "$REGION" \
  --query 'ids[0]' \
  --output text)

echo "Latest build: $BUILD_ID"

# Get CodeBuild logs
echo ""
echo "CodeBuild Logs:"
aws codebuild batch-get-builds \
  --ids "$BUILD_ID" \
  --region "$REGION" \
  --query 'builds[0].logs.deepLink' \
  --output text
```

---

## Step 21 – Test Web Server

```bash
# Get VPC ID from Terraform state in S3
aws s3 cp "s3://${TF_STATE_BUCKET}/terraform-vpc/terraform.tfstate" - 2>/dev/null | \
  grep -A 5 '"web_server_public_ip"' || echo "State file not yet available"

# Alternatively, get from EC2 tags
WEB_IP=$(aws ec2 describe-instances \
  --filters "Name=tag:Project,Values=TerraformVPCCICD" \
            "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$REGION")

echo ""
echo "Web Server IP: $WEB_IP"
echo "Web Server URL: http://$WEB_IP"
echo ""
echo "Testing web server..."
curl -s "http://$WEB_IP" || echo "Server not yet ready (wait 2-3 minutes for initialization)"
```

**Expected Output:**
```html
<h1>Hello from Terraform CI/CD</h1>
<p>Instance ID: i-0123456789abcdef0</p>
<p>Availability Zone: ap-southeast-2a</p>
```

---

## Step 22 – Test GitOps Workflow (Trigger Pipeline)

```bash
# Navigate to application directory
cd "$REPO_DIR/$APP_FOLDER"

# Modify Terraform configuration (change instance user_data)
cat >> main.tf << 'EOF'

# Updated: $(date)
EOF

# Commit and push changes
git add main.tf
git commit -m "Update Terraform configuration - test GitOps workflow"
git push origin main

echo ""
echo "Pushed changes to GitHub - pipeline will automatically trigger"
echo "Monitor pipeline: https://${REGION}.console.aws.amazon.com/codesuite/codepipeline/pipelines/${PIPELINE_NAME}/view"
```

**Observe:**
- CodePipeline automatically detects GitHub changes
- Triggers new execution
- CodeBuild runs terraform plan/apply
- Infrastructure updated automatically

---

## Step 23 – View Terraform State

```bash
# Download and view Terraform state from S3
aws s3 cp "s3://${TF_STATE_BUCKET}/terraform-vpc/terraform.tfstate" - | jq '.' > terraform-state.json

echo "Terraform state downloaded to terraform-state.json"
echo ""
echo "State version:"
jq '.version' terraform-state.json

echo ""
echo "Resources in state:"
jq '.resources[].type' terraform-state.json

echo ""
echo "Outputs:"
jq '.outputs' terraform-state.json
```

---

## Step 24 – Compare Terraform vs SAM/CloudFormation CI/CD

| Feature | Terraform (Lab 10.H) | SAM (Lab 10.G) | CloudFormation (Session 9) |
|---------|---------------------|----------------|----------------------------|
| **Language** | HCL (HashiCorp) | YAML/JSON | YAML/JSON |
| **State Management** | S3 + DynamoDB | CloudFormation | CloudFormation |
| **Multi-Cloud** | ✅ Yes (AWS, Azure, GCP) | ❌ AWS only | ❌ AWS only |
| **Serverless Focus** | ❌ Generic IaC | ✅ Serverless-first | ❌ Generic IaC |
| **Learning Curve** | Medium | Low | Medium |
| **CI/CD Integration** | CodeBuild (custom) | SAM CLI (native) | CloudFormation CLI |
| **Plan Preview** | terraform plan | sam validate | change sets |
| **State Locking** | DynamoDB | N/A (CloudFormation) | N/A |
| **Modularity** | Modules | Nested apps | Nested stacks |
| **Community** | Large (multi-cloud) | AWS-focused | AWS-focused |

**Key Differences:**
- **Terraform**: Best for multi-cloud, complex infrastructure, state management control
- **SAM**: Best for serverless applications, simplified Lambda/API Gateway deployment
- **CloudFormation**: AWS-native, no external tools, comprehensive AWS coverage

---

## Cleanup

### Option 1: Destroy via Pipeline (GitOps Approach)

```bash
# Modify buildspec.yml to run terraform destroy
cd "$REPO_DIR/$APP_FOLDER"

cat > buildspec-destroy.yml << 'EOF'
version: 0.2

phases:
  install:
    commands:
      - echo "Installing Terraform..."
      - wget -q https://releases.hashicorp.com/terraform/1.6.6/terraform_1.6.6_linux_amd64.zip
      - unzip -q terraform_1.6.6_linux_amd64.zip
      - mv terraform /usr/local/bin/
      - terraform --version

  pre_build:
    commands:
      - echo "Initializing Terraform..."
      - cd terraform-vpc-app
      - |
        terraform init \
          -backend-config="bucket=${TF_STATE_BUCKET}" \
          -backend-config="dynamodb_table=${TF_LOCK_TABLE}"

  build:
    commands:
      - echo "Destroying Terraform infrastructure..."
      - terraform destroy -auto-approve
EOF

# Update CodeBuild to use destroy buildspec (manual console change required)
echo "To destroy infrastructure via pipeline:"
echo "1. Update CodeBuild project buildspec to: terraform-vpc-app/buildspec-destroy.yml"
echo "2. Push change to trigger pipeline"
echo "3. Revert to buildspec.yml afterward"
```

### Option 2: Destroy Manually

```bash
cd "$REPO_DIR/$APP_FOLDER"

# Navigate to repository root
REPO_DIR=$(git rev-parse --show-toplevel)

# Set variables
REGION="ap-southeast-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TF_STATE_BUCKET="terraform-state-${ACCOUNT_ID}"
ARTIFACT_BUCKET="codepipeline-artifacts-terraform-${ACCOUNT_ID}"
TF_LOCK_TABLE="terraform-state-lock"
PIPELINE_NAME="terraform-vpc-pipeline"
CODEBUILD_PROJECT="terraform-vpc-deploy"

# Install Terraform locally
wget -q https://releases.hashicorp.com/terraform/1.6.6/terraform_1.6.6_linux_amd64.zip
unzip -q terraform_1.6.6_linux_amd64.zip
sudo mv terraform /usr/local/bin/
terraform --version

# Initialize Terraform with S3 backend
cd "$REPO_DIR/terraform-vpc-app"
terraform init \
  -backend-config="bucket=${TF_STATE_BUCKET}" \
  -backend-config="dynamodb_table=${TF_LOCK_TABLE}"

# Destroy infrastructure
terraform destroy -auto-approve

# Delete CodePipeline
aws codepipeline delete-pipeline \
  --name "$PIPELINE_NAME" \
  --region "$REGION"

# Delete CodeBuild project
aws codebuild delete-project \
  --name "$CODEBUILD_PROJECT" \
  --region "$REGION"

# Delete IAM roles
aws iam delete-role-policy \
  --role-name CodeBuildTerraformRole \
  --policy-name CodeBuildTerraformPolicy

aws iam delete-role \
  --role-name CodeBuildTerraformRole

aws iam delete-role-policy \
  --role-name CodePipelineTerraformRole \
  --policy-name CodePipelineTerraformPolicy

aws iam detach-role-policy \
  --role-name CodePipelineTerraformRole \
  --policy-arn arn:aws:iam::aws:policy/AWSCodePipeline_FullAccess

aws iam delete-role \
  --role-name CodePipelineTerraformRole

# Delete S3 buckets (empty first)
aws s3 rm "s3://${ARTIFACT_BUCKET}" --recursive
aws s3 rb "s3://${ARTIFACT_BUCKET}"

aws s3 rm "s3://${TF_STATE_BUCKET}" --recursive
aws s3 rb "s3://${TF_STATE_BUCKET}"

# Delete DynamoDB table
aws dynamodb delete-table \
  --table-name "$TF_LOCK_TABLE" \
  --region "$REGION"

echo "Cleanup complete!"
```

---

## Troubleshooting

### Issue: Terraform state locked

**Solution:**
```bash
# Check DynamoDB for locks
aws dynamodb scan \
  --table-name "$TF_LOCK_TABLE" \
  --region "$REGION"

# Manually remove lock (if stuck)
aws dynamodb delete-item \
  --table-name "$TF_LOCK_TABLE" \
  --key '{"LockID":{"S":"terraform-state-ACCOUNT_ID/terraform-vpc/terraform.tfstate-md5"}}' \
  --region "$REGION"
```

### Issue: CodeBuild fails with permission errors

**Solution:**
```bash
# Verify IAM role has EC2/VPC permissions
aws iam get-role-policy \
  --role-name CodeBuildTerraformRole \
  --policy-name CodeBuildTerraformPolicy

# Add missing permissions if needed
```

### Issue: Pipeline not triggering on GitHub push

**Solution:**
```bash
# Verify CodeStar connection status
aws codestar-connections get-connection \
  --connection-arn "$CONNECTION_ARN" \
  --region "$REGION"

# Status should be "AVAILABLE" (not "PENDING")
# Re-authorize in console if needed
```

---

## Key Takeaways

✅ **Terraform CI/CD**: Automated infrastructure deployment with GitOps workflow  
✅ **Remote State**: S3 backend with DynamoDB locking for team collaboration  
✅ **Multi-Cloud IaC**: Terraform works across AWS, Azure, GCP (unlike CloudFormation)  
✅ **CodeBuild Integration**: Custom buildspec for terraform init/plan/apply  
✅ **State Management**: Explicit state file management vs CloudFormation's automatic state  
✅ **Plan Preview**: terraform plan shows changes before applying (like CloudFormation change sets)  
✅ **HCL Language**: More readable than JSON/YAML for complex configurations  
✅ **GitOps Workflow**: Git push → Pipeline trigger → Automatic deployment

**Comparison to Session 9 Labs:**
- Session 9.D: Manual Terraform commands (local state)
- Lab 10.H: Automated Terraform with CodePipeline (remote state, CI/CD)

---

## Next Steps
- Explore Terraform modules for reusable components
- Implement terraform workspaces for multi-environment deployments (dev/staging/prod)
- Add manual approval stage in CodePipeline before terraform apply
- Integrate Terraform with Atlantis for pull request automation
- Use Terraform Cloud for enhanced collaboration and governance

---

**📘 Session 10 Complete:** You've now mastered 8 different CI/CD approaches covering code, containers, serverless, Kubernetes, VMs, and infrastructure automation!
