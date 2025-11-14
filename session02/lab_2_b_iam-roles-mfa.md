# Lab 2.B: IAM Roles and MFA for Secure Access
<img width="1418" height="864" alt="IMG" src="https://github.com/user-attachments/assets/13012146-e2db-4898-9786-0a0e127a7b9d" />

## Overview
This lab demonstrates how to create and configure IAM roles for cross-account or service access, require Multi-Factor Authentication (MFA) for privileged operations, and validate role assumption and MFA enforcement using the AWS CLI.

---

## Objectives
- Create IAM roles with proper trust policies (EC2, cross-account)
- Attach least-privilege managed or customer-managed policies to roles
- Require and enforce MFA for sensitive actions using IAM policies
- Use `sts:AssumeRole` and `sts:GetSessionToken` with MFA
- Test and validate role-based and MFA-protected access
- Clean up all IAM resources

---

## Prerequisites
- IAM permissions to create roles and policies
- MFA device (virtual or hardware) for testing
- Browser access for console MFA setup
- jq installed (optional but helpful)

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID dynamically
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set region
REGION="ap-southeast-2"
echo "REGION=$REGION"

# Set bucket name for MFA testing
BUCKET_NAME="mfa-test-bucket-${ACCOUNT_ID}"
echo "BUCKET_NAME=$BUCKET_NAME"

# Verify AWS CLI is configured
aws sts get-caller-identity

# Get current user ARN
USER_ARN=$(aws sts get-caller-identity \
  --query Arn \
  --output text)
echo "USER_ARN=$USER_ARN"

# Extract username from ARN
CURRENT_USER=$(echo $USER_ARN | cut -d'/' -f2)
echo "CURRENT_USER=$CURRENT_USER"
```

---

## Step 2 – Create S3 Test Bucket

```bash
# Create S3 bucket for MFA policy testing
aws s3api create-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

# Verify bucket creation
aws s3 ls | grep "$BUCKET_NAME"
```

---

## Step 3 – Create IAM Role for EC2 Service

```bash
# Set role name
ROLE_NAME="EC2ReadOnlyRole"
echo "ROLE_NAME=$ROLE_NAME"

# Create trust policy JSON for EC2 service
cat > trust-ec2.json <<EOF
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

# Display the trust policy
cat trust-ec2.json

# Create the IAM role with EC2 trust policy
aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document file://trust-ec2.json \
  --description "Role for EC2 instances with read-only access to S3"

# Attach AWS managed policy for S3 read-only access
aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Verify role creation
aws iam get-role \
  --role-name "$ROLE_NAME" \
  --query 'Role.[RoleName,Arn,CreateDate]' \
  --output table

# List attached policies
aws iam list-attached-role-policies \
  --role-name "$ROLE_NAME" \
  --output table
```

---

## Step 4 – Create Cross-Account IAM Role

```bash
# Set cross-account role name
CROSS_ROLE_NAME="CrossAccountAdminRole"
echo "CROSS_ROLE_NAME=$CROSS_ROLE_NAME"

# Set trusted account ID (replace with actual trusted AWS account ID)
# For demo purposes, using the same account ID
TRUSTED_ACCOUNT_ID="$ACCOUNT_ID"
echo "TRUSTED_ACCOUNT_ID=$TRUSTED_ACCOUNT_ID"

# Create cross-account trust policy JSON
cat > cross-trust.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::${TRUSTED_ACCOUNT_ID}:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "Bool": {
          "aws:MultiFactorAuthPresent": "true"
        }
      }
    }
  ]
}
EOF

# Display the trust policy
cat cross-trust.json

# Create the cross-account role
aws iam create-role \
  --role-name "$CROSS_ROLE_NAME" \
  --assume-role-policy-document file://cross-trust.json \
  --description "Cross-account role requiring MFA for assumption"

# Attach AWS managed policy for admin access
aws iam attach-role-policy \
  --role-name "$CROSS_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

# Verify role creation
aws iam get-role \
  --role-name "$CROSS_ROLE_NAME" \
  --query 'Role.[RoleName,Arn,CreateDate]' \
  --output table

# List attached policies
aws iam list-attached-role-policies \
  --role-name "$CROSS_ROLE_NAME" \
  --output table
```

---

## Step 5 – Create MFA Enforcement Policy

```bash
# Set MFA policy name
MFA_POLICY_NAME="MFARequiredForDelete"
echo "MFA_POLICY_NAME=$MFA_POLICY_NAME"

# Create MFA enforcement policy JSON
cat > mfa-required-delete.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowListActions",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyDeleteWithoutMFA",
      "Effect": "Deny",
      "Action": [
        "s3:DeleteBucket",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/*",
      "Condition": {
        "BoolIfExists": {
          "aws:MultiFactorAuthPresent": "false"
        }
      }
    }
  ]
}
EOF

# Display the policy document
cat mfa-required-delete.json

# Create the IAM policy
MFA_POLICY_ARN=$(aws iam create-policy \
  --policy-name "$MFA_POLICY_NAME" \
  --policy-document file://mfa-required-delete.json \
  --description "Requires MFA for S3 delete operations" \
  --query 'Policy.Arn' \
  --output text)
echo "MFA_POLICY_ARN=$MFA_POLICY_ARN"

# Verify policy creation
aws iam get-policy \
  --policy-arn "$MFA_POLICY_ARN" \
  --query 'Policy.[PolicyName,Arn,CreateDate]' \
  --output table

# Get policy version details
aws iam get-policy-version \
  --policy-arn "$MFA_POLICY_ARN" \
  --version-id v1 \
  --query 'PolicyVersion.Document' \
  --output json
```

---

## Step 6 – Attach MFA Policy to Current User

```bash
# Attach MFA policy to current user
aws iam attach-user-policy \
  --user-name "$CURRENT_USER" \
  --policy-arn "$MFA_POLICY_ARN"

# Verify policy attachment
aws iam list-attached-user-policies \
  --user-name "$CURRENT_USER" \
  --output table
```

---

## Step 7 – Set Up MFA Device (Virtual MFA)

```bash
# Create virtual MFA device
MFA_DEVICE_NAME="${CURRENT_USER}-mfa"
echo "MFA_DEVICE_NAME=$MFA_DEVICE_NAME"

# Create virtual MFA device
MFA_SERIAL=$(aws iam create-virtual-mfa-device \
  --virtual-mfa-device-name "$MFA_DEVICE_NAME" \
  --outfile qr-code.png \
  --bootstrap-method QRCodePNG \
  --query 'VirtualMFADevice.SerialNumber' \
  --output text)
echo "MFA_SERIAL=$MFA_SERIAL"

echo "QR code saved to qr-code.png"
echo "Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)"
echo ""
echo "After scanning, enter two consecutive MFA codes:"
read -p "Enter first MFA code: " MFA_CODE1
read -p "Enter second MFA code: " MFA_CODE2

# Enable MFA device for user
aws iam enable-mfa-device \
  --user-name "$CURRENT_USER" \
  --serial-number "$MFA_SERIAL" \
  --authentication-code-1 "$MFA_CODE1" \
  --authentication-code-2 "$MFA_CODE2"

# Verify MFA device is enabled
aws iam list-mfa-devices \
  --user-name "$CURRENT_USER" \
  --output table
```

---

## Step 8 – Test MFA with Session Token

```bash
# Test S3 access WITHOUT MFA session (should fail for delete operations)
echo "Testing S3 access without MFA session..."

# This should work (List/Get allowed without MFA)
aws s3 ls "s3://${BUCKET_NAME}/" || echo "Bucket is empty or access denied"

# Create test object
echo "Test content" > test-file.txt
aws s3 cp test-file.txt "s3://${BUCKET_NAME}/test-file.txt"

# This should FAIL (Delete requires MFA)
aws s3 rm "s3://${BUCKET_NAME}/test-file.txt" || echo "Delete denied without MFA (expected)"

echo ""
echo "Now testing with MFA session..."
read -p "Enter current MFA code: " MFA_CODE

# Get session token with MFA
SESSION_OUTPUT=$(aws sts get-session-token \
  --serial-number "$MFA_SERIAL" \
  --token-code "$MFA_CODE" \
  --duration-seconds 3600)

# Extract temporary credentials
export AWS_ACCESS_KEY_ID=$(echo $SESSION_OUTPUT | jq -r '.Credentials.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo $SESSION_OUTPUT | jq -r '.Credentials.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo $SESSION_OUTPUT | jq -r '.Credentials.SessionToken')

echo "Temporary MFA session credentials set"
echo "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID"

# Verify MFA session is active
aws sts get-caller-identity

# This should now SUCCEED (Delete with MFA session)
aws s3 rm "s3://${BUCKET_NAME}/test-file.txt"
echo "Delete succeeded with MFA session"

# Unset temporary credentials to return to normal session
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN

echo "Returned to normal session (without MFA)"
```

---

## Step 9 – Test Cross-Account Role Assumption with MFA

```bash
# Construct cross-account role ARN
CROSS_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${CROSS_ROLE_NAME}"
echo "CROSS_ROLE_ARN=$CROSS_ROLE_ARN"

echo "Attempting to assume cross-account role (requires MFA)..."
read -p "Enter current MFA code: " MFA_CODE

# Assume role with MFA
ASSUMED_ROLE_OUTPUT=$(aws sts assume-role \
  --role-arn "$CROSS_ROLE_ARN" \
  --role-session-name "mfa-test-session" \
  --serial-number "$MFA_SERIAL" \
  --token-code "$MFA_CODE" \
  --duration-seconds 3600)

# Extract assumed role credentials
export AWS_ACCESS_KEY_ID=$(echo $ASSUMED_ROLE_OUTPUT | jq -r '.Credentials.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo $ASSUMED_ROLE_OUTPUT | jq -r '.Credentials.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo $ASSUMED_ROLE_OUTPUT | jq -r '.Credentials.SessionToken')

echo "Assumed role credentials set"

# Verify assumed role identity
aws sts get-caller-identity

# Test admin permissions (list IAM users as admin)
aws iam list-users \
  --query 'Users[].UserName' \
  --output table

# Unset assumed role credentials
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN

echo "Returned to normal session"
```

---

## Step 10 – Enable Console MFA Enforcement

```bash
# Create policy to enforce MFA for console access
CONSOLE_MFA_POLICY_NAME="EnforceMFAForConsole"
echo "CONSOLE_MFA_POLICY_NAME=$CONSOLE_MFA_POLICY_NAME"

# Create console MFA enforcement policy JSON
cat > console-mfa-enforcement.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowViewAccountInfo",
      "Effect": "Allow",
      "Action": [
        "iam:GetAccountPasswordPolicy",
        "iam:ListVirtualMFADevices"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowManageOwnPasswords",
      "Effect": "Allow",
      "Action": [
        "iam:ChangePassword",
        "iam:GetUser"
      ],
      "Resource": "arn:aws:iam::*:user/\${aws:username}"
    },
    {
      "Sid": "AllowManageOwnMFA",
      "Effect": "Allow",
      "Action": [
        "iam:CreateVirtualMFADevice",
        "iam:DeleteVirtualMFADevice",
        "iam:EnableMFADevice",
        "iam:ListMFADevices",
        "iam:ResyncMFADevice"
      ],
      "Resource": [
        "arn:aws:iam::*:mfa/\${aws:username}",
        "arn:aws:iam::*:user/\${aws:username}"
      ]
    },
    {
      "Sid": "DenyAllExceptListedIfNoMFA",
      "Effect": "Deny",
      "NotAction": [
        "iam:CreateVirtualMFADevice",
        "iam:EnableMFADevice",
        "iam:GetUser",
        "iam:ListMFADevices",
        "iam:ListVirtualMFADevices",
        "iam:ResyncMFADevice",
        "sts:GetSessionToken"
      ],
      "Resource": "*",
      "Condition": {
        "BoolIfExists": {
          "aws:MultiFactorAuthPresent": "false"
        }
      }
    }
  ]
}
EOF

# Display the policy document
cat console-mfa-enforcement.json

# Create the IAM policy
CONSOLE_MFA_POLICY_ARN=$(aws iam create-policy \
  --policy-name "$CONSOLE_MFA_POLICY_NAME" \
  --policy-document file://console-mfa-enforcement.json \
  --description "Enforces MFA for AWS Console access" \
  --query 'Policy.Arn' \
  --output text)
echo "CONSOLE_MFA_POLICY_ARN=$CONSOLE_MFA_POLICY_ARN"

# Verify policy creation
aws iam get-policy \
  --policy-arn "$CONSOLE_MFA_POLICY_ARN" \
  --query 'Policy.[PolicyName,Arn,CreateDate]' \
  --output table

echo ""
echo "To enforce console MFA for a user, attach this policy:"
echo "aws iam attach-user-policy --user-name <username> --policy-arn $CONSOLE_MFA_POLICY_ARN"
```

---

## Step 11 – Cleanup Resources

```bash
# Detach MFA policy from current user
echo "Detaching MFA policy from user..."
aws iam detach-user-policy \
  --user-name "$CURRENT_USER" \
  --policy-arn "$MFA_POLICY_ARN"

# Disable and delete MFA device
echo "Disabling MFA device..."
aws iam deactivate-mfa-device \
  --user-name "$CURRENT_USER" \
  --serial-number "$MFA_SERIAL"

echo "Deleting virtual MFA device..."
aws iam delete-virtual-mfa-device \
  --serial-number "$MFA_SERIAL"

# Delete MFA enforcement policy
echo "Deleting MFA enforcement policy..."
aws iam delete-policy \
  --policy-arn "$MFA_POLICY_ARN"

# Delete console MFA enforcement policy
echo "Deleting console MFA enforcement policy..."
aws iam delete-policy \
  --policy-arn "$CONSOLE_MFA_POLICY_ARN"

# Detach and delete EC2 role
echo "Detaching policies from EC2 role..."
aws iam detach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

echo "Deleting EC2 role..."
aws iam delete-role \
  --role-name "$ROLE_NAME"

# Detach and delete cross-account role
echo "Detaching policies from cross-account role..."
aws iam detach-role-policy \
  --role-name "$CROSS_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

echo "Deleting cross-account role..."
aws iam delete-role \
  --role-name "$CROSS_ROLE_NAME"

# Empty and delete S3 bucket
echo "Emptying S3 bucket..."
aws s3 rm "s3://${BUCKET_NAME}" --recursive

echo "Deleting S3 bucket..."
aws s3api delete-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$REGION"

# Verify S3 bucket deletion
aws s3 ls | grep "$BUCKET_NAME" || echo "Bucket deleted successfully"

# Delete local JSON and image files
echo "Cleaning up local files..."
rm -f trust-ec2.json cross-trust.json mfa-required-delete.json console-mfa-enforcement.json qr-code.png test-file.txt

# Verify IAM roles are deleted
echo "Verifying role cleanup..."
aws iam list-roles \
  --query "Roles[?contains(RoleName,'EC2ReadOnlyRole') || contains(RoleName,'CrossAccountAdminRole')].RoleName" \
  --output table

# Verify IAM policies are deleted
echo "Verifying policy cleanup..."
aws iam list-policies \
  --scope Local \
  --query "Policies[?contains(PolicyName,'MFARequired') || contains(PolicyName,'EnforceMFA')].PolicyName" \
  --output table

# Verify MFA device is removed
echo "Verifying MFA device cleanup..."
aws iam list-mfa-devices \
  --user-name "$CURRENT_USER" \
  --output table

echo ""
echo "✅ Cleanup complete! All IAM roles, policies, MFA devices, and S3 resources have been removed."
```

---

## Key Takeaways
- **IAM Roles**: Use trust policies to define who/what can assume the role (EC2, cross-account, federated)
- **MFA Enforcement**: Require MFA for sensitive operations using condition keys (`aws:MultiFactorAuthPresent`)
- **Session Tokens**: Use `sts:GetSessionToken` with MFA to obtain temporary credentials
- **Assume Role**: Use `sts:AssumeRole` to switch to a different role with specific permissions
- **Console MFA**: Enforce MFA for console access by denying all actions except MFA setup without MFA
- **Least Privilege**: Always grant minimum necessary permissions and use MFA for privileged operations
- **Cleanup**: Always remove IAM resources, policies, and test buckets to avoid unnecessary costs

---

## Additional Resources
- [IAM Roles](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles.html)
- [Using MFA in AWS](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa.html)
- [AWS STS API Reference](https://docs.aws.amazon.com/STS/latest/APIReference/welcome.html)
- [IAM Policy Conditions](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html)

---
