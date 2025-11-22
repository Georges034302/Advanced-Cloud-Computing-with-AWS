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
