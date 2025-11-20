# Lab 10.G: Terraform CI/CD with GitHub Actions - Infrastructure Automation
<img width="1486" height="662" alt="IMG10H" src="https://github.com/user-attachments/assets/f93ba940-654b-43bb-8980-86a9b55034ca" />


## Overview
This lab demonstrates building a CI/CD pipeline for Terraform infrastructure deployments using GitHub Actions. You'll create Terraform configurations for VPC infrastructure, automate terraform plan/apply with GitHub Actions, implement remote state in S3, and enable GitOps workflows. This showcases production-grade infrastructure automation with multi-cloud IaC tools.

---

## Objectives
- Create Terraform configuration for VPC infrastructure
- Configure GitHub Actions for Terraform deployments
- Automate terraform init/plan/apply in GitHub Actions
- Implement S3 backend for remote state management
- Configure DynamoDB for state locking
- Enable GitOps workflow (Git push → Auto deploy)
- Use Terraform for IaC

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Git installed (`git --version`)
- GitHub account with repository access
- IAM permissions for VPC, EC2, S3, DynamoDB, IAM
- Region: ap-southeast-2

---

## Architecture

```
GitHub Push → GitHub Actions:
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
2. Push to main triggers GitHub Actions workflow
3. GitHub Actions installs Terraform CLI
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

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# S3 bucket for Terraform state
TF_STATE_BUCKET="terraform-state-${ACCOUNT_ID}"

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

## Step 9 – Create GitHub Actions Workflow

```bash
# Create GitHub Actions directory
mkdir -p .github/workflows

# Create Terraform deployment workflow
cat > .github/workflows/deploy-terraform.yml <<'EOF'
name: Deploy Terraform Infrastructure

on:
  push:
    branches:
      - main
    paths:
      - 'terraform-vpc-app/**'
      - '.github/workflows/deploy-terraform.yml'

jobs:
  terraform:
    runs-on: ubuntu-latest
    
    env:
      TF_STATE_BUCKET: ${{ secrets.TF_STATE_BUCKET }}
      TF_LOCK_TABLE: terraform-state-lock
      AWS_REGION: ap-southeast-2
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-southeast-2
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.6.6
      
      - name: Terraform Init
        run: |
          cd terraform-vpc-app
          terraform init \
            -backend-config="bucket=${TF_STATE_BUCKET}" \
            -backend-config="dynamodb_table=${TF_LOCK_TABLE}"
      
      - name: Terraform Validate
        run: |
          cd terraform-vpc-app
          terraform validate
      
      - name: Terraform Format Check
        run: |
          cd terraform-vpc-app
          terraform fmt -check || true
      
      - name: Terraform Plan
        run: |
          cd terraform-vpc-app
          terraform plan -out=tfplan
      
      - name: Terraform Apply
        run: |
          cd terraform-vpc-app
          terraform apply -auto-approve tfplan
      
      - name: Terraform Outputs
        run: |
          cd terraform-vpc-app
          echo "🚀 Terraform deployment completed!"
          terraform output -json
EOF

echo "✅ GitHub Actions workflow created"
```

---

## Step 10 – Create README

Create `README.md`:

```bash
cat > README.md << 'EOF'
# Terraform VPC CI/CD

This application demonstrates automated Terraform deployments using GitHub Actions.

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

GitHub Push → GitHub Actions → Terraform Apply → AWS Resources

## Remote State

- S3 Bucket: Stores terraform.tfstate
- DynamoDB Table: Provides state locking for concurrent operations
EOF

echo "Created README.md"
```

---

## Step 11 – Create AWS Credentials for GitHub Actions

```bash
# Create IAM user for GitHub Actions
aws iam create-user --user-name github-actions-terraform-deploy

# Create access policy for Terraform deployments
cat > github-actions-terraform-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:*",
        "vpc:*"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${TF_STATE_BUCKET}",
        "arn:aws:s3:::${TF_STATE_BUCKET}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${TF_LOCK_TABLE}"
    },
    {
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    }
  ]
}
EOF

# Attach policy to user
aws iam put-user-policy \
  --user-name github-actions-terraform-deploy \
  --policy-name TerraformDeployPolicy \
  --policy-document file://github-actions-terraform-policy.json

# Create access keys
ACCESS_KEYS=$(aws iam create-access-key \
  --user-name github-actions-terraform-deploy \
  --output json)

AWS_ACCESS_KEY_ID=$(echo "$ACCESS_KEYS" | jq -r '.AccessKey.AccessKeyId')
AWS_SECRET_ACCESS_KEY=$(echo "$ACCESS_KEYS" | jq -r '.AccessKey.SecretAccessKey')

echo "✅ IAM user created with access keys"
echo ""
echo "⚠️  SAVE THESE CREDENTIALS - They will not be shown again:"
echo "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID"
echo "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY"
echo "TF_STATE_BUCKET=$TF_STATE_BUCKET"
```

---

## Step 12 – Configure GitHub Secrets

```bash
echo "Configure GitHub repository secrets:"
echo ""
echo "1. Go to: https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/settings/secrets/actions"
echo "2. Click 'New repository secret'"
echo "3. Add these three secrets:"
echo ""
echo "   Name: AWS_ACCESS_KEY_ID"
echo "   Value: $AWS_ACCESS_KEY_ID"
echo ""
echo "   Name: AWS_SECRET_ACCESS_KEY"
echo "   Value: $AWS_SECRET_ACCESS_KEY"
echo ""
echo "   Name: TF_STATE_BUCKET"
echo "   Value: $TF_STATE_BUCKET"
echo ""
echo "Press Enter when secrets are configured..."
read
```

---

## Step 13 – Commit and Push to GitHub

```bash
# Navigate to repository root
cd "$REPO_DIR"

# Add all files
git add "$APP_FOLDER/" .github/

# Commit changes
git commit -m "Add Terraform VPC with GitHub Actions CI/CD"

# Push to GitHub (triggers workflow)
git push origin main

echo "✅ Code pushed - GitHub Actions workflow will start automatically"
echo "📊 Monitor workflow: https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions"
```

---

## Step 14 – Create S3 Bucket for Terraform State

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

echo "Created S3 bucket: $TF_STATE_BUCKET"
```

---

## Step 15 – Create DynamoDB Table for State Locking

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

## Step 16 – Monitor GitHub Actions Workflow

```bash
# Open workflow in browser
echo "📊 Monitor deployment:"
echo "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions"
echo ""
echo "Or use GitHub CLI:"
gh run list --limit 5
gh run watch
```

---

## Step 17 – Verify Terraform Deployment

```bash
# Wait for GitHub Actions workflow to complete (2-3 minutes)
echo "Waiting for deployment to complete..."
sleep 120

# Check VPC creation
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=tag:Name,Values=terraform-vpc-cicd-vpc" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region "$REGION")

echo "VPC_ID=$VPC_ID"

# Check EC2 instance
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=terraform-vpc-cicd-web-server" \
            "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text \
  --region "$REGION")

INSTANCE_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$REGION")

echo "INSTANCE_ID=$INSTANCE_ID"
echo "INSTANCE_IP=$INSTANCE_IP"
```

---

## Step 18 – View Terraform Outputs

```bash
# Get Terraform state from S3
aws s3 cp "s3://${TF_STATE_BUCKET}/terraform-vpc/terraform.tfstate" terraform.tfstate

# Extract outputs using jq
cat terraform.tfstate | jq '.outputs'

# Or view directly from workflow logs
echo "View outputs in GitHub Actions:"
echo "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions"
```

---

## Step 19 – Test Web Server

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
# Wait for GitHub Actions to complete (5-8 minutes)
echo "Waiting for deployment..."
sleep 60

# Get VPC ID from Terraform state in S3
aws s3 cp "s3://${TF_STATE_BUCKET}/terraform-vpc/terraform.tfstate" - 2>/dev/null | \
  grep -A 5 '"web_server_public_ip"' || echo "State file not yet available"

# Get instance IP from EC2 tags
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
curl -s "http://$WEB_IP" || echo "Server not yet ready (wait 2-3 minutes)"
```

**Expected Output:**
```html
<h1>Hello from Terraform CI/CD</h1>
<p>Instance ID: i-0123456789abcdef0</p>
<p>Availability Zone: ap-southeast-2a</p>
```

---

## Step 20 – Test GitOps Workflow

```bash
# Navigate to application directory
cd "$REPO_DIR/$APP_FOLDER"

# Modify Terraform configuration
cat >> main.tf << 'EOF'

# Updated: $(date)
EOF

# Commit and push changes
git add main.tf
git commit -m "Update Terraform configuration - test GitOps workflow"
git push origin main

echo ""
echo "✅ Pushed changes to GitHub - GitHub Actions will automatically trigger"
echo "📊 Monitor: https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions"
```

**Observe:**
- GitHub Actions automatically detects push to main
- Triggers new workflow
- Terraform runs plan/apply
- Infrastructure updated automatically

---

## Step 21 – View Terraform State

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

## Step 22 – Compare Terraform vs SAM/CloudFormation CI/CD

| Feature | Terraform (Lab 10.G) | SAM (Lab 10.F) | CloudFormation (Session 9) |
|---------|---------------------|----------------|----------------------------|
| **Language** | HCL (HashiCorp) | YAML/JSON | YAML/JSON |
| **State Management** | S3 + DynamoDB | CloudFormation | CloudFormation |
| **Multi-Cloud** | ✅ Yes (AWS, Azure, GCP) | ❌ AWS only | ❌ AWS only |
| **Serverless Focus** | ❌ Generic IaC | ✅ Serverless-first | ❌ Generic IaC |
| **Learning Curve** | Medium | Low | Medium |
| **CI/CD Integration** | GitHub Actions | GitHub Actions | CloudFormation CLI |
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

### Destroy Infrastructure with Terraform

```bash
cd "$REPO_DIR/terraform-vpc-app"

# Navigate to repository root
REPO_DIR=$(git rev-parse --show-toplevel)

# Set variables
REGION="ap-southeast-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TF_STATE_BUCKET="terraform-state-${ACCOUNT_ID}"
TF_LOCK_TABLE="terraform-state-lock"

# Install Terraform locally (if not already installed)
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

# Delete IAM user and access keys
aws iam list-access-keys \
  --user-name github-actions-terraform-deploy \
  --query 'AccessKeyMetadata[*].AccessKeyId' \
  --output text | while read key; do
    aws iam delete-access-key \
      --user-name github-actions-terraform-deploy \
      --access-key-id "$key"
done

aws iam delete-user-policy \
  --user-name github-actions-terraform-deploy \
  --policy-name TerraformDeployPolicy

aws iam delete-user \
  --user-name github-actions-terraform-deploy

# Delete S3 bucket
aws s3 rm "s3://${TF_STATE_BUCKET}" --recursive
aws s3 rb "s3://${TF_STATE_BUCKET}"

# Delete DynamoDB table
aws dynamodb delete-table \
  --table-name "$TF_LOCK_TABLE" \
  --region "$REGION"

# Remove application directory and workflow
cd "$REPO_DIR"
rm -rf "$APP_FOLDER" .github/workflows/deploy-terraform.yml
git add -A
git commit -m "Cleanup: Remove Terraform VPC application"
git push origin main

echo ""
echo "⚠️  Manually remove GitHub secrets:"
echo "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/settings/secrets/actions"

echo ""
echo "✅ Cleanup complete!"
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

### Issue: GitHub Actions workflow fails

**Solution:**
```bash
# Verify GitHub Secrets are configured
echo "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/settings/secrets/actions"

# Verify IAM permissions
aws iam get-user-policy \
  --user-name github-actions-terraform-deploy \
  --policy-name TerraformDeployPolicy
```

### Issue: S3 backend initialization fails

**Solution:**
```bash
# Verify S3 bucket exists
aws s3 ls "s3://${TF_STATE_BUCKET}"

# Verify DynamoDB table exists
aws dynamodb describe-table \
  --table-name "$TF_LOCK_TABLE" \
  --region "$REGION"
```

---

## Key Takeaways

✅ **Terraform CI/CD**: Automated infrastructure deployment with GitHub Actions  
✅ **Remote State**: S3 backend with DynamoDB locking for team collaboration  
✅ **Multi-Cloud IaC**: Terraform works across AWS, Azure, GCP (unlike CloudFormation)  
✅ **GitHub Actions**: Native CI/CD without CodePipeline or CodeBuild  
✅ **State Management**: Explicit state file management vs CloudFormation's automatic state  
✅ **Plan Preview**: terraform plan shows changes before applying  
✅ **HCL Language**: More readable than JSON/YAML for complex configurations  
✅ **GitOps Workflow**: Git push → GitHub Actions → Automatic deployment

**Comparison:**
- Session 9.D: Manual Terraform (local state)
- Lab 10.G: Automated Terraform with GitHub Actions (remote state, CI/CD)

---