# Lab 2.B: Configure IAM roles and MFA for secure access to AWS services

## Overview
This lab shows how to create and configure IAM roles for cross-account or service access, require MFA for privileged operations, and validate role assumption and MFA enforcement using the AWS CLI and console.

## Objectives
- Create IAM roles with proper trust policies (EC2, cross-account, federated)
- Attach least-privilege managed or customer-managed policies to roles
- Require and enforce MFA for sensitive actions using IAM policies
- Use sts:AssumeRole and sts:GetSessionToken with MFA
- Test and validate role-based and MFA-protected access
- Clean up IAM artifacts

## Prerequisites
- AWS CLI v2 configured with an admin-capable profile (ADMIN_PROFILE)
- jq (optional) for JSON handling
- Browser access for console MFA setup

---

## Key concepts (brief)
- Role = identity you can assume (has policies + trust policy)
- Trust policy = which principals can assume the role
- Permission boundary = maximum permissions a principal can obtain
- MFA enforcement = require an MFA device/session for sensitive actions

---

## Steps (CLI examples)

Replace placeholders: ADMIN_PROFILE, YOUR_ACCOUNT_ID, TRUSTED_ACCOUNT_ID, ALLOWED_S3_BUCKET, MFA_SERIAL (e.g., arn:aws:iam::YOUR_ACCOUNT_ID:mfa/your-user).

### 1. Create an IAM role for EC2 (trusting EC2 service)
trust-ec2.json:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Create role and attach policy (example: S3 read-only):
```bash
aws iam create-role --role-name lab-ec2-role --assume-role-policy-document file://trust-ec2.json --profile ADMIN_PROFILE
aws iam attach-role-policy --role-name lab-ec2-role --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess --profile ADMIN_PROFILE
aws iam create-instance-profile --instance-profile-name lab-ec2-instance-profile --profile ADMIN_PROFILE
aws iam add-role-to-instance-profile --instance-profile-name lab-ec2-instance-profile --role-name lab-ec2-role --profile ADMIN_PROFILE
```

### 2. Create a cross-account role (trusted account can assume)
cross-trust.json (replace TRUSTED_ACCOUNT_ID):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::TRUSTED_ACCOUNT_ID:root" },
      "Action": "sts:AssumeRole",
      "Condition": {}
    }
  ]
}
```
Create role and attach policy:
```bash
aws iam create-role --role-name cross-account-readonly --assume-role-policy-document file://cross-trust.json --profile ADMIN_PROFILE
aws iam attach-role-policy --role-name cross-account-readonly --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess --profile ADMIN_PROFILE
```

### 3. Require MFA for sensitive operations (example policy)
This policy denies s3:DeleteObject unless MFA is present in the session:
mfa-required-delete.json:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyS3DeleteWithoutMFA",
      "Effect": "Deny",
      "Action": "s3:DeleteObject",
      "Resource": "arn:aws:s3:::ALLOWED_S3_BUCKET/*",
      "Condition": {
        "Bool": { "aws:MultiFactorAuthPresent": "false" }
      }
    }
  ]
}
```
Attach as a customer-managed policy to the privileged group or role:
```bash
aws iam create-policy --policy-name RequireMFAForS3Delete --policy-document file://mfa-required-delete.json --profile ADMIN_PROFILE
aws iam attach-role-policy --role-name lab-ec2-role --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/RequireMFAForS3Delete --profile ADMIN_PROFILE
```

### 4. Setup MFA for a user (Console recommended)
- Console: IAM → Users → Select user → Security credentials → Manage MFA device → Assign virtual MFA (e.g., Authenticator app).
- Note the MFA ARN (MFA_SERIAL) for CLI use.

### 5. Obtain MFA session credentials and test actions
Get session token with MFA:
```bash
aws sts get-session-token --serial-number MFA_SERIAL --token-code 123456 --duration-seconds 3600 --profile ADMIN_PROFILE
# Use returned AccessKeyId/SecretAccessKey/SessionToken in environment or a temporary profile to test MFA enforced actions
```

Assume a role with MFA requirement (if trust policy + condition require MFA):
```bash
aws sts assume-role --role-arn arn:aws:iam::YOUR_ACCOUNT_ID:role/cross-account-readonly --role-session-name test --serial-number MFA_SERIAL --token-code 123456 --profile ADMIN_PROFILE
```

Validate you cannot perform denied actions without MFA, and can after obtaining MFA session credentials.

### 6. Example: Enforce MFA-only for Console Sign-in to AWS Management Console
Attach this managed policy to a group or user to require MFA for console actions (example snippet):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RequireMFAForConsole",
      "Effect": "Deny",
      "Action": "aws-portal:*",
      "Resource": "*",
      "Condition": { "Bool": { "aws:MultiFactorAuthPresent": "false" } }
    }
  ]
}
```
Apply carefully — test with a separate admin to avoid lockout.

---

## Validation Checklist
- [ ] EC2 role created and instance profile attached
- [ ] Cross-account role created with correct trust policy
- [ ] MFA device configured for user(s)
- [ ] MFA-enforcement policy attached and validated (denies without MFA)
- [ ] sts:GetSessionToken and sts:AssumeRole workflows tested successfully
- [ ] Permission boundaries and least privilege verified

## Cleanup
```bash
# Detach and delete policies and roles (replace names/arns)
aws iam remove-role-from-instance-profile --instance-profile-name lab-ec2-instance-profile --role-name lab-ec2-role --profile ADMIN_PROFILE || true
aws iam delete-instance-profile --instance-profile-name lab-ec2-instance-profile --profile ADMIN_PROFILE || true
aws iam detach-role-policy --role-name lab-ec2-role --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess --profile ADMIN_PROFILE || true
aws iam delete-role --role-name lab-ec2-role --profile ADMIN_PROFILE || true

aws iam detach-role-policy --role-name cross-account-readonly --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess --profile ADMIN_PROFILE || true
aws iam delete-role --role-name cross-account-readonly --profile ADMIN_PROFILE || true

# Delete custom policies
aws iam delete-policy --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/RequireMFAForS3Delete --profile ADMIN_PROFILE || true
```

## Summary
This lab configures roles and MFA to enforce secure, role-based access patterns. Use least privilege, test MFA enforcement thoroughly, and avoid policies that risk locking out administrators
