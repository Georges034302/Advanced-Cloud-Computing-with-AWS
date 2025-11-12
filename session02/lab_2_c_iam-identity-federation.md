# Lab 2.C: IAM Identity Federation and Temporary Credentials

## Overview
This lab demonstrates how to implement AWS IAM identity federation using OpenID Connect (OIDC) to allow external identities to access AWS resources without creating IAM users. You will configure temporary security credentials using AWS STS for federated access, commonly used in CI/CD pipelines and web applications.

---

## Objectives
- Set up OIDC identity provider in AWS IAM
- Create IAM roles with OIDC trust policies for federated access
- Configure GitHub Actions integration with AWS using OIDC
- Use `sts:AssumeRoleWithWebIdentity` for temporary credentials
- Implement session tags for attribute-based access control (ABAC)
- Test federated access with various conditions
- Audit federated access using CloudTrail

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions to create identity providers, roles, and policies
- GitHub account (for OIDC federation example)
- Basic understanding of OIDC/OAuth 2.0 concepts
- jq installed for JSON parsing

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

# Set bucket name for federation testing
BUCKET_NAME="federation-test-bucket-${ACCOUNT_ID}"
echo "BUCKET_NAME=$BUCKET_NAME"

# Set GitHub repository details (replace with your repo)
GITHUB_ORG="YourGitHubOrg"
echo "GITHUB_ORG=$GITHUB_ORG"

GITHUB_REPO="YourRepo"
echo "GITHUB_REPO=$GITHUB_REPO"

# Verify AWS CLI is configured
aws sts get-caller-identity

# Check if jq is installed
which jq || echo "Warning: jq not installed (recommended for JSON parsing)"
```

---

## Step 2 – Create S3 Bucket for Testing

```bash
# Create S3 bucket for federation testing
aws s3api create-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

# Verify bucket creation
aws s3 ls | grep "$BUCKET_NAME"

# Upload test file
echo "Federation test file" > federation-test.txt

# Upload to S3
aws s3 cp federation-test.txt "s3://${BUCKET_NAME}/"

# Verify file upload
aws s3 ls "s3://${BUCKET_NAME}/"
```

---

## Step 3 – Create OIDC Identity Provider for GitHub

```bash
# Set GitHub OIDC provider URL
GITHUB_OIDC_URL="https://token.actions.githubusercontent.com"
echo "GITHUB_OIDC_URL=$GITHUB_OIDC_URL"

# Set GitHub OIDC thumbprint (GitHub's current certificate thumbprint)
# This is GitHub's certificate thumbprint as of 2024
GITHUB_THUMBPRINT="6938fd4d98bab03faadb97b34396831e3780aea1"
echo "GITHUB_THUMBPRINT=$GITHUB_THUMBPRINT"

# Create OIDC identity provider for GitHub Actions
aws iam create-open-id-connect-provider \
  --url "$GITHUB_OIDC_URL" \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list "$GITHUB_THUMBPRINT" \
  --tags Key=Purpose,Value=GitHubActions Key=Environment,Value=Lab

# Get the OIDC provider ARN
OIDC_PROVIDER_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
echo "OIDC_PROVIDER_ARN=$OIDC_PROVIDER_ARN"

# Verify OIDC provider was created
aws iam get-open-id-connect-provider \
  --open-id-connect-provider-arn "$OIDC_PROVIDER_ARN"

# List all OIDC providers
aws iam list-open-id-connect-providers \
  --output table
```

---

## Step 4 – Create IAM Role with OIDC Trust Policy

```bash
# Set role name for GitHub Actions
GITHUB_ROLE_NAME="GitHubActionsRole"
echo "GITHUB_ROLE_NAME=$GITHUB_ROLE_NAME"

# Create trust policy JSON for GitHub OIDC provider
# This allows GitHub Actions from your specific repo to assume the role
cat > github-oidc-trust.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "${OIDC_PROVIDER_ARN}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_ORG}/${GITHUB_REPO}:*"
        }
      }
    }
  ]
}
EOF

# Display the trust policy
cat github-oidc-trust.json

# Create the IAM role with OIDC trust policy
aws iam create-role \
  --role-name "$GITHUB_ROLE_NAME" \
  --assume-role-policy-document file://github-oidc-trust.json \
  --description "Role for GitHub Actions to access AWS resources via OIDC" \
  --tags Key=ManagedBy,Value=GitHubActions

# Verify role creation
aws iam get-role \
  --role-name "$GITHUB_ROLE_NAME" \
  --query 'Role.[RoleName,Arn,CreateDate]' \
  --output table

# Get role ARN
GITHUB_ROLE_ARN=$(aws iam get-role \
  --role-name "$GITHUB_ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)
echo "GITHUB_ROLE_ARN=$GITHUB_ROLE_ARN"
```

---

## Step 5 – Create and Attach Permissions Policy

```bash
# Set policy name
FEDERATION_POLICY_NAME="FederationS3AccessPolicy"
echo "FEDERATION_POLICY_NAME=$FEDERATION_POLICY_NAME"

# Create permissions policy JSON with least-privilege S3 access
cat > federation-s3-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowListBucket",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}"
    },
    {
      "Sid": "AllowObjectOperations",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/*"
    },
    {
      "Sid": "AllowSTSGetCallerIdentity",
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    }
  ]
}
EOF

# Display the policy document
cat federation-s3-policy.json

# Create the IAM policy
FEDERATION_POLICY_ARN=$(aws iam create-policy \
  --policy-name "$FEDERATION_POLICY_NAME" \
  --policy-document file://federation-s3-policy.json \
  --description "S3 access policy for federated identities" \
  --query 'Policy.Arn' \
  --output text)
echo "FEDERATION_POLICY_ARN=$FEDERATION_POLICY_ARN"

# Attach policy to the GitHub Actions role
aws iam attach-role-policy \
  --role-name "$GITHUB_ROLE_NAME" \
  --policy-arn "$FEDERATION_POLICY_ARN"

# Verify policy attachment
aws iam list-attached-role-policies \
  --role-name "$GITHUB_ROLE_NAME" \
  --output table
```

---

## Step 6 – Create Role with Session Tags Support (ABAC)

```bash
# Set ABAC role name
ABAC_ROLE_NAME="FederationABACRole"
echo "ABAC_ROLE_NAME=$ABAC_ROLE_NAME"

# Create trust policy with session tags support
cat > abac-trust.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "${OIDC_PROVIDER_ARN}"
      },
      "Action": [
        "sts:AssumeRoleWithWebIdentity",
        "sts:TagSession"
      ],
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_ORG}/${GITHUB_REPO}:*"
        }
      }
    }
  ]
}
EOF

# Display the trust policy
cat abac-trust.json

# Create the ABAC role
aws iam create-role \
  --role-name "$ABAC_ROLE_NAME" \
  --assume-role-policy-document file://abac-trust.json \
  --description "Role with ABAC support using session tags" \
  --max-session-duration 3600

# Verify role creation
aws iam get-role \
  --role-name "$ABAC_ROLE_NAME" \
  --query 'Role.[RoleName,Arn,CreateDate]' \
  --output table
```

---

## Step 7 – Create ABAC Policy Using Session Tags

```bash
# Set ABAC policy name
ABAC_POLICY_NAME="SessionTagBasedS3Access"
echo "ABAC_POLICY_NAME=$ABAC_POLICY_NAME"

# Create ABAC policy that uses session tags for access control
cat > abac-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowListAllBuckets",
      "Effect": "Allow",
      "Action": "s3:ListAllMyBuckets",
      "Resource": "*"
    },
    {
      "Sid": "AllowAccessBasedOnSessionTag",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::${BUCKET_NAME}",
        "arn:aws:s3:::${BUCKET_NAME}/*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:PrincipalTag/Environment": "\${aws:RequestTag/Environment}"
        }
      }
    },
    {
      "Sid": "AllowSTSGetCallerIdentity",
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    }
  ]
}
EOF

# Display the ABAC policy
cat abac-policy.json

# Create the ABAC policy
ABAC_POLICY_ARN=$(aws iam create-policy \
  --policy-name "$ABAC_POLICY_NAME" \
  --policy-document file://abac-policy.json \
  --description "ABAC policy using session tags for S3 access" \
  --query 'Policy.Arn' \
  --output text)
echo "ABAC_POLICY_ARN=$ABAC_POLICY_ARN"

# Attach ABAC policy to the role
aws iam attach-role-policy \
  --role-name "$ABAC_ROLE_NAME" \
  --policy-arn "$ABAC_POLICY_ARN"

# Verify policy attachment
aws iam list-attached-role-policies \
  --role-name "$ABAC_ROLE_NAME" \
  --output table
```

---

## Step 8 – Create Role for Web Application Federation

```bash
# Set web app role name
WEB_APP_ROLE_NAME="WebAppFederationRole"
echo "WEB_APP_ROLE_NAME=$WEB_APP_ROLE_NAME"

# Create generic OIDC trust policy for web applications
cat > webapp-trust.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "${OIDC_PROVIDER_ARN}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
EOF

# Display the trust policy
cat webapp-trust.json

# Create the web app role
aws iam create-role \
  --role-name "$WEB_APP_ROLE_NAME" \
  --assume-role-policy-document file://webapp-trust.json \
  --description "Role for web application federation" \
  --max-session-duration 7200

# Attach read-only S3 policy
aws iam attach-role-policy \
  --role-name "$WEB_APP_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Verify role creation
aws iam get-role \
  --role-name "$WEB_APP_ROLE_NAME" \
  --query 'Role.[RoleName,Arn,CreateDate]' \
  --output table
```

---

## Step 9 – Test Federation Configuration

```bash
# Display configuration summary
echo ""
echo "=========================================="
echo "Federation Configuration Summary"
echo "=========================================="
echo "OIDC Provider ARN: $OIDC_PROVIDER_ARN"
echo "GitHub Actions Role ARN: $GITHUB_ROLE_ARN"
echo "S3 Bucket: $BUCKET_NAME"
echo ""
echo "GitHub Actions Workflow Configuration:"
echo "=========================================="
cat <<'WORKFLOW'
name: AWS Federation Test

on:
  push:
    branches: [ main ]

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Configure AWS credentials from OIDC
        uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: arn:aws:iam::ACCOUNT_ID:role/GitHubActionsRole
          aws-region: ap-southeast-2
      
      - name: Test S3 access
        run: |
          aws sts get-caller-identity
          aws s3 ls s3://federation-test-bucket-ACCOUNT_ID/
WORKFLOW

echo ""
echo "Replace ACCOUNT_ID with: $ACCOUNT_ID"
```

---

## Step 10 – Simulate Federated Access (Manual Test)

```bash
# Note: This step simulates what GitHub Actions would do
# In production, GitHub Actions would provide the web identity token

echo "=========================================="
echo "Federation Access Simulation"
echo "=========================================="
echo ""
echo "To test federated access, you would:"
echo "1. Configure GitHub Actions workflow with the role ARN above"
echo "2. GitHub Actions obtains OIDC token from GitHub"
echo "3. AWS STS validates token and issues temporary credentials"
echo "4. GitHub Actions uses temporary credentials to access S3"
echo ""
echo "Example AssumeRoleWithWebIdentity flow:"
echo "=========================================="

# Display example STS assume role command (requires actual OIDC token)
cat <<'EXAMPLE'
# This is what happens behind the scenes:
# aws sts assume-role-with-web-identity \
#   --role-arn arn:aws:iam::ACCOUNT_ID:role/GitHubActionsRole \
#   --role-session-name github-actions-session \
#   --web-identity-token $GITHUB_OIDC_TOKEN \
#   --duration-seconds 3600

# Response includes temporary credentials:
# {
#   "Credentials": {
#     "AccessKeyId": "ASIA...",
#     "SecretAccessKey": "...",
#     "SessionToken": "...",
#     "Expiration": "2024-..."
#   },
#   "SubjectFromWebIdentityToken": "repo:org/repo:ref:refs/heads/main",
#   "AssumedRoleUser": {
#     "AssumedRoleId": "...",
#     "Arn": "arn:aws:sts::ACCOUNT_ID:assumed-role/GitHubActionsRole/..."
#   }
# }
EXAMPLE

echo ""
echo "Federation trust is now configured!"
```

---

## Step 11 – Enable CloudTrail for Federation Auditing

```bash
# Set CloudTrail trail name
TRAIL_NAME="federation-audit-trail"
echo "TRAIL_NAME=$TRAIL_NAME"

# Set CloudTrail S3 bucket name
CLOUDTRAIL_BUCKET="cloudtrail-logs-${ACCOUNT_ID}"
echo "CLOUDTRAIL_BUCKET=$CLOUDTRAIL_BUCKET"

# Create S3 bucket for CloudTrail logs
aws s3api create-bucket \
  --bucket "$CLOUDTRAIL_BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

# Create bucket policy for CloudTrail
cat > cloudtrail-bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AWSCloudTrailAclCheck",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudtrail.amazonaws.com"
      },
      "Action": "s3:GetBucketAcl",
      "Resource": "arn:aws:s3:::${CLOUDTRAIL_BUCKET}"
    },
    {
      "Sid": "AWSCloudTrailWrite",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudtrail.amazonaws.com"
      },
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::${CLOUDTRAIL_BUCKET}/AWSLogs/${ACCOUNT_ID}/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-acl": "bucket-owner-full-control"
        }
      }
    }
  ]
}
EOF

# Apply bucket policy
aws s3api put-bucket-policy \
  --bucket "$CLOUDTRAIL_BUCKET" \
  --policy file://cloudtrail-bucket-policy.json

# Create CloudTrail trail
aws cloudtrail create-trail \
  --name "$TRAIL_NAME" \
  --s3-bucket-name "$CLOUDTRAIL_BUCKET" \
  --is-multi-region-trail \
  --enable-log-file-validation

# Start logging
aws cloudtrail start-logging \
  --name "$TRAIL_NAME"

# Verify trail status
aws cloudtrail get-trail-status \
  --name "$TRAIL_NAME" \
  --output table

echo ""
echo "CloudTrail is now logging federated access events"
echo "Events to monitor: AssumeRoleWithWebIdentity, AssumeRole, GetCallerIdentity"
```

---

## Step 12 – Query Federation Events (Optional)

```bash
# Query recent AssumeRoleWithWebIdentity events
echo "Querying recent federation events..."

# Look up events from the last hour
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRoleWithWebIdentity \
  --max-results 10 \
  --query 'Events[*].[EventTime,Username,EventName,Resources[0].ResourceName]' \
  --output table

# Query for specific role assumptions
echo ""
echo "Querying role assumption events..."
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue="$GITHUB_ROLE_NAME" \
  --max-results 10 \
  --query 'Events[*].[EventTime,Username,EventName]' \
  --output table || echo "No events found yet"
```

---

## Step 13 – Test OIDC Provider Configuration

```bash
# Verify OIDC provider configuration
echo "Verifying OIDC provider configuration..."

# Get OIDC provider details
aws iam get-open-id-connect-provider \
  --open-id-connect-provider-arn "$OIDC_PROVIDER_ARN" \
  --query '{URL:Url,ClientIDList:ClientIDList,ThumbprintList:ThumbprintList,CreateDate:CreateDate}' \
  --output table

# List all roles that trust this OIDC provider
echo ""
echo "Roles trusting this OIDC provider:"
aws iam list-roles \
  --query "Roles[?contains(AssumeRolePolicyDocument.Statement[0].Principal.Federated, 'oidc-provider')].{RoleName:RoleName,CreateDate:CreateDate}" \
  --output table
```

---

## Step 14 – Create Documentation for Team

```bash
# Generate documentation file
cat > FEDERATION_SETUP.md <<EOF
# AWS Federation Setup Documentation

## Overview
This document describes the OIDC federation setup for AWS access.

## Configuration Details

### OIDC Provider
- **Provider URL**: $GITHUB_OIDC_URL
- **Provider ARN**: $OIDC_PROVIDER_ARN
- **Audience**: sts.amazonaws.com

### IAM Roles

#### GitHub Actions Role
- **Role Name**: $GITHUB_ROLE_NAME
- **Role ARN**: $GITHUB_ROLE_ARN
- **Purpose**: Allows GitHub Actions workflows to access AWS
- **Permissions**: S3 read/write access to $BUCKET_NAME

#### ABAC Role
- **Role Name**: $ABAC_ROLE_NAME
- **Purpose**: Demonstrates attribute-based access control with session tags
- **Permissions**: S3 access based on session tag matching

#### Web App Role
- **Role Name**: $WEB_APP_ROLE_NAME
- **Purpose**: Read-only S3 access for web applications
- **Permissions**: Amazon S3 Read-Only Access

## Usage Instructions

### GitHub Actions Workflow

\`\`\`yaml
permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    steps:
      - uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: $GITHUB_ROLE_ARN
          aws-region: $REGION
\`\`\`

### Testing Access

\`\`\`bash
# Verify identity
aws sts get-caller-identity

# List S3 bucket
aws s3 ls s3://$BUCKET_NAME/
\`\`\`

## Security Notes
- Temporary credentials expire after 1 hour (3600 seconds)
- All federation events are logged in CloudTrail
- Trust policies restrict access to specific GitHub repositories

## Monitoring
- CloudTrail Trail: $TRAIL_NAME
- CloudTrail S3 Bucket: $CLOUDTRAIL_BUCKET
- Monitor events: AssumeRoleWithWebIdentity

---
Generated: $(date)
EOF

echo "Documentation created: FEDERATION_SETUP.md"
cat FEDERATION_SETUP.md
```

---

## Step 15 – Cleanup Resources

```bash
# Stop CloudTrail logging
echo "Stopping CloudTrail logging..."
aws cloudtrail stop-logging \
  --name "$TRAIL_NAME" || true

# Delete CloudTrail trail
echo "Deleting CloudTrail trail..."
aws cloudtrail delete-trail \
  --name "$TRAIL_NAME" || true

# Detach and delete policies from roles
echo "Detaching policies from roles..."

# GitHub Actions Role
aws iam detach-role-policy \
  --role-name "$GITHUB_ROLE_NAME" \
  --policy-arn "$FEDERATION_POLICY_ARN" || true

# ABAC Role
aws iam detach-role-policy \
  --role-name "$ABAC_ROLE_NAME" \
  --policy-arn "$ABAC_POLICY_ARN" || true

# Web App Role
aws iam detach-role-policy \
  --role-name "$WEB_APP_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess || true

# Delete IAM roles
echo "Deleting IAM roles..."
aws iam delete-role \
  --role-name "$GITHUB_ROLE_NAME" || true

aws iam delete-role \
  --role-name "$ABAC_ROLE_NAME" || true

aws iam delete-role \
  --role-name "$WEB_APP_ROLE_NAME" || true

# Delete custom policies
echo "Deleting custom policies..."
aws iam delete-policy \
  --policy-arn "$FEDERATION_POLICY_ARN" || true

aws iam delete-policy \
  --policy-arn "$ABAC_POLICY_ARN" || true

# Delete OIDC provider
echo "Deleting OIDC provider..."
aws iam delete-open-id-connect-provider \
  --open-id-connect-provider-arn "$OIDC_PROVIDER_ARN" || true

# Empty and delete S3 buckets
echo "Emptying and deleting S3 buckets..."
aws s3 rm "s3://${BUCKET_NAME}" --recursive || true
aws s3 rb "s3://${BUCKET_NAME}" || true

aws s3 rm "s3://${CLOUDTRAIL_BUCKET}" --recursive || true
aws s3 rb "s3://${CLOUDTRAIL_BUCKET}" || true

# Delete local files
echo "Cleaning up local files..."
rm -f github-oidc-trust.json \
  federation-s3-policy.json \
  abac-trust.json \
  abac-policy.json \
  webapp-trust.json \
  cloudtrail-bucket-policy.json \
  federation-test.txt \
  FEDERATION_SETUP.md

# Verify cleanup
echo ""
echo "Verifying cleanup..."

# Check OIDC providers
aws iam list-open-id-connect-providers \
  --query 'OpenIDConnectProviderList[?contains(Arn,`token.actions.githubusercontent.com`)]' \
  --output table || echo "OIDC provider deleted"

# Check roles
aws iam list-roles \
  --query "Roles[?RoleName=='$GITHUB_ROLE_NAME' || RoleName=='$ABAC_ROLE_NAME' || RoleName=='$WEB_APP_ROLE_NAME'].RoleName" \
  --output table || echo "Roles deleted"

# Check S3 buckets
aws s3 ls | grep -E "${BUCKET_NAME}|${CLOUDTRAIL_BUCKET}" || echo "S3 buckets deleted"

echo ""
echo "✅ Cleanup complete! All federation resources have been removed."
```

---

## Summary

In this lab, you have:
- Created an OIDC identity provider for GitHub Actions federation
- Configured IAM roles with OIDC trust policies for federated access
- Implemented least-privilege permissions for federated identities
- Set up attribute-based access control (ABAC) using session tags
- Created multiple federation patterns (GitHub Actions, web apps)
- Enabled CloudTrail logging for federation audit trails
- Generated documentation for team usage
- Successfully cleaned up all federation infrastructure

**Key Takeaways:**
- **No IAM Users Needed**: Federated identities eliminate the need for long-lived credentials
- **Temporary Credentials**: STS provides short-lived credentials that auto-expire
- **Trust Policies**: Define who can assume roles using OIDC conditions
- **ABAC with Session Tags**: Enable fine-grained access control based on attributes
- **CI/CD Integration**: Perfect for GitHub Actions, GitLab CI, and other pipelines
- **Audit Trail**: CloudTrail logs all federation activities for compliance
- **Least Privilege**: Each federated identity gets only the permissions it needs

**Real-World Use Cases:**
- GitHub Actions workflows deploying to AWS
- Web/mobile applications accessing AWS services
- Cross-account access without creating IAM users
- Enterprise SSO integration with SAML 2.0
- Third-party SaaS integrations requiring AWS access

---

## Additional Resources
- [IAM OIDC Identity Providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
- [AssumeRoleWithWebIdentity API](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html)
- [GitHub Actions OIDC with AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [Session Tags for ABAC](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_session-tags.html)
- [CloudTrail Event History](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/view-cloudtrail-events.html)

---
