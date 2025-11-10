# Lab 1.A: Introduction to AWS Console and IAM Basics

## Overview
This lab introduces you to the AWS Management Console and AWS Identity and Access Management (IAM). You'll learn how to navigate the console, understand the global infrastructure, and create your first IAM user with proper security practices.

## Objectives
- Navigate the AWS Management Console effectively
- Understand AWS global infrastructure (Regions and Availability Zones)
- Create IAM users with appropriate permissions
- Configure Multi-Factor Authentication (MFA)
- Apply the principle of least privilege

## Requirements
- An AWS account (Free Tier eligible)
- Access to AWS Management Console
- A smartphone or MFA device for authentication
- Basic understanding of cloud computing concepts

## Steps

### Step 1: Explore the AWS Console
1. Sign in to the AWS Management Console
2. Navigate through different service categories:
   - Compute
   - Storage
   - Database
   - Networking & Content Delivery
3. Explore the region selector in the top-right corner
4. Review available regions and their codes (e.g., us-east-1, eu-west-1)

### Step 2: Understand the IAM Dashboard
1. Navigate to IAM service (search for "IAM" in the services search bar)
2. Review the IAM Dashboard showing security recommendations
3. Note the IAM resources summary (Users, Groups, Roles, Policies)
4. Review the security status indicators

### Step 3: Create an IAM User
1. In the IAM Dashboard, click on "Users" in the left navigation
2. Click "Add users" button
3. Set user details:
   - Username: `lab-user-admin`
   - Select AWS credential type: Both Console and Programmatic access
4. Set permissions:
   - Attach existing policies directly
   - Select `AdministratorAccess` (for learning purposes only)
5. Add tags (optional):
   - Key: `Environment`, Value: `Lab`
6. Review and create the user
7. Download the credentials CSV file securely

### Step 4: Enable MFA for Root Account
1. Return to IAM Dashboard
2. Under Security Recommendations, select "Add MFA for root user"
3. Click "Manage MFA"
4. Choose "Virtual MFA device"
5. Use an authenticator app (Google Authenticator, Authy, etc.)
6. Scan the QR code
7. Enter two consecutive MFA codes
8. Complete MFA activation

### Step 5: Create a Custom IAM Policy
1. Navigate to Policies in IAM
2. Click "Create policy"
3. Use the Visual editor or JSON editor
4. Create a policy that allows read-only access to S3:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:ListBucket"
         ],
         "Resource": "*"
       }
     ]
   }
   ```
5. Name the policy: `S3ReadOnlyCustom`
6. Create the policy

## Validation
- [ ] Successfully logged into AWS Management Console
- [ ] Created at least one IAM user with console access
- [ ] MFA is enabled on the root account
- [ ] Custom IAM policy created successfully
- [ ] Can identify different AWS regions and their purposes
- [ ] Understand the difference between users, groups, and roles

## Cleanup
1. Navigate to IAM Users
2. Delete the test user `lab-user-admin`:
   - Select the user
   - Click "Delete user"
   - Confirm deletion
3. Delete the custom policy `S3ReadOnlyCustom`:
   - Navigate to Policies
   - Search for your policy
   - Select and delete
4. Keep MFA enabled on root account (security best practice)

## Summary
In this lab, you learned the fundamentals of AWS IAM and console navigation. You created IAM users, configured MFA for enhanced security, and created custom policies. These skills form the foundation for secure AWS resource management. Remember to always follow the principle of least privilege when assigning permissions and enable MFA for all users with console access.

**Key Takeaways:**
- IAM is a free service and essential for AWS security
- Always enable MFA for enhanced security
- Use IAM users instead of root account for daily operations
- Apply least privilege principle when assigning permissions
- Regularly review and audit IAM permissions
