# Lab 2.A: IAM Access Management and Custom Policies

## Overview
Hands-on lab to design and implement AWS Identity and Access Management (IAM) for least-privilege access. You will create users, groups, roles, policies (managed and inline), test permissions with the policy simulator, and apply permission boundaries and role trust policies.

## Objectives
- Create IAM users and groups with least-privilege policies
- Write and attach a custom managed policy (JSON)
- Create an IAM role with a trust policy for EC2
- Test effective permissions using aws iam simulate-principal-policy
- Apply permission boundaries and validate limits
- Follow IAM best practices (MFA, role-based access, no long-lived root keys)

## Prerequisites
- AWS CLI configured with an admin-capable profile
- jq installed for JSON manipulation (optional)
- Basic knowledge of IAM concepts (users, groups, roles, policies)

---

## Quick tips
- Use groups to grant permissions to multiple users.
- Prefer managed policies (customer-managed) over inline policies for reusability.
- Use roles (with instance profiles) for EC2 to avoid embedding credentials.
- Enforce MFA for privileged users and avoid using root account credentials.

---

## Steps (CLI examples)

Replace placeholders (e.g., ADMIN_PROFILE, YOUR_ACCOUNT_ID, YOUR_BUCKET_NAME, YOUR_IP/32).

### 1. Create groups and users
```bash
# create group
aws iam create-group --group-name lab-developers --profile ADMIN_PROFILE

# create users and add to group
aws iam create-user --user-name alice --profile ADMIN_PROFILE
aws iam create-user --user-name bob --profile ADMIN_PROFILE
aws iam add-user-to-group --user-name alice --group-name lab-developers --profile ADMIN_PROFILE
aws iam add-user-to-group --user-name bob --group-name lab-developers --profile ADMIN_PROFILE
```

### 2. Create a customer-managed policy (least-privilege example)
Create policy JSON (saves as s3-read-only-lab.json):
```json
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
        "arn:aws:s3:::YOUR_BUCKET_NAME",
        "arn:aws:s3:::YOUR_BUCKET_NAME/*"
      ]
    }
  ]
}
```
Attach policy:
```bash
aws iam create-policy --policy-name LabS3ReadOnly --policy-document file://s3-read-only-lab.json --profile ADMIN_PROFILE
aws iam attach-group-policy --group-name lab-developers --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/LabS3ReadOnly --profile ADMIN_PROFILE
```

### 3. Create an EC2 role with trust policy and attach policy
Trust policy (ec2-trust.json):
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
Create role and attach managed policy:
```bash
aws iam create-role --role-name lab-ec2-role --assume-role-policy-document file://ec2-trust.json --profile ADMIN_PROFILE
# attach AmazonS3ReadOnlyAccess or custom policy
aws iam attach-role-policy --role-name lab-ec2-role --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess --profile ADMIN_PROFILE

# create instance profile and add role
aws iam create-instance-profile --instance-profile-name lab-ec2-instance-profile --profile ADMIN_PROFILE
aws iam add-role-to-instance-profile --instance-profile-name lab-ec2-instance-profile --role-name lab-ec2-role --profile ADMIN_PROFILE
```

### 4. Use inline policy for a single user (when appropriate)
```bash
cat > alice-inline.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ec2:DescribeInstances",
      "Resource": "*"
    }
  ]
}
EOF

aws iam put-user-policy --user-name alice --policy-name DescribeEC2Only --policy-document file://alice-inline.json --profile ADMIN_PROFILE
```

### 5. Apply a permission boundary to limit what a user or role can do
Permission boundary policy (boundary.json) — example denies S3 deletes:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Deny",
      "Action": "s3:DeleteObject",
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*"
    }
  ]
}
```
Create boundary and attach when creating user/role:
```bash
aws iam create-policy --policy-name LabPermissionBoundary --policy-document file://boundary.json --profile ADMIN_PROFILE
aws iam create-user --user-name limited-user --permissions-boundary arn:aws:iam::YOUR_ACCOUNT_ID:policy/LabPermissionBoundary --profile ADMIN_PROFILE
```

### 6. Simulate and validate permissions
Simulate principal policy to see effective permissions:
```bash
# simulate as group principal (use group ARN or user ARN)
aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::YOUR_ACCOUNT_ID:user/alice --action-names s3:DeleteObject s3:GetObject --resource-arns arn:aws:s3:::YOUR_BUCKET_NAME/* --profile ADMIN_PROFILE
```

### 7. Enforce MFA and rotate keys
- Enable MFA in Console or via CLI for privileged users.
- Avoid long-lived access keys; use IAM role sessions or temporary credentials.

---

## Validation Checklist
- [ ] Users created and added to groups
- [ ] Custom managed policy created and attached to group
- [ ] EC2 role created with correct trust policy and policies attached
- [ ] Inline policies used only where justified
- [ ] Permission boundary tested and enforced
- [ ] Policy simulator confirms expected allow/deny behavior
- [ ] MFA configured for admin users

## Cleanup
```bash
# Detach and delete policies, remove users/groups/roles (replace names/ARNs)
aws iam detach-group-policy --group-name lab-developers --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/LabS3ReadOnly --profile ADMIN_PROFILE
aws iam delete-policy --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/LabS3ReadOnly --profile ADMIN_PROFILE

aws iam remove-user-from-group --user-name alice --group-name lab-developers --profile ADMIN_PROFILE
aws iam delete-user --user-name alice --profile ADMIN_PROFILE
aws iam delete-user --user-name bob --profile ADMIN_PROFILE

aws iam remove-role-from-instance-profile --instance-profile-name lab-ec2-instance-profile --role-name lab-ec2-role --profile ADMIN_PROFILE
aws iam delete-instance-profile --instance-profile-name lab-ec2-instance-profile --profile ADMIN_PROFILE
aws iam detach-role-policy --role-name lab-ec2-role --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess --profile ADMIN_PROFILE
aws iam delete-role --role-name lab-ec2-role --profile ADMIN_PROFILE
```

## Summary
This lab teaches how to safely manage IAM entities and craft policies that enforce least privilege. Use groups and roles, prefer managed policies, validate with the policy simulator, and apply permission boundaries and MFA for a secure IAM posture
