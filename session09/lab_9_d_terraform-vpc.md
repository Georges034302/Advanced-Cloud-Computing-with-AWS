# Lab 9.D: Terraform Basics - Multi-Region VPC Deployment

## Overview
This lab introduces Terraform, an alternative Infrastructure as Code tool to CloudFormation. You'll learn Terraform basics, deploy a VPC in ap-southeast-2, configure remote state storage in S3 with DynamoDB locking, and use core Terraform commands: init, plan, apply, and destroy.

**💰 Cost**: FREE TIER (VPC free, S3/DynamoDB minimal)

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
echo ""
echo "Installing Terraform CLI..."

# Download and install Terraform
cd /tmp
wget https://releases.hashicorp.com/terraform/1.6.6/terraform_1.6.6_linux_amd64.zip

# Unzip and move to PATH
unzip -q terraform_1.6.6_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Verify installation
terraform version

echo ""
echo "✅ Terraform installed"
```

---

## Step 2 – Set Variables and Create Project Directory

```bash
# Set region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "REGION=$REGION"

# Set unique bucket name for state
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
STATE_BUCKET="terraform-state-${ACCOUNT_ID}"
LOCK_TABLE="terraform-state-lock"

echo "STATE_BUCKET=$STATE_BUCKET"
echo "LOCK_TABLE=$LOCK_TABLE"

# Create project directory
mkdir -p /tmp/terraform-vpc
cd /tmp/terraform-vpc

echo ""
echo "✅ Project directory created: $(pwd)"
```

---

## Step 3 – Create Provider Configuration

```bash
echo ""
echo "Creating Terraform provider configuration..."

# Create provider.tf (AWS provider configuration)
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

echo "✅ Provider configuration created: provider.tf"
```

---

## Step 4 – Create Variables File

```bash
echo ""
echo "Creating variables file..."

# Create variables.tf (input variables)
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

echo "✅ Variables defined: variables.tf"
```

---

## Step 5 – Create VPC Resources

```bash
echo ""
echo "Creating VPC resources configuration..."

# Create vpc.tf (network infrastructure)
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

echo "✅ VPC resources defined: vpc.tf"
```

---

## Step 6 – Create EC2 Instance Configuration

```bash
echo ""
echo "Creating EC2 instance configuration..."

# Create ec2.tf (compute resources)
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

echo "✅ EC2 instance defined: ec2.tf"
```

---

## Step 7 – Create Outputs File

```bash
echo ""
echo "Creating outputs file..."

# Create outputs.tf (export values)
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

echo "✅ Outputs defined: outputs.tf"
```

---

## Step 8 – Initialize Terraform

```bash
echo ""
echo "================================================"
echo "INITIALIZING TERRAFORM PROJECT"
echo "================================================"
echo ""

# Initialize Terraform (downloads providers)
terraform init

echo ""
echo "✅ Terraform initialized"
echo "This downloaded AWS provider and set up working directory"
```

---

## Step 9 – Validate Configuration

```bash
echo ""
echo "Validating Terraform configuration..."

# Validate syntax and configuration
terraform validate

echo ""
echo "✅ Configuration is valid"
```

---

## Step 10 – Format Configuration Files

```bash
echo ""
echo "Formatting Terraform files..."

# Format all .tf files (consistent style)
terraform fmt

echo ""
echo "✅ Files formatted"
```

---

## Step 11 – Preview Changes (Terraform Plan)

```bash
echo ""
echo "================================================"
echo "CREATING EXECUTION PLAN"
echo "================================================"
echo ""

# Generate execution plan (preview changes)
terraform plan

echo ""
echo "✅ Plan shows all resources to be created"
echo "Review the plan carefully before applying"
```

---

## Step 12 – Apply Configuration (Deploy Infrastructure)

```bash
echo ""
echo "================================================"
echo "APPLYING TERRAFORM CONFIGURATION"
echo "================================================"
echo ""

# Apply configuration (deploy resources)
terraform apply -auto-approve

echo ""
echo "✅ Infrastructure deployed!"
```

---

## Step 13 – View Outputs

```bash
echo ""
echo "Terraform outputs:"

# Display all outputs
terraform output

echo ""

# Get specific output
WEB_URL=$(terraform output -raw web_url)
echo "Web Application: $WEB_URL"
```

---

## Step 14 – Test Web Application

```bash
echo ""
echo "Testing web application (waiting 2 minutes for initialization)..."
sleep 120

# Test HTTP endpoint
curl -s "$WEB_URL"

echo ""
echo ""
echo "✅ Application working!"
echo "Open in browser: $WEB_URL"
```

---

## Step 15 – View Terraform State

```bash
echo ""
echo "Viewing Terraform state..."

# List resources in state
terraform state list

echo ""
echo "State file location: terraform.tfstate (local)"
echo "Contains all resource IDs and metadata"
```

---

## Step 16 – Configure Remote State Backend (S3 + DynamoDB)

```bash
echo ""
echo "================================================"
echo "CONFIGURING REMOTE STATE BACKEND"
echo "================================================"
echo ""

# Create S3 bucket for state
echo "Creating S3 bucket for remote state..."

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

# Enable versioning (protect against accidental deletion)
aws s3api put-bucket-versioning \
  --bucket "$STATE_BUCKET" \
  --versioning-configuration Status=Enabled \
  --region "$REGION"

echo "✅ S3 bucket created: $STATE_BUCKET"

# Create DynamoDB table for state locking
echo "Creating DynamoDB table for state locking..."

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

echo "✅ DynamoDB table created: $LOCK_TABLE"
```

---

## Step 17 – Update Backend Configuration

```bash
echo ""
echo "Updating Terraform backend configuration..."

# Add backend configuration to provider.tf
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

echo "✅ Backend configuration created: backend.tf"

# Reinitialize with backend
echo ""
echo "Migrating state to S3..."

terraform init -migrate-state -force-copy

echo ""
echo "✅ State migrated to S3"
echo "State now stored remotely with locking enabled"
```

---

## Step 18 – Verify Remote State

```bash
echo ""
echo "Verifying remote state..."

# Check S3 bucket
aws s3 ls s3://"$STATE_BUCKET"/vpc/ --region "$REGION"

echo ""
echo "✅ State file in S3: vpc/terraform.tfstate"

# Check DynamoDB table
aws dynamodb describe-table \
  --table-name "$LOCK_TABLE" \
  --region "$REGION" \
  --query 'Table.{Name:TableName,Status:TableStatus,ItemCount:ItemCount}' \
  --output table

echo ""
echo "DynamoDB table provides state locking (prevents concurrent applies)"
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
cat > import-demo.tf <<'EOF'
# Example: Import existing VPC (demonstration only)
# resource "aws_vpc" "imported" {
#   cidr_block = "10.0.0.0/16"
#   
#   tags = {
#     Name = "imported-vpc"
#   }
# }
EOF

echo ""
echo "✅ Import example created"
echo ""
echo "To import existing resources:"
echo "terraform import aws_vpc.imported $VPC_ID"
echo ""
echo "This associates existing AWS resource with Terraform state"
echo "(We'll skip actual import to keep lab simple)"
```

---

## Step 20 – Cleanup

```bash
echo ""
echo "Cleaning up all resources..."

# Destroy infrastructure
terraform destroy -auto-approve

echo "✅ Infrastructure destroyed"

# Delete S3 state bucket
echo "Deleting S3 state bucket..."

aws s3 rm s3://"$STATE_BUCKET" --recursive --region "$REGION"
aws s3api delete-bucket --bucket "$STATE_BUCKET" --region "$REGION"

echo "✅ S3 bucket deleted"

# Delete DynamoDB table
echo "Deleting DynamoDB table..."

aws dynamodb delete-table \
  --table-name "$LOCK_TABLE" \
  --region "$REGION"

echo "✅ DynamoDB table deleted"
echo ""
echo "All resources cleaned up!"
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
