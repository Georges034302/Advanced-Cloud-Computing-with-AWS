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
