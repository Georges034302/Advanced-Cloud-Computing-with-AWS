# Lab 1.B: IAM Groups, Roles, and Policy Management

## Overview
This lab builds upon IAM fundamentals by exploring IAM Groups and Roles. You'll learn how to organize users efficiently, create roles for AWS services, and understand policy evaluation logic. This is essential for managing permissions at scale in production environments.

## Objectives
- Create and manage IAM Groups
- Assign users to groups for efficient permission management
- Create IAM Roles for AWS service access
- Understand policy types (managed vs. inline)
- Learn policy evaluation logic and permission boundaries

## Requirements
- Completed Lab 1.A or equivalent IAM knowledge
- AWS account with administrative access
- Understanding of JSON syntax basics
- Familiarity with AWS services (EC2, S3)

## Steps

### Step 1: Create IAM Groups
1. Navigate to IAM service in AWS Console
2. Click on "User groups" in the left navigation
3. Click "Create group"
4. Create three groups with the following configurations:

**Group 1: Developers**
- Group name: `Developers`
- Attach policies: `AmazonS3FullAccess`, `AmazonEC2ReadOnlyAccess`

**Group 2: Admins**
- Group name: `Admins`
- Attach policies: `AdministratorAccess`

**Group 3: ReadOnly**
- Group name: `ReadOnly`
- Attach policies: `ReadOnlyAccess`

### Step 2: Create IAM Users and Assign to Groups
1. Create three new IAM users:
   - `dev-user-1` (assign to Developers group)
   - `admin-user-1` (assign to Admins group)
   - `auditor-user-1` (assign to ReadOnly group)
2. For each user:
   - Enable console access
   - Set a temporary password
   - Require password reset at first login
3. Verify group membership in the user's summary page

### Step 3: Create an IAM Role for EC2
1. Navigate to "Roles" in IAM
2. Click "Create role"
3. Select trusted entity type: "AWS service"
4. Choose use case: "EC2"
5. Attach permissions policies:
   - `AmazonS3ReadOnlyAccess`
6. Add tags:
   - Key: `Purpose`, Value: `Lab-EC2-S3-Access`
7. Role name: `EC2-S3-ReadOnly-Role`
8. Review and create the role

### Step 4: Create a Cross-Account Role (Simulation)
1. Create another role
2. Select trusted entity: "AWS account"
3. Enter your account ID (for simulation)
4. Attach policy: `ViewOnlyAccess`
5. Role name: `CrossAccount-ReadOnly-Role`
6. Review the trust policy JSON
7. Create the role

### Step 5: Understand Policy Evaluation
1. Navigate to IAM Policy Simulator:
   - Search for "Policy Simulator" or access via: https://policysim.aws.amazon.com
2. Select one of your users (e.g., `dev-user-1`)
3. Test different actions:
   - Service: S3, Action: PutObject → Should be allowed
   - Service: EC2, Action: TerminateInstances → Should be denied
4. Review the evaluation logic explanation

### Step 6: Create an Inline Policy
1. Select the `Developers` group
2. Click on the "Permissions" tab
3. Click "Add permissions" → "Create inline policy"
4. Use JSON editor to create a policy that denies EC2 instance termination:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Deny",
         "Action": [
           "ec2:TerminateInstances"
         ],
         "Resource": "*"
       }
     ]
   }
   ```
5. Name the policy: `DenyEC2Termination`
6. Create the policy

### Step 7: Test Permission Boundaries
1. Create a new managed policy called `BoundaryPolicy`:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:*",
           "ec2:Describe*"
         ],
         "Resource": "*"
       }
     ]
   }
   ```
2. Create a new user: `boundary-test-user`
3. Attach `AdministratorAccess` policy to the user
4. Set `BoundaryPolicy` as the permissions boundary
5. Use Policy Simulator to verify the user can only perform S3 and EC2 Describe actions

## Validation
- [ ] Three IAM groups created with appropriate policies
- [ ] Multiple users created and assigned to groups
- [ ] EC2 service role created successfully
- [ ] Cross-account role created with proper trust policy
- [ ] Policy Simulator successfully tested permission evaluation
- [ ] Inline policy created and attached to a group
- [ ] Permission boundary applied and tested

## Cleanup
1. Delete all test users:
   - `dev-user-1`, `admin-user-1`, `auditor-user-1`, `boundary-test-user`
2. Delete IAM groups:
   - `Developers`, `Admins`, `ReadOnly`
3. Delete IAM roles:
   - `EC2-S3-ReadOnly-Role`, `CrossAccount-ReadOnly-Role`
4. Delete custom policies:
   - `BoundaryPolicy`
5. Verify all resources are deleted in IAM Dashboard

## Summary
In this lab, you learned advanced IAM concepts including groups, roles, and policy management. You explored how to organize users with groups for efficient permission management, created service roles for AWS resources, and understood complex policy evaluation logic including permission boundaries. These skills are crucial for implementing secure, scalable access control in production AWS environments.

**Key Takeaways:**
- Use groups to manage permissions for multiple users efficiently
- IAM roles enable AWS services to interact with other services securely
- Policy evaluation follows a specific logic: explicit deny > explicit allow > implicit deny
- Permission boundaries set maximum permissions a user can have
- Inline policies are attached directly to a single user, group, or role
- Managed policies can be reused across multiple entities
- Always test policies with Policy Simulator before production deployment
