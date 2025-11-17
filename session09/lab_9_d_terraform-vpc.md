# Lab 9.D: Terraform Basics - Multi-Region VPC Deployment

## Overview
This lab introduces Terraform, an alternative Infrastructure as Code tool to CloudFormation. You'll learn Terraform basics, deploy a VPC in ap-southeast-2, configure remote state storage in S3 with DynamoDB locking, and use core Terraform commands: init, plan, apply, and destroy.

---

## Objectives
- Install Terraform CLI
- Create Terraform configuration files (HCL syntax)
- Define providers, resources, variables, and outputs
- Initialize Terraform project
- Preview changes with `terraform plan`
- Deploy infrastructure with `terraform apply`
- Configure remote state in S3 with DynamoDB locking
- Import existing AWS resources into Terraform state
- Destroy infrastructure with `terraform destroy`

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for VPC, S3, DynamoDB, EC2
- Basic understanding of IaC concepts
- Region: ap-southeast-2

---

## Architecture

```
Terraform Configuration (HCL)
  ├── Provider (AWS)
  ├── VPC (10.0.0.0/16)
  ├── Public Subnet (10.0.1.0/24)
  ├── Internet Gateway
  ├── Route Table
  └── EC2 Instance (t2.micro)

Remote State Backend
  ├── S3 Bucket (terraform state)
  └── DynamoDB Table (state locking)
```

---

## Step 1 – Install Terraform CLI

```bash
# Download Terraform binary
cd /tmp
wget https://releases.hashicorp.com/terraform/1.6.6/terraform_1.6.6_linux_amd64.zip

# Extract and install to system PATH
unzip -q terraform_1.6.6_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Verify installation
terraform version
```

---

## Step 2 – Set Variables and Create Project Directory

```bash
# Set AWS region for Terraform deployment
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Create unique names for remote state backend (S3 bucket + DynamoDB table)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
STATE_BUCKET="terraform-state-${ACCOUNT_ID}"
LOCK_TABLE="terraform-state-lock"

# Create Terraform project directory
mkdir -p /tmp/terraform-vpc
cd /tmp/terraform-vpc

echo "REGION: $REGION"
echo "STATE_BUCKET: $STATE_BUCKET"
echo "LOCK_TABLE: $LOCK_TABLE"
echo "PROJECT_DIR: $(pwd)"
```

---

## Step 3 – Create Provider Configuration

```bash
# Create AWS provider configuration with default tags
cat > provider.tf <<EOF
# Terraform version and required providers
terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# AWS Provider configuration
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "Terraform-VPC-Lab"
      ManagedBy   = "Terraform"
      Environment = "Learning"
    }
  }
}
EOF

echo "provider.tf"
```

---

## Step 4 – Create Variables File

```bash
# Define input variables for flexible configuration
cat > variables.tf <<EOF
# AWS Region
variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "ap-southeast-2"
}

# VPC CIDR
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# Subnet CIDR
variable "subnet_cidr" {
  description = "CIDR block for public subnet"
  type        = string
  default     = "10.0.1.0/24"
}

# Project name
variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "terraform-lab"
}
EOF

echo "variables.tf"
```

---

## Step 5 – Create VPC Resources

```bash
# Define VPC infrastructure (VPC, subnet, IGW, routing)
cat > vpc.tf <<'EOF'
# VPC
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
  cidr_block              = var.subnet_cidr
  map_public_ip_on_launch = true
  availability_zone       = data.aws_availability_zones.available.names[0]
  
  tags = {
    Name = "${var.project_name}-public-subnet"
  }
}

# Route Table
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

# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}
EOF

echo "vpc.tf"
```

---

## Step 6 – Create EC2 Instance Configuration

```bash
# Define EC2 instance with security group and web server setup
cat > ec2.tf <<'EOF'
# Security Group for EC2
resource "aws_security_group" "web" {
  name        = "${var.project_name}-web-sg"
  description = "Allow HTTP and SSH"
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
    description = "All outbound traffic"
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
data "aws_ami" "amazon_linux" {
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

# EC2 Instance
resource "aws_instance" "web" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t2.micro"
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.web.id]
  
  user_data = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y httpd
    
    cat > /var/www/html/index.html <<HTMLEOF
    <!DOCTYPE html>
    <html>
    <head><title>Terraform Demo</title></head>
    <body style="font-family: Arial; text-align: center; padding: 50px;">
        <h1>🚀 Terraform Deployed VPC</h1>
        <p>This infrastructure was deployed using Terraform</p>
        <p><strong>VPC CIDR:</strong> ${var.vpc_cidr}</p>
        <p><strong>Region:</strong> ${var.aws_region}</p>
        <p><strong>Instance Type:</strong> t2.micro</p>
    </body>
    </html>
    HTMLEOF
    
    systemctl enable httpd
    systemctl start httpd
  EOF
  
  tags = {
    Name = "${var.project_name}-web-server"
  }
}
EOF

echo "ec2.tf"
```

---

## Step 7 – Create Outputs File

```bash
# Define outputs to export important values after deployment
cat > outputs.tf <<'EOF'
# VPC ID
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

# Subnet ID
output "subnet_id" {
  description = "Public Subnet ID"
  value       = aws_subnet.public.id
}

# EC2 Instance ID
output "instance_id" {
  description = "EC2 Instance ID"
  value       = aws_instance.web.id
}

# EC2 Public IP
output "instance_public_ip" {
  description = "EC2 Instance Public IP"
  value       = aws_instance.web.public_ip
}

# Web URL
output "web_url" {
  description = "Web Application URL"
  value       = "http://${aws_instance.web.public_ip}"
}
EOF

echo "outputs.tf"
```

---

## Step 8 – Initialize Terraform

```bash
# Initialize Terraform (downloads AWS provider and sets up working directory)
terraform init
```

---

## Step 9 – Validate Configuration

```bash
# Validate Terraform syntax and configuration
terraform validate
```

---

## Step 10 – Format Configuration Files

```bash
# Format all .tf files for consistent style
terraform fmt
```

---

## Step 11 – Preview Changes (Terraform Plan)

```bash
# Generate execution plan (preview what will be created/modified/destroyed)
terraform plan
```

---

## Step 12 – Apply Configuration (Deploy Infrastructure)

```bash
# Deploy all resources defined in Terraform configuration
terraform apply -auto-approve
```

---

## Step 13 – View Outputs

```bash
# Display all Terraform outputs
terraform output

# Extract web application URL
WEB_URL=$(terraform output -raw web_url)

echo "WEB_URL: $WEB_URL"
```

---

## Step 14 – Test Web Application

```bash
# Wait for UserData script to install and start httpd
sleep 120

# Test web application
curl -s "$WEB_URL"

# Open in browser
"$BROWSER" "$WEB_URL"

echo "WEB_URL: $WEB_URL"
```

---

## Step 15 – View Terraform State

```bash
# List all resources tracked in Terraform state
terraform state list

echo "State file: terraform.tfstate (local)"
```

---

## Step 16 – Configure Remote State Backend (S3 + DynamoDB)

```bash
# Create S3 bucket for remote state storage
if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$STATE_BUCKET" \
      --region "$REGION"
else
    aws s3api create-bucket \
      --bucket "$STATE_BUCKET" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi

# Enable versioning for state recovery
aws s3api put-bucket-versioning \
  --bucket "$STATE_BUCKET" \
  --versioning-configuration Status=Enabled \
  --region "$REGION"

# Create DynamoDB table for state locking (prevents concurrent applies)
aws dynamodb create-table \
  --table-name "$LOCK_TABLE" \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION"

# Wait for table to be active
aws dynamodb wait table-exists \
  --table-name "$LOCK_TABLE" \
  --region "$REGION"

echo "STATE_BUCKET: $STATE_BUCKET"
echo "LOCK_TABLE: $LOCK_TABLE"
```

---

## Step 17 – Update Backend Configuration

```bash
# Create backend configuration for S3 remote state with DynamoDB locking
cat > backend.tf <<EOF
# Remote state backend configuration
terraform {
  backend "s3" {
    bucket         = "${STATE_BUCKET}"
    key            = "vpc/terraform.tfstate"
    region         = "${REGION}"
    dynamodb_table = "${LOCK_TABLE}"
    encrypt        = true
  }
}
EOF

# Migrate local state to S3 backend
terraform init -migrate-state -force-copy

echo "backend.tf"
```

---

## Step 18 – Verify Remote State

```bash
# Verify state file exists in S3
aws s3 ls s3://"$STATE_BUCKET"/vpc/ --region "$REGION"

# Check DynamoDB table status (provides state locking)
aws dynamodb describe-table \
  --table-name "$LOCK_TABLE" \
  --region "$REGION" \
  --query 'Table.{Name:TableName,Status:TableStatus,ItemCount:ItemCount}' \
  --output table
```

---

## Step 19 – Import Existing Resource (Demonstration)

```bash
echo ""
echo "================================================"
echo "IMPORTING EXISTING AWS RESOURCE"
echo "================================================"
echo ""

# Get VPC ID
VPC_ID=$(terraform output -raw vpc_id)
echo "VPC_ID=$VPC_ID"

# Create new resource definition (example)
## Step 19 – Import Existing Resource (Demonstration)

```bash
# Example: If you had an existing AWS resource not created by Terraform,
# you could import it into state using terraform import

# Example syntax (not executing):
# terraform import aws_instance.example i-1234567890abcdef0

# For this lab, we created everything with Terraform, so no import needed
```

---

## Step 20 – Cleanup

```bash
# Destroy infrastructure
terraform destroy -auto-approve

# Delete S3 state bucket
aws s3 rm s3://"$STATE_BUCKET" --recursive --region "$REGION"
aws s3api delete-bucket --bucket "$STATE_BUCKET" --region "$REGION"

# Delete DynamoDB table
aws dynamodb delete-table \
  --table-name "$LOCK_TABLE" \
  --region "$REGION"

# Remove project directory
cd /tmp
rm -rf "$PROJECT_DIR"

echo "Cleanup completed"
```

---

## Summary

In this lab, you have:
- Installed Terraform CLI
- Created Terraform configuration files (HCL syntax)
- Defined AWS provider, VPC, subnet, IGW, route table, EC2 instance
- Used variables for flexible configuration
- Defined outputs to export values
- Initialized Terraform project
- Validated and formatted configuration files
- Previewed changes with `terraform plan`
- Deployed infrastructure with `terraform apply`
- Configured remote state in S3 with DynamoDB locking
- Migrated local state to S3 backend
- Tested web application on deployed EC2 instance
- Learned resource import concept
- Destroyed infrastructure with `terraform destroy`

**Key Takeaways:**
- **Terraform = Multi-Cloud IaC Tool** (AWS, Azure, GCP, etc.)
- **HCL = HashiCorp Configuration Language** (declarative syntax)
- **State File = Source of Truth** (tracks real infrastructure)
- **Remote State = Team Collaboration** (S3 + DynamoDB locking)
- **Plan Before Apply = Safety** (preview changes first)

**Terraform Workflow:**
```
Write Config → terraform init → terraform plan → terraform apply → terraform destroy
```

**Terraform vs CloudFormation:**
| Feature | CloudFormation | Terraform |
|---------|---------------|-----------|
| Cloud Support | AWS only | Multi-cloud (AWS, Azure, GCP) |
| Syntax | YAML/JSON | HCL (HashiCorp) |
| State Management | AWS-managed | Explicit (local or S3) |
| Preview Changes | Change Sets | terraform plan |
| Provider Ecosystem | AWS services | 1000+ providers |
| Community | AWS-focused | Multi-cloud community |

**Terraform Advantages:**
- Multi-cloud support (not locked to AWS)
- Large provider ecosystem (AWS, Azure, GCP, Kubernetes, GitHub, etc.)
- Clear state management (explicit control)
- Human-readable HCL syntax
- Strong community and modules

---

## Best Practices

**State Management:**
- Always use remote state for teams (S3 + DynamoDB)
- Enable S3 versioning (recover from mistakes)
- Encrypt state files (contains sensitive data)
- Never commit state files to Git
- One state file per environment (dev, staging, prod)

**Configuration:**
- Use variables for flexible values
- Define outputs for important information
- Use data sources for external references
- Organize files by resource type (vpc.tf, ec2.tf)
- Format code with `terraform fmt`

**Workflow:**
- Always run `terraform plan` before `apply`
- Review plan output carefully
- Use `-auto-approve` only in automation
- Lock state during apply (DynamoDB prevents concurrent changes)
- Tag all resources consistently

**Security:**
- Don't hardcode credentials (use AWS CLI or env vars)
- Use IAM roles for EC2 instances
- Store secrets in AWS Secrets Manager (reference in Terraform)
- Enable state encryption
- Restrict S3 bucket access

**Modules:**
- Create reusable modules for common patterns
- Use Terraform Registry for community modules
- Version modules for stability
- Test modules independently

---

## Production Enhancements

1. **Workspaces (Multiple Environments)**
   ```bash
   # Create dev/prod workspaces
   terraform workspace new dev
   terraform workspace new prod
   terraform workspace select prod
   ```

2. **Variable Files**
   ```bash
   # Environment-specific values
   terraform apply -var-file="prod.tfvars"
   ```

3. **Remote Execution (Terraform Cloud)**
   ```hcl
   terraform {
     cloud {
       organization = "my-org"
       workspaces {
         name = "my-workspace"
       }
     }
   }
   ```

4. **Module Usage**
   ```hcl
   module "vpc" {
     source  = "terraform-aws-modules/vpc/aws"
     version = "5.0.0"
     
     name = "my-vpc"
     cidr = "10.0.0.0/16"
   }
   ```

5. **State Locking Timeout**
   ```bash
   # Override default lock timeout
   terraform apply -lock-timeout=10m
   ```

---

## Troubleshooting

**Terraform init fails:**
- Check internet connectivity (downloads providers)
- Verify Terraform version compatibility
- Clear `.terraform` directory and retry

**Plan shows unexpected changes:**
- Check if resources were manually modified (drift)
- Verify variable values are correct
- Review state file for inconsistencies

**Apply fails:**
- Check AWS credentials and permissions
- Review error message for specific resource
- Verify resource names don't conflict
- Check AWS service quotas

**State locked:**
- Another apply is running
- Previous apply crashed (manual unlock required)
- `terraform force-unlock <LOCK_ID>`

**Cannot destroy:**
- Check dependencies between resources
- Review Terraform destroy order
- Manually delete resources blocking destruction
- Use `-target` for specific resources

---

## Terraform Commands Reference

```bash
# Initialize project (download providers)
terraform init

# Validate configuration
terraform validate

# Format configuration files
terraform fmt

# Show execution plan
terraform plan

# Apply configuration (deploy)
terraform apply

# Apply without confirmation
terraform apply -auto-approve

# Show current state
terraform show

# List resources in state
terraform state list

# View outputs
terraform output

# Destroy infrastructure
terraform destroy

# Import existing resource
terraform import <resource_type>.<name> <resource_id>

# Create workspace
terraform workspace new <name>

# List workspaces
terraform workspace list

# Force unlock state
terraform force-unlock <LOCK_ID>
```

---

## Additional Resources

- [Terraform Documentation](https://developer.hashicorp.com/terraform/docs)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Terraform Registry](https://registry.terraform.io/) - Browse modules
- [Terraform Best Practices](https://www.terraform-best-practices.com/)
- [Learn Terraform](https://learn.hashicorp.com/terraform)
