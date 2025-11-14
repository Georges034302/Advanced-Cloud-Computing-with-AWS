# Lab 2.A: IAM Users, Groups, and Custom Policies
<img width="1536" height="849" alt="IMG" src="https://github.com/user-attachments/assets/b2a3a015-330c-40a6-9bdd-9d1a95d00e15" />

## Overview
This lab demonstrates how to implement AWS Identity and Access Management (IAM) following the principle of least privilege. You will create IAM users, groups, and custom policies, configure roles for EC2 instances, test permissions, and apply security best practices.

---

## Objectives
- Create IAM users and groups with least-privilege access
- Write and attach custom managed policies using JSON
- Create IAM roles with trust policies for EC2
- Test effective permissions using the policy simulator
- Apply permission boundaries to limit maximum permissions

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions to create users, groups, roles, and policies
- Basic understanding of JSON and IAM concepts
- jq installed for JSON parsing (optional)

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Generate random bucket suffix
RAND=$(openssl rand -hex 4)
echo "RAND=$RAND"

# Set region
REGION="ap-southeast-2"
echo "REGION=$REGION"

# Set bucket name for testing
BUCKET_NAME="iam-lab-test-bucket-${RAND}"
echo "BUCKET_NAME=$BUCKET_NAME"

# Verify AWS CLI is configured
aws sts get-caller-identity

# Check if jq is installed (optional but useful)
which jq || echo "jq not installed (optional)"
```
---

## Step 2 – Create S3 Bucket for Testing

```bash
# Create S3 bucket for IAM policy testing
aws s3 mb s3://$BUCKET_NAME \
  --region $REGION

# Verify bucket was created
aws s3 ls | grep $BUCKET_NAME

# Upload a test file to the bucket
echo "This is a test file for IAM permissions" > test-file.txt

# Upload test file to S3
aws s3 cp test-file.txt s3://$BUCKET_NAME/

# Verify file was uploaded
aws s3 ls s3://$BUCKET_NAME/
```

---

## Step 3 – Create IAM Groups and Users

```bash
# Set group and user names
GROUP_NAME="lab-developers"
echo "GROUP_NAME=$GROUP_NAME"

USER_ALICE="alice"
echo "USER_ALICE=$USER_ALICE"

USER_BOB="bob"
echo "USER_BOB=$USER_BOB"

# Create IAM group
aws iam create-group \
  --group-name $GROUP_NAME

# Verify group was created
aws iam get-group \
  --group-name $GROUP_NAME

# Create IAM users
aws iam create-user \
  --user-name $USER_ALICE

aws iam create-user \
  --user-name $USER_BOB

# Verify users were created
aws iam list-users \
  --query 'Users[?UserName==`alice` || UserName==`bob`]'

# Add users to group
aws iam add-user-to-group \
  --user-name $USER_ALICE \
  --group-name $GROUP_NAME

aws iam add-user-to-group \
  --user-name $USER_BOB \
  --group-name $GROUP_NAME

# Verify users are in the group
aws iam get-group \
  --group-name $GROUP_NAME \
  --query 'Users[*].UserName'
```
---

## Step 4 – Create Custom Managed Policy (Least Privilege)

```bash
# Set policy name
POLICY_NAME="LabS3ReadOnly"
echo "POLICY_NAME=$POLICY_NAME"

# Create policy JSON file with least-privilege S3 read-only access
cat > s3-read-only-lab.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowListAndGetS3Lab",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::${BUCKET_NAME}",
        "arn:aws:s3:::${BUCKET_NAME}/*"
      ]
    }
  ]
}
EOF

# Verify the policy file was created
cat s3-read-only-lab.json

# Create the customer-managed policy
POLICY_ARN=$(aws iam create-policy \
  --policy-name $POLICY_NAME \
  --policy-document file://s3-read-only-lab.json \
  --query 'Policy.Arn' \
  --output text)
echo "POLICY_ARN=$POLICY_ARN"

# Verify policy was created
aws iam get-policy \
  --policy-arn $POLICY_ARN

# Attach policy to the group
aws iam attach-group-policy \
  --group-name $GROUP_NAME \
  --policy-arn $POLICY_ARN

# Verify policy is attached to group
aws iam list-attached-group-policies \
  --group-name $GROUP_NAME
```
---

## Step 5 – Create IAM Role for EC2 with Trust Policy

```bash
# Set role and instance profile names
ROLE_NAME="lab-ec2-role"
echo "ROLE_NAME=$ROLE_NAME"

INSTANCE_PROFILE_NAME="lab-ec2-instance-profile"
echo "INSTANCE_PROFILE_NAME=$INSTANCE_PROFILE_NAME"

# Create EC2 trust policy JSON file
cat > ec2-trust.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Verify trust policy file
cat ec2-trust.json

# Create the IAM role with trust policy
aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document file://ec2-trust.json

# Verify role was created
aws iam get-role \
  --role-name $ROLE_NAME

# Attach AWS managed S3 read-only policy to the role
aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Verify policy is attached to role
aws iam list-attached-role-policies \
  --role-name $ROLE_NAME

# Create instance profile for EC2
aws iam create-instance-profile \
  --instance-profile-name $INSTANCE_PROFILE_NAME

# Add role to instance profile
aws iam add-role-to-instance-profile \
  --instance-profile-name $INSTANCE_PROFILE_NAME \
  --role-name $ROLE_NAME

# Verify instance profile was created
aws iam get-instance-profile \
  --instance-profile-name $INSTANCE_PROFILE_NAME
```
---

## Step 6 – Create Inline Policy for Specific User

```bash
# Set inline policy name
INLINE_POLICY_NAME="DescribeEC2Only"
echo "INLINE_POLICY_NAME=$INLINE_POLICY_NAME"

# Create inline policy JSON file for Alice
cat > alice-inline.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowDescribeEC2Instances",
      "Effect": "Allow",
      "Action": "ec2:DescribeInstances",
      "Resource": "*"
    }
  ]
}
EOF

# Verify inline policy file
cat alice-inline.json

# Attach inline policy to Alice
aws iam put-user-policy \
  --user-name $USER_ALICE \
  --policy-name $INLINE_POLICY_NAME \
  --policy-document file://alice-inline.json

# Verify inline policy is attached
aws iam list-user-policies \
  --user-name $USER_ALICE

# Get inline policy details
aws iam get-user-policy \
  --user-name $USER_ALICE \
  --policy-name $INLINE_POLICY_NAME
```

> **Note:** Inline policies are useful for one-off permissions specific to a single user. For reusable permissions, prefer managed policies attached to groups.

---

## Step 7 – Apply Permission Boundary

```bash
# Set permission boundary policy name
BOUNDARY_POLICY_NAME="LabPermissionBoundary"
echo "BOUNDARY_POLICY_NAME=$BOUNDARY_POLICY_NAME"

# Set limited user name
LIMITED_USER="limited-user"
echo "LIMITED_USER=$LIMITED_USER"

# Create permission boundary policy JSON
# This defines the MAXIMUM permissions the user can have
cat > boundary.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowS3ReadOnlyMaximum",
      "Effect": "Allow",
      "Action": [
        "s3:Get*",
        "s3:List*"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowEC2ReadOnlyMaximum",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Verify permission boundary file
cat boundary.json

# Create permission boundary policy
BOUNDARY_ARN=$(aws iam create-policy \
  --policy-name $BOUNDARY_POLICY_NAME \
  --policy-document file://boundary.json \
  --query 'Policy.Arn' \
  --output text)
echo "BOUNDARY_ARN=$BOUNDARY_ARN"

# Create user with permission boundary
aws iam create-user \
  --user-name $LIMITED_USER \
  --permissions-boundary $BOUNDARY_ARN

# Verify user was created with boundary
aws iam get-user \
  --user-name $LIMITED_USER

# Try to attach a policy that grants more than the boundary allows
# Create a policy that includes S3 write permissions
cat > limited-user-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:*",
      "Resource": "*"
    }
  ]
}
EOF

# Attach inline policy to limited user
aws iam put-user-policy \
  --user-name $LIMITED_USER \
  --policy-name "S3FullAccess" \
  --policy-document file://limited-user-policy.json

# The user will only have S3 read permissions due to the permission boundary
echo "Permission boundary limits user to read-only S3 and EC2 describe actions only"
```

> **Note:** Permission boundaries set the maximum permissions. Even if you attach a policy with s3:*, the user can only perform s3:Get* and s3:List* due to the boundary.
---

## Step 8 – Simulate and Validate Permissions

```bash
# Get user ARN for simulation
ALICE_ARN=$(aws iam get-user \
  --user-name $USER_ALICE \
  --query 'User.Arn' \
  --output text)
echo "ALICE_ARN=$ALICE_ARN"

# Simulate Alice's permissions for S3 GetObject (should be allowed via group)
echo "Testing Alice's S3 GetObject permission (should be allowed)..."
aws iam simulate-principal-policy \
  --policy-source-arn $ALICE_ARN \
  --action-names s3:GetObject \
  --resource-arns "arn:aws:s3:::${BUCKET_NAME}/*"

# Simulate Alice's permissions for S3 DeleteObject (should be denied)
echo "Testing Alice's S3 DeleteObject permission (should be denied)..."
aws iam simulate-principal-policy \
  --policy-source-arn $ALICE_ARN \
  --action-names s3:DeleteObject \
  --resource-arns "arn:aws:s3:::${BUCKET_NAME}/*"

# Simulate Alice's EC2 DescribeInstances permission (should be allowed via inline policy)
echo "Testing Alice's EC2 DescribeInstances permission (should be allowed)..."
aws iam simulate-principal-policy \
  --policy-source-arn $ALICE_ARN \
  --action-names ec2:DescribeInstances \
  --resource-arns "*"

# Test limited-user with permission boundary
LIMITED_USER_ARN=$(aws iam get-user \
  --user-name $LIMITED_USER \
  --query 'User.Arn' \
  --output text)
echo "LIMITED_USER_ARN=$LIMITED_USER_ARN"

# Simulate limited-user's S3 PutObject (should be denied by boundary)
echo "Testing limited-user's S3 PutObject (should be denied by boundary)..."
aws iam simulate-principal-policy \
  --policy-source-arn $LIMITED_USER_ARN \
  --action-names s3:PutObject \
  --resource-arns "arn:aws:s3:::${BUCKET_NAME}/*"
```

---

## Step 9 – Cleanup Resources

```bash
# Delete access keys for Alice
echo "Deleting access keys for Alice..."
aws iam list-access-keys \
  --user-name $USER_ALICE \
  --query 'AccessKeyMetadata[*].AccessKeyId' \
  --output text | while read key_id; do
    aws iam delete-access-key \
      --user-name $USER_ALICE \
      --access-key-id $key_id
    echo "Deleted access key: $key_id"
done

# Remove inline policy from Alice
aws iam delete-user-policy \
  --user-name $USER_ALICE \
  --policy-name $INLINE_POLICY_NAME

# Remove users from group
aws iam remove-user-from-group \
  --user-name $USER_ALICE \
  --group-name $GROUP_NAME

aws iam remove-user-from-group \
  --user-name $USER_BOB \
  --group-name $GROUP_NAME

# Detach managed policy from group
aws iam detach-group-policy \
  --group-name $GROUP_NAME \
  --policy-arn $POLICY_ARN

# Delete group
aws iam delete-group \
  --group-name $GROUP_NAME

# Delete users
aws iam delete-user \
  --user-name $USER_ALICE

aws iam delete-user \
  --user-name $USER_BOB

# Delete inline policy from limited-user
aws iam delete-user-policy \
  --user-name $LIMITED_USER \
  --policy-name "S3FullAccess"

# Delete limited-user
aws iam delete-user \
  --user-name $LIMITED_USER

# Delete custom managed policy
aws iam delete-policy \
  --policy-arn $POLICY_ARN

# Delete permission boundary policy
aws iam delete-policy \
  --policy-arn $BOUNDARY_ARN

# Remove role from instance profile
aws iam remove-role-from-instance-profile \
  --instance-profile-name $INSTANCE_PROFILE_NAME \
  --role-name $ROLE_NAME

# Delete instance profile
aws iam delete-instance-profile \
  --instance-profile-name $INSTANCE_PROFILE_NAME

# Detach policy from role
aws iam detach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Delete role
aws iam delete-role \
  --role-name $ROLE_NAME

# Delete S3 bucket contents and bucket
aws s3 rm s3://$BUCKET_NAME \
  --recursive

aws s3 rb s3://$BUCKET_NAME

# Remove local JSON files
rm -f s3-read-only-lab.json \
  ec2-trust.json \
  alice-inline.json \
  boundary.json \
  limited-user-policy.json \
  test-file.txt

# Verify cleanup
echo "Verifying cleanup..."
aws iam list-users \
  --query 'Users[?UserName==`alice` || UserName==`bob` || UserName==`limited-user`]' || echo "Users deleted"

aws iam list-groups \
  --query 'Groups[?GroupName==`lab-developers`]' || echo "Group deleted"

aws s3 ls | grep $BUCKET_NAME || echo "S3 bucket deleted"

echo "Cleanup completed successfully"
```

---

## Summary

In this lab, you have:
- Created IAM users, groups, and implemented least-privilege access control
- Developed custom managed policies using JSON for specific S3 access
- Created IAM roles with trust policies for EC2 instance profiles
- Applied inline policies for user-specific permissions
- Implemented permission boundaries to limit maximum permissions
- Used the IAM policy simulator to validate effective permissions
- Successfully cleaned up all IAM resources and test infrastructure

---
